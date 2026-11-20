#!/usr/bin/env bash
# Открывает НОВОЕ окно терминала и показывает в нём ВИДЕО с iPhone.
#
# ВАЖНО: приложение IP Camera Lite «залипает», если к его HTTP-потоку
# подключиться одновременно два клиента (например, мост ffmpeg и плеер ffplay).
# Поэтому по умолчанию скрипт запускает один мост и смотрит /dev/video2 —
# поток с телефона читается один раз, картинка идёт живая.
#
# Запуск:
#   ./Показать\ видео\ с\ iPhone.sh            -- авто (рекомендуется)
#   ./Показать\ видео\ с\ iPhone.sh --vcam     -- только /dev/video2
#   ./Показать\ видео\ с\ iPhone.sh --direct   -- напрямую HTTP (только если мост выключен)
#   ./Показать\ видео\ с\ iPhone.sh --fix      -- поворот/обрезка для режима Multi Cam
#   ./Показать\ видео\ с\ iPhone.sh --help
#
# Переменные: IPHONE_IP=192.168.1.50 (если IP телефона сменился).

set -euo pipefail

SELF="$(readlink -f "$0")"
BASE="$(cd "$(dirname "$SELF")/../.." && pwd)"
BRIDGE="$BASE/IP Camera Lite - iPhone webcam.sh"
IP="${IPHONE_IP:-192.168.0.34}"
PORT=8081
USER=admin
PASS=admin
TITLE="iPhone Camera — live video"

url() { echo "http://${USER}:${PASS}@${IP}:${PORT}/video"; }

usage() {
  cat <<'EOF'
Живое видео с iPhone в новом окне терминала

  ./Показать видео с iPhone.sh            авто: поднять мост и показать /dev/video2
  ./Показать видео с iPhone.sh --vcam     показать /dev/video2 (что видят Zoom/OBS)
  ./Показать видео с iPhone.sh --direct   напрямую HTTP-поток (мост должен быть выключен)
  ./Показать видео с iPhone.sh --fix      повернуть/обрезать поток режима Multi Cam
  ./Показать видео с iPhone.sh --help     справка

Управление: q — выход, пробел — пауза, f — полноэкранный режим.
Если IP телефона сменился: IPHONE_IP=192.168.1.50 ./Показать\ видео\ с\ iPhone.sh
EOF
}

check_url() {
  local code
  code=$(curl -s -o /dev/null -w '%{http_code}' -m 2 "$1" || true)
  [ "$code" = "200" ]
}

bridge_running() {
  pgrep -f "^ffmpeg .*${PORT}/video" >/dev/null 2>&1
}

