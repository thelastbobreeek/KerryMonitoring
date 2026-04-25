import smtplib
import ssl
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

import config


def send_alert(our_article: str, our_price: float, cheaper_offers: list[dict]) -> None:
    subject = f"⚠️ Найдены более дешёвые товары для артикула {our_article}"

    lines = [f"Наша цена на артикул {our_article}: {our_price:.2f} руб.\n"]
    for offer in cheaper_offers:
        lines.append(f"Артикул: {offer['article']}")
        lines.append(f"Каталог: {offer['catalog']}")
        lines.append(f"Цена: {offer['price']:.2f} руб.")
        lines.append(f"Ссылка: https://autopiter.ru/search?search={offer['article']}")
        lines.append("---")

    body = "\n".join(lines)

    message = MIMEMultipart()
    message["From"] = config.EMAIL_FROM
    message["To"] = config.EMAIL_TO
    message["Subject"] = subject
    message.attach(MIMEText(body, "plain", "utf-8"))

    context = ssl.create_default_context()
    with smtplib.SMTP_SSL("smtp.gmail.com", 465, context=context) as server:
        server.login(config.EMAIL_FROM, config.EMAIL_PASSWORD)
        server.sendmail(config.EMAIL_FROM, config.EMAIL_TO, message.as_string())
