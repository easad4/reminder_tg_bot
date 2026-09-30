#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"

cmd="${1:-}"

dc() { docker compose "$@"; }

case "$cmd" in
    logs)      dc logs -f --tail=200 ;;
    restart)   dc restart ;;
    stop)      dc stop ;;
    start)     dc start ;;
    status)    dc ps ;;
    update)
        git pull --ff-only
        dc build
        dc up -d
        ;;
    backup)    bash backup.sh ;;
    restore)   bash restore.sh "$2" ;;
    "")
        while true; do
            cat <<'MENU'

========= Task-Bot управление =========
 1) Логи (tail -f)
 2) Перезапуск
 3) Остановить
 4) Запустить
 5) Обновить (git pull + rebuild)
 6) Резервная копия БД
 7) Восстановить БД
 8) Статус контейнера
 0) Выход
=======================================
MENU
            read -r -p "Выбор: " choice
            case "$choice" in
                1) dc logs -f --tail=200 ;;
                2) dc restart ;;
                3) dc stop ;;
                4) dc start ;;
                5) git pull --ff-only; dc build; dc up -d ;;
                6) bash backup.sh ;;
                7) read -r -p "Файл бэкапа: " f; bash restore.sh "$f" ;;
                8) dc ps ;;
                0) exit 0 ;;
                *) echo "Не понял." ;;
            esac
        done
        ;;
    *) echo "Команды: logs|restart|stop|start|status|update|backup|restore <file>"; exit 1 ;;
esac