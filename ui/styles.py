"""Modern Design System and Stylesheet for NEO AI Assistant."""

from datetime import datetime
from html import escape
import re

# Theme Palette Constants
BG_DARK = "#090d16"
BG_SURFACE = "#0f172a"
BG_CARD = "#141e33"
BG_CARD_HOVER = "#1a2742"
BORDER_SUBTLE = "#1e293b"
BORDER_FOCUS = "#00d2b4"
ACCENT_CYAN = "#00d2b4"
ACCENT_CYAN_HOVER = "#24e5c8"
ACCENT_INDIGO = "#6366f1"
TEXT_PRIMARY = "#f8fafc"
TEXT_SECONDARY = "#94a3b8"
TEXT_MUTED = "#64748b"


def get_application_stylesheet() -> str:
    """Return the complete product-grade stylesheet."""
    return """
        /* Global Window and Base */
        QMainWindow {
            background-color: #090d16;
        }
        QWidget#root {
            background-color: #090d16;
            color: #f8fafc;
            font-family: 'Segoe UI', -apple-system, BlinkMacSystemFont, 'Roboto', sans-serif;
            font-size: 13px;
        }

        /* Top Header Bar */
        QFrame#headerBar {
            background: #0f172a;
            border-bottom: 1px solid #1e293b;
            border-radius: 14px;
            padding: 4px;
        }
        QLabel#appLogo {
            background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #00d2b4, stop:1 #6366f1);
            color: #090d16;
            font-size: 20px;
            font-weight: 900;
            border-radius: 12px;
            padding: 4px;
        }
        QLabel#brandTitle {
            color: #ffffff;
            font-size: 18px;
            font-weight: 800;
            letter-spacing: 1.5px;
        }
        QLabel#brandBadge {
            background: #14243b;
            color: #38bdf8;
            border: 1px solid #1e3a5f;
            border-radius: 6px;
            padding: 2px 7px;
            font-size: 10px;
            font-weight: 700;
            letter-spacing: 0.8px;
        }
        QLabel#statusPillGreen {
            background: #0d2922;
            color: #34d399;
            border: 1px solid #10b981;
            border-radius: 12px;
            padding: 4px 11px;
            font-size: 11px;
            font-weight: 600;
        }
        QLabel#statusPillBlue {
            background: #13233c;
            color: #60a5fa;
            border: 1px solid #2563eb;
            border-radius: 12px;
            padding: 4px 11px;
            font-size: 11px;
            font-weight: 600;
        }
        QLabel#clockLabel {
            color: #94a3b8;
            font-size: 12px;
            font-weight: 500;
            padding: 0 4px;
        }

        /* Header Utility Buttons */
        QPushButton#headerBtn {
            background: #141e33;
            color: #cbd5e1;
            border: 1px solid #24324d;
            border-radius: 8px;
            padding: 6px 12px;
            font-size: 12px;
            font-weight: 600;
        }
        QPushButton#headerBtn:hover {
            background: #1e2c4a;
            color: #ffffff;
            border-color: #38bdf8;
        }
        QPushButton#headerBtn:pressed {
            background: #101828;
        }

        /* Hero / Welcome Banner */
        QFrame#heroCard {
            background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #121c33, stop:0.5 #0f2438, stop:1 #0c1a2e);
            border: 1px solid #1e3452;
            border-radius: 16px;
        }
        QLabel#heroSpark {
            color: #00d2b4;
            font-size: 20px;
            font-weight: bold;
        }
        QLabel#heroTitle {
            color: #ffffff;
            font-size: 22px;
            font-weight: 800;
            letter-spacing: 0.5px;
        }
        QLabel#heroSubtitle {
            color: #94a3b8;
            font-size: 13px;
            line-height: 140%;
        }

        /* Starter Prompt Chips */
        QPushButton#starterChip {
            background: #111a2e;
            color: #e2e8f0;
            border: 1px solid #22324d;
            border-radius: 10px;
            padding: 9px 13px;
            text-align: left;
            font-size: 12px;
            font-weight: 500;
        }
        QPushButton#starterChip:hover {
            background: #192742;
            color: #ffffff;
            border-color: #00d2b4;
        }
        QPushButton#starterChip:pressed {
            background: #0d1526;
        }

        /* Main Conversation Container */
        QFrame#chatPanel {
            background: #0f172a;
            border: 1px solid #1e293b;
            border-radius: 16px;
        }
        QLabel#panelHeading {
            color: #ffffff;
            font-size: 14px;
            font-weight: 700;
            letter-spacing: 0.5px;
        }
        QLabel#panelSubheading {
            color: #64748b;
            font-size: 10px;
            font-weight: 600;
            letter-spacing: 1px;
        }
        QTextBrowser#chatLog {
            background: transparent;
            border: none;
            color: #f1f5f9;
            selection-background-color: #1e3a5f;
            selection-color: #ffffff;
            font-size: 13px;
        }

        /* Activity / Thinking Card */
        QLabel#thinkingBox {
            background: #0e222d;
            color: #2dd4bf;
            border: 1px solid #134e4a;
            border-radius: 10px;
            padding: 8px 14px;
            font-size: 12px;
            font-weight: 600;
        }
        QLabel#listeningBox {
            background: #2b1117;
            color: #f87171;
            border: 1px solid #7f1d1d;
            border-radius: 10px;
            padding: 8px 14px;
            font-size: 12px;
            font-weight: 600;
        }

        /* Sidebar Panels */
        QFrame#sidebarCard {
            background: #0f172a;
            border: 1px solid #1e293b;
            border-radius: 16px;
        }
        QScrollArea#sidebarScroll {
            background: transparent;
            border: none;
        }
        QLabel#sidebarSectionTitle {
            color: #cbd5e1;
            font-size: 11px;
            font-weight: 700;
            letter-spacing: 1.2px;
            text-transform: uppercase;
        }

        /* Action Launch Buttons */
        QPushButton#actionBtn {
            background: #141e33;
            color: #e2e8f0;
            border: 1px solid #22324d;
            border-radius: 9px;
            padding: 9px 12px;
            font-size: 12px;
            font-weight: 600;
            text-align: left;
        }
        QPushButton#actionBtn:hover {
            background: #1a2845;
            color: #ffffff;
            border-color: #00d2b4;
        }
        QPushButton#actionBtn:pressed {
            background: #0e1524;
        }

        /* Weather Widget Card */
        QFrame#weatherCard {
            background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #12213a, stop:1 #111a2f);
            border: 1px solid #233758;
            border-radius: 12px;
            padding: 6px;
        }
        QLabel#weatherCity {
            color: #ffffff;
            font-size: 13px;
            font-weight: 700;
        }
        QLabel#weatherDetails {
            color: #94a3b8;
            font-size: 11px;
        }
        QLineEdit#weatherInput {
            background: #0a1120;
            color: #f8fafc;
            border: 1px solid #233758;
            border-radius: 6px;
            padding: 5px 8px;
            font-size: 11px;
        }
        QLineEdit#weatherInput:focus {
            border-color: #00d2b4;
        }
        QPushButton#weatherRefreshBtn {
            background: #1e3354;
            color: #38bdf8;
            border: 1px solid #2b4976;
            border-radius: 6px;
            padding: 5px 9px;
            font-size: 11px;
            font-weight: 600;
        }
        QPushButton#weatherRefreshBtn:hover {
            background: #27436e;
            color: #ffffff;
        }

        /* Composer Command Deck */
        QFrame#composerBar {
            background: #0f172a;
            border: 1.5px solid #1e293b;
            border-radius: 18px;
            padding: 4px 6px;
        }
        QFrame#composerBar:focus-within {
            border: 1.5px solid #00d2b4;
            background: #111b30;
        }
        QLabel#composerMode {
            background: #16243d;
            color: #00d2b4;
            border: 1px solid #203557;
            border-radius: 9px;
            padding: 6px 10px;
            font-size: 11px;
            font-weight: 700;
            letter-spacing: 0.5px;
        }
        QLineEdit#promptInput {
            background: transparent;
            color: #ffffff;
            border: none;
            font-size: 14px;
            padding: 6px 10px;
        }
        QLineEdit#promptInput:placeholder {
            color: #475569;
        }
        QPushButton#clearInputBtn {
            background: transparent;
            color: #64748b;
            border: none;
            border-radius: 12px;
            font-size: 13px;
            font-weight: bold;
            padding: 4px;
        }
        QPushButton#clearInputBtn:hover {
            color: #f87171;
            background: #1e293b;
        }
        QPushButton#sendBtn {
            background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #00d2b4, stop:1 #02b69c);
            color: #090d16;
            border: none;
            border-radius: 12px;
            padding: 8px 18px;
            font-size: 13px;
            font-weight: 800;
            letter-spacing: 0.5px;
        }
        QPushButton#sendBtn:hover {
            background: #25e5cb;
        }
        QPushButton#sendBtn:pressed {
            background: #019983;
        }
        QPushButton#sendBtn:disabled {
            background: #1e293b;
            color: #64748b;
        }
        QPushButton#listenBtn {
            background: #14243b;
            color: #38bdf8;
            border: 1px solid #1e3a5f;
            border-radius: 12px;
            padding: 8px 16px;
            font-size: 13px;
            font-weight: 700;
        }
        QPushButton#listenBtn:hover {
            background: #1c3252;
            color: #ffffff;
            border-color: #38bdf8;
        }
        QPushButton#listenBtn:disabled {
            background: #111a2c;
            color: #475569;
            border-color: #1e293b;
        }
        QPushButton#listenBtnActive {
            background: #7f1d1d;
            color: #ffffff;
            border: 1px solid #ef4444;
            border-radius: 12px;
            padding: 8px 16px;
            font-size: 13px;
            font-weight: 700;
        }

        /* Status & Shortcut Footer */
        QLabel#shortcutFooter {
            color: #64748b;
            font-size: 11px;
            font-weight: 500;
        }
        QLabel#systemStatus {
            color: #94a3b8;
            font-size: 11px;
            font-weight: 500;
        }

        /* Checkbox & Controls */
        QCheckBox {
            color: #cbd5e1;
            font-size: 12px;
            font-weight: 500;
            spacing: 8px;
        }
        QCheckBox::indicator {
            width: 17px;
            height: 17px;
            border-radius: 4px;
            border: 1px solid #334155;
            background: #141e33;
        }
        QCheckBox::indicator:hover {
            border-color: #00d2b4;
        }
        QCheckBox::indicator:checked {
            background: #00d2b4;
            border-color: #00d2b4;
            image: url(none);
        }

        /* Custom Scrollbars */
        QScrollBar:vertical {
            background: transparent;
            width: 6px;
            margin: 2px 0 2px 0;
        }
        QScrollBar::handle:vertical {
            background: #24324d;
            border-radius: 3px;
            min-height: 24px;
        }
        QScrollBar::handle:vertical:hover {
            background: #3b5077;
        }
        QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
            height: 0px;
        }
        QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {
            background: transparent;
        }

        /* Tooltips */
        QToolTip {
            background: #1e293b;
            color: #f8fafc;
            border: 1px solid #334155;
            border-radius: 6px;
            padding: 5px 9px;
            font-size: 11px;
        }
    """


