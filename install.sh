#!/usr/bin/env bash
# Установка Telegram-бота задач на чистый Ubuntu 22.04/24.04.
# Использование:
#   sudo bash install.sh
# Переменные:
#   REPO_URL  — URL git-репозитория с исходниками (обязательно)
#   BRANCH    — ветка (по умолчанию main)

set -euo pipefail

REPO_URL="${REPO_URL:-}"
BRANCH="${BRANCH:-main}"
PROJECT_DIR="/opt/task-bot"
SERVICE_DATA="${PROJECT_DIR}/data"
LOG_FILE="/var/log/task-bot-install.log"

log()  { echo -e "[\e[1;34m*\e[0m] $*" | tee -a "$LOG_FILE"; }
ok()   { echo -e "[\e[1;32m+\e[0m] $*" | tee -a "$LOG_FILE"; }
warn() { echo -e "[\e[1;33m!\e[0m] $*" | tee -a "$LOG_FILE"; }
die()  { echo -e "[\e[1;31m-\e[0m] $*" | tee -a "$LOG_FILE" >&2; exit 1; }

trap 'die "Установка прервана на строке $LINENO"' ERR

# --- 1. Проверки ---
[[ $EUID -eq 0 ]] || die "Запустите скрипт через sudo."
. /etc/os-release
[[ "${ID:-}" == "ubuntu" ]] || warn "Скрипт тестировался на Ubuntu, обнаружено: ${PRETTY_NAME:-unknown}"
log "ОС: ${PRETTY_NAME:-unknown}"

ARCH="$(uname -m)"
case "$ARCH" in
    x86_64|aarch64) ok "Архитектура $ARCH поддерживается" ;;
    *) die "Архитектура $ARCH не поддерживается" ;;
esac

if [[ -z "$REPO_URL" ]]; then
    echo
    read -r -p "Введите URL git-репозитория с исходниками бота: " REPO_URL
    [[ -n "$REPO_URL" ]] || die "URL репозитория не указан."
fi

# --- 2. Docker ---
if ! command -v docker >/dev/null 2>&1; then
    log "Установка Docker..."
    apt-get update -y >>"$LOG_FILE" 2>&1
    apt-get install -y ca-certificates curl gnupg git >>"$LOG_FILE" 2>&1
    install -m 0755 -d /etc/apt/keyrings
    curl -fsSL https://download.docker.com/linux/ubuntu/gpg \
        | gpg --dearmor -o /etc/apt/keyrings/docker.gpg
    chmod a+r /etc/apt/keyrings/docker.gpg
    echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] \
https://download.docker.com/linux/ubuntu $(. /etc/os-release && echo $VERSION_CODENAME) stable" \
        > /etc/apt/sources.list.d/docker.list
    apt-get update -y >>"$LOG_FILE" 2>&1
    apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin >>"$LOG_FILE" 2>&1
    systemctl enable --now docker >>"$LOG_FILE" 2>&1
    ok "Docker установлен"
else
    ok "Docker уже установлен: $(docker --version)"
fi

docker compose version >/dev/null 2>&1 || die "docker compose plugin недоступен."

# --- 3. Каталог проекта ---
mkdir -p "$PROJECT_DIR"
cd "$PROJECT_DIR"

# --- 4. Исходники ---
if [[ -d "$PROJECT_DIR/.git" ]]; then
    log "Обновление исходников..."
    git fetch --all >>"$LOG_FILE" 2>&1
    git checkout "$BRANCH" >>"$LOG_FILE" 2>&1
    git pull --ff-only >>"$LOG_FILE" 2>&1
else
    log "Клонирование $REPO_URL ($BRANCH)..."
    git clone --branch "$BRANCH" "$REPO_URL" "$PROJECT_DIR.tmp" >>"$LOG_FILE" 2>&1
    shopt -s dotglob
    mv "$PROJECT_DIR.tmp"/* "$PROJECT_DIR"/
    rmdir "$PROJECT_DIR.tmp"
    shopt -u dotglob
fi

# --- 5. .env и токен ---
if [[ -f "$PROJECT_DIR/.env" && -s "$PROJECT_DIR/.env" ]]; then
    ok ".env уже существует — оставляем как есть"
else
    echo
    read -r -s -p "Введите токен Telegram-бота (не отобразится): " BOT_TOKEN
    echo
    [[ -n "$BOT_TOKEN" ]] || die "Токен пуст."
    cat > "$PROJECT_DIR/.env" <<EOF
BOT_TOKEN=${BOT_TOKEN}
DB_PATH=/data/tasks.db
DEFAULT_TZ=Europe/Moscow
DEFAULT_DIGEST_TIME=09:00
LOG_LEVEL=INFO
EOF
    chmod 600 "$PROJECT_DIR/.env"
    ok ".env создан (права 600)"
fi

# --- 6. Постоянное хранилище SQLite ---
mkdir -p "$SERVICE_DATA"
chmod 700 "$SERVICE_DATA"
ok "Каталог данных: $SERVICE_DATA"

# --- 7. Сборка и запуск ---
log "Сборка контейнера (может занять минуту)..."
docker compose build >>"$LOG_FILE" 2>&1
log "Запуск..."
docker compose up -d >>"$LOG_FILE" 2>&1

# --- 8. Проверка ---
log "Проверка статуса контейнера (5 сек)..."
sleep 5
if docker compose ps --format json | grep -q '"State":"running"'; then
    ok "Контейнер запущен."
else
    warn "Контейнер не в состоянии running. Логи:"
    docker compose logs --tail=40 || true
    die "Установка завершилась с ошибкой."
fi

cat <<EOF

============================================================
 ✅ Установка завершена

 Проект:     $PROJECT_DIR
 Данные:     $SERVICE_DATA
 Логи:       cd $PROJECT_DIR && docker compose logs -f
 Управление: bash $PROJECT_DIR/manage.sh
 Перезапуск: cd $PROJECT_DIR && docker compose restart

 После перезагрузки VPS контейнер поднимется автоматически
 (restart: unless-stopped).
============================================================
EOF