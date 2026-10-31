import pyttsx3
import speech_recognition as sr

class SpeechService:
    def __init__(self, voice_rate: int = 175, voice_id: int = 0):
        # TTS
        self.engine = pyttsx3.init()
        self.engine.setProperty("rate", voice_rate)
        voices = self.engine.getProperty("voices")
        if voices and 0 <= voice_id < len(voices):
            self.engine.setProperty("voice", voices[voice_id].id)

        # STT
        self.recognizer = sr.Recognizer()
        self.recognizer.dynamic_energy_threshold = True
        self.recognizer.pause_threshold = 0.8

    def say(self, text: str):
        self.engine.say(text)
        self.engine.runAndWait()

    def listen_once(self) -> str:
        with sr.Microphone() as source:
            self.recognizer.adjust_for_ambient_noise(source, duration=0.6)
            audio = self.recognizer.listen(source, timeout=6, phrase_time_limit=8)
        try:
            text = self.recognizer.recognize_google(audio, language="en-IN")
            return text.strip()
        except sr.UnknownValueError:
            return ""
        except sr.RequestError as e:
            raise RuntimeError(f"Speech recognition error: {e}")

    def shutdown(self):
        try:
            self.engine.stop()
        except Exception:
            pass
