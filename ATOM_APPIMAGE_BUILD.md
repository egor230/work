# Atom AppImage (atom-amd64.deb → atom.AppImage) — паспорт сборки
Готово. Что сделано:

- **Скроллбар боковой панели** (`~/.atom/styles.less`): для `.tree-view` теперь обычный 8px со стандартным ползунком Atom; утолщённые 32px остались на редакторе/вкладках/панелях. Это пользовательский слой — в AppImage не входит, пересборка не нужна (конфиг-ключа для ширины скроллбара в Atom не существует, только таблица стилей).
- **Кнопки Найти/Заменить**: `cpp-tool-bar` 1.2.0 → **1.3.0** — Найти (`fa-search`, `find-and-replace:show`, Ctrl+F) и Заменить (`fa-exchange-alt`, `find-and-replace:show-replace`), всего 12 кнопок. Иконки и команды проверены по `iconsets.css` и find-and-replace в `app.asar`.
- **AppImage пересобран** (v3, 186 МБ, `appimagetool --comp zstd --no-appstream`); версии локальная и встроенная совпадают (1.3.0) — AppRun не затрёт правки. Бэкап старой сборки: `/tmp/atom.AppImage.v2.bak`; распакованное `squashfs-root/` в «linux must have» можно удалить.
- **ATOM_APPIMAGE_BUILD.md**: в начале добавлен раздел «Как менять (быстрый старт)» (таблица что/где/ нужна ли пересборка + главное правило о bump версии), добавлен раздел v3, обновлены таблица кнопок (12 шт., добавлена ранее неучтённая «Сохранить») и чек-лист.
Дата: 2026-09-13. Итоговый файл: `atom.AppImage` (186 МБ, Atom 1.60.0 / Electron 9.4.4 / Node 12.14.1), рядом лежит исходный `atom-amd64.deb` (2022, последний релиз Atom перед sunset). Актуальная сборка — **v3 (2026-09-24)**.

## Как менять (быстрый старт)

Два слоя настроек: **пользовательский** (`~/.atom/`, в AppImage НЕ входит, применяется сразу, без пересборки) и **встроенный** (пакеты внутри AppImage — нужна пересборка).

| Что меняем | Где править | Пересборка |
|---|---|---|
| Настройки (шрифты, видимость панелей, размер иконок `tool-bar` (`iconSize`), поведение редактора) | `~/.atom/config.cson` (в Atom: File → Config) | нет |
| Стили, скроллбары (толщина прокрутки и т.п.) | `~/.atom/styles.less` (в Atom: File → Stylesheet) | нет |
| Сниппеты Lua (lualoader) | `~/.atom/snippets.cson` | нет |
| Кнопки панели инструментов (добавить/убрать/переименовать) | `~/.atom/packages/cpp-tool-bar/lib/cpp-tool-bar.js` + `version` в `package.json` → скопировать пакет в `AppDir/usr/share/atom/resources/extra-packages/` → пересобрать | **да** |
| Компактность кнопок (×0.9) | `tool-bar` → `styles/tool-bar.less`, миксин `.tool-bar-size` | **да** |
| Иконки панели | проверять имя по факту в `tool-bar/dist/iconsets.css` (FA/Octicon…) | — |

**Главное правило пересборки**: AppRun синхронизирует `extra-packages/*` → `~/.atom/packages/` только если `version` в `package.json` отличается (см. `sync_bundled_packages` в AppRun). Поэтому любое изменение cpp-tool-bar/tool-bar = bump версии в `package.json` (1.2.0 → 1.3.0 и т.д.) + копирование в extra-packages + `appimagetool`. Без bump'а AppRun не перекачает пакет; если же локальная и встроенная версии совпадут, AppRun не затрёт твои локальные правки.

Рецепт пересборки (подробно — ниже, «Как пересобрать»): `./atom.AppImage --appimage-extract` → правки в `squashfs-root/` → `ARCH=x86_64 ./appimagetool --comp zstd --no-appstream squashfs-root atom.AppImage`.

