"""Check why specific articles return no price — shows catalog matches and volume filtering."""
import sys
import xml.etree.ElementTree as ET

import httpx

from autopiter import (
    ENDPOINT, NS, _build_envelope, _normalize_volume, _volume_matches,
    create_session,
)

_NS = f"{{{NS}}}"

ARTICLES_TO_CHECK = [
    ("A9628p", "650 мл."),
    ("A9628s", "650 мл."),
    ("DR9629", "650 мл."),
    ("DR9630", "650 мл."),
    ("DR9637", "650 мл."),
    ("A9622p", "650 мл."),
    ("A9622s", "650 мл."),
]


def _raw_post(client: httpx.Client, method: str, body: str) -> str:
    envelope = _build_envelope(method, body)
    headers = {
        "Content-Type": "text/xml; charset=utf-8",
        "SOAPAction": f"{NS}{method}",
    }
    r = client.post(ENDPOINT, content=envelope.encode("utf-8"), headers=headers)
    r.raise_for_status()
    return r.text


def check_article(client: httpx.Client, article: str, volume: str) -> None:
    print(f"\n{'=' * 60}")
    print(f"Артикул: {article}  |  Объём: {volume}")
    print("=" * 60)

    xml = _raw_post(client, "FindCatalog", f"<tns:Number>{article}</tns:Number>")
    root = ET.fromstring(xml)
    models = root.findall(f".//{_NS}SearchCatalogModel")

    if not models:
        print("  FindCatalog: нет результатов — артикул не найден в каталоге")
        return

    print(f"  FindCatalog: {len(models)} результатов")
    matched = []
    for m in models:
        aid = (m.findtext(f"{_NS}ArticleId") or "").strip()
        name = (m.findtext(f"{_NS}Name") or "").strip()
        rating = (m.findtext(f"{_NS}SalesRating") or "0").strip()
        catalog = (m.findtext(f"{_NS}CatalogName") or "").strip()
        hits = _volume_matches(name, volume)
        marker = "✓" if hits else " "
        print(f"  [{marker}] rating={rating:>3}  catalog={catalog:<20}  name={name}")
        if hits:
            matched.append(aid)

    if not matched:
        print(f"  → Ни одна запись не содержит '{volume}' — цена не возвращается")
    else:
        print(f"  → {len(matched)} совпадений по объёму, ArticleId: {matched}")


client = create_session()
articles = sys.argv[1:] if len(sys.argv) > 1 else None

if articles:
    for art in articles:
        check_article(client, art, "650 мл.")
else:
    for article, volume in ARTICLES_TO_CHECK:
        check_article(client, article, volume)

client.close()
