#!/usr/bin/env python3
"""
yam-cliamp: Retro Winamp / cliamp Terminal Player for Yandex Music.
Launches the full interactive Winamp TUI player by default with in-interface
Wave Mood selector, spectrum visualizer, playlist, and hotkeys.
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
        description="yam-cliamp: Терминальный ретро-плеер Яндекс Музыки (Winamp / cliamp TUI)"
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
        "--mood",
        choices=["active", "fun", "calm", "sad", "all"],
        help="Настроение волны: active (бодрое), fun (весёлое), calm (спокойное), sad (грустное), all (любое)",
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
        "--cliamp",
        action="store_true",
        help="Запустить внешний Go-клиент /usr/bin/cliamp вместо встроенного TUI",
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
    if args.wave:
        interactive_wave_setup(token)
    elif args.mood or args.character or args.lang:
        mood = args.mood or "all"
        char = args.character or "default"
        lang = args.lang or "any"
        print(f"Применяем настройки волны: настроение={mood}, характер={char}, язык={lang}...")
        set_wave_mood(token, mood=mood, diversity=char, language=lang)
        print("✅ Настройки применены!")

    # If --cliamp flag was explicitly requested, delegate to /usr/bin/cliamp
    if args.cliamp:
        cliamp_bin = shutil.which("cliamp")
        if cliamp_bin:
            cmd = [cliamp_bin, "--provider", "yandex"] + extra_args
            os.execvp(cliamp_bin, cmd)

    # DEFAULT BEHAVIOR:
    # Run our dedicated TUI player with in-interface Wave Mood modal,
    # spectrum analyzer, and dual EN/RU keyboard support!
    app = YamCliampApp()
    app.run()


if __name__ == "__main__":
    main()
