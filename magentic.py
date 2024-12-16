import sys
import time
import random
import queue
import threading
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QTextEdit, QPushButton, QLabel, QFrame, QScrollArea, QToolButton, QMessageBox
)
from PyQt5.QtCore import Qt, QUrl, QTimer, pyqtSignal
from PyQt5.QtGui import QFont, QPixmap
from PyQt5.QtMultimedia import QSoundEffect
import os

# -----------------------------
# GLOBAL QUEUES
# -----------------------------
userQueue = queue.Queue()  # sender queue for user's messages
botQueue = queue.Queue()   # receiver queue for bot messages

# -----------------------------
# Worker Thread (Magentic Flow)
# This continuously processes userQueue items,
# simulates multi-step replies with a delay,
# and enqueues each step into botQueue.
# -----------------------------
def magentic_flow_worker():
    """
    Runs in a background thread, handles the 'magentic flow'.
    Pulls user messages from userQueue,
    simulates multi-step logic,
    places each step's result into botQueue.
    """
    while True:
        username, message = userQueue.get()  # block until a user msg is available
        if message is None:
            # If we push None as a sentinel, we can break the loop or do cleanup
            break

        # Simulate multi-step logic with 1 second delay per step
        steps = [
            f"Parsing your request: '{message}'",
            "Validating payment details...",
            "Repairing transaction records...",
            "Verifying final statuses...",
            "Payment repair completed successfully!"
        ]
        emoji_list = ["🤖", "💡", "🔧", "✅", "✨", "📁", "🕑"]

        for step in steps:
            time.sleep(1)  # 1s delay per step
            # Compose a single-line reply without wrapping
            reply = f"{random.choice(emoji_list)} {step}"
            botQueue.put(reply)  # enqueue to botQueue

# We spawn the worker thread once
worker_thread = threading.Thread(target=magentic_flow_worker, daemon=True)
worker_thread.start()

# -----------------------------
# ChatBubble: single-line, no wrapping
# -----------------------------
class ChatBubble(QWidget):
    """
    Left-aligned bubble with an avatar + single-line message (no wrapping).
    """
    def __init__(self, avatar_path: str, name: str, message: str, parent=None):
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 5, 10, 5)
        layout.setSpacing(8)

        # Avatar
        avatar_label = QLabel()
        avatar_label.setFixedSize(40, 40)
        avatar_label.setScaledContents(True)
        pix = QPixmap(avatar_path)
        if not pix.isNull():
            pix = pix.scaled(40, 40, Qt.KeepAspectRatio, Qt.SmoothTransformation)
        avatar_label.setPixmap(pix)
        layout.addWidget(avatar_label)

        # Single-line message only
        msg_layout = QVBoxLayout()
        text_label = QLabel(message)
        text_label.setWordWrap(False)  # no wrapping
        msg_layout.addWidget(text_label, alignment=Qt.AlignLeft)
        layout.addLayout(msg_layout)

# -----------------------------
# Multi-line Text Input with Enter-to-send (via signal)
# -----------------------------
class MyTextEdit(QTextEdit):
    sendSignal = pyqtSignal()  # custom signal for "Send"

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setPlaceholderText("Type a message (Press Enter to send, Shift+Enter for new line)")
        self.setFixedHeight(80)

    def keyPressEvent(self, event):
        if event.key() in (Qt.Key_Return, Qt.Key_Enter) and not (event.modifiers() & Qt.ShiftModifier):
            # Press Enter (without Shift) => emit the send signal
            self.sendSignal.emit()
            event.accept()
        else:
            super().keyPressEvent(event)

