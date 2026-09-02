#!/usr/bin/env bash
#
# ============================================================================
#  fix-grub-efi.sh
#  Автоматическая диагностика и исправление проблемы
#  "GNU GRUB command line при включении ПК" (Linux Mint / Ubuntu / UEFI)
# ============================================================================
#
#  ПРОБЛЕМА, КОТОРУЮ РЕШАЕТ СКРИПТ
#  --------------------------------
#  При включении компьютера сначала появляется чёрный экран с приглашением
#  "grub>" (GNU GRUB в режиме командной строки). Пользователь вынужден
#  вводить "exit", после чего UEFI переходит к следующей загрузочной
#  записи и показывает нормальное графическое меню GRUB с выбором Linux Mint.
#
#  ПРИЧИНА
#  --------------------------------
#  В NVRAM UEFI присутствуют две (или более) записи "ubuntu", указывающие
#  на разные EFI System Partition (ESP):
#    * Boot0001 -> активный ESP (где сейчас стоит Linux Mint)
#    * Boot0003 -> старый/чужой ESP (например, раздел с Windows или с
#                  прежней установкой Ubuntu/Mint), где GRUB стоит, но
#                  не настроен на текущую систему.
#  При этом BootOrder начинается со старой записи (0003,0001,0000),
#  поэтому UEFI первой запускает "неправильный" GRUB.
#
#  ЧТО ДЕЛАЕТ СКРИПТ
#  --------------------------------
#  1. Проверяет окружение (root, UEFI, наличие efibootmgr).
#  2. Сохраняет полную резервную копию NVRAM в файл с timestamp.
#  3. Определяет активный ESP (примонтированный к /boot/efi) и его PARTUUID.
#  4. Разбирает вывод `efibootmgr -v` и находит все записи "ubuntu".
#  5. Сопоставляет PARTUUID каждой записи с PARTUUID активного ESP —
#     та, что совпадает, считается "правильной".
#  6. Формирует новый BootOrder: правильная запись первой, остальные
#     записи сохраняются после неё в исходном порядке.
#  7. Показывает план изменений и просит подтверждение (если не --yes).
#  8. Применяет новый BootOrder через `efibootmgr -o`.
#  9. Проверяет, что изменение вступило в силу, и печатает инструкцию
#     по откату.
#
#  БЕЗОПАСНОСТЬ
#  --------------------------------
#  Скрипт НЕ удаляет:
#    * EFI-разделы (никакие разделы не затрагиваются);
#    * загрузочные записи из NVRAM (команда -o только меняет порядок);
#    * папку EFI/Microsoft (Windows продолжает загружаться);
#    * файлы GRUB/shimx64.efi.
#  Любое изменение полностью обратимо через восстановление BootOrder
#  из резервной копии.
#
#  ИСПОЛЬЗОВАНИЕ
#  --------------------------------
#  sudo bash fix-grub-efi.sh            # интерактивный режим
#  sudo bash fix-grub-efi.sh --yes      # без подтверждения (для автоматизации)
#  sudo bash fix-grub-efi.sh --dry-run  # только показать план, не применять
#  sudo bash fix-grub-efi.sh --help     # справка
#
#  СОВМЕСТИМОСТЬ
#  --------------------------------
#  Linux Mint 21+, Ubuntu 22.04+, любой дистрибутив на базе systemd с
#  UEFI-загрузкой. Требуется bash >= 4 (для ассоциативных массивов).
#
#  АВТОР: сгенерировано на основе реального случая Linux Mint с двумя ESP.
# ============================================================================

set -Eeuo pipefail

# --- Параметры по умолчанию ----------------------------------------------- #
ASSUME_YES=0
DRY_RUN=0
BACKUP_DIR="/root/efi-boot-backups"
TS="$(date +%Y%m%d-%H%M%S)"
BACKUP_FILE="${BACKUP_DIR}/efibootmgr-${TS}.txt"

# --- Цветной вывод (только для терминала) --------------------------------- #
if [[ -t 1 ]]; then
    C_RED=$'\033[1;31m'
    C_GREEN=$'\033[1;32m'
    C_YELLOW=$'\033[1;33m'
    C_BLUE=$'\033[1;34m'
    C_CYAN=$'\033[1;36m'
    C_BOLD=$'\033[1m'
    C_RST=$'\033[0m'
