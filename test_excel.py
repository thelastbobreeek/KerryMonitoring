import random
import sys
from pathlib import Path

from excel_report import build_report
from import_articles import read_articles_from_xls

xls_path = sys.argv[1] if len(sys.argv) > 1 else "articles.xls"

if not Path(xls_path).exists():
    print(f"Файл не найден: {xls_path}")
    sys.exit(1)

articles = read_articles_from_xls(xls_path)
print(f"Прочитано {len(articles)} артикулов")

all_brands: list[str] = []
seen_brands: set[str] = set()
for data in articles.values():
    for competitor in data["competitors"].values():
        brand = competitor["brand"] if isinstance(competitor, dict) else competitor
        if brand not in seen_brands:
            all_brands.append(brand)
            seen_brands.add(brand)

print(f"Уникальных брендов конкурентов: {len(all_brands)}")

rows = []
for our_article, data in articles.items():
    our_price = round(random.uniform(100, 1000), 2)

    comp_best: dict[str, dict | None] = {brand: None for brand in all_brands}
    for comp_article, competitor in data["competitors"].items():
        comp_brand = competitor["brand"] if isinstance(competitor, dict) else competitor
        comp_name = competitor.get("name", "") if isinstance(competitor, dict) else ""
        price = round(random.uniform(80, 1100), 2)
        current = comp_best.get(comp_brand)
        if current is None or price < current["price"]:
            comp_best[comp_brand] = {
                "price": price,
                "article": comp_article,
                "catalog": "",
                "article_id": "",  # no real ID in test — links skipped intentionally
                "input_name": comp_name,
            }

    rows.append({
        "brand": data["brand"],
        "article": our_article,
        "name": data["name"],
        "our_price": our_price,
        "competitors": comp_best,
    })

xlsx_bytes = build_report(rows, all_brands)

output_path = "test_output.xlsx"
with open(output_path, "wb") as f:
    f.write(xlsx_bytes)

print(f"Сохранено в {output_path}")
