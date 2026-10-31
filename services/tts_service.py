"""Text to speech; initialize the engine in the worker that uses it."""


def speak(text):
    import pyttsx3

    try:
        import pythoncom
    except ImportError:
        pythoncom = None
    if pythoncom:
        pythoncom.CoInitialize()
    try:
        engine = pyttsx3.init()
        engine.setProperty("rate", 170)
        engine.say(text)
        engine.runAndWait()
        engine.stop()
    finally:
        if pythoncom:
            pythoncom.CoUninitialize()
