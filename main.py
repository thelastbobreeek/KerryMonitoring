import json
import logging
import time
from datetime import datetime
from pathlib import Path

import schedule

import config
from autopiter import create_session, get_min_price
from email_receiver import fetch_latest_excel
from excel_report import build_report
from import_articles import read_articles_from_xls
from notifier import send_report

PRICES_FILE = Path("prices.json")
ARTICLES_FILE = Path("articles_received.xls")

logger = logging.getLogger(__name__)


def load_prices() -> dict:
    if not PRICES_FILE.exists():
        return {}
    with PRICES_FILE.open(encoding="utf-8") as file:
        return json.load(file)


def save_prices(prices: dict) -> None:
    with PRICES_FILE.open("w", encoding="utf-8") as file:
        json.dump(prices, file, ensure_ascii=False, indent=2)


def _load_articles() -> dict:
    global ARTICLES_FILE

    result = fetch_latest_excel()
    if result is not None:
        filename, data = result
        ARTICLES_FILE = Path(f"articles_received{Path(filename).suffix.lower()}")
        ARTICLES_FILE.write_bytes(data)
        logger.info("Файл артикулов обновлён из почты: %s", filename)

    if ARTICLES_FILE.exists():
        logger.info("Загружаем артикулы из %s", ARTICLES_FILE)
        return read_articles_from_xls(str(ARTICLES_FILE))

    logger.warning("Файл артикулов не найден — используем config.ARTICLES")
    return config.ARTICLES


def check_prices() -> None:
    logger.info("Начинаем проверку цен")
    articles = _load_articles()
    prices = load_prices()
    client = create_session()

    all_brands: list[str] = []
    seen_brands: set[str] = set()
    for article_data in articles.values():
        for comp_brand in article_data["competitors"].values():
            if comp_brand not in seen_brands:
                all_brands.append(comp_brand)
                seen_brands.add(comp_brand)

    rows: list[dict] = []

    for our_article, article_data in articles.items():
        logger.info("Проверяем артикул: %s", our_article)

        our_result = get_min_price(our_article, client)
        if our_result is None:
            logger.warning("Не удалось получить цену для %s — пропускаем", our_article)
        else:
            our_price = our_result["price"]
            logger.info("Наша цена для %s: %.2f руб. (%s)", our_article, our_price, our_result["catalog"])
            prices[our_article] = {
                "price": our_price,
                "catalog": our_result["catalog"],
                "checked_at": datetime.now().isoformat(timespec="seconds"),
            }

        comp_best: dict[str, dict | None] = {brand: None for brand in all_brands}

        for comp_article, comp_brand in article_data["competitors"].items():
            logger.info("  Проверяем конкурента: %s (%s)", comp_article, comp_brand)
            result = get_min_price(comp_article, client)

            if result is None:
                logger.warning("  Не удалось получить цену для %s", comp_article)
                continue

            logger.info("  Цена %s: %.2f руб. (%s)", comp_article, result["price"], result["catalog"])
            prices[comp_article] = {
                "price": result["price"],
                "catalog": result["catalog"],
                "checked_at": datetime.now().isoformat(timespec="seconds"),
            }

            current_best = comp_best.get(comp_brand)
            if current_best is None or result["price"] < current_best["price"]:
                comp_best[comp_brand] = result

        rows.append({
            "brand": article_data["brand"],
            "article": our_article,
            "name": article_data["name"],
            "our_price": our_result["price"] if our_result else None,
            "competitors": comp_best,
        })

    logger.info("Формируем отчёт по %d артикулам", len(rows))
    xlsx_bytes = build_report(rows, all_brands)
    send_report(xlsx_bytes)
    logger.info("Отчёт отправлен")

    save_prices(prices)
    logger.info("Проверка завершена, данные сохранены в %s", PRICES_FILE)


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s  %(levelname)s  %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    check_prices()
    schedule.every(24).hours.do(check_prices)

    while True:
        schedule.run_pending()
        time.sleep(60)
