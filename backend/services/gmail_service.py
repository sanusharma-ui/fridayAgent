"""Gmail REST client. Credentials stay local; no mailbox mutations on reads."""
import base64
import time
from email.message import EmailMessage
from email.utils import getaddresses
from html import unescape
import re
from urllib.parse import quote

import requests
from backend import config


class GmailError(Exception):
    pass


class GmailService:
    BASE = "https://gmail.googleapis.com/gmail/v1/users/me"

    def __init__(self, session=None):
        self.session = session or requests.Session()
        self.token = ""
        self.expires = 0

    def _access_token(self):
        if not config.GMAIL_ENABLED:
            raise GmailError("Set GMAIL_ENABLED=true and configure Gmail OAuth in .env, then restart.")
        if not all((config.GMAIL_CLIENT_ID, config.GMAIL_CLIENT_SECRET, config.GMAIL_REFRESH_TOKEN)):
            raise GmailError("Set GMAIL_CLIENT_ID, GMAIL_CLIENT_SECRET and GMAIL_REFRESH_TOKEN in .env, then restart.")
        if self.token and time.monotonic() < self.expires:
            return self.token
        try:
            response = self.session.post("https://oauth2.googleapis.com/token", data={
                "client_id": config.GMAIL_CLIENT_ID, "client_secret": config.GMAIL_CLIENT_SECRET,
                "refresh_token": config.GMAIL_REFRESH_TOKEN, "grant_type": "refresh_token",
            }, timeout=20)
            if response.status_code != 200:
                raise GmailError("OAuth authorization failed. Check your Gmail credentials and reauthorize if revoked or expired.")
            data = response.json()
            self.token = data["access_token"]
            self.expires = time.monotonic() + max(0, int(data.get("expires_in", 3600)) - 60)
            return self.token
        except (requests.RequestException, ValueError, KeyError, TypeError):
            raise GmailError("Could not obtain Gmail authorization. Check connectivity and OAuth configuration.") from None

    def _request(self, method, path, **kwargs):
        token = self._access_token()
        try:
            response = self.session.request(method, self.BASE + path,
                headers={"Authorization": "Bearer " + token}, timeout=25, **kwargs)
            if response.status_code == 401:
                self.token = ""
                raise GmailError("Gmail authorization expired. Retry the request or reauthorize your account.")
            if response.status_code == 403:
                raise GmailError("Gmail access denied. Enable the Gmail API and authorize gmail.readonly and gmail.send scopes.")
            if not 200 <= response.status_code < 300:
                raise GmailError(f"Gmail request failed (HTTP {response.status_code}).")
            return response.json()
        except (requests.RequestException, ValueError):
            if method == "POST":
                raise GmailError("Send status is unknown. Check Gmail Sent before trying again; the message may have been sent.") from None
            raise GmailError("Could not read Gmail. Check your connection and try again.") from None

    def read(self, query="in:inbox", limit=5):
        listing = self._request("GET", "/messages", params={"q": query, "maxResults": max(1, min(limit, 10))})
        result = []
        for entry in listing.get("messages", [])[:10]:
            message = self._request("GET", "/messages/" + entry["id"], params={"format": "full"})
            payload = message.get("payload", {})
            headers = {h["name"].lower(): h.get("value", "") for h in payload.get("headers", [])}
            result.append({"from": headers.get("from", "Unknown sender"),
                           "subject": headers.get("subject", "(No subject)"),
                           "date": headers.get("date", ""),
                           "body": self._body(payload) or unescape(message.get("snippet", ""))})
        return result

    @classmethod
    def _body(cls, payload):
        if payload.get("filename"):
            return ""  # Never fetch attachments.
        parts = payload.get("parts", [])
        if parts:
            if payload.get("mimeType") == "multipart/alternative":
                parts = sorted(parts, key=lambda p: p.get("mimeType") != "text/plain")
                return next((text for part in parts if (text := cls._body(part))), "")
            return "\n".join(filter(None, (cls._body(p) for p in parts)))[:12000]
        kind = payload.get("mimeType")
        data = payload.get("body", {}).get("data", "")
        if kind not in {"text/plain", "text/html"} or not data:
            return ""
        try:
            text = base64.urlsafe_b64decode(data + "=" * (-len(data) % 4)).decode("utf-8", errors="replace")
        except ValueError:
            return ""
        if kind == "text/html":
            text = re.sub(r"(?is)<(script|style)\b.*?</\1>", "", text)
            text = unescape(re.sub(r"<[^>]+>", " ", text))
        return text.strip()[:12000]

    def send(self, recipient, subject, body):
        if not re.fullmatch(r"[A-Za-z0-9.!#$%&'*+/=?^_`{|}~-]+@[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)+", recipient):
            raise GmailError("Provide one complete recipient email address.")
        if not subject.strip() or "\r" in subject or "\n" in subject or len(subject) > 200:
            raise GmailError("Provide a one-line subject of at most 200 characters.")
        if not body.strip() or len(body) > 10000:
            raise GmailError("Provide a message body of 1 to 10000 characters.")
        message = EmailMessage()
        message["To"] = recipient
        message["Subject"] = subject
        message.set_content(body)
        raw = base64.urlsafe_b64encode(message.as_bytes()).decode("ascii")
        result = self._request("POST", "/messages/send", json={"raw": raw})
        message_id = result.get("id") if isinstance(result, dict) else None
        if not isinstance(message_id, str) or not message_id.strip():
            raise GmailError("Send status is unknown. Check Gmail Sent before trying again.")
        # Verify the exact Sent record without ever retrying the send operation.
        receipt = f"To: {recipient}\nGmail message ID: {message_id}"
        try:
            stored = self._request("GET", "/messages/" + quote(message_id, safe=""),
                params={"format": "metadata", "metadataHeaders": ["From", "To"]})
            if not isinstance(stored, dict) or stored.get("id") != message_id or "SENT" not in stored.get("labelIds", []):
                raise GmailError("Sent record is not available yet.")
            headers = {h["name"].lower(): h.get("value", "") for h in stored.get("payload", {}).get("headers", [])}
            actual_to = [address.casefold() for _, address in getaddresses([headers.get("to", "")])]
            sender = headers.get("from", "(sender unavailable)")
            if actual_to != [recipient.casefold()]:
                return ("Gmail accepted the email, but the recorded recipient could not be verified. "
                        "Check Gmail Sent before sending again.\n" + receipt +
                        f"\nRecorded To: {headers.get('to', '(unavailable)')}\nFrom: {sender}")
        except (GmailError, KeyError, TypeError, AttributeError):
            return ("Gmail accepted the email, but Sent-folder verification is unavailable. "
                    "Check Gmail Sent before sending again.\n" + receipt +
                    "\nRecipient inbox delivery is not confirmed.")
        return ("Email sent; verified in Gmail Sent.\n" + f"From: {sender}\n" + receipt +
                "\nRecipient inbox delivery is not confirmed. If it hasn't arrived, check Spam, All Mail, filters, and any bounce message.")