def format_message_html(speaker: str, text: str) -> str:
    """Format chat messages with avatars, timestamps, and syntax cards."""
    now_str = datetime.now().strftime("%I:%M %p")
    safe_text = escape(text)

    # Detect tool actions (opening apps, created PDF, notes)
    is_action = any(phrase in text for phrase in [
        "Opening ", "Searching YouTube", "Searching Google",
        "PDF created:", "Created a new document and opened it in Notepad",
        "It is ", "Weather unavailable:"
    ])

    if speaker.lower() in ("you", "user"):
        return f"""
        <div style="margin: 14px 0 10px 0;">
            <div style="display: flex; justify-content: flex-end; align-items: baseline; margin-bottom: 5px;">
                <span style="color: #6366f1; font-weight: 700; font-size: 11px; letter-spacing: 0.5px;">👤 YOU</span>
                <span style="color: #64748b; font-size: 10px; margin-left: 8px;">{now_str}</span>
            </div>
            <div style="background-color: #1a253b; border: 1px solid #2a3a5c; border-radius: 12px; border-top-right-radius: 3px; padding: 12px 16px; color: #f8fafc; line-height: 150%; font-size: 13px;">
                {safe_text.replace(chr(10), '<br>')}
            </div>
        </div>
        """

    if speaker.lower() in ("error", "alert"):
        return f"""
        <div style="margin: 14px 0 10px 0;">
            <div style="margin-bottom: 5px;">
                <span style="color: #f87171; font-weight: 700; font-size: 11px;">⚠️ SYSTEM NOTICE</span>
                <span style="color: #64748b; font-size: 10px; margin-left: 8px;">{now_str}</span>
            </div>
            <div style="background-color: #241116; border: 1px solid #581c24; border-radius: 12px; padding: 12px 16px; color: #fca5a5; line-height: 150%; font-size: 13px;">
                {safe_text.replace(chr(10), '<br>')}
            </div>
        </div>
        """

    if is_action:
        return f"""
        <div style="margin: 14px 0 10px 0;">
            <div style="margin-bottom: 5px;">
                <span style="color: #00d2b4; font-weight: 700; font-size: 11px; letter-spacing: 0.5px;">⚡ DESKTOP ACTION</span>
                <span style="color: #64748b; font-size: 10px; margin-left: 8px;">{now_str}</span>
            </div>
            <div style="background-color: #0b1e23; border: 1px solid #134e4a; border-radius: 12px; padding: 12px 16px; color: #5eead4; line-height: 150%; font-size: 13px;">
                <span style="font-weight: 700; color: #2dd4bf;">✓ Execution:</span> {safe_text.replace(chr(10), '<br>')}
            </div>
        </div>
        """

    # Format code blocks and markdown accents for standard AI responses
    formatted_body = _format_rich_markdown(safe_text)

    return f"""
    <div style="margin: 14px 0 10px 0;">
        <div style="margin-bottom: 5px;">
            <span style="color: #00d2b4; font-weight: 800; font-size: 11px; letter-spacing: 0.5px;">✦ NEO AI</span>
            <span style="color: #38bdf8; font-size: 10px; font-weight: 600; margin-left: 6px; background: #0c2338; border: 1px solid #143759; padding: 1px 6px; border-radius: 4px;">AGENT</span>
            <span style="color: #64748b; font-size: 10px; margin-left: 8px;">{now_str}</span>
        </div>
        <div style="background-color: #10192b; border: 1px solid #1c2b45; border-radius: 12px; border-top-left-radius: 3px; padding: 13px 17px; color: #e2e8f0; line-height: 155%; font-size: 13px;">
            {formatted_body}
        </div>
    </div>
    """


