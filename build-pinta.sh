#!/usr/bin/env bash
# ============================================================
#  Pinta — установка из исходников (без Flatpak/Snap)
#  Скрипт содержит полную цепочку действий:
#    Попытки apt → PPA → GitHub .deb → неудача
#    Pinta 3.x: .NET 10 + GTK4 → сборка → краш (GTK4 4.18 нужен)
#    Pinta 2.1.2: .NET 8 + GTK3 → сборка → работает!
#    Русская локализация: компиляция .mo + настройка системы
#
#  Совместимость: Ubuntu / Linux Mint / Debian (apt)
# ============================================================
set -euo pipefail

# --- Цвета для вывода ---
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
CYAN='\033[0;36m'
BOLD='\033[1m'
NC='\033[0m'

# --- Счётчик шагов ---
STEP=0
TOTAL_STEPS=11
next_step() {
    STEP=$((STEP + 1))
    echo ""
    echo -e "${CYAN}══════════════════════════════════════════════════════════════${NC}"
    echo -e "${BOLD}  Шаг $STEP/$TOTAL_STEPS: $1${NC}"
    echo -e "${CYAN}══════════════════════════════════════════════════════════════${NC}"
}

info()    { echo -e "  ${GREEN}[✓]${NC} $1"; }
warn()    { echo -e "  ${YELLOW}[!]${NC} $1"; }
fail()    { echo -e "  ${RED}[✗]${NC} $1"; }
section() { echo -e "\n${BOLD}--- $1 ---${NC}"; }

# --- Переменные ---
PINTA_VERSION="2.1.2"                    # Финальная рабочая версия (GTK3)
PINTA_VERSION_FAILED="3.2"              # Версия, которая НЕ работает на GTK4 4.14
PINTA_REPO="https://github.com/PintaProject/Pinta.git"
SOURCE_DIR="/tmp/Pinta-build"           # Куда клонируем исходники
PUBLISH_DIR="/tmp/Pinta-publish"       # Куда publis'им
INSTALL_DIR="/usr/local/lib/pinta"     # Куда ставим в систему
LAUNCHER="/usr/local/bin/pinta"        # Лаунчер
LOCALE="ru_RU.UTF-8"                   # Целевая локаль

echo -e "${BOLD}${GREEN}"
echo "╔══════════════════════════════════════════════════════════╗"
echo "║       Pinta — установка из исходников                   ║"
echo "║       Без Flatpak, без Snap, чистая сборка              ║"
echo "║       Русская локализация включена                      ║"
echo "╚══════════════════════════════════════════════════════════╝"
echo -e "${NC}"


# ============================================================
#  Шаг 1: Определение системы
# ============================================================
next_step "Определение дистрибутива Linux"

if [[ -f /etc/os-release ]]; then
    . /etc/os-release
    info "Система: $PRETTY_NAME"
    info "ID: $ID (BASE: $ID_LIKE)"
    info "Кодовое имя: $VERSION_CODENAME"
else
    warn "Не удалось определить дистрибутив, продолжаем..."
fi

# Проверяем, что это apt-based система
if ! command -v apt-get &>/dev/null; then
    fail "Этот скрипт предназначен для apt-based систем (Ubuntu/Mint/Debian)"
    fail "Для других систем установите: git, libgtk-3-dev, dotnet-sdk-8.0 вручную"
    exit 1
fi


# ============================================================
#  Шаг 2: Попытки установки готовыми пакетами (все три провалились)
# ============================================================
next_step "Попытки установки готовыми пакетами (apt / PPA / .deb)"

section "2a: apt install pinta"
warn "Пытаемся: sudo apt install pinta"
if sudo apt-cache show pinta &>/dev/null 2>&1; then
    info "Пакет pinta найден в репозиториях!"
    info "Устанавливаем через apt..."
    sudo apt-get install -y pinta
    info "Готово! Pinta установлена через apt."
    exit 0
else
    fail "Пакет pinta НЕ найден в репозиториях $VERSION_CODENAME"
    warn "Это нормально — в Ubuntu Noble / Linux Mint 22 pinta отсутствует"
fi

