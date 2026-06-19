// background.js
chrome.runtime.onInstalled.addListener(() => {
  console.log("Расширение готово к работе!");
});

chrome.runtime.onStartup.addListener(() => {
    restoreLastClosedTab();
});

async function restoreLastClosedTab() {
    try {
        const sessions = await chrome.sessions.getRecentlyClosed({ limit: 1 });
        if (sessions.length === 0) {
            console.log("Нет недавно закрытых вкладок.");
            return;
        }

        const session = sessions[0];
        if (session.tab) {
            // Восстановление вкладки
            chrome.windows.create({
                tabId: session.tab.id,
                focused: true
            }, (window) => {
                console.log("Вкладка восстановлена:", session.tab.url);
            });
        } else {
            console.warn("Восстановление невозможно: нет данных о вкладке.");
        }
    } catch (error) {
            console.warn("Восстановление невозможно: нет данных о вкладке.");
    }
}