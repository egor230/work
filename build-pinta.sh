#!/usr/bin/env bash
set -euo pipefail

GREEN='\033[0;32m'; YELLOW='\033[1;33m'; RED='\033[0;31m'; NC='\033[0m'
STEP=0
next_step() { STEP=$((STEP+1)); echo -e "\n${GREEN}[$STEP/7] $1${NC}"; }

PINTA_VERSION="2.1.2"
PINTA_REPO="https://github.com/PintaProject/Pinta.git"
SOURCE_DIR="/home/egor/Downloads/Pinta"
PUBLISH_DIR="/home/egor/Downloads/pinta-install"
INSTALL_DIR="/usr/local/lib/pinta"
DOTNET_DIR="$HOME/.dotnet"

export PATH="$DOTNET_DIR:$PATH"

# ============================================================
# 1. Зависимости системы
# ============================================================
next_step "Установка системных зависимостей"

if command -v apt-get &>/dev/null; then
    sudo apt-get update -qq
    sudo apt-get install -y git libgtk-3-dev libgirepository1.0-dev wget curl
elif command -v dnf &>/dev/null; then
    sudo dnf install -y git gtk3-devel gobject-introspection-devel wget curl
elif command -v pacman &>/dev/null; then
    sudo pacman -Sy --noconfirm git gtk3 gobject-introspection wget curl
else
    echo -e "${RED}Неизвестный менеджер пакетов. Вам нужно установить: git, libgtk-3-dev, libgirepository1.0-dev${NC}"
    exit 1
fi

# ============================================================
# 2. .NET SDK (нужна 8+ версия)
# ============================================================
next_step "Проверка .NET SDK"

if command -v dotnet &>/dev/null; then
    DOTNET_VER=$(dotnet --version 2>/dev/null | cut -d. -f1)
    echo "  Найден .NET SDK версии $(dotnet --version)"
else
    DOTNET_VER="0"
    echo "  .NET не найден"
fi

if [[ "$DOTNET_VER" -lt 8 ]]; then
    echo -e "${YELLOW}  Требуется .NET 8+. Устанавливаю...${NC}"
    wget -q https://dot.net/v1/dotnet-install.sh -O /tmp/dotnet-install.sh
    chmod +x /tmp/dotnet-install.sh
    /tmp/dotnet-install.sh --channel 8.0 --install-dir "$DOTNET_DIR"
    export PATH="$DOTNET_DIR:$PATH"
    echo -e "${GREEN}  Установлен .NET SDK $(dotnet --version)${NC}"
fi

# ============================================================
# 3. Получение исходников (с сохранением наших правок)
# ============================================================
next_step "Получение исходников Pinta $PINTA_VERSION"

if [[ -d "$SOURCE_DIR/.git" ]]; then
    echo "  Использую существующий локальный репозиторий в $SOURCE_DIR"
    echo "  Версия: $(cd "$SOURCE_DIR" && git describe --tags 2>/dev/null || echo 'unknown')"
else
    echo "  Клонирую репозиторий..."
    git clone --branch "$PINTA_VERSION" --depth 1 "$PINTA_REPO" "$SOURCE_DIR"
fi

cd "$SOURCE_DIR"

# ============================================================
# 4. Применение патчей для защиты от отсутствующих иконок
# ============================================================
next_step "Применение патчей для защиты от краша с иконками"

echo -e "${YELLOW}  Патч 1: GtkExtensions.cs — LoadIcon через ResourceLoader (с fallback)${NC}"
cat > /tmp/patch-gtkextensions.py << 'PYEOF'
import re

filepath = "Pinta.Core/Extensions/GtkExtensions.cs"
with open(filepath, 'r') as f:
    content = f.read()

old = '''\t\tpublic static Gdk.Pixbuf LoadIcon (this Gtk.IconTheme theme, string icon_name, int size)
\t\t{
\t\t\t// Simple wrapper to avoid the verbose IconLookupFlags parameter.
\t\t\treturn theme.LoadIcon (icon_name, size, Gtk.IconLookupFlags.ForceSize);
\t\t}'''

new = '''\t\tpublic static Gdk.Pixbuf LoadIcon (this Gtk.IconTheme theme, string icon_name, int size)
\t\t{
\t\t\t// Use ResourceLoader for robust fallback support
\t\t\t// (handles missing icons gracefully instead of crashing).
\t\t\treturn Pinta.Resources.ResourceLoader.GetIcon (icon_name, size);
\t\t}'''

if old in content:
    content = content.replace(old, new)
    with open(filepath, 'w') as f:
        f.write(content)
    print("  ✓ GtkExtensions.cs patched")
else:
    # Check if already patched
    if 'ResourceLoader.GetIcon' in content:
        print("  ✓ GtkExtensions.cs already patched")
    else:
        print("  ✗ GtkExtensions.cs: pattern not found!")
        exit(1)
PYEOF
python3 /tmp/patch-gtkextensions.py

echo -e "${YELLOW}  Патч 2: MoveSelectedTool.cs — ResourceLoader вместо LoadIcon${NC}"
cat > /tmp/patch-moveselected.py << 'PYEOF'
filepath = "Pinta.Tools/Tools/MoveSelectedTool.cs"
with open(filepath, 'r') as f:
    content = f.read()

