import sys
import queue
import threading
import asyncio
import os
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QTextEdit, QPushButton, QLabel, QFrame, QScrollArea, QToolButton, QMessageBox, QDialog
)
from PyQt5.QtCore import Qt, QUrl, QTimer, pyqtSignal
from PyQt5.QtGui import QFont, QPixmap
from PyQt5.QtMultimedia import QSoundEffect
from magentic_flow_worker import userQueue, botQueue, magentic_flow_worker

# Worker Thread
def start_magentic_flow_worker():
    worker_thread = threading.Thread(target=magentic_flow_worker, daemon=True)
    worker_thread.start()
    return worker_thread

# ChatBubble Class
class ChatBubble(QWidget):
    def __init__(self, avatar_path: str, message: str, image_path: str = None, is_bot=False, parent=None):
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 5, 10, 5)
        layout.setSpacing(8)

        avatar_label = QLabel()
        avatar_label.setFixedSize(30, 30)
        pix = QPixmap(avatar_path).scaled(30, 30, Qt.KeepAspectRatio, Qt.SmoothTransformation)
        avatar_label.setPixmap(pix)
        layout.addWidget(avatar_label)

        bubble_layout = QVBoxLayout()
        text_label = QLabel(message)
        text_label.setWordWrap(True)
        text_label.setStyleSheet(f"""
            QLabel {{
                background-color: {"#FFCC80" if not is_bot else "#FFF3E0"};
                border-radius: 12px;
                padding: 10px;
            }}
        """)
        bubble_layout.addWidget(text_label, alignment=Qt.AlignLeft)

        if image_path:
            image_label = QLabel()
            image_label.setPixmap(QPixmap(image_path).scaled(200, 150, Qt.KeepAspectRatio))
            image_label.setCursor(Qt.PointingHandCursor)
            image_label.mousePressEvent = lambda event: self.zoom_image(image_path)
            bubble_layout.addWidget(image_label, alignment=Qt.AlignLeft)

        layout.addLayout(bubble_layout)

    def zoom_image(self, image_path):
        zoom_dialog = QDialog(self)
        zoom_dialog.setWindowTitle("Zoomed Image")
        zoom_layout = QVBoxLayout(zoom_dialog)
        image_label = QLabel()
        image_label.setPixmap(QPixmap(image_path).scaled(600, 400, Qt.KeepAspectRatio))
        zoom_layout.addWidget(image_label)
        zoom_dialog.exec_()

# Loading Dots Animation
class LoadingDots(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.dot_label = QLabel("Bot is typing")
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.animate)
        self.dots = ""
        self.timer.start(500)
        layout = QHBoxLayout(self)
        layout.addWidget(self.dot_label)

    def animate(self):
        self.dots += "."
        if len(self.dots) > 3:
            self.dots = ""
        self.dot_label.setText("Bot is typing" + self.dots)

# Main BotWindow Class
class BotWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Chat Bot Window")
        self.worker_thread = start_magentic_flow_worker()
        self.user_avatar = "user_avatar.png"
        self.bot_avatar = "bot_avatar.png"

        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        layout = QVBoxLayout(main_widget)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Heading
        heading_frame = QFrame()
        heading_frame.setObjectName("headingFrame")
        heading_layout = QVBoxLayout(heading_frame)
        heading_layout.setContentsMargins(0, 0, 0, 0)
        heading_label = QLabel("Chat Interface")
        heading_label.setFont(QFont("Arial", 24, QFont.Bold))
        heading_label.setAlignment(Qt.AlignCenter)
        heading_label.setStyleSheet("color: white;")
        heading_layout.addWidget(heading_label)
        layout.addWidget(heading_frame)

        # Chat Area
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        layout.addWidget(self.scroll_area)

        self.chat_container = QWidget()
        self.chat_layout = QVBoxLayout(self.chat_container)
        self.chat_layout.setAlignment(Qt.AlignTop)
        self.chat_container.setLayout(self.chat_layout)
        self.scroll_area.setWidget(self.chat_container)

        self.show_welcome_bubble()

        # Input Row
        input_row = QHBoxLayout()
        self.input_field = QTextEdit()
        self.input_field.setFixedHeight(80)
        input_row.addWidget(self.input_field)

        self.send_button = QPushButton("Send")
        self.send_button.clicked.connect(self.send_message)
        input_row.addWidget(self.send_button)

        layout.addLayout(input_row)

        self.sound_effect = QSoundEffect()
        wav_path = "notification.wav"
        if os.path.exists(wav_path):
            self.sound_effect.setSource(QUrl.fromLocalFile(wav_path))

        self.poll_timer = QTimer(self)
        self.poll_timer.timeout.connect(self.poll_bot_queue)
        self.poll_timer.start(200)

        self.setStyleSheet("""
            QMainWindow { background-color: #FFDAB9; }
            #headingFrame { background-color: #800000; }
            QTextEdit { border: 1px solid #CCCCCC; padding: 5px; }
            QPushButton { background-color: #2E8B57; color: white; padding: 10px; border-radius: 5px; }
            QPushButton:hover { background-color: #3CB371; }
        """)

    def show_welcome_bubble(self):
        bubble = ChatBubble(self.bot_avatar, "👋 Hello! How can I assist you today?", is_bot=True)
        self.chat_layout.addWidget(bubble)

    def show_loading_dots(self):
        self.loading_widget = LoadingDots()
        self.chat_layout.addWidget(self.loading_widget)

    def send_message(self):
        user_text = self.input_field.toPlainText().strip()
        if not user_text:
            return
        bubble = ChatBubble(self.user_avatar, user_text)
        self.chat_layout.addWidget(bubble)
        self.input_field.clear()
        self.show_loading_dots()
        userQueue.put(("You", user_text))

    def poll_bot_queue(self):
        while not botQueue.empty():
            msg = botQueue.get_nowait()
            if hasattr(self, 'loading_widget'):
                self.loading_widget.deleteLater()
            bubble = ChatBubble(self.bot_avatar, msg, "screenshot.png", is_bot=True)
            self.chat_layout.addWidget(bubble)
            if self.sound_effect:
                self.sound_effect.play()

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = BotWindow()
    window.show()
    sys.exit(app.exec_())
