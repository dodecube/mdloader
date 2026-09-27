// content.js
console.log("[Librezam] Скрипт запущен");

function getTrackData() {
    const host = window.location.hostname;

    // YouTube - используем прямую ссылку
    if (host.includes('youtube.com')) {
        if (window.location.href.includes('watch?v=')) {
            return { action: 'downloadUrl', url: window.location.href };
        }
        const link = document.querySelector('a.ytmVideoInfoVideoTitle');
        if (link && link.href && link.href.includes('watch?v=')) {
            return { action: 'downloadUrl', url: link.href };
        }
        return null;
    }

    // Last.fm - используем экшен downloadTrack, который есть в твоем background.js
    if (host.includes('last.fm')) {
        // 1. Сначала пробуем взять из плеера (самое точное)
        const playerLink = document.querySelector('a.ytmVideoInfoVideoTitle');
        if (playerLink && playerLink.href && playerLink.href.includes('youtube.com/watch')) {
            return { 
                action: 'downloadUrl', 
                url: playerLink.href 
            };
        }
        
        // 2. Fallback на старый метод (если плеер не открыт)
        const selectors = [
            { a: '.player-bar-artist-name', t: '.player-bar-track-name' },
            { a: '.header-new-crumb span', t: 'h1[itemprop="name"]' },
            { a: '.header-featured-artist', t: '.header-title-display-name' }
        ];

        for (let s of selectors) {
            const artistEl = document.querySelector(s.a);
            const trackEl = document.querySelector(s.t);
            if (artistEl && trackEl) {
                const artist = artistEl.textContent.trim();
                const track = trackEl.textContent.trim();
                if (artist && track) {
                    return { 
                        action: 'downloadTrack', 
                        artist: artist, 
                        track: track 
                    };
                }
            }
        }
    }
    return null;
}

function addDownloadButton() {
    if (document.querySelector('.librezam-download-btn')) return;

    const btn = document.createElement('button');
    btn.textContent = '⬇️ Download';
    btn.className = 'librezam-download-btn';
    
    // Твои оригинальные стили
    btn.style.cssText = `
        position: fixed !important;
        bottom: 90px !important;
        right: 20px !important;
        z-index: 2147483647 !important;
        padding: 12px 18px !important;
        background: #d51007 !important;
        color: #ffffff !important;
        border: none !important;
        border-radius: 25px !important;
        cursor: pointer !important;
        font-size: 14px !important;
        font-weight: bold !important;
        font-family: Arial, sans-serif !important;
        box-shadow: 0 4px 12px rgba(0, 0, 0, 0.4) !important;
        transition: background 0.2s ease !important;
        user-select: none !important;
        line-height: 1 !important;
    `;
    
    btn.onclick = (e) => {
        e.preventDefault();
        const data = getTrackData();
        
        if (!data) {
            btn.textContent = '❌ Трек не найден';
            setTimeout(() => btn.textContent = '⬇️ Download', 2000);
            return;
        }

        btn.textContent = '⏳ В очереди...';
        
        // Отправляем сообщение в background.js
        chrome.runtime.sendMessage(data, (response) => {
            // Твой background.js вернет {success: true}
            if (response && response.success) {
                btn.textContent = '✅ Добавлено';
            } else {
                btn.textContent = '❌ Ошибка';
            }
            setTimeout(() => btn.textContent = '⬇️ Download', 2000);
        });
    };
    
    document.body.appendChild(btn);
}

// Запуск
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', addDownloadButton);
} else {
    addDownloadButton();
}

// Следим за изменениями (SPA)
const observer = new MutationObserver(() => {
    if (!document.querySelector('.librezam-download-btn')) {
        addDownloadButton();
    }
});
observer.observe(document.body, { childList: true, subtree: true });