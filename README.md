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

Groq is an optional fallback when the Colab backend is unavailable. Set `GROQ_ENABLED=true` and provide `GROQ_API_KEY` in `.env`; leave `GROQ_ENABLED=false` to prevent all Groq requests. `GROQ_MODEL` defaults to `llama-3.3-70b-versatile`. Friday remains the primary backend whenever it responds successfully.

Voice input uses the bundled English Vosk model and records for six seconds after **Listen** is pressed. It works offline, though English recognition can struggle with Hindi or Hinglish. Type those commands when recognition fails. **Speak replies** is optional. Microphone permission and a working input device are required.

**Agent** handles typed and spoken requests. The Friday model plans supported tool calls as JSON, and the desktop app validates the tool and its arguments before running it locally. It can open apps, websites and supported files, search the web or YouTube, and create a PDF. General questions go to Friday. The Colab backend is a text generator rather than a native tool-calling API; model output may need rephrasing if it produces an invalid plan. Simple open requests also work without the backend. AI-generated text is never run as shell code. Other requests require the API key and a reachable backend described above.

Try `open facebook`, `open terminal`, `open file report.pdf`, `play lo-fi on youtube`, or `create a PDF about solar energy`. For files, provide a full path or an exact filename directly inside Desktop, Documents, or Downloads. Only supported document and image formats can be opened. PDF creation asks Friday to write the document and saves a new file in `Documents/NEO PDFs`; check the generated content. Opening Gmail does not send mail. Arbitrary application control, sending messages, file deletion, and running arbitrary shell commands are not wired up. There is no always-on wake word: press Listen for each six-second recording.

You can also open installed Windows apps by their Start menu name, or say `open example.com` for a website. If multiple app names match, specify the exact name. Apps without a Start menu shortcut may not be found.

`Open terminal` opens PowerShell in a separate console window; `open command prompt` opens a separate Command Prompt window. Opening a terminal does not run commands inside it.

Say `write an essay about moons` or `write a short poem about rain in Notepad`: Friday generates the requested content, saves a new UTF-8 text file in `Documents/NEO Notes`, and opens it in a new Notepad document. It does not type into or change an already-open document. For literal text, say `write exactly Hello from NEO`; the words following `exactly` are saved as given. Generated content requires the Friday backend and should be reviewed.

For weather, set `OPENWEATHER_API_KEY` in the environment. The key formerly present in source should be rotated before reuse.

## Chrome session controls

Install the updated `requirements.txt` and have Google Chrome installed. Website commands now use a visible Chrome session managed by the assistant. The interface, status messages, examples, and AI reply instructions use English.

Send these requests one at a time from the desktop or your authorized Telegram chat:

1. `Can you open YouTube for me?`
2. `Search for relaxing piano music`
3. `Open the first result`
4. `Pause the video`
5. `Go back`
6. `Scroll down`

For numbered YouTube playback, say `play 2`, `play two`, or `play the second video` while on search results. The assistant checks the controlled tab's current page, opens that numbered video result, and requests playback. On an open video, `play` resumes it and `pause` pauses it. On search results, plain `play` asks you to choose a number. Playback failures are reported rather than treated as success. Numbers refer to standard video results, excluding Shorts shelves and playlists.

Other controls: `scroll up`, `scroll to the top`, `scroll to the bottom`, `refresh`, `go forward`, `open a new tab`, `show tabs`, `switch to tab 2`, and `close this tab`. The sidebar also has Chrome shortcut buttons. Simple controls and searches work without Colab; more varied wording uses the AI planner.

Follow-up searches use the selected controlled tab's current website: YouTube, Google, Bing, or DuckDuckGo. Say `search for astronomy on Google` or `search for astronomy on YouTube` to change sites explicitly. Numbered result opening supports YouTube videos and Google results, up to the first 20 available links. Consent dialogs or changed website layouts can prevent result selection; close the dialog and retry. Scrolling targets the page, not nested panels.

The browser uses a separate temporary profile. Existing personal Chrome windows, logins, and tabs are not controlled. Use `show tabs` and `switch to tab N` to select the target; manually clicking a different tab does not change the assistant's selected tab. Desktop and Telegram share this session. Closing the app closes its controlled browser; a new app session starts without its previous logins. Arbitrary clicks, form submissions, purchases, and downloads are not implemented.

