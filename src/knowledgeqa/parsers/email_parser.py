from __future__ import annotations

import hashlib
import mailbox
from email import policy
from email.message import Message
from email.parser import BytesParser
from email.utils import parsedate_to_datetime
from pathlib import Path

from bs4 import BeautifulSoup

from knowledgeqa.email_models import EmailAttachment, ParsedEmail


def _header(value: str | None) -> str:
    return (value or "").strip()


def _html_to_text(value: str) -> str:
    return BeautifulSoup(value, "html.parser").get_text("\n", strip=True)


def _extract_body(message: Message) -> str:
    body_part = message.get_body(preferencelist=("plain", "html")) if hasattr(
        message,
        "get_body",
    ) else None
    if body_part is not None:
        content = body_part.get_content()
        if body_part.get_content_type() == "text/html":
            return _html_to_text(content).strip()
        return content.strip()

    if message.is_multipart():
        for part in message.walk():
            if (
                part.get_content_type() == "text/plain"
                and part.get_content_disposition() != "attachment"
            ):
                return part.get_content().strip()
        return ""

    content = message.get_content()
    if message.get_content_type() == "text/html":
        return _html_to_text(content).strip()
    return content.strip()


def _extract_attachments(message: Message) -> list[EmailAttachment]:
    attachments: list[EmailAttachment] = []
    if not message.is_multipart():
        return attachments
    for part in message.walk():
        file_name = part.get_filename()
        if not file_name and part.get_content_disposition() != "attachment":
            continue
        payload = part.get_payload(decode=True) or b""
        attachments.append(
            EmailAttachment(
                file_name=file_name or "attachment",
                content_type=part.get_content_type(),
                payload=payload,
            )
        )
    return attachments


def _sent_at(value: str) -> str:
    if not value:
        return ""
    try:
        return parsedate_to_datetime(value).isoformat()
    except (TypeError, ValueError):
        return value


def _message_hash(
    subject: str,
    from_addr: str,
    to_addr: str,
    cc_addr: str,
    sent_at: str,
    body_text: str,
) -> str:
    normalized = "\n".join(
        [subject, from_addr, to_addr, cc_addr, sent_at, body_text]
    )
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def _to_parsed_email(message: Message, source_path: str) -> ParsedEmail:
    subject = _header(message.get("Subject"))
    from_addr = _header(message.get("From"))
    to_addr = _header(message.get("To"))
    cc_addr = _header(message.get("Cc"))
    sent_at = _sent_at(_header(message.get("Date")))
    body_text = _extract_body(message)
    attachments = _extract_attachments(message)
    if attachments:
        names = ", ".join(attachment.file_name for attachment in attachments)
        body_text = f"{body_text}\n\n附件: {names}".strip()

    message_id = _header(message.get("Message-ID")) or None
    references = _header(message.get("References"))
    thread_id = references.split()[0] if references.split() else None
    if thread_id is None:
        thread_id = _header(message.get("In-Reply-To")) or message_id

    return ParsedEmail(
        message_id=message_id,
        thread_id=thread_id,
        subject=subject,
        from_addr=from_addr,
        to_addr=to_addr,
        cc_addr=cc_addr,
        sent_at=sent_at,
        body_text=body_text,
        message_hash=_message_hash(
            subject,
            from_addr,
            to_addr,
            cc_addr,
            sent_at,
            body_text,
        ),
        source_path=source_path,
        attachments=attachments,
    )


def parse_eml(path: Path) -> list[ParsedEmail]:
    message = BytesParser(policy=policy.default).parsebytes(path.read_bytes())
    return [_to_parsed_email(message, path.name)]


def parse_mbox(path: Path) -> list[ParsedEmail]:
    box = mailbox.mbox(path)
    try:
        messages: list[ParsedEmail] = []
        for message in box:
            parsed = BytesParser(policy=policy.default).parsebytes(
                message.as_bytes()
            )
            messages.append(_to_parsed_email(parsed, path.name))
        return messages
    finally:
        box.close()


def parse_email_file(path: Path) -> list[ParsedEmail]:
    suffix = path.suffix.lower()
    if suffix == ".eml":
        return parse_eml(path)
    if suffix in {".mbox", ".mbx"}:
        return parse_mbox(path)
    raise ValueError(f"Unsupported email format: {suffix}")
