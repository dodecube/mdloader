"""Entry point: the native messaging loop the browser talks to."""

from __future__ import annotations

import logging

from . import media
from .config import Config, load_config
from .downloader import download, probe_yt_dlp, validate_url
from .messaging import configure_logging, read_message, send_error, send_progress, send_success

log = logging.getLogger("mdloader.host")


def handle_download(config: Config, url: str, use_cookies: bool, playlist: bool = False) -> None:
    send_progress("🚀 Загрузка плейлиста..." if playlist else "🚀 Запуск загрузки...", 5)

    valid, result = validate_url(url)
    if not valid:
        send_error(f"❌ {result}")
        return

    missing = config.missing_dependencies()
    if missing:
        send_error("❌ Не найдены зависимости:\n" + "\n".join(missing))
        return

    ok, message = probe_yt_dlp(config)
    if not ok:
        send_error(f"❌ {message}")
        return
    send_progress("✅ Зависимости проверены...", 15)

    outcome = download(config, result, use_cookies, playlist)
    if not outcome.ok:
        send_error(f"❌ {outcome.message}")
        return

    send_progress("🎨 Обработка обложек и тегов...", 96)
    media.process_downloads(config, outcome.files)
    media.cleanup(config.download_dir)

    if outcome.folder is not None:
        send_success(f"🎉 {outcome.message} → {outcome.folder.name}")
    else:
        send_success(f"🎉 {outcome.message}")


def handle(config: Config, message: dict) -> None:
    action = message.get("action")
    if action == "download":
        url = message.get("url")
        if not url:
            send_error("❌ URL не передан")
            return
        handle_download(
            config,
            url,
            bool(message.get("useCookies", False)),
            bool(message.get("playlist", False)),
        )
    elif action == "ping":
        ok, version = probe_yt_dlp(config)
        send_success(f"yt-dlp {version}") if ok else send_error(version)
    else:
        send_error(f"❌ Неизвестное действие: {action}")


def main() -> int:
    configure_logging()
    log.info("Native host started")
    try:
        config = load_config()
    except SystemExit as exc:
        send_error(f"❌ Конфигурация: {exc}")
        return 1

    while True:
        message = read_message()
        if message is None:
            log.info("Browser disconnected, exiting")
            return 0
        log.info("Received: %s", message)
        try:
            handle(config, message)
        except Exception as exc:  # noqa: BLE001 - the loop must survive any job failure
            log.exception("Unhandled error while processing message")
            send_error(f"💥 Внутренняя ошибка: {exc}")


if __name__ == "__main__":
    raise SystemExit(main())
