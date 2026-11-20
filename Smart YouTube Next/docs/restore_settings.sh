#!/bin/bash
# Восстановить «обычные» настройки егор_щербанов из бэкапа на приставке.
# Работает и для приставки, и для эмулятора (указать ADB-адрес через first arg).
set -e
DEV="${1:-192.168.0.7:5555}"
adb connect "$DEV" >/dev/null 2>&1 || true
PKG=com.egor.youtubetv
OWNER=$(adb -s "$DEV" shell "su -c 'stat -c %u:%g /data/data/$PKG'" 2>/dev/null | tr -d '\r' || echo 10148:10148)

echo "Device: $DEV, owner: $OWNER"
adb -s "$DEV" shell am force-stop "$PKG"

echo "1) shared prefs from /sdcard/yt_prefs_backup …"
adb -s "$DEV" shell "su -c 'mkdir -p /data/data/$PKG/shared_prefs && cp -a /sdcard/yt_prefs_backup/shared_prefs/. /data/data/$PKG/shared_prefs/'"

echo "2) sidebar (74+ channels) …"
adb -s "$DEV" shell "su -c '[ -f /sdcard/sidebar_fixiki.txt ] && cp /sdcard/sidebar_fixiki.txt \"/data/data/$PKG/files/app_prefs/егор_щербанов_sidebar_data\" || true'"

echo "3) fix ownership …"
adb -s "$DEV" shell "su -c 'chown -R $OWNER /data/data/$PKG'"

echo "4) start app …"
adb -s "$DEV" shell "am start -n $PKG/com.liskovsoft.smartyoutubetv2.tv.ui.main.SplashActivity" >/dev/null 2>&1 || true
echo "Done."