# -----------------------------
# Main Chatbot Window
# -----------------------------
class BotWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("TachyonCrew")
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
        heading_label = QLabel("TachyonCrew")
        heading_label.setFont(QFont("Arial", 24, QFont.Bold))
        heading_label.setAlignment(Qt.AlignCenter)
        heading_layout.addWidget(heading_label)
        layout.addWidget(heading_frame, 0)

        # Scroll area for chat
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        layout.addWidget(self.scroll_area, 1)

        self.chat_container = QWidget()
        self.chat_layout = QVBoxLayout(self.chat_container)
        self.chat_layout.setAlignment(Qt.AlignTop)
        self.chat_container.setLayout(self.chat_layout)
        self.scroll_area.setWidget(self.chat_container)

        # Create a default welcome bubble
        self.show_welcome_bubble()

        # Input row
        input_row = QHBoxLayout()

        self.input_field = MyTextEdit()
        # Connect the custom signal to this window's send_message method
        self.input_field.sendSignal.connect(self.send_message)
        input_row.addWidget(self.input_field)

        # Help button
        self.help_button = QToolButton()
        self.help_button.setText("?")
        self.help_button.setFixedSize(40, 40)
        self.help_button.setToolTip("Multi-step flow using two queues (userQueue, botQueue).")
        input_row.addWidget(self.help_button)
        self.help_button.clicked.connect(self.show_help_dialog)

        # New Task button
        self.new_task_button = QPushButton("New Task")
        self.new_task_button.setStyleSheet("background-color: #3CB371; color: white; padding: 6px;")
        self.new_task_button.clicked.connect(self.reset_chat)
        input_row.addWidget(self.new_task_button)

        layout.addLayout(input_row)

        # Send button
        send_layout = QHBoxLayout()
        self.send_button = QPushButton("Send")
        self.send_button.setObjectName("sendButton")
        self.send_button.clicked.connect(self.send_message)
        send_layout.addWidget(self.send_button)
        layout.addLayout(send_layout)

        # Sound effect
        self.sound_effect = QSoundEffect()
        wav_path = "notification.wav"
        if os.path.exists(wav_path):
            self.sound_effect.setSource(QUrl.fromLocalFile(wav_path))
        else:
            self.sound_effect = None

        # QTimer to poll botQueue
        self.poll_timer = QTimer(self)
        self.poll_timer.timeout.connect(self.poll_bot_queue)
        self.poll_timer.start(200)  # check botQueue every 200ms

        self.setStyleSheet("""
            * {
                font-size: 20px;
            }
            QMainWindow {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #f0f0f0, stop:1 #e0e0e0);
            }
            #headingFrame {
                background-color: #aaaaaa; /* grey heading BG */
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
        """Show static welcome bubble."""
        welcome_text = "👋 Hello, I'm the Magentic Flow Bot!\n✨ I can handle tasks like 'repair payment messages' and more. ✨"

        bubble = ChatBubble(self.bot_avatar, "Bot", welcome_text)
        #bubble.setMaximumWidth(int(self.width() * 0.9))
        self.chat_layout.addWidget(bubble)

    def show_help_dialog(self):
        QMessageBox.information(self, "Help",
            "You can ask me tasks like:\n"
            "- 'repair payment messages'\n"
            "- 'validate logs'\n"
            "- 'export data'\n"
            "or anything else you need!"
        )

    def send_message(self):
        user_text = self.input_field.toPlainText().strip()
        if not user_text:
            return

        # Add user bubble
        bubble = ChatBubble(self.user_avatar, "You", user_text)
        bubble.setMaximumWidth(int(self.width() * 0.9))
        self.chat_layout.addWidget(bubble)
        self.input_field.clear()

        # Put user message in userQueue
        userQueue.put(("You", user_text))

        # Scroll down
        self.scroll_area.verticalScrollBar().setValue(
            self.scroll_area.verticalScrollBar().maximum()
        )

    def poll_bot_queue(self):
        """
        Called every 200ms by a QTimer to check for new bot messages in botQueue.
        If found, display them in the chat.
        """
        while not botQueue.empty():
            msg = botQueue.get_nowait()
            # Show a single-line bubble from Bot
            bubble = ChatBubble(self.bot_avatar, "Bot", msg)
            bubble.setMaximumWidth(int(self.width() * 0.9))
            self.chat_layout.addWidget(bubble)
            
            if self.sound_effect:
                self.sound_effect.play()

            self.scroll_area.verticalScrollBar().setValue(
                self.scroll_area.verticalScrollBar().maximum()
            )

    def reset_chat(self):
        # Clear the chat
        while self.chat_layout.count():
            item = self.chat_layout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()

        # Show welcome bubble again
        self.show_welcome_bubble()

    def showEvent(self, event):
        super().showEvent(event)
        desktop = QApplication.desktop()
        screen_rect = desktop.availableGeometry(self)
        
        fixed_width = 900
        top_margin = 50
        bottom_margin = 50
        window_height = screen_rect.height() - (top_margin + bottom_margin)
        
        self.setGeometry(0, top_margin, fixed_width, window_height)
        self.setFixedSize(fixed_width, window_height)

###############################
# Main Entry
###############################
if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = BotWindow()
    window.show()
    sys.exit(app.exec_())
