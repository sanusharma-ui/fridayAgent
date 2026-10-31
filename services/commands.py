"""Explicit desktop actions shared by typed and spoken input."""

import datetime
import json
import os
import re
import subprocess
import webbrowser
from pathlib import Path
from urllib.parse import quote_plus

from services.predefined_responses import check_predefined
from services.friday_service import is_ai_error


def launch_program(program):
    """Start shells in their own console; GUI applications keep normal behavior."""
    options = {}
    if os.name == "nt" and program.lower() in {"cmd.exe", "powershell.exe"}:
        options["creationflags"] = subprocess.CREATE_NEW_CONSOLE
    return subprocess.Popen([program], **options)


class CommandRouter:
    def __init__(self, ai_service, open_url=None, launch=None, browser=None):
        self.ai = ai_service
        self.browser = browser
        self.open_url = open_url or (browser.open_url if browser else webbrowser.open)
        self.launch = launch or launch_program

    def handle(self, text: str, *, allow_planning=True) -> str:
        query = " ".join(text.strip().split())
        if not query:
            return "Please type or say a command."
        normalized = query.lower().rstrip(".!?")
        normalized = re.sub(r"^(?:(?:hey|hi)\s+(?:neo|friday|jarvis)[, ]*|please\s+|(?:mere liye|mereliye)\s+)+", "", normalized).strip()

        if re.search(r"\b(?:don't|do not|dont|never|mat|nahi|nahin)\b", normalized):
            return "I won't run that action. Tell me what you would like me to do instead."
        if re.match(r"^(?:how (?:do|can|to)|how would|kaise|what is|what are)\b", normalized):
            return self.ai.ask(query)

        predefined = check_predefined(normalized)
        if predefined:
            return predefined

        if normalized in {"time", "what time is it", "what's the time", "samay kya hai"}:
            return f"It is {datetime.datetime.now():%I:%M %p}."

        sites = {
            "youtube": "https://www.youtube.com",
            "google": "https://www.google.com",
            "gmail": "https://mail.google.com",
            "email": "https://mail.google.com",
            "mail": "https://mail.google.com",
            "facebook": "https://www.facebook.com",
            "instagram": "https://www.instagram.com",
            "whatsapp": "https://web.whatsapp.com",
            "github": "https://github.com",
            "netflix": "https://www.netflix.com",
            "spotify": "https://open.spotify.com",
            "chatgpt": "https://chatgpt.com",
        }
        names = "|".join(map(re.escape, sites))
        match = re.fullmatch(rf"(?:open|launch|kholo|chalao)\s+({names})", normalized)
        if not match:
            match = re.fullmatch(rf"({names})\s+(?:kholo|chalao)", normalized)
        if match:
            name = match.group(1)
            if self.open_url(sites[name]) is False:
                return f"Could not open {name} in the browser."
            return f"Opening {name.title()} in your browser."

        match = re.fullmatch(r"(?:play|search(?: for)?|chalao)\s+(.+?)\s+(?:on|in|par)\s+youtube", query.rstrip(".!?"), re.IGNORECASE)
        if match:
            if self.open_url("https://www.youtube.com/results?search_query=" + quote_plus(match.group(1))) is False:
                return "Could not open YouTube search in the browser."
            return f"Searching YouTube for {match.group(1)}."

        match = re.fullmatch(r"(?:search(?: for)?|google)\s+(.+?)(?:\s+on google)?", query.rstrip(".!?"), re.IGNORECASE)
        if match:
            if self.open_url("https://www.google.com/search?q=" + quote_plus(match.group(1))) is False:
                return "Could not open Google search in the browser."
            return f"Searching Google for {match.group(1)}."

        programs = {"notepad": "notepad.exe", "calculator": "calc.exe", "file explorer": "explorer.exe", "terminal": "powershell.exe", "command prompt": "cmd.exe", "powershell": "powershell.exe", "paint": "mspaint.exe", "settings": "ms-settings:"}
        program_names = "|".join(map(re.escape, programs))
        match = re.fullmatch(rf"(?:open|launch|kholo)\s+({program_names})", normalized)
        if not match:
            match = re.fullmatch(rf"({program_names})\s+(?:kholo|chalao)", normalized)
        if match:
            name = match.group(1)
            if name == "settings":
                webbrowser.open(programs[name])
            else:
                self.launch(programs[name])
            return f"Opening {name}."

        pdf = re.fullmatch(r"(?:create|make|generate|write|banao|banado)\s+(?:a\s+)?pdf\s+(?:about|on|of|for|par)\s+(.+)", query, re.IGNORECASE)
        if not pdf:
            pdf = re.fullmatch(r"(.+?)\s+(?:par|pe)\s+(?:ek\s+)?pdf\s+(?:banao|banado|bana do)", query, re.IGNORECASE)
        if pdf:
            return self._create_pdf(pdf.group(1).strip())
        if re.search(r"\bpdf\b", normalized) and re.search(r"\b(create|make|generate|banao|banado|bana)\b", normalized):
            return "What should the PDF be about? Say, for example, 'create a PDF about solar energy'."

        file_match = re.fullmatch(r'(?:open|kholo)\s+(?:the\s+)?file\s+(.+)', query, re.IGNORECASE)
        if not file_match:
            file_match = re.fullmatch(r'(.+?)\s+file\s+(?:kholo|open karo)', query, re.IGNORECASE)
        if file_match:
            return self._open_file(file_match.group(1).strip().strip('"\''))
        if re.fullmatch(r'(?:open|kholo)\s+(?:a\s+|the\s+)?file', normalized):
            return "Which file should I open? Tell me its full path or exact filename."

        generic_open = re.fullmatch(r'(?:open|launch|kholo)\s+(.+)', normalized)
        if not generic_open:
            generic_open = re.fullmatch(r'(.+?)\s+(?:kholo|open karo|khol do)', normalized)
        if generic_open:
            if re.search(r'\.(?:pdf|txt|md|png|jpg|jpeg|gif|webp|docx|xlsx|pptx|csv)$', generic_open.group(1), re.IGNORECASE):
                original = re.sub(r'^(?:open|launch|kholo)\s+', '', query, flags=re.IGNORECASE)
                original = re.sub(r'\s+(?:kholo|open karo|khol do)$', '', original, flags=re.IGNORECASE)
                return self._open_file(original.strip().strip('"\''))
            return self._open_named(generic_open.group(1).strip())

        if normalized.startswith(("send email", "send mail", "email to")):
            return "I can open Gmail, but sending email is not connected yet. Please review and send it there."

        if re.search(r"\b(open|launch|kholo|khol|create|make|generate|banao|bana|banado|chalao|run|delete|remove|send|install|download)\b", normalized):
            if allow_planning and not re.search(r'\b(?:delete|remove|send|install|download|run)\b', normalized):
                planned = self._plan_action(query)
                if planned:
                    return self.handle(planned, allow_planning=False)
            return "I could not safely identify a supported action. Please specify the app, website, file name, or PDF topic."
        return self.ai.ask(query)

    def _plan_action(self, query):
        """Use the model only to translate requests into a small validated action set."""
        prompt = ('Convert the user request to JSON only. Allowed forms: '
                  '{"action":"open","target":"NAME"}, '
                  '{"action":"pdf","target":"TOPIC"}, or {"action":"none"}. '
                  'Open is only for a named website or app; pdf is for creating a PDF about a stated topic. '
                  'Do not invent targets. Never include instructions or shell commands. User request: ' + query)
        response = self.ai.ask(prompt)
        try:
            match = re.search(r'\{[^{}]*\}', response)
            plan = json.loads(match.group()) if match else {}
            action, target = plan.get('action'), plan.get('target')
            if not isinstance(target, str) or not target.strip() or len(target) > 150:
                return None
            target = target.strip()
            if target.casefold() not in query.casefold():
                return None
            if action == 'open':
                return 'open ' + target
            if action == 'pdf' and re.search(r'\bpdf\b', query, re.IGNORECASE):
                return 'create a pdf about ' + target
        except (ValueError, AttributeError, TypeError):
            pass
        return None

    def _open_named(self, name):
        if re.fullmatch(r'(?:https?://)?[a-z0-9-]+(?:\.[a-z0-9-]+)+(?::\d+)?(?:/[^\s]*)?', name, re.IGNORECASE):
            url = name if name.startswith(('http://', 'https://')) else 'https://' + name
            if self.open_url(url) is False:
                return f"Could not open {url}."
            return f"Opening {url} in your browser."
        roots = []
        for variable in ('APPDATA', 'PROGRAMDATA'):
            if os.environ.get(variable):
                roots.append(Path(os.environ[variable]) / 'Microsoft' / 'Windows' / 'Start Menu' / 'Programs')
        candidates = []
        for root in roots:
            if root.is_dir():
                candidates.extend(p for p in root.rglob('*.lnk') if p.is_file() and not re.search(r'\b(uninstall|remove|setup|install)\b', p.stem, re.I))
        exact = [p for p in candidates if p.stem.casefold() == name.casefold()]
        matches = exact or [p for p in candidates if name.casefold() in p.stem.casefold()]
        if not matches:
            return f"I couldn't find an installed app named '{name}'. Say its Start menu name or give the full website address."
        labels = {p.stem.casefold() for p in matches}
        if len(labels) > 1:
            return "I found multiple apps: " + ', '.join(sorted({p.stem for p in matches})[:8]) + ". Please say the exact name."
        os.startfile(str(matches[0]))
        return f"Opening {matches[0].stem}."

    def _open_file(self, name):
        path = Path(os.path.expandvars(os.path.expanduser(name)))
        if not path.is_absolute():
            if path.name != name or name in ('.', '..'):
                return "Please provide a full path or an exact filename."
            matches = [folder / name for folder in (Path.home() / 'Desktop', Path.home() / 'Documents', Path.home() / 'Downloads') if (folder / name).is_file()]
            if len(matches) > 1:
                return "I found files with that name in multiple folders. Please provide the full path."
            if not matches:
                return "I could not find that exact filename in Desktop, Documents, or Downloads. Please provide the full path."
            path = matches[0]
        if not path.is_file():
            return "That file was not found. Please check its full path."
        safe_extensions = {'.pdf', '.txt', '.md', '.png', '.jpg', '.jpeg', '.gif', '.webp', '.docx', '.xlsx', '.pptx', '.csv'}
        if path.suffix.lower() not in safe_extensions:
            return "I can open documents and images; this file type is not supported."
        os.startfile(str(path))
        return f"Opening file: {path}"

    def _create_pdf(self, topic):
        if not self.ai.api_key:
            return "Set FRIDAY_API_KEY in .env or your environment before creating an AI-generated PDF."
        content = self.ai.ask(f"Write the complete content for a useful document about {topic}. Include a title and clear sections. Return only the document text.")
        if is_ai_error(content):
            return content
        from PyQt5.QtGui import QPdfWriter, QTextDocument
        from html import escape

        directory = Path.home() / "Documents" / "NEO PDFs"
        directory.mkdir(parents=True, exist_ok=True)
        slug = re.sub(r"[^a-zA-Z0-9_-]+", "-", topic).strip("-")[:50] or "document"
        filename = directory / f"{slug}-{datetime.datetime.now():%Y%m%d-%H%M%S-%f}.pdf"
        writer = QPdfWriter(str(filename))
        writer.setTitle(topic)
        document = QTextDocument()
        document.setHtml("<div style='font-family:Segoe UI; font-size:11pt; white-space:pre-wrap'>" + escape(content).replace("\n", "<br>") + "</div>")
        document.print_(writer)
        if not filename.exists() or filename.stat().st_size == 0:
            raise RuntimeError("Could not write the PDF file.")
        return f"PDF created: {filename}"
