import sys
import queue
import threading
import asyncio
import subprocess
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QTextEdit, QPushButton, QLabel, QFrame, QScrollArea, QToolButton, QMessageBox
)
from PyQt5.QtCore import Qt, QUrl, QTimer, pyqtSignal
from PyQt5.QtGui import QFont, QPixmap
from PyQt5.QtMultimedia import QSoundEffect
import os
from magentic_flow_worker import userQueue, botQueue, magentic_flow_worker  # Import the queues from external worker

###############################################################################
# Worker Thread Launch
###############################################################################
def start_magentic_flow_worker():
    """
    Launch the external worker in a background thread so our PyQt main thread is free.
    """
    worker_thread = threading.Thread(target=magentic_flow_worker, daemon=True)
    worker_thread.start()
    return worker_thread

###############################################################################
# Launch Playwright Chromium in a separate thread using asyncio.run
###############################################################################
def spawn_playwright_chromium_in_thread(x, y, width, height):
    """
    Spawns a new thread that runs an asyncio event loop, launching Chromium
    positioned at (x, y) with size (width, height).
    """
    def run_chromium():
        asyncio.run(launch_chromium_on_right(x, y, width, height))
    t = threading.Thread(target=run_chromium, daemon=True)
    t.start()

async def launch_chromium_on_right(x, y, width, height):
    """
    Actually run asynchronous playwright code in the new thread's event loop.
    """
    from playwright.async_api import async_playwright
    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=False,
            args=[
                f"--window-position={x},{y}",
                f"--window-size={width},{height}"
            ]
        )
        context = await browser.new_context()
        page = await context.new_page()
        await page.goto("https://www.google.com")
        # Keep the browser alive
        while True:
            await asyncio.sleep(0.2)

###############################################################################
# ChatBubble: single-line, no wrapping
###############################################################################
class ChatBubble(QWidget):
    def __init__(self, avatar_path: str, name: str, message: str, parent=None):
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 5, 10, 5)
        layout.setSpacing(8)

        avatar_label = QLabel()
        avatar_label.setFixedSize(40, 40)
        avatar_label.setScaledContents(True)
        pix = QPixmap(avatar_path)
        if not pix.isNull():
            pix = pix.scaled(40, 40, Qt.KeepAspectRatio, Qt.SmoothTransformation)
        avatar_label.setPixmap(pix)
        layout.addWidget(avatar_label)

        msg_layout = QVBoxLayout()
        text_label = QLabel(message)
        text_label.setWordWrap(False)
        msg_layout.addWidget(text_label, alignment=Qt.AlignLeft)
        layout.addLayout(msg_layout)

###############################################################################
# Multi-line Text Input with Enter-to-send (via signal)
###############################################################################
class MyTextEdit(QTextEdit):
    sendSignal = pyqtSignal()
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setPlaceholderText("Type a message (Press Enter to send, Shift+Enter for new line)")
        self.setFixedHeight(80)

    def keyPressEvent(self, event):
        if event.key() in (Qt.Key_Return, Qt.Key_Enter) and not (event.modifiers() & Qt.ShiftModifier):
            self.sendSignal.emit()
            event.accept()
        else:
            super().keyPressEvent(event)

