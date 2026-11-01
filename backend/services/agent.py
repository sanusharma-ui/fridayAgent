"""Translate natural language into validated local tool calls.

The Colab backend exposes text generation, not native function calling, so the
planner uses a small JSON protocol. Model output is untrusted data, never code.
"""

import json
import re
import time
from backend.services.notepad import NotepadWriter
from backend.services.commands import parse_file_creation_request
from backend.services.browser import BrowserError
from backend.services.browser_commands import parse_browser_request, parse_fill_request, parse_click_target, control_is_grounded
from backend.services.friday_service import is_ai_error
from backend.services.gmail_commands import GmailCommands
from backend.services.intent_planner import PLAN_RULES, verify_semantic_plan


class DesktopAgent:
    MAX_CALLS = 3

    def __init__(self, ai, router, notepad=None):
        self.ai = ai
        self.router = router
        self.notepad = notepad or NotepadWriter(ai)
        self.browser = getattr(router, "browser", None)
        self.gmail = getattr(router, "gmail", None) or GmailCommands(ai)
        self.mail_sessions = {}
        self.clarifications = {}

    def handle(self, text, mail_context="desktop"):
        try:
            return self._handle(text, mail_context)
        except BrowserError as exc:
            return f"Browser: {exc}"

    def _handle(self, text, mail_context="desktop"):
        request = text.strip()
        if not request:
            return "Please type or say what you need."

        mail = self.gmail
        if mail_context != "desktop":
            if mail_context not in self.mail_sessions:
                if len(self.mail_sessions) >= 64:
                    self.mail_sessions.pop(next(iter(self.mail_sessions)))
                self.mail_sessions[mail_context] = GmailCommands(self.ai)
            mail = self.mail_sessions[mail_context]
        # Form values stay local and must never enter the mail interpretation prompt.
        fill_request = parse_fill_request(request) if self.browser else None
        open_mail_site = re.fullmatch(r"(?:(?:please|can you)\s+)?(?:open|launch)\s+(?:gmail|email|mail)[.!?]?", request, re.I)
        mail_result = None if fill_request or open_mail_site else mail.handle(request)
        if mail_result is not None:
            self.clarifications.pop(mail_context, None)
            return mail_result

        previous = self.clarifications.pop(mail_context, None)
        has_context = bool(previous and previous["expires"] > time.monotonic() and not fill_request)
        if has_context:
            request = ("Previous user request: " + previous["request"] + "\nAssistant question: "
                       + previous["question"] + "\nLatest user message: " + request)

        browser_request = parse_browser_request(request) if self.browser else None
        if browser_request:
            return self._execute(*browser_request, request)

        fill_request = parse_fill_request(request) if self.browser else None
        click_target = parse_click_target(request) if self.browser else None
        if click_target:
            return self.browser.click_matching(click_target)

        if parse_file_creation_request(request):
            return self.router.handle(request, allow_planning=False)

        # Common writing requests use the complete instruction to generate the
        # document, rather than treating the topic as the document itself.
        if (not fill_request and re.match(r"\s*(?:(?:please|can you|could you|would you)\s+)*(?:write|draft|compose|type)\s+", request, re.I)
                and not re.search(r"\b(?:don't|dont|do not|never|mat|nahi|nahin|pdf|email|mail|send|delete|remove)\b", request, re.I)
                and not re.match(r"\s*(?:write|type)\s+(?:exactly|verbatim)\s*[:\-]?\s*$", request, re.I)):
            return self.notepad.write(request)

        # Common direct requests remain usable even when Colab is offline.
        simple = re.fullmatch(
            r"\s*(?:(?:hey|hi)\s+(?:neo|friday|jarvis)[, ]+)?"
            r"(?:(?:please|can you|could you|would you|will you)\s+)*"
            r"(open|launch)\s+([\w.-]+)(?:\s+(?:for me|please))?[.!?]*\s*",
            request, re.IGNORECASE,
        )
        if simple:
            return self.router.handle("open " + simple.group(2))

        # Short spoken Hinglish requests do not need an online model.
        spoken_open = re.fullmatch(
            r"\s*(?:please\s+|(?:mere liye|mere liye ek)\s+)?"
            r"([\w.-]+(?:\s+[\w.-]+){0,2})\s+"
            r"(?:kholo|khol do|open karo|chalao)[.!?]*\s*",
            request, re.IGNORECASE,
        )
        if spoken_open:
            return self.router.handle("open " + spoken_open.group(1))

        prompt = PLAN_RULES + "User request: " + json.dumps(request, ensure_ascii=False)
        page_context = ""
        if self.browser:
            try:
                context_result = self.browser.page_context()
                if isinstance(context_result, str):
                    page_context = context_result
                else:
                    page_context = "(CURRENT PAGE CONTEXT unavailable; do not select browser_click.)"
            except BrowserError:
                page_context = "(CURRENT PAGE CONTEXT unavailable; do not select browser_click.)"
        ai_request = request
        if fill_request:
            value, target = fill_request
            ai_request = f"Fill the field matching {target!r} with the user-provided value [VALUE REDACTED LOCALLY]."
        prompt = prompt.replace(json.dumps(request, ensure_ascii=False), json.dumps(ai_request, ensure_ascii=False))
        # Leave room for FridayService's language prefix and this context label.
        # The backend limit applies to the complete serialized prompt, not just
        # the user's short command.
        context_budget = max(0, 3300 - len(prompt))
        page_context = page_context[:context_budget]
        prompt += "\n\nCURRENT PAGE CONTEXT (fresh for this request; never use an old context):\n" + page_context
        if len(prompt) > 3800:
            return "Please shorten the request so I can interpret it reliably."
        response = self.ai.ask(prompt)
        if is_ai_error(response):
            return response
        plan = self._parse_plan(response)
        if not plan:
            return "I couldn't understand the action reliably. Please try again or describe it more specifically."
        kind = plan.get("type")
        if kind == "mail":
            return mail._semantic(request)
        if kind == "chat":
            if fill_request:
                return "I couldn't identify a safe form field for that value. Please specify the field more clearly."
            return self.ai.ask(request)
        if kind == "clarify":
            message = plan.get("message")
            question = message.strip()[:400] if isinstance(message, str) and message.strip() else "Please provide more details."
            if not fill_request and len(request) <= 1400:
                if len(self.clarifications) >= 64:
                    self.clarifications.pop(next(iter(self.clarifications)))
                self.clarifications[mail_context] = dict(request=request, question=question, expires=time.monotonic() + 300)
            return question
        if kind != "tools":
            return "I couldn't identify a supported action. Please rephrase your request."

        calls = plan.get("calls")
        if not isinstance(calls, list) or not 1 <= len(calls) <= self.MAX_CALLS:
            return "I couldn't create a valid action plan. Please rephrase your request."
        # Validate the complete plan before performing any action.
        validated = []
        needs_semantic_check = has_context
        for call in calls:
            if not isinstance(call, dict):
                return "I couldn't create a valid action plan. Please rephrase your request."
            tool, argument = call.get("tool"), call.get("argument")
            allowed_tools = {"open", "open_file", "search_web", "search_youtube", "create_pdf", "create_file", "write_notepad",
                             "browser_search", "browser_control", "browser_tab", "browser_result", "browser_click",
                             "browser_fill"}
            if (not isinstance(tool, str) or tool not in allowed_tools
                    or not isinstance(argument, str) or not argument.strip()
                    or len(argument) > 300):
                return "I couldn't verify the requested action or its details. Please be more specific."
            argument = argument.strip()
            if tool.startswith("browser_") and not self.browser:
                return "Browser controls are not connected. Restart the desktop app."
            if tool == "browser_click":
                if not re.search(rf"^\[{re.escape(argument)}\]", page_context, re.M):
                    return "I couldn't verify that control on the current page. Please describe the visible control."
                grounded = (
                    bool(re.search(r"\bclick\b", request, re.I))
                    and bool(re.search(rf"\[{re.escape(argument)}\]", page_context))
                )
            elif tool == "browser_fill":
                grounded = (
                    bool(fill_request)
                    and bool(re.search(rf"\[{re.escape(argument)}\]", page_context))
                )
                if not grounded:
                    return "Please specify the field and its value clearly."
            elif tool == "browser_control":
                if argument not in {"scroll_up", "scroll_down", "top", "bottom", "back", "forward", "refresh", "new_tab", "tabs", "close_tab", "play", "pause"}:
                    return "I couldn't verify the requested browser action."
                grounded = control_is_grounded(argument, request)
            elif tool in {"browser_tab", "browser_result"}:
                number = re.fullmatch(r"[1-9][0-9]?", argument)
                if not number:
                    return "Please choose a valid tab or result number."
                ordinal = {"1": "first", "2": "second", "3": "third"}.get(argument)
                noun = "tab" if tool == "browser_tab" else "result"
                grounded = bool(number and re.search(rf"\b{noun}\b", request, re.I) and (re.search(rf"\b{argument}\b", request)
                                             or (ordinal and re.search(rf"\b{ordinal}\b", request, re.I))))
            else:
                grounded = argument.casefold() in request.casefold()
            if not grounded:
                needs_semantic_check = True
            if tool == "create_pdf" and not re.search(r"\bpdf\b", request, re.I):
                needs_semantic_check = True
            if tool == "create_file" and not parse_file_creation_request(argument):
                return "Please provide a filename and content for the file."
            validated.append((tool, argument.strip()))

        if needs_semantic_check and not verify_semantic_plan(self.ai, ai_request, validated):
            return "I couldn't verify the intended action or its details. Could you clarify what you want me to do?"

        # A conservative guard prevents a planner mistake from executing a negated
        # or explicitly instructional request. Unsupported sensitive operations
        # are never delegated to a partial action plan.
        if re.search(r"\b(?:don't|dont|do not|never|mat|nahi|nahin)\b", request, re.I):
            return "I won't run an action from that request. Please tell me what you want me to do."
        if re.match(r"\s*(?:how (?:do|can|to)|how would|kaise|what is|what are|who is|explain)\b", request, re.I):
            return self.ai.ask(request)
        if re.search(r"\b(?:delete|remove|send|install|download|execute|run command)\b", request, re.I):
            return "That action is not connected yet, so I haven't run it."

        results = []
        for tool, argument in validated:
            try:
                if tool == "browser_fill":
                    if not fill_request:
                        return "Tell me what value to enter and which field to use."
                    value, _ = fill_request
                    field_line = re.search(
                        rf"^\[{re.escape(argument)}\][^\n]*$",
                        page_context,
                        re.I | re.M,
                    )
                    if field_line and re.search(
                        r"\b(?:type=(?:password|hidden)|password|passcode|otp|one[- ]time|cvv|card|credit|debit)\b",
                        field_line.group(0),
                        re.I,
                    ):
                        return "For safety, I won't automatically fill password, OTP, or card fields."
                    result = self.browser.fill_element(argument, value)
                else:
                    result = self._execute(tool, argument, request)
            except Exception as exc:
                results.append(f"Action failed: {exc}")
                break
            results.append(result)
            if result.startswith(("Could not", "I could", "I couldn't", "That file", "Please", "Set FRIDAY", "Friday ")):
                break
        return "\n".join(results)

    @staticmethod
    def _parse_plan(response):
        try:
            start = response.find("{")
            if start < 0:
                return None
            value, _ = json.JSONDecoder().raw_decode(response[start:])
            return value if isinstance(value, dict) else None
        except (ValueError, TypeError):
            return None

    def _execute(self, tool, argument, request):
        if tool.startswith("browser_"):
            if not self.browser:
                return "Browser controls are not connected. Restart the desktop app."
            if tool == "browser_search":
                return self.browser.search(argument)
            if tool == "browser_control":
                return self.browser.control(argument)
            if tool == "browser_tab":
                return self.browser.switch_tab(int(argument))
            if tool == "browser_result":
                return self.browser.open_result(int(argument))
            if tool == "browser_click":
                return self.browser.click_element(argument)
            if tool == "browser_play_result":
                return self.browser.play_result(int(argument))
        if tool == "open":
            return self.router.handle("open " + argument, allow_planning=False)
        if tool == "open_file":
            return self.router._open_file(argument.strip('"\''))
        if tool == "search_web":
            return self.router.handle("search " + argument, allow_planning=False)
        if tool == "search_youtube":
            return self.router.handle("search " + argument + " on youtube", allow_planning=False)
        if tool == "create_file":
            return self.router._create_file_from_request(argument)
        if tool == "write_notepad":
            return self.notepad.write(request)
        return self.router._create_pdf(argument)
