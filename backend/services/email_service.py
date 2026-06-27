"""Email service — send via SMTP, receive via IMAP, LLM classification."""

import asyncio
import smtplib
import imaplib
import email as email_lib
from email.message import EmailMessage
from email.header import decode_header
from datetime import datetime, timezone
from typing import Optional

from backend.agents import TradeAgent


class EmailService:
    """Handle email sending and receiving for a mailbox."""

    @staticmethod
    def _decode_mime_header(header_value: str) -> str:
        """Decode MIME encoded header text to plain string."""
        if not header_value:
            return ""
        parts = decode_header(header_value)
        result = []
        for part, encoding in parts:
            if isinstance(part, bytes):
                try:
                    result.append(part.decode(encoding or "utf-8", errors="replace"))
                except (LookupError, UnicodeDecodeError):
                    result.append(part.decode("utf-8", errors="replace"))
            else:
                result.append(str(part))
        return "".join(result)

    @staticmethod
    async def send_email(
        smtp_host: str,
        smtp_port: int,
        smtp_user: str,
        smtp_pass: str,
        from_addr: str,
        to_addr: str,
        subject: str,
        body: str,
        use_ssl: bool = True,
    ) -> bool:
        """Send an email via SMTP (offloaded to thread pool)."""
        def _send():
            msg = EmailMessage()
            msg["From"] = from_addr
            msg["To"] = to_addr
            msg["Subject"] = subject
            msg.set_content(subject)
            if body.strip().startswith("<") or "html" in body[:200].lower():
                msg.set_content("This email requires HTML support.")
                msg.add_alternative(body, subtype="html")
            else:
                msg.set_content(body)

            if use_ssl or smtp_port == 465:
                with smtplib.SMTP_SSL(smtp_host, smtp_port, timeout=30) as server:
                    if smtp_user:
                        server.login(smtp_user, smtp_pass)
                    server.send_message(msg)
            else:
                with smtplib.SMTP(smtp_host, smtp_port, timeout=30) as server:
                    server.starttls()
                    if smtp_user:
                        server.login(smtp_user, smtp_pass)
                    server.send_message(msg)

        try:
            loop = asyncio.get_running_loop()
            await loop.run_in_executor(None, _send)
            return True
        except Exception as e:
            print(f"[EmailService] Send failed: {e}")
            return False

    @staticmethod
    async def check_inbox(
        imap_host: str,
        imap_port: int,
        imap_user: str,
        imap_pass: str,
        use_ssl: bool = True,
    ) -> list[dict]:
        """Fetch unread emails from IMAP inbox (offloaded to thread pool)."""
        def _check():
            results = []
            if use_ssl or imap_port == 993:
                imap = imaplib.IMAP4_SSL(imap_host, imap_port, timeout=30)
            else:
                imap = imaplib.IMAP4(imap_host, imap_port, timeout=30)

            imap.login(imap_user, imap_pass)
            imap.select("INBOX")

            status, message_ids = imap.search(None, "UNSEEN")
            if status != "OK":
                imap.logout()
                return results

            ids = message_ids[0].split() if message_ids[0] else []
            for mid in ids[-20:]:
                status, msg_data = imap.fetch(mid, "(RFC822)")
                if status != "OK":
                    continue

                for response_part in msg_data:
                    if isinstance(response_part, tuple):
                        raw_email = response_part[1]
                        msg = email_lib.message_from_bytes(raw_email)

                        subject = EmailService._decode_mime_header(msg.get("Subject", ""))
                        from_hdr = EmailService._decode_mime_header(msg.get("From", ""))
                        body = ""

                        if msg.is_multipart():
                            for part in msg.walk():
                                if part.get_content_type() == "text/plain":
                                    payload = part.get_payload(decode=True)
                                    if payload:
                                        body = payload.decode("utf-8", errors="replace")
                                    break
                        else:
                            payload = msg.get_payload(decode=True)
                            if payload:
                                body = payload.decode("utf-8", errors="replace")

                        results.append({
                            "message_id": msg.get("Message-ID", ""),
                            "subject": subject,
                            "from": from_hdr,
                            "body": body[:5000],
                            "date": msg.get("Date", ""),
                        })

            imap.logout()
            return results

        try:
            loop = asyncio.get_running_loop()
            return await loop.run_in_executor(None, _check)
        except Exception as e:
            err_msg = str(e)
            print(f"[EmailService] IMAP check failed: {err_msg}")
            return [{"error": True, "message": f"IMAP failed: {err_msg[:200]}"}]

    @staticmethod
    async def classify_email(subject: str, body: str) -> dict:
        """Use LLM to classify incoming email intent. Returns category + extracted info."""
        agent = TradeAgent(system_prompt="You are an email classifier for a PP hollow board trading company.")

        prompt = f"""Classify this incoming buyer email:

Subject: {subject}
Body: {body[:1000]}

Categories:
1. price_inquiry — asking for price/quote
2. negotiation — bargaining or asking for discount
3. order_confirmation — placing an order
4. complaint — problem with product/service
5. general_inquiry — other business questions
6. spam — irrelevant or promotional

Respond in format:
CATEGORY: <category>
SUMMARY: <one-line summary of what they need>
URGENCY: <high/medium/low>
PRODUCT: <product mentioned or "unknown">
"""
        try:
            response = await agent.chat(prompt, temperature=0.1)
            result = {"category": "general_inquiry", "summary": "", "urgency": "medium", "product": "unknown"}

            for line in response.strip().split("\n"):
                if line.startswith("CATEGORY:"):
                    val = line.split(":", 1)[1].strip().lower()
                    if val in ("price_inquiry", "negotiation", "order_confirmation", "complaint", "general_inquiry", "spam"):
                        result["category"] = val
                elif line.startswith("SUMMARY:"):
                    result["summary"] = line.split(":", 1)[1].strip()
                elif line.startswith("URGENCY:"):
                    val = line.split(":", 1)[1].strip().lower()
                    if val in ("high", "medium", "low"):
                        result["urgency"] = val
                elif line.startswith("PRODUCT:"):
                    result["product"] = line.split(":", 1)[1].strip()

            return result
        except Exception:
            # Keyword fallback
            text = f"{subject} {body}".lower()
            if any(w in text for w in ["price", "quote", "cost", "how much"]):
                return {"category": "price_inquiry", "summary": "Price inquiry", "urgency": "medium", "product": "unknown"}
            if any(w in text for w in ["order", "purchase", "buy"]):
                return {"category": "order_confirmation", "summary": "Order inquiry", "urgency": "medium", "product": "unknown"}
            if any(w in text for w in ["complaint", "damage", "wrong", "broken"]):
                return {"category": "complaint", "summary": "Complaint", "urgency": "high", "product": "unknown"}
            if any(w in text for w in ["discount", "cheap", "lower price"]):
                return {"category": "negotiation", "summary": "Negotiation", "urgency": "medium", "product": "unknown"}
            if any(w in text for w in ["seo", "marketing", "advertise", "rank"]):
                return {"category": "spam", "summary": "Spam", "urgency": "low", "product": "unknown"}
            return {"category": "general_inquiry", "summary": "General inquiry", "urgency": "low", "product": "unknown"}