## Обновление 2026-09-14 (v2 AppImage)

Версии пакетов подняты и пересобраны: **cpp-tool-bar 1.1.0 → 1.2.0**, **tool-bar 1.4.4 → 1.4.5**.
В `ATOM_APPIMAGE_BUILD.md` и в `README.md` пакетов отражены изменения:

1. **Вывод сборки — нижняя док-панель, а не модальное окно.** В `cpp-tool-bar.js` `atom.workspace.addModalPanel` заменён на `atom.workspace.addBottomPanel` — консоль «Консоль сборки C++» всегда живёт в нижнем доке (как в обычных IDE), ничего не перекрывает и не требует закрытия. Кнопки панели: «Очистить», «Закрыть». Показ/скрытие — `cpp-tool-bar:toggle-output` (**Ctrl+Alt+O**, добавлен в keymaps), высоту можно менять за верхнюю границу. Стили — в `styles/cpp-tool-bar.less` (`.cpp-tool-bar-output`, высота 220px, `flex` + скролл лога).
2. **Кнопки тулбара компактнее на 10%.** Правка в самом `tool-bar → styles/tool-bar.less`: миксин `.tool-bar-size(@size)` теперь использует `@s: @size * 0.9` (было — голый `@size`). Действует для любого `iconSize` (12…32px). Был испробован вариант перекрытия из cpp-tool-bar.less с более высокой специфичностью (`.tool-bar.tool-bar-24px .tool-bar-btn`) — НЕ сработал из-за алфавитного порядка активации пакетов (cpp-tool-bar грузится РАНЬШЕ tool-bar, его стили проигрывают при равной специфичности, а tool-bar.css выигрывает). Поэтому масштабирование внесено в ПОРОЖДАЮЩИЙ пакет tool-bar.
3. Проверено E2E через init.coffee (методика «Отладка» выше): 9 кнопок, кнопка 50×50px → **45.2×45.2px**, иконка 24px → **21.6px**; build → выхлоп g++ идёт в нижнюю док-панель (220px, шрифт 12px), без модалок.

Порядок пересборки (v2): правки в `~/.atom/packages/{cpp-tool-bar,tool-bar}` → `node --check lib/cpp-tool-bar.js` → скопировать оба пакета в `AppDir/usr/share/atom/resources/extra-packages/` → `ARCH=x86_64 appimagetool --comp zstd --no-appstream AppDir atom.AppImage` → заменить файл в «linux must have» (не забыть дождаться отмонтирования старого инстанса). Версии менять ОБЯЗАТЕЛЬНО — иначе AppRun-синхронизация не перекачает пакеты в `~/.atom/packages`.

## Обновление 2026-09-24 (v3 AppImage)

1. **Кнопки «Найти» и «Заменить» на панели инструментов.** `cpp-tool-bar` 1.2.0 → **1.3.0**, кнопок стало 10 → **12**. Новые стоят в группе редактирования, после «Вставить» и перед «Закомментировать»:
   - **Найти** — иконка `fa-search`, команда `find-and-replace:show` (Ctrl+F);
   - **Заменить** — иконка `fa-exchange-alt`, команда `find-and-replace:show-replace` (шортката по умолчанию на Linux нет — только `cmd-alt-f` на macOS; кнопка — единственный быстрый путь).
   - Имена иконок проверены по `tool-bar/dist/iconsets.css` (`search` и `exchange-alt` существуют), команды — по find-and-replace внутри `app.asar` (обе команды есть, меню «Replace in Buffer»).
   - Заодно в паспорт добавлена кнопка **Сохранить** (`fa-save`, `core:save`, Ctrl+S) — она стояла в коде ещё с v2, но в таблице ниже не отражалась.
   - `node --check lib/cpp-tool-bar.js` — ОК; обновлены `package.json` (version + description) и `README.md` пакета.