else
    C_RED=''; C_GREEN=''; C_YELLOW=''; C_BLUE=''; C_CYAN=''; C_BOLD=''; C_RST=''
fi

log()  { printf '%s==> %s%s\n' "${C_BLUE}" "$*" "${C_RST}"; }
ok()   { printf '%s[ OK ]%s %s\n' "${C_GREEN}" "${C_RST}" "$*"; }
warn() { printf '%s[WARN]%s %s\n' "${C_YELLOW}" "${C_RST}" "$*"; }
err()  { printf '%s[ERR ]%s %s\n' "${C_RED}" "${C_RST}" "$*" >&2; }
hr()   { printf -- '--------------------------------------------------------------------------\n'; }

# --- Обработка аргументов ------------------------------------------------- #
while [[ $# -gt 0 ]]; do
    case "$1" in
        --yes|-y) ASSUME_YES=1; shift ;;
        --dry-run) DRY_RUN=1; shift ;;
        --help|-h)
            sed -n '2,/^# ====/p' "$0" | sed 's/^# \?//'
            exit 0
            ;;
        *)
            err "Неизвестный аргумент: $1"
            err "Использование: sudo bash $0 [--yes|--dry-run|--help]"
            exit 2
            ;;
    esac
done

# --- Ловушка ошибок (откат не нужен — NVRAM ещё не менялась) ------------- #
on_error() {
    local rc=$?
    local line=$1
    err "Скрипт прерван на строке $line (код $rc)."
    err "NVRAM не была изменена — загрузка компьютера не нарушена."
    exit "$rc"
}
trap 'on_error $LINENO' ERR

# ============================================================================
#  ШАГ 1/6. ПРОВЕРКА ОКРУЖЕНИЯ
# ============================================================================
hr
log "Шаг 1/6. Проверка окружения"
hr

# 1.1. root
if [[ $EUID -ne 0 ]]; then
    err "Скрипт должен запускаться от root (используйте sudo)."
    err "  Пример:  sudo bash $0"
    exit 1
fi
ok "Запущен от root."

# 1.2. UEFI-режим
if [[ ! -d /sys/firmware/efi ]]; then
    err "Система загружена в режиме Legacy BIOS, а не UEFI."
    err "Этот скрипт предназначен только для UEFI-систем."
    err "Если у вас Legacy — проблема решается переустановкой GRUB на MBR,"
    err "это совсем другая процедура."
    exit 1
fi
ok "Система загружена в UEFI-режиме."

# 1.3. efibootmgr
if ! command -v efibootmgr >/dev/null 2>&1; then
    err "Не найдена команда 'efibootmgr'."
    err "Установите её:  sudo apt install efibootmgr"
    exit 1
fi
ok "efibootmgr найден: $(command -v efibootmgr)"

# 1.4. findmnt / lsblk
if ! command -v findmnt >/dev/null 2>&1; then
    err "Не найдена команда 'findmnt' (часть util-linux)."
    err "Установите её:  sudo apt install util-linux"
    exit 1
fi
if ! command -v lsblk >/dev/null 2>&1; then
    err "Не найдена команда 'lsblk' (часть util-linux)."
    exit 1
fi
ok "findmnt и lsblk доступны."

# 1.5. bash version (нужны ассоциативные массивы)
if ((BASH_VERSINFO[0] < 4)); then
    err "Требуется bash >= 4.0 (текущая версия: ${BASH_VERSION})."
    err "На старых системах обновите bash или выполните шаги вручную."
    exit 1
fi
ok "bash ${BASH_VERSION} — поддерживает ассоциативные массивы."

# ============================================================================
#  ШАГ 2/6. РЕЗЕРВНАЯ КОПИЯ NVRAM
# ============================================================================
hr
log "Шаг 2/6. Сохранение резервной копии NVRAM"
hr

