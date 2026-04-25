import xml.etree.ElementTree as ET

import httpx

import config

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
    # httpx.Client сохраняет Set-Cookie автоматически и отправляет их в следующих запросах
    body = (
        f"<tns:UserID>{config.AUTOPITER_USER_ID}</tns:UserID>"
        f"<tns:Password>{config.AUTOPITER_PASSWORD}</tns:Password>"
        "<tns:Save>true</tns:Save>"
    )
    _post(client, "Authorization", body)


def _find_catalog(client: httpx.Client, article: str) -> str | None:
    body = f"<tns:Number>{article}</tns:Number>"
    root = _post(client, "FindCatalog", body)

    best_id: str | None = None
    best_rating = -1

    for item in root.findall(f".//{_NS}SearchCatalogModel"):
        rating_el = item.find(f"{_NS}SalesRating")
        article_id_el = item.find(f"{_NS}ArticleId")

        if rating_el is None or article_id_el is None:
            continue

        rating = int(rating_el.text or "0")
        if rating > best_rating:
            best_rating = rating
            best_id = article_id_el.text

    return best_id


def _get_prices(client: httpx.Client, article_id: str) -> list[dict]:
    body = (
        f"<tns:ArticleId>{article_id}</tns:ArticleId>"
        "<tns:SearchCross>1</tns:SearchCross>"
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


def get_min_price(article: str) -> dict | None:
    with httpx.Client(timeout=60.0) as client:
        _authorize(client)

        article_id = _find_catalog(client, article)
        if article_id is None:
            return None

        offers = _get_prices(client, article_id)
        if not offers:
            return None

        return min(offers, key=lambda offer: offer["price"])
