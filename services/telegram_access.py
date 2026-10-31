"""Private Telegram text/voice access to the existing desktop agent.

No public web server is needed. All traffic uses Telegram HTTPS long polling.
"""

import re
import tempfile
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath

import requests
from PyQt5.QtCore import QThread, pyqtSignal

from services.telegram_voice import VoiceTranscriber
from services.screenshot import Screenshot, is_screenshot_request


MAX_VOICE_BYTES = 10 * 1024 * 1024
MAX_REQUEST_CHARS = 1500


def parse_allowed_ids(value):
    if not value.strip():
        return frozenset()
    parts = [item.strip() for item in value.split(",")]
    if any(not re.fullmatch(r"[1-9][0-9]*", item) for item in parts):
        raise ValueError("Telegram allowed IDs must be positive numeric user IDs separated by commas.")
    return frozenset(int(item) for item in parts)


class TelegramError(RuntimeError):
    def __init__(self, message, fatal=False):
        super().__init__(message)
        self.fatal = fatal


class TelegramClient:
    def __init__(self, token, session=None):
        if not re.fullmatch(r"[0-9]+:[A-Za-z0-9_-]{20,}", token):
            raise ValueError("Enter a valid Telegram bot token from BotFather in Settings or .env.")
        self.token = token
        self.session = session or requests.Session()

    def call(self, method, data=None, poll=False):
        try:
            response = self.session.post(
                f"https://api.telegram.org/bot{self.token}/{method}",
                json=data or {}, timeout=(5, 15 if poll else 10),
            )
            if response.status_code in (401, 404):
                raise TelegramError("Telegram rejected the bot token. Check Settings.", fatal=True)
            if response.status_code == 409:
                raise TelegramError("Telegram has another poller or webhook connected. Stop it before using this app.", fatal=True)
            response.raise_for_status()
            body = response.json()
            if not isinstance(body, dict) or not body.get("ok"):
                raise TelegramError("Telegram could not complete the request. Try again later.")
            return body.get("result")
        except (requests.RequestException, ValueError):
            # Requests exceptions include the URL, which contains the bot token.
            raise TelegramError("Telegram connection failed. Check your internet connection.") from None

    def updates(self, offset, timeout=10):
        result = self.call("getUpdates", {"offset": offset, "timeout": timeout,
                                         "allowed_updates": ["message"], "limit": 20}, poll=True)
        if not isinstance(result, list):
            raise TelegramError("Telegram returned an invalid update list.")
        return result

    def send(self, chat_id, text):
        # Plain text prevents a generated answer from injecting Telegram markup.
        text = str(text).replace(self.token, "[redacted]")[:14000]
        for position in range(0, len(text), 3000):
            self.call("sendMessage", {"chat_id": chat_id, "text": text[position:position + 3000],
                                      "link_preview_options": {"is_disabled": True}})

    def send_photo(self, chat_id, screenshot):
        if not isinstance(screenshot, Screenshot) or not screenshot.data or len(screenshot.data) > 9 * 1024 * 1024:
            raise TelegramError("The captured screenshot is invalid or too large.")
        try:
            response = self.session.post(
                f"https://api.telegram.org/bot{self.token}/sendPhoto",
                data={"chat_id": chat_id, "caption": screenshot.caption},
                files={"photo": (screenshot.filename, screenshot.data, "image/jpeg")},
                timeout=(5, 30),
            )
            if response.status_code in (401, 404):
                raise TelegramError("Telegram rejected the bot token. Check Settings.", fatal=True)
            response.raise_for_status()
            body = response.json()
            if not isinstance(body, dict) or not body.get("ok"):
                raise TelegramError("Telegram rejected the screenshot upload.")
        except (requests.RequestException, ValueError):
            raise TelegramError("Screenshot upload failed. Check your connection and request a new screenshot.") from None

    def download_voice(self, file_id, destination):
        info = self.call("getFile", {"file_id": file_id})
        if not isinstance(info, dict):
            raise TelegramError("Telegram could not locate the voice recording.")
        if info.get("file_size", 0) > MAX_VOICE_BYTES:
            raise TelegramError("Voice notes must be smaller than 10 MB.")
        name = info.get("file_path", "")
        path = PurePosixPath(name)
        if not name or path.is_absolute() or ".." in path.parts or not re.fullmatch(r"[A-Za-z0-9_./-]+", name):
            raise TelegramError("Telegram returned an invalid voice-file location.")
        try:
            with self.session.get(f"https://api.telegram.org/file/bot{self.token}/{name}",
                                  stream=True, timeout=(5, 15)) as response:
                response.raise_for_status()
                total = 0
                with Path(destination).open("wb") as output:
                    for chunk in response.iter_content(65536):
                        total += len(chunk)
                        if total > MAX_VOICE_BYTES:
                            raise TelegramError("Voice notes must be smaller than 10 MB.")
                        output.write(chunk)
        except requests.RequestException:
            raise TelegramError("Could not download the voice note. Please send it again.") from None

    def close(self):
        self.session.close()


