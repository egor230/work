chrome.runtime.onInstalled.addListener((details) => {
    if (details.reason === 'install') {
      // Code to be executed on first install
      // eg. open a tab with a URL
      chrome.tabs.create({
        url: "https://google-chrome-extensions.com/apps/youtube-transcription/welcome/",
      });
    } else if (details.reason === 'update') {
      // When the extension is updated
    } else if (details.reason === 'chrome_update') {
      // When the browser is updated
    } else if (details.reason === 'shared_module_update') {
      // When a shared module is updated
    }
  });

chrome.runtime.setUninstallURL("https://google-chrome-extensions.com/apps/youtube-transcription/help-us/");