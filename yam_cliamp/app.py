"""
Main application controller for yam-cliamp.
Runs the main event loop, handles keyboard shortcuts (both EN and RU layouts),
and orchestrates the player backend, in-interface mood modal, and retro Winamp TUI.
"""

import sys
import time
import curses
from yam_cliamp.auth import get_stored_token, launch_browser_for_auth, get_wave_preference, save_wave_preference
from yam_cliamp.api_player import ApiPlayer
from yam_cliamp.ui import WinampUI, WAVE_MOOD_ITEMS
from yam_cliamp.wave_settings import set_wave_mood


class YamCliampApp:
    def __init__(self):
        self.token = get_stored_token()
        self.player: ApiPlayer | None = None
        self.ui: WinampUI | None = None
        self.running = True

    def ensure_auth(self):
        """Ensures valid token; launches browser if needed."""
        if not self.token:
            self.token = launch_browser_for_auth()
        self.player = ApiPlayer(self.token)
        try:
            self.player.init_api()
        except Exception as e:
            print(f"Ошибка токена ({e}). Открываем браузер для повторной авторизации...")
            self.token = launch_browser_for_auth()
            self.player = ApiPlayer(self.token)
            self.player.init_api()

    def run(self):
        self.ensure_auth()
        # Pre-load "Моя волна" with saved preference and start playing automatically
        try:
            pref = get_wave_preference()
            mood = pref.get("mood", "all")
            div = pref.get("diversity", "default")
            label = pref.get("label", "Моя волна")
            self.player.load_wave(mood=mood, diversity=div, label=label)
            if self.player.playlist:
                self.player.play_index(0)
        except Exception:
            pass

        curses.wrapper(self._main_loop)

    def _main_loop(self, stdscr):
        self.ui = WinampUI(stdscr)
        self.ui.set_status("Готово. [W] - Настроение волны в меню, [S] - Shuffle", 4.0)

        fps = 30.0
        frame_duration = 1.0 / fps

        while self.running:
            loop_start = time.time()

            try:
                key = stdscr.get_wch()
            except curses.error:
                key = None

            if key is not None:
                self._handle_key(key, stdscr)

            state = self.player.get_playback_state()

            self.ui.render(
                state=state,
                playlist=self.player.playlist,
                active_idx=self.player.current_index,
                source_name=self.player.source_name,
                shuffle=self.player.shuffle,
            )

            elapsed = time.time() - loop_start
            sleep_time = max(0.005, frame_duration - elapsed)
            time.sleep(sleep_time)

        if self.player:
            self.player.close()

    def _handle_key(self, key, stdscr):
        # Convert character strings to lowercase for dual EN/RU layout support
        ch = key.lower() if isinstance(key, str) else None

        # 1. Handle keys when Wave Mood Modal is OPEN
        if self.ui.show_wave_modal:
            if key == 27 or ch in ["q", "й"]:  # Escape or Q/Й
                self.ui.show_wave_modal = False
                return
            elif key == curses.KEY_UP:
                self.ui.wave_modal_idx = (self.ui.wave_modal_idx - 1) % len(WAVE_MOOD_ITEMS)
                return
            elif key == curses.KEY_DOWN:
                self.ui.wave_modal_idx = (self.ui.wave_modal_idx + 1) % len(WAVE_MOOD_ITEMS)
                return
            elif ch and "1" <= ch <= str(len(WAVE_MOOD_ITEMS)):
                self.ui.wave_modal_idx = int(ch) - 1
                self._apply_modal_wave_mood()
                return
            elif key in [10, 13, curses.KEY_ENTER] or ch in ["\n", "\r"]:
                self._apply_modal_wave_mood()
                return
            return

        # 2. Main Player Hotkeys (supporting both EN and RU layouts)
        if ch in ["q", "й"]:
            self.running = False
            return

        # Open Wave Mood Modal directly in interface: [W] / [Ц]
        if ch in ["w", "ц"]:
            self.ui.show_wave_modal = True
            return

        # Shuffle toggle: [S] / [Ы]
        elif ch in ["s", "ы"]:
            is_shuf = self.player.toggle_shuffle()
            self.ui.set_status(f"Случайный порядок (Shuffle): {'ВКЛ' if is_shuf else 'ВЫКЛ'}")

        # Playback controls
        elif ch in ["x", "ч"]:
            self.player.toggle_play()
            self.ui.set_status("Воспроизведение")
        elif ch in ["c", "с", " "]:
            self.player.toggle_play()
            self.ui.set_status("Пауза / Возобновить")
        elif ch in ["v", "м"]:
            self.player.stop()
            self.ui.set_status("Остановлено")
        elif ch in ["z", "я", "<", ",", "б"]:
            self.player.prev_track()
            self.ui.selected_playlist_idx = self.player.current_index
            self.ui.set_status("Предыдущий трек")
        elif ch in ["b", "и", ">", ".", "ю"]:
            self.player.next_track()
            self.ui.selected_playlist_idx = self.player.current_index
            self.ui.set_status("Следующий трек")

        # Volume controls
        elif ch in ["+", "="]:
            self.player.set_volume(5, is_delta=True)
            self.ui.set_status(f"Громкость: {self.player.volume}%")
        elif ch in ["-", "_"]:
            self.player.set_volume(-5, is_delta=True)
            self.ui.set_status(f"Громкость: {self.player.volume}%")

        # Seek controls
        elif key == curses.KEY_RIGHT:
            self.player.seek(10)
            self.ui.set_status("Перемотка: +10 сек")
        elif key == curses.KEY_LEFT:
            self.player.seek(-10)
            self.ui.set_status("Перемотка: -10 сек")

        # Playlist navigation
        elif key == curses.KEY_UP:
            if self.ui.selected_playlist_idx > 0:
                self.ui.selected_playlist_idx -= 1
        elif key == curses.KEY_DOWN:
            if self.ui.selected_playlist_idx < len(self.player.playlist) - 1:
                self.ui.selected_playlist_idx += 1
        elif key in [10, 13, curses.KEY_ENTER] or ch in ["\n", "\r"]:
            self.player.play_index(self.ui.selected_playlist_idx)
            self.ui.set_status(f"Играет трек #{self.ui.selected_playlist_idx + 1}")

        # Liked tracks: [L] / [Д]
        elif ch in ["l", "д"]:
            self.ui.set_status("Загрузка любимых треков...")
            self.player.load_likes()
            self.ui.selected_playlist_idx = 0
            if self.player.playlist:
                self.player.play_index(0)
            self.ui.set_status("Загружены любимые треки")

        # Visualizer toggle: [M] / [Ь]
        elif ch in ["m", "ь"]:
            self.ui.vis.toggle_mode()
            self.ui.set_status(f"Режим визуализатора: {self.ui.vis.mode}")

        # Search modal: [/]
        elif ch == "/":
            query = self._prompt_search(stdscr)
            if query:
                self.ui.set_status(f"Поиск: {query}...")
                self.player.search(query)
                self.ui.selected_playlist_idx = 0
                if self.player.playlist:
                    self.player.play_index(0)
                self.ui.set_status(f"Найдено {len(self.player.playlist)} треков")

        # Re-authenticate in browser: [A] / [Ф]
        elif ch in ["a", "ф"]:
            curses.endwin()
            self.token = launch_browser_for_auth()
            self.player = ApiPlayer(self.token)
            self.player.init_api()
            self.player.load_wave()
            self.ui = WinampUI(stdscr)
            self.ui.set_status("Авторизация обновлена!", 4.0)

    def _apply_modal_wave_mood(self):
        """Applies selected mood from modal to Yandex servers and reloads wave."""
        mood, char, label = WAVE_MOOD_ITEMS[self.ui.wave_modal_idx]
        self.ui.show_wave_modal = False
        self.ui.set_status(f"Настройка волны: {label}...")

        # Save preference so it persists as default for future launches
        save_wave_preference(mood, char, label)

        # Update on server (standard moods use rotor station settings)
        if mood != "lofi":
            set_wave_mood(self.token, mood=mood, diversity=char)
        # Reload playlist
        self.player.load_wave(mood=mood, diversity=char, label=label)
        self.ui.selected_playlist_idx = 0
        if self.player.playlist:
            self.player.play_index(0)
        self.ui.set_status(f"Включена волна: {label}", 4.0)

    def _prompt_search(self, stdscr) -> str:
        max_y, max_x = stdscr.getmaxyx()
        prompt = "Поиск в Яндекс Музыке: "
        stdscr.nodelay(False)
        curses.echo()
        curses.curs_set(1)

        stdscr.addstr(max_y - 1, 0, " " * (max_x - 1), curses.A_REVERSE)
        stdscr.addstr(max_y - 1, 2, prompt, curses.A_REVERSE | curses.A_BOLD)
        stdscr.refresh()

        try:
            raw = stdscr.getstr(max_y - 1, 2 + len(prompt), 40)
            query = raw.decode("utf-8", errors="ignore").strip()
        except Exception:
            query = ""

        curses.noecho()
        curses.curs_set(0)
        stdscr.nodelay(True)
        return query
