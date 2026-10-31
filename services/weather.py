import requests

import config


class WeatherService:
    def __init__(self, api_key: str):
        self.api_key = api_key

    def get_weather_report(self, city: str) -> str:
        key = self.api_key or config.OPENWEATHER_API_KEY
        if not key:
            return "Set OPENWEATHER_API_KEY to enable weather."
        try:
            response = requests.get(
                "https://api.openweathermap.org/data/2.5/weather",
                params={"q": city, "appid": key, "units": "metric"},
                timeout=8,
            )
            response.raise_for_status()
            data = response.json()
            description = data["weather"][0]["description"].capitalize()
            temp = data["main"]["temp"]
            feels = data["main"].get("feels_like")
            humidity = data["main"].get("humidity")
            return f"{city}: {description}, {temp}°C (feels {feels}°C), humidity {humidity}%."
        except (requests.RequestException, ValueError, KeyError, IndexError) as exc:
            return f"Weather unavailable: {exc}"
