// background.js – основной сервис-воркер
let downloadPort = null;
let downloadTimeout = null;
let isDownloading = false;
let downloadQueue = [];       // текущая очередь
let downloadHistory = [];     // архив завершённых и ошибочных

// Загрузка сохранённых данных при старте
async function loadStorage() {
  const data = await chrome.storage.local.get(['downloadQueue', 'downloadHistory']);
  downloadQueue = data.downloadQueue || [];
  downloadHistory = data.downloadHistory || [];
  updateQueueBadge();
  // Если был незавершённый download – сбросить статусы queued, но downloading не восстанавливаем
  let needSave = false;
  for (let job of downloadQueue) {
    if (job.status === 'downloading') {
      job.status = 'queued';
      needSave = true;
    }
  }
  if (needSave) saveToStorage();
  // Запустить обработку очереди, если нужно
  if (!isDownloading && downloadQueue.some(j => j.status === 'queued')) {
    processNextDownload();
  }
}

function saveToStorage() {
  chrome.storage.local.set({ downloadQueue, downloadHistory });
}

// Добавить в историю (завершённые или ошибки)
function addToHistory(job) {
  const copy = { ...job };
  downloadHistory.unshift(copy); // свежие сверху
  // Ограничим историю 100 записями
  if (downloadHistory.length > 100) downloadHistory.pop();
  saveToStorage();
}

// Обновить бейдж иконки
function updateQueueBadge() {
  const downloadingCount = downloadQueue.filter(j => j.status === 'downloading').length;
  const queuedCount = downloadQueue.filter(j => j.status === 'queued').length;
  if (downloadingCount > 0) {
    chrome.action.setBadgeText({ text: queuedCount > 0 ? `${queuedCount}+` : '...' });
    chrome.action.setBadgeBackgroundColor({ color: '#4CAF50' });
  } else if (queuedCount > 0) {
    chrome.action.setBadgeText({ text: queuedCount.toString() });
    chrome.action.setBadgeBackgroundColor({ color: '#FF9800' });
  } else {
    chrome.action.setBadgeText({ text: '' });
  }
}

// Добавление задания в очередь
function addJob(job) {
  downloadQueue.push(job);
  saveToStorage();
  updateQueueBadge();
  showNotification(`Added to queue: ${job.searchQuery || job.url}`, 'info');
  if (!isDownloading) processNextDownload();
}

// Создание задания из URL или поискового запроса
function createJob(url, searchQuery = null, tabId = null) {
  return {
    id: Date.now() + '-' + Math.random().toString(36).substr(2, 6),
    url: url,
    searchQuery: searchQuery,
    tabId: tabId,
    status: 'queued',
    addedAt: new Date().toISOString()
  };
}

// Обработка сообщений от content script и popup
chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  if (message.action === 'downloadTrack') {
    const { artist, track } = message;
    const searchQuery = `${artist} - ${track}`;
    const ytUrl = `ytsearch:${searchQuery}`;
    const job = createJob(ytUrl, searchQuery, sender.tab?.id);
    addJob(job);
    sendResponse({ success: true, jobId: job.id });
  } 
  else if (message.action === 'cancelJob') {
    const index = downloadQueue.findIndex(j => j.id === message.jobId);
    if (index !== -1) {
      downloadQueue.splice(index, 1);
      saveToStorage();
      updateQueueBadge();
      showNotification('Job cancelled from queue', 'info');
      if (!isDownloading) processNextDownload();
    }
    sendResponse({ success: true });
  }
  else if (message.action === 'retryJob') {
    const jobInHistory = downloadHistory.find(j => j.id === message.jobId);
    if (jobInHistory) {
      const newJob = createJob(jobInHistory.url, jobInHistory.searchQuery, jobInHistory.tabId);
      addJob(newJob);
      // удаляем из истории (необязательно)
      const idx = downloadHistory.findIndex(j => j.id === message.jobId);
      if (idx !== -1) downloadHistory.splice(idx, 1);
      saveToStorage();
    }
    sendResponse({ success: true });
  }
  else if (message.action === 'clearHistory') {
    downloadHistory = downloadHistory.filter(j => j.status === 'downloading'); // не удаляем активные
    saveToStorage();
    sendResponse({ success: true });
  }
  else if (message.action === 'downloadUrl') {
    const job = createJob(message.url, null, sender.tab?.id);
    addJob(job);
    sendResponse({ success: true, jobId: job.id });
  }
  return true; // асинхронный ответ
});

// Клик по иконке (без попапа) – скачать текущий URL
chrome.action.onClicked.addListener(async (tab) => {
  const job = createJob(tab.url, null, tab.id);
  addJob(job);
});

