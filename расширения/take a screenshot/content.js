(function () {
    // === Отключение театрального режима с надежной проверкой ===
    function tryDisableTheaterModeWithCheck(retries = 15, baseInterval = 500) {
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
                    console.log(`Попытка ${attempt} отключения театрального режима через ${Math.round(delay)} мс`);
                    setTimeout(attemptResize, delay);
                } else {
                    console.warn('Не удалось найти плеер или кнопку изменения размера после всех попыток.');
                }
                return;
            }

            if (player.classList.contains('ytp-player-theater-mode')) {
                sizeButton.click();
                console.log('Кнопка изменения размера нажата. Ожидаем обновления...');
                setTimeout(() => {
                    if (player.classList.contains('ytp-player-theater-mode')) {
                        console.warn('Театральный режим всё ещё активен. Повторная попытка...');
                        attempt++;
                        if (attempt < retries) {
                            setTimeout(attemptResize, baseInterval * 2);
                        } else {
                            console.error('Не удалось выйти из театрального режима.');
                        }
                    } else {
                        console.log('Театральный режим успешно отключен.');
                    }
                }, 2000);
            } else {
                console.log('Плеер уже в стандартном режиме.');
            }
        }

        attemptResize();
    }

    // === Автоматическое нажатие кнопки "Magic Skip" через 3 секунды ===
    function autoClickMagicSkip() {
        let intervalId;
        setTimeout(() => {
            intervalId = setInterval(() => {
                const skipButton = document.querySelector('.ytp-ad-skip-button.ytp-button');
                if (skipButton) {
                    skipButton.click();
                    console.log('Кнопка "Пропустить рекламу" нажата.');
                    clearInterval(intervalId); // Остановить проверку после клика
                }
            }, 800); // Проверять каждые 0.5 секунды
        }, 5000); // Начать проверку через 5 секунд
        
    }

    // === Единая функция для работы с меню настроек плеера ===
    function withPlayerSettings(callback, maxAttempts = 5, delay = 700) {
        const settingsButton = document.querySelector('.ytp-settings-button');
        if (!settingsButton) {
            console.warn('Кнопка настроек плеера не найдена.');
            return;
        }

        let attempts = 0;
        const interval = setInterval(() => {
            if (document.querySelectorAll('.ytp-menuitem').length > 0 || attempts >= maxAttempts) {
                clearInterval(interval);
                if (attempts < maxAttempts) {
                    settingsButton.click(); // Открываем меню
                    setTimeout(() => {
                        callback();
                        settingsButton.click(); // Закрываем меню
                    }, 500);
                } else {
                    console.warn('Меню настроек не открылось после нескольких попыток.');
                }
            }
            attempts++;
        }, delay);
    }

    // === Отключение Ambient Mode (профессионального освещения) с поддержкой разных языков и максимальной надёжностью ===
    function disableAmbientModeIfEnabled() {
        // Список возможных вариантов названия пункта меню Ambient Mode на разных языках
        const ambientKeywords = [
            'ambient', 'освещение', 'lighting', 'проф', 'professional',
            'ambiente', 'ambiente', 'ambiente', // испанский, итальянский, португальский
            'ambiance', // французский
            'ambiente', // немецкий
            'ambiente', // польский
            'ambiente', // турецкий
            'ambiente', // японский (латиницей)
            'ambiente', // корейский (латиницей)
            // ... можно добавить другие языки
        ];

        // Проверяем, что мы на YouTube
        if (!/^(https?:\/\/)?(www\.)?youtube\.com\//.test(window.location.href)) {
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
                    console.warn('Ambient Mode: не найдена кнопка настроек плеера.');
                }
                return;
            }

            // Открываем меню, если оно закрыто
            if (!document.querySelector('.ytp-menuitem')) {
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
                            console.log('Ambient Mode/Проф. освещение отключено.');
                        }
                        break;
                    }
                }
                // Закрываем меню, если открывали
                if (document.querySelector('.ytp-menuitem')) {
                    settingsButton.click();
                }
                if (!found && attempts < maxAttempts) {
                    attempts++;
                    setTimeout(tryDisable, interval);
                } else if (!found) {
                    console.warn('Ambient Mode: пункт меню не найден.');
                }
            }, 500);
        }
        tryDisable();
    }

    // === Отключение аннотаций ===
    async function disableAnnotations() {
        const maxAttempts = 16; // Больше попыток для надёжности
        const delay = 800; // ms между попытками
    
        // Предполагаемая обёртка (замени на свою, если есть; это ждёт загрузки плеера)
        async function withPlayerSettings(callback) {
            return new Promise(resolve => {
                const checkPlayer = () => {
                    const player = document.querySelector('.html5-video-player');
                    if (player) {
                        resolve(callback());
                    } else {
                        setTimeout(checkPlayer, 500);
                    }
                };
                checkPlayer();
            });
        }
    
        return withPlayerSettings(async () => {
            // Шаг 1: Открываем меню настроек, если оно закрыто
            const settingsButton = document.querySelector('.ytp-settings-button');
            if (settingsButton && !document.querySelector('.ytp-settings-menu')) {
                settingsButton.click();
                await new Promise(resolve => setTimeout(resolve, 300)); // Ждём открытия меню
            }
    
            for (let attempt = 1; attempt <= maxAttempts; attempt++) {
                const annotationItem = findAnnotationMenuItem();
                
                if (annotationItem) {
                    if (annotationItem.getAttribute('aria-checked') === 'true') {
                        annotationItem.click();
                        console.log('Попытка отключения аннотаций...');
                        
                        // Шаг 2: Ждём и проверяем, отключены ли (как ты просил)
                        await new Promise(resolve => setTimeout(resolve, 1000)); // 1 сек на применение
                        const updatedItem = findAnnotationMenuItem(); // Ищем заново
                        if (updatedItem && updatedItem.getAttribute('aria-checked') === 'false') {
                            console.log('Аннотации успешно отключены!');
                            return true; // Успех
                        } else {
                            console.warn('Аннотации не отключились после клика (попытка ' + attempt + ')');
                        }
                    } else {
                        console.log('Аннотации уже отключены');
                        return false; // Уже выключены
                    }
                }
                
                // Ждём перед следующей попыткой
                await new Promise(resolve => setTimeout(resolve, delay));
            }
            
            console.warn('Пункт меню аннотаций не найден после ' + maxAttempts + ' попыток. Возможно, аннотации не поддерживаются в этом видео.');
            return false;
        });
    }
    
    // Вспомогательная функция для поиска элемента (расширил ключевые слова для надёжности)
    function findAnnotationMenuItem() {
        const menuItems = Array.from(document.querySelectorAll('.ytp-menuitem, .ytp-menuitem-toggle'));
        const keywords = [
            'аннотац',    // Русский (аннотации)
            'annotat',    // Английский (annotations)
            'anotation',  // Вариации
            'anotación',  // Испанский
            'anotação',   // Португальский
            'annotazione',// Итальянский
            '注释',       // Китайский
            '註解',       // Трад. китайский
            '注解',       // Японский (chūshaku)
            '주석'        // Корейский
        ];
        
        return menuItems.find(item => {
            const text = item.textContent?.toLowerCase() || '';
            return keywords.some(kw => text.includes(kw));
        });
    }
             
    })();
    

    // === Обработка SPA-навигации на YouTube ===
    let lastUrl = location.href;
    new MutationObserver(() => {
        if (location.href !== lastUrl) {
            lastUrl = location.href;
            setTimeout(() => {
                tryDisableTheaterModeWithCheck();
                disableAmbientModeIfEnabled();
                disableAnnotationsIfEnabled();
                tryDisableTheaterModeWithCheck();
                autoClickMagicSkip();
            }, 5000);
        }
    }).observe(document, { subtree: true, childList: true });

    // === Запуск при загрузке страницы ===
    window.addEventListener('load', () => {
        setTimeout(() => {
            tryDisableTheaterModeWithCheck();
            disableAmbientModeIfEnabled();
            tryDisableTheaterModeWithCheck();
            autoClickMagicSkip();
                // Запуск функции при загрузке страницы и при изменениях плеера
            let observer = new MutationObserver(() => disableAnnotations());
            observer.observe(document.body, { childList: true, subtree: true });
            disableAnnotations(); // Первоначальный запуск
        }, 5000);
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