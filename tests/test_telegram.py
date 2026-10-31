import tempfile
import threading
import time
import unittest
from pathlib import Path
from unittest.mock import Mock

import requests

from services.telegram_access import (TelegramBridge, TelegramClient, TelegramError,
                                      MAX_VOICE_BYTES, parse_allowed_ids)


class FakeClient:
    def __init__(self):
        self.sent = []
        self.downloads = []

    def send(self, chat_id, text):
        self.sent.append((chat_id, text))

    def download_voice(self, file_id, path):
        self.downloads.append(path)
        path.write_bytes(b"fake audio")


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

    def test_voice_is_transcribed_and_temp_file_removed(self):
        self.bridge.process_update(self.update(voice=True))
        self.assertEqual(self.executed, ["open youtube"])
        self.assertTrue(any("Heard: open youtube" in text for _, text in self.client.sent))
        self.assertFalse(self.client.downloads[0].exists())

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


if __name__ == "__main__":
    unittest.main()
