#!/bin/bash
# Меню включения/выключения автозапуска zapret.
# При запуске открывает НОВОЕ окно терминала и показывает меню:
#   1 - включить в автозапуск
#   2 - выключить из автозапуска

DESKTOP_FILE="$HOME/.config/autostart/zapret.desktop"

# --- Открыть новое окно терминала, если мы ещё не в дочернем меню ---
if [[ "${ZAPRET_MENU_CHILD:-0}" != "1" ]]; then
  export ZAPRET_MENU_CHILD=1
  SELF="$(readlink -f "$0")"

  if command -v gnome-terminal >/dev/null 2>&1; then
    exec gnome-terminal --title="Автозапуск zapret" -- bash -c 'exec bash "$1"' _ "$SELF"
  elif command -v xfce4-terminal >/dev/null 2>&1; then
    exec xfce4-terminal --title="Автозапуск zapret" -x bash -c 'exec bash "$1"' _ "$SELF"
  elif command -v xterm >/dev/null 2>&1; then
    exec xterm -T "Автозапуск zapret" -e bash "$SELF"
  else
    echo "Терминал не найден. Запустите вручную: bash \"$SELF\""
    exit 1
  fi
fi

# --- Работа с desktop-файлом автозапуска ---
get_status() {
  grep '^X-GNOME-Autostart-enabled=' "$DESKTOP_FILE" 2>/dev/null | head -1 | cut -d= -f2
}

set_status() {
  local value="$1"
  if grep -q '^X-GNOME-Autostart-enabled=' "$DESKTOP_FILE" 2>/dev/null; then
    sed -i "s/^X-GNOME-Autostart-enabled=.*/X-GNOME-Autostart-enabled=$value/" "$DESKTOP_FILE"
  else
    echo "X-GNOME-Autostart-enabled=$value" >> "$DESKTOP_FILE"
  fi
}

if [[ ! -f "$DESKTOP_FILE" ]]; then
  echo "ОШИБКА: не найден файл $DESKTOP_FILE"
  echo "Нажмите Enter для выхода..."
  read -r
  exit 1
fi

# --- Само меню ---
while true; do
  clear
  echo "=================================================="
  echo "          АВТОЗАПУСК ZAPRET"
  echo "=================================================="
  echo " Сейчас: $(get_status)   (true=включён, false=выключен)"
  echo
  echo "   1 - Включить в автозапуск"
  echo "   2 - Выключить из автозапуска"
  echo "   0 - Выход"
  echo "=================================================="
  read -r -p " Ваш выбор: " choice

  case "$choice" in
    1)
      set_status true
      echo
      echo " ГОТОВО: zapret включён в автозапуск."
      echo " При следующем входе в систему скрипт запустится сам."
      ;;
    2)
      set_status false
      echo
      echo " ГОТОВО: zapret выключен из автозапуска."
      echo " При следующем входе в систему он НЕ запустится."
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