2. **Скроллбар боковой панели (tree-view) — обычный, не утолщённый.** Пользовательский слой `~/.atom/styles.less`, в AppImage НЕ входит — пересобирать не нужно. Раньше утолщение 32px применялось ко всему (редактор, дерево, панели, вкладки); теперь для `.tree-view` добавлен отдельный блок: **8px**, ползунок `rgba(150,150,150,0.33)` — стандартный вид Atom, как в редакторе. Утолщённые скроллбары остались на редакторе/панелях/вкладках. Специфичность `.tree-view::-webkit-scrollbar` (0,1,1) перебивает глобальный `::-webkit-scrollbar` (0,0,1), поэтому порядок правил не важен. ВАЖНО: конфиг-ключа для ширины скроллбара в Atom нет — только пользовательская таблица стилей.
3. Пересборка: `--appimage-extract` старого AppImage → `rm -rf extra-packages/cpp-tool-bar && cp -r ~/.atom/packages/cpp-tool-bar extra-packages/` → `ARCH=x86_64 appimagetool --comp zstd --no-appstream squashfs-root atom.AppImage`. `tool-bar` не трогали — остался 1.4.5. Бэкап v2-сборки: `/tmp/atom.AppImage.v2.bak`. Распакованное дерево `squashfs-root/` в «linux must have» можно удалить (регенерируется `--appimage-extract`).

## Что внутри готового AppImage

1. **deb, распакованный в AppDir** (`usr/bin/atom`, `usr/share/atom/...`)
2. **AppRun** (самописный, см. ниже)
3. **Пакет `tool-bar` 1.4.5** (atom-community, скачан с web.archive.org) — контейнер панели + иконки (+масштабирование кнопок ×0.9)
4. **Пакет `cpp-tool-bar` 1.3.0** (самописный) — 12 кнопок + сборка C++ через g++ + нижняя док-консоль
5. Оба пакета лежат в `usr/share/atom/resources/extra-packages/` внутри AppImage

## Кнопки панели (top position, иконки Font Awesome) — 12 шт.

| Кнопка | Иконка FA | Команда | Шорткат |
|---|---|---|---|
| Открыть | fa-folder-open | application:open-file | Ctrl+O |
| Сохранить | fa-save | core:save | Ctrl+S |
| Собрать | fa-cogs | cpp-tool-bar:build | Ctrl+Alt+B / F6 |
| Собрать+запустить | fa-play | cpp-tool-bar:run | Ctrl+Alt+R |
| Отменить | fa-undo | core:undo | Ctrl+Z |
| Вернуть | fa-redo | core:redo | Ctrl+Shift+Z |
| Вырезать | fa-cut | core:cut | Ctrl+X |
| Копировать | fa-copy | core:copy | Ctrl+C |
| Вставить | fa-clipboard | core:paste | Ctrl+V |
| Найти | fa-search | find-and-replace:show | Ctrl+F |
| Заменить | fa-exchange-alt | find-and-replace:show-replace | — (только macOS: cmd-alt-f) |
| Закомментировать | fa-comment-dots | editor:toggle-line-comments | Ctrl+/ |

Иконки: в дистрибутиве tool-bar иконки FA/Foundation/Ionicons встроены в `dist/iconsets.css` + woff-шрифты в `iconsets/`. ВАЖНО: имена проверять по фактическому наличию в iconsets.css (например `scissors` НЕ существует, нужен `cut`; `comment-discussion` не существует — `comment-dots`; `repo-push`/`corner-down-left` — octicon-набора нет в этой сборке).