mkdir -p "$BACKUP_DIR"
{
    echo "# efibootmgr backup"
    echo "# Host:    $(hostname)"
    echo "# Date:    $(date -Iseconds)"
    echo "# User:    ${SUDO_USER:-$(whoami)}"
    echo "# Script:  fix-grub-efi.sh"
    echo "#"
    echo "# Восстановление прежнего BootOrder:"
    echo "#   sudo efibootmgr -o \$(grep '^BootOrder:' '$BACKUP_FILE' | awk '{print \$2}')"
    echo
    efibootmgr -v
} > "$BACKUP_FILE"
chmod 600 "$BACKUP_FILE"
ok "Резервная копия сохранена: $BACKUP_FILE"
echo "    Размер: $(wc -c < "$BACKUP_FILE") байт."
echo

# ============================================================================
#  ШАГ 3/6. ОПРЕДЕЛЕНИЕ АКТИВНОГО ESP
# ============================================================================
hr
log "Шаг 3/6. Определение активного ESP (/boot/efi)"
hr

# 3.1. Что примонтировано к /boot/efi
ESP_DEVICE="$(findmnt -n -o SOURCE /boot/efi 2>/dev/null || true)"
if [[ -z "$ESP_DEVICE" ]]; then
    warn "/boot/efi не смонтирован. Пытаюсь определить ESP автоматически..."
    # Ищем раздел с типом "EFI System"
    ESP_DEVICE="$(lsblk -n -o NAME,PARTTYPENAME -l 2>/dev/null \
                  | awk '/EFI System/ {print "/dev/"$1; exit}' || true)"
    if [[ -z "$ESP_DEVICE" ]]; then
        err "Не удалось автоматически определить EFI System Partition."
        err "Примонтируйте ESP вручную и перезапустите скрипт:"
        err "  sudo mkdir -p /boot/efi"
        err "  sudo mount /dev/sdXN /boot/efi"
        err "  sudo bash $0"
        exit 1
    fi
    warn "Найден кандидат на ESP: $ESP_DEVICE. Монтирую в /boot/efi..."
    mount "$ESP_DEVICE" /boot/efi
fi
ok "Активный ESP: $ESP_DEVICE (примонтирован к /boot/efi)"

# 3.2. Получаем PARTUUID активного ESP (используется в HD(...,GPT,<uuid>,...) в efibootmgr)
ESP_PARTUUID="$(lsblk -n -o PARTUUID "$ESP_DEVICE" 2>/dev/null | head -n1 | tr '[:upper:]' '[:lower:]' || true)"
if [[ -z "$ESP_PARTUUID" ]]; then
    # fallback на blkid
    ESP_PARTUUID="$(blkid -s PARTUUID -o value "$ESP_DEVICE" 2>/dev/null | tr '[:upper:]' '[:lower:]' || true)"
fi
if [[ -z "$ESP_PARTUUID" ]]; then
    err "Не удалось получить PARTUUID для $ESP_DEVICE."
    err "Это может означать, что раздел не является GPT — скрипт работает только с GPT/UEFI."
    exit 1
fi
ok "PARTUUID активного ESP: $ESP_PARTUUID"

# 3.3. Проверим, что на ESP действительно лежит рабочий загрузчик ubuntu
if [[ ! -f /boot/efi/EFI/ubuntu/shimx64.efi ]]; then
    warn "На $ESP_DEVICE нет файла /EFI/ubuntu/shimx64.efi."
    warn "Возможно, активный ESP не содержит загрузчика Linux Mint — продолжаем,"
    warn "но будьте внимательны: возможно, правильный ESP на другом разделе."
    warn "Проверьте вручную:  sudo find /boot/efi/EFI -maxdepth 2 -type f"
else
    ok "Найден рабочий загрузчик: /boot/efi/EFI/ubuntu/shimx64.efi"
fi

# ============================================================================
#  ШАГ 4/6. РАЗБОР NVRAM И ПОИСК ДУБЛИРУЮЩИХ ЗАПИСЕЙ
# ============================================================================
hr
log "Шаг 4/6. Анализ загрузочных записей NVRAM"
hr

# Полный вывод efibootmgr -v
EFIOUT="$(efibootmgr -v)"

