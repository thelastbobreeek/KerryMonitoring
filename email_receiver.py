import email
import imaplib
import logging
from email.header import decode_header
from pathlib import Path

import config

logger = logging.getLogger(__name__)

IMAP_HOST = "imap.yandex.ru"
IMAP_PORT = 993


def fetch_excel_attachments() -> list[tuple[str, bytes]]:
    """
    Connects to the bot inbox, collects all Excel attachments from all unread emails.
    Marks each email as read after extracting its attachments.
    Returns list of (filename, bytes), empty list if nothing new.
    """
    results: list[tuple[str, bytes]] = []
    try:
        with imaplib.IMAP4_SSL(IMAP_HOST, IMAP_PORT) as mail:
            mail.login(config.EMAIL_FROM, config.EMAIL_PASSWORD)
            mail.select("INBOX")

            _, message_ids = mail.search(None, "UNSEEN")
            if not message_ids[0]:
                logger.info("Новых писем нет")
                return []

            ids = message_ids[0].split()
            logger.info("Непрочитанных писем: %d", len(ids))

            for msg_id in ids:
                _, msg_data = mail.fetch(msg_id, "(RFC822)")
                msg = email.message_from_bytes(msg_data[0][1])

                found_in_email = False
                for part in msg.walk():
                    raw_filename = part.get_filename()
                    if not raw_filename:
                        continue

                    decoded_parts = decode_header(raw_filename)
                    filename = "".join(
                        chunk.decode(enc or "utf-8") if isinstance(chunk, bytes) else chunk
                        for chunk, enc in decoded_parts
                    )

                    if Path(filename).suffix.lower() in (".xls", ".xlsx"):
                        results.append((filename, part.get_payload(decode=True)))
                        found_in_email = True
                        logger.info("Получен файл артикулов: %s", filename)

                if found_in_email:
                    mail.store(msg_id, "+FLAGS", "\\Seen")

        return results
    except Exception as exc:
        logger.warning("Ошибка при проверке почты: %s", exc)
        return []
