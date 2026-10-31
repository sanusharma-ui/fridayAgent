"""NEO desktop window: one command surface for voice and keyboard."""

from datetime import datetime
from html import escape

from PyQt5.QtCore import Qt, QThread, QTimer, pyqtSignal
from PyQt5.QtWidgets import (
    QCheckBox, QComboBox, QFrame, QHBoxLayout, QInputDialog, QLabel, QLineEdit, QMainWindow,
    QPushButton, QScrollArea, QTextBrowser, QVBoxLayout, QWidget,
)

import config
from services.commands import CommandRouter
from services.agent import DesktopAgent
from services.friday_service import FridayService
from services.speech_recognition import listen_command
from services.tts_service import speak
from services.weather import WeatherService


class Job(QThread):
    result = pyqtSignal(str)
    error = pyqtSignal(str)

    def __init__(self, action, parent=None):
        super().__init__(parent)
        self.action = action

    def run(self):
        try:
            self.result.emit(str(self.action()))
        except Exception as exc:
            self.error.emit(str(exc))


class AssistantWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(f"{config.APP_NAME} · Desktop Assistant")
        self.resize(1120, 760)
        self.setMinimumSize(680, 540)
        self.ai = FridayService()
        self.router = CommandRouter(self.ai)
        self.agent = DesktopAgent(self.ai, self.router)
        self.weather = WeatherService(config.OPENWEATHER_API_KEY)
        self.jobs = set()
        self.busy = False
        self.closing = False
        self.thinking_step = 0
        self.thinking_timer = QTimer(self)
        self.thinking_timer.setInterval(450)
        self.thinking_timer.timeout.connect(self._animate_thinking)

        root = QWidget()
        root.setObjectName("root")
        layout = QVBoxLayout(root)
        layout.setContentsMargins(28, 22, 28, 20)
        layout.setSpacing(15)
        self.setCentralWidget(root)

        header = QHBoxLayout()
        mark = QLabel("N")
        mark.setObjectName("mark")
        mark.setAlignment(Qt.AlignCenter)
        mark.setFixedSize(46, 46)
        header.addWidget(mark)
        header.addSpacing(9)
        brand = QVBoxLayout()
        brand.setSpacing(2)
        title = QLabel(config.APP_NAME)
        title.setObjectName("brand")
        subtitle = QLabel("YOUR PERSONAL DESKTOP ASSISTANT")
        subtitle.setObjectName("muted")
        subtitle.setStyleSheet("font-size: 10px; letter-spacing: 1px;")
        brand.addWidget(title)
        brand.addWidget(subtitle)
        header.addLayout(brand)
        header.addStretch()
        self.badge = QLabel("●  AGENT WORKSPACE")
        self.badge.setObjectName("badge")
        header.addWidget(self.badge)
        header.addSpacing(12)
        self.clock = QLabel()
        self.clock.setObjectName("clock")
        header.addWidget(self.clock)
        layout.addLayout(header)

        intro = QFrame()
        intro.setObjectName("intro")
        intro_layout = QVBoxLayout(intro)
        intro_layout.setContentsMargins(24, 19, 24, 21)
        intro_layout.setSpacing(5)
        eyebrow = QLabel("✦   YOUR AI COMPANION")
        eyebrow.setObjectName("eyebrow")
        heading = QLabel("A little help. A lot done.")
        heading.setObjectName("heading")
        tips = QLabel("Ask anything, get things done, or just say what’s on your mind.")
        tips.setWordWrap(True)
        tips.setObjectName("muted")
        intro_layout.addWidget(eyebrow)
        intro_layout.addWidget(heading)
        intro_layout.addWidget(tips)
        layout.addWidget(intro)

        body = QHBoxLayout()
        body.setSpacing(18)
        conversation = QFrame()
        conversation.setObjectName("panel")
        conversation_layout = QVBoxLayout(conversation)
        conversation_layout.setContentsMargins(20, 17, 20, 17)
        conversation_header = QHBoxLayout()
        conversation_title = QLabel("Conversation")
        conversation_title.setObjectName("sectionTitle")
        conversation_header.addWidget(conversation_title)
        conversation_header.addStretch()
        conversation_hint = QLabel("YOUR SPACE TO THINK & DO")
        conversation_hint.setObjectName("sectionHint")
        conversation_header.addWidget(conversation_hint)
        conversation_layout.addLayout(conversation_header)
        self.log = QTextBrowser()
        self.log.setObjectName("log")
        self.log.setOpenExternalLinks(False)
        conversation_layout.addWidget(self.log, 1)
        self.thinking_indicator = QLabel()
        self.thinking_indicator.setObjectName("thinking")
        self.thinking_indicator.hide()
        conversation_layout.addWidget(self.thinking_indicator)
        body.addWidget(conversation, 3)

        sidebar = QFrame()
        sidebar.setObjectName("panel")
        side = QVBoxLayout(sidebar)
        side.setContentsMargins(16, 17, 16, 17)
        side.setSpacing(8)
        side_title = QLabel("Quick actions")
        side_title.setObjectName("sectionTitle")
        side.addWidget(side_title)
        side_hint = QLabel("A little shortcut for your day")
        side_hint.setObjectName("sideHint")
        side_hint.setWordWrap(True)
        side.addWidget(side_hint)
        side.addSpacing(4)
        for label, command in (("Open YouTube", "open youtube"), ("Open Facebook", "open facebook"),
                               ("Open Terminal", "open terminal"), ("Open Gmail", "open gmail"), ("Open Notepad", "open notepad")):
            button = QPushButton(label)
            button.setObjectName("quick")
            button.clicked.connect(lambda _, value=command: self.run_command(value, command_mode=True))
            side.addWidget(button)
        side.addSpacing(6)
        self.weather_button = QPushButton("Check weather...")
        self.weather_button.setObjectName("quick")
        self.weather_button.clicked.connect(self.refresh_weather)
        side.addWidget(self.weather_button)
        side.addStretch()
        self.speak_toggle = QCheckBox("Speak replies")
        self.speak_toggle.setChecked(True)
        side.addWidget(self.speak_toggle)
        sidebar_scroll = QScrollArea()
        sidebar_scroll.setObjectName("sidebarScroll")
        sidebar_scroll.setFixedWidth(232)
        sidebar_scroll.setWidgetResizable(True)
        sidebar_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        sidebar_scroll.setFrameShape(QFrame.NoFrame)
        sidebar_scroll.setWidget(sidebar)
        self.sidebar_scroll = sidebar_scroll
        body.addWidget(sidebar_scroll)
        layout.addLayout(body, 1)

        composer_frame = QFrame()
        composer_frame.setObjectName("composer")
        composer = QHBoxLayout(composer_frame)
        composer.setContentsMargins(7, 7, 7, 7)
        composer.setSpacing(7)
        self.mode = QComboBox()
        self.mode.addItems(["Agent"])
        self.mode.setToolTip("Run supported actions or ask AI a question")
        self.mode.currentIndexChanged.connect(self._update_mode)
        composer.addWidget(self.mode)
        self.input = QLineEdit()
        self.input.setPlaceholderText("Type a command or question...")
        self.input.returnPressed.connect(self.send_text)
        composer.addWidget(self.input, 1)
        self.send_button = QPushButton("Send  ↗")
        self.send_button.setObjectName("send")
        self.send_button.clicked.connect(self.send_text)
        composer.addWidget(self.send_button)
        self.listen_button = QPushButton("●  Listen")
        self.listen_button.setObjectName("accent")
        self.listen_button.clicked.connect(self.listen)
        composer.addWidget(self.listen_button)
        layout.addWidget(composer_frame)

        self.status = QLabel("Ready · tap Listen to record a 6-second command")
        self.status.setObjectName("muted")
        layout.addWidget(self.status)
        timer = QTimer(self)
        timer.timeout.connect(lambda: self.clock.setText(datetime.now().strftime("%a, %d %b · %I:%M %p")))
        timer.start(30000)
        self.clock.setText(datetime.now().strftime("%a, %d %b · %I:%M %p"))
        self._apply_styles()
        self._update_mode()
        self._message(config.APP_NAME, "Hi! Tap Listen and say ‘open YouTube’, ‘open terminal’, or ‘create a PDF about space’. You can also type or ask a question.")

    def _job(self, action, success, failure=None):
        job = Job(action, self)
        self.jobs.add(job)
        job.result.connect(success)
        job.error.connect(failure or self._error)
        job.finished.connect(lambda: self._job_finished(job))
        job.start()

    def _job_finished(self, job):
        self.jobs.discard(job)
        if self.closing and not self.jobs:
            self.close()

    def _set_busy(self, value, message="Ready"):
        self.busy = value
        self.send_button.setEnabled(not value)
        self.listen_button.setEnabled(not value)
        self.input.setEnabled(not value)
        self.mode.setEnabled(not value)
        self.status.setText(message)
        if not value:
            self.thinking_timer.stop()
            self.thinking_indicator.hide()

    def _animate_thinking(self):
        self.thinking_step = (self.thinking_step + 1) % 4
        self.thinking_indicator.setText("✦  Thinking" + "." * self.thinking_step)

    def _start_thinking(self, message):
        self._set_busy(True, message)
        self.thinking_step = 0
        self._animate_thinking()
        self.thinking_indicator.show()
        self.thinking_timer.start()

    def _message(self, speaker, message):
        color = "#a5b9ff" if speaker == "You" else "#81e5d3"
        safe_message = escape(message).replace("\n", "<br>")
        self.log.append(f'<p style="margin:16px 0 5px;color:{color};font-size:10pt;"><b>{escape(speaker.upper())}</b></p><p style="margin:0 0 14px;color:#e4e9f5;line-height:145%;">{safe_message}</p>')

    def _error(self, error):
        self._set_busy(False, "Ready · last action failed")
        self._message("Error", error)

    def send_text(self):
        text = self.input.text().strip()
        if text:
            self.input.clear()
            self.run_command(text)

    def _update_mode(self):
        self.input.setPlaceholderText("Ask a question or tell me what to do...")

    def run_command(self, text, command_mode=None):
        if self.busy:
            return
        self._message("You", text)
        self._start_thinking("Thinking about your request...")
        self._job(lambda: self.agent.handle(text), self._reply)

    def _reply(self, reply):
        self._set_busy(False)
        self._message(config.APP_NAME, reply)
        if self.speak_toggle.isChecked():
            self._job(lambda: speak(reply), lambda _: None,
                      lambda error: self._message("Voice", error))

    def listen(self):
        if self.busy:
            return
        self._set_busy(True, "Listening for 6 seconds...")
        self._job(listen_command, self._heard)

    def _heard(self, text):
        self._set_busy(False)
        if text:
            self.run_command(text)
        else:
            self.status.setText("No speech recognized · please try again")

    def refresh_weather(self):
        if self.busy:
            return
        city, accepted = QInputDialog.getText(self, "Weather", "City", text=config.DEFAULT_CITY)
        if not accepted:
            return
        city = city.strip() or config.DEFAULT_CITY
        self._start_thinking(f"Checking weather in {city}...")
        self.weather_button.setEnabled(False)
        def show(report):
            self._message(config.APP_NAME, report)
            self._set_busy(False)
            self.weather_button.setEnabled(True)
        def fail(error):
            self._error(error)
            self.weather_button.setEnabled(True)
        self._job(lambda: self.weather.get_weather_report(city), show, fail)

    def closeEvent(self, event):
        if self.jobs:
            self.closing = True
            self.status.setText("Finishing current action before closing...")
            event.ignore()
            return
        super().closeEvent(event)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if hasattr(self, "sidebar_scroll"):
            compact = event.size().width() < 850
            self.sidebar_scroll.setFixedWidth(195 if compact else 232)
            self.badge.setVisible(not compact)
            self.clock.setVisible(not compact)

    def _apply_styles(self):
        self.setStyleSheet("""
            QWidget#root { background: #090e1a; color: #e8edf7; font-family: 'Segoe UI'; font-size: 13px; }
            QLabel { color: #e8edf7; }
            QLabel#mark { background: #84e4d0; color: #102a29; border-radius: 15px; font-size: 21px; font-weight: 800; }
            QLabel#brand { color: #f5f7ff; font-size: 20px; font-weight: 800; letter-spacing: 2px; }
            QLabel#heading { color: #f7f9ff; font-size: 26px; font-weight: 700; }
            QLabel#eyebrow { color: #85e5d2; font-size: 10px; font-weight: 700; letter-spacing: 2px; }
            QLabel#clock, QLabel#muted, QLabel#sideHint { color: #8e9db5; }
            QLabel#sideHint { font-size: 11px; }
            QLabel#sectionTitle { color: #f3f6ff; font-size: 14px; font-weight: 700; }
            QLabel#sectionHint { color: #73839c; font-size: 9px; letter-spacing: 1px; }
            QLabel#badge { color: #9bdfd0; background: #142b2e; border: 1px solid #264c49; border-radius: 11px; padding: 7px 10px; font-size: 9px; font-weight: 700; }
            QLabel#thinking { color: #a9e9da; background: #18302f; border: 1px solid #2d514a; border-radius: 10px; padding: 9px 12px; font-weight: 600; }
            QFrame#intro { background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #1a2843, stop:0.6 #172b3b, stop:1 #173834); border: 1px solid #2b4150; border-radius: 18px; }
            QFrame#panel { background: #101a2a; border: 1px solid #243249; border-radius: 17px; }
            QFrame#composer { background: #111c2c; border: 1px solid #2b3b50; border-radius: 15px; }
            QScrollArea#sidebarScroll { background: transparent; border: 0; }
            QScrollBar:vertical { background: #111b2d; width: 8px; margin: 0; }
            QScrollBar::handle:vertical { background: #405773; border-radius: 4px; min-height: 30px; }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
            QTextBrowser#log { background: transparent; color: #e8edf7; border: 0; selection-background-color: #385c79; }
            QLineEdit { background: transparent; color: #f5f8ff; border: 0; padding: 10px; }
            QComboBox { background: #1c2b3e; color: #b8c9df; border: 0; border-radius: 9px; padding: 10px; min-width: 75px; }
            QComboBox QAbstractItemView { background: #18253a; color: #e8edf7; selection-background-color: #2d665f; }
            QPushButton { background: #263953; color: #eef4ff; border: 0; border-radius: 10px; padding: 10px 15px; font-weight: 600; }
            QPushButton:hover { background: #345070; }
            QPushButton#send { background: #293d57; }
            QPushButton#accent { background: #85e4d0; color: #102b28; }
            QPushButton#accent:hover { background: #a9f1e1; }
            QPushButton#quick { background: #1b2a3e; color: #dce7f6; text-align: left; padding: 10px 12px; border: 1px solid #293c53; }
            QPushButton#quick:hover { background: #263d53; border-color: #537b80; }
            QPushButton:disabled { color: #8793a6; background: #253348; }
            QCheckBox { color: #c4d0e3; }
        """)
