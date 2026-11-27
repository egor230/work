#!/bin/bash
# Тихий запуск WARP только для Telegram + CF Workers.
# В Compass: поднимает обход DPI для хендшейка, подключает WARP,
# убирает обход и при необходимости перезапускает TgWsProxy.
exec >>/home/egor/.config/warp-telegram-quiet.log 2>&1
echo "=== старт $(date) ==="

SERVICE="/home/egor/Downloads/zapret-discord-youtube-linux/service.sh"
TGWS="/mnt/807EB5FA7EB5E954/soft/Virtual_machine/linux must have/TgWsProxy_linux_amd64.AppImage"

# Ждём сеть
for i in $(seq 1 30); do
  ip route 2>/dev/null | grep -q default && break
  sleep 2
done

if warp-cli --accept-tos status 2>&1 | grep -q 'Connected'; then
  echo "WARP уже подключён"
else
  echo "Поднимаем обход для хендшейка"
  bash "$SERVICE" run -s general_alt12.bat -i any >/dev/null 2>&1 &
  sleep 8
  warp-cli --accept-tos connect 2>&1
  for i in $(seq 1 12); do
    sleep 5
    st=$(warp-cli --accept-tos status 2>&1 | tr '\n' ' ')
    echo "t=$((i*5))s: $st"
    echo "$st" | grep -q 'Connected' && break
  done

  echo "Убираем обход"
  bash "$SERVICE" kill >/dev/null 2>&1
  PIDS=$(pgrep -f '[s]ervice\.sh run' | tr '\n' ' ')
  [ -n "$PIDS" ] && kill $PIDS 2>/dev/null
  sleep 2
  SLEEPS=$(sudo -n pgrep -f '[s]leep infinity' 2>/dev/null | tr '\n' ' ')
  [ -n "$SLEEPS" ] && sudo -n kill -9 $SLEEPS 2>/dev/null
fi

# TgWsProxy, если не слушает
if ! ss -lntp 2>/dev/null | grep -q ':1443'; then
  echo "Перезапуск TgWsProxy"
  PIDS=$(pgrep -f '[T]gWsProxy_linux|[t]g-ws-proxy' | tr '\n' ' ')
  [ -n "$PIDS" ] && kill $PIDS 2>/dev/null
  sleep 3
  setsid nohup "$TGWS" >/home/egor/.config/tgws-autostart.log 2>&1 </dev/null &
fi

echo "Итог: $(warp-cli --accept-tos status 2>&1 | tr '\n' ' ')"
echo "=== конец $(date) ==="
