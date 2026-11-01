# SUNDAY desktop assistant

SUNDAY is the Electron/React desktop pet in `sunday/`, connected to the existing Python agent in `backend/`. It supports typed commands, offline push-to-talk, desktop/browser actions, Friday AI (with the existing optional Groq fallback), weather, and opt-in Telegram access.

## Setup (Windows PowerShell)

```powershell
python -m pip install -r requirements.txt
Copy-Item .env.example .env # if you do not already have a .env file
# Edit .env: use the Colab secret and the current ngrok URL.
python main.py
```

The key must equal the `FRIDAY_API_KEY` stored in Colab Secrets. The app loads `.env` from the project root; environment variables take precedence. The app sends `POST /chat` with `{"message": "..."}` and the `x-api-key` header, then reads the `response` field. Keep the Colab runtime and ngrok tunnel active. If the tunnel URL changes, update `AI_ENDPOINT_URL`. Never share or commit `.env` or real keys.

Groq is an optional fallback when the Colab backend is unavailable. Set `GROQ_ENABLED=true` and provide `GROQ_API_KEY` in `.env`; leave `GROQ_ENABLED=false` to prevent all Groq requests. `GROQ_MODEL` defaults to `llama-3.3-70b-versatile`. Friday remains the primary backend whenever it responds successfully.

Desktop voice input uses OpenAI Whisper tiny.en through faster-whisper: 39M parameters, English-only, and downloaded to the local Hugging Face cache on first use (about 75 MB). After that first download it transcribes locally; it does not upload recordings. The backend starts microphone monitoring automatically and listens for **“Hey Sunday”**. After the wake word, it records one six-second command; the **Listen (6s)** button remains available as a manual fallback. English is the recognition language; Hindi/Hinglish speech may not transcribe correctly. Whisper inference runs in a separate Python worker so its native CPU runtime cannot terminate the Qt backend. Pet voice is controlled through SUNDAY Settings > Sound & Voice (Speak, Babble, or Off). Speech bubbles show a 600-character preview; Speak mode receives the full reply and the full text remains in chat. Microphone permission and a working input device are required.

**Agent** handles typed and spoken requests. The Friday model plans supported tool calls as JSON, and the desktop app validates the tool and its arguments before running it locally. It can open apps, websites and supported files, search the web or YouTube, and create a PDF. General questions go to Friday. The Colab backend is a text generator rather than a native tool-calling API; model output may need rephrasing if it produces an invalid plan. Simple open requests also work without the backend. AI-generated text is never run as shell code. Other requests require the API key and a reachable backend described above.

Try `open facebook`, `open terminal`, `open file report.pdf`, `play lo-fi on youtube`, or `create a PDF about solar energy`. For files, provide a full path or an exact filename directly inside Desktop, Documents, or Downloads. Only supported document and image formats can be opened. PDF creation asks Friday to write the document and saves a new file in `Documents/NEO PDFs`; check the generated content. Opening Gmail only opens its website; the Gmail commands below provide mail summaries and confirmed sending. Arbitrary application control, other outbound messaging, file deletion, and running arbitrary shell commands are not wired up. The wake-word listener pauses while a command is being processed and resumes after the reply, so it does not compete with command recording.

You can also open installed Windows apps by their Start menu name, or say `open example.com` for a website. If multiple app names match, specify the exact name. Apps without a Start menu shortcut may not be found.

`Open terminal` opens PowerShell in a separate console window; `open command prompt` opens a separate Command Prompt window. Opening a terminal does not run commands inside it.

Say `write an essay about moons` or `write a short poem about rain in Notepad`: Friday generates the requested content, saves a new UTF-8 text file in `Documents/NEO Notes`, and opens it in a new Notepad document. It does not type into or change an already-open document. For literal text, say `write exactly Hello from NEO`; the words following `exactly` are saved as given. Generated content requires the Friday backend and should be reviewed.

To create a file, say `create file hello.txt with content Hello from SUNDAY`. New files are created only inside `D:\test` for now; paths outside that folder and overwriting existing files are rejected. Content is written as UTF-8, and arbitrary shell commands are not executed. This restricted location can be expanded later after the file workflow is reviewed.

