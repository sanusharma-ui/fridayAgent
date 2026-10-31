"""Preferences and Diagnostics modal dialog for NEO AI Assistant."""

from pathlib import Path
import os
import re
import tempfile
from dotenv import set_key
from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QTabWidget, QWidget, QFrame, QMessageBox, QCheckBox
)

import config
from services.telegram_access import parse_allowed_ids


class SettingsDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Preferences & System Settings")
        self.resize(620, 560)
        self.setModal(True)
        self._init_ui()
        self._apply_dialog_styles()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(16)

        # Header
        header = QHBoxLayout()
        title_box = QVBoxLayout()
        title = QLabel("System Settings")
        title.setStyleSheet("color: #ffffff; font-size: 18px; font-weight: 800;")
        subtitle = QLabel("Configure AI backend connection, weather keys, and voice options.")
        subtitle.setStyleSheet("color: #94a3b8; font-size: 12px;")
        title_box.addWidget(title)
        title_box.addWidget(subtitle)
        header.addLayout(title_box)
        layout.addLayout(header)

        # Tabs
        self.tabs = QTabWidget()
        self.tabs.setObjectName("settingsTabs")

        # Tab 1: AI Backend
        ai_tab = QWidget()
        ai_layout = QVBoxLayout(ai_tab)
        ai_layout.setContentsMargins(14, 16, 14, 16)
        ai_layout.setSpacing(12)

        ai_layout.addWidget(QLabel("Friday Colab Backend URL (Ngrok)"))
        self.endpoint_input = QLineEdit()
        self.endpoint_input.setText(config.AI_ENDPOINT_URL)
        self.endpoint_input.setPlaceholderText("https://....ngrok-free.dev")
        ai_layout.addWidget(self.endpoint_input)

        ai_layout.addWidget(QLabel("Friday API Key (x-api-key)"))
        self.api_key_input = QLineEdit()
        self.api_key_input.setEchoMode(QLineEdit.Password)
        self.api_key_input.setText(config.FRIDAY_API_KEY)
        self.api_key_input.setPlaceholderText("Enter FRIDAY_API_KEY")
        ai_layout.addWidget(self.api_key_input)

        test_row = QHBoxLayout()
        self.show_key_btn = QPushButton("Show Key")
        self.show_key_btn.setFixedWidth(90)
        self.show_key_btn.clicked.connect(self._toggle_key_visibility)
        test_row.addWidget(self.show_key_btn)
        test_row.addStretch()

        self.test_ai_btn = QPushButton("Ping Friday Server")
        self.test_ai_btn.clicked.connect(self._test_ai_connection)
        test_row.addWidget(self.test_ai_btn)
        ai_layout.addLayout(test_row)
        ai_layout.addStretch()
        self.tabs.addTab(ai_tab, "Friday AI")

        # Tab 2: Weather & Tools
        tools_tab = QWidget()
        tools_layout = QVBoxLayout(tools_tab)
        tools_layout.setContentsMargins(14, 16, 14, 16)
        tools_layout.setSpacing(12)

        tools_layout.addWidget(QLabel("OpenWeather API Key"))
        self.weather_key_input = QLineEdit()
        self.weather_key_input.setEchoMode(QLineEdit.Password)
        self.weather_key_input.setText(config.OPENWEATHER_API_KEY)
        self.weather_key_input.setPlaceholderText("Optional OpenWeatherMap Key")
        tools_layout.addWidget(self.weather_key_input)

        tools_layout.addWidget(QLabel("Default City"))
        self.city_input = QLineEdit()
        self.city_input.setText(config.DEFAULT_CITY)
        self.city_input.setPlaceholderText("e.g. Nagpur, Mumbai, London")
        tools_layout.addWidget(self.city_input)

        tools_layout.addStretch()
        self.tabs.addTab(tools_tab, "Weather & Environment")

        telegram_tab = QWidget()
        telegram_layout = QVBoxLayout(telegram_tab)
        telegram_layout.setContentsMargins(14, 16, 14, 16)
        telegram_layout.setSpacing(8)
        help_text = QLabel("Create a bot with @BotFather. Save its token here, connect Telegram, then send /id to your bot. Add your numeric ID below and reconnect to allow tasks. Keep the laptop app running.")
        help_text.setWordWrap(True)
        telegram_layout.addWidget(help_text)
        telegram_layout.addWidget(QLabel("Bot token (kept in local .env)"))
        self.telegram_token_input = QLineEdit(config.TELEGRAM_BOT_TOKEN)
        self.telegram_token_input.setEchoMode(QLineEdit.Password)
        self.telegram_token_input.setPlaceholderText("123456789:token-from-BotFather")
        telegram_layout.addWidget(self.telegram_token_input)
        telegram_layout.addWidget(QLabel("Allowed user IDs (comma separated; empty = setup only)"))
        self.telegram_ids_input = QLineEdit(config.TELEGRAM_ALLOWED_USER_IDS)
        self.telegram_ids_input.setPlaceholderText("Your numeric Telegram user ID")
        telegram_layout.addWidget(self.telegram_ids_input)
        telegram_layout.addWidget(QLabel("Voice model / language (empty language = auto-detect)"))
        voice_row = QHBoxLayout()
        self.telegram_model_input = QLineEdit(config.TELEGRAM_WHISPER_MODEL)
        self.telegram_model_input.setPlaceholderText("base")
        self.telegram_language_input = QLineEdit(config.TELEGRAM_VOICE_LANGUAGE)
        self.telegram_language_input.setPlaceholderText("auto / en / hi")
        voice_row.addWidget(self.telegram_model_input)
        voice_row.addWidget(self.telegram_language_input)
        telegram_layout.addLayout(voice_row)
        self.telegram_enabled = QCheckBox("Connect Telegram automatically when this app starts")
        self.telegram_enabled.setChecked(config.TELEGRAM_ENABLED)
        telegram_layout.addWidget(self.telegram_enabled)
        voice_help = QLabel("Voice notes need requirements-telegram.txt. The first voice note downloads the multilingual model; text works without it. Replies are text. Changes require reconnecting Telegram.")
        voice_help.setWordWrap(True)
        telegram_layout.addWidget(voice_help)
        telegram_layout.addStretch()
        self.tabs.addTab(telegram_tab, "Telegram")

        # Tab 3: Shortcuts & Cheatsheet
        shortcuts_tab = QWidget()
        sc_layout = QVBoxLayout(shortcuts_tab)
        sc_layout.setContentsMargins(14, 16, 14, 16)
        sc_layout.setSpacing(10)

        cheat_text = QLabel("""
        <table style="width:100%; border-collapse:collapse; color:#cbd5e1; font-size:12px;">
            <tr style="border-bottom: 1px solid #1e293b;">
                <td style="padding:6px 0; color:#38bdf8; font-weight:bold;">Ctrl + Return / Enter</td>
                <td style="padding:6px 0;">Send query or command</td>
            </tr>
            <tr style="border-bottom: 1px solid #1e293b;">
                <td style="padding:6px 0; color:#38bdf8; font-weight:bold;">Ctrl + Space / F2</td>
                <td style="padding:6px 0;">Start 6-second voice recording</td>
            </tr>
            <tr style="border-bottom: 1px solid #1e293b;">
                <td style="padding:6px 0; color:#38bdf8; font-weight:bold;">Ctrl + N</td>
                <td style="padding:6px 0;">Start fresh conversation</td>
            </tr>
            <tr style="border-bottom: 1px solid #1e293b;">
                <td style="padding:6px 0; color:#38bdf8; font-weight:bold;">Ctrl + L</td>
                <td style="padding:6px 0;">Focus command prompt box</td>
            </tr>
            <tr style="border-bottom: 1px solid #1e293b;">
                <td style="padding:6px 0; color:#38bdf8; font-weight:bold;">Ctrl + M</td>
                <td style="padding:6px 0;">Toggle spoken replies (TTS)</td>
            </tr>
            <tr style="border-bottom: 1px solid #1e293b;">
                <td style="padding:6px 0; color:#38bdf8; font-weight:bold;">F5</td>
                <td style="padding:6px 0;">Refresh current weather forecast</td>
            </tr>
            <tr>
                <td style="padding:6px 0; color:#38bdf8; font-weight:bold;">Ctrl + ,</td>
                <td style="padding:6px 0;">Open this preferences dialog</td>
            </tr>
        </table>
        """)
        cheat_text.setTextFormat(Qt.RichText)
        sc_layout.addWidget(cheat_text)
        sc_layout.addStretch()
        self.tabs.addTab(shortcuts_tab, "Keyboard Shortcuts")

        layout.addWidget(self.tabs)

        # Footer Buttons
        footer = QHBoxLayout()
        footer.addStretch()
        cancel_btn = QPushButton("Cancel")
        cancel_btn.setObjectName("dialogSecondaryBtn")
        cancel_btn.clicked.connect(self.reject)
        footer.addWidget(cancel_btn)

        save_btn = QPushButton("Save Settings")
        save_btn.setObjectName("dialogPrimaryBtn")
        save_btn.clicked.connect(self._save_settings)
        footer.addWidget(save_btn)
        layout.addLayout(footer)

    def _toggle_key_visibility(self):
        if self.api_key_input.echoMode() == QLineEdit.Password:
            self.api_key_input.setEchoMode(QLineEdit.Normal)
            self.show_key_btn.setText("Hide Key")
        else:
            self.api_key_input.setEchoMode(QLineEdit.Password)
            self.show_key_btn.setText("Show Key")

    def _test_ai_connection(self):
        endpoint = self.endpoint_input.text().strip().rstrip("/")
        key = self.api_key_input.text().strip()
        if not endpoint:
            QMessageBox.warning(self, "Validation", "Please enter a valid Friday backend URL.")
            return

        import requests
        self.test_ai_btn.setEnabled(False)
        self.test_ai_btn.setText("Pinging...")
        try:
            res = requests.post(
                f"{endpoint}/chat",
                json={"message": "ping"},
                headers={"x-api-key": key, "ngrok-skip-browser-warning": "true"},
                timeout=6,
            )
            if res.status_code == 200:
                QMessageBox.information(self, "Success", "Connected to Friday backend successfully!")
            elif res.status_code == 401:
                QMessageBox.warning(self, "Auth Error", "Connected to server, but the API key was rejected (HTTP 401).")
            else:
                QMessageBox.warning(self, "Status", f"Server responded with code {res.status_code}.")
        except Exception as exc:
            QMessageBox.critical(self, "Connection Failed", f"Could not reach Friday backend:\n{exc}")
        finally:
            self.test_ai_btn.setEnabled(True)
            self.test_ai_btn.setText("Ping Friday Server")

    def _save_settings(self):
        token = self.telegram_token_input.text().strip()
        allowed_ids = self.telegram_ids_input.text().strip()
        language = self.telegram_language_input.text().strip().lower()
        if language == "auto":
            language = ""
        try:
            parse_allowed_ids(allowed_ids)
            if token and not re.fullmatch(r"[0-9]+:[A-Za-z0-9_-]{20,}", token):
                raise ValueError("Enter a valid bot token from BotFather.")
            if self.telegram_enabled.isChecked() and not token:
                raise ValueError("Enter a Telegram bot token before enabling automatic connection.")
            if language and not re.fullmatch(r"[a-z]{2,3}", language):
                raise ValueError("Use a language code such as en or hi, or leave it empty.")
        except ValueError as exc:
            QMessageBox.warning(self, "Telegram settings", str(exc))
            return
        settings_map = {
            "AI_ENDPOINT_URL": self.endpoint_input.text().strip().rstrip("/"),
            "FRIDAY_API_KEY": self.api_key_input.text().strip(),
            "OPENWEATHER_API_KEY": self.weather_key_input.text().strip(),
            "DEFAULT_CITY": self.city_input.text().strip() or "Nagpur",
            "TELEGRAM_BOT_TOKEN": token,
            "TELEGRAM_ALLOWED_USER_IDS": allowed_ids,
            "TELEGRAM_WHISPER_MODEL": self.telegram_model_input.text().strip() or "base",
            "TELEGRAM_VOICE_LANGUAGE": language,
            "TELEGRAM_ENABLED": "true" if self.telegram_enabled.isChecked() else "false",
        }

        # Quote values and replace atomically so tokens never become malformed
        # environment entries, and failed writes don't silently appear successful.
        env_path = Path(__file__).resolve().parents[1] / ".env"
        temporary = None
        try:
            with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", prefix=".env.", suffix=".tmp",
                                             dir=env_path.parent, delete=False) as handle:
                temporary = Path(handle.name)
                if env_path.is_file():
                    handle.write(env_path.read_text(encoding="utf-8"))
            for key, value in settings_map.items():
                set_key(str(temporary), key, value, quote_mode="always")
            os.replace(temporary, env_path)
        except Exception:
            QMessageBox.warning(self, "Save failed", "Could not save .env. Check folder permissions; settings have not been applied.")
            return
        finally:
            if temporary and temporary.exists():
                temporary.unlink()
        for key, value in settings_map.items():
            setattr(config, key, value == "true" if key == "TELEGRAM_ENABLED" else value)
        self.accept()

    def _apply_dialog_styles(self):
        self.setStyleSheet("""
            QDialog {
                background-color: #0b101c;
                color: #f8fafc;
                font-family: 'Segoe UI', sans-serif;
            }
            QLabel {
                color: #cbd5e1;
                font-size: 12px;
                font-weight: 500;
            }
            QLineEdit {
                background-color: #121a2c;
                color: #ffffff;
                border: 1px solid #1e2c45;
                border-radius: 8px;
                padding: 8px 12px;
                font-size: 13px;
            }
            QLineEdit:focus {
                border-color: #00d2b4;
            }
            QTabWidget::pane {
                border: 1px solid #1e293b;
                background: #0f172a;
                border-radius: 10px;
                top: -1px;
            }
            QTabBar::tab {
                background: #111a2d;
                color: #94a3b8;
                padding: 8px 16px;
                border-top-left-radius: 8px;
                border-top-right-radius: 8px;
                margin-right: 4px;
                font-weight: 600;
            }
            QTabBar::tab:selected {
                background: #0f172a;
                color: #00d2b4;
                border-bottom: 2px solid #00d2b4;
            }
            QPushButton {
                background: #16243d;
                color: #e2e8f0;
                border: 1px solid #233658;
                border-radius: 8px;
                padding: 8px 14px;
                font-size: 12px;
                font-weight: 600;
            }
            QPushButton:hover {
                background: #1e3357;
                color: #ffffff;
            }
            QPushButton#dialogPrimaryBtn {
                background: #00d2b4;
                color: #090d16;
                font-weight: 800;
                border: none;
            }
            QPushButton#dialogPrimaryBtn:hover {
                background: #23e5cb;
            }
            QPushButton#dialogSecondaryBtn {
                background: transparent;
                border: 1px solid #24324d;
                color: #94a3b8;
            }
            QPushButton#dialogSecondaryBtn:hover {
                background: #141f33;
                color: #ffffff;
            }
        """)