class TelegramBridge:
    def __init__(self, client, allowed_ids, execute, transcribe, stopped=None, status=None, capture=None):
        self.client = client
        self.allowed_ids = frozenset(allowed_ids)
        self.execute = execute
        self.transcribe = transcribe
        self.stopped = stopped or threading.Event()
        self.status = status or (lambda text: None)
        self.paused = False
        self.offset = 0
        self.capture = capture

    def run(self):
        try:
            self.status("Telegram: connecting...")
            self.client.call("getMe")
            # Discard offline/backlogged actions on every explicit connection.
            pending = self.client.updates(-1, timeout=0)
            self.offset = max((item["update_id"] + 1 for item in pending), default=0)
            ready = "Telegram: connected" if self.allowed_ids else "Telegram: setup only — send /id"
            self.status(ready)
            while not self.stopped.is_set():
                try:
                    updates = self.client.updates(self.offset)
                    self.status("Telegram: paused" if self.paused else ready)
                    for update in updates:
                        if self.stopped.is_set():
                            break
                        self.process_update(update)
                except TelegramError as exc:
                    if exc.fatal:
                        raise
                    self.status(str(exc))
                    self.stopped.wait(5)
        except TelegramError as exc:
            self.status(str(exc))
        except Exception:
            self.status("Telegram stopped after an unexpected error. Check configuration and reconnect.")
        finally:
            self.client.close()

    def process_update(self, update):
        update_id = update.get("update_id")
        if not isinstance(update_id, int) or update_id < self.offset:
            return
        # Advance before dispatch. Delivery retries must never repeat an action.
        self.offset = update_id + 1
        message = update.get("message")
        if not isinstance(message, dict):
            return
        chat, sender = message.get("chat", {}), message.get("from", {})
        user_id, chat_id = sender.get("id"), chat.get("id")
        if chat.get("type") != "private" or not isinstance(user_id, int) or chat_id != user_id or sender.get("is_bot"):
            return
        date = message.get("date", 0)
        if not isinstance(date, (int, float)) or not 0 <= time.time() - date <= 120:
            return
        text = message.get("text", "").strip()
        # ID lookup is the only operation available without authorization.
        if text == "/id":
            self.client.send(chat_id, f"Your Telegram user ID: {user_id}\nAdd this number to Allowed user IDs in the laptop app's Telegram settings.")
            return
        if user_id not in self.allowed_ids:
            return
        if message.get("forward_origin") or message.get("forward_from") or message.get("forward_date"):
            self.client.send(chat_id, "Forwarded messages are not executed. Please send your own request directly.")
            return
        if text in ("/start", "/help"):
            self.client.send(chat_id, "Connected to your laptop agent. Send text or a voice note (up to 60 seconds).\nExamples: open YouTube; write an essay about moons; create a PDF about space.\n/screenshot — capture the laptop's primary display and send the image here\n/status — connection status\n/pause — pause new tasks\n/resume — allow new tasks\n/id — your user ID\nActions run on your laptop. Screenshots are sent as photos; other generated documents remain on the laptop.")
            return
        if text == "/pause":
            self.paused = True
            self.status("Telegram: paused")
            self.client.send(chat_id, "New Telegram tasks are paused. Use /resume to continue.")
            return
        if text == "/resume":
            self.paused = False
            self.status("Telegram: connected")
            self.client.send(chat_id, "Telegram tasks resumed.")
            return
        if text == "/status":
            self.client.send(chat_id, "Laptop connected. Telegram tasks are " + ("paused." if self.paused else "enabled."))
            return
        if self.paused:
            self.client.send(chat_id, "Telegram tasks are paused. Send /resume first.")
            return
        if text.startswith("/") and text != "/screenshot":
            self.client.send(chat_id, "Unknown command. Use /help or send a normal text/voice request.")
            return
        voice = message.get("voice")
        if voice:
            if not isinstance(voice, dict) or voice.get("duration", 999) > 60 or voice.get("file_size", 0) > MAX_VOICE_BYTES:
                self.client.send(chat_id, "Please send a voice note up to 60 seconds and 10 MB.")
                return
            file_id = voice.get("file_id")
            if not isinstance(file_id, str) or not file_id:
                return
            self.client.send(chat_id, "Transcribing your voice note... First use may download the speech model.")
            try:
                with tempfile.TemporaryDirectory(prefix="neo-telegram-") as folder:
                    audio_path = Path(folder) / "voice.ogg"
                    self.client.download_voice(file_id, audio_path)
                    if self.stopped.is_set():
                        return
                    text = self.transcribe(audio_path)
            except (RuntimeError, ValueError) as exc:
                self.client.send(chat_id, str(exc))
                return
            except Exception:
                self.client.send(chat_id, "Voice transcription failed. Try a shorter voice note or send text.")
                return
            if self.stopped.is_set():
                return
            if not text.strip():
                self.client.send(chat_id, "No speech recognized. Please try again or send text.")
                return
            self.client.send(chat_id, "Heard: " + text[:MAX_REQUEST_CHARS])
        if not text:
            self.client.send(chat_id, "Please send text or a Telegram voice note.")
            return
        if len(text) > MAX_REQUEST_CHARS:
            self.client.send(chat_id, "Please keep requests under 1500 characters.")
            return
        if self.stopped.is_set():
            return
        if is_screenshot_request(text):
            self._send_screenshot(chat_id)
            return
        self.client.send(chat_id, "Thinking... Working on your laptop.")
        result = self.execute(text)
        if not self.stopped.is_set():
            self.client.send(chat_id, result)

    def _send_screenshot(self, chat_id):
        if self.capture is None:
            self.client.send(chat_id, "Screen capture is not connected. Please restart the desktop app.")
            return
        self.client.send(chat_id, "Capturing your laptop screen...")
        result = self.capture()
        if self.stopped.is_set():
            return
        if not isinstance(result, Screenshot):
            self.client.send(chat_id, str(result))
            return
        try:
            self.client.send_photo(chat_id, result)
            self.status("Telegram: screenshot sent")
        except TelegramError as exc:
            self.status(str(exc))
            if exc.fatal:
                raise
            self.client.send(chat_id, "The screenshot was captured, but upload failed. Send /screenshot to try again.")


