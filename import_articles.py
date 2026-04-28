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


def read_articles_from_xls(path: str, limit: int | None = None) -> dict[str, list[str]]:
    workbook = xlrd.open_workbook(path)
    sheet = workbook.sheet_by_index(0)

    result: dict[str, list[str]] = {}
    total_rows = min(sheet.nrows, limit) if limit else sheet.nrows

    for row_idx in range(1, total_rows):
        our_article = _clean_cell(sheet.cell(row_idx, 1))      # column B
        competitor_article = _clean_cell(sheet.cell(row_idx, 3))  # column D

        if not our_article or not competitor_article or our_article == competitor_article:
            continue

        if our_article not in result:
            result[our_article] = []
        if competitor_article not in result[our_article]:
            result[our_article].append(competitor_article)

    return result


def update_config_articles(articles: dict[str, list[str]]) -> None:
    content = CONFIG_FILE.read_text(encoding="utf-8")

    lines = []
    for our_article, competitors in articles.items():
        competitors_repr = ", ".join(f'"{c}"' for c in competitors)
        lines.append(f'    "{our_article}": [{competitors_repr}],')

    new_block = "ARTICLES = {\n" + "\n".join(lines) + "\n}"

    new_content = re.sub(
        r"ARTICLES\s*=\s*\{[^}]*\}",
        new_block,
        content,
        flags=re.DOTALL,
    )

    if new_content == content:
        print("Блок ARTICLES не найден в config.py")
        sys.exit(1)

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
    for our_article, competitors in articles.items():
        preview = ", ".join(competitors[:5])
        suffix = f"... (+{len(competitors) - 5})" if len(competitors) > 5 else ""
        print(f"  {our_article} → {preview}{suffix}")

    if args.dry_run:
        print("\n--dry-run: config.py не изменён")
    else:
        update_config_articles(articles)
        print("\nconfig.py обновлён")