find_phone() {
  check_url "$(url)" && return 0
  local iface net base cand hosts
  echo "Телефон ${IP} не отвечает, ищу в локальной сети..."
  iface=$(ip route | awk '/default/{print $5; exit}')
  net=$(ip -4 -o addr show dev "$iface" | awk '{print $4}')
  base=${net%.*}
  found=""
  if command -v nmap >/dev/null 2>&1; then
    hosts=$(nmap -p "$PORT" --open -oG - "${base}.0/24" 2>/dev/null | awk '/Host:/{print $2}')
    for cand in $hosts; do
      if check_url "http://${cand}:${PORT}/video"; then found="$cand"; break; fi
    done
  else
    found=$(seq 1 254 | xargs -P 32 -I{} bash -c '
      ip="'"${base}"'.{}"
      code=$(curl -s -o /dev/null -w "%{http_code}" -m 1 "http://$ip:'"$PORT"'/video" || true)
      [ "$code" = 200 ] && echo "$ip"
    ' 2>/dev/null | head -1)
  fi
  [ -n "$found" ] || return 1
  IP="$found"
  echo "Найден: $IP"
}

# ------------------------------------------------------------------ плеер внутри окна
if [ "${1:-}" = "--inner" ]; then
  mode="${2:-auto}"
  src=""
  vf=""
  restart_bridge=0

  echo "============================================================"
  echo " iPhone Camera — живое видео"
  echo "============================================================"

  if ! command -v ffplay >/dev/null 2>&1; then
    echo "ОШИБКА: ffplay не найден. Установите: sudo apt install ffmpeg"
    echo; read -r _ || true; exit 1
  fi

  case "$mode" in
    auto|vcam)
      if ! bridge_running; then
        echo "Запускаю мост в виртуальную камеру /dev/video2 ..."
        if [ -x "$BRIDGE" ]; then
          "$BRIDGE" start || true
        else
          echo "ОШИБКА: не найден $BRIDGE"; echo; read -r _ || true; exit 1
        fi
      fi
      sleep 1
      if [ ! -e /dev/video2 ] || ! bridge_running; then
        echo "ОШИБКА: мост не запустился. Проверьте: $BRIDGE start"
        echo; read -r _ || true; exit 1
      fi
      src=/dev/video2
      echo "Источник: $src (поток с телефона читается один раз — картинка живая)"
      ;;
    direct|fix)
      if bridge_running; then
        echo "Останавливаю мост: два подключения к iPhone замораживают кадр."
        "$BRIDGE" stop 2>/dev/null || pkill -f "^ffmpeg .*${PORT}/video" 2>/dev/null || true
        [ "$mode" = "fix" ] && restart_bridge=1
        sleep 1
      fi
      find_phone || {
        echo "Не найдено. Проверьте: IP Camera Lite открыта на телефоне,"
        echo "телефон и ПК в одной Wi-Fi сети, HTTP-сервер включён."
        echo; read -r _ || true; exit 1
      }
      src="$(url)"
      if [ "$mode" = "fix" ]; then
        vf="crop=475:233:907:165,transpose=2,scale=-2:720,pad=1280:720:(ow-iw)/2:(oh-ih)/2:black"
        echo "Источник: $src (режим --fix: поворот и обрезка Multi Cam)"
      else
        echo "Источник: $src (прямой поток)"
      fi
      ;;
    *)
      echo "Неизвестный режим: $mode"; echo; read -r _ || true; exit 1
      ;;
  esac

  echo "Управление: q — выход | пробел — пауза | f — полноэкранный режим"
  echo "------------------------------------------------------------"

  if [ -n "$vf" ]; then
    ffplay -hide_banner -loglevel info -fflags nobuffer -flags low_delay \
      -framedrop -an -window_title "$TITLE" -vf "$vf" "$src" || true
  else
    ffplay -hide_banner -loglevel info -fflags nobuffer -flags low_delay \
      -framedrop -an -window_title "$TITLE" "$src" || true
  fi

  if [ "$restart_bridge" = 1 ]; then
    echo "Возвращаю виртуальную камеру /dev/video2 ..."
    "$BRIDGE" start 2>/dev/null || true
  fi

  echo
  echo "Плеер закрыт. Нажмите Enter, чтобы выйти."
  read -r _ || true
  exit 0
fi

# ------------------------------------------------------------------ запуск нового окна
case "${1:-auto}" in
  --help|-h) usage; exit 0 ;;
  --vcam) mode=vcam ;;
  --direct) mode=direct ;;
  --fix) mode=fix ;;
  auto|"") mode=auto ;;
  *) echo "Неизвестный режим: $1" >&2; usage >&2; exit 1 ;;
esac

if [ -z "${DISPLAY:-}" ]; then
  echo "ОШИБКА: DISPLAY не задан — некуда открыть окно." >&2
  exit 1
fi

inner_cmd='"$SELF" --inner "$MODE"; echo; echo "--- Плеер завершён. Нажмите Enter для выхода ---"; read -r _ || true; exec bash'

if command -v gnome-terminal >/dev/null 2>&1; then
  gnome-terminal --title="$TITLE" -- env SELF="$SELF" MODE="$mode" bash -lc "$inner_cmd" &
elif command -v xterm >/dev/null 2>&1; then
  xterm -T "$TITLE" -e env SELF="$SELF" MODE="$mode" bash -lc "$inner_cmd" &
else
  echo "ОШИБКА: не найден gnome-terminal или xterm." >&2
  exit 1
fi

sleep 1
echo "Открыто новое окно «$TITLE». Видео появится в отдельном окне плеера."
echo "Если окно не появилось: '$SELF' --inner $mode"