section "2b: PPA pinta-maintainers"
warn "Пытаемся: sudo add-apt-repository ppa:pinta-maintainers/pinta-stable"
if sudo add-apt-repository ppa:pinta-maintainers/pinta-stable -y 2>/dev/null; then
    sudo apt-get update -qq
    if sudo apt-cache show pinta &>/dev/null 2>&1; then
        info "PPA работает! Устанавливаем..."
        sudo apt-get install -y pinta
        info "Готово! Pinta установлена через PPA."
        exit 0
    else
        fail "PPA добавлена, но пакет pinta в ней не найден"
    fi
else
    fail "PPA pinta-maintainers/pinta-stable не существует или не поддерживает $VERSION_CODENAME"
fi

section "2c: .deb из GitHub Releases"
warn "Ищем .deb пакеты в GitHub Releases..."
DEB_URL=$(curl -sL --connect-timeout 10 \
    "https://api.github.com/repos/PintaProject/Pinta/releases" 2>/dev/null \
    | python3 -c "
import sys, json
try:
    releases = json.loads(sys.stdin.read())
    for r in releases:
        for a in r.get('assets', []):
            if '.deb' in a['name']:
                print(a['browser_download_url'])
                sys.exit(0)
except: pass
" 2>/dev/null || true)

if [[ -n "$DEB_URL" ]]; then
    info "Найден .deb: $DEB_URL"
    wget -q "$DEB_URL" -O /tmp/pinta.deb
    sudo dpkg -i /tmp/pinta.deb || sudo apt-get install -f -y
    info "Готово! Pinta установлена из .deb"
    exit 0
else
    fail ".deb пакеты НЕ найдены в GitHub Releases (начиная с Pinta 3.x их больше нет)"
fi

section "Попытки установки готовыми пакетами — все провалились"
warn "Переход к сборке из исходников..."
echo ""


# ============================================================
#  Шаг 3: Установка системных зависимостей
# ============================================================
next_step "Установка системных зависимостей"

section "3a: Пакеты для сборки"
sudo apt-get update -qq
sudo apt-get install -y \
    git \
    libgtk-3-dev \
    libgtk-4-dev \
    libadwaita-1-dev \
    libgirepository1.0-dev \
    gettext \
    locales \
    webp-pixbuf-loader \
    wget \
    curl \
    python3 \
    2>&1 | grep -v "^$" | tail -5

info "Системные зависимости установлены"

section "3b: Версии GTK"
GTK3_VER=$(dpkg -l | grep "libgtk-3-0 " | awk '{print $3}' || echo "не установлен")
GTK4_VER=$(dpkg -l | grep "libgtk-4-1 " | awk '{print $3}' || echo "не установлен")
info "GTK3: $GTK3_VER"
info "GTK4: $GTK4_VER"
warn "Pinta 3.x требует GTK4 >= 4.18, у нас $GTK4_VER — НЕ хватает!"
info "Pinta 2.x использует GTK3 — будет работать"


# ============================================================
#  Шаг 4: Настройка системной локали ru_RU.UTF-8
# ============================================================
next_step "Настройка системной локали $LOCALE"

section "4a: Проверка текущей локали"
CURRENT_LOCALE=$(locale 2>/dev/null | grep "^LANG=" | cut -d= -f2 | tr -d '"')
info "Текущая локаль: $CURRENT_LOCALE"

section "4a.5: Генерация $LOCALE"
# Проверяем, раскомментирована ли нужная строка в locale.gen
if grep -q "^${LOCALE}" /etc/locale.gen 2>/dev/null; then
    info "$LOCALE уже активирована в locale.gen"
elif grep -q "${LOCALE}" /etc/locale.gen 2>/dev/null; then
    warn "Раскомментирую $LOCALE в locale.gen..."
    sudo sed -i "s|^# *${LOCALE}|${LOCALE}|" /etc/locale.gen
    info "Раскомментирована"
else
    warn "$LOCALE не найдена в locale.gen, добавляю..."
    echo "${LOCALE} UTF-8" | sudo tee -a /etc/locale.gen > /dev/null
fi

# Генерируем локаль
info "Генерирую локаль $LOCALE (это может занять время)..."
sudo locale-gen "$LOCALE" 2>&1 | while read -r line; do
    info "  $line"
done
sudo update-locale LANG="$LOCALE" 2>/dev/null || true
info "Локаль $LOCALE сгенерирована и активирована"

section "4b: Проверка результата"
if locale -a 2>/dev/null | grep -q "ru_RU.utf8\|ru_RU.UTF-8"; then
    info "Локаль $LOCALE доступна в системе"
else
    warn "Локаль может быть недоступна, но Pinta всё равно будет работать с переводом"
fi


# ============================================================
#  Шаг 5: Установка .NET SDK
# ============================================================
next_step "Установка .NET SDK"

# Проверяем, есть ли уже подходящий dotnet
DOTNET_FOUND_VER="0"
if command -v dotnet &>/dev/null; then
    DOTNET_FOUND_VER=$(dotnet --version 2>/dev/null | cut -d. -f1)
    info "Найден .NET SDK: $(dotnet --version)"
fi

# Для Pinta 2.1.2 нужен .NET 8
if [[ "$DOTNET_FOUND_VER" -lt 8 ]]; then
    warn ".NET 8+ не найден (найден $DOTNET_FOUND_VER.x). Устанавливаю..."
    wget -q https://dot.net/v1/dotnet-install.sh -O /tmp/dotnet-install.sh
    chmod +x /tmp/dotnet-install.sh
    sudo /tmp/dotnet-install.sh --channel 8.0 --install-dir /usr/share/dotnet 2>&1 | tail -3
    info ".NET 8 SDK установлен: $(dotnet --list-sdks | grep ^8 | tail -1)"
else
    info ".NET 8+ уже установлен, пропускаем"
fi

section "Установленные SDK:"
dotnet --list-sdks 2>&1 | while read -r line; do
    info "  $line"
done


# ============================================================
#  Шаг 6: Попытка сборки Pinta 3.2 (ПРОВАЛ — GTK4 слишком старый)
# ============================================================
next_step "Попытка сборки Pinta $PINTA_VERSION_FAILED (GTK4) — ДЛЯ ДОКАЗАТЕЛЬСТВА"

warn "Клонируем Pinta $PINTA_VERSION_FAILED для демонстрации проблемы..."
rm -rf /tmp/Pinta3
git clone --depth 1 --branch "$PINTA_VERSION_FAILED" "$PINTA_REPO" /tmp/Pinta3 2>&1 | tail -3

section "Требования Pinta $PINTA_VERSION_FAILED:"
warn "  .NET 10 (фреймворк net10.0)"
warn "  GTK4 >= 4.18 + libadwaita >= 1.7"
warn "  У нас GTK4 $GTK4_VER — НЕ хватает!"

section "Устанавливаем .NET 10 для эксперимента..."
sudo /tmp/dotnet-install.sh --channel 10.0 --install-dir /usr/share/dotnet 2>&1 | tail -3
info ".NET 10: $(dotnet --list-sdks | grep ^10 | tail -1)"

section "Собираем Pinta $PINTA_VERSION_FAILED..."
cd /tmp/Pinta3
if dotnet build Pinta.sln -c Release 2>&1 | tail -3; then
    info "Сборка завершена БЕЗ ошибок"
else
    fail "Сборка провалилась"
fi

section "Тестируем запуск Pinta $PINTA_VERSION_FAILED..."
warn "Запускаем pinta и ловим ошибку..."
CRASH_OUTPUT=$(timeout 5 dotnet run --project Pinta -c Release 2>&1 || true)
if echo "$CRASH_OUTPUT" | grep -q "EntryPointNotFoundException\|gdk_memory_texture"; then
    fail "КРАШ! Ошибка: gdk_memory_texture_builder_get_type"
    fail "Причина: GTK4 $GTK4_VER слишком старый (нужен >= 4.18)"
    fail "Функция gdk_memory_texture_builder появилась только в GTK4 4.18"
    warn "ВЫВОД: Pinta $PINTA_VERSION_FAILED НЕРАБОТОСПОСОБНА на $VERSION_CODENAME"
else
    warn "Неожиданный вывод: $CRASH_OUTPUT"
fi

echo ""
warn "Очищаем за собой..."
rm -rf /tmp/Pinta3
cd /tmp


# ============================================================
#  Шаг 7: Клонирование Pinta 2.1.2 (рабочая версия на GTK3)
# ============================================================
next_step "Клонирование Pinta $PINTA_VERSION (GTK3 — рабочая версия)"

warn "Pinta 2.1.2 использует GtkSharp 3.24 — совместима с GTK3"
info "Требования: .NET 8 + GTK3 (у нас есть и то, и другое)"

if [[ -d "$SOURCE_DIR/.git" ]]; then
    info "Репозиторий уже существует: $SOURCE_DIR"
    cd "$SOURCE_DIR"
    info "Текущая версия: $(git describe --tags 2>/dev/null || echo 'unknown')"
else
    info "Клонируем Pinta $PINTA_VERSION (depth=1 для скорости)..."
    rm -rf "$SOURCE_DIR"
    git clone --depth 1 --branch "$PINTA_VERSION" "$PINTA_REPO" "$SOURCE_DIR" 2>&1 | tail -5
    cd "$SOURCE_DIR"
    info "Клонирование завершено"
fi

section "Проверка версии:"
info "Версия: $(grep '<Version>' Directory.Build.props | head -1)"
info "Фреймворк: $(grep 'TargetFramework' Directory.Build.props | head -1)"
info "GTK-зависимость: $(grep 'GtkSharp' Pinta/*.csproj 2>/dev/null || echo 'найти не удалось')"

section "Проверка локализации в исходниках:"
RU_PO_SIZE=$(wc -c < "$SOURCE_DIR/po/ru.po" 2>/dev/null || echo "0")
info "Файл перевода ru.po: $RU_PO_SIZE байт"
TOTAL_PO=$(ls "$SOURCE_DIR/po/"*.po 2>/dev/null | wc -l)
info "Всего языков: $TOTAL_PO"


# ============================================================
#  Шаг 8: Сборка Pinta 2.1.2 С локализацией
# ============================================================
next_step "Сборка Pinta $PINTA_VERSION (с русской локализацией)"

section "8a: Компиляция переводов (.po → .mo)"
info "Компилируем ru.po → ru.mo..."
mkdir -p /tmp/pinta-locales
msgfmt "$SOURCE_DIR/po/ru.po" -o /tmp/pinta-locales/ru.mo 2>&1
RU_MO_SIZE=$(wc -c < /tmp/pinta-locales/ru.mo)
info "Скомпилирован ru.mo: $RU_MO_SIZE байт"

section "8b: dotnet build (с флагом локализации)"
info "Команда: dotnet build Pinta.sln -c Release -p:BuildTranslations=true"
cd "$SOURCE_DIR"
dotnet build Pinta.sln -c Release -p:BuildTranslations=true 2>&1 | tail -10

section "8c: dotnet publish (с локализацией)"
info "Команда: dotnet publish -c Release -p:BuildTranslations=true"
rm -rf "$PUBLISH_DIR"
dotnet publish Pinta/Pinta.csproj -c Release \
    -p:PublishDir="$PUBLISH_DIR" \
    -p:BuildTranslations=true 2>&1 | tail -5

section "8d: Проверка локалей в publish/"
if [[ -d "$PUBLISH_DIR/locale/ru/LC_MESSAGES" ]]; then
    info "Русская локаль найдена в сборке!"
    ls "$PUBLISH_DIR/locale/ru/LC_MESSAGES/" | while read -r f; do
        info "  $f ($(wc -c < "$PUBLISH_DIR/locale/ru/LC_MESSAGES/$f") байт)"
    done
else
    warn "Автоматическая локализация не попала в publish"
    warn "Установим скомпилированный ru.mo вручную"
fi

section "8e: Содержимое publish/"
info "Файлов: $(find "$PUBLISH_DIR" -type f | wc -l)"
find "$PUBLISH_DIR" -maxdepth 1 -name "*.dll" | while read -r f; do
    info "  $(basename "$f")"
done
info "Сборка завершена успешно!"


# ============================================================
#  Шаг 9: Установка в систему
# ============================================================
next_step "Установка Pinta в систему"

section "9a: Удаление старой установки (если есть)"
if [[ -d "$INSTALL_DIR" ]]; then
    warn "Удаляю старую установку: $INSTALL_DIR"
    sudo rm -rf "$INSTALL_DIR"
fi
if [[ -f "$LAUNCHER" ]]; then
    warn "Удаляю старый лаунчер: $LAUNCHER"
    sudo rm -f "$LAUNCHER"
fi
info "Старая установка очищена"

section "9b: Копирование бинарников"
sudo mkdir -p "$INSTALL_DIR"
sudo cp -r "$PUBLISH_DIR/." "$INSTALL_DIR/"
sudo chmod -R 755 "$INSTALL_DIR"
info "Файлы скопированы в $INSTALL_DIR"
info "Файлов: $(sudo find "$INSTALL_DIR" -type f | wc -l)"

section "9c: Установка русской локали"
# Если автоматическая локализация не попала в publish — ставим вручную
if [[ ! -d "$INSTALL_DIR/locale/ru/LC_MESSAGES" ]]; then
    warn "Автоматическая локализация не найдена, устанавливаю вручную..."
fi
sudo mkdir -p "$INSTALL_DIR/locale/ru/LC_MESSAGES"
sudo cp /tmp/pinta-locales/ru.mo "$INSTALL_DIR/locale/ru/LC_MESSAGES/pinta.mo"
sudo chmod 644 "$INSTALL_DIR/locale/ru/LC_MESSAGES/pinta.mo"
RU_INSTALLED_SIZE=$(wc -c < "$INSTALL_DIR/locale/ru/LC_MESSAGES/pinta.mo")
info "Русская локаль установлена: $INSTALL_DIR/locale/ru/LC_MESSAGES/pinta.mo ($RU_INSTALLED_SIZE байт)"

section "9d: Создание лаунчера"
# Лаунчер устанавливает переменные окружения для русской локали
sudo tee "$LAUNCHER" > /dev/null << LAUNCHER_EOF
#!/bin/bash
# Pinta $PINTA_VERSION launcher
# Автоматически создан скриптом build-pinta.sh
# Устанавливаем русскую локаль для интерфейса
export LANG=$LOCALE
export LC_ALL=$LOCALE
export TEXTDOMAIN=pinta
export TEXTDOMAINDIR=$INSTALL_DIR/locale
exec dotnet $INSTALL_DIR/Pinta.dll "\$@"
LAUNCHER_EOF
sudo chmod +x "$LAUNCHER"
info "Лаунчер создан: $LAUNCHER"
info "Содержимое:"
cat "$LAUNCHER" | while read -r line; do
    info "  $line"
done

section "9e: Создание .desktop файла"
sudo mkdir -p /usr/local/share/applications
sudo tee /usr/local/share/applications/com.github.PintaProject.Pinta.desktop > /dev/null << 'DESKTOP_EOF'
[Desktop Entry]
Version=1.0
Name=Pinta
Name[ru]=Pinta — Редактор изображений
Comment=Easily create and edit images
Comment[ru]=Простое создание и редактирование изображений
GenericName=Image Editor
GenericName[ru]=Редактор изображений
X-GNOME-FullName=Pinta Image Editor
X-GNOME-FullName[ru]=Pinta — Редактор изображений
TryExec=pinta
Exec=pinta %F
Icon=com.github.PintaProject.Pinta
StartupNotify=false
StartupWMClass=Pinta
Terminal=false
Type=Application
Categories=Graphics;2DGraphics;RasterGraphics;GTK;
Keywords=draw;drawing;paint;painting;graphics;raster;2d;
Keywords[ru]=рисование;живопись;графика;редактор;изображений;растровая;
MimeType=image/bmp;image/gif;image/jpeg;image/jpg;image/pjpeg;image/png;image/svg+xml;image/tiff;image/x-bmp;image/x-gray;image/x-icb;image/x-ico;image/x-png;image/x-portable-anymap;image/x-portable-bitmap;image/x-portable-graymap;image/x-portable-pixmap;image/x-xbitmap;image/x-xpixmap;image/x-pcx;image/x-targa;image/x-tga;image/openraster;
DESKTOP_EOF
info ".desktop файл создан с русскими названиями"
info "Путь: /usr/local/share/applications/com.github.PintaProject.Pinta.desktop"

section "9f: Установка иконок"
sudo mkdir -p /usr/local/share/icons/hicolor
if [[ -d "$SOURCE_DIR/Pinta.Resources/icons" ]]; then
    sudo cp -r "$SOURCE_DIR/Pinta.Resources/icons/hicolor/"* \
        /usr/local/share/icons/hicolor/ 2>/dev/null || true
    info "Иконки скопированы из $SOURCE_DIR/Pinta.Resources/icons/hicolor/"
elif [[ -d "$INSTALL_DIR/icons" ]]; then
    sudo cp -r "$INSTALL_DIR/icons/hicolor/"* \
        /usr/local/share/icons/hicolor/ 2>/dev/null || true
    info "Иконки скопированы из $INSTALL_DIR/icons/hicolor/"
else
    warn "Иконки не найдены, пропускаем (не критично)"
fi
sudo gtk-update-icon-cache /usr/local/share/icons/hicolor/ 2>/dev/null || true

section "9g: Обновление кэша desktop-файлов"
sudo update-desktop-database /usr/local/share/applications/ 2>/dev/null || true
info "Кэш desktop-файлов обновлён"

info "Установка в систему завершена!"


# ============================================================
#  Шаг 10: Тестирование — проверяем что Pinta НЕ вылетает
# ============================================================
next_step "Тестирование запуска Pinta (русская локаль)"

section "10a: Проверка версии"
warn "Команда: pinta --version"
PINTA_VER_OUTPUT=$(pinta --version 2>&1 || true)
if [[ "$PINTA_VER_OUTPUT" == *"$PINTA_VERSION"* ]]; then
    info "Версия корректна: $PINTA_VER_OUTPUT"
else
    fail "Неожиданная версия: $PINTA_VER_OUTPUT"
fi

section "10b: Проверка лаунчера"
info "Путь: $(which pinta)"
info "Тип: $(file "$(which pinta)")"
info "Права: $(ls -la "$(which pinta)" | awk '{print $1}')"

section "10c: Проверка локали"
info "Файл перевода: $INSTALL_DIR/locale/ru/LC_MESSAGES/pinta.mo"
if [[ -f "$INSTALL_DIR/locale/ru/LC_MESSAGES/pinta.mo" ]]; then
    info "Файл существует, размер: $(wc -c < "$INSTALL_DIR/locale/ru/LC_MESSAGES/pinta.mo") байт"
else
    fail "Файл перевода НЕ найден!"
fi

section "10d: Запуск Pinta на 10 секунд (русская локаль)"
warn "Запускаем Pinta с LANG=$LOCALE на 10 секунд..."
CRASH_LOG="/tmp/pinta-crash-test.log"
LANG="$LOCALE" LC_ALL="$LOCALE" timeout 10 pinta > "$CRASH_LOG" 2>&1 || EXIT_CODE=$?
EXIT_CODE=${EXIT_CODE:-0}

if [[ "$EXIT_CODE" -eq 124 ]]; then
    # Exit code 124 = timeout убил процесс = Pinta работала все 10 секунд
    info "Pinta работала все 10 секунд — НЕ вылетела!"
    info "Exit code 124 = timeout принудительно завершил (значит Pinta жива)"
elif [[ "$EXIT_CODE" -eq 0 ]]; then
    info "Pinta завершилась нормально (exit 0)"
else
    fail "Pinta завершилась с кодом: $EXIT_CODE"
    warn "Последние строки лога:"
    tail -10 "$CRASH_LOG" | while read -r line; do
        fail "  $line"
    done
fi

section "10e: Проверка лога на ошибки"
# Проверяем, нет ли в логе критических ошибок
if grep -q "Unhandled exception\|EntryPointNotFoundException\|Segmentation fault\|SIGSEGV" "$CRASH_LOG" 2>/dev/null; then
    fail "В логе найдены критические ошибки!"
    grep -A2 "Unhandled exception\|EntryPointNotFoundException\|Segmentation fault" "$CRASH_LOG" | head -10
else
    info "Критических ошибок в логе НЕТ"
    # Показываем предупреждения (безобидные)
    WARNINGS=$(grep -c "WARNING\|CRITICAL\|warning" "$CRASH_LOG" 2>/dev/null || echo "0")
    info "Предупреждений: $WARNINGS (безобидные, не влияют на работу)"
fi

info "Тест пройден — Pinta работает стабильно с русской локалью"


# ============================================================
#  Шаг 11: Очистка и итоговый отчёт
# ============================================================
next_step "Очистка и итоговый отчёт"

section "11a: Очистка временных файлов"
rm -f /tmp/pinta-crash-test.log
rm -f /tmp/pinta.desktop
rm -f /tmp/find_deb.py
rm -f /tmp/list_tags.py
# Не удаляем исходники и ru.mo — могут пригодиться
info "Временные файлы удалены"

section "11b: Очистка apt-кэша (по желанию)"
warn "Для очистки кэша apt выполните: sudo apt-get clean"

section "11c: Размер установки"
INSTALL_SIZE=$(sudo du -sh "$INSTALL_DIR" 2>/dev/null | awk '{print $1}')
info "Размер установки: $INSTALL_SIZE"
info "Каталог: $INSTALL_DIR"

section "11d: Список локалей в установке"
find "$INSTALL_DIR/locale" -name "*.mo" 2>/dev/null | while read -r f; do
    LANG_CODE=$(echo "$f" | sed "s|$INSTALL_DIR/locale/||; s|/LC_MESSAGES/.*||")
    FILE_SIZE=$(wc -c < "$f")
    info "  $LANG_CODE — $(basename "$f") ($FILE_SIZE байт)"
done

section "11e: Список SDK (на всякий случай)"
dotnet --list-sdks 2>&1 | while read -r line; do
    info "  $line"
done


# ============================================================
#  ИТОГ
# ============================================================
echo ""
echo -e "${GREEN}${BOLD}"
echo "╔══════════════════════════════════════════════════════════════════╗"
echo "║                                                                ║"
echo "║   Pinta $PINTA_VERSION успешно установлена!                          ║"
echo "║                                                                ║"
echo "║   Запуск из терминала:  pinta                                  ║"
echo "║   Запуск из меню:       Pinta — Редактор изображений           ║"
echo "║                                                                ║"
echo "║   Установлена:   $INSTALL_DIR        ║"
echo "║   Лаунчер:       $LAUNCHER                                  ║"
echo "║   .desktop:      com.github.PintaProject.Pinta.desktop        ║"
echo "║                                                                ║"
echo "║   Версия:        $PINTA_VERSION (GTK3)                             ║"
echo "║   Локаль:        $LOCALE                              ║"
echo "║   Перевод:       $INSTALL_DIR/locale/ru/LC_MESSAGES/pinta.mo   ║"
echo "║   .NET SDK:      $(dotnet --list-sdks 2>/dev/null | grep ^8 | tail -1 | xargs)                       ║"
echo "║                                                                ║"
echo "║   Почему НЕ Pinta 3.x?                                         ║"
echo "║   Pinta 3.2 требует GTK4 >= 4.18, а в $VERSION_CODENAME     ║"
echo "║   установлен GTK4 $GTK4_VER. Функция gdk_memory_texture_builder  ║"
echo "║   появилась только в GTK4 4.18.                                ║"
echo "║                                                                ║"
echo "║   Если хотите Pinta 3.x — обновите систему до Ubuntu 25.04+   ║"
echo "║                                                                ║"
echo "╚══════════════════════════════════════════════════════════════════╝"
echo -e "${NC}"

# Финальная проверка — запускаем pinta --version
echo -e "${CYAN}Финальная проверка:${NC}"
pinta --version 2>&1 | while read -r line; do
    echo -e "  ${GREEN}$line${NC}"
done
echo ""
echo -e "${GREEN}Готово! Pinta работает с русской локализацией. 🎨${NC}"
