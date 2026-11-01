"""
Authentication module for Yandex Music.
Opens Chromium with the official Yandex OAuth authorization page:
https://oauth.yandex.ru/authorize?response_type=token&client_id=23cabbbdc6cd418abb4b39c32c41195d

User logs in (via QR-code, password, or phone + SMS/Yandex Key).
Upon successful login, Yandex redirects to https://music.yandex.ru/#access_token=...
The CDP listener intercepts the token, automatically terminates the browser,
and saves credentials to ~/.config/yam-cliamp/config.json and ~/.config/cliamp/config.toml.
"""

import os
import sys
import time
import json
import shutil
import urllib.request
import urllib.parse
import subprocess
from yandex_music import Client
from yandex_music.exceptions import DeviceAuthError

CONFIG_DIR = os.path.expanduser("~/.config/yam-cliamp")
CONFIG_FILE = os.path.join(CONFIG_DIR, "config.json")
PROFILE_DIR = os.path.join(CONFIG_DIR, "profile")
CLIAMP_CONFIG_FILE = os.path.expanduser("~/.config/cliamp/config.toml")

# Official working client ID used by Yandex Music
CLIENT_ID = "23cabbbdc6cd418abb4b39c32c41195d"
OAUTH_URL = f"https://oauth.yandex.ru/authorize?response_type=token&client_id={CLIENT_ID}"


def get_config() -> dict:
    if not os.path.exists(CONFIG_FILE):
        return {}
    try:
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def get_stored_token() -> str | None:
    return get_config().get("token")


def save_token(token: str, uid: str | None = None, expires_in: int | None = None):
    os.makedirs(CONFIG_DIR, exist_ok=True)
    cfg = get_config()
    cfg.update({
        "token": token,
        "uid": uid,
        "expires_in": expires_in,
        "saved_at": time.time(),
    })
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(cfg, f, indent=2, ensure_ascii=False)

    # Sync with cliamp config if possible
    sync_with_cliamp(token)


def get_wave_preference() -> dict:
    cfg = get_config()
    return cfg.get("wave", {
        "mood": "all",
        "diversity": "default",
        "label": "Моя волна (по умолчанию)",
    })


def save_wave_preference(mood: str, diversity: str, label: str):
    os.makedirs(CONFIG_DIR, exist_ok=True)
    cfg = get_config()
    cfg["wave"] = {
        "mood": mood,
        "diversity": diversity,
        "label": label,
    }
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(cfg, f, indent=2, ensure_ascii=False)


def sync_with_cliamp(token: str):
    """Write token into ~/.config/cliamp/config.toml so cliamp works seamlessly."""
    try:
        os.makedirs(os.path.dirname(CLIAMP_CONFIG_FILE), exist_ok=True)
        content = ""
        if os.path.exists(CLIAMP_CONFIG_FILE):
            with open(CLIAMP_CONFIG_FILE, "r", encoding="utf-8") as f:
                content = f.read()

        if "[yandex]" in content:
            lines = content.splitlines()
            new_lines = []
            in_yandex = False
            for line in lines:
                if line.strip().startswith("[") and not line.strip().startswith("[yandex]"):
                    in_yandex = False
                elif line.strip().startswith("[yandex]"):
                    in_yandex = True
                    new_lines.append(line)
                    new_lines.append("enabled = true")
                    new_lines.append(f'token = "{token}"')
                    continue

                if in_yandex:
                    if line.strip().startswith("token") or line.strip().startswith("enabled"):
                        continue
                new_lines.append(line)
            content = "\n".join(new_lines) + "\n"
        else:
            content += f'\n[yandex]\nenabled = true\ntoken = "{token}"\n'

        with open(CLIAMP_CONFIG_FILE, "w", encoding="utf-8") as f:
            f.write(content.strip() + "\n")

        lua_plugin = os.path.expanduser("~/.config/cliamp/plugins/yandex-wave.lua")
        if os.path.exists(lua_plugin):
            with open(lua_plugin, "r", encoding="utf-8") as f:
                lcontent = f.read()
            import re
            lcontent = re.sub(r'local token = ".*?"', f'local token = "{token}"', lcontent)
            with open(lua_plugin, "w", encoding="utf-8") as f:
                f.write(lcontent)
    except Exception as e:
        print(f"Warning: could not sync with cliamp config: {e}", file=sys.stderr)


def find_browser_executable() -> str:
    for name in ["chromium", "google-chrome", "google-chrome-stable", "brave"]:
        path = shutil.which(name)
        if path:
            return path
    raise RuntimeError("Не найден браузер (Chromium/Chrome) в системе!")


