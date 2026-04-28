import smtplib
import ssl
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

import config

MAX_EMAIL_CHARS = 50_000


def _format_entry(entry: dict) -> str:
    our_article = entry["our_article"]
    our_price = entry["our_price"]
    competitors = entry["competitors"]

    lines = [f"Артикул: {our_article}  |  Наша цена: {our_price:.2f} руб."]

    if not competitors:
        lines.append("  (конкуренты не найдены)")
    else:
        for offer in competitors:
            marker = "  ⚠ ДЕШЕВЛЕ" if offer["is_cheaper"] else ""
            url = f"https://autopiter.ru/goods/{offer['article'].lower()}/{offer['catalog'].lower()}/id{offer['article_id']}"
            lines.append(f"  {offer['article']}  {offer['price']:.2f} руб.  ({offer['catalog']}){marker}")
            lines.append(f"  {url}")

    lines.append("- - -")
    return "\n".join(lines)


def _send_email(subject: str, body: str) -> None:
    message = MIMEMultipart()
    message["From"] = config.EMAIL_FROM
    message["To"] = config.EMAIL_TO
    message["Subject"] = subject
    message.attach(MIMEText(body, "plain", "utf-8"))

    context = ssl.create_default_context()
    with smtplib.SMTP_SSL("smtp.yandex.ru", 465, context=context) as server:
        server.login(config.EMAIL_FROM, config.EMAIL_PASSWORD)
        server.sendmail(config.EMAIL_FROM, config.EMAIL_TO, message.as_string())


def send_report(entries: list[dict]) -> None:
    sections = [_format_entry(e) for e in entries]

    parts: list[list[str]] = [[]]
    current_length = 0

    for section in sections:
        if current_length + len(section) > MAX_EMAIL_CHARS and parts[-1]:
            parts.append([])
            current_length = 0
        parts[-1].append(section)
        current_length += len(section)

    total_parts = len(parts)
    for i, part_sections in enumerate(parts, start=1):
        subject = f"Kerry мониторинг цен — {len(entries)} артикулов"
        if total_parts > 1:
            subject += f" (часть {i}/{total_parts})"
        body = "\n\n".join(part_sections)
        _send_email(subject, body)
