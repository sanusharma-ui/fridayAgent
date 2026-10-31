import json
import unittest
import subprocess
import tempfile
from pathlib import Path
from unittest.mock import patch

from services.agent import DesktopAgent
from services.commands import CommandRouter, launch_program
from services.notepad import NotepadWriter


class FakeAI:
    def __init__(self, plan):
        self.plan = plan
        self.requests = []

    def ask(self, text):
        self.requests.append(text)
        return self.plan if text.startswith("You are a desktop assistant planner") else "A normal answer."


class AgentTests(unittest.TestCase):
    def setUp(self):
        self.opened = []
        self.ai = FakeAI("")
        self.router = CommandRouter(self.ai, open_url=lambda url: self.opened.append(url) or True)
        self.agent = DesktopAgent(self.ai, self.router)

    def plan(self, *calls):
        self.ai.plan = json.dumps({"type": "tools", "calls": [
            {"tool": tool, "argument": argument} for tool, argument in calls
        ]})

    def test_polite_open_works_without_backend(self):
        self.agent.handle("can you open youtube for me")
        self.assertEqual(self.opened, ["https://www.youtube.com"])
        self.assertFalse(self.ai.requests)

    def test_natural_language_uses_tool_result(self):
        self.plan(("open", "facebook"))
        result = self.agent.handle("I would like to visit facebook")
        self.assertIn("Opening Facebook", result)
        self.assertEqual(self.opened, ["https://www.facebook.com"])

    def test_hinglish_open_routes_without_backend(self):
        self.agent.handle("youtube khol do")
        self.assertEqual(self.opened, ["https://www.youtube.com"])
        self.assertFalse(self.ai.requests)

    def test_terminal_uses_powershell_and_separate_console(self):
        with patch("services.commands.subprocess.Popen") as process:
            router = CommandRouter(self.ai)
            result = router.handle("open terminal")
            self.assertEqual(result, "Opening terminal.")
            process.assert_called_once_with(["powershell.exe"], creationflags=subprocess.CREATE_NEW_CONSOLE)

    def test_gui_app_does_not_request_console(self):
        with patch("services.commands.subprocess.Popen") as process:
            launch_program("notepad.exe")
            process.assert_called_once_with(["notepad.exe"])

    def test_multiple_tools_execute_in_order(self):
        self.plan(("open", "youtube"), ("search_web", "weather in Delhi"))
        self.agent.handle("open youtube and search weather in Delhi")
        self.assertEqual(len(self.opened), 2)
        self.assertIn("youtube.com", self.opened[0])
        self.assertIn("weather+in+Delhi", self.opened[1])

    def test_invalid_later_call_prevents_all_execution(self):
        self.plan(("open", "youtube"), ("open", "invented"))
        result = self.agent.handle("please open youtube and another site")
        self.assertIn("couldn't verify", result)
        self.assertFalse(self.opened)

    def test_unsupported_and_negated_requests_do_not_execute(self):
        self.plan(("open", "youtube"))
        self.agent.handle("don't open youtube")
        self.agent.handle("open youtube and delete my files")
        self.assertFalse(self.opened)

    def test_question_does_not_execute_bad_plan(self):
        self.plan(("open", "youtube"))
        self.assertEqual(self.agent.handle("how do I open youtube?"), "A normal answer.")
        self.assertFalse(self.opened)

    def test_invalid_json_and_backend_error_are_visible(self):
        self.ai.plan = "not JSON"
        self.assertIn("couldn't understand", self.agent.handle("visit youtube"))
        self.ai.plan = "Friday is unavailable: connection failed"
        self.assertIn("unavailable", self.agent.handle("visit youtube"))

    def test_essay_is_generated_then_opened_as_a_new_document(self):
        with tempfile.TemporaryDirectory() as folder:
            opened = []
            self.agent.notepad = NotepadWriter(self.ai, folder, opened.append)
            result = self.agent.handle("write essay about moons")
            self.assertIn("opened it in Notepad", result)
            self.assertEqual(len(opened), 1)
            self.assertEqual(opened[0].read_text(encoding="utf-8-sig"), "A normal answer.")
            self.assertIn("write essay about moons", self.ai.requests[0])

    def test_verbatim_text_skips_generation(self):
        with tempfile.TemporaryDirectory() as folder:
            opened = []
            self.agent.notepad = NotepadWriter(self.ai, folder, opened.append)
            self.agent.handle("write exactly Hello from NEO")
            self.assertEqual(opened[0].read_text(encoding="utf-8-sig"), "Hello from NEO")
            self.assertFalse(self.ai.requests)

    def test_generation_error_does_not_create_or_open_a_file(self):
        class FailedAI:
            def ask(self, _):
                return "Friday is unavailable: timeout"
        with tempfile.TemporaryDirectory() as folder:
            opened = []
            writer = NotepadWriter(FailedAI(), folder, opened.append)
            self.assertIn("unavailable", writer.write("write an essay about moons"))
            self.assertEqual(list(Path(folder).iterdir()), [])
            self.assertFalse(opened)

    def test_planned_notepad_action_passes_full_request(self):
        self.plan(("write_notepad", "moon par essay likho"))
        with tempfile.TemporaryDirectory() as folder:
            opened = []
            self.agent.notepad = NotepadWriter(self.ai, folder, opened.append)
            self.agent.handle("notepad mein moon par essay likho")
            self.assertIn("notepad mein moon par essay likho", self.ai.requests[-1])
            self.assertEqual(opened[0].read_text(encoding="utf-8-sig"), "A normal answer.")


if __name__ == "__main__":
    unittest.main()
