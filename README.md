# mdloader

My usual way to download music — расширение для Firefox / Zen, которое отправляет
ссылку с YouTube или last.fm локальному Python-хосту, а тот качает трек через
yt-dlp, встраивает квадратную обложку и приводит теги с именем файла к виду
`Artist - Title.mp3`.

## Структура

```
extension/          WebExtension (MV3, Firefox/Zen)
  manifest.json       манифест Firefox (event page + gecko.id)
  manifest.chrome.json  исходный манифест Chrome, для справки
  background.js       очередь загрузок, связь с нативным хостом
  content.js          кнопка «Download» на last.fm и YouTube
  popup.{html,js}     управление очередью и историей
host/               Python native messaging host
  mdloader_host/
    config.py         пути из config.json / переменных окружения
    messaging.py      протокол native messaging (4 байта длины + JSON)
    process.py        запуск подпроцессов без всплывающих консолей
    downloader.py     сборка команды yt-dlp, прогресс, разбор ошибок
    media.py          обложки, ID3-теги, переименование, очистка
    naming.py         чистые функции для имён файлов и тегов
    host.py           главный цикл
native-host/        манифест нативного хоста и установщик
tests/              pytest
msg.py              совместимость: старая точка входа
config.example.json шаблон путей (реальный config.json не коммитится)
```

## Установка

### 1. Настроить пути

```bash
cp config.example.json config.json
```

и отредактировать `download_dir`, `yt_dlp_path`, `ffmpeg_dir`, `cookies_path`.
`config.json` в `.gitignore`, поэтому машинно-зависимые пути и cookies
больше не попадают в репозиторий. Альтернатива — переменные окружения
`MDLOADER_DOWNLOAD_DIR`, `MDLOADER_YT_DLP`, `MDLOADER_FFMPEG_DIR`, `MDLOADER_COOKIES`.

### 2. Зависимости и регистрация хоста

```bash
pip install -r requirements.txt
python native-host/install_firefox_host.py
```

Проверить связь можно так (должен ответить версией yt-dlp):

```bash
python -c "import json,struct,sys;m=json.dumps({'action':'ping'}).encode();sys.stdout.buffer.write(struct.pack('@I',len(m))+m)" | python host
```

### 3. Установить расширение

**Временно (для разработки):** `about:debugging#/runtime/this-firefox` →
«Загрузить временное дополнение» → `extension/manifest.json`. Слетает при
перезапуске браузера.

**Постоянно:** нужен подписанный Mozilla `.xpi`. В Zen и релизном Firefox
настройка `xpinstall.signatures.required` не действует, поэтому неподписанное
расширение установить нельзя. Подпись в канале **unlisted** не публикует
дополнение в каталоге AMO, проходит автоматическую проверку за минуты и даёт
файл, который ставится как обычное дополнение.

## Постоянная установка: подпись .xpi

Полная пошаговая инструкция — **[docs/SIGNING.md](docs/SIGNING.md)**: что такое AMO,
как получить API-ключи, подписать и установить расширение.

Коротко:

```bash
npm install
set WEB_EXT_API_KEY=user:12345:67        # Windows cmd
set WEB_EXT_API_SECRET=…
npm run sign                              # -> artifacts/*.xpi
```

Затем `about:addons` → шестерёнка → **Install Add-on From File…**

## Разработка

```bash
npm run lint     # web-ext lint, 0 ошибок обязательны
npm run start    # запустить Firefox с расширением
npm run build    # неподписанный zip в artifacts/
python -m pytest tests -q
```

CI (`.github/workflows/ci.yml`) гоняет pytest и `web-ext lint` на каждый push.

## Известные ограничения

- Метаданные иногда содержат дублирующиеся имена исполнителей — чинится отдельно.
- Хост обрабатывает одну загрузку за раз; очередь держится на стороне расширения.
