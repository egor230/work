# Останавливаем и удаляем старый сервис
sudo systemctl stop v2raya 2>/dev/null
sudo systemctl disable v2raya 2>/dev/null
sudo rm -f /etc/systemd/system/v2raya.service
sudo rm -f /usr/local/bin/v2raya

# Устанавливаем через официальный APT репозиторий
curl -Ls https://github.com/v2rayA/v2rayA-installer/raw/main/installer.sh | sudo sh -s -- --with-xray

# Если APT установка не сработала, пробуем через snap (альтернативный способ)
if ! command -v v2raya &> /dev/null; then
    echo "APT установка не удалась, пробуем snap..."
    sudo snap install v2raya
fi

# Запускаем сервис
sudo systemctl daemon-reload
sudo systemctl start v2raya 2>/dev/null || sudo systemctl start snap.v2raya.v2raya 2>/dev/null
sudo systemctl enable v2raya 2>/dev/null || sudo systemctl enable snap.v2raya.v2raya 2>/dev/null

# Проверяем статус
sleep 2
sudo systemctl status v2raya --no-pager 2>/dev/null || sudo systemctl status snap.v2raya.v2raya --no-pager

# Если всё ещё не работает, запускаем прямо из терминала
if ! systemctl is-active --quiet v2raya 2>/dev/null && ! systemctl is-active --quiet snap.v2raya.v2raya 2>/dev/null; then
    echo ""
    echo "Запускаем v2raya вручную в отдельном терминале..."
    echo "Откройте НОВЫЙ терминал и выполните: sudo v2raya"
    echo "А в ЭТОМ терминале нажмите Enter"
    read
fi

echo ""
echo "============================================="
echo "Откройте браузер: http://localhost:2017"
echo "Если не работает, выполните вручную:"
echo "sudo v2raya"
echo "============================================="