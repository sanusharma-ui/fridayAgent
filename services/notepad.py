"""Create a new text document and open it in Notepad."""

from datetime import datetime
from pathlib import Path
import re
import subprocess
from uuid import uuid4


class NotepadWriter:
    def __init__(self, ai, directory=None, launch=None):
        self.ai = ai
        self.directory = Path(directory) if directory is not None else Path.home() / "Documents" / "NEO Notes"
        self.launch = launch or (lambda path: subprocess.Popen(["notepad.exe", str(path)]))

    def write(self, request):
        # Verbatim mode only applies to content explicitly following the marker.
        verbatim = re.search(r"\b(?:write|type)\s+(?:exactly|verbatim)\s*[:\-]?\s+(.+)", request, re.I | re.S)
        if verbatim:
            content = verbatim.group(1).strip()
        else:
            prompt = (
                "Write the actual finished text requested below for a Notepad document. "
                "Follow the topic, length, language and style requested. "
                "Return only the document text, not instructions, a description of what you would do, "
                "or the user's request repeated.\n\nRequest: " + request
            )
            content = self.ai.ask(prompt)
            if content.startswith(("Friday is unavailable:", "Friday API key was rejected.",
                                   "Friday returned", "Set FRIDAY_API_KEY")):
                return content
            if not content.strip() or content.strip().casefold() == request.strip().casefold():
                return "Friday did not generate the requested document. Please try again."

        if not content.strip():
            return "Please tell me what to write."
        self.directory.mkdir(parents=True, exist_ok=True)
        path = self.directory / f"note-{datetime.now():%Y%m%d-%H%M%S}-{uuid4().hex[:8]}.txt"
        with path.open("x", encoding="utf-8-sig", newline="") as document:
            document.write(content)
        try:
            self.launch(path)
        except OSError as exc:
            return f"Text saved to {path}, but Notepad could not be opened: {exc}"
        return f"Created a new document and opened it in Notepad: {path}"
