import smtplib
import ssl
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

import config

MAX_EMAIL_CHARS = 333_333


def _format_entry(entry: dict) -> str:
    our_article = entry["our_article"]
    our_price = entry["our_price"]
    cheaper_offers = entry["cheaper_offers"]

    lines = [f"{our_article}: (наша цена {our_price:.2f} руб.)"]
    for offer in cheaper_offers:
        url = f"https://autopiter.ru/goods/{offer['article'].lower()}/{offer['catalog'].lower()}/id{offer['article_id']}"
        lines.append(f"  {offer['article']}  {offer['price']:.2f} руб.  ({offer['catalog']})")
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


def send_alert(alerts: list[dict]) -> None:
    sections = [_format_entry(e) for e in alerts]
    full_text = "\n\n".join(sections)

    if len(full_text) <= MAX_EMAIL_CHARS:
        _send_email(f"⚠️ Найдены более дешёвые товары — {len(alerts)} артикулов", full_text)
        return

    import math
    num_parts = min(math.ceil(len(full_text) / MAX_EMAIL_CHARS), 3)
    per_part = math.ceil(len(sections) / num_parts)
    batches = [sections[i:i + per_part] for i in range(0, len(sections), per_part)]

    for i, batch in enumerate(batches, start=1):
        subject = f"⚠️ Найдены более дешёвые товары — {len(alerts)} артикулов (часть {i}/{len(batches)})"
        _send_email(subject, "\n\n".join(batch))
