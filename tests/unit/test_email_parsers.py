import mailbox
from email.message import EmailMessage
from pathlib import Path

from knowledgeqa.parsers.email_parser import parse_eml, parse_mbox


def make_message(
    subject: str = "付款条件",
    message_id: str = "<abc@example.com>",
) -> EmailMessage:
    message = EmailMessage()
    message["Subject"] = subject
    message["From"] = "a@example.com"
    message["To"] = "b@example.com"
    message["Date"] = "Thu, 16 Oct 2026 10:00:00 +0800"
    message["Message-ID"] = message_id
    message["References"] = "<thread@example.com>"
    message.set_content("验收后30日内付款。")
    return message


def test_parse_eml_extracts_headers_body_and_thread(tmp_path: Path) -> None:
    path = tmp_path / "mail.eml"
    path.write_bytes(make_message().as_bytes())

    emails = parse_eml(path)

    assert len(emails) == 1
    email = emails[0]
    assert email.message_id == "<abc@example.com>"
    assert email.thread_id == "<thread@example.com>"
    assert email.subject == "付款条件"
    assert "验收后30日内付款" in email.body_text
    assert email.from_addr == "a@example.com"
    assert email.to_addr == "b@example.com"


def test_parse_eml_records_attachment_names(tmp_path: Path) -> None:
    path = tmp_path / "mail.eml"
    message = make_message()
    message.add_attachment(
        b"attachment body",
        maintype="text",
        subtype="plain",
        filename="terms.txt",
    )
    path.write_bytes(message.as_bytes())

    email = parse_eml(path)[0]

    assert "附件: terms.txt" in email.body_text
    assert email.attachments[0].file_name == "terms.txt"


def test_parse_mbox_returns_one_email_per_message(tmp_path: Path) -> None:
    path = tmp_path / "archive.mbox"
    box = mailbox.mbox(path)
    try:
        box.add(make_message(message_id="<one@example.com>"))
        box.add(make_message(subject="第二封", message_id="<two@example.com>"))
        box.flush()
    finally:
        box.close()

    emails = parse_mbox(path)

    assert [email.message_id for email in emails] == [
        "<one@example.com>",
        "<two@example.com>",
    ]
    assert emails[1].subject == "第二封"
