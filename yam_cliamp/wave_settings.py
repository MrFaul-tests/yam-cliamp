"""
Module for configuring 'Моя волна' (My Wave) settings:
Mood (energy), Diversity (character), and Language.
Saves settings to Yandex Music servers for the user's 'user:onyourwave' station.
"""

from yandex_music import Client

MOODS = {
    "1": ("active", "🔥 Бодрое (энергичное)"),
    "2": ("fun", "😄 Весёлое (радостное)"),
    "3": ("calm", "☕ Спокойное (релакс)"),
    "4": ("sad", "🌧 Грустное (меланхоличное)"),
    "5": ("all", "🎲 Любое (по умолчанию)"),
}

DIVERSITIES = {
    "1": ("favorite", "❤️ Любимое (знакомые треки и лайки)"),
    "2": ("discover", "✨ Незнакомое (открытия и новинки)"),
    "3": ("popular", "⭐ Популярное (хиты)"),
    "4": ("default", "🎲 Любое (микс)"),
}

LANGUAGES = {
    "1": ("any", "🌍 Любой язык"),
    "2": ("russian", "🇷🇺 Только на русском"),
    "3": ("not-russian", "🌐 Только иностранный"),
}


def set_wave_mood(
    token: str,
    mood: str = "all",
    diversity: str = "default",
    language: str = "any",
) -> bool:
    """Sets wave settings directly on Yandex servers for user:onyourwave."""
    try:
        client = Client(token).init()
        return bool(
            client.rotor_station_settings2(
                station="user:onyourwave",
                mood_energy=mood,
                diversity=diversity,
                language=language,
            )
        )
    except Exception as e:
        print(f"Ошибка настройки волны: {e}")
        return False


def interactive_wave_setup(token: str) -> tuple[str, str, str]:
    """Interactive CLI menu to choose wave mood, character, and language."""
    print("\n" + "\033[1;36m" + "╔" + "═" * 60 + "╗" + "\033[0m")
    print("\033[1;36m" + "║" + "\033[0m" + "             \033[1;33mНАСТРОЙКА «МОЕЙ ВОЛНЫ» (ЯНДЕКС МУЗЫКА)\033[0m          " + "\033[1;36m" + "║" + "\033[0m")
    print("\033[1;36m" + "╚" + "═" * 60 + "╝" + "\033[0m\n")

    # 1. Настроение
    print("\033[1;32m1. Выберите настроение:\033[0m")
    for k, (_, label) in MOODS.items():
        print(f"   [{k}] {label}")
    ans_m = input("   Выберите пункт (1-5, Enter = Любое): ").strip()
    mood = MOODS.get(ans_m, ("all", ""))[0]

    # 2. Характер
    print("\n\033[1;32m2. Выберите характер треков:\033[0m")
    for k, (_, label) in DIVERSITIES.items():
        print(f"   [{k}] {label}")
    ans_d = input("   Выберите пункт (1-4, Enter = Любое): ").strip()
    diversity = DIVERSITIES.get(ans_d, ("default", ""))[0]

    # 3. Язык
    print("\n\033[1;32m3. Выберите язык треков:\033[0m")
    for k, (_, label) in LANGUAGES.items():
        print(f"   [{k}] {label}")
    ans_l = input("   Выберите пункт (1-3, Enter = Любой): ").strip()
    language = LANGUAGES.get(ans_l, ("any", ""))[0]

    print("\nСохраняем настройки в вашем профиле Яндекс Музыки...")
    ok = set_wave_mood(token, mood=mood, diversity=diversity, language=language)
    if ok:
        print("✅ Настройки «Моей волны» успешно сохранены!\n")
    else:
        print("⚠️ Не удалось обновить настройки на сервере.\n")

    return mood, diversity, language