`BROWSER_CHANNEL=chrome` is the default in `.env.example`. You may use `msedge` with installed Microsoft Edge, or `chromium` after running `python -m playwright install chromium`. Restart the app after changing this setting. See the [Playwright browser documentation](https://playwright.dev/python/docs/browsers). If Playwright is missing, the app shows an installation message instead of reporting that the browser action succeeded.

## Control your laptop from Telegram

Telegram text and voice notes use the same agent and supported tools as the desktop window. Tasks run on the laptop, and the bot sends a text result to your phone. This is voice-note input, not a live call; generated PDFs and Notepad files remain on the laptop.

1. In Telegram, open the official [@BotFather](https://t.me/BotFather), use `/newbot`, and copy your new bot's token. Never send the token to other chats or commit it.
2. For voice notes, install the optional speech dependencies on the laptop:

   ```powershell
   python -m pip install -r requirements-telegram.txt
   python app.py
   ```

   Text requests work with the normal `requirements.txt` installation.
3. In the laptop app, open **Settings > Telegram**, paste the bot token, and save. Leave **Allowed user IDs** empty for initial pairing. Click **Connect Telegram** in the sidebar.
4. Open your own bot's private chat on your phone and send `/id` **after the laptop says connected/setup only**. Copy your numeric user ID into **Settings > Telegram > Allowed user IDs**, save, wait for disconnection, then click **Connect Telegram** again. An empty allowlist permits only `/id`; it never permits tasks. Add multiple trusted IDs separated by commas if needed.
5. Send `/start`, then try `can you open YouTube for me`, or record a Telegram voice note saying `write an essay about moons`. You will see the recognized text, a thinking message, and the tool result. The desktop conversation also shows remote requests.

Settings are stored in the local ignored `.env`; equivalent variables are listed in `.env.example`. You can optionally enable automatic Telegram connection on app startup. Changing Telegram settings requires disconnecting and reconnecting. A bot can only have one polling app/webhook active; use a dedicated bot for this laptop.

Voice notes support multilingual transcription with [faster-whisper](https://github.com/SYSTRAN/faster-whisper); its PyAV dependency decodes Telegram audio without a separate FFmpeg executable. The default `base` model runs on CPU and downloads to the user model cache on first use. That first request can take longer; later transcription is local. Use `TELEGRAM_VOICE_LANGUAGE=en` or `hi` if automatic language detection is unreliable. Hindi/Hinglish recognition and action interpretation can still make mistakes. Audio downloads are temporary and deleted after transcription. Voice notes are limited to 60 seconds and 10 MB; text/transcripts are limited to 1500 characters. Transcript text is sent to the configured Friday backend when AI planning or generation is needed.

Only allowed **numeric user IDs in private chats** can run tasks. Group, forwarded, edited and old messages are not executed. Pending messages from before connection are discarded to avoid replaying offline commands. `/pause` pauses new tasks, `/resume` enables them, `/status` checks the connection, and `/help` lists controls. These commands are processed after the current request finishes; they do not cancel an already-running action. Use **Disconnect Telegram** on the laptop to stop accepting remote work. In-progress desktop work is allowed to finish, and shutdown can wait for a running transcription/model download.

Keep the laptop awake, signed into Windows, online, and the desktop app open. AI tasks also require the Friday Colab backend to be running. Local actions can still work without Colab. If the desktop assistant is busy or a settings dialog is open, a remote task is rejected with a retry message instead of running concurrently. Telegram uses outbound [Bot API long polling](https://core.telegram.org/bots/api#getupdates); you do not need to expose a laptop port or create another ngrok tunnel.

### Screenshots to Telegram

Send `/screenshot`, `take a screenshot`, or `screenshot bhejo` to your bot, or use a voice note with the same request. The app captures the laptop's **primary display** and sends a photo directly to the authorized private chat that requested it. This includes whatever is visible on that display. No Friday/Colab request or extra screenshot package is needed. Voice input still needs the optional transcription packages.

The screenshot stays in memory during upload; no screenshot file is saved on the laptop. Images are resized to a maximum 2560-pixel edge and sent as JPEG through Telegram's [sendPhoto API](https://core.telegram.org/bots/api#sendphoto). Keep Windows signed in and unlocked; a disconnected/locked display may fail to capture. Paused, unauthorized, forwarded and stale requests do not capture or send images. If upload fails, request a new screenshot; the app does not silently retry an old image.

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
