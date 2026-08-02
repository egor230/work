'use strict';

document.addEventListener('DOMContentLoaded', function () {
  var btn = document.getElementById('theme-toggle');
  if (!btn) return;

  function render(theme) {
    btn.classList.toggle('dark', theme === 'dark');
  }

  chrome.storage.local.get(['maTheme'], function (result) {
    render(result.maTheme || 'light');
  });

  btn.addEventListener('click', function () {
    chrome.storage.local.get(['maTheme'], function (result) {
      var next = result.maTheme === 'dark' ? 'light' : 'dark';
      chrome.storage.local.set({ maTheme: next });
      render(next);
    });
  });
});
