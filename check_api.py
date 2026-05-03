"""Quick check: authorize → FindCatalog → GetPriceId for one article."""
import sys

from autopiter import _authorize, _find_catalog, _get_prices, create_session

ARTICLE = sys.argv[1] if len(sys.argv) > 1 else "A9601"

print(f"Проверяем артикул: {ARTICLE}")

try:
    client = create_session()
    print("✓ Авторизация успешна")

    article_ids = _find_catalog(client, ARTICLE)
    if not article_ids:
        print("✗ FindCatalog: артикул не найден")
        sys.exit(1)
    print(f"✓ FindCatalog: найдено {len(article_ids)} вариантов, первый ID = {article_ids[0]}")

    offers = _get_prices(client, article_ids[0])
    if offers:
        best = min(offers, key=lambda o: o["price"])
        print(f"✓ GetPriceId: {len(offers)} предложений, лучшая цена {best['price']:.2f} руб. ({best['catalog']})")
    else:
        print("✓ GetPriceId: ответ получен, предложений нет")

except Exception as exc:
    print(f"✗ Ошибка: {exc}")
    sys.exit(1)
