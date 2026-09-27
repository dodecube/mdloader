"""Register (or remove) the mdloader native messaging host for Firefox / Zen.

    python native-host/install_firefox_host.py             # install
    python native-host/install_firefox_host.py --uninstall # remove

Windows uses a registry key; Linux and macOS use a well-known directory.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

HOST_NAME = "com.example.youtube_downloader"
EXTENSION_ID = "mdloader@dodecube"

HERE = Path(__file__).resolve().parent
REPO_ROOT = HERE.parent
LAUNCHER = HERE / ("run_msg.bat" if os.name == "nt" else "run_msg.sh")
MANIFEST_NAME = f"{HOST_NAME}.json"

REG_PATH = rf"Software\Mozilla\NativeMessagingHosts\{HOST_NAME}"

# Where Firefox looks for host manifests on non-Windows platforms.
UNIX_DIRS = {
    "darwin": Path.home() / "Library/Application Support/Mozilla/NativeMessagingHosts",
    "linux": Path.home() / ".mozilla/native-messaging-hosts",
}


def build_manifest() -> dict:
    return {
        "name": HOST_NAME,
        "description": "mdloader native host (yt-dlp bridge)",
        "path": str(LAUNCHER),
        "type": "stdio",
        "allowed_extensions": [EXTENSION_ID],
    }


def target_dir() -> Path:
    if os.name == "nt":
        return HERE
    directory = UNIX_DIRS.get(sys.platform)
    if directory is None:
        raise SystemExit(f"Unsupported platform: {sys.platform}")
    return directory


def install() -> None:
    if not LAUNCHER.exists():
        raise SystemExit(f"Launcher not found: {LAUNCHER}")
    if not (REPO_ROOT / "config.json").exists():
        print("! config.json is missing — copy config.example.json and set your paths.")

    directory = target_dir()
    directory.mkdir(parents=True, exist_ok=True)
    manifest_path = directory / MANIFEST_NAME
    manifest_path.write_text(json.dumps(build_manifest(), indent=2), encoding="utf-8")
    print(f"Wrote {manifest_path}")

    if os.name == "nt":
        import winreg

        with winreg.CreateKey(winreg.HKEY_CURRENT_USER, REG_PATH) as key:
            winreg.SetValueEx(key, None, 0, winreg.REG_SZ, str(manifest_path))
        print(rf"Registered HKCU\{REG_PATH}")
    else:
        LAUNCHER.chmod(0o755)

    print(f"Host '{HOST_NAME}' is now available to extension {EXTENSION_ID}.")


def uninstall() -> None:
    manifest_path = target_dir() / MANIFEST_NAME
    if manifest_path.exists():
        manifest_path.unlink()
        print(f"Removed {manifest_path}")

    if os.name == "nt":
        import winreg

        try:
            winreg.DeleteKey(winreg.HKEY_CURRENT_USER, REG_PATH)
            print("Removed registry key.")
        except FileNotFoundError:
            print("Registry key was not present.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--uninstall", action="store_true", help="remove the registration")
    args = parser.parse_args()
    uninstall() if args.uninstall else install()
