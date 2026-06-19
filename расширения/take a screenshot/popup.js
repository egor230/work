document.addEventListener('DOMContentLoaded', async () => {
    const statusDiv = document.getElementById('status');

    try {
        const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
        if (!tab) {
            statusDiv.textContent = 'Вкладка не найдена';
            setTimeout(() => window.close(), 2000);
            return;
        }

        // Скриншот видимой области
        const screenshotDataUrl = await chrome.tabs.captureVisibleTab(null, { format: 'png' });

        // Преобразование в blob
        const response = await fetch(screenshotDataUrl);
        const blob = await response.blob();

        setTimeout(() => window.close(), 1500);
        // Копирование изображения в буфер обмена
        try {
            const clipboardItemInput = new ClipboardItem({ [blob.type]: blob });
            await navigator.clipboard.write([clipboardItemInput]);
            statusDiv.textContent = 'Скриншот скопирован в буфер обмена';
        } catch (copyError) {
            console.error('Ошибка копирования:', copyError);
            statusDiv.textContent = 'Не удалось скопировать в буфер';
        }


    } catch (e) {
        console.error('Ошибка:', e);
        statusDiv.textContent = 'Общая ошибка выполнения';
        setTimeout(() => window.close(), 2000);
    }
});

        // // Сохранение файла
        // const now = new Date();
        // const currentDate = now.toISOString().split('T')[0];
        // const currentTime = now.toTimeString().split(' ')[0].replace(/:/g, '-');
        // const fileName = `Screenshot ${currentTime} ${currentDate}.png`;

        // try {
        //     await chrome.downloads.download({
        //         url: screenshotDataUrl,
        //         filename: fileName,
        //         saveAs: true
        //     });
        //     statusDiv.textContent += `\nСкриншот сохранён как ${fileName}`;
        // } catch (saveError) {
        //     console.error('Ошибка сохранения:', saveError);
        //     statusDiv.textContent += '\nОшибка сохранения файла';
        // }