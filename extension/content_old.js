// content.js – добавляет кнопки Download к трекам на last.fm

// Функция добавления кнопки к одному элементу трека
function addDownloadButton(trackElement) {
  if (trackElement.querySelector('.librezam-download-btn')) return;

  // Пытаемся извлечь исполнителя и название трека
  let artist = '', title = '';

  // Различные селекторы last.fm (адаптируйте при необходимости)
  const artistEl = trackElement.querySelector('.chartlist-artist, .resource-list-artist, .track-artist, a[href*="/music/"]');
  const titleEl = trackElement.querySelector('.chartlist-name, .resource-list-title, .track-name, .js-track-name');

  if (artistEl) artist = artistEl.textContent.trim();
  if (titleEl) title = titleEl.textContent.trim();

  // Альтернативный способ: из data-атрибутов
  if (!artist && trackElement.dataset.artist) artist = trackElement.dataset.artist;
  if (!title && trackElement.dataset.track) title = trackElement.dataset.track;

  if (!artist || !title) return; // не удалось определить трек

  // Создаём кнопку
  const btn = document.createElement('button');
  btn.textContent = '⬇️ Download';
  btn.className = 'librezam-download-btn';
  btn.style.marginLeft = '8px';
  btn.style.padding = '2px 6px';
  btn.style.fontSize = '12px';
  btn.style.cursor = 'pointer';

  btn.addEventListener('click', (e) => {
    e.stopPropagation();
    chrome.runtime.sendMessage({
      action: 'downloadTrack',
      artist: artist,
      track: title
    }, (response) => {
      if (chrome.runtime.lastError) {
        console.error('Send error:', chrome.runtime.lastError);
      } else {
        console.log('Download queued:', response);
      }
    });
  });

  // Найти контейнер для кнопки (рядом с кнопкой Play или лайком)
  const controls = trackElement.querySelector('.chartlist-actions, .resource-actions, .track-actions, .js-actions');
  if (controls) {
    controls.appendChild(btn);
  } else {
    // Или просто в конец элемента трека
    trackElement.appendChild(btn);
  }
}

// Инициализация: обрабатываем все существующие треки
function initDownloadButtons() {
  // Селекторы строк треков на last.fm (популярные страницы, плейлисты, рекомендации)
  const selectors = [
    '.chartlist-row',
    '.resource-list--track',
    'tr[data-track-name]',
    '.track-row',
    '.js-track'
  ];
  selectors.forEach(sel => {
    document.querySelectorAll(sel).forEach(addDownloadButton);
  });
}

// Наблюдатель за динамически подгружаемым контентом (бесконечный скролл)
const observer = new MutationObserver((mutations) => {
  let added = false;
  for (const mutation of mutations) {
    if (mutation.addedNodes.length) {
      added = true;
      break;
    }
  }
  if (added) initDownloadButtons();
});
observer.observe(document.body, { childList: true, subtree: true });

// Запуск при загрузке страницы
if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', initDownloadButtons);
} else {
  initDownloadButtons();
}