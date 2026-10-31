"""On-demand primary-display capture for an authorized Telegram request."""

from dataclasses import dataclass
from datetime import datetime
import re

from PyQt5.QtCore import QBuffer, QByteArray, QIODevice, QThread, Qt
from PyQt5.QtGui import QGuiApplication


@dataclass(frozen=True)
class Screenshot:
    data: bytes
    filename: str
    caption: str


def is_screenshot_request(text):
    request = " ".join(text.casefold().strip().split()).rstrip(".!?")
    if request == "/screenshot":
        return True
    request = re.sub(r"^(?:(?:please|can you|could you|would you)\s+)+", "", request)
    noun = r"(?:screenshot|screen shot|screenshort|स्क्रीनशॉट)"
    patterns = (
        rf"{noun}",
        rf"(?:take|capture|get|send)(?: me)?\s+(?:(?:a|the|my|current|desktop|laptop)\s+)*{noun}"
        r"(?: of (?:my |the )?(?:screen|desktop|laptop))?"
        r"(?: for me)?(?: (?:and )?send (?:it )?(?:to me|on telegram|to telegram))?(?: please)?",
        rf"(?:(?:ek|mera|mere laptop ka|mere screen ka)\s+)?{noun}"
        r"\s+(?:lo|le lo|leke bhejo|le kar bhejo|le ke bhejo|bhejo|bhej do|lelo|लो|भेजो|भेज दो)",
    )
    return any(re.fullmatch(pattern, request) for pattern in patterns)


def encode_screenshot(pixmap):
    if pixmap.isNull():
        raise RuntimeError("Could not capture the screen. Keep the Windows desktop signed in and unlocked.")
    # Leave headroom for Telegram's photo dimensions and file-size limits.
    if max(pixmap.width(), pixmap.height()) > 2560:
        pixmap = pixmap.scaled(2560, 2560, Qt.KeepAspectRatio, Qt.SmoothTransformation)
    if max(pixmap.width(), pixmap.height()) / min(pixmap.width(), pixmap.height()) > 20:
        raise RuntimeError("This display's aspect ratio is not supported for Telegram photos.")
    encoded = QByteArray()
    buffer = QBuffer(encoded)
    buffer.open(QIODevice.WriteOnly)
    if not pixmap.save(buffer, "JPEG", 90):
        raise RuntimeError("Could not encode the screenshot.")
    buffer.close()
    data = bytes(encoded)
    if not data or len(data) > 9 * 1024 * 1024:
        raise RuntimeError("The screenshot is too large to send as a Telegram photo.")
    now = datetime.now()
    return Screenshot(data, f"screenshot-{now:%Y%m%d-%H%M%S}.jpg",
                      f"Laptop screenshot — primary display — {now:%d %b %Y, %H:%M:%S}")


def capture_primary_screen():
    app = QGuiApplication.instance()
    if app is None or QThread.currentThread() != app.thread():
        raise RuntimeError("Screen capture must run through the desktop window.")
    screen = app.primaryScreen()
    if screen is None:
        raise RuntimeError("No active display is available for a screenshot.")
    return encode_screenshot(screen.grabWindow(0))
