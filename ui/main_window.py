"""NEO Desktop Assistant: High-performance product-grade AI & Desktop Automation."""

from datetime import datetime
from html import escape
from pathlib import Path

from PyQt5.QtCore import Qt, QThread, QTimer, pyqtSignal
from PyQt5.QtGui import QKeySequence
from PyQt5.QtWidgets import (
    QApplication, QCheckBox, QFrame, QHBoxLayout, QLabel, QLineEdit,
    QMainWindow, QPushButton, QScrollArea, QShortcut, QTextBrowser,
    QVBoxLayout, QWidget, QGridLayout
)

import config
from services.commands import CommandRouter
from services.agent import DesktopAgent
from services.friday_service import FridayService
from services.speech_recognition import listen_command
from services.tts_service import speak
from services.weather import WeatherService
from ui.settings_dialog import SettingsDialog
from ui.styles import get_application_stylesheet, format_message_html


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
        self.setWindowTitle(f"{config.APP_NAME} · Desktop Assistant Pro")
        self.resize(1180, 800)
        self.setMinimumSize(780, 560)

        # Core Services
        self.ai = FridayService()
        self.router = CommandRouter(self.ai)
        self.agent = DesktopAgent(self.ai, self.router)
        self.weather = WeatherService(config.OPENWEATHER_API_KEY)

        # State Variables
        self.jobs = set()
        self.busy = False
        self.closing = False
        self.thinking_step = 0
        self.message_count = 0
        self.last_ai_reply = ""

        # Activity Timer
        self.thinking_timer = QTimer(self)
        self.thinking_timer.setInterval(400)
        self.thinking_timer.timeout.connect(self._animate_thinking)

        # Build UI
        self._init_ui()
        self._apply_styles()
        self._setup_shortcuts()

        # Initial Welcome Message
        self._welcome_user()

        # Update initial backend indicators
        self._update_connection_indicators()

    def _init_ui(self):
        root = QWidget()
        root.setObjectName("root")
        main_layout = QVBoxLayout(root)
        main_layout.setContentsMargins(20, 16, 20, 16)
        main_layout.setSpacing(12)
        self.setCentralWidget(root)

        # 1. Top Header Bar
        header_frame = QFrame()
        header_frame.setObjectName("headerBar")
        header_layout = QHBoxLayout(header_frame)
        header_layout.setContentsMargins(12, 8, 12, 8)
        header_layout.setSpacing(12)

        # Brand / Logo
        logo = QLabel("✦ N")
        logo.setObjectName("appLogo")
        logo.setAlignment(Qt.AlignCenter)
        logo.setFixedSize(40, 40)
        header_layout.addWidget(logo)

        brand_box = QVBoxLayout()
        brand_box.setSpacing(1)
        title_row = QHBoxLayout()
        title_row.setSpacing(6)
        brand_title = QLabel(config.APP_NAME)
        brand_title.setObjectName("brandTitle")
        brand_badge = QLabel("PRO AGENT")
        brand_badge.setObjectName("brandBadge")
        title_row.addWidget(brand_title)
        title_row.addWidget(brand_badge)
        title_row.addStretch()

        brand_sub = QLabel("Autonomous Desktop Copilot")
        brand_sub.setStyleSheet("color: #64748b; font-size: 10px; font-weight: 600; letter-spacing: 0.5px;")
        brand_box.addLayout(title_row)
        brand_box.addWidget(brand_sub)
        header_layout.addLayout(brand_box)

        header_layout.addSpacing(16)

        # Live Backend Status Pills
        self.ai_status_pill = QLabel("● Friday AI Ready")
        self.ai_status_pill.setObjectName("statusPillGreen")
        self.ai_status_pill.setToolTip("Friday Colab neural backend is active")
        header_layout.addWidget(self.ai_status_pill)

        self.voice_status_pill = QLabel("🎤 Vosk Offline")
        self.voice_status_pill.setObjectName("statusPillBlue")
        self.voice_status_pill.setToolTip("Offline speech recognition engine ready")
        header_layout.addWidget(self.voice_status_pill)

        header_layout.addStretch()

        # Header Action Buttons
        self.new_chat_btn = QPushButton("+ New Chat")
        self.new_chat_btn.setObjectName("headerBtn")
        self.new_chat_btn.setToolTip("Start a clean conversation (Ctrl+N)")
        self.new_chat_btn.clicked.connect(self.new_chat)
        header_layout.addWidget(self.new_chat_btn)

        self.copy_btn = QPushButton("📋 Copy Last")
        self.copy_btn.setObjectName("headerBtn")
        self.copy_btn.setToolTip("Copy latest AI response to clipboard (Ctrl+Shift+C)")
        self.copy_btn.clicked.connect(self.copy_last_reply)
        header_layout.addWidget(self.copy_btn)

        self.settings_btn = QPushButton("⚙ Settings")
        self.settings_btn.setObjectName("headerBtn")
        self.settings_btn.setToolTip("Configure keys, backend & shortcuts (Ctrl+,)")
        self.settings_btn.clicked.connect(self.open_settings)
        header_layout.addWidget(self.settings_btn)

        # Digital Clock
        self.clock_label = QLabel()
        self.clock_label.setObjectName("clockLabel")
        header_layout.addWidget(self.clock_label)
        self.clock_timer = QTimer(self)
        self.clock_timer.timeout.connect(self._update_clock)
        self.clock_timer.start(1000)
        self._update_clock()

        main_layout.addWidget(header_frame)

        # 2. Hero Starter Card (Interactive Suggestions)
        self.hero_card = QFrame()
        self.hero_card.setObjectName("heroCard")
        hero_layout = QVBoxLayout(self.hero_card)
        hero_layout.setContentsMargins(18, 14, 18, 14)
        hero_layout.setSpacing(10)

        hero_top = QHBoxLayout()
        hero_spark = QLabel("✦")
        hero_spark.setObjectName("heroSpark")
        hero_text_box = QVBoxLayout()
        hero_text_box.setSpacing(2)
        hero_title = QLabel("What would you like to achieve today?")
        hero_title.setObjectName("heroTitle")
        hero_sub = QLabel("Ask a general question, create documents, or let NEO orchestrate applications and live desktop tools.")
        hero_sub.setObjectName("heroSubtitle")
        hero_text_box.addWidget(hero_title)
        hero_text_box.addWidget(hero_sub)
        hero_top.addWidget(hero_spark)
        hero_top.addSpacing(8)
        hero_top.addLayout(hero_text_box)
        hero_top.addStretch()
        hero_layout.addLayout(hero_top)

        # 4 Prompt Starter Chips
        chips_grid = QGridLayout()
        chips_grid.setSpacing(8)

        prompts = [
            ("📄 Create AI PDF", "create a PDF about artificial intelligence", "Generate a formatted research document"),
            ("📝 Smart Notepad", "write an essay about space exploration in Notepad", "Draft and open article in Notepad"),
            ("🌤 Live Weather", f"what is the weather in {config.DEFAULT_CITY}", "Check current weather & humidity"),
            ("💻 Open Terminal", "open terminal", "Launch PowerShell development console"),
        ]

        for i, (btn_title, query, desc) in enumerate(prompts):
            chip = QPushButton(f"<b>{btn_title}</b> · <span style='color:#94a3b8;'>{desc}</span>")
            chip.setObjectName("starterChip")
            chip.clicked.connect(lambda _, q=query: self._on_starter_clicked(q))
            chips_grid.addWidget(chip, i // 2, i % 2)

        hero_layout.addLayout(chips_grid)
        main_layout.addWidget(self.hero_card)

        # 3. Main Workspace (Conversation + Control Sidebar)
        body_layout = QHBoxLayout()
        body_layout.setSpacing(14)

        # Conversation Panel
        chat_panel = QFrame()
        chat_panel.setObjectName("chatPanel")
        chat_layout = QVBoxLayout(chat_panel)
        chat_layout.setContentsMargins(16, 14, 16, 14)
        chat_layout.setSpacing(10)

        chat_header = QHBoxLayout()
        chat_title = QLabel("Conversation Stream")
        chat_title.setObjectName("panelHeading")
        chat_sub = QLabel("AUTONOMOUS AGENT WORKSPACE")
        chat_sub.setObjectName("panelSubheading")
        chat_header.addWidget(chat_title)
        chat_header.addStretch()
        chat_header.addWidget(chat_sub)
        chat_layout.addLayout(chat_header)

        self.log = QTextBrowser()
        self.log.setObjectName("chatLog")
        self.log.setOpenExternalLinks(True)
        chat_layout.addWidget(self.log, 1)

        # Animated Thinking / Listening Status Box
        self.activity_indicator = QLabel()
        self.activity_indicator.setObjectName("thinkingBox")
        self.activity_indicator.hide()
        chat_layout.addWidget(self.activity_indicator)

        body_layout.addWidget(chat_panel, 3)

        # Sidebar Control Deck
        sidebar_scroll = QScrollArea()
        sidebar_scroll.setObjectName("sidebarScroll")
        sidebar_scroll.setFixedWidth(250)
        sidebar_scroll.setWidgetResizable(True)
        sidebar_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        sidebar_scroll.setFrameShape(QFrame.NoFrame)

        sidebar_card = QFrame()
        sidebar_card.setObjectName("sidebarCard")
        side_layout = QVBoxLayout(sidebar_card)
        side_layout.setContentsMargins(14, 14, 14, 14)
        side_layout.setSpacing(10)

        # Quick Launch Section
        launch_title = QLabel("Quick Tools")
        launch_title.setObjectName("sidebarSectionTitle")
        side_layout.addWidget(launch_title)

        quick_actions = [
            ("🔴  YouTube", "open youtube"),
            ("💻  Terminal", "open terminal"),
            ("📝  Notepad", "open notepad"),
            ("📁  File Explorer", "open file explorer"),
            ("🧮  Calculator", "open calculator"),
            ("✉️  Gmail", "open gmail"),
        ]

        for label, cmd in quick_actions:
            btn = QPushButton(label)
            btn.setObjectName("actionBtn")
            btn.clicked.connect(lambda _, value=cmd: self.run_command(value, command_mode=True))
            side_layout.addWidget(btn)

        side_layout.addSpacing(6)

        # Mini Weather Card
        weather_title = QLabel("Live Weather")
        weather_title.setObjectName("sidebarSectionTitle")
        side_layout.addWidget(weather_title)

        weather_box = QFrame()
        weather_box.setObjectName("weatherCard")
        w_layout = QVBoxLayout(weather_box)
        w_layout.setContentsMargins(10, 10, 10, 10)
        w_layout.setSpacing(6)

        self.w_city_label = QLabel(f"📍 {config.DEFAULT_CITY}")
        self.w_city_label.setObjectName("weatherCity")
        self.w_desc_label = QLabel("Tap Refresh to query")
        self.w_desc_label.setObjectName("weatherDetails")
        self.w_desc_label.setWordWrap(True)

        w_input_row = QHBoxLayout()
        w_input_row.setSpacing(4)
        self.w_city_input = QLineEdit()
        self.w_city_input.setObjectName("weatherInput")
        self.w_city_input.setPlaceholderText("City name...")
        self.w_city_input.setText(config.DEFAULT_CITY)
        self.w_city_input.returnPressed.connect(self.refresh_weather)

        self.w_refresh_btn = QPushButton("Check")
        self.w_refresh_btn.setObjectName("weatherRefreshBtn")
        self.w_refresh_btn.clicked.connect(self.refresh_weather)

        w_input_row.addWidget(self.w_city_input, 1)
        w_input_row.addWidget(self.w_refresh_btn)

        w_layout.addWidget(self.w_city_label)
        w_layout.addWidget(self.w_desc_label)
        w_layout.addLayout(w_input_row)
        side_layout.addWidget(weather_box)

        side_layout.addSpacing(6)

        # Audio Settings Section
        audio_title = QLabel("Audio Engine")
        audio_title.setObjectName("sidebarSectionTitle")
        side_layout.addWidget(audio_title)

        self.speak_toggle = QCheckBox("🔊 Speak replies (TTS)")
        self.speak_toggle.setChecked(True)
        self.speak_toggle.setToolTip("Toggle pyttsx3 voice readout (Ctrl+M)")
        side_layout.addWidget(self.speak_toggle)

        voice_info = QLabel("Speech input: Vosk Offline (6s)")
        voice_info.setStyleSheet("color: #64748b; font-size: 10px;")
        side_layout.addWidget(voice_info)

        side_layout.addStretch()

        # Session Stats
        self.stats_label = QLabel("Ready · 0 messages")
        self.stats_label.setStyleSheet("color: #64748b; font-size: 11px;")
        side_layout.addWidget(self.stats_label)

        sidebar_scroll.setWidget(sidebar_card)
        self.sidebar_scroll = sidebar_scroll
        body_layout.addWidget(sidebar_scroll)

        main_layout.addLayout(body_layout, 1)

        # 4. Floating Command Composer Bar
        composer_frame = QFrame()
        composer_frame.setObjectName("composerBar")
        composer_layout = QHBoxLayout(composer_frame)
        composer_layout.setContentsMargins(6, 6, 6, 6)
        composer_layout.setSpacing(8)

        # Mode Indicator
        self.mode_badge = QLabel("⚡ AGENT")
        self.mode_badge.setObjectName("composerMode")
        self.mode_badge.setToolTip("Autonomous mode: Plans tools and general queries")
        composer_layout.addWidget(self.mode_badge)

        # Input Prompt Box
        self.input = QLineEdit()
        self.input.setObjectName("promptInput")
        self.input.setPlaceholderText("Ask a question, request a PDF, or type a command... (Ctrl+L to focus)")
        self.input.returnPressed.connect(self.send_text)
        self.input.textChanged.connect(self._on_input_text_changed)
        composer_layout.addWidget(self.input, 1)

        # Clear Input Button
        self.clear_btn = QPushButton("✕")
        self.clear_btn.setObjectName("clearInputBtn")
        self.clear_btn.setToolTip("Clear text (Esc)")
        self.clear_btn.setFixedSize(24, 24)
        self.clear_btn.hide()
        self.clear_btn.clicked.connect(self.input.clear)
        composer_layout.addWidget(self.clear_btn)

        # Listen (Microphone) Button
        self.listen_button = QPushButton("🎙  Listen")
        self.listen_button.setObjectName("listenBtn")
        self.listen_button.setToolTip("Record 6-second voice command (Ctrl+Space or F2)")
        self.listen_button.clicked.connect(self.listen)
        composer_layout.addWidget(self.listen_button)

        # Send Button
        self.send_button = QPushButton("Send  ➔")
        self.send_button.setObjectName("sendBtn")
        self.send_button.setToolTip("Execute command (Enter)")
        self.send_button.clicked.connect(self.send_text)
        composer_layout.addWidget(self.send_button)

        main_layout.addWidget(composer_frame)

        # 5. Footer Status & Keyboard Shortcuts
        footer_layout = QHBoxLayout()
        self.status = QLabel("Ready · Press Ctrl+Space to speak or type your request")
        self.status.setObjectName("systemStatus")
        footer_layout.addWidget(self.status)
        footer_layout.addStretch()

        shortcut_hint = QLabel("↵ Send  •  Ctrl+Space Voice  •  Ctrl+N New Chat  •  Ctrl+L Focus  •  Ctrl+, Settings")
        shortcut_hint.setObjectName("shortcutFooter")
        footer_layout.addWidget(shortcut_hint)

        main_layout.addLayout(footer_layout)

    def _setup_shortcuts(self):
        """Register global ergonomic keyboard shortcuts."""
        # Focus input: Ctrl+L
        QShortcut(QKeySequence("Ctrl+L"), self, activated=self._focus_input)

        # New chat: Ctrl+N
        QShortcut(QKeySequence("Ctrl+N"), self, activated=self.new_chat)

        # Settings: Ctrl+,
        QShortcut(QKeySequence("Ctrl+,"), self, activated=self.open_settings)

        # Copy last reply: Ctrl+Shift+C
        QShortcut(QKeySequence("Ctrl+Shift+C"), self, activated=self.copy_last_reply)

        # Voice Listen: Ctrl+Space and F2
        QShortcut(QKeySequence("Ctrl+Space"), self, activated=self.listen)
        QShortcut(QKeySequence("F2"), self, activated=self.listen)

        # Toggle Speech: Ctrl+M
        QShortcut(QKeySequence("Ctrl+M"), self, activated=self._toggle_speech)

        # Refresh Weather: F5
        QShortcut(QKeySequence("F5"), self, activated=self.refresh_weather)

        # Escape to clear input
        QShortcut(QKeySequence("Esc"), self, activated=self._handle_escape)

    def _focus_input(self):
        self.input.setFocus()
        self.input.selectAll()

    def _handle_escape(self):
        if self.input.text():
            self.input.clear()
        elif self.hero_card.isHidden():
            self.hero_card.show()

    def _toggle_speech(self):
        self.speak_toggle.setChecked(not self.speak_toggle.isChecked())
        state = "Enabled" if self.speak_toggle.isChecked() else "Muted"
        self.status.setText(f"Spoken replies (TTS) {state}")

    def _on_input_text_changed(self, text):
        self.clear_btn.setVisible(bool(text.strip()))

    def _on_starter_clicked(self, query):
        self.input.setText(query)
        self.send_text()

    def _welcome_user(self):
        welcome_text = (
            f"Hello! I am **{config.APP_NAME}**, your desktop assistant.\n\n"
            "Here are a few things I can do for you:\n"
            "- **Desktop Apps & Sites**: `open youtube`, `open terminal`, `open calculator`\n"
            "- **Documents & PDFs**: `create a PDF about renewable energy`\n"
            "- **Notepad Notes**: `write an essay about artificial intelligence in Notepad`\n"
            "- **Live Forecast**: `what is the weather in {config.DEFAULT_CITY}`\n"
            "- **General AI Questions**: Ask me anything!\n\n"
            "Press **Ctrl+Space** or tap **🎙 Listen** for voice, or type a request below."
        )
        self._message(config.APP_NAME, welcome_text)

    def new_chat(self):
        """Reset conversation and restore welcome suggestions."""
        self.log.clear()
        self.message_count = 0
        self.last_ai_reply = ""
        self.hero_card.show()
        self.stats_label.setText("Ready · 0 messages")
        self._welcome_user()
        self.status.setText("New conversation started.")
        self.input.clear()
        self.input.setFocus()

    def copy_last_reply(self):
        """Copy the most recent AI reply to system clipboard."""
        if not self.last_ai_reply:
            self.status.setText("No AI reply to copy yet.")
            return
        clipboard = QApplication.clipboard()
        clipboard.setText(self.last_ai_reply)
        self.status.setText("✓ Copied last AI response to clipboard!")

    def open_settings(self):
        """Open the Preferences & Diagnostics dialog."""
        dialog = SettingsDialog(self)
        if dialog.exec_():
            # Reload services with new keys / urls
            self.ai = FridayService()
            self.router = CommandRouter(self.ai)
            self.agent = DesktopAgent(self.ai, self.router)
            self.weather = WeatherService(config.OPENWEATHER_API_KEY)
            self.w_city_label.setText(f"📍 {config.DEFAULT_CITY}")
            self.w_city_input.setText(config.DEFAULT_CITY)
            self._update_connection_indicators()
            self.status.setText("✓ Settings saved and applied successfully.")

    def _update_connection_indicators(self):
        has_ai_key = bool(config.FRIDAY_API_KEY.strip())
        if has_ai_key:
            self.ai_status_pill.setText("● Friday AI Ready")
            self.ai_status_pill.setObjectName("statusPillGreen")
        else:
            self.ai_status_pill.setText("○ Standby (Local actions ready)")
            self.ai_status_pill.setObjectName("statusPillBlue")

        vosk_path = Path(__file__).resolve().parents[1] / "vosk-model-small-en-us-0.15" / "vosk-model-small-en-us-0.15"
        if vosk_path.is_dir():
            self.voice_status_pill.setText("🎤 Vosk Offline")
        else:
            self.voice_status_pill.setText("🎤 Vosk Missing")

    def _update_clock(self):
        self.clock_label.setText(datetime.now().strftime("%a, %d %b · %I:%M %p"))

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
        self.status.setText(message)
        if not value:
            self.thinking_timer.stop()
            self.activity_indicator.hide()
            self.listen_button.setObjectName("listenBtn")
            self.listen_button.setText("🎙  Listen")
            self.listen_button.setStyleSheet("")

    def _animate_thinking(self):
        self.thinking_step = (self.thinking_step + 1) % 4
        dots = "." * self.thinking_step
        self.activity_indicator.setText(f"✦ Friday AI is planning action{dots}")

    def _start_thinking(self, message):
        self._set_busy(True, message)
        self.thinking_step = 0
        self.activity_indicator.setObjectName("thinkingBox")
        self._animate_thinking()
        self.activity_indicator.show()
        self.thinking_timer.start()

    def _start_listening(self):
        self._set_busy(True, "Recording for 6 seconds... (speak clearly)")
        self.listen_button.setObjectName("listenBtnActive")
        self.listen_button.setText("🔴  Recording...")
        self.listen_button.setStyleSheet("background: #7f1d1d; color: #ffffff; border: 1px solid #ef4444;")
        self.activity_indicator.setObjectName("listeningBox")
        self.activity_indicator.setText("🎤 Listening to microphone for 6 seconds...")
        self.activity_indicator.show()

    def _message(self, speaker, message):
        html = format_message_html(speaker, message)
        self.log.append(html)
        self.log.verticalScrollBar().setValue(self.log.verticalScrollBar().maximum())
        if speaker != "Error":
            self.message_count += 1
            self.stats_label.setText(f"Active · {self.message_count} messages")
        if speaker.lower() not in ("you", "user", "error"):
            self.last_ai_reply = message

    def _error(self, error):
        self._set_busy(False, "Ready · last action encountered an issue")
        self._message("Error", error)

    def send_text(self):
        text = self.input.text().strip()
        if text:
            self.input.clear()
            self.run_command(text)

    def run_command(self, text, command_mode=None):
        if self.busy:
            return
        # Hide hero suggestion deck when real conversation proceeds to maximize space
        if self.hero_card.isVisible():
            self.hero_card.hide()

        self._message("You", text)
        self._start_thinking("Thinking about your request...")
        self._job(lambda: self.agent.handle(text), self._reply)

    def _reply(self, reply):
        self._set_busy(False)
        self._message(config.APP_NAME, reply)
        if self.speak_toggle.isChecked():
            self._job(lambda: speak(reply), lambda _: None,
                      lambda error: self._message("Error", f"Voice readout: {error}"))

    def listen(self):
        if self.busy:
            return
        self._start_listening()
        self._job(listen_command, self._heard)

    def _heard(self, text):
        self._set_busy(False)
        if text:
            self.run_command(text)
        else:
            self.status.setText("No speech recognized · please try again or type.")

    def refresh_weather(self):
        if self.busy:
            return
        city = self.w_city_input.text().strip() or config.DEFAULT_CITY
        self._start_thinking(f"Checking weather in {city}...")
        self.w_refresh_btn.setEnabled(False)

        def show(report):
            self._message(config.APP_NAME, report)
            self._set_busy(False)
            self.w_refresh_btn.setEnabled(True)
            self.w_city_label.setText(f"📍 {city}")
            self.w_desc_label.setText(report.split(":", 1)[-1].strip() if ":" in report else report)

        def fail(error):
            self._error(error)
            self.w_refresh_btn.setEnabled(True)
            self.w_desc_label.setText("Fetch failed")

        self._job(lambda: self.weather.get_weather_report(city), show, fail)

    def closeEvent(self, event):
        if self.jobs:
            self.closing = True
            self.status.setText("Finishing current task before closing...")
            event.ignore()
            return
        super().closeEvent(event)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if hasattr(self, "sidebar_scroll"):
            compact = event.size().width() < 880
            self.sidebar_scroll.setFixedWidth(190 if compact else 250)
            self.ai_status_pill.setVisible(not compact)
            self.voice_status_pill.setVisible(not compact)

    def _apply_styles(self):
        self.setStyleSheet(get_application_stylesheet())