Сборка: `g++ -Wall -Wextra -O2 -std=c++17 -o <файл_без_ext> <файл>`; `.c` → `-std=c17`; `.h/.hpp` → `-fsyntax-only` (заголовок не имеет main). Вывод — в нижней док-панели «Консоль сборки C++» (`.cpp-toolbar-log`; v2: заменила модалку addModalPanel→addBottomPanel), итог — в уведомлениях. Настройки: `cpp-tool-bar.compilerPath` (default `g++`), `cpp-tool-bar.compilerArgs` (доп. флаги).

## Как пересобрать (полный рецепт)

### 1. Распаковать deb → AppDir

```bash
mkdir AppDir && dpkg-deb -x atom-amd64.deb AppDir
cp AppDir/usr/share/applications/atom.desktop AppDir/
cp AppDir/usr/share/pixmaps/atom.png AppDir/       # 1024x1024
ln -sf atom.png AppDir/.DirIcon
sed -i 's|^Exec=.*|Exec=atom %F|' AppDir/atom.desktop
rm -f AppDir/usr/share/atom/chrome-sandbox        # setuid в squashfs всё равно не работает (nosuid)
```

### 2. AppRun (ключевые моменты)

- `$0` через `readlink -f` → HERE (runtime AppImage передаёт `<mountpoint>/AppRun` в argv[0]); `$APPDIR` экспортируется
- PATH += dugite-git (`app.asar.unpacked/node_modules/dugite/git/bin`)
- `ELECTRON_RUN_AS_NODE=1` → напрямую exec бинаря (нужно для apm)
- **Синхронизация пакетов**: `sync_bundled_packages` копирует `usr/share/atom/resources/extra-packages/*` в `~/.atom/packages/`, но только если version в package.json отличается (сравнение через python3 + json). Причина — ниже.

### 3. Упаковка

```bash
ARCH=x86_64 appimagetool --comp zstd --no-appstream AppDir atom.AppImage
# appimagetool лежит в той же папке ("linux must have/appimagetool", static-pie)
```

`--no-appstream` — AppStream-валидацию atom не проходит, она не нужна.

## Пакет cpp-tool-bar (главные грабли)

Структура: `package.json` + `lib/cpp-tool-bar.js` + `styles/cpp-tool-bar.less` + `keymaps/` + `menus/` + `README.md`.

