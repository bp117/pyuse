import sys
import json
import asyncio
import time
from datetime import datetime
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QTextEdit, QLineEdit,
    QPushButton, QScrollArea, QLabel, QHBoxLayout, QGridLayout, QDialog,
    QVBoxLayout as QVBoxDialogLayout
)
from PyQt5.QtCore import Qt, QThread, pyqtSignal
from PyQt5.QtGui import QPixmap, QFont
from playwright.async_api import async_playwright, Page, BrowserContext
import os

class ClickableLabel(QLabel):
    clicked = pyqtSignal(str)
    def __init__(self, image_path: str, parent=None):
        super().__init__(parent)
        self.image_path = image_path

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.clicked.emit(self.image_path)

class BrowserThread(QThread):
    update_chat = pyqtSignal(str)
    update_screenshot = pyqtSignal(str)
    
    def __init__(self, url, mode='capture'):
        super().__init__()
        self.url = url.strip()
        self.mode = mode  # 'capture' or 'replay'
        self.logs = []
        self.is_capturing = True

        self.last_screenshot_time = 0
        self.screenshot_interval = 2.0

        
        if os.path.exists('interaction_logs.json'):
            try:
                with open('interaction_logs.json', 'r') as f:
                    content = f.read().strip()
                    if content:
                        self.logs = json.loads(content)
                    else:
                        self.logs = []
            except json.JSONDecodeError:
                self.logs = []

    def stop_capture(self):
        self.is_capturing = False

    async def log_interaction(self, action, target, url, value=None):
        if not self.is_capturing:
            return

        log_entry = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "action": action,
            "target": target,
            "url": url
        }
        if value is not None:
            log_entry["value"] = value
            
        self.logs.append(log_entry)
        
        try:
            with open('interaction_logs.json', 'w') as f:
                json.dump(self.logs, f, indent=2)
        except Exception as e:
            print(f"Error writing logs: {e}")
        
        msg = f"{action} on {target}"
        if value:
            msg += f": {value}"
        self.update_chat.emit(msg)

    async def maybe_take_screenshot(self, page: Page):
        current_time = time.time()
        if (current_time - self.last_screenshot_time) >= self.screenshot_interval:
            self.last_screenshot_time = current_time
            screenshot_path = f'screenshots/screenshot_{datetime.now().strftime("%Y%m%d_%H%M%S")}.png'
            await page.screenshot(path=screenshot_path)
            self.update_screenshot.emit(screenshot_path)

    async def inject_event_listeners(self, page: Page):
        await page.expose_function("reportDomEvent", self.report_dom_event)
        
        script = """
            (function() {
                if (window.__event_injected) return;
                window.__event_injected = true;

                function getSelector(el) {
                    if (!el) return '';
                    if (el.id) return '#' + el.id;
                    if (el.className) {
                        let classes = el.className.toString().split(' ');
                        if (classes[0])
                            return el.tagName.toLowerCase() + '#' + classes[0];
                    }
                    return el.tagName.toLowerCase();
                }

               
                document.addEventListener('click', e => {
                    let selector = getSelector(e.target);
                    if (selector !== 'html' && selector !== 'body') {
                        window.reportDomEvent({
                            action: 'Click',
                            target: selector,
                            value: '',
                            url: window.location.href
                        });
                    }
                }, true);

             
                document.addEventListener('keydown', e => {
                    if (e.key === 'Enter') {
                        window.reportDomEvent({
                            action: 'KeyPress',
                            target: 'keyboard',
                            value: 'Enter',
                            url: window.location.href
                        });
                    }
                }, true);

              
                document.addEventListener('input', e => {
                    let selector = getSelector(e.target);
                    let value = '';
                    if (e.target && 'value' in e.target) {
                        value = e.target.value;
                    }
                    window.reportDomEvent({
                        action: 'Input',
                        target: selector,
                        value: value,
                        url: window.location.href
                    });
                }, true);
            })();
        """
        await page.add_init_script(script)
        await page.evaluate(script)

    async def report_dom_event(self, event_data: dict):
        action = event_data.get("action", "")
        target = event_data.get("target", "")
        value = event_data.get("value", "")
        url = event_data.get("url", "")

        if not self.is_capturing:
            return
        
        await self.log_interaction(action, target, url, value)
        if self._last_active_page:
            await self.maybe_take_screenshot(self._last_active_page)

    async def handle_frame_navigated(self, frame):
        if frame == self._last_active_page.main_frame:
            url = frame.url
            await self.log_interaction("Navigate", "main_frame", url)
            await asyncio.sleep(0.3)
            await self.maybe_take_screenshot(self._last_active_page)

    async def handle_new_page(self, new_page: Page):
        await asyncio.sleep(1)
        if not self.is_capturing:
            return

        url = new_page.url
        await self.log_interaction("OpenNewTab", "popup", url)
        self._last_active_page = new_page
        await self.maybe_take_screenshot(new_page)

        await self.inject_event_listeners(new_page)
        new_page.on("framenavigated", lambda frame: asyncio.create_task(self.handle_frame_navigated(frame)))

    async def capture_mode(self, context: BrowserContext, page: Page):
        self._last_active_page = page
        await self.inject_event_listeners(page)

        context.on("page", lambda pg: asyncio.create_task(self.handle_new_page(pg)))
        page.on("framenavigated", lambda frame: asyncio.create_task(self.handle_frame_navigated(frame)))

        while self.is_capturing:
            await asyncio.sleep(1)

    async def replay_mode(self, page: Page):
        try:
            if not os.path.exists('interaction_logs.json') or os.path.getsize('interaction_logs.json') == 0:
                self.update_chat.emit("No interaction logs found or file is empty")
                return

            with open('interaction_logs.json', 'r') as f:
                content = f.read().strip()
                if not content:
                    self.update_chat.emit("Interaction logs file is empty")
                    return
                replay_logs = json.loads(content)

            initial_url = None
            for log in replay_logs:
                if log.get("url"):
                    initial_url = log["url"]
                    break

            if initial_url:
                if initial_url.startswith("http"):
                    await page.goto(initial_url)
                    await asyncio.sleep(2)
                else:
                    self.update_chat.emit(f"Skipping invalid initial URL: {initial_url}")

            for log in replay_logs:
                action = log.get("action")
                target = log.get("target")
                value = log.get("value", "")
                log_url = log.get("url", "")

                try:
                    if action == "Click":
                        element = await page.wait_for_selector(target, timeout=5000)
                        if element:
                            await element.click()
                            await asyncio.sleep(0.3)
                            
                    elif action == "Input":
                        element = await page.wait_for_selector(target, timeout=5000)
                        if element:
                            await element.fill(value)
                            await asyncio.sleep(0.3)
                            
                    elif action == "KeyPress" and value == "Enter":
                        await page.keyboard.press("Enter")
                        await asyncio.sleep(1)

                    elif action == "Navigate":
                        if log_url.startswith("http"):
                            await page.goto(log_url)
                            await asyncio.sleep(1)
                        else:
                            self.update_chat.emit(f"Skipping invalid URL: '{log_url}'")

                    elif action == "OpenNewTab":
                        if log_url.startswith("chrome://"):
                            self.update_chat.emit(f"Skipping internal browser URL: {log_url}")
                        else:
                            self.update_chat.emit(f"OpenNewTab replay not implemented: {log_url}")

                    self.update_chat.emit(f"Replayed: {action} on {target}")
                except Exception as e:
                    self.update_chat.emit(f"Failed to replay action: {str(e)}")

        except Exception as e:
            self.update_chat.emit(f"Error during replay: {str(e)}")

    async def browser_automation(self):
        try:
            async with async_playwright() as p:
                browser = await p.chromium.launch(headless=False)
                context = await browser.new_context()
                page = await context.new_page()
                
                if not os.path.exists('screenshots'):
                    os.makedirs('screenshots')

                if self.mode == 'capture':
                    if not (self.url.startswith('http://') or self.url.startswith('https://')):
                        self.url = 'https://' + self.url
                    await page.goto(self.url)
                    await self.maybe_take_screenshot(page)
                    await self.capture_mode(context, page)
                else:
                    await self.replay_mode(page)
                    
                await browser.close()
        except Exception as e:
            self.update_chat.emit(f"Browser automation error: {str(e)}")

    def run(self):
        asyncio.run(self.browser_automation())