# Текущий BootOrder и BootCurrent
CURRENT_ORDER="$(awk '/^BootOrder:/ {print $2; exit}' <<<"$EFIOUT")"
BOOT_CURRENT="$(awk '/^BootCurrent:/ {print $2; exit}' <<<"$EFIOUT")"

if [[ -z "$CURRENT_ORDER" ]]; then
    err "Не удалось определить текущий BootOrder."
    err "Вывод efibootmgr выглядит некорректно. Выход."
    exit 1
fi
ok "Текущий BootOrder: $CURRENT_ORDER"

if [[ -n "$BOOT_CURRENT" ]]; then
    ok "BootCurrent (запись, с которой загружена система): $BOOT_CURRENT"
else
    warn "BootCurrent не определён — возможно, загрузка была через fallback NVRAM."
fi

echo
echo "Найденные загрузочные записи:"
echo

# Ассоциативные массивы: ключ = "0001" (4-значный hex)
declare -A ENTRIES_DESC=()
declare -A ENTRIES_PARTUUID=()
declare -A ENTRIES_PATH=()
declare -A ENTRIES_IS_UBUNTU=()

# Регулярка: BootXXXX[* ]<пробелы>description<TAB>HD(...)
# Описание отделяется от HD(...) табом (формат efibootmgr -v).
LINE_RE='^Boot([0-9A-Fa-f]{4})[* ]?[[:space:]]+(.*)$'
PUUID_RE='HD\([0-9]+,GPT,([0-9A-Fa-f-]+),'
PATH_RE='/File\(([^)]+)\)'

