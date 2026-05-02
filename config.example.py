AUTOPITER_USER_ID = "YOUR_USER_ID"
AUTOPITER_PASSWORD = "YOUR_PASSWORD"

# Yandex требует пароль приложения если включена двухфакторная аутентификация.
# Создать: id.yandex.ru → Безопасность → Пароли приложений
EMAIL_FROM = "YOUR_BOT@yandex.com"
EMAIL_PASSWORD = "YOUR_APP_PASSWORD"
EMAIL_TO = "YOUR_RECIPIENT@gmail.com"

# Ящик, на который вы отправляете Excel с артикулами.
# Скрипт заберёт вложение через IMAP и запустит проверку цен.
# Пароль — тоже пароль приложения (не основной).
IMAP_EMAIL = "monitoring.kerry.bot@yandex.com"
IMAP_PASSWORD = "YOUR_BOT_APP_PASSWORD"

# Заполняется автоматически через: python import_articles.py articles.xls
ARTICLES = {
    "KR965-1": {
        "brand": "KERRY",
        "name": "Очиститель тормозов",
        "competitors": {
            "A9601": "AXIOM",
            "BC-810-RW": "Abro",
            "PAC105": "Pacific",
        },
    },
}
