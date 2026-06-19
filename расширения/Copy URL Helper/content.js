(function () {
    'use strict';

    let isProcessing = false;
    let lastVideoId = null;
    let adSkipInterval = null;

    // === Отключение театрального режима с надежной проверкой ===
    function tryDisableTheaterModeWithCheck(retries = 15, baseInterval = 500) {
        return new Promise((resolve) => {
            let attempt = 0;

            function attemptResize() {
                const player = document.getElementById('movie_player');
                const sizeButton = document.querySelector('.ytp-size-button') ||
                                   document.querySelector('button[aria-label="Размер плеера"]') ||
                                   document.querySelector('button[aria-label="Player size"]');

                if (!player || !sizeButton) {
                    if (attempt < retries) {
                        attempt++;
                        const delay = baseInterval * Math.pow(1.2, attempt);
                        console.log(`[TheaterMode] Попытка ${attempt} через ${Math.round(delay)} мс`);
                        setTimeout(attemptResize, delay);
                    } else {
                        console.warn('[TheaterMode] Не удалось найти плеер или кнопку после всех попыток.');
                        resolve(false);
                    }
                    return;
                }

                if (player.classList.contains('ytp-player-theater-mode')) {
                    sizeButton.click();
                    console.log('[TheaterMode] Кнопка нажата. Ожидаем...');
                    setTimeout(() => {
                        if (player.classList.contains('ytp-player-theater-mode')) {
                            console.warn('[TheaterMode] Режим всё ещё активен.');
                            attempt++;
                            if (attempt < retries) {
                                setTimeout(attemptResize, baseInterval * 2);
                            } else {
                                console.error('[TheaterMode] Не удалось выйти из режима.');
                                resolve(false);
                            }
                        } else {
                            console.log('[TheaterMode] Успешно отключен.');
                            resolve(true);
                        }
                    }, 2000);
                } else {
                    console.log('[TheaterMode] Уже в стандартном режиме.');
                    resolve(true);
                }
            }

            attemptResize();
        });
    }

    // === Автоматическое нажатие кнопки "Пропустить рекламу" ===
    function autoClickMagicSkip() {
        // Очищаем предыдущий интервал, если был
        if (adSkipInterval) clearInterval(adSkipInterval);

        setTimeout(() => {
            adSkipInterval = setInterval(() => {
                const adContainer = document.querySelector('.video-ads.ytp-ad-module');
                // Если рекламного контейнера нет или он пуст — рекламы нет
                if (!adContainer || adContainer.children.length === 0) {
                    clearInterval(adSkipInterval);
                    console.log('[AdSkip] Реклама не обнаружена или завершена.');
                    return;
                }

                const skipButton = document.querySelector('.ytp-ad-skip-button.ytp-button');
                if (skipButton) {
                    skipButton.click();
                    console.log('[AdSkip] Кнопка "Пропустить" нажата.');
                    clearInterval(adSkipInterval);
                }
            }, 800);
        }, 3000); // Начинаем проверку через 3 секунды после запуска видео
    }

    // === Отключение Ambient Mode (профессионального освещения) ===
    function disableAmbientModeIfEnabled() {
        return new Promise((resolve) => {
            const ambientKeywords = [
                'ambient', 'освещение', 'lighting', 'проф', 'professional',
                'ambiente', 'ambiance'
            ];

            if (!/^(https?:\/\/)?(www\.)?youtube\.com\//.test(window.location.href)) {
                resolve(false);
                return;
            }

            let attempts = 0;
            const maxAttempts = 15;
            const interval = 750;

            function tryDisable() {
                const settingsButton = document.querySelector('.ytp-settings-button');
                if (!settingsButton) {
                    if (attempts < maxAttempts) {
                        attempts++;
                        setTimeout(tryDisable, interval);
                    } else {
                        console.warn('[AmbientMode] Кнопка настроек не найдена.');
                        resolve(false);
                    }
                    return;
                }

                // Открываем меню, если закрыто
                const isMenuOpen = document.querySelector('.ytp-menuitem');
                if (!isMenuOpen) {
                    settingsButton.click();
                }

                setTimeout(() => {
                    const items = Array.from(document.querySelectorAll('.ytp-menuitem'));
                    let found = false;
                    for (const item of items) {
                        const text = item.textContent.trim().toLowerCase();
                        if (ambientKeywords.some(keyword => text.includes(keyword))) {
                            found = true;
                            if (item.getAttribute('aria-checked') === 'true') {
                                item.click();
                                console.log('[AmbientMode] Отключено.');
                            }
                            break;
                        }
                    }

                    // Закрываем меню, если открывали
                    if (!isMenuOpen && document.querySelector('.ytp-menuitem')) {
                        settingsButton.click();
                    }

                    if (!found && attempts < maxAttempts) {
                        attempts++;
                        setTimeout(tryDisable, interval);
                    } else if (!found) {
                        console.warn('[AmbientMode] Пункт меню не найден.');
                    }
                    resolve(found);
                }, 500);
            }

            tryDisable();
        });
    }

    // === Отключение аннотаций ===
    async function disableAnnotations() {
        const maxAttempts = 16;
        const delay = 800;

        // Ждём появления плеера
        await new Promise(resolve => {
            const checkPlayer = () => {
                if (document.querySelector('.html5-video-player')) {
                    resolve();
                } else {
                    setTimeout(checkPlayer, 500);
                }
            };
            checkPlayer();
        });

        // Шаг 1: Открываем меню настроек
        const settingsButton = document.querySelector('.ytp-settings-button');
        if (!settingsButton) {
            console.warn('[Annotations] Кнопка настроек не найдена.');
            return false;
        }

        if (!document.querySelector('.ytp-settings-menu')) {
            settingsButton.click();
            await new Promise(resolve => setTimeout(resolve, 300));
        }

        // Ищем пункт меню
        function findAnnotationMenuItem() {
            const menuItems = Array.from(document.querySelectorAll('.ytp-menuitem, .ytp-menuitem-toggle'));
            const keywords = [
                'аннотац', 'annotat', 'anotation', 'anotación', 'anotação',
                'annotazione', '注释', '註解', '注解', '주석'
            ];
            return menuItems.find(item => {
                const text = item.textContent?.toLowerCase() || '';
                return keywords.some(kw => text.includes(kw));
            });
        }

        for (let attempt = 1; attempt <= maxAttempts; attempt++) {
            const annotationItem = findAnnotationMenuItem();

            if (annotationItem) {
                if (annotationItem.getAttribute('aria-checked') === 'true') {
                    annotationItem.click();
                    console.log('[Annotations] Попытка отключения...');

                    await new Promise(resolve => setTimeout(resolve, 1000));
                    const updatedItem = findAnnotationMenuItem();
                    if (updatedItem && updatedItem.getAttribute('aria-checked') === 'false') {
                        console.log('[Annotations] Успешно отключены!');
                        // Закрываем меню
                        if (document.querySelector('.ytp-settings-menu')) {
                            settingsButton.click();
                        }
                        return true;
                    } else {
                        console.warn(`[Annotations] Не отключились (попытка ${attempt})`);
                    }
                } else {
                    console.log('[Annotations] Уже отключены');
                    if (document.querySelector('.ytp-settings-menu')) {
                        settingsButton.click();
                    }
                    return false;
                }
            }

            await new Promise(resolve => setTimeout(resolve, delay));
        }

        console.warn(`[Annotations] Пункт не найден после ${maxAttempts} попыток.`);
        return false;
    }

    // === Основная функция запуска всех фиксов ===
    async function runAllFixes() {
        if (isProcessing) {
            console.log('[Main] Пропуск: уже выполняется');
            return;
        }

        isProcessing = true;
        console.log('[Main] Запуск всех исправлений...');

        try {
            await tryDisableTheaterModeWithCheck();
            await disableAmbientModeIfEnabled();
            await disableAnnotations();
            autoClickMagicSkip(); // Запускаем фоном, без await
        } catch (err) {
            console.error('[Main] Ошибка при выполнении фиксов:', err);
        } finally {
            isProcessing = false;
        }
    }

    // === Отслеживание смены видео через URL ===
    function getVideoId() {
        const match = window.location.href.match(/[?&]v=([^&]+)/);
        return match ? match[1] : null;
    }

    function checkVideoChange() {
        const currentVideoId = getVideoId();
        if (currentVideoId && currentVideoId !== lastVideoId) {
            lastVideoId = currentVideoId;
            console.log(`[Main] Обнаружено новое видео: ${currentVideoId}`);
            setTimeout(runAllFixes, 3000); // Даём плееру загрузиться
        }
    }

    // === Инициализация при загрузке страницы ===
    function init() {
        // Первый запуск
        setTimeout(runAllFixes, 5000);

        // Отслеживаем смену видео
        setInterval(checkVideoChange, 2000);

        // Дополнительно слушаем мутации для SPA
        new MutationObserver(checkVideoChange).observe(document, {
            subtree: true,
            childList: true
        });

        console.log('[Main] Скрипт инициализирован.');
    }

    // Запуск после полной загрузки страницы
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }

})();

    // Добавляю обработчик нажатия на кнопку изменения размера видео
    // document.addEventListener('click', function(e) {
    //     const sizeButton = document.querySelector('.ytp-size-button');
    //     if (sizeButton && sizeButton.contains(e.target)) {
    //         setTimeout(() => {
    //             const player = document.getElementById('movie_player');
    //             if (player && !player.classList.contains('ytp-player-theater-mode')) {
    //                 // Плеер в стандартном режиме
    //                 // Здесь можно добавить нужную логику, например, оповещение:
    //                 // alert('Плеер в стандартном режиме!');
    //             } else {
    //                 // Плеер в широком режиме
    //                 // alert('Плеер в широком режиме!');
    //             }
    //         }, 300); // Ждём, чтобы DOM успел обновиться
    //     }
    // });
    // window.addEventListener('load', () => {
    //     setTimeout(() => {
    //         const skipButton = document.querySelector('[aria-label="Magic Skip"]');
    //         if (skipButton) {
    //             skipButton.click();
    //         }
    //     }, 6000);
    // }); 