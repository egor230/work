# Magic Actions for YouTube — Custom (v2.0.0)

Кастомная урезанная версия расширения «Magic Actions for YouTube»: единственная
функция — переключение светлой/тёмной темы YouTube. Полное объяснение с
историей всех находок и багов — в «Как работает Magic Actions for YouTube.md».
Файлы оригинала (`esw30.js`, `gjs30/`, `gcss30/`, `e*.html`) не подключены в
manifest.json и ни на что не влияют.

## Архитектура (v3: light = «расширение выключено»)

- **dark** = форсаж включён: атрибут `dark=""` + кук `f6=400` + блокировки
  атрибутов/куки в main_world.js + тёмные CSS-токены в styles.css.
- **light** = расширение «выключено»: нативная пара атрибутов
  (`light=""`, снять `dark`) + кук `f6=80000` + чистка застрявших классов
  `*Dark` у строки поиска. НИ ОДНОГО CSS-правила для светлой темы — YouTube
  рендерит её сам, идеально. Родной тумблер YouTube подхватывается
  (attrGuard синхронизирует chrome.storage).
- Тема применяется живьём во всех вкладках (chrome.storage → onChanged),
  без reload; переживает перезагрузку страницы и SPA-навигацию.

## Файлы

| Файл | Роль |
|---|---|
| `manifest.json` | MV3, только `storage`. Два content-скрипта на `youtube.com`, оба `document_start`, `main_world.js` — в MAIN world, `content.js` + `styles.css` — в ISOLATED |
| `content.js` | Ядро: тема, тумблер `#__magic-theme-switch`, чистка классов *Dark, слежение за родным тумблером YT |
| `main_world.js` | Патчи в контексте страницы (активны только в dark-режиме) + диспетч yt-action по метке `data-ma-notify` |
| `styles.css` | Тумблер + ТОЛЬКО тёмная тема (`html[dark]` через `--yt-spec-*` и `--yt-sys-color-baseline--*`) |
| `popup.html`/`popup.js` | Кнопка в popup → та же запись в `chrome.storage.local` |

## Для пользователя

Пересоздать расширение в `chrome://extensions` (Reload) и обновить вкладки
YouTube. Переключение — плавающая кнопка слева вверху (солнце/луна) или
кнопка в popup. Светлая тема выглядит ровно как нативная — в ней расширение
ничего не красит.
