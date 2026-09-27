"""Register the mdloader native messaging host for Firefox / Zen on Windows.

Usage:  python native-host/install_firefox_host.py
Uninstall: python native-host/install_firefox_host.py --uninstall
"""
import json
import os
import sys
import winreg

HOST_NAME = "com.example.youtube_downloader"
EXT_ID = "mdloader@dodecube"
HERE = os.path.dirname(os.path.abspath(__file__))
MANIFEST_PATH = os.path.join(HERE, "com.example.youtube_downloader.firefox.json")
BAT_PATH = os.path.join(HERE, "run_msg.bat")
REG_KEY = r"Software\Mozilla\NativeMessagingHosts\\" + HOST_NAME


def install():
    manifest = {
        "name": HOST_NAME,
        "description": "mdloader native host (yt-dlp bridge)",
        "path": BAT_PATH,
        "type": "stdio",
        "allowed_extensions": [EXT_ID],
    }
    with open(MANIFEST_PATH, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2)
    with winreg.CreateKey(winreg.HKEY_CURRENT_USER, REG_KEY) as key:
        winreg.SetValueEx(key, None, 0, winreg.REG_SZ, MANIFEST_PATH)
    print("Installed native host manifest:", MANIFEST_PATH)
    print("Registry:", "HKCU\\" + REG_KEY)


def uninstall():
    try:
        winreg.DeleteKey(winreg.HKEY_CURRENT_USER, REG_KEY)
        print("Removed registry key.")
    except FileNotFoundError:
        print("Registry key not present.")


if __name__ == "__main__":
    if os.name != "nt":
        sys.exit("This installer is Windows-only.")
    uninstall() if "--uninstall" in sys.argv else install()
