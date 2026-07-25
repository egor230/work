#!/bin/bash

# ============================================
# Скрипт добавляет команды для управления 
# рабочими областями в настройки клавиатуры
# ============================================

# Определяем окружение
if command -v gsettings &> /dev/null && gsettings list-schemas | grep -q "org.cinnamon"; then
    DESKTOP="cinnamon"
elif command -v gsettings &> /dev/null && gsettings list-schemas | grep -q "org.mate"; then
    DESKTOP="mate"
elif command -v xfconf-query &> /dev/null; then
    DESKTOP="xfce"
else
    echo "❌ Неподдерживаемое окружение"
    exit 1
fi

# Получаем количество рабочих областей
if [ "$DESKTOP" = "cinnamon" ]; then
    WORKSPACE_COUNT=$(gsettings get org.cinnamon.desktops num-workspaces)
elif [ "$DESKTOP" = "mate" ]; then
    WORKSPACE_COUNT=$(gsettings get org.mate.Marco.general num-workspaces)
elif [ "$DESKTOP" = "xfce" ]; then
    WORKSPACE_COUNT=$(xfconf-query -c xfwm4 -p /general/workspace_count)
fi

echo "🚀 Добавляю команды для $WORKSPACE_COUNT рабочих областей..."

# Функция добавления команды в Cinnamon
add_cinnamon_command() {
    local name="$1"
    local command="$2"
    local description="$3"
    
    # Получаем текущий список пользовательских команд
    local current=$(gsettings get org.cinnamon.desktop.keybindings custom-list 2>/dev/null)
    if [ "$current" = "[]" ] || [ -z "$current" ]; then
        current="[]"
    fi
    
    # Генерируем уникальный ID
    local id="custom-workspace-$(date +%s)-$RANDOM"
    
    # Добавляем команду
    gsettings set org.cinnamon.desktop.keybindings.custom-keybindings."$id" name "$name"
    gsettings set org.cinnamon.desktop.keybindings.custom-keybindings."$id" command "$command"
    gsettings set org.cinnamon.desktop.keybindings.custom-keybindings."$id" binding "[]"
    
    # Добавляем ID в список
    local new_list=$(echo "$current" | sed "s/]/, '$id']/" | sed "s/\[, /[/")
    gsettings set org.cinnamon.desktop.keybindings custom-list "$new_list"
    
    echo "✅ Добавлена команда: $name"
}

# Функция добавления команды в MATE
add_mate_command() {
    local name="$1"
    local command="$2"
    
    # В MATE используем dconf
    local id="custom-workspace-$(date +%s)-$RANDOM"
    
    dconf write /org/mate/desktop/keybindings/"$id"/name "'$name'"
    dconf write /org/mate/desktop/keybindings/"$id"/command "'$command'"
    dconf write /org/mate/desktop/keybindings/"$id"/binding "[]"
    
    # Добавляем в список
    local current=$(dconf read /org/mate/desktop/keybindings/custom-list 2>/dev/null || echo "[]")
    local new_list=$(echo "$current" | sed "s/]/, '$id']/" | sed "s/\[, /[/")
    dconf write /org/mate/desktop/keybindings/custom-list "$new_list"
    
    echo "✅ Добавлена команда: $name"
}

# Функция добавления команды в Xfce
add_xfce_command() {
    local name="$1"
    local command="$2"
    
    # В Xfce используем xfconf-query
    local id=$(date +%s)-$RANDOM
    
    xfconf-query -c xfce4-keyboard-shortcuts -p "/commands/custom/$id" -s "$command" --create
    xfconf-query -c xfce4-keyboard-shortcuts -p "/commands/custom/$id/name" -s "$name" --create
    
    echo "✅ Добавлена команда: $name"
}

# ===== СОЗДАЁМ КОМАНДЫ =====

for i in $(seq 1 $WORKSPACE_COUNT); do
    case "$DESKTOP" in
        cinnamon)
            add_cinnamon_command "Переключиться на область $i" \
                "gsettings set org.cinnamon.desktop.wm.keybindings switch-to-workspace-$i \"['']\" && gsettings set org.cinnamon.desktop.wm.keybindings switch-to-workspace-$i \"['']\" && echo 'Переключено на область $i'"
            ;;
        mate)
            add_mate_command "Переключиться на область $i" \
                "gsettings set org.mate.Marco.window-keybindings switch-to-workspace-$i \"['']\""
            ;;
        xfce)
            add_xfce_command "Переключиться на область $i" \
                "xfconf-query -c xfwm4 -p /general/workspace_${i}_key -s ''"
            ;;
    esac
done

# Добавляем команды для перемещения окон
case "$DESKTOP" in
    cinnamon)
        add_cinnamon_command "Переместить окно на область 1" \
            "gsettings set org.cinnamon.desktop.wm.keybindings move-to-workspace-1 \"['']\""
        add_cinnamon_command "Переместить окно на область 2" \
            "gsettings set org.cinnamon.desktop.wm.keybindings move-to-workspace-2 \"['']\""
        add_cinnamon_command "Переместить окно на область 3" \
            "gsettings set org.cinnamon.desktop.wm.keybindings move-to-workspace-3 \"['']\""
        add_cinnamon_command "Переместить окно на область 4" \
            "gsettings set org.cinnamon.desktop.wm.keybindings move-to-workspace-4 \"['']\""
        ;;
esac

echo ""
echo "✨ ГОТОВО! Теперь:"
echo "1. Открой Настройки → Клавиатура → Сочетания клавиш"
echo "2. Найди раздел 'Пользовательские сочетания' или 'Custom Shortcuts'"
echo "3. Там будут команды:"
echo "   - 'Переключиться на область 1'... и т.д."
echo "   - 'Переместить окно на область 1'... и т.д."
echo "4. Нажми на каждую и назначь ЛЮБУЮ удобную клавишу!"
echo ""
echo "💡 Например:"
echo "   - Ctrl+Alt+1 для переключения на область 1"
echo "   - Ctrl+Shift+1 для перемещения окна в область 1"
echo "   - Или любые другие комбинации!"