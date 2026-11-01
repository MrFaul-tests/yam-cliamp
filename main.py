#!/usr/bin/env python3
"""
yam-cliamp: Retro Winamp / cliamp Terminal Player for Yandex Music.
Launches the official cliamp player with Yandex Music provider (--provider yandex) by default,
handling browser-based authorization and My Wave mood/character configuration.
"""

import sys
import os
import shutil
import argparse

# Add package directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from yam_cliamp.auth import launch_browser_for_auth, get_stored_token, CONFIG_FILE, CLIAMP_CONFIG_FILE
from yam_cliamp.app import YamCliampApp
from yam_cliamp.wave_settings import set_wave_mood, interactive_wave_setup


def main():
    parser = argparse.ArgumentParser(
        description="yam-cliamp: Терминальный плеер Яндекс Музыки (оригинальный cliamp)"
    )
    parser.add_argument(
        "--auth",
        action="store_true",
        help="Открыть браузер для входа / обновления токена Яндекс Музыки",
    )
    parser.add_argument(
        "--status",
        action="store_true",
        help="Показать статус авторизации и конфигурации",
    )
    parser.add_argument(
        "--wave",
        action="store_true",
        help="Интерактивно выбрать настроение, характер и язык «Моей волны» перед запуском",
    )
    parser.add_argument(
        "--lofi",
        action="store_true",
        help="Запустить волну «Моя волна: Lo-Fi» (чилл, фокус, lofi hip-hop)",
    )
    parser.add_argument(
        "--mood",
        choices=["active", "fun", "calm", "sad", "all", "lofi"],
        help="Настроение волны: active (бодрое), fun (весёлое), calm (спокойное), sad (грустное), all (любое), lofi (лоу-фай)",
    )
    parser.add_argument(
        "--character",
        choices=["favorite", "discover", "popular", "default"],
        help="Характер треков: favorite (любимое), discover (незнакомое), popular (популярное), default (любое)",
    )
    parser.add_argument(
        "--lang",
        choices=["any", "russian", "not-russian"],
        help="Язык треков: any (любой), russian (русский), not-russian (иностранный)",
    )
    parser.add_argument(
        "--py",
        action="store_true",
        help="Запустить альтернативный Python curses TUI плеер",
    )

    args, extra_args = parser.parse_known_args()

    if args.status:
        token = get_stored_token()
        print(f"Конфиг yam-cliamp: {CONFIG_FILE}")
        print(f"Конфиг cliamp:     {CLIAMP_CONFIG_FILE}")
        if token:
            masked = token[:6] + "..." + token[-4:] if len(token) > 10 else "***"
            print(f"Статус токена:     ✅ Авторизован ({masked})")
        else:
            print("Статус токена:     ❌ Не авторизован (запустите yam-cliamp для авторизации)")
        return

    if args.auth:
        launch_browser_for_auth()
        print("Готово! Токен обновлен и сохранён.")
        return

    # Check authorization
    token = get_stored_token()
    if not token:
        print("Токен Яндекс Музыки не найден. Открываем окно для входа...")
        token = launch_browser_for_auth()

    # Apply wave mood settings if passed via CLI flags
    is_lofi = args.lofi or (args.mood == "lofi")
    if args.wave:
        interactive_wave_setup(token)
    elif is_lofi:
        from yam_cliamp.auth import save_wave_preference
        save_wave_preference("lofi", "default", "🎧 Lo-Fi (чилл / фокус / lofi hip-hop)")
        print("🎧 Включен режим «Моя волна: Lo-Fi»!")
    elif args.mood or args.character or args.lang:
        mood = args.mood or "all"
        char = args.character or "default"
        lang = args.lang or "any"
        print(f"Применяем настройки волны: настроение={mood}, характер={char}, язык={lang}...")
        set_wave_mood(token, mood=mood, diversity=char, language=lang)
        print("✅ Настройки применены!")

    # If --py flag was explicitly requested, run the Python curses TUI
    if args.py:
        app = YamCliampApp()
        app.run()
        return

    # DEFAULT BEHAVIOR:
    # Run official cliamp with --provider yandex
    cliamp_bin = shutil.which("cliamp")
    if cliamp_bin:
        cmd = [cliamp_bin, "--provider", "yandex"]
        if is_lofi:
            cmd += ["--playlist", "wave:lofi", "--auto-play"]
        cmd += extra_args
        os.execvp(cliamp_bin, cmd)
    else:
        # Fallback to python TUI if cliamp is not in PATH
        app = YamCliampApp()
        app.run()


if __name__ == "__main__":
    main()
