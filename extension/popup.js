// popup.js — интерфейс очереди.
// Весь DOM строится через createElement: названия треков приходят со сторонних
// страниц, поэтому innerHTML использовать нельзя.

const isTabView = new URLSearchParams(location.search).get("view") === "tab";

const el = (id) => document.getElementById(id);

/* -------------------------------------------------------------- вспомогательное */

function showToast(text, kind) {
  const toast = el("toast");
  toast.textContent = text;
  toast.className = `show ${kind}`;
  clearTimeout(showToast.timer);
  showToast.timer = setTimeout(() => {
    toast.className = "";
  }, 4000);
}

function send(action, payload = {}) {
  return chrome.runtime.sendMessage({ action, ...payload });
}

function timeOf(iso) {
  return iso ? new Date(iso).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }) : "";
}

/* ------------------------------------------------------------------ загрузка */

async function startDownload(mode) {
  const button = el(mode === "playlist" ? "download-playlist" : "download-track");
  button.disabled = true;
  try {
    const result = await send("enqueueCurrent", { mode });
    if (result?.ok) {
      showToast(`Добавлено: ${result.job.label}`, "ok");
    } else {
      showToast(result?.error || "Не удалось добавить задачу", "err");
    }
  } catch (error) {
    showToast(error.message, "err");
  } finally {
    button.disabled = false;
    render();
  }
}

/* -------------------------------------------------------------------- рендер */

function listItem(job, { showTime = true, action } = {}) {
  const li = document.createElement("li");

  const dot = document.createElement("span");
  dot.className = `dot ${job.status}`;
  li.append(dot);

  const title = document.createElement("span");
  title.className = "title";
  title.textContent = job.label || job.url;
  title.title = job.errorMsg || job.url;
  li.append(title);

  if (job.mode === "playlist") {
    const tag = document.createElement("span");
    tag.className = "tag";
    tag.textContent = "альбом";
    li.append(tag);
  }

  if (showTime) {
    const meta = document.createElement("span");
    meta.className = "meta";
    meta.textContent = timeOf(job.finishedAt || job.addedAt);
    li.append(meta);
  }

  if (action) {
    const button = document.createElement("button");
    button.className = "icon";
    button.textContent = action.label;
    button.addEventListener("click", async () => {
      button.disabled = true;
      const result = await send(action.name, { jobId: job.id });
      if (result?.error) showToast(result.error, "err");
      render();
    });
    li.append(button);
  }

  return li;
}

function fill(listId, jobs, emptyText, options) {
  const list = el(listId);
  list.replaceChildren();
  if (!jobs.length) {
    const li = document.createElement("li");
    li.className = "empty";
    li.textContent = emptyText;
    list.append(li);
    return;
  }
  list.append(...jobs.map((job) => listItem(job, options)));
}

async function render() {
  const { downloadQueue = [], downloadHistory = [], activeProgress = null } =
    await chrome.storage.local.get(["downloadQueue", "downloadHistory", "activeProgress"]);

  const active = downloadQueue.find((j) => j.status === "downloading");
  const queued = downloadQueue.filter((j) => j.status === "queued");

  const activeBox = el("active");
  if (active) {
    const percent = activeProgress?.jobId === active.id ? activeProgress.progress : active.progress || 0;
    activeBox.hidden = false;
    el("active-name").textContent = active.label || active.url;
    el("active-status").textContent =
      (activeProgress?.jobId === active.id ? activeProgress.message : active.progressMessage) || "Загрузка...";
    el("active-bar").style.width = `${Math.min(100, Math.max(0, percent))}%`;
  } else {
    activeBox.hidden = true;
  }

  el("queue-count").textContent = String(queued.length);
  fill("queue-list", queued, "Очередь пуста", {
    action: { name: "cancelJob", label: "✕" },
  });

  fill("history-list", downloadHistory.slice(0, 30), "Пока ничего не скачано", {
    action: undefined,
  });

  // Кнопка повтора только у ошибочных задач.
  const historyList = el("history-list");
  downloadHistory.slice(0, 30).forEach((job, index) => {
    if (job.status !== "error") return;
    const li = historyList.children[index];
    if (!li) return;
    const retry = document.createElement("button");
    retry.className = "icon";
    retry.textContent = "↻";
    retry.title = job.errorMsg || "Повторить";
    retry.addEventListener("click", async () => {
      retry.disabled = true;
      const result = await send("retryJob", { jobId: job.id });
      if (result?.error) showToast(result.error, "err");
      render();
    });
    li.append(retry);
  });
}

/* -------------------------------------------------------------------- старт */

async function init() {
  if (isTabView) document.body.classList.add("tab-view");
  el("version").textContent = `v${chrome.runtime.getManifest().version}`;

  const { useCookies } = await chrome.storage.local.get(["useCookies"]);
  el("use-cookies").checked = useCookies === true;
  el("use-cookies").addEventListener("change", (event) => {
    chrome.storage.local.set({ useCookies: event.target.checked });
  });

  el("download-track").addEventListener("click", () => startDownload("track"));
  el("download-playlist").addEventListener("click", () => startDownload("playlist"));
  el("clear-history").addEventListener("click", async () => {
    await send("clearHistory");
    render();
  });
  el("open-tab").addEventListener("click", () => {
    chrome.tabs.create({ url: chrome.runtime.getURL("popup.html?view=tab") });
    window.close();
  });

  chrome.storage.onChanged.addListener((changes, area) => {
    if (area === "local") render();
  });

  await render();

  // Клик по иконке = сразу качаем текущий трек (поведение старой версии).
  // Пункт «Открыть меню» в ПКМ выставляет флаг, который это подавляет.
  const { suppressAutoDownload } = await chrome.storage.local.get(["suppressAutoDownload"]);
  await chrome.storage.local.remove("suppressAutoDownload");
  if (!isTabView && !suppressAutoDownload) startDownload("track");
}

init();
