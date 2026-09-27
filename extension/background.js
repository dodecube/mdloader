// background.js — очередь загрузок и мост к нативному хосту.

const NATIVE_HOST = "com.example.youtube_downloader";
const DOWNLOAD_TIMEOUT_MS = 30 * 60 * 1000; // плейлист может качаться долго
const HISTORY_LIMIT = 100;

let downloadPort = null;
let downloadTimeout = null;
let isDownloading = false;
let downloadQueue = [];
let downloadHistory = [];

/* ---------------------------------------------------------------- storage */

async function loadStorage() {
  const data = await chrome.storage.local.get(["downloadQueue", "downloadHistory"]);
  downloadQueue = data.downloadQueue || [];
  downloadHistory = data.downloadHistory || [];
  // После перезапуска браузера незавершённые задачи возвращаем в очередь.
  for (const job of downloadQueue) {
    if (job.status === "downloading") job.status = "queued";
  }
  await save();
  processNext();
}

function save() {
  return chrome.storage.local.set({ downloadQueue, downloadHistory });
}

function setActive(progress) {
  return chrome.storage.local.set({ activeProgress: progress });
}

/* ------------------------------------------------------------------ badge */

function updateBadge() {
  const downloading = downloadQueue.filter((j) => j.status === "downloading").length;
  const queued = downloadQueue.filter((j) => j.status === "queued").length;
  let text = "";
  let color = "#FF9800";
  if (downloading > 0) {
    text = queued > 0 ? `${queued}+` : "...";
    color = "#4CAF50";
  } else if (queued > 0) {
    text = String(queued);
  }
  chrome.action.setBadgeText({ text });
  if (text) chrome.action.setBadgeBackgroundColor({ color });
}

function notify(message, type) {
  if (type !== "error" && type !== "success") return;
  chrome.notifications.create({
    type: "basic",
    iconUrl: "icon.png",
    title: type === "error" ? "❌ Ошибка загрузки" : "✅ Загрузка завершена",
    message: String(message).slice(0, 300),
    priority: type === "error" ? 2 : 1,
  });
}

/* ------------------------------------------------------------------- jobs */

function createJob({ url, label, mode, tabId }) {
  return {
    id: `${Date.now()}-${Math.random().toString(36).slice(2, 8)}`,
    url,
    label: label || url,
    mode: mode === "playlist" ? "playlist" : "track",
    tabId: tabId ?? null,
    status: "queued",
    progress: 0,
    progressMessage: "В очереди",
    addedAt: new Date().toISOString(),
  };
}

async function addJob(job) {
  const duplicate = downloadQueue.find((j) => j.url === job.url && j.mode === job.mode);
  if (duplicate) {
    return { ok: false, error: "Уже в очереди", job: duplicate };
  }
  downloadQueue.push(job);
  await save();
  updateBadge();
  processNext();
  return { ok: true, job };
}

/** Спрашивает у content-скрипта активной вкладки, что качать. */
async function collectFromTab(mode) {
  const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
  if (!tab?.id) return { error: "Нет активной вкладки" };

  let data = null;
  try {
    data = await chrome.tabs.sendMessage(tab.id, { action: "collect", mode });
  } catch {
    // Content-скрипт не внедрён (страница вне last.fm/youtube).
  }

  if (!data && mode === "track" && /^https?:/.test(tab.url || "")) {
    data = { url: tab.url }; // запасной вариант: просто адрес вкладки
  }
  if (!data) {
    return {
      error:
        mode === "playlist"
          ? "Плейлист или альбом на этой странице не найден"
          : "Трек на этой странице не найден",
    };
  }
  return { data, tabId: tab.id, title: tab.title };
}

async function enqueueCurrent(mode) {
  const result = await collectFromTab(mode);
  if (result.error) return { ok: false, error: result.error };

  const { data, tabId, title } = result;
  const label = data.label || data.title || title || data.url;
  return addJob(createJob({ url: data.url, label, mode, tabId }));
}

/* -------------------------------------------------------------- pipeline */

function processNext() {
  if (isDownloading) return;
  const job = downloadQueue.find((j) => j.status === "queued");
  if (!job) {
    updateBadge();
    setActive(null);
    return;
  }
  isDownloading = true;
  job.status = "downloading";
  job.startedAt = new Date().toISOString();
  save();
  updateBadge();
  startDownload(job);
}

async function startDownload(job) {
  try {
    disconnect();
    armTimeout(job);

    downloadPort = chrome.runtime.connectNative(NATIVE_HOST);
    downloadPort.onMessage.addListener((response) => onHostMessage(response, job));
    downloadPort.onDisconnect.addListener(() => onHostDisconnect(job));

    const { useCookies } = await chrome.storage.local.get(["useCookies"]);
    downloadPort.postMessage({
      action: "download",
      url: job.url,
      useCookies: useCookies === true,
      playlist: job.mode === "playlist",
    });
  } catch (error) {
    finish(job, false, `Не удалось подключиться к хосту: ${error.message}`);
  }
}

