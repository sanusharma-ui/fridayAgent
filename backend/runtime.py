"""Private JSON-lines bridge. Qt stays alive for settings and screen capture."""
import json
import sys
import threading

from PyQt5.QtCore import QObject, QThread, pyqtSignal
from PyQt5.QtWidgets import QApplication

from backend import config
from backend.services.agent import DesktopAgent
from backend.services.browser import BrowserController
from backend.services.commands import CommandRouter
from backend.services.friday_service import FridayService, is_ai_error
from backend.services.speech_recognition import listen_command, wake_word_loop
from backend.services.screenshot import capture_primary_screen
from backend.services.telegram_access import TelegramWorker
from backend.settings_dialog import SettingsDialog
from backend.services.weather import WeatherService


class Job(QThread):
    done = pyqtSignal(object, object)

    def __init__(self, action):
        super().__init__()
        self.action = action

    def run(self):
        try:
            self.done.emit(self.action(), None)
        except Exception as exc:
            self.done.emit(None, str(exc))


class WakeWordListener:
    def __init__(self, detected, error):
        self.detected = detected
        self.error = error
        self.stop_event = threading.Event()
        self.paused_event = threading.Event()
        self.thread = threading.Thread(target=self.run, name="wake-word-listener", daemon=True)

    def start(self):
        self.thread.start()

    def run(self):
        wake_word_loop(self.stop_event, self.paused_event, self.detected, self.error)

    def pause(self):
        self.paused_event.set()

    def resume(self):
        self.paused_event.clear()

    def stop(self):
        self.stop_event.set()
        self.paused_event.clear()


class Runtime(QObject):
    incoming = pyqtSignal(object)
    wake_detected_signal = pyqtSignal(str)
    wake_error_signal = pyqtSignal(str)

    def __init__(self, emit):
        super().__init__()
        self.emit = emit
        self.browser = BrowserController(config.BROWSER_CHANNEL)
        self.reload()
        self.jobs = set()
        self.busy = False
        self.closing = False
        self.telegram = None
        self.wake_detected_signal.connect(self.wake_detected)
        self.wake_error_signal.connect(self.wake_error)
        self.wake_listener = WakeWordListener(self.wake_detected_signal.emit, self.wake_error_signal.emit)
        self.incoming.connect(self.request)
        if config.TELEGRAM_ENABLED:
            self.toggle_telegram()
        self.emit({"type": "ready"})
        self.wake_listener.start()

    def reload(self):
        self.ai = FridayService()
        self.agent = DesktopAgent(self.ai, CommandRouter(self.ai, browser=self.browser))

    def message(self, text, role="system"):
        self.emit({"type": "message", "role": role, "text": str(text)})

    def state(self, status):
        self.emit({"type": "state", "status": status})

    def job(self, action, callback):
        job = Job(action)
        self.jobs.add(job)
        job.done.connect(callback)
        job.finished.connect(lambda: self.finished(job))
        job.start()

    def finished(self, job):
        self.jobs.discard(job)
        job.deleteLater()
        if self.closing:
            self.shutdown()

    def reply(self, result, error, remote=None):
        self.busy = False
        if not error and is_ai_error(result):
            error = result
        self.message(error or result, "system" if error else "sunday")
        self.state("error" if error else "idle")
        self.wake_listener.resume()
        if remote:
            remote.finish(error or result)

    def command(self, text, remote=None):
        self.busy = True
        self.state("thinking")
        action = (lambda: self.agent.handle(text, mail_context=f"telegram:{remote.user_id}")) if remote else (lambda: self.agent.handle(text))
        self.job(action, lambda result, error: self.reply(result, error, remote))

    def heard(self, text, error):
        self.busy = False
        if error or not text:
            self.reply("No speech recognized. Please try again.", error)
            return
        self.message(text, "user")
        self.command(text)

    def wake_detected(self, transcript):
        if self.closing or self.busy:
            self.wake_listener.resume()
            return
        self.message(f"Wake word detected: {transcript}", "system")
        self.busy = True
        self.state("listening")
        self.job(listen_command, self.heard)

    def wake_error(self, error):
        if not self.closing:
            self.message(f"Wake-word microphone: {error}")

    def request(self, request):
        if not isinstance(request, dict):
            return
        kind = request.get("type")
        if kind == "shutdown":
            self.closing = True
            self.shutdown()
            return
        if self.closing or self.busy:
            self.message("The assistant is busy. Please wait for the current task.")
            return
        if kind == "chat":
            text = request.get("text")
            if isinstance(text, str) and text.strip() and len(text) <= 4000:
                self.command(text.strip())
        elif kind == "listen":
            self.wake_listener.pause()
            self.busy = True
            self.state("listening")
            self.job(listen_command, self.heard)
        elif kind == "settings":
            self.busy = True
            self.state("working")
            dialog = SettingsDialog()
            if dialog.exec_():
                self.reload()
                if self.telegram:
                    self.telegram.stop()
                    self.message("Telegram disconnecting; reconnect to apply saved settings.")
                self.message("Backend settings saved.")
            self.busy = False
            self.state("idle")
        elif kind == "telegram":
            self.toggle_telegram()
        elif kind == "weather":
            self.busy = True
            self.state("thinking")
            self.job(lambda: WeatherService(config.OPENWEATHER_API_KEY).get_weather_report(config.DEFAULT_CITY), self.reply)

    def toggle_telegram(self):
        if self.telegram:
            self.telegram.stop()
            return
        try:
            worker = TelegramWorker(config.TELEGRAM_BOT_TOKEN, config.TELEGRAM_ALLOWED_USER_IDS,
                                    config.TELEGRAM_WHISPER_MODEL, config.TELEGRAM_VOICE_LANGUAGE, self)
            self.telegram = worker
            worker.status.connect(self.message)
            worker.task.connect(self.remote)
            worker.finished.connect(self.telegram_finished)
            worker.start()
        except ValueError as exc:
            self.message(str(exc))

    def telegram_finished(self):
        worker, self.telegram = self.telegram, None
        worker.deleteLater()
        self.message("Telegram: off")
        if self.closing:
            self.shutdown()

    def remote(self, task):
        if self.closing or self.busy or task.cancelled.is_set() or not self.telegram or self.telegram.stopped.is_set():
            task.finish("The assistant is busy or disconnected. Please try again later.")
        elif task.kind == "screenshot":
            try:
                task.finish(capture_primary_screen())
            except RuntimeError as exc:
                task.finish(str(exc))
        else:
            self.message(f"Telegram: {task.text}", "user")
            self.command(task.text, task)

    def shutdown(self):
        self.wake_listener.stop()
        if self.telegram:
            self.telegram.stop()
        if self.jobs or self.telegram:
            return
        self.browser.close()
        QApplication.instance().quit()


def main():
    sys.stdin.reconfigure(encoding="utf-8")
    sys.stdout.reconfigure(encoding="utf-8", line_buffering=True)
    output = sys.stdout
    sys.stdout = sys.stderr  # third-party logs cannot corrupt the protocol
    def emit(event):
        output.write(json.dumps(event, ensure_ascii=True) + "\n")
        output.flush()
    app = QApplication([])
    app.setQuitOnLastWindowClosed(False)
    runtime = Runtime(emit)
    def read():
        for line in sys.stdin:
            try:
                runtime.incoming.emit(json.loads(line))
            except ValueError:
                continue
        runtime.incoming.emit({"type": "shutdown"})
    threading.Thread(target=read, daemon=True).start()
    return app.exec_()


if __name__ == "__main__":
    raise SystemExit(main())
