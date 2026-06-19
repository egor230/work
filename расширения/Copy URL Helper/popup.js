// Флаг для отображения аннотации
const showAnnotation = true;

document.addEventListener('DOMContentLoaded', async () => {
    const urlDiv = document.getElementById('url');

    try {
        // Получаем активную вкладку
        const tabs = await chrome.tabs.query({ active: true, currentWindow: true });
        if (tabs.length === 0) {
            urlDiv.textContent = 'Вкладка не найдена';
            setTimeout(() => window.close(), 2000);
            return;
        }

        const tab = tabs[0];
        let currentUrl = tab.url || 'URL не найден';

        // Декодируем URL для читаемого отображения
        if (currentUrl.startsWith('http')) {
            try {
                currentUrl = decodeURIComponent(currentUrl);
            } catch (e) {
                console.warn('Ошибка декодирования URL:', e);
            }
        }

        // Очистка URL (опционально, если нужно удалить параметры запроса)
        chrome.storage.sync.get({ clean_url: false }, async (items) => {
            if (items.clean_url) {
                currentUrl = currentUrl.split('?')[0]; // Удаляем параметры запроса
            }

            // Отображаем URL
            urlDiv.textContent = currentUrl;
            console.log('URL:', tab.url);

            // Копируем URL в буфер обмена
            try {
                await navigator.clipboard.writeText(currentUrl);
                if (showAnnotation) {
                    urlDiv.textContent = `${currentUrl}`;
                } 
                setTimeout(() => window.close(), 1500);
            } catch (error) {
                console.error('Ошибка копирования в буфер:', error);
                urlDiv.textContent = 'Ошибка копирования URL';
                setTimeout(() => window.close(), 2000);
            }
        });

    } catch (error) {
        console.error('Ошибка при получении URL:', error);
        urlDiv.textContent = 'Ошибка при получении URL';
        setTimeout(() => window.close(), 2000);
    }
});