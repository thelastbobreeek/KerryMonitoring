import smtplib
import ssl
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

import config


def send_alert(alerts: list[dict]) -> None:
    subject = f"⚠️ Найдены более дешёвые товары ({len(alerts)} артикул{'а' if len(alerts) < 5 else 'ов'})"

    sections = []
    for alert in alerts:
        our_article = alert["our_article"]
        our_price = alert["our_price"]
        cheaper_offers = alert["cheaper_offers"]

        lines = [f"Наша цена на артикул {our_article}: {our_price:.2f} руб.\n"]
        for offer in cheaper_offers:
            lines.append(f"Артикул: {offer['article']}")
            lines.append(f"Каталог: {offer['catalog']}")
            lines.append(f"Цена: {offer['price']:.2f} руб.")
            url = f"https://autopiter.ru/goods/{offer['article'].lower()}/{offer['catalog'].lower()}/id{offer['article_id']}"
            lines.append(f"Ссылка: {url}")
            lines.append("---")

        sections.append("\n".join(lines))

    body = "\n\n- - -\n\n".join(sections)

    message = MIMEMultipart()
    message["From"] = config.EMAIL_FROM
    message["To"] = config.EMAIL_TO
    message["Subject"] = subject
    message.attach(MIMEText(body, "plain", "utf-8"))

    context = ssl.create_default_context()
    with smtplib.SMTP_SSL("smtp.yandex.ru", 465, context=context) as server:
        server.login(config.EMAIL_FROM, config.EMAIL_PASSWORD)
        server.sendmail(config.EMAIL_FROM, config.EMAIL_TO, message.as_string())