function armTimeout(job) {
  clearTimeout(downloadTimeout);
  downloadTimeout = setTimeout(() => finish(job, false, "Превышено время ожидания"), DOWNLOAD_TIMEOUT_MS);
}

function disconnect() {
  clearTimeout(downloadTimeout);
  if (downloadPort) {
    try {
      downloadPort.disconnect();
    } catch {
      /* порт уже закрыт */
    }
    downloadPort = null;
  }
}

function onHostMessage(response, job) {
  if (response.status === "progress") {
    armTimeout(job);
    job.progress = Math.round(response.progress ?? job.progress);
    job.progressMessage = response.message || "";
    chrome.action.setBadgeText({ text: `${job.progress}%` });
    setActive({ jobId: job.id, label: job.label, mode: job.mode, progress: job.progress, message: job.progressMessage });
  } else if (response.status === "success") {
    finish(job, true, response.message || "Готово");
  } else if (response.status === "error") {
    finish(job, false, response.message || "Неизвестная ошибка");
  }
}

function onHostDisconnect(job) {
  if (job.status === "downloading") {
    finish(job, false, "Соединение с нативным хостом потеряно");
  }
}

async function finish(job, ok, message) {
  if (job.status !== "downloading") return; // защита от двойного завершения
  disconnect();

  job.status = ok ? "completed" : "error";
  job.progress = ok ? 100 : job.progress;
  job.progressMessage = message;
  job.finishedAt = new Date().toISOString();
  if (!ok) job.errorMsg = message;

  const index = downloadQueue.findIndex((j) => j.id === job.id);
  if (index !== -1) downloadQueue.splice(index, 1);
  downloadHistory.unshift({ ...job });
  downloadHistory = downloadHistory.slice(0, HISTORY_LIMIT);

  await save();
  await setActive(null);
  updateBadge();
  notify(`${job.label}: ${message}`, ok ? "success" : "error");

  isDownloading = false;
  processNext();
}

/* --------------------------------------------------------------- messages */

const handlers = {
  async enqueueCurrent({ mode }) {
    return enqueueCurrent(mode);
  },
  async cancelJob({ jobId }) {
    const index = downloadQueue.findIndex((j) => j.id === jobId && j.status === "queued");
    if (index === -1) return { ok: false, error: "Задача уже выполняется" };
    downloadQueue.splice(index, 1);
    await save();
    updateBadge();
    return { ok: true };
  },
  async retryJob({ jobId }) {
    const old = downloadHistory.find((j) => j.id === jobId);
    if (!old) return { ok: false, error: "Задача не найдена" };
    downloadHistory = downloadHistory.filter((j) => j.id !== jobId);
    await save();
    return addJob(createJob({ url: old.url, label: old.label, mode: old.mode, tabId: old.tabId }));
  },
  async clearHistory() {
    downloadHistory = [];
    await save();
    return { ok: true };
  },
  async clearQueue() {
    downloadQueue = downloadQueue.filter((j) => j.status === "downloading");
    await save();
    updateBadge();
    return { ok: true };
  },
};

chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  const handler = handlers[message?.action];
  if (!handler) return false;
  handler(message)
    .then(sendResponse)
    .catch((error) => sendResponse({ ok: false, error: error.message }));
  return true; // ответ придёт асинхронно
});

/* ----------------------------------------------------------- context menu */

chrome.runtime.onInstalled.addListener(() => {
  chrome.contextMenus.removeAll(() => {
    chrome.contextMenus.create({ id: "openMenu", title: "Открыть меню (без загрузки)", contexts: ["action"] });
    chrome.contextMenus.create({ id: "sep1", type: "separator", contexts: ["action"] });
    chrome.contextMenus.create({ id: "downloadPlaylist", title: "Скачать альбом / плейлист", contexts: ["action"] });
    chrome.contextMenus.create({ id: "openQueue", title: "Открыть очередь во вкладке", contexts: ["action"] });
    chrome.contextMenus.create({ id: "clearQueue", title: "Очистить очередь", contexts: ["action"] });
  });
});

async function openPopup({ autoDownload }) {
  // Попап сам решает, качать ли трек при открытии.
  await chrome.storage.local.set({ suppressAutoDownload: !autoDownload });
  try {
    await chrome.action.openPopup();
  } catch {
    // openPopup доступен не во всех сборках — открываем очередь во вкладке.
    await chrome.storage.local.remove("suppressAutoDownload");
    chrome.tabs.create({ url: chrome.runtime.getURL("popup.html?view=tab") });
  }
}

chrome.contextMenus.onClicked.addListener(async (info) => {
  if (info.menuItemId === "openMenu") {
    await openPopup({ autoDownload: false });
  } else if (info.menuItemId === "downloadPlaylist") {
    const result = await enqueueCurrent("playlist");
    if (!result.ok) notify(result.error, "error");
    await openPopup({ autoDownload: false });
  } else if (info.menuItemId === "openQueue") {
    chrome.tabs.create({ url: chrome.runtime.getURL("popup.html?view=tab") });
  } else if (info.menuItemId === "clearQueue") {
    await handlers.clearQueue({});
  }
});

loadStorage();