old = "Gtk.IconTheme.Default.LoadIcon (Pinta.Resources.Icons.ToolMoveCursor, 16)"
new = "Pinta.Resources.ResourceLoader.GetIcon (Pinta.Resources.Icons.ToolMoveCursor, 16)"

if old in content:
    content = content.replace(old, new)
    with open(filepath, 'w') as f:
        f.write(content)
    print("  ✓ MoveSelectedTool.cs patched")
else:
    if 'ResourceLoader.GetIcon' in content:
        print("  ✓ MoveSelectedTool.cs already patched")
    else:
        print("  ✗ MoveSelectedTool.cs: pattern not found!")
        exit(1)
PYEOF
python3 /tmp/patch-moveselected.py

echo -e "${YELLOW}  Патч 3: MoveSelectionTool.cs — ResourceLoader вместо LoadIcon${NC}"
cat > /tmp/patch-moveselection.py << 'PYEOF'
filepath = "Pinta.Tools/Tools/MoveSelectionTool.cs"
with open(filepath, 'r') as f:
    content = f.read()

old = "Gtk.IconTheme.Default.LoadIcon (Pinta.Resources.Icons.ToolMoveSelection, 16)"
new = "Pinta.Resources.ResourceLoader.GetIcon (Pinta.Resources.Icons.ToolMoveSelection, 16)"

if old in content:
    content = content.replace(old, new)
    with open(filepath, 'w') as f:
        f.write(content)
    print("  ✓ MoveSelectionTool.cs patched")
else:
    if 'ResourceLoader.GetIcon' in content:
        print("  ✓ MoveSelectionTool.cs already patched")
    else:
        print("  ✗ MoveSelectionTool.cs: pattern not found!")
        exit(1)
PYEOF
python3 /tmp/patch-moveselection.py

# ============================================================
# 5. Установка Pinta-иконок в системные темы
# ============================================================
next_step "Установка Pinta-иконок в системные темы"

ICONS_SRC="$SOURCE_DIR/Pinta.Resources/icons/hicolor/scalable/actions"

if [[ -d "$ICONS_SRC" ]]; then
    echo "  Устанавливаю в /usr/share/icons/hicolor/scalable/actions/"
    sudo mkdir -p /usr/share/icons/hicolor/scalable/actions/
    for f in "$ICONS_SRC"/*.svg; do
        sudo cp "$f" /usr/share/icons/hicolor/scalable/actions/
    done
    sudo gtk-update-icon-cache /usr/share/icons/hicolor/ 2>/dev/null || true

    echo "  Устанавливаю в /usr/share/icons/Mint-X/scalable/actions/"
    sudo mkdir -p /usr/share/icons/Mint-X/actions/scalable/
    for f in "$ICONS_SRC"/*.svg; do
        sudo cp "$f" /usr/share/icons/Mint-X/actions/scalable/
    done
    sudo gtk-update-icon-cache /usr/share/icons/Mint-X/ 2>/dev/null || true

    echo -e "${GREEN}  ✓ Все иконки установлены (${YELLOW}$(ls "$ICONS_SRC"/*.svg | wc -l)${GREEN} SVG)${NC}"
else
    echo -e "${RED}  Иконки не найдены: $ICONS_SRC${NC}"
    exit 1
fi

cd "$SOURCE_DIR"

# ============================================================
# 6. Сборка Pinta (self-contained)
# ============================================================
next_step "Сборка Pinta $PINTA_VERSION"

rm -rf "$PUBLISH_DIR"
dotnet publish Pinta/Pinta.csproj -c Release -o "$PUBLISH_DIR" --self-contained true
echo -e "${GREEN}  ✓ Сборка завершена. Бинарники: $PUBLISH_DIR${NC}"

# ============================================================
# 7. Установка в систему
# ============================================================
next_step "Установка в систему"

sudo rm -rf "$INSTALL_DIR"
sudo mkdir -p "$INSTALL_DIR"
sudo cp -r "$PUBLISH_DIR/." "$INSTALL_DIR/"
sudo chmod -R 755 "$INSTALL_DIR"

# Создаём симлинк для запуска
sudo ln -sf "$INSTALL_DIR/Pinta" /usr/local/bin/pinta
echo -e "${GREEN}  ✓ Установлено в $INSTALL_DIR${NC}"
echo -e "${GREEN}  ✓ Симлинк: /usr/local/bin/pinta → $INSTALL_DIR/Pinta${NC}"

# Создаём .desktop файл
cat > /tmp/pinta.desktop << EOF
[Desktop Entry]
Name=Pinta
Comment=Рисуй. Редактируй. Твори.
Exec=$INSTALL_DIR/Pinta
Icon=$INSTALL_DIR/icons/hicolor/scalable/actions/image-resize-canvas-base-symbolic.svg
Terminal=false
Type=Application
Categories=Graphics;2DGraphics;RasterGraphics;
StartupNotify=true
EOF
sudo cp /tmp/pinta.desktop /usr/share/applications/pinta.desktop
echo -e "${GREEN}  ✓ Создан /usr/share/applications/pinta.desktop${NC}"

# ============================================================
# Готово
# ============================================================
echo -e "\n${GREEN}══════════════════════════════════════════════════${NC}"
echo -e "${GREEN}  Pinta $PINTA_VERSION собрана и установлена!${NC}"
echo -e "${GREEN}  Запуск: pinta${NC}"
echo -e "${GREEN}  Или через меню приложений${NC}"
echo -e "${GREEN}══════════════════════════════════════════════════${NC}"