- `consumedServices: {"tool-bar": {"versions": {"1": "consumeToolBar"}}}` — сервис tool-bar даёт объект `toolBar(name)`, у него `addButton/addSpacer`
- **НЕ ставить `activationCommands` в package.json!** Иначе пакет активируется лениво (только по команде) и панель не появится. В отладке это проявляется как `active: false, mainModule: false`
- `addButton({tooltip, icon, iconset:'fa', callback, priority})`; приоритеты через spacer'ы дают разделители
- Логика сборки: `BufferedProcess` (atom API), компилятор из конфига, `onWillThrowError` ловит отсутствие g++
- Тултипы с кириллицей работают, hotkeys — в keymaps/*.cson

## ГЛАВНАЯ грабля: bundled-пакеты нельзя добавить в asar

Пытался вшить tool-bar/cpp-tool-bar прямо в `app.asar` (bin-хирургия заголовка: дописать файлы в конец data, пересобрать pickle-заголовок, добавить в `packageDependencies` корневого package.json). Всё технически корректно — `fs.readFileSync` и asar-листинги видят пакеты, `packageDependencies` = 95.

**НО**: `require('../package.json')` в `src/package-manager.js` возвращает СТАРЫЙ объект (93 deps) — Atom 1.60 запекает результат require в v8 startup snapshot (`v8_context_snapshot.bin`/`snapshot_blob.bin`). Пути: `getAvailablePackages()` читает deps из замыкания → пакеты невидимы, resolvePackagePath их при этом находит (несоответствие!). Симптом: `nDeps: 93, has tool-bar: false, avail: false`.

Отсюда решение — extra-packages + синхронизация в `~/.atom/packages` при каждом запуске (AppRun). User-пакеты Atom читает с диска динамически, это работает.

Черновая хирургия asar делалась скриптами (формат asar: `[sizePickle 8B][headerPickle: {uint32 payloadSize}{int32 strLen}{json}][data]`, offsets в header — строки относительно начала data). Если понадобится снова: проще держать asar НЕТРОНУТЫМ.

## Отладка (как проверял)

- **init.coffee** в `~/.atom/` — setTimeout + dump в /tmp-файл. Работает только после полной загрузки окна (~15с), иначе рендер ещё не готов. Не забыть УДАЛЯТЬ init.coffee после отладки
- `atom.packages.getAvailablePackages().map(p->p.name)` — видимость пакетов
- `document.querySelector('.tool-bar')?.querySelectorAll('button').length` — панель (ожидалось 12, v3)
- Диспетч команд: `atom.commands.dispatch atom.views.getView(atom.workspace), 'cpp-tool-bar:build'`
- Проверка результата: `fs.existsSync('/tmp/.../hello')` + spawnSync бинарника
- При открытии файла аргументом путь редактора появляется НЕ сразу — нужен poll `getActiveTextEditor().getPath()` каждые 1.5с
- Активные пакеты после старта: tool-bar=active, cpp-tool-bar=active (после удаления activationCommands)

## Известные флаки

1. **GPU-краш при старте** (замечен и на нетронутом deb-билде): `FATAL:gpu_data_manager_impl_private.cc(439)] GPU process isn't usable. Goodbye.` — Atom умирает молча (в логе только nemo_action cp-ошибка, 0 процессов). Лечение: просто перезапустить (обычно 1-я или 2-я попытка стартует), стабильно помогает `--disable-gpu`. При краше Atom посылает wget на atom.io/crash_reports (301 → github.blog sunsetting-atom) — безвредно.
2. Wrapper `usr/bin/atom` на старте пишет `cp: resources/linux/desktopeniroment/cinnamon/atom.nemo_action ...` — безвредно (проверка cinnamon DESKTOP_SESSION в окружении).
3. **pkill-паттерны обязаны содержать брекет** (`'atom-wor[k]/AppDir'`, `'mount_ato[m]'`, `'ato[m]/atom'`), иначе pkill -f убивает сам bash-процесс опенкода. Копирование последовательностей команд с pkill в ОДНОМ bash-вызове часто убивает shell — pkill выносить отдельным вызовом.
4. Electron 9 в монтe AppImage: chrome-sandbox (setuid) удалён; userns-песочница работает (`kernel.unprivileged_userns_clone=1` на Linux Mint 22.3).
5. `--load-extension` и CDP-трюки для atom не нужны — он Electron, диагностика через init.coffee.
6. tesseract-скриншот-проверки часто ловят НЕ то окно — надёжнее DOM-дампы через init.coffee.

## tool-bar: где взять в 2026 (Atom закрыт в 2022)

atom.io (301 → sunsetting), но **web.archive.org отдаёт API и tarball'ы**: API `https://web.archive.org/web/2im_/https://atom.io/api/packages/<имя>`, в ответе `versions.<v>.dist.tarball` — прямая ссылка на archived tarball (tool-bar 1.4.4, dist-сборка внутри, без npm install). Так же доступны file-icons 2.1.47 и другие пакеты.

## Конфиг пользователя (~/.atom/config.cson)

```cson
"*":
  "tool-bar":
    position: "Top"
    fullWidth: true
    visible: true
    iconSize: "24px"
  "cpp-tool-bar":
    visible: true
  core:
    audioBeep: false
```

`iconSize` по-прежнему выбирается из набора (12…32px), но физические размеры кнопок
автоматически ×0.9 (миксин `.tool-bar-size` в tool-bar.less, v2).

### Пользовательская таблица стилей (`~/.atom/styles.less`)

Там живёт ширина скроллбаров (конфиг-ключа для этого в Atom нет — только стили).
Сборка v3: утолщённое 32px правило применяется к редактору/панелям/вкладкам, а для
боковой панели (`.tree-view`) добавлен отдельный блок 8px со стандартным ползунком
Atom — чтобы прокрутка дерева была обычной, как в редакторе, а не «кирпичом».
Меняется через File → Stylesheet в Atom, в AppImage не входит, пересборка не нужна.

## Автодополнение Lua-функций lualoader (ГДЕ лежит и КАК обновлять)

Автодополнение для скриптов lualoader (GTA VC) — это **корневые пользовательские
снаппеты Atom**, а НЕ пакет и НЕ часть AppImage. Файл автодополнения:

| Роль | Путь | Править? |
|---|---|---|
| **Исходный файл автодополнения** | `~/.atom/snippets.cson` | ДА — это то, что обновляют |
| Кэш (Atom сам переписывает из cson) | `~/.atom/compile-cache/cson/<hash>.json` | НЕТ — авто-создаётся |
| Стандартные снаппеты языка Lua | `~/.atom/packages/language-lua/snippets/language-lua.cson` | НЕТ (не lualoader) |

- В шапке `~/.atom/snippets.cson` написано: *«Автодополнение Lua-функций
  lualoader (N функций). Сгенерировано из `lualoader-src/LUA_API_СПРАВОЧНИК.md`»*.
- Структура: корневой ключ `'.source.lua':` → под ним каждая функция:
  `prefix` (имя), `body` (готовый вызов), `description`
  (формат `«описание | тип-возврата | вызов»`). На 2026-09-14: **1506 функций, 7534 строки**.
- Автодополнение по лудаскриптам = просто допечатать имя функции в `.lua`-файле
  (по `prefix`), снаппет вставляет `body`.

### Как обновить автодополнение (когда растёт API lualoader)

1. Файл-источник: `lualoader-src/LUA_API_СПРАВОЧНИК.md` (функции lualoader,
   разделы «Транспорт: авто», «Педы», «Объекты» и т.д.).
2. Пересгенерировать `~/.atom/snippets.cson` из этого MD: каждая строка вида
   `- **N.** имя(арг) → тип — описание` превращается в снаппет:
   `prefix=имя`, `body=имя(арг)`, `description="описание. | тип | имя(арг)"`,
   всё под ключом `'.source.lua':`. (Полный репогенератор не закреплён в этом MD —
   при обновлении либо вручную править cson, либо держать генератор рядом
   с lualoader-src.)
3. После правки cson кэш `~/.atom/compile-cache/.../<hash>.json` Atom сам
   пересобирает при следующем старте (hash зависит от содержимого cson) —
   JSON **не править руками**.
4. `~/.atom/snippets.cson` — это пользовательский слой `~/.atom`, **НЕ входит в
   AppImage** (AppImage содержит только `extra-packages`: tool-bar, cpp-tool-bar).
   Поэтому обновлять автодополнение = править `~/.atom/snippets.cson` напрямую,
   пересобирать atom.AppImage для этого НЕ нужно.

## Инструментарий C++ (уже в системе, не в AppImage)

g++ 13.3.0, make 4.3, gdb, clang — Ubuntu/Mint 24.04 stack. AppImage НЕ тянет свой g++ — берёт из PATH (настраивается `cpp-tool-bar.compilerPath`).

## Чек-лист повторной сборки

1. `--appimage-extract` текущего AppImage → правки в AppDir
2. Правки пакетов: менять version в package.json (иначе sync не сработает), `node --check lib/*.js`
3. Убрать `~/.atom/packages/{tool-bar,cpp-tool-bar}` перед тестом — проверить, что sync их пересоздал
4. Убрать `~/.atom/init.coffee`, `~/.atom/storage` перед финальным тестом
5. appimagetool с `--comp zstd --no-appstream`
6. E2E: запустить с `--disable-gpu` + тестовым .cpp; панель=12 кнопок (v3), build → бинарник + stdout
