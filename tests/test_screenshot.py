import os
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from PyQt5.QtGui import QGuiApplication, QPixmap, QImage, QColor

from backend.services.screenshot import encode_screenshot, is_screenshot_request


class ScreenshotTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QGuiApplication.instance() or QGuiApplication([])

    def test_explicit_requests(self):
        for text in ("/screenshot", "screenshot", "take a screenshot", "can you take a screenshot for me",
                     "screenshot bhejo", "please send me a screenshot", "screenshort lo", "स्क्रीनशॉट लो"):
            with self.subTest(text=text):
                self.assertTrue(is_screenshot_request(text))

    def test_questions_negation_and_other_recipients_are_not_capture_requests(self):
        for text in ("how do I take a screenshot?", "don't take a screenshot", "screenshot mat lo",
                     "send a screenshot to someone else", "what is screenshot", "take a screenshot tomorrow"):
            with self.subTest(text=text):
                self.assertFalse(is_screenshot_request(text))

    def test_synthetic_image_is_bounded_and_encoded_in_memory(self):
        pixmap = QPixmap(4000, 2000)
        pixmap.fill(QColor("#204060"))
        result = encode_screenshot(pixmap)
        image = QImage.fromData(result.data)
        self.assertFalse(image.isNull())
        self.assertEqual((image.width(), image.height()), (2560, 1280))
        self.assertLess(len(result.data), 9 * 1024 * 1024)
        self.assertTrue(result.filename.endswith(".jpg"))

    def test_null_capture_does_not_produce_attachment(self):
        with self.assertRaises(RuntimeError):
            encode_screenshot(QPixmap())
