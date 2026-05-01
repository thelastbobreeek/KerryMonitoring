import smtplib
import ssl
from datetime import date
from email import encoders
from email.mime.base import MIMEBase
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

import config


def send_report(xlsx_bytes: bytes) -> None:
    today = date.today().strftime("%Y-%m-%d")
    subject = f"Отчёт по ценам конкурентов — {today}"

    message = MIMEMultipart()
    message["From"] = config.EMAIL_FROM
    message["To"] = config.EMAIL_TO
    message["Subject"] = subject

    message.attach(MIMEText("Отчёт по ценам конкурентов во вложении.", "plain", "utf-8"))

    attachment = MIMEBase("application", "vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    attachment.set_payload(xlsx_bytes)
    encoders.encode_base64(attachment)
    attachment.add_header("Content-Disposition", f'attachment; filename="prices_{today}.xlsx"')
    message.attach(attachment)

    context = ssl.create_default_context()
    with smtplib.SMTP_SSL("smtp.yandex.ru", 465, context=context) as server:
        server.login(config.EMAIL_FROM, config.EMAIL_PASSWORD)
        server.sendmail(config.EMAIL_FROM, config.EMAIL_TO, message.as_string())
