# Папка: исследование переключения темы YouTube (Magic Actions for YouTube)

Оригинальные исследовательские заметки сессии 2026-09-10 (13:13–14:01) —
12 файлов `yt_*.md` + краткий конспект `yt_theme_final.txt`.

## Объединённые документы (в родительской папке ../)
- `Magic Actions for YouTube — исследование переключения темы (сводный документ).md`
  — ВСЕ 12 заметок `yt_*.md`, склеенные в один файл в хронологическом порядке
  (разделы 1–12 соответствуют `yt_theme_analysis` → `yt_final_implementation`).
  Часть гипотез ранних разделов позже опровергнута (например,
  `window.yt.config_.INNERTUBE_CONTEXT`) — сохранены как история поиска.
- `Magic Actions for YouTube — проблемы и ошибки.md` — актуальные баги/симптомы
  (стала часть сводного документа: раздел 2 сводного = этот файл, проверено).

## Документация по расширению (тоже перенесена сюда)
- `Magic Actions for YouTube — разбор сессии.md` — разбор отладки: ошибки,
  трудности, неверные решения (перенесён из папки расширения ../Magic Actions for YouTube/).
- `Как работает Magic Actions for YouTube.md` — пошаговое устройство темы v3
  и причины багов по разбору реальных бандлов YouTube и CDP-диагностике
  (перенесён из папки расширения ../Magic Actions for YouTube/).
- Осталось в ../Magic Actions for YouTube/: `Журнал изменений.md` (история
  сессий разработки), `Диагностика и решение проблем с расширением для
  браузера.md` (про Яндекс-браузер, не про тему), сами исходники
  (content.js, main_world.js, styles.css) и `README.md`.

## Порядок тем (от первых гипотез к финальной реализации)
1. `yt_theme_analysis.md` — базовый разбор: setAttribute/CSS-токены/debounce/рассинхрон.
2. `yt_theme_qa.md` — короткий QA по тем же вопросам + TL;DR.
3. `yt_theme_final.txt` — текстовая сводка решений (1–4 вопроса).
4. `yt_scrollbar_diagnosis.md` — почему «меняется только прокрутка».
5. `yt_event_format.md` — формат CustomEvent `yt-action` (detail: actionName/args).
6. `yt_api_deep_dive.md` — API и хранение темы: `yt-dark-mode-toggled-action` vs
   `/youtubei/v1/account/set_setting`, storage для не-авторизованных (кука PREF f6).
7. `yt_searchbox_rendering_pipeline.md` — жизненный цикл yt-searchbox (Lit/Polymer).
8. `yt_event_property_flow.md` — поток event→property→render в yt-searchbox.
9. `yt_timing_race_analysis.md` — тайминги и гонки: почему debounce 100ms вредил.
10. `yt_final_checklist.md` — чек-лист перед изменениями кода (двойной dispatch и т.п.).
11. `yt_searchbox_asymmetry_analysis.md` — асимметрия light→dark / dark→light,
    *Dark-классы (HostDark/InputBoxDark/SearchButtonDark/SuggestionsContainerDark).
12. `yt_searchbox_property_forensics.md` — форенсика имён свойств/DI-токенов,
    snippet диагностики через DevTools/CDP, дерево решений (requestUpdate vs классы).
13. `yt_final_implementation.md` — ФИНАЛЬНАЯ реализация: syncSearchboxClasses +
    requestUpdate + полный готовый код content.js/main_world.js.

## Связь с исходниками
Исходники расширения (content.js, main_world.js, styles.css, README.md и др.)
лежат в `../Magic Actions for YouTube/`.

С 2026-09-24 функционал темы влит в Enhancer for YouTube: исходники живут там
(`js/ma-content.js`, `js/ma-main-world.js`, `css/ma.css` — §3 `../Enhancer
for YouTube/README-CUSTOM.md`), папку Magic Actions больше не нужно
устанавливать в браузер.
