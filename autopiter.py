import logging
import time
import xml.etree.ElementTree as ET

import httpx

import config

logger = logging.getLogger(__name__)

_RETRIES = 3
_RETRY_DELAY = 10
_REQUEST_DELAY = 2

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


def _find_catalog(client: httpx.Client, article: str) -> list[str]:
    body = f"<tns:Number>{article}</tns:Number>"
    root = _post(client, "FindCatalog", body)

    items: list[tuple[int, str]] = []
    for item in root.findall(f".//{_NS}SearchCatalogModel"):
        rating_el = item.find(f"{_NS}SalesRating")
        article_id_el = item.find(f"{_NS}ArticleId")

        if article_id_el is None:
            continue

        rating = int(rating_el.text or "0") if rating_el is not None else 0
        items.append((rating, article_id_el.text))

    items.sort(key=lambda x: x[0], reverse=True)
    return [article_id for _, article_id in items]


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

        if price_el is None or price_el.text is None:
            continue

        offers.append({
            "price": float(price_el.text),
            "catalog": catalog_el.text if catalog_el is not None else "",
            "article": number_el.text if number_el is not None else "",
            "detail_uid": uid_el.text if uid_el is not None else "",
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


def get_min_price(article: str, client: httpx.Client) -> dict | None:
    global _get_price_calls
    for attempt in range(1, _RETRIES + 1):
        try:
            article_ids = _find_catalog(client, article)
            if not article_ids:
                return None

            for article_id in article_ids:
                offers = _get_prices(client, article_id)
                _get_price_calls += 1
                time.sleep(_REQUEST_DELAY)
                if offers:
                    best = min(offers, key=lambda offer: offer["price"])
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
            return None
        except httpx.HTTPError as exc:
            logger.warning("Ошибка сети при запросе артикула %s: %s", article, exc)
            if attempt < _RETRIES:
                time.sleep(_RETRY_DELAY)

    logger.error("Не удалось получить цену для %s после %d попыток — пропускаем", article, _RETRIES)
    return None
