#!/bin/bash
# Меню включения/выключения WARP в автозапуске.
# При запуске открывает НОВОЕ окно терминала и показывает меню:
#   1 - включить WARP в автозапуск
#   2 - выключить WARP из автозапуска

SYS_UNITS="warp-svc.service warp-weekly-update.timer"
USER_UNIT="warp-taskbar.service"

# --- Открыть новое окно терминала, если мы ещё не в дочернем меню ---
if [[ "${WARP_MENU_CHILD:-0}" != "1" ]]; then
  export WARP_MENU_CHILD=1
  SELF="$(readlink -f "$0")"

  if command -v gnome-terminal >/dev/null 2>&1; then
    exec gnome-terminal --title="Автозапуск WARP" -- bash -c 'exec bash "$1"' _ "$SELF"
  elif command -v xfce4-terminal >/dev/null 2>&1; then
    exec xfce4-terminal --title="Автозапуск WARP" -x bash -c 'exec bash "$1"' _ "$SELF"
  elif command -v xterm >/dev/null 2>&1; then
    exec xterm -T "Автозапуск WARP" -e bash "$SELF"
  else
    echo "Терминал не найден. Запустите вручную: bash \"$SELF\""
    exit 1
  fi
fi

# --- Текущее состояние ---
show_status() {
  local u state
  for u in $SYS_UNITS; do
    state=$(systemctl is-enabled "$u" 2>/dev/null)
    [[ -z "$state" ]] && state="unknown"
    printf '   %-28s %s\n' "$u" "$state"
  done
  state=$(systemctl --user is-enabled "$USER_UNIT" 2>/dev/null)
  [[ -z "$state" ]] && state="unknown"
  printf '   %-28s %s\n' "$USER_UNIT" "$state"
}

enable_warp() {
  sudo systemctl enable $SYS_UNITS
  systemctl --user enable "$USER_UNIT"
}

disable_warp() {
  sudo systemctl disable $SYS_UNITS
  systemctl --user disable "$USER_UNIT"
}

# --- Само меню ---
while true; do
  clear
  echo "=================================================="
  echo "          АВТОЗАПУСК CLOUDFLARE WARP"
  echo "=================================================="
  echo " Текущее состояние:"
  show_status
  echo
  echo "   1 - Включить WARP в автозапуск"
  echo "   2 - Выключить WARP из автозапуска"
  echo "   0 - Выход"
  echo "=================================================="
  echo " Изменения вступают в силу после перезагрузки."
  echo
  read -r -p " Ваш выбор: " choice

  case "$choice" in
    1)
      echo
      enable_warp
      echo
      echo " ГОТОВО: WARP включён в автозапуск."
      ;;
    2)
      echo
      disable_warp
      echo
      echo " ГОТОВО: WARP выключен из автозапуска."
      ;;
    0|q|Q)
      exit 0
      ;;
    *)
      echo
      echo " Неверный ввод. Нужно ввести 1, 2 или 0."
      ;;
  esac

  echo
  read -r -p " Нажмите Enter, чтобы продолжить..." dummy
done
