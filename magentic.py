import sys
import time
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QTextEdit, QPushButton, QLabel, QFrame
)
from PyQt5.QtCore import Qt, QThread, pyqtSignal
from PyQt5.QtGui import QFont, QPalette, QPixmap, QLinearGradient, QColor, QPainter, QBrush
import os

###############################
# Placeholder Workflow Function
###############################

def run_magentic_workflow(nlp_input):
    """
    Simulates a series of actions for 'repair payment messages'.
    Replace this with your actual 'magentic one framework' logic.
    """
    steps = [
        f"Parsing your request: '{nlp_input}'",
        "Validating payment details...",
        "Repairing transaction records...",
        "Verifying final statuses...",
        "Payment repair completed successfully!"
    ]
    for step in steps:
        time.sleep(1)  # simulate some processing delay
        yield step

##################
# Worker Thread
##################

class ActionThread(QThread):
    update_chat = pyqtSignal(str)

    def __init__(self, user_input):
        super().__init__()
        self.user_input = user_input

    def run(self):
        # Call your utility function, yielding step-by-step messages
        for msg in run_magentic_workflow(self.user_input):
            self.update_chat.emit(msg)

########################
# Main Window
########################

class FancyBotWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Magentic One Fancy Chatbot")
        self.setGeometry(100, 100, 1500, 2000)

        # Main widget and layout
        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        layout = QVBoxLayout(main_widget)

        # Create a heading label
        heading_label = QLabel("Magentic One Payment Repair Chatbot")
        heading_label.setFont(QFont("Arial", 16, QFont.Bold))
        heading_label.setAlignment(Qt.AlignHCenter)
        layout.addWidget(heading_label)

        # Chat display (read-only)
        self.chat_display = QTextEdit()
        self.chat_display.setReadOnly(True)
        layout.addWidget(self.chat_display)

        # Multi-line text area for user input
        self.input_field = QTextEdit()
        self.input_field.setPlaceholderText("Type your request here, e.g. 'repair payment messages'...")
        self.input_field.setFixedHeight(80)
        layout.addWidget(self.input_field)

        # Button row
        button_layout = QHBoxLayout()

        self.send_button = QPushButton("Send")
        self.send_button.clicked.connect(self.send_message)
        button_layout.addWidget(self.send_button)

        layout.addLayout(button_layout)

        self.bot_thread = None

        # Apply a fancy style sheet
        self.apply_fancy_styles()

    def apply_fancy_styles(self):
        """
        Applies a style sheet with a gradient background, styled buttons,
        and larger fonts. Adjust colors as desired.
        """

        self.setStyleSheet("""
            QMainWindow {
                background-color: #f0f0f0;
            }
            QLabel {
                color: #333;
            }
            QPushButton {
                background-color: #4CAF50;
                color: white;
                font-size: 30px;
                padding: 8px 16px;
                border-radius: 4px;
            }
            QPushButton:hover {
                background-color: #45a049;
            }
            QTextEdit {
                font-size: 30px;
                border: 2px solid #ccc;
                border-radius: 4px;
                padding: 6px;
                background-color: #ffffff;
            }
        """)

        # Alternatively, create a gradient palette for the main window background:
        palette = self.palette()
        gradient = QLinearGradient(0, 0, 0, self.height())
        gradient.setColorAt(0.0, QColor("#cfd9df"))  # top color
        gradient.setColorAt(1.0, QColor("#e2ebf0"))  # bottom color
        palette.setBrush(QPalette.Window, QBrush(gradient))
        self.setPalette(palette)

    def send_message(self):
        user_text = self.input_field.toPlainText().strip()
        if not user_text:
            return

        # Display user's message in chat
        self.chat_display.append(f"<span style='color: blue; font-weight: bold;'>You:</span> {user_text}")
        self.input_field.clear()

        # Create worker thread to run the "magentic" logic
        self.bot_thread = ActionThread(user_text)
        self.bot_thread.update_chat.connect(self.show_bot_message)
        self.bot_thread.start()

    def show_bot_message(self, message):
        """
        Called by worker thread for each partial result from the workflow.
        """
        self.chat_display.append(f"<span style='color: darkgreen; font-weight: bold;'>Bot:</span> {message}")


#######################
# Main Entry Point
#######################

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = FancyBotWindow()
    window.show()
    sys.exit(app.exec_())
