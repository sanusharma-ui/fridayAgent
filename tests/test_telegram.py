import tempfile
import threading
import time
import unittest
from pathlib import Path
from unittest.mock import Mock

import requests

from backend.services.telegram_access import (TelegramBridge, TelegramClient, TelegramError,
                                      MAX_VOICE_BYTES, parse_allowed_ids)
from backend.services.screenshot import Screenshot


class FakeClient:
    def __init__(self):
        self.sent = []
        self.downloads = []
        self.photos = []

    def send(self, chat_id, text):
        self.sent.append((chat_id, text))

    def download_voice(self, file_id, path):
        self.downloads.append(path)
        path.write_bytes(b"fake audio")

    def send_photo(self, chat_id, screenshot):
        self.photos.append((chat_id, screenshot))


class TelegramAccessTests(unittest.TestCase):
    def setUp(self):
        self.client = FakeClient()
        self.executed = []
        self.stop = threading.Event()
        self.bridge = TelegramBridge(self.client, {123}, self.execute,
                                     lambda path: "open youtube", self.stop)

    def execute(self, text):
        self.executed.append(text)
        return "Action completed"

    def update(self, text=None, user=123, update_id=1, voice=False, **fields):
        message = {"date": int(time.time()), "from": {"id": user},
                   "chat": {"id": user, "type": "private"}, **fields}
        if text is not None:
            message["text"] = text
        if voice:
            message["voice"] = {"file_id": "voice-id", "duration": 5, "file_size": 200}
        return {"update_id": update_id, "message": message}

    def test_private_allowlist_before_voice_download(self):
        self.bridge.process_update(self.update(user=456, voice=True))
        self.assertEqual(self.client.downloads, [])
        self.assertEqual(self.executed, [])
        self.assertEqual(self.client.sent, [])

    def test_group_and_forwarded_messages_do_not_execute(self):
        update = self.update("open youtube")
        update["message"]["chat"] = {"id": -99, "type": "group"}
        self.bridge.process_update(update)
        self.bridge.process_update(self.update("open youtube", update_id=2, forward_origin={"type": "user"}))
        self.assertFalse(self.executed)

    def test_setup_only_allows_id_lookup(self):
        self.bridge.allowed_ids = frozenset()
        self.bridge.process_update(self.update("/id"))
        self.assertIn("123", self.client.sent[-1][1])
        self.bridge.process_update(self.update("open youtube", update_id=2))
        self.assertFalse(self.executed)

    def test_text_task_is_executed_once_and_reports_result(self):
        update = self.update("can you open youtube for me")
        self.bridge.process_update(update)
        self.bridge.process_update(update)
        self.assertEqual(self.executed, ["can you open youtube for me"])
        self.assertIn("Thinking", self.client.sent[0][1])
        self.assertEqual(self.client.sent[-1][1], "Action completed")

    def test_scoped_dispatch_preserves_authorized_user_identity(self):
        self.bridge.execute_scoped = Mock(return_value="Draft ready")
        self.bridge.process_update(self.update("email Alex about a meeting"))
        self.bridge.execute_scoped.assert_called_once_with("email Alex about a meeting", 123)
        self.assertFalse(self.executed)

    def test_voice_is_transcribed_and_temp_file_removed(self):
        self.bridge.process_update(self.update(voice=True))
        self.assertEqual(self.executed, ["open youtube"])
        self.assertTrue(any("Heard: open youtube" in text for _, text in self.client.sent))
        self.assertFalse(self.client.downloads[0].exists())

    def test_voice_help_is_authorized_and_does_not_execute(self):
        self.bridge.process_update(self.update("/voice", user=456))
        self.assertFalse(self.client.sent)
        self.bridge.process_update(self.update("/voice", update_id=2))
        self.assertIn("microphone", self.client.sent[-1][1])
        self.assertIn("60 seconds", self.client.sent[-1][1])
        self.assertFalse(self.executed)

    def test_voice_error_does_not_execute(self):
        self.bridge.transcribe = Mock(side_effect=RuntimeError("Install voice dependencies"))
        self.bridge.process_update(self.update(voice=True))
        self.assertFalse(self.executed)
        self.assertFalse(self.client.downloads[0].exists())
        self.assertIn("dependencies", self.client.sent[-1][1])

    def test_oversized_voice_and_stale_messages_do_not_execute(self):
        update = self.update(voice=True)
        update["message"]["voice"]["file_size"] = MAX_VOICE_BYTES + 1
        self.bridge.process_update(update)
        self.bridge.process_update(self.update("open youtube", update_id=2, date=int(time.time()) - 300))
        self.assertFalse(self.executed)
        self.assertFalse(self.client.downloads)

    def test_pause_resume_and_disconnected_guard(self):
        self.bridge.process_update(self.update("/pause"))
        self.bridge.process_update(self.update("open youtube", update_id=2))
        self.assertFalse(self.executed)
        self.bridge.process_update(self.update("/resume", update_id=3))
        self.bridge.process_update(self.update("open youtube", update_id=4))
        self.assertEqual(self.executed, ["open youtube"])
        self.stop.set()
        self.bridge.process_update(self.update("open notepad", update_id=5))
        self.assertEqual(self.executed, ["open youtube"])

    def test_failed_result_delivery_does_not_repeat_action(self):
        self.client.send = Mock(side_effect=[None, TelegramError("offline")])
        update = self.update("open youtube")
        with self.assertRaises(TelegramError):
            self.bridge.process_update(update)
        self.bridge.process_update(update)
        self.assertEqual(self.executed, ["open youtube"])

    def test_connection_discards_offline_backlog(self):
        offsets = []
        def updates(offset, timeout=10):
            offsets.append(offset)
            if offset == -1:
                return [self.update("old request", update_id=10)]
            self.stop.set()
            return []
        self.client.updates = updates
        self.client.call = Mock(return_value={})
        self.client.close = Mock()
        self.bridge.run()
        self.assertEqual(offsets, [-1, 11])
        self.assertFalse(self.executed)

    def test_client_redacts_token_in_exception(self):
        token = "123:" + "x" * 30
        session = Mock()
        session.post.side_effect = requests.ConnectionError("https://api.telegram.org/bot" + token)
        with self.assertRaises(TelegramError) as raised:
            TelegramClient(token, session).call("getMe")
        self.assertNotIn(token, str(raised.exception))

    def test_client_rejects_file_path_escape(self):
        client = TelegramClient("123:" + "x" * 30, Mock())
        client.call = Mock(return_value={"file_path": "../secret", "file_size": 1})
        with tempfile.TemporaryDirectory() as folder, self.assertRaises(TelegramError):
            client.download_voice("id", Path(folder) / "audio")

    def test_numeric_ids_fail_closed(self):
        self.assertEqual(parse_allowed_ids("123, 456"), {123, 456})
        for value in ("all", "123,", "-100", "@username"):
            with self.assertRaises(ValueError):
                parse_allowed_ids(value)

    def test_screenshot_sent_only_to_requesting_authorized_chat(self):
        photo = Screenshot(b"fake-jpeg", "screenshot.jpg", "Captured")
        self.bridge.capture = Mock(return_value=photo)
        self.bridge.allowed_ids = {123, 456}
        update = self.update("/screenshot")
        self.bridge.process_update(update)
        self.bridge.process_update(update)
        self.bridge.capture.assert_called_once_with()
        self.assertEqual(self.client.photos, [(123, photo)])
        self.assertFalse(self.executed)

    def test_unauthorized_and_paused_screenshots_never_capture(self):
        self.bridge.capture = Mock()
        self.bridge.process_update(self.update("/screenshot", user=456))
        self.bridge.paused = True
        self.bridge.process_update(self.update("screenshot bhejo", update_id=2))
        self.bridge.capture.assert_not_called()
        self.assertFalse(self.client.photos)

    def test_voice_screenshot_reaches_capture_without_llm(self):
        photo = Screenshot(b"fake-jpeg", "screenshot.jpg", "Captured")
        self.bridge.capture = Mock(return_value=photo)
        self.bridge.transcribe = lambda path: "take a screenshot"
        self.bridge.process_update(self.update(voice=True))
        self.assertEqual(self.client.photos, [(123, photo)])
        self.assertFalse(self.executed)

    def test_capture_error_is_reported_without_upload(self):
        self.bridge.capture = Mock(return_value="Could not capture the screen")
        self.bridge.process_update(self.update("/screenshot"))
        self.assertEqual(self.client.sent[-1][1], "Could not capture the screen")
        self.assertFalse(self.client.photos)

    def test_disconnect_after_capture_prevents_upload(self):
        def capture():
            self.stop.set()
            return Screenshot(b"fake-jpeg", "screenshot.jpg", "Captured")
        self.bridge.capture = capture
        self.bridge.process_update(self.update("/screenshot"))
        self.assertFalse(self.client.photos)

    def test_upload_failure_reports_failure_without_recapture(self):
        self.bridge.capture = Mock(return_value=Screenshot(b"fake-jpeg", "screen.jpg", "Captured"))
        self.client.send_photo = Mock(side_effect=TelegramError("offline"))
        self.bridge.process_update(self.update("/screenshot"))
        self.bridge.capture.assert_called_once_with()
        self.assertIn("upload failed", self.client.sent[-1][1])

    def test_photo_upload_uses_multipart_and_redacts_network_errors(self):
        token = "123:" + "x" * 30
        session = Mock()
        session.post.return_value.status_code = 200
        session.post.return_value.json.return_value = {"ok": True}
        photo = Screenshot(b"fake-jpeg", "screen.jpg", "Captured")
        client = TelegramClient(token, session)
        client.send_photo(123, photo)
        kwargs = session.post.call_args.kwargs
        self.assertEqual(kwargs["data"]["chat_id"], 123)
        self.assertEqual(kwargs["files"]["photo"], ("screen.jpg", b"fake-jpeg", "image/jpeg"))
        session.post.side_effect = requests.ConnectionError(token)
        with self.assertRaises(TelegramError) as raised:
            client.send_photo(123, photo)
        self.assertNotIn(token, str(raised.exception))


if __name__ == "__main__":
    unittest.main()
