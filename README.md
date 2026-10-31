# NEO desktop assistant

PyQt5 desktop assistant with typed commands, push-to-talk voice input, local desktop actions, and answers from the Friday Colab backend.

## Setup (Windows PowerShell)

```powershell
python -m pip install -r requirements.txt
Copy-Item .env.example .env # if you do not already have a .env file
# Edit .env: use the Colab secret and the current ngrok URL.
python app.py
```

The key must equal the `FRIDAY_API_KEY` stored in Colab Secrets. The app loads `.env` beside `config.py`; environment variables take precedence. The app sends `POST /chat` with `{"message": "..."}` and the `x-api-key` header, then reads the `response` field. Keep the Colab runtime and ngrok tunnel active. If the tunnel URL changes, update `AI_ENDPOINT_URL`. Never share or commit `.env` or real keys.

Voice input uses the bundled English Vosk model and records for six seconds after **Listen** is pressed. It works offline, though English recognition can struggle with Hindi or Hinglish. Type those commands when recognition fails. **Speak replies** is optional. Microphone permission and a working input device are required.

**Agent** handles typed and spoken requests. The Friday model plans supported tool calls as JSON, and the desktop app validates the tool and its arguments before running it locally. It can open apps, websites and supported files, search the web or YouTube, and create a PDF. General questions go to Friday. The Colab backend is a text generator rather than a native tool-calling API; model output may need rephrasing if it produces an invalid plan. Simple open requests also work without the backend. AI-generated text is never run as shell code. Other requests require the API key and a reachable backend described above.

Try `open facebook`, `open terminal`, `open file report.pdf`, `play lo-fi on youtube`, or `create a PDF about solar energy`. For files, provide a full path or an exact filename directly inside Desktop, Documents, or Downloads. Only supported document and image formats can be opened. PDF creation asks Friday to write the document and saves a new file in `Documents/NEO PDFs`; check the generated content. Opening Gmail does not send mail. Arbitrary application control, sending messages, file deletion, and running arbitrary shell commands are not wired up. There is no always-on wake word: press Listen for each six-second recording.

You can also open installed Windows apps by their Start menu name, or say `open example.com` for a website. If multiple app names match, specify the exact name. Apps without a Start menu shortcut may not be found.

`Open terminal` opens PowerShell in a separate console window; `open command prompt` opens a separate Command Prompt window. Opening a terminal does not run commands inside it.

Say `write an essay about moons` or `write a short poem about rain in Notepad`: Friday generates the requested content, saves a new UTF-8 text file in `Documents/NEO Notes`, and opens it in a new Notepad document. It does not type into or change an already-open document. For literal text, say `write exactly Hello from NEO`; the words following `exactly` are saved as given. Generated content requires the Friday backend and should be reviewed.

For weather, set `OPENWEATHER_API_KEY` in the environment. The key formerly present in source should be rotated before reuse.

## Pro UI & Keyboard Shortcuts

- `Return` / `Ctrl+Return`: Send typed command
- `Ctrl+Space` or `F2`: Push-to-talk voice input (6s offline recording)
- `Ctrl+N`: New chat session (resets stream & reveals starter prompt cards)
- `Ctrl+L`: Instantly focus command input
- `Ctrl+Shift+C`: Copy latest AI response to clipboard
- `Ctrl+M`: Toggle spoken voice replies (TTS)
- `F5`: Refresh weather forecast
- `Ctrl+,`: Open Settings & Diagnostics dialog (test Friday endpoint, update API keys, configure default city)
- `Esc`: Clear input line or reset view