def launch_browser_for_auth(port: int = 9222) -> str:
    """
    Opens browser with official Yandex OAuth authorization URL.
    Monitors DevTools tabs for redirect with #access_token=...,
    intercepts token, saves it, and automatically closes the browser.
    """
    browser_bin = find_browser_executable()
    os.makedirs(PROFILE_DIR, exist_ok=True)

    # Device code backup flow
    device_client = Client()
    device_code = None
    try:
        device_code = device_client.request_device_code(client_id=CLIENT_ID)
    except Exception:
        pass

    print("\n" + "\033[1;36m" + "╔" + "═" * 68 + "╗" + "\033[0m")
    print("\033[1;36m" + "║" + "\033[0m" + "                    \033[1;33mВХОД В ЯНДЕКС МУЗЫКУ\033[0m                            " + "\033[1;36m" + "║" + "\033[0m")
    print("\033[1;36m" + "╠" + "═" * 68 + "╣" + "\033[0m")
    print("\033[1;36m" + "║" + "\033[0m" + " В открывшемся окне браузера подтвердите вход в свой Яндекс ID:     " + "\033[1;36m" + "║" + "\033[0m")
    print("\033[1;36m" + "║" + "\033[0m" + "                                                                    " + "\033[1;36m" + "║" + "\033[0m")
    print("\033[1;36m" + "║" + "\033[0m" + "  \033[1;32m1. Самый быстрый способ:\033[0m нажмите «QR-код» в окне браузера         " + "\033[1;36m" + "║" + "\033[0m")
    print("\033[1;36m" + "║" + "\033[0m" + "     и наведите камеру телефона (или приложения Яндекс Музыка)       " + "\033[1;36m" + "║" + "\033[0m")
    print("\033[1;36m" + "║" + "\033[0m" + "                                                                    " + "\033[1;36m" + "║" + "\033[0m")
    print("\033[1;36m" + "║" + "\033[0m" + "  \033[1;37m2. Обычный вход:\033[0m введите номер телефона / логин, пароль           " + "\033[1;36m" + "║" + "\033[0m")
    print("\033[1;36m" + "║" + "\033[0m" + "     и код из СМС или приложения «Яндекс Ключ»                      " + "\033[1;36m" + "║" + "\033[0m")
    print("\033[1;36m" + "║" + "\033[0m" + "                                                                    " + "\033[1;36m" + "║" + "\033[0m")
    print("\033[1;36m" + "║" + "\033[0m" + " Сразу после входа окно браузера автоматически закроется!           " + "\033[1;36m" + "║" + "\033[0m")
    print("\033[1;36m" + "╚" + "═" * 68 + "╝" + "\033[0m\n")

    cmd = [
        browser_bin,
        f"--user-data-dir={PROFILE_DIR}",
        f"--remote-debugging-port={port}",
        f"--app={OAUTH_URL}",
        "--no-first-run",
        "--no-default-browser-check",
    ]

    proc = subprocess.Popen(
        cmd,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )

    token = None
    start_wait = time.time()
    try:
        while time.time() - start_wait < 300:  # 5 minutes
            if proc.poll() is not None:
                # Browser closed by user
                break

            # 1. Check CDP tabs for redirect URL with access_token
            try:
                with urllib.request.urlopen(f"http://127.0.0.1:{port}/json/list", timeout=0.5) as resp:
                    tabs = json.loads(resp.read().decode())
                    for tab in tabs:
                        url = tab.get("url", "")
                        if "access_token=" in url:
                            frag = urllib.parse.urlparse(url).fragment
                            params = dict(urllib.parse.parse_qsl(frag))
                            token = params.get("access_token")
                            uid = params.get("uid")
                            expires_in = int(params.get("expires_in", 31536000))
                            if token:
                                save_token(token, uid=uid, expires_in=expires_in)
                                break
            except Exception:
                pass

            if token:
                break

            # 2. Check Device Code if active
            if device_code:
                try:
                    tok_obj = device_client.poll_device_token(device_code.device_code, client_id=CLIENT_ID)
                    if tok_obj and tok_obj.access_token:
                        token = tok_obj.access_token
                        save_token(token)
                        break
                except DeviceAuthError:
                    pass
                except Exception:
                    pass

            time.sleep(0.4)
    finally:
        if proc.poll() is None:
            proc.terminate()
            try:
                proc.wait(timeout=2)
            except subprocess.TimeoutExpired:
                proc.kill()

    if not token:
        token = get_stored_token()

    if not token:
        raise RuntimeError("Не удалось получить токен авторизации. Попробуйте еще раз.")

    print("\n✅ Авторизация успешна! Токен сохранён.\n")
    return token
