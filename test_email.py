"""Тест отправки письма."""
import smtplib
import ssl
from email.mime.text import MIMEText
import config

print(f"Подключаемся к smtp.yandex.ru:465")
print(f"От: {config.EMAIL_FROM}")
print(f"Кому: {config.EMAIL_TO}")
print(f"Пароль: {config.EMAIL_PASSWORD[:3]}***")

context = ssl.create_default_context()
try:
    with smtplib.SMTP_SSL("smtp.yandex.ru", 465, context=context) as server:
        server.set_debuglevel(1)
        print("\nЛогинимся...")
        server.login(config.EMAIL_FROM, config.EMAIL_PASSWORD)
        print("Логин успешен!")

        msg = MIMEText("Тест отправки письма из KerryMonitoring.", "plain", "utf-8")
        msg["From"] = config.EMAIL_FROM
        msg["To"] = config.EMAIL_TO
        msg["Subject"] = "KerryMonitoring — тест"

        refused = server.sendmail(config.EMAIL_FROM, config.EMAIL_TO, msg.as_string())
        if refused:
            print(f"Отклонено: {refused}")
        else:
            print("Письмо принято сервером!")
except smtplib.SMTPAuthenticationError as e:
    print(f"Ошибка авторизации: {e}")
except Exception as e:
    print(f"Ошибка: {type(e).__name__}: {e}")
