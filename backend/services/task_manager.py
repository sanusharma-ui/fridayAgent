"""Compatibility entry point for callers outside the window."""

from backend.services.commands import CommandRouter
from backend.services.friday_service import FridayService
from backend.services.agent import DesktopAgent
from backend.services.browser import BrowserController
import atexit
from backend import config

_browser = BrowserController(config.BROWSER_CHANNEL)
_ai = FridayService()
_router = CommandRouter(_ai, browser=_browser)
_agent = DesktopAgent(_ai, _router)
atexit.register(_browser.close)


def process_input(user_input):
    return _agent.handle(user_input)
