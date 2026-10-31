import unittest
from unittest.mock import Mock, patch

from backend import config
import requests
from backend.services.friday_service import FridayService
from backend.services.groq_service import GroqService


class AIServiceTests(unittest.TestCase):
    def test_friday_remains_primary_when_it_succeeds(self):
        with patch("backend.services.friday_service.requests.post") as friday_post:
            friday_post.return_value.status_code = 200
            friday_post.return_value.json.return_value = {"response": "Friday answer"}
            with patch.object(config, "GROQ_ENABLED", True), \
                    patch.object(config, "GROQ_API_KEY", "groq-key"):
                result = FridayService("https://friday.test", "friday-key").ask("Hello")
            self.assertEqual(result, "Friday answer")
            friday_post.assert_called_once()

    def test_enabled_groq_is_used_when_friday_is_unavailable(self):
        def response_for_backend(url, **_):
            if url.endswith("/chat"):
                raise requests.ConnectionError("offline")
            response = Mock(status_code=200)
            response.json.return_value = {
                "choices": [{"message": {"content": "Groq answer"}}]
            }
            return response

        with patch("backend.services.friday_service.requests.post", side_effect=response_for_backend) as post:
            with patch.object(config, "GROQ_ENABLED", True), \
                    patch.object(config, "GROQ_API_KEY", "groq-key"):
                result = FridayService("https://friday.test", "friday-key").ask("Hello")
            self.assertEqual(result, "Groq answer")
            self.assertEqual(post.call_args.kwargs["headers"]["Authorization"], "Bearer groq-key")

    def test_disabled_groq_is_never_called(self):
        with patch("backend.services.friday_service.requests.post") as friday_post:
            friday_post.side_effect = requests.ConnectionError("offline")
            with patch.object(config, "GROQ_ENABLED", False), \
                    patch.object(config, "GROQ_API_KEY", "groq-key"):
                result = FridayService("https://friday.test", "friday-key").ask("Hello")
            self.assertIn("Friday is unavailable", result)

    def test_groq_client_uses_chat_completion_shape(self):
        with patch("backend.services.groq_service.requests.post") as post:
            post.return_value.status_code = 200
            post.return_value.json.return_value = {
                "choices": [{"message": {"content": "Answer"}}]
            }
            result = GroqService("groq-key", "test-model", "https://groq.test").ask("Hello")
            self.assertEqual(result, "Answer")
            self.assertEqual(post.call_args.kwargs["json"]["model"], "test-model")


if __name__ == "__main__":
    unittest.main()