###############################################################################
# Main Chatbot Window
###############################################################################
class BotWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Side-by-Side Chat + Chromium via External Worker")
        # Create external worker for queues
        self.worker_thread = start_magentic_flow_worker()

        # Avatars
        self.user_avatar = "user_avatar.png"
        self.bot_avatar  = "bot_avatar.png"

        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        layout = QVBoxLayout(main_widget)

        # Heading
        heading_frame = QFrame()
        heading_frame.setObjectName("headingFrame")
        heading_layout = QVBoxLayout(heading_frame)
        heading_layout.setContentsMargins(10,10,10,10)
        heading_label = QLabel("Chat Left, Chromium Right (External Worker)")
        heading_label.setFont(QFont("Arial", 24, QFont.Bold))
        heading_label.setAlignment(Qt.AlignCenter)
        heading_layout.addWidget(heading_label)
        layout.addWidget(heading_frame, 0)

        # Scroll area
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        layout.addWidget(self.scroll_area, 1)

        self.chat_container = QWidget()
        self.chat_layout = QVBoxLayout(self.chat_container)
        self.chat_layout.setAlignment(Qt.AlignTop)
        self.chat_container.setLayout(self.chat_layout)
        self.scroll_area.setWidget(self.chat_container)

        # Welcome bubble
        self.show_welcome_bubble()

        # Input row
        input_row = QHBoxLayout()
        self.input_field = MyTextEdit()
        self.input_field.sendSignal.connect(self.send_message)
        input_row.addWidget(self.input_field)

        self.help_button = QToolButton()
        self.help_button.setText("?")
        self.help_button.setFixedSize(40, 40)
        self.help_button.clicked.connect(self.show_help_dialog)
        input_row.addWidget(self.help_button)

        self.new_task_button = QPushButton("New Task")
        self.new_task_button.setStyleSheet("background-color: #3CB371; color: white; padding: 6px;")
        self.new_task_button.clicked.connect(self.reset_chat)
        input_row.addWidget(self.new_task_button)

        layout.addLayout(input_row)

        send_layout = QHBoxLayout()
        self.send_button = QPushButton("Send")
        self.send_button.setObjectName("sendButton")
        self.send_button.clicked.connect(self.send_message)
        send_layout.addWidget(self.send_button)
        layout.addLayout(send_layout)

        self.sound_effect = QSoundEffect()
        wav_path = "notification.wav"
        if os.path.exists(wav_path):
            self.sound_effect.setSource(QUrl.fromLocalFile(wav_path))
        else:
            self.sound_effect = None

        # QTimer to poll botQueue
        self.poll_timer = QTimer(self)
        self.poll_timer.timeout.connect(self.poll_bot_queue)
        self.poll_timer.start(200)

        self.setStyleSheet("""
            * {
                font-size: 20px;
            }
            QMainWindow {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #f0f0f0, stop:1 #e0e0e0);
            }
            #headingFrame {
                background-color: #aaaaaa;
            }
            QTextEdit {
                font-size: 20px;
            }
            QPushButton {
                font-size: 20px;
                color: white;
                background-color: #2E8B57;
                border-radius: 8px;
                padding: 6px;
            }
            QPushButton#sendButton {
                background-color: #008CBA;
            }
            QPushButton:hover {
                opacity: 0.8;
            }
        """)

    def show_welcome_bubble(self):
        welcome_text = "👋 Hello, I'm the left-side Chatbot. The external worker logic handles the 2 queues."
        bubble = ChatBubble(self.bot_avatar, "Bot", welcome_text)
        bubble.setMaximumWidth(int(self.width() * 0.9))
        self.chat_layout.addWidget(bubble)

    def show_help_dialog(self):
        QMessageBox.information(self, "Help",
            "Left side: PyQt chatbot. Right side: Playwright Chromium.\n"
            "External worker handles userQueue -> botQueue in magentic_flow_worker.py."
        )

    def send_message(self):
        user_text = self.input_field.toPlainText().strip()
        if not user_text:
            return
        bubble = ChatBubble(self.user_avatar, "You", user_text)
        bubble.setMaximumWidth(int(self.width() * 0.9))
        self.chat_layout.addWidget(bubble)
        self.input_field.clear()

        # Send to external worker's userQueue
        userQueue.put(("You", user_text))

        self.scroll_area.verticalScrollBar().setValue(
            self.scroll_area.verticalScrollBar().maximum()
        )

    def poll_bot_queue(self):
        while not botQueue.empty():
            msg = botQueue.get_nowait()
            bubble = ChatBubble(self.bot_avatar, "Bot", msg)
            bubble.setMaximumWidth(int(self.width() * 0.9))
            self.chat_layout.addWidget(bubble)
            if self.sound_effect:
                self.sound_effect.play()
            self.scroll_area.verticalScrollBar().setValue(
                self.scroll_area.verticalScrollBar().maximum()
            )

    def reset_chat(self):
        while self.chat_layout.count():
            item = self.chat_layout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()
        self.show_welcome_bubble()

    def showEvent(self, event):
        super().showEvent(event)
        desktop = QApplication.desktop()
        screen_rect = desktop.availableGeometry(self)

        # Place PyQt window on the left half
        half_width = int(screen_rect.width() / 2)
        top_margin = 50
        bottom_margin = 50
        window_height = screen_rect.height() - (top_margin + bottom_margin)

        self.setGeometry(0, top_margin, half_width, window_height)
        self.setFixedSize(half_width, window_height)

        # Launch Playwright Chromium in a separate thread with an asyncio loop
        x_right = half_width
        y_right = top_margin
        width_right = half_width
        height_right = window_height
        spawn_playwright_chromium_in_thread(x_right, y_right, width_right, height_right)

###############################
# Main
###############################
if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = BotWindow()
    window.show()
    sys.exit(app.exec_())
