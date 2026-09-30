#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"

BACKUP_DIR="./backups"
mkdir -p "$BACKUP_DIR"
TS="$(date +%Y%m%d-%H%M%S)"
OUT="$BACKUP_DIR/tasks-$TS.db"

if [[ ! -f ./data/tasks.db ]]; then
    echo "Нет ./data/tasks.db"; exit 1
fi

# Используем sqlite3 внутри контейнера, чтобы получить консистентный дамп.
docker compose exec -T bot python - <<'PY' > "$OUT"
import sqlite3, sys
src = sqlite3.connect("/data/tasks.db")
dst = sqlite3.connect(":memory:")
src.backup(dst)
for line in dst.iterdump():
    sys.stdout.write(line + "\n")
PY

echo "Сохранено: $OUT ($(du -h "$OUT" | cut -f1))"

# Храним последние 10 бэкапов
ls -1t "$BACKUP_DIR"/tasks-*.db 2>/dev/null | tail -n +11 | xargs -r rm -f