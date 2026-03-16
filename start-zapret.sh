#!/bin/bash
gnome-terminal -- bash -c '
SCRIPT_DIR="/home/egor/Загрузки/zapret-discord-youtube-linux"
SERVICE_SCRIPT="$SCRIPT_DIR/service.sh"
CONF_INI="$SCRIPT_DIR/conf.ini"

WAIT_TIME=2
CURL_TIMEOUT=3

CUSTOM_DIR="$SCRIPT_DIR/custom-strategies"
if [[ -d "$CUSTOM_DIR" ]]; then
  for bat in "$SCRIPT_DIR"/zapret-latest/*.bat; do
    if [[ -f "$bat" ]]; then
      ln -sf "$bat" "$CUSTOM_DIR/$(basename "$bat")"
    fi
  done
fi

STRATEGY_FILES=($("$SERVICE_SCRIPT" strategy list | grep -E "\.bat$"))

if [[ "${#STRATEGY_FILES[@]}" -eq 0 ]]; then
  echo "Стратегии не найдены"
  echo "Запустите: $SERVICE_SCRIPT download-deps --default"
  echo "Нажмите Enter..."
  read -r
  exit 1
fi

check_youtube_main() {
  local tmp=$(mktemp)
  local code=$(curl -s --tlsv1.3 --connect-timeout "$CURL_TIMEOUT" --max-time "$CURL_TIMEOUT" -o "$tmp" -w "%{http_code}" "https://www.youtube.com" 2>/dev/null)
  grep -qi "youtube" "$tmp" && local has=1 || local has=0
  rm -f "$tmp"
  [[ "$code" =~ ^[23] ]] && [[ "$has" -eq 1 ]]
}

check_youtube_cdn() {
  local code=$(curl -s --tlsv1.3 --connect-timeout "$CURL_TIMEOUT" --max-time "$CURL_TIMEOUT" -o /dev/null -w "%{http_code}" "https://redirector.googlevideo.com" 2>/dev/null)
  [[ "$code" != "000" ]]
}

echo "Тестирование ${#STRATEGY_FILES[@]} стратегий..."

# Первое действие: остановить zapret (если запущен)
"$SERVICE_SCRIPT" kill >/dev/null 2>&1
sleep 1

WORKING=()
index=1

for strategy_path in "${STRATEGY_FILES[@]}"; do
  strategy_name=$(basename "$strategy_path")
  echo -n "Тестируем $strategy_name ... "

  # Запускаем стратегию в фоне
  "$SERVICE_SCRIPT" run -s "$strategy_name" -i any >/dev/null 2>&1 &
  sleep "$WAIT_TIME"

  # Проверяем доступность YouTube и CDN
  if check_youtube_main; then
    yt_ok=1
    check_youtube_cdn && cdn_ok=1 || cdn_ok=0
    echo "РАБОТАЕТ (CDN: $cdn_ok)"
    WORKING+=("$index:$strategy_name:$yt_ok:$cdn_ok")
  else
    yt_ok=0
    echo "НЕ РАБОТАЕТ"
  fi

  # Останавливаем стратегию перед следующей
  "$SERVICE_SCRIPT" kill >/dev/null 2>&1
  sleep 1

  ((index++))
done

echo ""
echo "Рабочих стратегий найдено: ${#WORKING[@]}"
echo ""

if [[ "${#WORKING[@]}" -eq 0 ]]; then
  echo "Подходящих стратегий нет."
  echo "Нажмите Enter..."
  read -r
  exit 0
fi

current_strategy=""

if [[ -f "$CONF_INI" ]]; then
  saved_num=$(cat "$CONF_INI" 2>/dev/null)
  if [[ "$saved_num" =~ ^[0-9]+$ ]]; then
    for entry in "${WORKING[@]}"; do
      IFS=":" read -r n name yt cdn <<< "$entry"
      if [[ "$n" == "$saved_num" ]]; then
        echo "Найдена сохранённая стратегия: $name"
        "$SERVICE_SCRIPT" kill >/dev/null 2>&1
        sleep 1
        echo "Запускаю..."
        "$SERVICE_SCRIPT" run -s "$name" -i any >/dev/null 2>&1 &
        current_strategy="$name"
        sleep 1
        echo "Стратегия запущена."
        echo ""
        break
      fi
    done
  fi
fi

while true; do
  echo "========================================================"
  echo "Рабочие стратегии:"
  echo "№   Стратегия                                 CDN"
  echo "--------------------------------------------------------"

  for entry in "${WORKING[@]}"; do
    IFS=":" read -r num name yt cdn <<< "$entry"
    if [[ "$cdn" -eq 1 ]]; then
      cdn_str="+"
    else
      cdn_str="-"
    fi
    printf "%2s  %-42s  %s\n" "$num" "$name" "$cdn_str"
  done

  echo "--------------------------------------------------------"
  if [[ -n "$current_strategy" ]]; then
    echo "Текущая стратегия: $current_strategy"
  else
    echo "Текущая стратегия: не запущена"
  fi
  echo ""
  echo "Команды:"
  echo "  <номер>  - запустить стратегию"
  echo "  s        - сохранить текущую в $CONF_INI"
  echo "  x        - остановить zapret"
  echo "  q        - выйти"
  echo ""

  read -p "> " input
  input="${input// /}"

  if [[ -z "$input" || "$input" =~ ^[qQ]$ ]]; then
    echo "Выход..."
    exit 0
  fi

  if [[ "$input" =~ ^[sS]$ ]]; then
    if [[ -n "$current_strategy" ]]; then
      for entry in "${WORKING[@]}"; do
        IFS=":" read -r n name yt cdn <<< "$entry"
        if [[ "$name" == "$current_strategy" ]]; then
          echo "$n" > "$CONF_INI"
          echo "$n" > "$CONF_INI" && echo "Стратегия $current_strategy (номер $n) сохранена в $CONF_INI"
          break
        fi
      done
    else
      echo "Нет запущенной стратегии для сохранения."
    fi
    echo ""
    continue
  fi

  if [[ "$input" =~ ^[xX]$ ]]; then
    "$SERVICE_SCRIPT" kill >/dev/null 2>&1
    current_strategy=""
    echo "zapret остановлен."
    echo ""
    continue
  fi

  if [[ "$input" =~ ^[0-9]+$ ]]; then
    num="$input"
    found=0
    for entry in "${WORKING[@]}"; do
      IFS=":" read -r n name yt cdn <<< "$entry"
      if [[ "$n" == "$num" ]]; then
        found=1
        echo "Выбрана стратегия: $name"
        "$SERVICE_SCRIPT" kill >/dev/null 2>&1
        sleep 1
        echo "Запускаю..."
        "$SERVICE_SCRIPT" run -s "$name" -i any >/dev/null 2>&1 &
        current_strategy="$name"
        sleep 1
        echo "Стратегия запущена."
        echo ""
        break
      fi
    done

    if [[ "$found" -eq 0 ]]; then
      echo "Стратегия с номером $num не найдена"
      echo ""
    fi
    continue
  fi

  echo "Неверный ввод."
  echo ""
done
echo "Нажмите Enter..."
read -r
exec bash'
