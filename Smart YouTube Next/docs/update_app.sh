#!/bin/bash
# Обновление нашего приложения на_AM9 без потери аккаунта/настроек.
#Usage: update_app.sh /path/to/app.apk
set -e
PKG=com.egor.youtubetv
APK="$1"
[ -f "$APK" ] || { echo "Usage: $0 APK"; exit 1; }
BACKUP=/tmp/opencode/appdata_backup
mkdir -p "$BACKUP"

echo "1) Backup app data (account, prefs, sidebar)…"
adb shell "su -c 'tar czf /sdcard/appdata_backup.tgz -C /data/data/$PKG .'"
adb pull /sdcard/appdata_backup.tgz "$BACKUP/appdata.tgz" >/dev/null

echo "2) Install $APK …"
adb shell am force-stop "$PKG"
adb install -r "$APK"

echo "3) Restore app data…"
OWNER=$(adb shell "su -c 'stat -c %u:%g /data/data/$PKG'" | tr -d '\r')
adb push "$BACKUP/appdata.tgz" /sdcard/appdata_backup.tgz >/dev/null
adb shell "su -c 'tar xzf /sdcard/appdata_backup.tgz -C /data/data/$PKG && chown -R $OWNER /data/data/$PKG'"

echo "Done. Account and settings preserved."
