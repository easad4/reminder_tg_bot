#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"

FILE="${1:-}"
[[ -n "$FILE" && -f "$FILE" ]] || { echo "Использование: bash restore.sh <backup.db>"; exit 1; }

read -r -p "Восстановить из $FILE? Текущая БД будет перезаписана [y/N]: " ans
[[ "${ans:-N}" =~ ^[Yy]$ ]] || { echo "Отменено."; exit 0; }

docker compose stop bot >/dev/null
cp -a ./data/tasks.db "./data/tasks.db.bak-$(date +%s)" 2>/dev/null || true
docker compose run --rm --no-deps -T bot python - "$FILE" <<'PY'
import sqlite3, sys, os
src = sys.argv[1]
dst_path = "/data/tasks.db"
if os.path.exists(dst_path):
    os.remove(dst_path)
dst = sqlite3.connect(dst_path)
with open(src, "r", encoding="utf-8") as f:
    dst.executescript(f.read())
dst.commit()
print("Восстановлено:", dst_path)
PY
docker compose start bot >/dev/null
echo "Готово."