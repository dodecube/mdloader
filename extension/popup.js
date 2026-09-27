// popup.js — управление очередью загрузок.
// Весь DOM строится через createElement: названия треков приходят со сторонних
// страниц, поэтому innerHTML здесь использовать нельзя.

const STATUS_LABELS = {
  downloading: "downloading",
  queued: "queued",
  completed: "done",
  error: "error",
};

function formatJob(job) {
  const name = job.searchQuery || job.url || "unknown";
  const added = job.addedAt ? new Date(job.addedAt).toLocaleTimeString() : "—";
  return `${name} (added: ${added})`;
}

/** <li>текст <span class="job-status …">…</span> [кнопка]</li> */
function jobItem(job, button) {
  const li = document.createElement("li");
  li.append(document.createTextNode(formatJob(job) + " "));

  const badge = document.createElement("span");
  badge.className = `job-status ${job.status}`;
  badge.textContent = STATUS_LABELS[job.status] || job.status;
  li.append(badge);

  if (button) {
    const btn = document.createElement("button");
    btn.className = button.className;
    btn.textContent = button.label;
    btn.addEventListener("click", () => button.onClick(job.id));
    li.append(" ", btn);
  }
  return li;
}

function fillList(elementId, jobs, emptyText, button) {
  const list = document.getElementById(elementId);
  if (!list) return;
  list.replaceChildren();
  if (jobs.length === 0) {
    const li = document.createElement("li");
    li.textContent = emptyText;
    list.append(li);
    return;
  }
  list.append(...jobs.map((job) => jobItem(job, button)));
}

function sendAction(message) {
  chrome.runtime.sendMessage(message, () => {
    if (chrome.runtime.lastError) {
      console.warn("[mdloader]", chrome.runtime.lastError.message);
    }
    render();
  });
}

async function render() {
  const { downloadQueue = [], downloadHistory = [] } = await chrome.storage.local.get([
    "downloadQueue",
    "downloadHistory",
  ]);

  const downloading = downloadQueue.filter((j) => j.status === "downloading");
  const queued = downloadQueue.filter((j) => j.status === "queued");

  fillList("downloading-list", downloading, "None");
  fillList("queue-list", queued, "Queue is empty", {
    className: "cancel-btn",
    label: "Cancel",
    onClick: (jobId) => sendAction({ action: "cancelJob", jobId }),
  });
  fillList("completed-list", downloadHistory.filter((j) => j.status === "completed"), "None");
  fillList("errors-list", downloadHistory.filter((j) => j.status === "error"), "No errors", {
    className: "retry-btn",
    label: "Retry",
    onClick: (jobId) => sendAction({ action: "retryJob", jobId }),
  });

  const counter = document.getElementById("queue-count");
  if (counter) counter.textContent = String(queued.length);
}

async function setupCookiesCheckbox() {
  const checkbox = document.getElementById("use-cookies-checkbox");
  if (!checkbox) return;
  const { useCookies } = await chrome.storage.local.get(["useCookies"]);
  checkbox.checked = useCookies === true;
  checkbox.addEventListener("change", (event) => {
    chrome.storage.local.set({ useCookies: event.target.checked });
  });
}

document.getElementById("clear-all-btn")?.addEventListener("click", () => {
  if (confirm("Clear all history (completed and errors)?")) {
    sendAction({ action: "clearHistory" });
  }
});

chrome.storage.onChanged.addListener((changes, area) => {
  if (area === "local" && (changes.downloadQueue || changes.downloadHistory)) {
    render();
  }
});

render();
setupCookiesCheckbox();
