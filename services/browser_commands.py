"""English browser commands shared by local and Telegram requests."""

import re


def parse_fill_request(request):
    """Extract a user-provided value locally, without sending it to the AI."""
    text = request.strip().rstrip(".!?")
    patterns = (
        r"(?:type|enter|fill|put|write)\s+(.+?)\s+(?:in|into|on)\s+(?:the\s+)?(.+)",
        r"(?:the\s+)?(.+?)\s+field\s+(?:me|mein|par)\s+(.+?)\s+(?:daalo|dalo|bhar do|bharna)",
    )
    for pattern in patterns:
        match = re.fullmatch(pattern, text, re.I)
        if match:
            if "field" in pattern:
                target, value = match.group(1), match.group(2)
            else:
                value, target = match.group(1), match.group(2)
            value = value.strip().strip("\"'")
            target = target.strip()
            if value and target:
                return value, target
    return None


CONTROL_PHRASES = {
    "scroll up": "scroll_up", "scroll down": "scroll_down",
    "page up": "scroll_up", "page down": "scroll_down",
    "scroll to the top": "top", "scroll to top": "top", "go to the top": "top",
    "scroll to the bottom": "bottom", "scroll to bottom": "bottom", "go to the bottom": "bottom",
    "back": "back", "go back": "back", "back to the previous page": "back",
    "forward": "forward", "go forward": "forward",
    "refresh": "refresh", "refresh page": "refresh", "refresh the page": "refresh", "reload": "refresh",
    "new tab": "new_tab", "open a new tab": "new_tab", "open new tab": "new_tab",
    "open chrome": "new_tab", "open google chrome": "new_tab", "open browser": "new_tab",
    "list tabs": "tabs", "show tabs": "tabs", "show my tabs": "tabs",
    "close tab": "close_tab", "close this tab": "close_tab", "close the current tab": "close_tab",
    "play video": "play", "play the video": "play", "resume video": "play",
    "play": "play", "play karo": "play", "resume": "play", "pause": "pause",
    "pause video": "pause", "pause the video": "pause",
}


def parse_browser_request(request):
    # Anchored matches do not turn questions, negatives or quoted text into actions.
    text = request.strip().rstrip(".!?")
    text = re.sub(r"^(?:(?:please|can you|could you|would you)\s+)+", "", text, flags=re.I)
    text = re.sub(r"\s+(?:please|for me)$", "", text, flags=re.I)
    normalized = " ".join(text.lower().split())
    if normalized in CONTROL_PHRASES:
        return "browser_control", CONTROL_PHRASES[normalized]
    match = re.fullmatch(r"play (?:the )?(?:(?:video|result) )?(\d+|one|two|three|four|five|first|second|third)(?: (?:video|result))?", normalized)
    if match:
        value = match.group(1)
        numbers = {"one": 1, "first": 1, "two": 2, "second": 2, "three": 3, "third": 3, "four": 4, "five": 5}
        return "browser_play_result", str(numbers.get(value, value))
    match = re.fullmatch(r"(?:switch to|go to|select|switch) tab (\d+)", normalized)
    if match:
        return "browser_tab", match.group(1)
    match = re.fullmatch(r"(?:open|click|play) (?:the )?(?:search )?(?:result|link) (\d+)", normalized)
    if match:
        return ("browser_play_result" if normalized.startswith("play ") else "browser_result"), match.group(1)
    match = re.fullmatch(
        r"(?:open|click|play) (?:the )?(first|second|third) (?:search )?(?:result|link)",
        normalized,
    )
    if match:
        return ("browser_play_result" if normalized.startswith("play ") else "browser_result"), str({"first": 1, "second": 2, "third": 3}[match.group(1)])
    match = re.fullmatch(r"click (?:the )?(\d+)(?:st|nd|rd|th)?(?: (?:search )?(?:result|link))?", normalized)
    if match:
        return "browser_result", match.group(1)
    match = re.fullmatch(r"search(?: for)? (.+)", text, re.I)
    if match:
        query = match.group(1).strip()
        explicit = re.fullmatch(r"(.+?)\s+(?:on|in)\s+(youtube|google)", query, re.I)
        if explicit:
            return ("search_youtube" if explicit.group(2).lower() == "youtube" else "search_web"), explicit.group(1)
        if not re.search(r"\s+(?:on|in)\s+(?:youtube|google|bing|duckduckgo)$", query, re.I):
            return "browser_search", query
    return None


def control_is_grounded(action, request):
    """Validate model-selected enum actions against the user's direction/intent."""
    patterns = {
        "scroll_up": r"\b(?:up|upwards|upward)\b",
        "scroll_down": r"\b(?:down|downwards|downward)\b",
        "top": r"\btop\b", "bottom": r"\bbottom\b",
        "back": r"\b(?:back|previous)\b", "forward": r"\b(?:forward|next)\b",
        "refresh": r"\b(?:refresh|reload)\b",
        "new_tab": r"\bnew\s+(?:browser\s+)?tab\b",
        "tabs": r"\b(?:list|show)\b.*\btabs\b",
        "close_tab": r"\bclose\b.*\btab\b",
        "play": r"\b(?:play|resume)\b.*\bvideo\b",
        "pause": r"\bpause\b.*\bvideo\b",
    }
    return action in patterns and bool(re.search(patterns[action], request, re.I))
