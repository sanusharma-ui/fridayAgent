"""Client for the optional Groq chat-completions fallback."""

import requests

import config


class GroqService:
    def __init__(self, api_key=None, model=None, endpoint=None):
        self.api_key = api_key if api_key is not None else config.GROQ_API_KEY
        self.model = model or config.GROQ_MODEL
        self.endpoint = (endpoint or config.GROQ_API_URL).rstrip("/")

    def ask(self, prompt: str) -> str:
        if not self.api_key:
            return "Groq API key is not configured. Set GROQ_API_KEY."
        try:
            response = requests.post(
                self.endpoint,
                json={
                    "model": self.model,
                    "messages": [{"role": "user", "content": prompt}],
                    "temperature": 0.2,
                },
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
                timeout=(8, 90),
            )
            if response.status_code in {401, 403}:
                return "Groq API key was rejected. Check GROQ_API_KEY."
            response.raise_for_status()
            data = response.json()
            choices = data.get("choices")
            reply = choices[0].get("message", {}).get("content") if choices else None
            if not isinstance(reply, str) or not reply.strip():
                return "Groq returned an empty or invalid response."
            return reply.strip()
        except requests.RequestException as exc:
            return f"Groq is unavailable: {exc}"
        except (ValueError, IndexError, AttributeError, TypeError):
            return "Groq returned invalid JSON. Check the Groq API response."
