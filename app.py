import sys
import json
import os
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QVBoxLayout, QWidget, QPushButton,
    QTextEdit, QLabel, QComboBox, QScrollArea, QFrame, QSpinBox
)
from PyQt5.QtCore import pyqtSignal, QObject, Qt
from PyQt5.QtGui import QPixmap
import asyncio
from playwright.async_api import async_playwright
from qasync import QEventLoop, asyncSlot
from datetime import datetime


class WorkerSignals(QObject):
    log_signal = pyqtSignal(str)
    screenshot_signal = pyqtSignal(str)


class MainApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.initUI()
        self.signals = WorkerSignals()
        self.logs = []  # Interaction logs
        self.screenshot_dir = "screenshots"  # Directory for screenshots
        self.is_capturing = True  # Flag to control capturing
        self._last_screenshot_time = None  # Track last screenshot timestamp
        os.makedirs(self.screenshot_dir, exist_ok=True)

        # Connect signals to GUI update methods
        self.signals.log_signal.connect(self.update_log)
        self.signals.screenshot_signal.connect(self.add_screenshot)

    def initUI(self):
        self.setWindowTitle("Python Playwright Desktop App")
        self.setGeometry(100, 100, 800, 600)

        # Central Widget
        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        # Layout
        layout = QVBoxLayout()

        # Dropdown for Models
        self.model_selector = QComboBox()
        self.model_selector.addItems(["Select Model", "Capture Interactions", "Replay Interactions"])
        layout.addWidget(self.model_selector)

        # Input Text Area
        self.input_prompt = QTextEdit()
        self.input_prompt.setPlaceholderText("Enter starting URL (e.g., https://example.com)...")
        layout.addWidget(self.input_prompt)

        # Replay Speed Input
        self.replay_speed_label = QLabel("Replay Speed (seconds):")
        layout.addWidget(self.replay_speed_label)
        self.replay_speed_input = QSpinBox()
        self.replay_speed_input.setRange(1, 10)  # Replay delay range: 1 to 10 seconds
        self.replay_speed_input.setValue(2)  # Default value
        layout.addWidget(self.replay_speed_input)

        # Buttons
        self.start_button = QPushButton("Start")
        self.start_button.clicked.connect(self.handle_start)
        layout.addWidget(self.start_button)

        self.stop_button = QPushButton("Stop Capture")
        self.stop_button.clicked.connect(self.handle_stop_capture)
        layout.addWidget(self.stop_button)

        self.replay_button = QPushButton("Replay")
        self.replay_button.clicked.connect(self.handle_replay)
        layout.addWidget(self.replay_button)

        # Log Area
        self.log_area = QTextEdit()
        self.log_area.setReadOnly(True)
        layout.addWidget(self.log_area)

        # Scroll Area for Screenshots
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_content = QWidget()
        self.scroll_layout = QVBoxLayout(self.scroll_content)
        self.scroll_area.setWidget(self.scroll_content)
        layout.addWidget(self.scroll_area)

        central_widget.setLayout(layout)

    def handle_start(self):
        model = self.model_selector.currentText()
        if model == "Select Model":
            self.update_log("Please select a valid model.")
            return
        elif model == "Capture Interactions":
            url = self.input_prompt.toPlainText().strip()
            if not url.startswith("http://") and not url.startswith("https://"):
                self.update_log("Invalid URL! Make sure it starts with http:// or https://")
                return
            self.logs = []  # Clear previous logs
            self.is_capturing = True
            self.update_log(f"Starting interaction capture on {url}...")
            asyncio.ensure_future(self.async_capture_interactions(url))

    def handle_stop_capture(self):
        self.is_capturing = False
        self.update_log("Stopped interaction capture.")

    def handle_replay(self):
        if not self.logs:
            self.update_log("No interactions to replay. Capture interactions first.")
            return
        self.update_log("Replaying interactions...")
        asyncio.ensure_future(self.async_replay_interactions())

    def update_log(self, message):
        self.log_area.append(message)

    def add_screenshot(self, path):
        """Add a screenshot to the scroll area."""
        pixmap = QPixmap(path)
        screenshot_label = QLabel()
        screenshot_label.setPixmap(pixmap)
        screenshot_label.setFrameStyle(QFrame.Box)  # Add a border for better visibility
        self.scroll_layout.addWidget(screenshot_label)  # Add the screenshot to the layout
        self.scroll_area.verticalScrollBar().setValue(
            self.scroll_area.verticalScrollBar().maximum()
        )  # Auto-scroll to the latest screenshot

    async def async_capture_interactions(self, start_url):
        async with async_playwright() as p:
            browser = await p.chromium.launch(
                headless=False,
                args=[
                    "--disable-gpu",
                    "--disable-extensions",
                    "--disable-background-timer-throttling",
                    "--disable-renderer-backgrounding",
                    "--disable-backgrounding-occluded-windows",
                    "--enable-automation",
                    "--start-maximized",
                ],
            )
            context = await browser.new_context()
            page = await context.new_page()

            # Attach listeners to the main page
            await self.attach_listeners(page)

            # Capture new tabs
            context.on("page", lambda new_page: asyncio.ensure_future(self.attach_listeners(new_page)))

            # Navigate to the starting URL
            try:
                await page.goto(start_url)
                self.log_interaction("navigate", None, start_url)
                self.signals.log_signal.emit(f"Navigated to {start_url}")
                await self.take_screenshot(page, "Initial Navigation")
            except Exception as e:
                self.signals.log_signal.emit(f"Error navigating to {start_url}: {e}")

            # Wait for user interactions until stopped
            while self.is_capturing:
                await asyncio.sleep(1)

            # Save logs to file
            log_file = "interaction_logs.json"
            with open(log_file, "w") as f:
                json.dump(self.logs, f, indent=4)
            self.signals.log_signal.emit(f"Logs saved to {log_file}")

            await browser.close()

    async def async_replay_interactions(self):
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=False)
            context = await browser.new_context()
            page = await context.new_page()

            delay_between_actions = self.replay_speed_input.value()

            for log in self.logs:
                action = log["action"]
                target = log.get("target")
                value = log.get("value")
                url = log.get("url")

                try:
                    if action == "navigate":
                        await page.goto(url)
                        self.signals.log_signal.emit(f"Replayed navigation to {url}")
                    elif action == "click":
                        await page.click(target)
                        self.signals.log_signal.emit(f"Replayed click on {target}")
                    elif action == "input":
                        await page.fill(target, value)
                        self.signals.log_signal.emit(f"Replayed input '{value}' on {target}")
                    elif action == "press":
                        await page.press(target, value)
                        self.signals.log_signal.emit(f"Replayed key press '{value}' on {target}")
                except Exception as e:
                    self.signals.log_signal.emit(f"Error during replay for action '{action}': {e}")

                # Delay between actions
                await asyncio.sleep(delay_between_actions)

            await browser.close()
            self.signals.log_signal.emit("Replay completed.")

    async def attach_listeners(self, page):
        """Attach listeners to a page to capture interactions."""
        self.signals.log_signal.emit(f"Attaching listeners to {page.url}")

        # Capture navigations
        page.on("framenavigated", lambda frame: asyncio.ensure_future(self.on_navigation(frame, page)))

        # Capture clicks, inputs, and keypresses
        await page.expose_function("log_interaction", lambda interaction: self.log_interaction(**interaction))
        await page.evaluate("""
            if (!window.listenersAttached) {
                document.addEventListener("click", (event) => {
                    const target = event.target.tagName.toLowerCase();
                    const selector = target + (event.target.id ? `#${event.target.id}` : "") +
                                     (event.target.className ? `.${event.target.className.split(" ").join(".")}` : "");
                    window.log_interaction({ action: "click", target: selector, url: window.location.href });
                });

                document.addEventListener("input", (event) => {
                    const target = event.target.tagName.toLowerCase();
                    const value = event.target.value || "";
                    const selector = target + (event.target.id ? `#${event.target.id}` : "") +
                                     (event.target.className ? `.${event.target.className.split(" ").join(".")}` : "");
                    window.log_interaction({ action: "input", target: selector, value, url: window.location.href });
                });

                document.addEventListener("keydown", (event) => {
                    if (event.key === "Enter") {
                        const target = event.target.tagName.toLowerCase();
                        const selector = target + (event.target.id ? `#${event.target.id}` : "") +
                                         (event.target.className ? `.${event.target.className.split(" ").join(".")}` : "");
                        window.log_interaction({ action: "press", target: selector, value: "Enter", url: window.location.href });
                    }
                });

                window.listenersAttached = true;
            }
        """)

    async def take_screenshot(self, page, description, debounce_time=2):
        """Take a screenshot with a debounce to avoid rapid successive captures."""
        current_time = datetime.utcnow()
        if self._last_screenshot_time:
            time_since_last = (current_time - self._last_screenshot_time).total_seconds()
            if time_since_last < debounce_time:
                self.signals.log_signal.emit(f"Skipped screenshot due to debounce: {description}")
                return

        self._last_screenshot_time = current_time
        screenshot_path = os.path.join(self.screenshot_dir, f"screenshot_{len(self.logs)}.png")
        try:
            await page.screenshot(path=screenshot_path, full_page=True)
            self.signals.log_signal.emit(f"Screenshot ({description}) saved: {screenshot_path}")
            self.signals.screenshot_signal.emit(screenshot_path)
        except Exception as e:
            self.signals.log_signal.emit(f"Failed to capture screenshot: {e}")

    async def on_navigation(self, frame, page):
        """Log navigation events."""
        if frame == page.main_frame:
            url = frame.url
            self.log_interaction("navigate", None, url)
            self.signals.log_signal.emit(f"Navigated to {url}")
            await self.take_screenshot(page, "Navigation")

    def log_interaction(self, action, target, url=None, value=None):
        """Log an interaction."""
        interaction = {
            "timestamp": datetime.utcnow().isoformat(),
            "action": action,
            "target": target,
            "url": url,
            "value": value
        }
        self.logs.append(interaction)
        self.signals.log_signal.emit(f"Captured interaction: {interaction}")


def main():
    app = QApplication(sys.argv)
    loop = QEventLoop(app)
    asyncio.set_event_loop(loop)

    window = MainApp()
    window.show()

    with loop:
        loop.run_forever()


if __name__ == "__main__":
    main()
