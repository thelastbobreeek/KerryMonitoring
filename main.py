import json
import logging
import time
from datetime import datetime
from pathlib import Path

import schedule

import config
from autopiter import get_min_price
from notifier import send_alert

PRICES_FILE = Path("prices.json")

logger = logging.getLogger(__name__)


def load_prices() -> dict:
    if not PRICES_FILE.exists():
        return {}
    with PRICES_FILE.open(encoding="utf-8") as file:
        return json.load(file)


def save_prices(prices: dict) -> None:
    with PRICES_FILE.open("w", encoding="utf-8") as file:
        json.dump(prices, file, ensure_ascii=False, indent=2)


def check_prices() -> None:
    logger.info("Начинаем проверку цен")
    prices = load_prices()

    for our_article, competitor_articles in config.ARTICLES.items():
        logger.info("Проверяем артикул: %s", our_article)

        our_result = get_min_price(our_article, search_cross=0)
        if our_result is None:
            logger.warning("Не удалось получить цену для нашего артикула %s — пропускаем", our_article)
            continue

        our_price = our_result["price"]
        logger.info("Наша цена для %s: %.2f руб. (%s)", our_article, our_price, our_result["catalog"])

        prices[our_article] = {
            "price": our_price,
            "catalog": our_result["catalog"],
            "checked_at": datetime.now().isoformat(timespec="seconds"),
        }

        cheaper_offers: list[dict] = []

        for competitor_article in competitor_articles:
            logger.info("  Проверяем конкурента: %s", competitor_article)
            competitor_result = get_min_price(competitor_article)

            if competitor_result is None:
                logger.warning("  Не удалось получить цену для артикула конкурента %s — пропускаем", competitor_article)
                continue

            competitor_price = competitor_result["price"]
            logger.info("  Цена %s: %.2f руб. (%s)", competitor_article, competitor_price, competitor_result["catalog"])

            prices[competitor_article] = {
                "price": competitor_price,
                "catalog": competitor_result["catalog"],
                "checked_at": datetime.now().isoformat(timespec="seconds"),
            }

            if competitor_price < our_price:
                cheaper_offers.append(competitor_result)

        if cheaper_offers:
            logger.info("Найдено %d более дешёвых предложений для %s — отправляем алерт", len(cheaper_offers), our_article)
            send_alert(our_article, our_price, cheaper_offers)
            logger.info("Алерт отправлен")
        else:
            logger.info("Более дешёвых предложений для %s не найдено", our_article)

    save_prices(prices)
    logger.info("Проверка завершена, данные сохранены в %s", PRICES_FILE)


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s  %(levelname)s  %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    check_prices()
    schedule.every(1).hours.do(check_prices)

    while True:
        schedule.run_pending()
        time.sleep(60)
