# Готовое объединённое расширение: Enhancer for YouTube + Magic Actions (2026-10-29)

Один пакет делает функции двух расширений:

- **Enhancer for YouTube™** (оригинал MRFDEV, store 3.1.0 + кастомные правки
  §1–§10 из `Enhancer for YouTube/README-CUSTOM.md`): скорость, качество,
  скрытие Shorts/карточек/комментариев, панель скорости по каналам,
  «Поиск на YouTube», бэкап настроек и т.д.
- **Magic Actions for YouTube** (кастомная v2.0.0, `Magic Actions for YouTube/`):
  переключение светлой/тёмной темы — плавающая кнопка солнце/луна на странице,
  тумблер в popup, кукка `PREF f6`, guards, без CSS-вмятин в светлой теме.

Тема Magic Actions влита в Enhancer (§3, `js/ma-content.js`, `js/ma-main-world.js`,
`css/ma.css`); отдельной установкой Magic Actions больше не нужен.

## Что в пакете

Папка **`Enhancer for YouTube/`** (в этой директории) — готовое расширение,
**`Enhancer_for_YouTube.crx`** — собранный пакет того же содержимого
(скрипт `package-crx.sh`, верифицирован; ID `ifojmbdceojdnhhagpmfnmjndpplcndi`,
ключ `efyt_private.pem` прежний).

Вид — оригинальный Enhancer: имя `Enhancer for YouTube™`, оригинальные иконки,
страница настроек `html/options.html`. Popup: тумблер темы + «Настройки
Enhancer» + сохранение/восстановление бэкапа.

## Значения по умолчанию = настройки Яндекс Браузера

Сняты 2026-10-29 из
`~/.config/yandex-browser/Default/Local Extension Settings/ifojmbdceojdnhhagpmfnmjndpplcndi`
(чтение LevelDB-лога, последние записи):

| Настройка | Дефолт (как в Яндексе) |
|---|---|
| Тема YouTube (`maTheme`) | **тёмная** |
| Скорость воспроизведения | **1.2×** |
| Качество видео / плейлистов | **hd2160 (2160p)** |
| Автоматический выбор качества | **вкл** |
| Кнопки-контролы | **speed-minus, speed, speed-plus, screenshot, options** |
| Панель контролов | **неактивна, по центру, фикс. позиция** |
| Видимость контролов | **вкл** |
| Shorts на главной | **скрыты** |
| Видео в ряду (канал) | **8** (применяется) |
| Видео в ряду (главная) | **6** (применяется) |

Механизмы:

1. `js/config.js` — дефолты объекта `config` (работает и в .crx, и в unpacked);
2. `js/ma-content.js` — `DEFAULT_THEME='dark'` (первый запуск без storage);
3. `config-backup.json` — снапшот Яндекса; `js/service-worker.js` при старте
   SW **non-destructive gap-fill**: дописывает только отсутствующие ключи,
   живые изменения пользователя не затирает (в .crx файла нет — там работают
   пункты 1–2).

## Установка

- **Яндекс/Chrome:** `yandex://extensions` / `chrome://extensions` →
  «Разработчик» → «Загрузить распакованное расширение» (папку
  `Enhancer for YouTube/`) или пакетированный `Enhancer_for_YouTube.crx`.
- ID совпадает с ранее установленным → `chrome.storage.local` (текущие
  настройки Яндекса) сохраняется, визуально ничего не меняется; дефолты
  проявятся только для новых ключей/чистого профиля.
- После обновления: перезагрузите вкладки YouTube (F5), чтобы подхватились
  новые content-скрипты.

## Состояние папок в `расширения/`

| Папка/файл | Роль |
|---|---|
| `Enhancer for YouTube/` | **готовое объединённое расширение** (источник правды, 2026-10-29) |
| `Enhancer_for_YouTube.crx` | готовый пакет из этой папки |
| `Magic Actions for YouTube/` | архив/исходник темы (не устанавливается отдельно) |
| `Magic Actions for YouTube — проблемы и ошибки.md` | история отладки темы |
| `Magic Actions for YouTube — исследование переключения темы (сводный документ).md` | полное исследование (12 заметок) |
| `yt_исследование_темы_ Magic Actions/` | рабочие заметки сессии 2026-09-10 |
| `Enhancer for YouTube/README-CUSTOM.md` | документация всех правок Enhancer (разделы §1–§11) |

Подробности этой сессии — в `Enhancer for YouTube/README-CUSTOM.md`, **§11**.
