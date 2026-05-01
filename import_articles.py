import re
import sys
from pathlib import Path

import xlrd

CONFIG_FILE = Path("config.py")


def _clean_cell(cell: xlrd.sheet.Cell) -> str:
    if cell.ctype == xlrd.XL_CELL_EMPTY:
        return ""
    if cell.ctype == xlrd.XL_CELL_NUMBER:
        value = cell.value
        return str(int(value)) if value == int(value) else str(value)
    return str(cell.value).strip()


def read_articles_from_xls(path: str, limit: int | None = None) -> dict[str, dict]:
    workbook = xlrd.open_workbook(path)
    sheet = workbook.sheet_by_index(0)

    result: dict[str, dict] = {}
    total_rows = min(sheet.nrows, limit) if limit else sheet.nrows

    for row_idx in range(1, total_rows):
        our_brand = _clean_cell(sheet.cell(row_idx, 0))         # column A
        our_article = _clean_cell(sheet.cell(row_idx, 1))       # column B
        comp_brand = _clean_cell(sheet.cell(row_idx, 2))        # column C
        competitor_article = _clean_cell(sheet.cell(row_idx, 3))  # column D
        name = _clean_cell(sheet.cell(row_idx, 4))              # column E

        if not our_article or not competitor_article or our_article == competitor_article:
            continue

        if our_article not in result:
            result[our_article] = {
                "brand": our_brand,
                "name": name,
                "competitors": {},
            }

        if competitor_article not in result[our_article]["competitors"]:
            result[our_article]["competitors"][competitor_article] = comp_brand

    return result


def _find_articles_block(content: str) -> tuple[int, int] | None:
    match = re.search(r"ARTICLES\s*=\s*\{", content)
    if not match:
        return None

    brace_start = match.end() - 1
    depth = 0
    for i, ch in enumerate(content[brace_start:]):
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return match.start(), brace_start + i + 1
    return None


def _format_articles(articles: dict) -> str:
    lines = ["ARTICLES = {"]
    for our_article, data in articles.items():
        lines.append(f"    {repr(our_article)}: {{")
        lines.append(f'        "brand": {repr(data["brand"])},')
        lines.append(f'        "name": {repr(data["name"])},')
        lines.append(f'        "competitors": {{')
        for comp_article, comp_brand in data["competitors"].items():
            lines.append(f"            {repr(comp_article)}: {repr(comp_brand)},")
        lines.append("        },")
        lines.append("    },")
    lines.append("}")
    return "\n".join(lines)


def update_config_articles(articles: dict) -> None:
    content = CONFIG_FILE.read_text(encoding="utf-8")

    block_range = _find_articles_block(content)
    if block_range is None:
        print("Блок ARTICLES не найден в config.py")
        sys.exit(1)

    start, end = block_range
    new_content = content[:start] + _format_articles(articles) + content[end:]
    CONFIG_FILE.write_text(new_content, encoding="utf-8")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("file", nargs="?", default="articles.xls")
    parser.add_argument("--limit", type=int, default=None, help="обработать только первые N строк")
    parser.add_argument("--dry-run", action="store_true", help="показать результат без записи в config.py")
    args = parser.parse_args()

    if not Path(args.file).exists():
        print(f"Файл не найден: {args.file}")
        sys.exit(1)

    articles = read_articles_from_xls(args.file, limit=args.limit)
    if not articles:
        print("Артикулы не найдены в файле")
        sys.exit(1)

    print(f"Найдено {len(articles)} артикулов:")
    for our_article, data in articles.items():
        comp_preview = ", ".join(list(data["competitors"].keys())[:5])
        suffix = f"... (+{len(data['competitors']) - 5})" if len(data["competitors"]) > 5 else ""
        print(f"  {our_article} ({data['brand']}) → {comp_preview}{suffix}")

    if args.dry_run:
        print("\n--dry-run: config.py не изменён")
    else:
        update_config_articles(articles)
        print("\nconfig.py обновлён")
