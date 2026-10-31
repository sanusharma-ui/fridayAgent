"""Exercise the real stdio bridge with a stubbed provider, without desktop actions."""
import json
import os
from pathlib import Path
import subprocess
import sys
import unittest


class RuntimeTests(unittest.TestCase):
    def test_real_process_routes_reply_and_shuts_down(self):
        script = '''
from backend import config
config.TELEGRAM_ENABLED = False
from backend.services.friday_service import FridayService
FridayService.ask = lambda self, prompt: '{"type":"chat"}' if 'desktop assistant planner' in prompt else 'Bridge reply: नमस्ते'
from backend.runtime import main
raise SystemExit(main())
'''
        env = dict(os.environ, QT_QPA_PLATFORM="offscreen", PYTHONIOENCODING="utf-8")
        result = subprocess.run([sys.executable, "-u", "-c", script],
            input=json.dumps({"type": "chat", "text": "Explain stars"}) + '\n',
            cwd=Path(__file__).resolve().parents[1], env=env,
            capture_output=True, text=True, encoding="utf-8", timeout=20)
        self.assertEqual(result.returncode, 0, result.stderr)
        events = [json.loads(line) for line in result.stdout.splitlines()]
        self.assertEqual(events[0], {"type": "ready"})
        self.assertIn({"type": "state", "status": "thinking"}, events)
        self.assertIn({"type": "message", "role": "sunday", "text": "Bridge reply: नमस्ते"}, events)
        self.assertEqual(events[-1], {"type": "state", "status": "idle"})

    def test_busy_gate_rejects_second_request(self):
        script = '''
from backend import config
config.TELEGRAM_ENABLED = False
from backend.services.agent import DesktopAgent
import time
def handle(self, text):
    time.sleep(.1)
    return "Handled " + text
DesktopAgent.handle = handle
from backend.runtime import main
raise SystemExit(main())
'''
        requests = [{"type": "chat", "text": "first"}, {"type": "chat", "text": "second"}]
        result = subprocess.run([sys.executable, "-u", "-c", script],
            input='\n'.join(json.dumps(r) for r in requests) + '\n',
            cwd=Path(__file__).resolve().parents[1],
            env=dict(os.environ, QT_QPA_PLATFORM="offscreen"),
            capture_output=True, text=True, encoding="utf-8", timeout=20)
        self.assertEqual(result.returncode, 0, result.stderr)
        events = [json.loads(line) for line in result.stdout.splitlines()]
        replies = [e['text'] for e in events if e.get('role') == 'sunday']
        self.assertEqual(replies, ['Handled first'])
        self.assertTrue(any('busy' in e.get('text', '') for e in events))


if __name__ == "__main__":
    unittest.main()
