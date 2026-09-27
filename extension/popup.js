// popup.js – взаимодействие со страницей управления

let currentData = { queue: [], history: [] };

async function loadCookiesSetting() {
  const result = await chrome.storage.local.get(['useCookies']);
  const checkbox = document.getElementById('use-cookies-checkbox');
  if (checkbox) {
    checkbox.checked = result.useCookies === true;
  }
}

// Сохранение настройки при изменении
function setupCookiesCheckbox() {
  const checkbox = document.getElementById('use-cookies-checkbox');
  if (!checkbox) return;
  checkbox.addEventListener('change', async (e) => {
    await chrome.storage.local.set({ useCookies: e.target.checked });
  });
}

function formatJob(job) {
  const displayName = job.searchQuery || job.url || 'unknown';
  return `${displayName} (added: ${new Date(job.addedAt).toLocaleTimeString()})`;
}

function render() {
  // Получаем данные из storage
  chrome.storage.local.get(['downloadQueue', 'downloadHistory'], (result) => {
    const queue = result.downloadQueue || [];
    const history = result.downloadHistory || [];

    // Текущее скачивание
    const downloading = queue.filter(j => j.status === 'downloading');
    const queued = queue.filter(j => j.status === 'queued');

    document.getElementById('downloading-list').innerHTML = downloading.map(job => `
      <li>${formatJob(job)} <span class="job-status downloading">downloading</span></li>
    `).join('') || '<li>None</li>';

    document.getElementById('queue-count').innerText = queued.length;
    document.getElementById('queue-list').innerHTML = queued.map(job => `
      <li>${formatJob(job)} <span class="job-status queued">queued</span>
      <button class="cancel-btn" data-id="${job.id}">Cancel</button></li>
    `).join('') || '<li>Queue is empty</li>';

    // Завершённые
    const completed = history.filter(j => j.status === 'completed');
    document.getElementById('completed-list').innerHTML = completed.map(job => `
      <li>${formatJob(job)} <span class="job-status completed">done</span></li>
    `).join('') || '<li>None</li>';

    // Ошибки
    const errors = history.filter(j => j.status === 'error');
    document.getElementById('errors-list').innerHTML = errors.map(job => `
      <li>${formatJob(job)} <span class="job-status error">error</span>
      <button class="retry-btn" data-id="${job.id}">Retry</button></li>
    `).join('') || '<li>No errors</li>';

    // Вешаем обработчики на кнопки отмены и повтора
    document.querySelectorAll('.cancel-btn').forEach(btn => {
      btn.onclick = () => cancelJob(btn.dataset.id);
    });
    document.querySelectorAll('.retry-btn').forEach(btn => {
      btn.onclick = () => retryJob(btn.dataset.id);
    });
  });
}

function cancelJob(jobId) {
  chrome.runtime.sendMessage({ action: 'cancelJob', jobId: jobId }, () => {
    render();
  });
}

function retryJob(jobId) {
  chrome.runtime.sendMessage({ action: 'retryJob', jobId: jobId }, () => {
    render();
  });
}

document.getElementById('clear-all-btn').onclick = () => {
  if (confirm('Clear all history (completed and errors)?')) {
    chrome.runtime.sendMessage({ action: 'clearHistory' }, () => {
      render();
    });
  }
};

// Обновляем при открытии попапа и при изменениях в storage
chrome.storage.onChanged.addListener((changes, area) => {
  if (area === 'local' && (changes.downloadQueue || changes.downloadHistory)) {
    render();
  }
});

render();
loadCookiesSetting();
setupCookiesCheckbox();