def _format_rich_markdown(text: str) -> str:
    """Format markdown elements like code blocks, bullets, bold, italics."""
    # Convert code blocks ```...```
    def replace_code_block(match):
        code_content = match.group(2)
        lang = match.group(1) or "code"
        return f'<div style="background-color: #080d17; border: 1px solid #1b283d; border-radius: 8px; margin: 8px 0; padding: 10px 14px; font-family: Consolas, monospace; font-size: 12px; color: #38bdf8;"><div style="color: #64748b; font-size: 10px; margin-bottom: 4px; text-transform: uppercase;">{lang}</div><pre style="margin:0; white-space:pre-wrap;">{code_content}</pre></div>'

    text = re.sub(r'```(\w+)?\n?(.*?)```', replace_code_block, text, flags=re.DOTALL)

    # Inline code `...`
    text = re.sub(
        r'`([^`]+)`',
        r'<code style="background-color: #090e1a; border: 1px solid #1e2d44; color: #38bdf8; padding: 2px 6px; border-radius: 4px; font-family: Consolas, monospace; font-size: 12px;">\1</code>',
        text
    )

    # Bold **text**
    text = re.sub(r'\*\*([^*]+)\*\*', r'<b style="color: #ffffff;">\1</b>', text)

    # Bullet points
    text = re.sub(r'^[•\-\*]\s+(.*)$', r'<div style="margin: 3px 0 3px 14px;">▪ \1</div>', text, flags=re.MULTILINE)

    # Convert remaining newlines
    text = text.replace('\n', '<br>')
    return text
