"""Send a partial report from saved progress without interrupting the main script."""
import json
import sys
from pathlib import Path

from excel_report import build_report
from notifier import send_report

PROGRESS_FILE = Path("progress_state.json")

if not PROGRESS_FILE.exists():
    print("Нет сохранённого прогресса — скрипт ещё не запускался или уже завершён")
    sys.exit(1)

with PROGRESS_FILE.open(encoding="utf-8") as f:
    p = json.load(f)

rows = p["rows"]
if not rows:
    print("Прогресс есть, но строк пока 0 — подождите первого завершённого артикула")
    sys.exit(1)

xlsx = build_report(rows, p["all_brands"])
send_report(xlsx)
print(f"Отправлено: {len(rows)} из {len(p['articles_keys'])} артикулов")
