"""Client for the Friday Colab backend exposed through ngrok."""

import requests

import config


class FridayService:
    def __init__(self, endpoint=None, api_key=None):
        self.endpoint = (endpoint or config.AI_ENDPOINT_URL).rstrip("/")
        self.api_key = api_key if api_key is not None else config.FRIDAY_API_KEY

    def ask(self, prompt: str) -> str:
        if not self.api_key:
            return "Set FRIDAY_API_KEY in your environment to use the Friday AI backend."
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