class ZoomDialog(QDialog):
    def __init__(self, image_path, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Screenshot Zoom")
        self.resize(900, 600)

        layout = QVBoxDialogLayout(self)

        label = QLabel(self)
        pixmap = QPixmap(image_path)
        scaled_pixmap = pixmap.scaled(self.width(), self.height(), Qt.KeepAspectRatio, Qt.SmoothTransformation)
        label.setPixmap(scaled_pixmap)

        layout.addWidget(label)

class ChatbotWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setFixedSize(1500, 2000)  
        self.setWindowTitle("Browser Automation Chatbot")

        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        layout = QVBoxLayout(main_widget)
        
        heading = QLabel("Browser Automation Chatbot")
        heading.setFont(QFont("Arial", 20, QFont.Bold))
        heading.setAlignment(Qt.AlignHCenter)
        layout.addWidget(heading)
        
        self.chat_display = QTextEdit()
        self.chat_display.setReadOnly(True)
        layout.addWidget(self.chat_display)

        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setFixedHeight(500)
        layout.addWidget(scroll_area)

        screenshot_widget = QWidget()
        self.screenshot_grid = QGridLayout(screenshot_widget)
        self.screenshot_grid.setHorizontalSpacing(5)
        self.screenshot_grid.setVerticalSpacing(5)
        self.screenshot_grid.setContentsMargins(5, 5, 5, 5)

        screenshot_widget.setStyleSheet("background-color: #222;")
        screenshot_widget.setLayout(self.screenshot_grid)
        scroll_area.setWidget(screenshot_widget)

        self.screenshot_col = 0
        self.screenshot_row = 0
        self.max_cols = 3

        # Button layout
        button_layout = QHBoxLayout()

        # **Multi-line input field (QTextEdit instead of QLineEdit)**
        self.input_field = QTextEdit()
        self.input_field.setPlaceholderText("Type your commands or queries here (multi-line). Press Send to proceed.")
        self.input_field.setFixedHeight(80)  # You can adjust this as needed
        button_layout.addWidget(self.input_field)
        
        self.send_button = QPushButton("Send")
        self.send_button.setStyleSheet("background-color: #0078D7; color: white; padding: 6px;")
        self.send_button.clicked.connect(self.send_message)
        button_layout.addWidget(self.send_button)
        
        self.stop_button = QPushButton("Stop Capture")
        self.stop_button.setStyleSheet("background-color: #666; color: white; padding: 6px;")
        self.stop_button.clicked.connect(self.stop_capture)
        button_layout.addWidget(self.stop_button)
        
        self.replay_button = QPushButton("Replay")
        self.replay_button.setStyleSheet("background-color: #2E8B57; color: white; padding: 6px;")
        self.replay_button.clicked.connect(self.replay_interactions)
        button_layout.addWidget(self.replay_button)

        self.clear_logs_button = QPushButton("Clear Logs")
        self.clear_logs_button.setStyleSheet("background-color: #bb2124; color: white; padding: 6px;")
        self.clear_logs_button.clicked.connect(self.clear_logs)
        button_layout.addWidget(self.clear_logs_button)
        
        layout.addLayout(button_layout)

        self.show_welcome_message()
        self.browser_thread = None

        self.setStyleSheet("""
            QTextEdit, QLabel {
                font-size: 30px;
            }
        """)

    def show_welcome_message(self):
        welcome_msg = """<b>Welcome to the Browser Automation Chatbot!</b><br>
Type a website URL or commands in the multi-line box below and press Send to start capturing.<br>
- Click "Stop Capture" to stop logging<br>
- Click "Replay" to replay recorded interactions<br>
- Click "Clear Logs" to remove the interaction logs<br><br>
"""
        self.chat_display.append(welcome_msg)

    def send_message(self):
        # For QTextEdit, use toPlainText() to get multi-line input
        user_input = self.input_field.toPlainText().strip()
        if not user_input:
            return

        self.chat_display.append(f"<span style='color:blue;'>You:</span> {user_input}")
        self.input_field.clear()

        # Start capture mode with the user input as a URL or command
        self.browser_thread = BrowserThread(user_input, mode='capture')
        self.browser_thread.update_chat.connect(self.update_chat)
        self.browser_thread.update_screenshot.connect(self.show_screenshot)
        self.browser_thread.start()

    def stop_capture(self):
        if self.browser_thread:
            self.browser_thread.stop_capture()
            self.chat_display.append("<span style='color:red;'>Bot:</span> Stopped capturing interactions")

    def replay_interactions(self):
        if os.path.exists('interaction_logs.json'):
            self.browser_thread = BrowserThread('', mode='replay')
            self.browser_thread.update_chat.connect(self.update_chat)
            self.browser_thread.update_screenshot.connect(self.show_screenshot)
            self.browser_thread.start()
            self.chat_display.append("<span style='color:green;'>Bot:</span> Replaying interactions...")
        else:
            self.chat_display.append("<span style='color:red;'>Bot:</span> No recorded interactions found")

    def clear_logs(self):
        if os.path.exists('interaction_logs.json'):
            os.remove('interaction_logs.json')
            self.chat_display.append("<span style='color:red;'>Bot:</span> Interaction logs cleared.")
        else:
            self.chat_display.append("<span style='color:red;'>Bot:</span> No logs to clear.")

    def update_chat(self, message):
        self.chat_display.append(f"<span style='color:purple;'>Bot:</span> {message}")
        scrollbar = self.chat_display.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())

    def show_screenshot(self, path):
        from PyQt5.QtCore import Qt
        clickable_label = ClickableLabel(path)
        pixmap = QPixmap(path)
        scaled_pixmap = pixmap.scaled(280, 180, Qt.KeepAspectRatio, Qt.SmoothTransformation)
        clickable_label.setPixmap(scaled_pixmap)
        clickable_label.clicked.connect(self.open_zoom_dialog)

        self.screenshot_grid.addWidget(clickable_label, self.screenshot_row, self.screenshot_col)
        self.screenshot_col += 1
        if self.screenshot_col >= self.max_cols:
            self.screenshot_col = 0
            self.screenshot_row += 1

    def open_zoom_dialog(self, image_path: str):
        dlg = ZoomDialog(image_path, self)
        dlg.exec_()

if __name__ == '__main__':
    app = QApplication(sys.argv)
    window = ChatbotWindow()
    window.show()
    sys.exit(app.exec_())
