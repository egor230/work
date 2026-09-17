#!/bin/bash
# Подключение к FTP-приставке (Ugoos AM9) и открытие папки в Nemo.
# Монтирует корневой FTP как «admin на 192.168.0.7:7357» через GVfs и открывает
# Nemo в каталоге device/Download приставки (там лежат APK).

HOST="192.168.0.7"
PORT="7357"
USER="admin"
PASS="1"
OPEN_SUB="device/Download"          # какой подкаталог приставки открыть в Nemo
MOUNT_URI="ftp://${USER}@${HOST}:${PORT}/"
GVL_PATH="/run/user/$(id -u)/gvfs/ftp:host=${HOST},port=${PORT},user=${USER}/${OPEN_SUB}"

# 1) Проверка, что приставка отвечает по FTP-порту
if ! printf 'USER anon\r\n' | nc -w 3 "$HOST" "$PORT" 2>/dev/null | grep -q "220"; then
    echo "ОШИБКА: FTP-сервер приставки ${HOST}:${PORT} не отвечает."
    echo "Проверьте, что AM9 включена и в локальной сети. (логин/пароль: ${USER} / ${PASS})"
    exit 1
fi

# 2) Если уже смонтирован — отмонтировать, чтобы гарантировать чистое подключение
gio mount -u "$MOUNT_URI" 2>/dev/null

# 3) Монтирование. GVfs интерактивно запрашивает пароль — подаём его в stdin.
#    Для не-anonymous логина пароль НЕ берётся из URL, только из stdin.
if ! printf '%s\n' "$PASS" | gio mount "$MOUNT_URI" ; then
    echo "ОШИБКА: не удалось смонтировать ${MOUNT_URI} (пароль «${PASS}» не принят?)."
    exit 1
fi
echo "Смонтировано: admin на ${HOST}:${PORT}"
echo "Точка монтирования: /run/user/$(id -u)/gvfs/ftp:host=${HOST},port=${PORT},user=${USER}/"

# 4) Даём GVfs секунду подтянуть список, чтобы ls работал
sleep 1

# 5) Открыть в Nemo. Пробуем путь через gio (FUSE-точка) и через URL;
#    FUSE-точка более надёжна для Nemo.
opened=0
if [ -d "$GVL_PATH" ]; then
    nemo "$GVL_PATH" 2>/dev/null && opened=1
fi
if [ "$opened" -eq 0 ]; then
    nemo "$MOUNT_URI${OPEN_SUB}" 2>/dev/null && opened=1
fi
if [ "$opened" -eq 0 ]; then
    # Fallback: просто открыть корень — папку можно пройти рукой
    nemo "$MOUNT_URI" 2>/dev/null
fi

echo "Готово: открыт каталог приставки '${OPEN_SUB}' (там лежат APK, например SmartTube_stable_32.46_arm64-v8a.apk)."
echo
echo "Отмонтировать, когда не нужно:  gio mount -u \"$MOUNT_URI\""
echo "Переподключить:                 ./imenu.sh"
echo "Только отмонтировать:           ./imenu.sh unmount"

# Команды на будущее
if [ "$1" = "unmount" ]; then
    gio mount -u "$MOUNT_URI"
    echo "Отмонтировано."
fi