@dataclass
class RemoteTask:
    text: str
    kind: str = "agent"
    completed: threading.Event = field(default_factory=threading.Event)
    cancelled: threading.Event = field(default_factory=threading.Event)
    result: object = ""

    def finish(self, result):
        self.result = result if isinstance(result, Screenshot) else str(result)
        self.completed.set()


class TelegramWorker(QThread):
    status = pyqtSignal(str)
    task = pyqtSignal(object)

    def __init__(self, token, allowed_ids, model, language, parent=None):
        super().__init__(parent)
        self.stopped = threading.Event()
        authorized = parse_allowed_ids(allowed_ids)
        self.client = TelegramClient(token)
        self.transcriber = VoiceTranscriber(model, language)
        self.bridge = TelegramBridge(self.client, authorized, self._execute,
                                     self.transcriber.transcribe, self.stopped, self.status.emit,
                                     capture=lambda: self._execute("Take a screenshot", kind="screenshot"))

    def _execute(self, text, kind="agent"):
        task = RemoteTask(text, kind=kind)
        self.task.emit(task)
        while not task.completed.wait(0.1):
            if self.stopped.is_set():
                task.cancelled.set()
                return "Telegram disconnected."
        return task.result

    def run(self):
        self.bridge.run()

    def stop(self):
        self.stopped.set()
