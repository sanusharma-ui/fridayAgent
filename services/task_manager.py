"""Compatibility entry point for callers outside the window."""

from services.commands import CommandRouter
from services.friday_service import FridayService

_router = CommandRouter(FridayService())


def process_input(user_input):
    return _router.handle(user_input)
