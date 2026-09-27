# mdloader
My Usual way to download music

Расширение для браузера (Firefox / Zen) + Python-хост поверх yt-dlp.

## Состав

- `extension/` — WebExtension (MV3, Firefox/Zen): очередь загрузок, кнопка на last.fm и YouTube.
- `msg.py` — native messaging host, вызывает yt-dlp/ffmpeg.
- `native-host/` — манифест нативного хоста и установщик для Firefox.
- `extension/manifest.chrome.json` — исходный манифест под Chrome (на всякий случай).

## Установка (Firefox / Zen, Windows)

1. Настрой пути в начале `msg.py`: `DOWNLOAD_DIR`, `YT_DLP_PATH`, `FFMPEG_PATH`, `COOKIES_PATH`.
2. Зарегистрируй нативный хост:

       python native-host/install_firefox_host.py

3. Открой `about:debugging#/runtime/this-firefox` → «Загрузить временное дополнение» → выбери `extension/manifest.json`.

Для постоянной установки расширение нужно подписать на addons.mozilla.org в режиме
**unlisted** (код остаётся приватным, на выходе — `.xpi`).

ID расширения: `mdloader@dodecube` — он должен совпадать в `manifest.json`
и в `allowed_extensions` манифеста нативного хоста.
