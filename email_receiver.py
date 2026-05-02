import email
import imaplib
import logging
from email.header import decode_header
from pathlib import Path

import config

logger = logging.getLogger(__name__)

IMAP_HOST = "imap.yandex.ru"
IMAP_PORT = 993


def fetch_latest_excel() -> tuple[str, bytes] | None:
    """
    Connects to the bot inbox, finds the newest unread email with an Excel attachment.
    Returns (filename, bytes) or None if nothing new.
    Marks the email as read on success.
    """
    if not getattr(config, "IMAP_EMAIL", None) or not getattr(config, "IMAP_PASSWORD", None):
        logger.debug("IMAP не настроен — пропускаем проверку почты")
        return None

    try:
        with imaplib.IMAP4_SSL(IMAP_HOST, IMAP_PORT) as mail:
            mail.login(config.IMAP_EMAIL, config.IMAP_PASSWORD)
            mail.select("INBOX")

            _, message_ids = mail.search(None, "UNSEEN")
            if not message_ids[0]:
                logger.info("Новых писем нет")
                return None

            ids = message_ids[0].split()
            logger.info("Непрочитанных писем: %d", len(ids))

            for msg_id in reversed(ids):
                _, msg_data = mail.fetch(msg_id, "(RFC822)")
                msg = email.message_from_bytes(msg_data[0][1])

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
                        mail.store(msg_id, "+FLAGS", "\\Seen")
                        logger.info("Получен файл артикулов: %s", filename)
                        return filename, part.get_payload(decode=True)

        return None
    except Exception as exc:
        logger.warning("Ошибка при проверке почты: %s", exc)
        return None