// Обработка очереди
async function processNextDownload() {
  if (isDownloading) return;
  const nextJob = downloadQueue.find(j => j.status === 'queued');
  if (!nextJob) {
    isDownloading = false;
    updateQueueBadge();
    return;
  }
  isDownloading = true;
  nextJob.status = 'downloading';
  nextJob.startedAt = new Date().toISOString();
  saveToStorage();
  updateQueueBadge();
  await startDownload(nextJob);
}

async function startDownload(job) {
  try {
    if (downloadPort) {
      downloadPort.disconnect();
      downloadPort = null;
    }
    // Таймаут
    downloadTimeout = setTimeout(() => {
      handleDownloadError('Download timed out', job);
    }, 300000);

    downloadPort = chrome.runtime.connectNative('com.example.youtube_downloader');
    downloadPort.onMessage.addListener((response) => handleDownloadResponse(response, job));
    downloadPort.onDisconnect.addListener(() => handleDownloadDisconnect(job));

    // Читаем настройку использования cookies
    const storage = await chrome.storage.local.get(['useCookies']);
    const useCookies = storage.useCookies === true;

    downloadPort.postMessage({
      action: 'download',
      url: job.url,
      useCookies: useCookies   // <-- добавляем флаг
    });
  } catch (err) {
    handleDownloadError('Native host connection failed: ' + err.message, job);
  }
}

function handleDownloadResponse(response, job) {
  if (downloadTimeout) {
    clearTimeout(downloadTimeout);
    downloadTimeout = setTimeout(() => handleDownloadError('Timeout', job), 300000);
  }
  if (response.status === 'progress') {
    let progressText = response.progress !== undefined ? `${Math.round(response.progress)}%` : '...';
    chrome.action.setBadgeText({ text: progressText });
    showNotification(response.message, 'info', null, response.progress);
  } 
  else if (response.status === 'success') {
    handleDownloadSuccess(job);
  } 
  else if (response.status === 'error') {
    handleDownloadError(response.message, job);
  }
}

function handleDownloadSuccess(job) {
  if (downloadTimeout) clearTimeout(downloadTimeout);
  job.status = 'completed';
  job.completedAt = new Date().toISOString();
  // Удаляем из очереди, добавляем в историю
  const idx = downloadQueue.findIndex(j => j.id === job.id);
  if (idx !== -1) downloadQueue.splice(idx, 1);
  addToHistory(job);
  saveToStorage();
  updateQueueBadge();
  showNotification(`✅ Download completed: ${job.searchQuery || job.url}`, 'success');
  if (downloadPort) { downloadPort.disconnect(); downloadPort = null; }
  isDownloading = false;
  processNextDownload();
}

function handleDownloadError(msg, job) {
  if (downloadTimeout) clearTimeout(downloadTimeout);
  job.status = 'error';
  job.errorMsg = msg;
  job.failedAt = new Date().toISOString();
  const idx = downloadQueue.findIndex(j => j.id === job.id);
  if (idx !== -1) downloadQueue.splice(idx, 1);
  addToHistory(job);
  saveToStorage();
  updateQueueBadge();
  showNotification(`❌ ${msg}`, 'error');
  if (downloadPort) { downloadPort.disconnect(); downloadPort = null; }
  isDownloading = false;
  processNextDownload();
}

function handleDownloadDisconnect(job) {
  if (downloadTimeout) clearTimeout(downloadTimeout);
  // Если ещё не обработано – ошибка
  if (job.status === 'downloading') {
    handleDownloadError('Connection lost to native host', job);
  } else {
    if (downloadPort) downloadPort = null;
    isDownloading = false;
    processNextDownload();
  }
}

function showNotification(message, type, tabId = null, progress = null) {
    // Показываем уведомления ТОЛЬКО для ошибок и завершения
    if (type !== 'error' && type !== 'success') return;

    chrome.notifications.create({
        type: 'basic',
        iconUrl: 'icon.png',
        title: type === 'error' ? '❌ Download Error' : '✅ Download Complete',
        message: message,
        priority: type === 'error' ? 2 : 1
    });
}

// Контекстное меню (оставляем как есть)
chrome.runtime.onInstalled.addListener(() => {
  chrome.contextMenus.create({ id: 'showQueue', title: 'Show Download Queue', contexts: ['action'] });
  chrome.contextMenus.create({ id: 'clearQueue', title: 'Clear Download Queue', contexts: ['action'] });
});
chrome.contextMenus.onClicked.addListener((info, tab) => {
  if (info.menuItemId === 'showQueue') {
    const q = downloadQueue.filter(j => j.status === 'queued').length;
    const d = downloadQueue.filter(j => j.status === 'downloading').length;
    showNotification(`Queue: ${q} queued, ${d} downloading`, 'info', tab.id);
  } else if (info.menuItemId === 'clearQueue') {
    downloadQueue = downloadQueue.filter(j => j.status === 'downloading');
    saveToStorage();
    updateQueueBadge();
    showNotification('Cleared queued items', 'info', tab.id);
  }
});

// Загрузка сохранённого состояния при старте
loadStorage();