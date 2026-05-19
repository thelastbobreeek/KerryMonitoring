import json
import logging
import time
from datetime import datetime, timedelta
from pathlib import Path

import schedule

import config
from autopiter import RateLimitError, create_session, get_min_price
from email_receiver import fetch_latest_excel
from excel_report import build_report
from import_articles import read_articles_from_xls
from notifier import send_report

PRICES_FILE = Path("prices.json")
ARTICLES_FILE = Path("articles_received.xls")
PROGRESS_FILE = Path("progress_state.json")

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


def _save_progress(
    paused_until: str | None,
    article_idx: int,
    our_price_fetched: bool,
    our_result: dict | None,
    comp_idx: int,
    comp_best: dict,
    rows: list[dict],
    prices: dict,
    all_brands: list[str],
    articles_keys: list[str],
) -> None:
    state = {
        "paused_until": paused_until,
        "article_idx": article_idx,
        "our_price_fetched": our_price_fetched,
        "our_result": our_result,
        "comp_idx": comp_idx,
        "comp_best": comp_best,
        "rows": rows,
        "prices": prices,
        "all_brands": all_brands,
        "articles_keys": articles_keys,
    }
    with PROGRESS_FILE.open("w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)
    if paused_until:
        logger.info(
            "Лимит API. Прогресс сохранён: артикул %d/%d, конкурент %d. Возобновление: %s",
            article_idx, len(articles_keys), comp_idx, paused_until,
        )
    else:
        logger.info("Прогресс: %d/%d артикулов завершено", article_idx, len(articles_keys))


def _load_progress() -> dict | None:
    if not PROGRESS_FILE.exists():
        return None
    with PROGRESS_FILE.open(encoding="utf-8") as f:
        return json.load(f)


def _wait_until(iso_timestamp: str) -> None:
    remaining = (datetime.fromisoformat(iso_timestamp) - datetime.now()).total_seconds()
    if remaining > 0:
        logger.info("Лимит API. Ждём %.0f сек до %s", remaining, iso_timestamp)
        time.sleep(remaining)


def check_prices() -> None:
    logger.info("Начинаем проверку цен")
    articles = _load_articles()
    prices = load_prices()

    all_brands: list[str] = []
    seen_brands: set[str] = set()
    for article_data in articles.values():
        for comp_brand in article_data["competitors"].values():
            if comp_brand not in seen_brands:
                all_brands.append(comp_brand)
                seen_brands.add(comp_brand)

    articles_keys = list(articles.keys())

    progress = _load_progress()
    if progress:
        logger.info("Продолжаем с артикула %d из %d", progress["article_idx"], len(articles_keys))
        if progress.get("paused_until"):
            _wait_until(progress["paused_until"])
        rows: list[dict] = progress["rows"]
        prices = progress["prices"]
        all_brands = progress["all_brands"]
        articles_keys = progress["articles_keys"]
        i = progress["article_idx"]
        our_price_fetched: bool = progress["our_price_fetched"]
        our_result: dict | None = progress["our_result"]
        comp_start: int = progress["comp_idx"]
        comp_best: dict = progress["comp_best"]
    else:
        rows = []
        i = 0
        our_price_fetched = False
        our_result = None
        comp_start = 0
        comp_best = {brand: None for brand in all_brands}

    client = create_session()

    while i < len(articles_keys):
        our_article = articles_keys[i]
        article_data = articles[our_article]
        competitors_list = list(article_data["competitors"].items())

        if not our_price_fetched:
            logger.info("Проверяем артикул %d/%d: %s", i + 1, len(articles_keys), our_article)
            try:
                our_result = get_min_price(our_article, client)
            except RateLimitError:
                paused_until = (datetime.now() + timedelta(hours=24)).isoformat(timespec="seconds")
                _save_progress(paused_until, i, False, None, 0, comp_best, rows, prices, all_brands, articles_keys)
                client.close()
                _wait_until(paused_until)
                client = create_session()
                continue

            our_price_fetched = True
            if our_result:
                logger.info("Наша цена для %s: %.2f руб. (%s)", our_article, our_result["price"], our_result["catalog"])
                prices[our_article] = {
                    "price": our_result["price"],
                    "catalog": our_result["catalog"],
                    "checked_at": datetime.now().isoformat(timespec="seconds"),
                }
            else:
                logger.warning("Не удалось получить цену для %s", our_article)

        rate_limited = False
        j = comp_start
        while j < len(competitors_list):
            comp_article, comp_brand = competitors_list[j]
            logger.info("  Проверяем конкурента: %s (%s)", comp_article, comp_brand)

            try:
                result = get_min_price(comp_article, client)
            except RateLimitError:
                paused_until = (datetime.now() + timedelta(hours=24)).isoformat(timespec="seconds")
                _save_progress(paused_until, i, True, our_result, j, comp_best, rows, prices, all_brands, articles_keys)
                client.close()
                _wait_until(paused_until)
                client = create_session()
                comp_start = j
                rate_limited = True
                break

            if result is None:
                logger.warning("  Не удалось получить цену для %s", comp_article)
            else:
                logger.info("  Цена %s: %.2f руб. (%s)", comp_article, result["price"], result["catalog"])
                prices[comp_article] = {
                    "price": result["price"],
                    "catalog": result["catalog"],
                    "checked_at": datetime.now().isoformat(timespec="seconds"),
                }
                current_best = comp_best.get(comp_brand)
                if current_best is None or result["price"] < current_best["price"]:
                    comp_best[comp_brand] = result

            j += 1

        if rate_limited:
            continue

        rows.append({
            "brand": article_data["brand"],
            "article": our_article,
            "name": article_data["name"],
            "our_price": our_result["price"] if our_result else None,
            "competitors": comp_best,
        })
        i += 1
        our_price_fetched = False
        our_result = None
        comp_start = 0
        comp_best = {brand: None for brand in all_brands}
        _save_progress(None, i, False, None, 0, comp_best, rows, prices, all_brands, articles_keys)

    if PROGRESS_FILE.exists():
        PROGRESS_FILE.unlink()

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
