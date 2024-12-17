import sys
import queue
import threading
import os
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QTextEdit, QPushButton, QLabel, QFrame, QScrollArea, QDialog
)
from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtGui import QFont, QPixmap

# Simulated external worker
userQueue = queue.Queue()
botQueue = queue.Queue()


def start_magentic_flow_worker():
    """Worker thread simulation."""
    def simulate_bot_worker():
        while True:
            if not userQueue.empty():
                user_input = userQueue.get()
                botQueue.put(f"Bot Reply: Echoing '{user_input[1]}'")
    worker_thread = threading.Thread(target=simulate_bot_worker, daemon=True)
    worker_thread.start()
    return worker_thread


# ChatBubble Class
class ChatBubble(QWidget):
    def __init__(self, avatar_path: str, message: str, is_bot=False, parent=None):
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(5, 5, 5, 5)
        layout.setSpacing(8)

        # Avatar
        avatar_label = QLabel()
        avatar_label.setFixedSize(30, 30)
        pix = QPixmap(avatar_path).scaled(30, 30, Qt.KeepAspectRatio, Qt.SmoothTransformation)
        avatar_label.setPixmap(pix)
        layout.addWidget(avatar_label, alignment=Qt.AlignTop)

        # Message bubble
        bubble_label = QLabel(message)
        bubble_label.setWordWrap(True)  # Allow text wrapping
        bubble_label.setMaximumWidth(500)  # Bubble width limit
        bubble_label.setSizePolicy(QLabel.Preferred, QLabel.Expanding)  # Expand height dynamically
        bubble_label.setStyleSheet(f"""
            QLabel {{
                background-color: {"#FFCC80" if not is_bot else "#FFF3E0"};
                border-radius: 12px;
                padding: 10px;
            }}
        """)
        layout.addWidget(bubble_label, alignment=Qt.AlignLeft)


# Loading Dots Animation
class LoadingDots(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.dot_label = QLabel("...")
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
        self.dot_label.setText(self.dots)


# Main Chat Window
class BotWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Chat Bot")
        self.setFixedWidth(600)  # Set fixed window width
        self.worker_thread = start_magentic_flow_worker()
        self.user_avatar = "user_avatar.png"
        self.bot_avatar = "bot_avatar.png"

        # Main layout
        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        layout = QVBoxLayout(main_widget)
        layout.setContentsMargins(0, 0, 0, 0)

        # Chat Area
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOn)
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

        # Timer for bot queue
        self.poll_timer = QTimer(self)
        self.poll_timer.timeout.connect(self.poll_bot_queue)
        self.poll_timer.start(200)

        # Stylesheet
        self.setStyleSheet("""
            QMainWindow { background-color: #FFDAB9; }
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
        self.scroll_to_bottom()

    def send_message(self):
        user_text = self.input_field.toPlainText().strip()
        if not user_text:
            return
        # User Bubble
        bubble = ChatBubble(self.user_avatar, user_text)
        self.chat_layout.addWidget(bubble)
        self.input_field.clear()

        # Show loading dots
        self.show_loading_dots()
        userQueue.put(("You", user_text))

    def poll_bot_queue(self):
        while not botQueue.empty():
            msg = botQueue.get_nowait()
            if hasattr(self, 'loading_widget'):
                self.loading_widget.deleteLater()
            bubble = ChatBubble(self.bot_avatar, msg, is_bot=True)
            self.chat_layout.addWidget(bubble)
            self.scroll_to_bottom()

    def scroll_to_bottom(self):
        self.scroll_area.verticalScrollBar().setValue(self.scroll_area.verticalScrollBar().maximum())


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = BotWindow()
    window.show()
    sys.exit(app.exec_())