while IFS= read -r line; do
    [[ "$line" =~ $LINE_RE ]] || continue
    bid="${BASH_REMATCH[1]}"
    rest="${BASH_REMATCH[2]}"

    # description = всё до первой табуляции
    desc="${rest%%$'\t'*}"
    # trim trailing whitespace
    desc="${desc%"${desc##*[![:space:]]}"}"

    # partuuid из HD(N,GPT,<uuid>,...)
    puuid=""
    if [[ "$rest" =~ $PUUID_RE ]]; then
        puuid="${BASH_REMATCH[1],,}"   # lowercase
    fi

    # путь к .efi
    efi_path=""
    if [[ "$rest" =~ $PATH_RE ]]; then
        efi_path="${BASH_REMATCH[1]}"
    fi

    ENTRIES_DESC[$bid]="$desc"
    ENTRIES_PARTUUID[$bid]="$puuid"
    ENTRIES_PATH[$bid]="$efi_path"

    # Считаем запись "ubuntu-подобной", если:
    #   - описание содержит ubuntu или mint, ИЛИ
    #   - путь к .efi указывает на \EFI\ubuntu\... (Linux Mint тоже ставит туда)
    if [[ "$desc" == *ubuntu* || "$desc" == *mint* || "$efi_path" == *\\EFI\\ubuntu\\* ]]; then
        ENTRIES_IS_UBUNTU[$bid]=1
    else
        ENTRIES_IS_UBUNTU[$bid]=0
    fi

    # Печать строки
    marker=" "
    if [[ -n "$BOOT_CURRENT" && "$bid" == "$BOOT_CURRENT" ]]; then
        marker="${C_GREEN}>${C_RST}"
    fi
    printf '  %s Boot%s  %-22s  partuuid=%-38s  path=%s\n' \
        "$marker" "$bid" "$desc" "${puuid:-(нет)}" "${efi_path:-(нет)}"
done <<<"$EFIOUT"

echo

# ============================================================================
#  ШАГ 5/6. ОПРЕДЕЛЕНИЕ "ПРАВИЛЬНОЙ" ЗАПИСИ
# ============================================================================
hr
log "Шаг 5/6. Поиск правильной ubuntu-записи (совпадающей с активным ESP)"
hr

CORRECT_ID=""
DUPLICATE_IDS=()

# Перебираем только ubuntu-записи
for bid in "${!ENTRIES_DESC[@]}"; do
    [[ "${ENTRIES_IS_UBUNTU[$bid]:-0}" == "1" ]] || continue
    puuid="${ENTRIES_PARTUUID[$bid]}"
    if [[ "$puuid" == "$ESP_PARTUUID" ]]; then
        if [[ -z "$CORRECT_ID" ]]; then
            CORRECT_ID="$bid"
        else
            warn "Аномалия: несколько записей ссылаются на активный ESP."
            warn "  Уже выбрана: Boot$CORRECT_ID"
            warn "  Также совпадает: Boot$bid"
            warn "Будет использована первая (это безопасно)."
        fi
    else
        DUPLICATE_IDS+=("$bid")
    fi
done

if [[ -z "$CORRECT_ID" ]]; then
    err "Не найдена ubuntu-запись, ссылающаяся на активный ESP."
    err "  Активный ESP:   $ESP_DEVICE"
    err "  PARTUUID ESP:   $ESP_PARTUUID"
    err
    err "Возможные причины:"
    err "  1. На активном ESP нет /EFI/ubuntu/shimx64.efi"
    err "  2. Запись была удалена из NVRAM вручную"
    err "  3. Linux Mint установлен на другом диске, а /boot/efi указывает на чужой ESP"
    err
    err "Без правильной записи менять BootOrder небезопасно — выход."
    err "Резервная копия NVRAM: $BACKUP_FILE"
    exit 3
fi

ok "Правильная ubuntu-запись: Boot$CORRECT_ID"
ok "  описание:  ${ENTRIES_DESC[$CORRECT_ID]}"
ok "  partuuid:  ${ENTRIES_PARTUUID[$CORRECT_ID]}"
ok "  efi-путь:  ${ENTRIES_PATH[$CORRECT_ID]}"

if ((${#DUPLICATE_IDS[@]} == 0)); then
    warn "Дублирующих ubuntu-записей не найдено."
    warn "Возможно, 'grub>' появляется по другой причине (например, сломанный"
    warn "grub.cfg на самом ESP). Если смена BootOrder не поможет — нужно"
    warn "будет переустановить GRUB:  sudo grub-install --target=x86_64-efi"
    warn "                              --efi-directory=/boot/efi --bootloader-id=ubuntu"
else
    for d in "${DUPLICATE_IDS[@]}"; do
        warn "Найдена дублирующая ubuntu-запись: Boot$d"
        warn "  описание:  ${ENTRIES_DESC[$d]}"
        warn "  partuuid:  ${ENTRIES_PARTUUID[$d]} (НЕ активный ESP)"
    done
fi

echo

# ============================================================================
#  ШАГ 6/6. ФОРМИРОВАНИЕ И ПРИМЕНЕНИЕ НОВОГО BootOrder
# ============================================================================
hr
log "Шаг 6/6. Формирование нового BootOrder"
hr

# Разбиваем текущий BootOrder на массив
IFS=',' read -ra OLD_ORDER <<<"$CURRENT_ORDER"

# Новый порядок: правильная запись первой, затем все остальные в исходном порядке
NEW_ORDER=("$CORRECT_ID")
for id in "${OLD_ORDER[@]}"; do
    [[ "$id" == "$CORRECT_ID" ]] && continue
    NEW_ORDER+=("$id")
done

# Собираем обратно в строку через запятую
NEW_ORDER_STR="$(IFS=,; echo "${NEW_ORDER[*]}")"

echo "Старый BootOrder:  $CURRENT_ORDER"
echo "Новый BootOrder:  $NEW_ORDER_STR"
echo

# Если ничего не меняется — выходим без изменений
if [[ "$NEW_ORDER_STR" == "$CURRENT_ORDER" ]]; then
    ok "BootOrder уже корректен — правильная запись и так первая."
    ok "Если 'grub>' всё ещё появляется, проблема НЕ в порядке записей."
    ok "Возможные причины:"
    ok "  * Сломан grub.cfg на ESP — переустановите GRUB (см. подсказку выше)."
    ok "  * UEFI падает в fallback-режим из-за неверного BootXXXX."
    ok "  * В NVRAM есть кривая запись, несовместимая с вашим UEFI."
    ok
    ok "Резервная копия NVRAM на всякий случай сохранена: $BACKUP_FILE"
    exit 0
fi

# План изменений
echo "${C_BOLD}План изменений:${C_RST}"
echo "  1. Применить новый BootOrder: $NEW_ORDER_STR"
echo "  2. НЕ удалять никакие Boot-записи (команда -o только меняет порядок)."
echo "  3. НЕ удалять никакие файлы на ESP."
echo "  4. НЕ трогать EFI/Microsoft (Windows продолжит загружаться)."
echo
echo "${C_BOLD}Откат${C_RST} (если что-то пойдёт не так):"
echo "  sudo efibootmgr -o $CURRENT_ORDER"
echo "  или используйте резервную копию:  $BACKUP_FILE"
echo

# --- Режим dry-run -------------------------------------------------------- #
if [[ "$DRY_RUN" == "1" ]]; then
    warn "Режим --dry-run: изменения НЕ применяются."
    warn "Уберите --dry-run, чтобы применить изменение на самом деле."
    exit 0
fi

# --- Подтверждение -------------------------------------------------------- #
if [[ "$ASSUME_YES" != "1" ]]; then
    read -r -p $'Применить изменения? [y/N] ' answer
    answer="${answer,,}"
    if [[ "$answer" != "y" && "$answer" != "yes" && "$answer" != "д" && "$answer" != "да" ]]; then
        warn "Отменено пользователем. NVRAM не изменена."
        warn "Резервная копия всё равно сохранена: $BACKUP_FILE"
        exit 0
    fi
fi

# --- Применение ----------------------------------------------------------- #
log "Применение: efibootmgr -o $NEW_ORDER_STR"
if ! efibootmgr -o "$NEW_ORDER_STR" >/dev/null 2>&1; then
    err "Не удалось применить новый BootOrder."
    err "Проверьте вручную:  efibootmgr"
    err "Возможно, NVRAM переполнена или защищена от записи."
    err "Резервная копия: $BACKUP_FILE"
    exit 4
fi
ok "Команда выполнена успешно."

# --- Верификация ---------------------------------------------------------- #
echo
NEW_CURRENT="$(efibootmgr | awk '/^BootOrder:/ {print $2; exit}')"
if [[ "$NEW_CURRENT" == "$NEW_ORDER_STR" ]]; then
    ok "Верификация: новый BootOrder вступил в силу."
    ok "  Текущий BootOrder: $NEW_CURRENT"
else
    warn "Верификация: BootOrder в NVRAM = $NEW_CURRENT"
    warn "Ожидался: $NEW_ORDER_STR"
    warn "Некоторые UEFI-прошивки корректируют порядок самостоятельно"
    warn "(добавляют скрытые записи или меняют очерёдность)."
    warn "Если 'grub>' больше не появляется — всё в порядке."
fi

# --- Итог ----------------------------------------------------------------- #
echo
hr
echo "${C_BOLD}Готово.${C_RST}"
hr
echo
echo "Что было сделано:"
echo "  1. Сохранена резервная копия NVRAM: $BACKUP_FILE"
echo "  2. BootOrder изменён:"
echo "       было:  $CURRENT_ORDER"
echo "       стало: $NEW_CURRENT"
echo "  3. Записи и файлы НЕ удалялись — операция полностью обратима."
echo
echo "${C_BOLD}Следующие шаги:${C_RST}"
echo "  1. Перезагрузите компьютер:  sudo reboot"
echo "  2. Проверьте, что 'grub>' больше не появляется."
echo "  3. Если всё нормально — операция завершена."
echo "  4. Если 'grub>' всё ещё появляется:"
echo "       a. Восстановите прежний порядок:  sudo efibootmgr -o $CURRENT_ORDER"
echo "       b. Пришлите вывод 'efibootmgr -v' и 'sudo find /boot/efi/EFI -maxdepth 2 -type f'"
echo "          для дополнительной диагностики."
echo "  5. Через 1-2 недели стабильной работы можно (опционально) удалить"
echo "     дублирующие записи BootXXXX командой:"
echo "       sudo efibootmgr -b XXXX -B"
echo "     где XXXX — номер лишней записи (например, 0003)."
echo "     Но это НЕ обязательно — они просто не будут запускаться."
echo
echo "Резервная копия NVRAM до изменения: $BACKUP_FILE"
echo

exit 0
