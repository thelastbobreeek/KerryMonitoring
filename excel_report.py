from io import BytesIO

import openpyxl
from openpyxl.styles import Font


def build_report(rows: list[dict], all_brands: list[str]) -> bytes:
    """
    rows: list of {
        "brand": str,
        "article": str,
        "name": str,
        "our_price": float | None,
        "competitors": {brand: {"price": float, "article": str, "catalog": str, "article_id": str} | None}
    }
    all_brands: ordered list of all unique competitor brands (determines column order)
    """
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Цены"

    fixed_headers = ["Наш бренд", "Артикул", "Наименование", "Наша цена", "Лучшая цена конкурента"]
    comp_headers = [f"{brand}(конкурент{i + 1})" for i, brand in enumerate(all_brands)]
    ws.append(fixed_headers + comp_headers)

    for row_data in rows:
        our_price = row_data["our_price"]
        comp_results = row_data["competitors"]

        comp_prices = [v["price"] for v in comp_results.values() if v and v.get("price") is not None]
        best_comp_price = min(comp_prices) if comp_prices else None

        ws.append([
            row_data["brand"],
            row_data["article"],
            row_data["name"],
            our_price,
            best_comp_price,
        ])
        row_num = ws.max_row

        for col_idx, brand in enumerate(all_brands, start=6):
            comp = comp_results.get(brand)
            if not comp or comp.get("price") is None:
                continue

            price = comp["price"]
            article = comp["article"]
            catalog = comp.get("catalog", "")
            article_id = comp.get("article_id", "")

            cell = ws.cell(row=row_num, column=col_idx)
            cell.value = f"{price:.0f}({article})"

            if article_id and catalog and article:
                url = f"https://autopiter.ru/goods/{article.lower()}/{catalog.lower()}/id{article_id}"
                cell.hyperlink = url
                cell.font = Font(color="0563C1", underline="single")

    buf = BytesIO()
    wb.save(buf)
    return buf.getvalue()
