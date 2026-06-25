#!/bin/bash
gnome-terminal -- bash -c '

DIR="/home/egor/Загрузки/zapret-discord-youtube-linux"


# Клонирование
echo -e "${C}[2/5]${N} Клонирование репозитория..."
[ ! -d "$DIR" ] && git clone --depth=1 https://github.com/Sergeydigl3/zapret-discord-youtube-linux.git "$DIR"
cd "$DIR"

# Права
chmod +x service.sh auto_tune_youtube.sh 2>/dev/null || true
chmod +x src/lib/*.sh src/cli/*.sh 2>/dev/null || true

# Скачивание nfqws
echo -e "${C}[3/5]${N} Скачивание nfqws..."
[ ! -f "$DIR/nfqws" ] && ./service.sh download-deps --default

# Проверка YouTube
echo -e "${C}[4/5]${N} Проверка YouTube..."
if curl -s --tlsv1.3 --connect-timeout 5 --max-time 5 -o /dev/null -w "%{http_code}" "https://www.youtube.com" 2>/dev/null | grep -q "^[23]"; then
    echo -e "${G}✓ YouTube уже доступен!${N}"
    read -p "Нажмите Enter..."
    exit 0
fi
echo -e "${R}✗ YouTube заблокирован${N}"

# Поиск стратегии
echo -e "${C}[5/5]${N} Поиск рабочей стратегии..."
exec ./auto_tune_youtube.sh
ENDSCRIPT
    chmod +x "$SCRIPT"
fi

# Запускаем
bash "$SCRIPT"
exec bash
'

