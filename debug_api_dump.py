"""One-shot debug script — print raw XML from FindCatalog and GetPriceId for inspection."""
import xml.etree.ElementTree as ET

import httpx

import config
from autopiter import ENDPOINT, NS, _build_envelope, create_session

_NS = f"{{{NS}}}"


def _raw_post(client: httpx.Client, method: str, body: str) -> str:
    envelope = _build_envelope(method, body)
    headers = {
        "Content-Type": "text/xml; charset=utf-8",
        "SOAPAction": f"{NS}{method}",
    }
    r = client.post(ENDPOINT, content=envelope.encode("utf-8"), headers=headers)
    r.raise_for_status()
    return r.text


def _pretty(xml_text: str) -> str:
    root = ET.fromstring(xml_text)
    ET.indent(root, space="  ")
    return ET.tostring(root, encoding="unicode")


client = create_session()
first_article = next(iter(config.ARTICLES))
print(f"Используем артикул: {first_article}\n")

print("=" * 60)
print("FindCatalog response")
print("=" * 60)
xml1 = _raw_post(client, "FindCatalog", f"<tns:Number>{first_article}</tns:Number>")
print(_pretty(xml1))

root1 = ET.fromstring(xml1)
article_id = root1.findtext(f".//{_NS}ArticleId") or ""
print(f"\nПервый ArticleId: {article_id}")

if article_id:
    body2 = (
        f"<tns:ArticleId>{article_id}</tns:ArticleId>"
        "<tns:SearchCross>0</tns:SearchCross>"
        "<tns:MinSalesRating>0</tns:MinSalesRating>"
        "<tns:MinRealTimeInProc>0</tns:MinRealTimeInProc>"
    )
    print("\n" + "=" * 60)
    print("GetPriceId response (первые 3000 символов)")
    print("=" * 60)
    xml2 = _raw_post(client, "GetPriceId", body2)
    print(_pretty(xml2)[:3000])
else:
    print("ArticleId не найден — нечего запрашивать в GetPriceId")

client.close()
