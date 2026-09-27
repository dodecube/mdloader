// content.js — извлекает данные о треке и плейлисте по запросу из background.
// Своего UI здесь нет: загрузка запускается кликом по иконке расширения.

function youtubeTrack() {
  if (location.href.includes("watch?v=")) {
    // Убираем list=/index=, чтобы случайно не утянуть весь плейлист.
    const url = new URL(location.href);
    for (const param of ["list", "index", "start_radio", "pp"]) url.searchParams.delete(param);
    return { url: url.toString() };
  }
  const link = document.querySelector("a.ytmVideoInfoVideoTitle");
  return link?.href?.includes("watch?v=") ? { url: link.href } : null;
}

function youtubePlaylist() {
  const url = new URL(location.href);
  const list = url.searchParams.get("list");
  if (!list) return null;
  const title =
    document.querySelector("yt-formatted-string#text.ytd-playlist-panel-renderer")?.textContent?.trim() ||
    document.querySelector("h1.ytd-playlist-header-renderer")?.textContent?.trim() ||
    document.querySelector("#header-description h1")?.textContent?.trim() ||
    null;
  return { url: `https://www.youtube.com/playlist?list=${list}`, title };
}

function lastfmTrack() {
  // Открытый плеер — самый точный источник: у него есть прямая ссылка на YouTube.
  const playerLink = document.querySelector("a.ytmVideoInfoVideoTitle");
  if (playerLink?.href?.includes("youtube.com/watch")) {
    return { url: playerLink.href };
  }

  const selectors = [
    { artist: ".player-bar-artist-name", track: ".player-bar-track-name" },
    { artist: ".header-new-crumb span", track: 'h1[itemprop="name"]' },
    { artist: ".header-featured-artist", track: ".header-title-display-name" },
  ];
  for (const selector of selectors) {
    const artist = document.querySelector(selector.artist)?.textContent.trim();
    const track = document.querySelector(selector.track)?.textContent.trim();
    if (artist && track) {
      return { url: `ytsearch:${artist} - ${track}`, label: `${artist} - ${track}` };
    }
  }
  return null;
}

function lastfmAlbum() {
  // Страница альбома last.fm: /music/<artist>/<album>
  const match = location.pathname.match(/^\/music\/([^/]+)\/(?!_\/)([^/]+)\/?$/);
  if (!match) return null;
  const artist = decodeURIComponent(match[1]).replace(/\+/g, " ");
  const album = decodeURIComponent(match[2]).replace(/\+/g, " ");
  const label = `${artist} - ${album}`;
  // Ищем альбом на YouTube: yt-dlp сам развернёт найденный плейлист.
  return { url: `ytsearch1:${label} full album`, title: label, label };
}

/** @returns {{url: string, title?: string|null, label?: string}|null} */
function collect(mode) {
  const host = location.hostname;
  if (host.includes("youtube.com")) {
    return mode === "playlist" ? youtubePlaylist() : youtubeTrack();
  }
  if (host.includes("last.fm")) {
    return mode === "playlist" ? lastfmAlbum() : lastfmTrack();
  }
  return null;
}

chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  if (message?.action === "collect") {
    sendResponse(collect(message.mode));
  }
  return false;
});
