#!/bin/bash
gnome-terminal -- bash -c '
# Zapret installer for Linux Mint (без цветов, исправленный)

REPO_DIR="/home/egor/Загрузки/zapret-discord-youtube-linux"
NFQWS_DIR="$REPO_DIR/nfq"
ZAPRET_REPO="https://github.com/bol-van/zapret"
NFQWS_RELEASE="https://github.com/bol-van/zapret/releases/download/v70.5/zapret-v70.5.tar.gz"

echo "[*] Zapret Installer for Linux Mint"
echo "[*] Требуются права sudo..."

# Проверка sudo
if ! sudo -n true 2>/dev/null; then
    echo "[!] Введите пароль sudo:"
    sudo -v
fi

# ============================================
# 1. Установка зависимостей
# ============================================
echo "[1/5] Установка зависимостей..."
sudo apt-get update -qq
sudo apt-get install -y curl wget git nftables iptables-persistent \
    libnetfilter-queue1 libnetfilter-conntrack3 libcap2-bin \
    ipset dnsmasq python3

# ============================================
# 2. Создание директорий
# ============================================
echo "[2/5] Создание структуры директорий..."
mkdir -p "$NFQWS_DIR" "$REPO_DIR/lists" "$REPO_DIR/bin"

# ============================================
# 3. Скачивание nfqws бинарника
# ============================================
echo "[3/5] Скачивание zapret (nfqws)..."

cd "$REPO_DIR"

ARCH=$(uname -m)
case $ARCH in
    x86_64) BIN_ARCH="x86_64" ;;
    aarch64) BIN_ARCH="aarch64" ;;
    armv7l) BIN_ARCH="arm" ;;
    *) echo "[!] Неизвестная архитектура: $ARCH"; exit 1 ;;
esac

echo "[*] Архитектура: $BIN_ARCH"

copy_binary() {
    local src="$1"
    if [ -f "$src" ]; then
        cp "$src" "$REPO_DIR/bin/nfqws"
        echo "[+] nfqws скопирован"
        return 0
    fi
    return 1
}

if wget -q --show-progress "$NFQWS_RELEASE" -O zapret.tar.gz; then
    echo "[+] Релиз скачан, распаковка..."
    tar -xzf zapret.tar.gz
    if copy_binary "zapret-v70.5/binaries/$BIN_ARCH/nfqws"; then
        rm -rf zapret-v70.5
    else
        echo "[!] Бинарник не найден, пробуем собрать из исходников..."
        rm -rf zapret-v70.5
        git clone --depth=1 "$ZAPRET_REPO" zapret-git
        cd zapret-git
        make -C nfq
        copy_binary "nfq/nfqws" || cp nfq/nfqws "$REPO_DIR/bin/" 2>/dev/null
        cd ..
        rm -rf zapret-git
    fi
    rm -f zapret.tar.gz
else
    echo "[!] Не удалось скачать релиз, клонируем репозиторий..."
    git clone --depth=1 "$ZAPRET_REPO" zapret-git
    cd zapret-git
    if copy_binary "binaries/$BIN_ARCH/nfqws"; then
        :
    else
        make -C nfq
        copy_binary "nfq/nfqws" || cp nfq/nfqws "$REPO_DIR/bin/" 2>/dev/null
    fi
    cd ..
    rm -rf zapret-git
fi

if [ ! -f "$REPO_DIR/bin/nfqws" ]; then
    echo "[!] Ошибка: nfqws не найден"
    exit 1
fi

chmod +x "$REPO_DIR/bin/nfqws"
sudo setcap cap_net_admin,cap_net_raw+eip "$REPO_DIR/bin/nfqws" 2>/dev/null || true

# ============================================
# 4. Создание списков (lists)
# ============================================
echo "[4/5] Создание списков хостов..."

cat > "$REPO_DIR/lists/list-general.txt" << 'EOF'
googlevideo.com
youtube.com
youtu.be
ytimg.com
googleapis.com
gstatic.com
play.google.com
discord.com
discord.gg
discord.media
discordapp.com
discordapp.net
discordstatus.com
cloudflare-ech.com
EOF

cat > "$REPO_DIR/lists/list-google.txt" << 'EOF'
googlevideo.com
youtube.com
youtu.be
ytimg.com
googleapis.com
gstatic.com
play.google.com
google.com
EOF

cat > "$REPO_DIR/lists/list-exclude.txt" << 'EOF'
# Локальные адреса
localhost
127.0.0.1
::1
# Служебные
ntp.org
pool.ntp.org
EOF

cat > "$REPO_DIR/lists/ipset-all.txt" << 'EOF'
173.194.0.0/16
74.125.0.0/16
142.250.0.0/15
172.217.0.0/16
216.58.192.0/19
108.177.0.0/17
64.233.160.0/19
66.102.0.0/20
66.249.64.0/19
72.14.192.0/18
EOF

cat > "$REPO_DIR/lists/ipset-exclude.txt" << 'EOF'
127.0.0.0/8
10.0.0.0/8
172.16.0.0/12
192.168.0.0/16
EOF

# ============================================
# 5. Создание фейковых пакетов
# ============================================
echo "[5/5] Создание фейковых пакетов..."

# Генерируем заглушку QUIC-пакета
if [ ! -f "$REPO_DIR/bin/quic_initial_www_google_com.bin" ]; then
    echo "[*] Генерируем заглушку QUIC-пакета..."
    python3 << EOF