For weather, set `OPENWEATHER_API_KEY` in the environment. The key formerly present in source should be rotated before reuse.

## Gmail: brief summaries and sending

Gmail is optional and disabled by default. It uses the Gmail API with your account's OAuth permission; it does not use your Google password or the controlled browser's login. No extra Python dependencies are required.

1. In [Google Cloud Console](https://console.cloud.google.com/), create/select a project, enable **Gmail API**, and configure Google Auth Platform's consent screen. Add your Gmail account as a test user if the app is in Testing.
2. Create an OAuth client of type **Web application** for the manual setup below. Add `https://developers.google.com/oauthplayground` as an authorized redirect URI.
3. Open [Google OAuth Playground](https://developers.google.com/oauthplayground/). In its settings, select **Use your own OAuth credentials**, enter your client ID and client secret, and keep access type **Offline**. Authorize both `https://www.googleapis.com/auth/gmail.readonly` and `https://www.googleapis.com/auth/gmail.send` with the Gmail account you want the assistant to use.
4. Exchange the authorization code for tokens. Copy the refresh token into your local `.env`, along with that same client ID and secret. Using your own OAuth credentials avoids Playground's default 24-hour refresh-token revocation.
5. Set the following values and restart the app:

   ```dotenv
   GMAIL_ENABLED=true
   GMAIL_CLIENT_ID=your_oauth_client_id
   GMAIL_CLIENT_SECRET=your_oauth_client_secret
   GMAIL_REFRESH_TOKEN=your_refresh_token
   ```

Keep `FRIDAY_API_KEY` and `AI_ENDPOINT_URL` configured for summaries and generated drafts. An enabled Groq fallback can also process this content. External OAuth apps in Testing normally receive refresh tokens that expire after seven days for Gmail scopes; reauthorize when needed. See [Google's token expiration guidance](https://developers.google.com/identity/protocols/oauth2#expiration). No Gmail API key, account password, sender-address key, or manually refreshed access token is needed: messages send from the account that authorized the refresh token.

Example commands in the existing desktop chat, voice input, or authorized Telegram chat:

- `read my emails` — summarize up to five inbox messages.
- `summarize my unread 3 emails in brief` — brief summaries without marking messages as read.
- `read my emails from person@example.com` — filter by sender.
- `send email to person@example.com subject: Meeting body: Can we meet tomorrow at 10?` — preview your exact text.
- `draft email to person@example.com about rescheduling our meeting` — generate a body and preview it.
- `Send email to person@example.com Subject: Can we meet` — AI writes the missing body; no command template is required.
- `Email person@example.com and ask if they are free for a meeting` — interpret the request and prepare an English draft.
- `Make it shorter and more polite` or `isko thoda polite karo` — revise the current draft and show a fresh preview.
- `Yes, send it` or `haan bhej do` — approve the current preview in the same conversation.
- `confirm send CODE` — use the eight-character code in the preview to send that draft once, within five minutes.
- `cancel email` — discard the pending draft.

Email interpretation accepts English and Hinglish, with English drafts and replies by default. If the recipient or purpose is missing, the assistant asks a short question and keeps the conversation context for five minutes. Natural interpretation and revisions require a working AI provider; exact subject/body commands remain available without it. Recipient names are not resolved or guessed: provide the full email address when asked. Generated draft content and your instructions are sent to your configured AI provider.

Drafts stay in app memory, separately for the desktop and each authorized Telegram user. A revision replaces the previous preview and invalidates its confirmation code. Inspect the full preview before approving; approval sends once and expires after five minutes. After an unrelated turn, short approval is disabled until a fresh preview; the explicit confirmation code remains available for an unchanged, unexpired draft. The model cannot call send: only your local approval of a preview can do that. Cancellation, malformed revisions, and failed sends cannot silently reuse an old approval.

Reading is capped at ten messages per request; summaries use bounded message text and identify partial content. Attachments are not read or sent. Mail text and sender/subject metadata are sent to your configured AI provider for summaries, and summaries appear in the requesting chat (including Telegram). Gmail credentials are not included in AI prompts. If AI is unavailable, reading shows a short original-text preview instead. After an uncertain send result, check Gmail Sent before making another draft; the app does not retry sends automatically.

After sending, the app reads back the exact Gmail message and checks its SENT label and recipient. The receipt shows the actual sender, recipient, and Gmail message ID. This verifies Gmail Sent, not arrival in the recipient's inbox. If verification is unavailable, the app reports that separately and never retries sending. For a missing incoming email, check the recipient account's Spam, All Mail, Trash, and filters, plus the sender's bounce notices.

The implementation follows Google's [message listing](https://developers.google.com/workspace/gmail/api/reference/rest/v1/users.messages/list) and [MIME sending](https://developers.google.com/workspace/gmail/api/guides/sending) APIs. Local mocked tests cover the API contract and confirmation flow; account authorization and actual delivery require your configured Gmail account.

## Chrome session controls

Install the updated `requirements.txt` and have Google Chrome installed. Website commands now use a visible Chrome session managed by the assistant. The interface, status messages, examples, and AI reply instructions use English.

Send these requests one at a time from the desktop or your authorized Telegram chat:

1. `Can you open YouTube for me?`
2. `Search for relaxing piano music`
3. `Click 1` (or `click the first link`)
4. `Pause the video`
5. `Go back`
6. `Scroll down`

For numbered YouTube playback, say `play 2`, `play two`, or `play the second video` while on search results. The assistant checks the controlled tab's current page, opens that numbered video result, and requests playback. On an open video, `play` resumes it and `pause` pauses it. On search results, plain `play` asks you to choose a number. Playback failures are reported rather than treated as success. Numbers refer to standard video results, excluding Shorts shelves and playlists.

Other controls: `scroll up`, `scroll to the top`, `scroll to the bottom`, `refresh`, `go forward`, `open a new tab`, `show tabs`, `switch to tab 2`, and `close this tab`. Send these controls through the pet chat panel. Simple controls and searches work without Colab; more varied wording uses the AI planner.

Follow-up searches use the selected controlled tab's current website: YouTube, Google, Bing, or DuckDuckGo. Say `search for astronomy on Google` or `search for astronomy on YouTube` to change sites explicitly. Numbered result opening supports YouTube videos and Google results, up to the first 20 available links. Consent dialogs or changed website layouts can prevent result selection; close the dialog and retry. Scrolling targets the page, not nested panels.

For AI-planned browser actions, each request receives only a fresh, compact snapshot of the active tab: title, URL, limited visible text, and visible buttons, links, inputs, tabs, and other interactive controls. The snapshot includes semantic roles, accessible names, ARIA labels, associated form labels, IDs, and disabled state. You can say `click the Continue button` or `click the Sign in link`; the model selects a temporary element reference and the app validates that reference against the current page before clicking. Clear commands such as `click Continue` use a local unique accessible-name match first; duplicate matches are rejected instead of guessed. The snapshot is regenerated after navigation or other page changes and is never reused as page state. Context is bounded so requests stay within the backend limit.

Ordinary visible form fields can be filled with commands such as `enter user@example.com in the email field` or `password field me ... daalo`. The value is extracted locally and redacted before the AI request. Password, OTP, card, CVV, and other sensitive fields are intentionally blocked in safe mode; the assistant will not submit forms or expose those values to the AI backend.

The browser uses a separate temporary profile. Existing personal Chrome windows, logins, and tabs are not controlled. Use `show tabs` and `switch to tab N` to select the target; manually clicking a different tab does not change the assistant's selected tab. Desktop and Telegram share this session. Closing the app closes its controlled browser; a new app session starts without its previous logins. Arbitrary clicks, form submissions, purchases, and downloads are not implemented.

`BROWSER_CHANNEL=chrome` is the default in `.env.example`. You may use `msedge` with installed Microsoft Edge, or `chromium` after running `python -m playwright install chromium`. Restart the app after changing this setting. See the [Playwright browser documentation](https://playwright.dev/python/docs/browsers). If Playwright is missing, the app shows an installation message instead of reporting that the browser action succeeded.

## Control your laptop from Telegram

Telegram text and voice notes use the same agent and supported tools as the desktop window. Tasks run on the laptop, and the bot sends a text result to your phone. This is voice-note input, not a live call; generated PDFs and Notepad files remain on the laptop.

1. In Telegram, open the official [@BotFather](https://t.me/BotFather), use `/newbot`, and copy your new bot's token. Never send the token to other chats or commit it.
2. For voice notes, install the optional speech dependencies on the laptop:

   ```powershell
   python -m pip install -r requirements-telegram.txt
   python main.py
   ```

   Text requests work with the normal `requirements.txt` installation.
3. In the laptop app, open **Backend settings > Telegram**, paste the bot token, and save. Leave **Allowed user IDs** empty for initial pairing. Click **Toggle Telegram** below the chat.
4. Open your own bot's private chat on your phone and send `/id` **after the laptop says connected/setup only**. Copy your numeric user ID into **Backend settings > Telegram > Allowed user IDs**, save, wait for disconnection, then click **Toggle Telegram** again. An empty allowlist permits only `/id`; it never permits tasks. Add multiple trusted IDs separated by commas if needed.
5. Send `/start`, then `/voice` for recording instructions. Hold Telegram's **microphone** button, speak, and send the voice note; if the button shows a camera, tap it to switch to microphone. Say `open YouTube`, `read my unread emails` (after Gmail setup), or `explain solar energy briefly`. No "Hey Sunday" wake word is needed in Telegram. You will see `Heard: ...`, a thinking message, and a text reply. The desktop conversation also shows remote requests.

For `.env` setup, use these values (the token and ID must be your own), then restart:

```dotenv
TELEGRAM_ENABLED=true
TELEGRAM_BOT_TOKEN=your_botfather_token
TELEGRAM_ALLOWED_USER_IDS=your_numeric_id_from_the_id_command
TELEGRAM_WHISPER_MODEL=base
TELEGRAM_VOICE_LANGUAGE=
```

Leave the language empty for auto-detection, or set `hi` for Hindi / `en` for English. Start with a short 5–10 second note. If it is misheard, send the corrected request as text. Gmail sending still requires preview confirmation: reply `Yes, send it` in the same chat, or type the displayed `confirm send CODE`.

Telegram speech decoding and transcription run in a hidden separate Python process, with a five-minute timeout, so a native speech-library crash does not terminate the desktop app. The model weights are cached, but the speech process loads the model for each note. Missing dependencies, download failures, and worker crashes produce a text error. A failed transcription never reaches the agent.

Settings are stored in the local ignored `.env`; equivalent variables are listed in `.env.example`. You can optionally enable automatic Telegram connection on app startup. Changing Telegram settings requires disconnecting and reconnecting. A bot can only have one polling app/webhook active; use a dedicated bot for this laptop.

Voice notes support multilingual transcription with [faster-whisper](https://github.com/SYSTRAN/faster-whisper); its PyAV dependency decodes Telegram audio without a separate FFmpeg executable. The default `base` model runs on CPU and downloads to the user model cache on first use. That first request can take longer; later transcription is local. Use `TELEGRAM_VOICE_LANGUAGE=en` or `hi` if automatic language detection is unreliable. Hindi/Hinglish recognition and action interpretation can still make mistakes. Audio downloads are temporary and deleted after transcription. Voice notes are limited to 60 seconds and 10 MB; text/transcripts are limited to 1500 characters. Transcript text is sent to the configured Friday backend when AI planning or generation is needed.

Only allowed **numeric user IDs in private chats** can run tasks. Group, forwarded, edited and old messages are not executed. Pending messages from before connection are discarded to avoid replaying offline commands. `/pause` pauses new tasks, `/resume` enables them, `/status` checks the connection, and `/help` lists controls. These commands are processed after the current request finishes; they do not cancel an already-running action. Use **Toggle Telegram** on the laptop to stop accepting remote work. In-progress desktop work is allowed to finish, and shutdown can wait for a running transcription/model download.

Keep the laptop awake, signed into Windows, online, and the desktop app open. AI tasks also require the Friday Colab backend to be running. Local actions can still work without Colab. If the desktop assistant is busy or a settings dialog is open, a remote task is rejected with a retry message instead of running concurrently. Telegram uses outbound [Bot API long polling](https://core.telegram.org/bots/api#getupdates); you do not need to expose a laptop port or create another ngrok tunnel.

### Screenshots to Telegram

Send `/screenshot`, `take a screenshot`, or `screenshot bhejo` to your bot, or use a voice note with the same request. The app captures the laptop's **primary display** and sends a photo directly to the authorized private chat that requested it. This includes whatever is visible on that display. No Friday/Colab request or extra screenshot package is needed. Desktop push-to-talk installs faster-whisper through `requirements.txt`; Telegram voice-note transcription uses the separately configured multilingual model and `requirements-telegram.txt`.

The screenshot stays in memory during upload; no screenshot file is saved on the laptop. Images are resized to a maximum 2560-pixel edge and sent as JPEG through Telegram's [sendPhoto API](https://core.telegram.org/bots/api#sendphoto). Keep Windows signed in and unlocked; a disconnected/locked display may fail to capture. Paused, unauthorized, forwarded and stale requests do not capture or send images. If upload fails, request a new screenshot; the app does not silently retry an old image.

## Starting and using SUNDAY

Install Node.js 22.12+ (or Node.js 24 LTS), Python, and the Python requirements above. Run `python main.py` from this checkout. On the first run the launcher installs npm dependencies and builds the pet; internet is needed for that setup. Later launches reuse the build unless frontend source files change. `python app.py` is an alias for the same launcher.

The pet and chat panel open together. Double-click the pet to reopen chat; right-click it or use the tray for appearance, animation studio, and pet settings. Closing chat leaves the pet running. Use **Quit SUNDAY / Exit** to close everything; running backend work finishes before exit.

- **Enter** sends chat; **Shift+Enter** adds a line.
- **Listen (6s)** records one offline voice request and routes the transcript through the same agent.
- **Weather** uses the city saved in **Backend settings**, where API keys, endpoint, default city, and Telegram preferences remain editable.
- **Toggle Telegram** connects/disconnects the existing allowlisted Telegram service. Connection details appear in chat.
- SUNDAY pet settings control its appearance, roaming, sounds and speech. Secrets stay in Python and the root `.env`.

## How the connection works

`main.py` starts Electron using the current Python interpreter. Electron starts `python -u -m backend.runtime` as a hidden child process. A private UTF-8 JSON-lines pipe carries chat/control requests and replies/status events. No local HTTP server or additional ngrok tunnel is opened. The renderer only receives a validated Electron preload API.

The Python runtime owns one agent/router/browser session. Slow tasks run off the Qt event thread; settings and screenshots stay on that thread. Overlapping desktop/voice/Telegram work is rejected with a busy message rather than executed twice. Voice transcripts are displayed without being resubmitted. EOF or Exit stops Telegram, finishes current work and closes the managed browser. An unexpected backend failure is shown in chat; requests are never silently replayed.

```
main.py                 # one-command launcher
app.py                  # compatibility launcher
backend/
  config.py             # loads root .env
  runtime.py            # process bridge and task lifecycle
  settings_dialog.py    # existing backend preferences
  services/             # agent, browser, AI, voice, Telegram, weather
sunday/                 # pet, chat, Electron bridge and frontend assets
tests/                  # backend regression and bridge tests
```

Whisper weights are cached by Hugging Face outside the repository on first use.

## Validation and troubleshooting

```powershell
python -m unittest discover -s tests -v
cd sunday
npm.cmd run build
npm.cmd test
npx.cmd playwright test tests/e2e/backend.spec.ts
```

If Python dependencies are missing, use the same interpreter as the launcher: `python -m pip install -r requirements.txt`. The roughly 75 MB Whisper model downloads from Hugging Face the first time you press Listen; later voice recognition runs locally. If the frontend install/build fails, the launcher stops and prints the error. If chat says disconnected, inspect the launch terminal and restart `python main.py`. An active Friday/ngrok endpoint and valid key are still required for online AI. Optional Telegram voice dependencies remain in `requirements-telegram.txt`.

The standalone Electron packaging commands in `sunday/` package the pet only; a self-contained installer bundling Python and the model is not part of this source launcher.
