'use strict';

document.addEventListener('DOMContentLoaded', function () {
  var btn = document.getElementById('theme-toggle');

  if (!btn) return;

  var currentTheme = null;

  chrome.storage.local.get(['maTheme'], function (result) {
    currentTheme = result.maTheme || 'light';
    btn.classList.toggle('dark', currentTheme === 'dark');
  });

  btn.addEventListener('click', function () {
    if (!currentTheme) {
      currentTheme = 'light';
    }
    var next = currentTheme === 'dark' ? 'light' : 'dark';
    currentTheme = next;

    chrome.storage.local.set({ maTheme: next });
    btn.classList.toggle('dark', next === 'dark');
  });
});