with open("$REPO_DIR/bin/quic_initial_www_google_com.bin", "wb") as f:
    f.write(b'\xc3\xff\x00\x00\x1d' + b'\x00' * 1195)
EOF
    # Если python не сработал, создаём пустой файл
    [ -f "$REPO_DIR/bin/quic_initial_www_google_com.bin" ] || \
        dd if=/dev/zero of="$REPO_DIR/bin/quic_initial_www_google_com.bin" bs=1200 count=1 2>/dev/null
fi

# ============================================
# 6. Создание основного скрипта запуска (упрощённая версия)
# ============================================
echo "[*] Создание скрипта запуска..."

cat > "$REPO_DIR/start-zapret.sh" << 'EOF'
#!/bin/bash

ZAPRET_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BIN="$ZAPRET_DIR/bin"
LISTS="$ZAPRET_DIR/lists"
PIDFILE="/tmp/zapret.pid"

stop_zapret() {
    echo "[*] Остановка zapret..."
    if [ -f "$PIDFILE" ]; then
        sudo kill $(cat "$PIDFILE") 2>/dev/null || true
        rm -f "$PIDFILE"
    fi
    sudo nft flush table inet zapret 2>/dev/null || true
    sudo nft delete table inet zapret 2>/dev/null || true
    echo "[+] Zapret остановлен"
}

start_zapret() {
    if [ -f "$PIDFILE" ] && kill -0 $(cat "$PIDFILE") 2>/dev/null; then
        echo "[!] Zapret уже запущен (PID: $(cat $PIDFILE))"
        return
    fi

    echo "[*] Запуск zapret..."

    cd "$ZAPRET_DIR"

    # Таблица nftables
    sudo nft add table inet zapret 2>/dev/null || true
    sudo nft add chain inet zapret prerouting { type filter hook prerouting priority mangle\; policy accept\; } 2>/dev/null || true
    sudo nft add chain inet zapret output { type route hook output priority mangle\; policy accept\; } 2>/dev/null || true

    # Запуск nfqws (основные параметры)
    sudo "$BIN/nfqws" \
        --qnum=200 \
        --wf-tcp=80,443 \
        --wf-udp=443,19294-19344 \
        --filter-udp=443 --hostlist="$LISTS/list-general.txt" --dpi-desync=fake --dpi-desync-repeats=6 --dpi-desync-fake-quic="$BIN/quic_initial_www_google_com.bin" \
        --new \
        --filter-tcp=443 --hostlist="$LISTS/list-google.txt" --dpi-desync=fake,disorder2 --dpi-desync-fooling=md5sig \
        --new \
        --filter-tcp=80,443 --hostlist="$LISTS/list-general.txt" --hostlist-exclude="$LISTS/list-exclude.txt" --dpi-desync=fake,disorder2 --dpi-desync-fooling=md5sig &

    echo $! | sudo tee "$PIDFILE" > /dev/null
    sleep 1

    # Правила nftables
    sudo nft add rule inet zapret prerouting meta nfproto ipv4 tcp dport {80,443} queue num 200 2>/dev/null || true
    sudo nft add rule inet zapret prerouting meta nfproto ipv4 udp dport 443 queue num 200 2>/dev/null || true

    echo "[+] Zapret запущен (PID: $(cat $PIDFILE))"
    echo "[*] Проверьте YouTube в браузере"
}

case "$1" in
    stop) stop_zapret ;;
    restart) stop_zapret; sleep 1; start_zapret ;;
    status)
        if [ -f "$PIDFILE" ] && kill -0 $(cat "$PIDFILE") 2>/dev/null; then
            echo "[+] Zapret работает (PID: $(cat $PIDFILE))"
        else
            echo "[-] Zapret не запущен"
        fi
        ;;
    *) start_zapret ;;
esac
EOF

chmod +x "$REPO_DIR/start-zapret.sh"

# ============================================
# 7. Создание systemd сервиса
# ============================================
echo "[*] Создание systemd сервиса..."

sudo tee /etc/systemd/system/zapret.service > /dev/null << EOF
[Unit]
Description=Zapret DPI bypass service
After=network-online.target
Wants=network-online.target

[Service]
Type=forking
ExecStart=$REPO_DIR/start-zapret.sh
ExecStop=$REPO_DIR/start-zapret.sh stop
PIDFile=/tmp/zapret.pid
Restart=on-failure
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload

# ============================================
# 8. Запуск
# ============================================
echo "[*] Готово!"
echo "====================================="
echo "Установлено в: $REPO_DIR"
echo ""
echo "Команды управления:"
echo "  Запуск:        $REPO_DIR/start-zapret.sh"
echo "  Остановка:     $REPO_DIR/start-zapret.sh stop"
echo "  Статус:        $REPO_DIR/start-zapret.sh status"
echo "  Сервис запуск: sudo systemctl start zapret"
echo "  Автозагрузка:  sudo systemctl enable zapret"
echo ""
echo "Запускаем сейчас..."

sleep 2
cd "$REPO_DIR"
./start-zapret.sh

echo "[+] Установка завершена!"
echo "[*] Проверьте YouTube в браузере"
echo "[*] Это окно можно закрыть, zapret продолжит работу в фоне."
exec bash
'
