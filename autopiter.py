import logging
import re
import time
import xml.etree.ElementTree as ET

import httpx

import config

logger = logging.getLogger(__name__)


class RateLimitError(Exception):
    pass

_RETRIES = 3
_RETRY_DELAY = 10

_session_start: float | None = None
_get_price_calls = 0

ENDPOINT = "http://service.autopiter.ru/v2/price"
NS = "http://www.autopiter.ru/"
_NS = f"{{{NS}}}"


def _build_envelope(method: str, body: str) -> str:
    return (
        '<?xml version="1.0" encoding="utf-8"?>'
        '<soap:Envelope xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/"'
        f' xmlns:tns="{NS}">'
        "<soap:Body>"
        f"<tns:{method}>"
        f"{body}"
        f"</tns:{method}>"
        "</soap:Body>"
        "</soap:Envelope>"
    )


def _post(client: httpx.Client, method: str, body: str) -> ET.Element:
    envelope = _build_envelope(method, body)
    headers = {
        "Content-Type": "text/xml; charset=utf-8",
        "SOAPAction": f"{NS}{method}",
    }
    response = client.post(ENDPOINT, content=envelope.encode("utf-8"), headers=headers)
    response.raise_for_status()
    return ET.fromstring(response.text)


def _authorize(client: httpx.Client) -> None:
    body = (
        f"<tns:UserID>{config.AUTOPITER_USER_ID}</tns:UserID>"
        f"<tns:Password>{config.AUTOPITER_PASSWORD}</tns:Password>"
        "<tns:Save>true</tns:Save>"
    )
    root = _post(client, "Authorization", body)
    result_el = root.find(f".//{_NS}AuthorizationResult")
    if result_el is None or result_el.text != "true":
        raise RuntimeError("Авторизация на autopiter.ru не удалась — проверьте UserID и Password в config.py")


def _normalize_volume(v: str) -> str:
    v = v.strip().rstrip(".")
    v = re.sub(r"(\d)\s*(мл|л)", r"\1 \2", v, flags=re.IGNORECASE)
    return v.lower()


def _volume_matches(text: str, target: str) -> bool:
    return _normalize_volume(target) in _normalize_volume(text)


def _find_catalog(client: httpx.Client, article: str) -> list[tuple[str, str]]:
    body = f"<tns:Number>{article}</tns:Number>"
    root = _post(client, "FindCatalog", body)

    items: list[tuple[int, str, str]] = []
    for item in root.findall(f".//{_NS}SearchCatalogModel"):
        rating_el = item.find(f"{_NS}SalesRating")
        article_id_el = item.find(f"{_NS}ArticleId")
        name_el = item.find(f"{_NS}Name")

        if article_id_el is None:
            continue

        rating = int(rating_el.text or "0") if rating_el is not None else 0
        name = (name_el.text or "").strip() if name_el is not None else ""
        if name == "-":
            name = ""
        items.append((rating, article_id_el.text, name))

    items.sort(key=lambda x: x[0], reverse=True)
    return [(article_id, name) for _, article_id, name in items]


def _get_prices(client: httpx.Client, article_id: str) -> list[dict]:
    body = (
        f"<tns:ArticleId>{article_id}</tns:ArticleId>"
        "<tns:SearchCross>0</tns:SearchCross>"
        "<tns:MinSalesRating>0</tns:MinSalesRating>"
        "<tns:MinRealTimeInProc>0</tns:MinRealTimeInProc>"
    )
    root = _post(client, "GetPriceId", body)

    offers: list[dict] = []
    for item in root.findall(f".//{_NS}PriceSearchModel"):
        price_el = item.find(f"{_NS}SalePrice")
        catalog_el = item.find(f"{_NS}CatalogName")
        number_el = item.find(f"{_NS}Number")
        uid_el = item.find(f"{_NS}DetailUid")
        name_el = item.find(f"{_NS}Name")

        if price_el is None or price_el.text is None:
            continue

        offers.append({
            "price": float(price_el.text),
            "catalog": catalog_el.text if catalog_el is not None else "",
            "article": number_el.text if number_el is not None else "",
            "detail_uid": uid_el.text if uid_el is not None else "",
            "name": (name_el.text or "").strip() if name_el is not None else "",
        })

    return offers


def create_session() -> httpx.Client:
    global _session_start, _get_price_calls
    client = httpx.Client(timeout=120.0)
    _authorize(client)
    _session_start = time.monotonic()
    _get_price_calls = 0
    logger.info("Авторизация на autopiter.ru успешна")
    return client


def get_min_price(article: str, client: httpx.Client, target_volume: str | None = None) -> dict | None:
    global _get_price_calls
    for attempt in range(1, _RETRIES + 1):
        try:
            candidates = _find_catalog(client, article)
            if not candidates:
                return None

            if target_volume:
                filtered = [(aid, name) for aid, name in candidates if _volume_matches(name, target_volume)]
                if filtered:
                    candidates = filtered
                else:
                    logger.warning(
                        "Объём '%s' не найден в каталоге для %s — берём лучший по рейтингу",
                        target_volume, article,
                    )

            for article_id, _ in candidates:
                offers = _get_prices(client, article_id)
                _get_price_calls += 1
                if not offers:
                    continue

                if target_volume:
                    volume_offers = [o for o in offers if _volume_matches(o["name"], target_volume)]
                    if volume_offers:
                        offers = volume_offers

                best = min(offers, key=lambda o: o["price"])
                best["article_id"] = article_id
                return best

            return None
        except httpx.TimeoutException:
            logger.warning("Таймаут при запросе артикула %s (попытка %d/%d)", article, attempt, _RETRIES)
            if attempt < _RETRIES:
                time.sleep(_RETRY_DELAY)
        except httpx.HTTPStatusError as exc:
            elapsed = time.monotonic() - _session_start if _session_start else 0
            logger.warning(
                "HTTP %d при запросе артикула %s — %d успешных GetPriceId за %.0f сек от старта сессии",
                exc.response.status_code, article, _get_price_calls, elapsed,
            )
            if exc.response.status_code == 500:
                raise RateLimitError(article) from exc
            return None
        except httpx.HTTPError as exc:
            logger.warning("Ошибка сети при запросе артикула %s: %s", article, exc)
            if attempt < _RETRIES:
                time.sleep(_RETRY_DELAY)

    logger.error("Не удалось получить цену для %s после %d попыток — пропускаем", article, _RETRIES)
    return None
