predefined_responses = {
    "hello": "Hello! How can I help?",
    "hi": "Hi! What would you like to do?",
    "who are you": "I am NEO, your desktop assistant.",
    "what's your name": "My name is NEO.",
    "what can you do": (
        "I can open Gmail, YouTube and Google, search the web or YouTube, "
        "open Notepad, Calculator and File Explorer, and answer questions through Friday AI."
    ),
    "what you can do": (
        "I can open Gmail, YouTube and Google, search the web or YouTube, "
        "open Notepad, Calculator and File Explorer, and answer questions through Friday AI."
    ),
}

system_commands = {
    "atomic number of calcium": "20",
    "atomic number of hydrogen": "1",
    "atomic number of oxygen": "8",
    "atomic number of carbon": "6",
}


def check_predefined(query: str):
    query = query.lower().strip()
    if query in predefined_responses:
        return predefined_responses[query]
    if query in system_commands:
        return f"The {query} is {system_commands[query]}."
    return None
