#!/usr/bin/env bash
# Полное удаление Task-Bot с VPS.
# Использование:
#   sudo bash uninstall.sh            # интерактивный режим (рекомендуется)
#   sudo bash uninstall.sh --yes      # без вопросов (кроме удаления бэкапов)
#   sudo bash uninstall.sh --keep-backups   # удалить всё, но оставить ./backups
#   sudo bash uninstall.sh --purge-all      # удалить всё, включая бэкапы и .env
#
# Скрипт НЕ трогает:
#   - Docker и другие контейнеры
#   - системные пакеты
#   - пользовательские данные за пределами /opt/task-bot
#   - SSH-конфиг, firewall

set -euo pipefail

PROJECT_DIR="/opt/task-bot"
DATA_DIR="${PROJECT_DIR}/data"
BACKUPS_DIR="${PROJECT_DIR}/backups"
LOG_FILE="/var/log/task-bot-uninstall.log"

ASSUME_YES=0
KEEP_BACKUPS=0
PURGE_ALL=0

for arg in "$@"; do
    case "$arg" in
        --yes|-y)         ASSUME_YES=1 ;;
        --keep-backups)   KEEP_BACKUPS=1 ;;
        --purge-all)      PURGE_ALL=1; ASSUME_YES=1 ;;
        -h|--help)
            grep '^#' "$0" | sed 's/^# \{0,1\}//'
            exit 0
            ;;
        *) echo "Неизвестный флаг: $arg"; exit 1 ;;
    esac
done

log()  { echo -e "[\e[1;34m*\e[0m] $*" | tee -a "$LOG_FILE"; }
ok()   { echo -e "[\e[1;32m+\e[0m] $*" | tee -a "$LOG_FILE"; }
warn() { echo -e "[\e[1;33m!\e[0m] $*" | tee -a "$LOG_FILE"; }
die()  { echo -e "[\e[1;31m-\e[0m] $*" | tee -a "$LOG_FILE" >&2; exit 1; }

confirm() {
    # confirm "текст" — возвращает 0, если да
    local prompt="$1"
    if [[ $ASSUME_YES -eq 1 ]]; then
        return 0
    fi
    read -r -p "$prompt [y/N]: " ans
    [[ "${ans:-N}" =~ ^[Yy]$ ]]
}

# --- 0. Проверки ---
[[ $EUID -eq 0 ]] || die "Запустите через sudo."

if [[ ! -d "$PROJECT_DIR" ]]; then
    warn "Каталог $PROJECT_DIR не найден. Возможно, бот уже удалён."
    exit 0
fi

log "Удаление Task-Bot из $PROJECT_DIR"
echo

# --- 1. Показать, что будет удалено ---
echo "Будет удалено:"
echo "  • Docker-контейнер: task-bot"
echo "  • Docker-образ:      task-bot:latest"
echo "  • Каталог проекта:   $PROJECT_DIR (кроме ./backups, если не --purge-all)"
echo

if [[ -d "$BACKUPS_DIR" ]]; then
    echo "Найдены бэкапы БД:"
    ls -lh "$BACKUPS_DIR" 2>/dev/null | tail -n +2 | sed 's/^/    /' || true
    echo "  → сохранятся в ${PROJECT_DIR}/backups"
    echo "    (удалить: запустите с флагом --purge-all)"
    echo
fi

if [[ -f "${PROJECT_DIR}/.env" ]]; then
    echo "  ⚠ Файл .env содержит BOT_TOKEN и будет удалён."
    echo "    Отзовите токен в @BotFather командой /revoke — этого достаточно."
    echo
fi

if ! confirm "Продолжить удаление?"; then
    echo "Отменено."
    exit 0
fi

cd "$PROJECT_DIR"

# --- 2. Остановить и удалить контейнер ---
if command -v docker >/dev/null 2>&1 && docker compose version >/dev/null 2>&1; then
    log "Остановка контейнера..."
    docker compose down --remove-orphans >>"$LOG_FILE" 2>&1 || true
    ok "Контейнер остановлен"
else
    warn "Docker Compose недоступен — пропускаем остановку контейнера"
fi

# --- 3. Удалить образ ---
if command -v docker >/dev/null 2>&1; then
    if docker image inspect task-bot:latest >/dev/null 2>&1; then
        if confirm "Удалить Docker-образ task-bot:latest?"; then
            docker rmi task-bot:latest >>"$LOG_FILE" 2>&1 || warn "Не удалось удалить образ (возможно, используется)"
            ok "Образ удалён"
        else
            warn "Образ оставлен"
        fi
    fi
fi

# --- 4. Сохранить бэкапы, если нужно ---
BACKUP_KEEP_PATH=""
if [[ -d "$BACKUPS_DIR" && ! $PURGE_ALL -eq 1 ]]; then
    BACKUP_KEEP_PATH="/root/task-bot-backups-$(date +%Y%m%d-%H%M%S)"
    log "Перенос бэкапов в $BACKUP_KEEP_PATH"
    mkdir -p "$BACKUP_KEEP_PATH"
    cp -a "$BACKUPS_DIR"/. "$BACKUP_KEEP_PATH"/ 2>/dev/null || true
    chmod 700 "$BACKUP_KEEP_PATH"
    ok "Бэкапы сохранены: $BACKUP_KEEP_PATH"
fi

# --- 5. Удалить каталог проекта ---
if confirm "Удалить каталог $PROJECT_DIR?"; then
    rm -rf "$PROJECT_DIR"
    ok "Каталог удалён"
else
    warn "Каталог оставлен. Ручное удаление: rm -rf $PROJECT_DIR"
    exit 0
fi

# --- 6. Удалить логи ---
if [[ -f "$LOG_FILE" ]]; then
    if confirm "Удалить лог установки/удаления $LOG_FILE?"; then
        rm -f "$LOG_FILE"
        ok "Лог удалён"
    fi
fi

# --- 7. Итог ---
echo
cat <<EOF
============================================================
 ✅ Task-Bot удалён с сервера

 Что сделано:
   • Контейнер остановлен и удалён
   • Каталог ${PROJECT_DIR} удалён
EOF

if [[ -n "$BACKUP_KEEP_PATH" ]]; then
    echo "   • Бэкапы БД перенесены в: $BACKUP_KEEP_PATH"
fi

cat <<EOF

 Что НЕ тронуто (специально):
   • Docker и его образы для других приложений
   • Системные пакеты
   • SSH-конфиг, firewall, cron

 Если вы создавали cron для бэкапов (0 3 * * * ... task-bot ...),
 удалите его вручную:
   crontab -e

 Не забудьте отозвать токен в @BotFather командой /revoke.
============================================================
EOF