"""Client for the Friday Colab backend exposed through ngrok."""

import requests

from backend import config
from backend.services.groq_service import GroqService


AI_ERROR_PREFIXES = (
    "Friday is unavailable:",
    "Friday API key was rejected.",
    "Friday returned",
    "Set FRIDAY_API_KEY",
    "Groq is unavailable:",
    "Groq API key was rejected.",
    "Groq returned",
    "Groq API key is not configured.",
)


def is_ai_error(response: str) -> bool:
    return isinstance(response, str) and response.startswith(AI_ERROR_PREFIXES)


class FridayService:
    def __init__(self, endpoint=None, api_key=None):
        self.endpoint = (endpoint or config.AI_ENDPOINT_URL).rstrip("/")
        self.api_key = api_key if api_key is not None else config.FRIDAY_API_KEY

    def ask(self, prompt: str) -> str:
        prompt = "Use English for replies and explanations. Preserve requested JSON formats and literal text.\n" + prompt
        if len(prompt) > 4000:
            return "Friday returned no answer: the request is too long. Please shorten it."
        if not self.api_key:
            friday_result = "Set FRIDAY_API_KEY in your environment to use the Friday AI backend."
        else:
            friday_result = self._ask_friday(prompt)

        if not is_ai_error(friday_result):
            return friday_result
        if config.GROQ_ENABLED and config.GROQ_API_KEY:
            groq_result = GroqService().ask(prompt)
            if not is_ai_error(groq_result):
                return groq_result
            return f"{friday_result} Groq fallback also failed: {groq_result}"
        return friday_result

    def _ask_friday(self, prompt: str) -> str:
        """Call Friday and return a user-visible error instead of raising."""
        try:
            response = requests.post(
                f"{self.endpoint}/chat",
                json={"message": prompt},
                headers={
                    "x-api-key": self.api_key,
                    "ngrok-skip-browser-warning": "true",
                },
                timeout=(8, 90),
            )
            if response.status_code == 401:
                return "Friday API key was rejected. Check FRIDAY_API_KEY."
            response.raise_for_status()
            data = response.json()
            reply = data.get("response")
            if not isinstance(reply, str) or not reply.strip():
                return "Friday returned an empty or invalid response."
            return reply.strip()
        except requests.RequestException as exc:
            return f"Friday is unavailable: {exc}"
        except ValueError:
            return "Friday returned invalid JSON. Check the Colab server and ngrok URL."
