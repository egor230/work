#!/bin/bash
# Подключение к FTP-приставке (Ugoos AM9) и открытие папки в Nemo.
#
# ВАЖНО: FTP-сервер приставки (192.168.0.7:7357) слушает ТОЛЬКО loopback —
# напрямую с ПК он недоступен. Работает через релей pc-ftp-relay.py, который:
#   - поднимает adb forward tcp:7357 -> tcp:7357,
#   - слушает 127.0.0.1:2121 и пробрасывает data-каналы.
# Поэтому подключаемся к 127.0.0.1:2121 (логин pc / пароль 1).

ADB=/usr/bin/adb
DEVICE="192.168.0.7:5555"
RELAY=/home/egor/.local/bin/pc-ftp-relay.py

HOST="127.0.0.1"
PORT="2121"
USER="pc"
PASS="1"
OPEN_SUB="device/Download"          # какой подкаталог приставки открыть в Nemo
MOUNT_URI="ftp://${USER}@${HOST}:${PORT}/"
GVL_PATH="/run/user/$(id -u)/gvfs/ftp:host=${HOST},port=${PORT},user=${USER}/${OPEN_SUB}"

die() { echo "ОШИБКА: $*" >&2; exit 1; }

# --- 1) ADB-подключение к приставке -------------------------------------
connect_adb() {
    "$ADB" connect "$DEVICE" >/dev/null 2>&1
    for i in $(seq 1 30); do
        [ "$("$ADB" -s "$DEVICE" get-state 2>/dev/null | tr -d '\r')" = "device" ] && return 0
        "$ADB" connect "$DEVICE" >/dev/null 2>&1
        sleep 1
    done
    return 1
}

# --- 2) Релей FTP (если не запущен) -------------------------------------
ensure_relay() {
    if pgrep -f 'pc-ftp-relay.py' >/dev/null 2>&1; then
        echo "Релей FTP уже запущен."
        return 0
    fi
    [ -x "$RELAY" ] || die "не найден релей: $RELAY"
    echo "Запускаю релей FTP..."
    nohup python3 "$RELAY" >/tmp/pc-ftp-relay.log 2>&1 &
    for i in $(seq 1 20); do
        printf 'USER pc\r\n' | timeout 2 nc -w 2 127.0.0.1 2121 2>/dev/null | grep -q "220" && return 0
        sleep 0.5
    done
    die "релей не поднялся (смотри /tmp/pc-ftp-relay.log)"
}

# --- 3) Монтирование / размонтирование ----------------------------------
do_mount() {
    connect_adb   || die "приставка ${DEVICE} не отвечает по ADB. Включите ADB на AM9."
    ensure_relay  || exit 1

    # чистое переподключение (GVfs может держать старый RIP-монт)
    gio mount -u "$MOUNT_URI" 2>/dev/null
    sleep 1

    # пароль подаём в stdin: GVfs не берёт его из URL
    printf '%s\n' "$PASS" | gio mount "$MOUNT_URI" >/dev/null 2>&1 || \
        die "не удалось смонтировать ${MOUNT_URI}"

    # ждём появления точки монтирования
    for i in $(seq 1 20); do
        [ -d "$GVL_PATH" ] && break
        sleep 0.5
    done
    [ -d "$GVL_PATH" ] || die "точка монтирования не появилась: $GVL_PATH"

    echo "Смонтировано: ${USER}@${HOST}:${PORT} -> ${GVL_PATH}"

    # открываем Nemo完全 в фоне (setsid), чтобы скрипт сразу вернулся
    if [ -d "$GVL_PATH" ]; then
        setsid nemo "$GVL_PATH" >/dev/null 2>&1 </dev/null &
    else
        setsid nemo "${MOUNT_URI}${OPEN_SUB}" >/dev/null 2>&1 </dev/null &
    fi
    disown 2>/dev/null || true
    echo "Готово: открыта папка приставки '${OPEN_SUB}'."
}

do_unmount() {
    gio mount -u "$MOUNT_URI" 2>/dev/null && echo "Отмонтировано: $MOUNT_URI" || echo "Не было смонтировано."
}

# --- 4) Команды ----------------------------------------------------------
case "$1" in
    unmount)
        do_unmount
        ;;
    relay-stop)
        pkill -f 'pc-ftp-relay.py' 2>/dev/null && echo "Релей остановлен." || echo "Релей не запущен."
        do_unmount
        ;;
    "")
        do_mount
        ;;
    *)
        echo "Использование: $0 [unmount|relay-stop]"
        echo "  (без аргументов) — подключить и открыть Nemo"
        echo "  unmount          — отмонтировать FTP"
        echo "  relay-stop       — остановить релей и отмонтировать"
        ;;
esac
