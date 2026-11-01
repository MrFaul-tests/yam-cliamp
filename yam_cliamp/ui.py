"""
Winamp 2.x / cliamp Retro Terminal UI for Yandex Music.
Renders the iconic green/amber/red spectrum analyzer, scrolling marquee title,
LED time display, seek bar, volume control, scrollable playlist editor,
and in-interface interactive wave mood selection modal.
"""

import curses
import time
from yam_cliamp.visualizer import WinampVisualizer

WAVE_MOOD_ITEMS = [
    ("all", "default", "🎲 По умолчанию (стандартная Моя волна)"),
    ("active", "default", "🔥 Бодрое (энергичное)"),
    ("calm", "default", "☕ Спокойное (релакс)"),
    ("fun", "default", "😄 Весёлое (радостное)"),
    ("sad", "default", "🌧 Грустное (меланхоличное)"),
    ("all", "favorite", "❤️ Любимое (треки из лайков)"),
    ("all", "discover", "✨ Незнакомое (открытия и новинки)"),
    ("all", "popular", "⭐ Популярное (топовые хиты)"),
]


class WinampUI:
    def __init__(self, stdscr):
        self.stdscr = stdscr
        self.vis = WinampVisualizer(bands=24, max_height=6)
        self.marquee_offset = 0
        self.last_marquee_time = time.time()
        self.selected_playlist_idx = 0
        self.playlist_scroll_top = 0
        self.status_msg = ""
        self.status_msg_time = 0.0

        # Modal state
        self.show_wave_modal = False
        self.wave_modal_idx = 0

        # Setup curses
        curses.curs_set(0)
        curses.start_color()
        curses.use_default_colors()
        self.stdscr.nodelay(True)
        self.stdscr.keypad(True)

        # Initialize color pairs
        curses.init_pair(1, curses.COLOR_GREEN, -1)   # Green
        curses.init_pair(2, curses.COLOR_YELLOW, -1)  # Yellow / Amber
        curses.init_pair(3, curses.COLOR_RED, -1)     # Red
        curses.init_pair(4, curses.COLOR_CYAN, -1)    # Cyan
        curses.init_pair(5, curses.COLOR_BLACK, curses.COLOR_GREEN) # Highlight
        curses.init_pair(6, curses.COLOR_WHITE, -1)   # White
        curses.init_pair(7, curses.COLOR_BLACK, curses.COLOR_YELLOW) # Yellow highlight

    def set_status(self, msg: str, duration: float = 3.0):
        self.status_msg = msg
        self.status_msg_time = time.time() + duration

    def render(self, state: dict, playlist: list, active_idx: int, source_name: str, shuffle: bool = False):
        self.stdscr.erase()
        max_y, max_x = self.stdscr.getmaxyx()

        if max_y < 24 or max_x < 78:
            self.stdscr.addstr(0, 0, "Окно терминала слишком маленькое. Увеличьте размер (минимум 80x25).", curses.color_pair(3))
            self.stdscr.refresh()
            return

        is_playing = state.get("isPlaying", False)
        pos = state.get("position", 0)
        dur = state.get("duration", 0)
        vol = state.get("volume", 80)
        title = state.get("title", "Yandex Music")
        artist = state.get("artist", "")
        full_title = f"{artist} - {title}" if artist else title

        # Update visualizer physics
        self.vis.update(is_playing, pos)

        # Draw Frame 1: MAIN WINAMP PLAYER (Rows 0 .. 13)
        self._draw_main_player(0, 0, max_x, state, full_title, pos, dur, vol, is_playing, shuffle)

        # Draw Frame 2: EQUALIZER / STATUS (Rows 14 .. 16)
        self._draw_equalizer(14, 0, max_x, source_name)

        # Draw Frame 3: PLAYLIST EDITOR (Rows 17 .. max_y - 2)
        pl_height = max_y - 19
        self._draw_playlist(17, 0, max_x, pl_height, playlist, active_idx)

        # Draw Footer / Help bar (Row max_y - 1)
        self._draw_footer(max_y - 1, 0, max_x)

        # Draw Modal overlay if open
        if self.show_wave_modal:
            self._draw_wave_modal(max_y, max_x)

        self.stdscr.refresh()

    def _draw_main_player(self, top: int, left: int, width: int, state: dict, title: str, pos: int, dur: int, vol: int, is_playing: bool, shuffle: bool):
        c_cyan = curses.color_pair(4)
        c_green = curses.color_pair(1)
        c_yellow = curses.color_pair(2)
        c_red = curses.color_pair(3)
        c_white = curses.color_pair(6)

        w = min(width - 2, 78)

        # Title border
        title_str = " WINAMP 2.91 ─ [ YANDEX MUSIC ] "
        border_top = "┌─" + title_str + "─" * max(0, w - len(title_str) - 3) + "┐"
        self.stdscr.addstr(top, left, border_top[:w], c_cyan | curses.A_BOLD)

        # Side walls
        for y in range(top + 1, top + 13):
            self.stdscr.addstr(y, left, "│", c_cyan)
            self.stdscr.addstr(y, left + w - 1, "│", c_cyan)

        # Row 1: Time display (left), Marquee title (mid), Bitrate (right)
        time_str = f"{pos // 60:02d}:{pos % 60:02d}"
        time_box = f"┌TIME┐ [{time_str}]"
        self.stdscr.addstr(top + 1, left + 2, time_box, c_green | curses.A_BOLD)

        # Marquee
        marquee_w = w - 38
        if marquee_w > 10:
            now = time.time()
            if now - self.last_marquee_time > 0.2:
                self.marquee_offset += 1
                self.last_marquee_time = now

            scroll_text = f"*** {title} ***   ·   "
            if len(scroll_text) > 0:
                idx = self.marquee_offset % len(scroll_text)
                disp = (scroll_text + scroll_text)[idx : idx + marquee_w]
                self.stdscr.addstr(top + 1, left + 18, disp[:marquee_w], c_green)

        # Bitrate info box
        kbps_box = "┌KBPS┐ [320k]"
        self.stdscr.addstr(top + 1, left + w - 16, kbps_box, c_yellow)

        # Row 2: Visualizer box + Volume & Controls
        vis_top = top + 3
        self.stdscr.addstr(vis_top - 1, left + 2, "┌─ SPECTRUM ANALYZER ────────┐", c_cyan)
        for vy in range(6):
            self.stdscr.addstr(vis_top + vy, left + 2, "│", c_cyan)
            self.stdscr.addstr(vis_top + vy, left + 31, "│", c_cyan)
        self.stdscr.addstr(vis_top + 6, left + 2, "└────────────────────────────┘", c_cyan)

        # Render spectrum bars
        blocks = [" ", " ", "▂", "▃", "▄", "▅", "▆", "▇", "█"]
        peak_glyph = "⎺"
        H = 6
        for row in range(H):
            curr_row_from_bottom = H - 1 - row
            row_ratio = curr_row_from_bottom / float(H - 1)
            if row_ratio > 0.66:
                attr = c_red | curses.A_BOLD
            elif row_ratio > 0.33:
                attr = c_yellow | curses.A_BOLD
            else:
                attr = c_green

            for i in range(min(28, self.vis.bands)):
                bval = self.vis.bar_heights[i]
                pval = self.vis.peak_positions[i]
                has_peak = (int(pval) == curr_row_from_bottom) and (pval > 0.1)

                if bval >= curr_row_from_bottom + 1:
                    ch = "█"
                elif bval > curr_row_from_bottom:
                    fraction = bval - curr_row_from_bottom
                    ch = blocks[max(1, min(8, int(fraction * 8)))]
                elif has_peak:
                    ch = peak_glyph
                else:
                    ch = " "

                try:
                    self.stdscr.addstr(vis_top + row, left + 3 + i, ch, attr)
                except curses.error:
                    pass

        # Right of Visualizer: Volume, Balance, Status
        side_left = left + 34
        self.stdscr.addstr(vis_top - 1, side_left, "┌─ CONTROLS ────────────────────────┐", c_cyan)
        for sy in range(6):
            self.stdscr.addstr(vis_top + sy, side_left, "│", c_cyan)
            self.stdscr.addstr(vis_top + sy, left + w - 3, "│", c_cyan)
        self.stdscr.addstr(vis_top + 6, side_left, "└───────────────────────────────────┘", c_cyan)

        # Volume bar
        vol_filled = int((vol / 100.0) * 12)
        vol_bar = "█" * vol_filled + "░" * (12 - vol_filled)
        self.stdscr.addstr(vis_top + 1, side_left + 2, f"VOLUME: [{vol_bar}] {vol}%", c_white)

        # Play state indicator
        state_str = "▶ PLAYING" if is_playing else "⏸ PAUSED "
        state_color = c_green | curses.A_BOLD if is_playing else c_yellow | curses.A_BOLD
        self.stdscr.addstr(vis_top + 3, side_left + 2, f"STATE:  {state_str}", state_color)

        # Mode indicator + Shuffle
        shuf_str = "[SHUF: ON]" if shuffle else "[SHUF: OFF]"
        shuf_color = c_green | curses.A_BOLD if shuffle else c_white
        self.stdscr.addstr(vis_top + 4, side_left + 2, f"VIS: [{self.vis.mode.upper()}]  ", c_yellow)
        self.stdscr.addstr(vis_top + 4, side_left + 16, shuf_str, shuf_color)

        # Row 10: Seek bar / progress
        seek_top = top + 10
        total_bar_w = w - 24
        if total_bar_w > 10:
            ratio = (pos / float(dur)) if dur > 0 else 0.0
            ratio = max(0.0, min(1.0, ratio))
            head_idx = int(ratio * (total_bar_w - 1))

            seek_line = []
            for idx in range(total_bar_w):
                if idx == head_idx:
                    seek_line.append("●")
                elif idx < head_idx:
                    seek_line.append("━")
                else:
                    seek_line.append("─")
            seek_str = "".join(seek_line)

            pos_s = f"{pos // 60:02d}:{pos % 60:02d}"
            dur_s = f"{dur // 60:02d}:{dur % 60:02d}"
            self.stdscr.addstr(seek_top, left + 2, f"{pos_s}  {seek_str}  {dur_s}", c_green)

        # Row 11: Button transport bar
        btn_top = top + 11
        buttons = "[⏮ Z] PREV   [▶ X] PLAY   [⏸ C] PAUSE   [⏹ V] STOP   [⏭ B] NEXT   [M] VIS"
        self.stdscr.addstr(btn_top, left + 4, buttons, c_white | curses.A_BOLD)

        # Bottom border of main player
        self.stdscr.addstr(top + 12, left, "└" + "─" * (w - 2) + "┘", c_cyan)

    def _draw_equalizer(self, top: int, left: int, width: int, source_name: str):
        c_cyan = curses.color_pair(4)
        c_yellow = curses.color_pair(2)

        w = min(width - 2, 78)
        header = f"┌─ EQUALIZER · [ SOURCE: {source_name} ] "
        self.stdscr.addstr(top, left, header + "─" * max(0, w - len(header) - 1) + "┐", c_cyan)
        eq_labels = "  60Hz  170Hz  310Hz  600Hz   1kHz   3kHz   6kHz  12kHz  14kHz  16kHz"
        eq_values = "  +2dB   +3dB   +1dB    0dB   +1dB   +4dB   +3dB   +2dB   +1dB   +3dB"
        self.stdscr.addstr(top + 1, left, "│", c_cyan)
        self.stdscr.addstr(top + 1, left + 2, eq_labels[: w - 4], c_yellow)
        self.stdscr.addstr(top + 1, left + w - 1, "│", c_cyan)

        self.stdscr.addstr(top + 2, left, "└" + "─" * (w - 2) + "┘", c_cyan)

    def _draw_playlist(self, top: int, left: int, width: int, height: int, playlist: list, active_idx: int):
        c_cyan = curses.color_pair(4)
        c_green = curses.color_pair(1)
        c_white = curses.color_pair(6)
        c_highlight = curses.color_pair(5)

        w = min(width - 2, 78)
        header = f"┌─ WINAMP PLAYLIST EDITOR ({len(playlist)} tracks) "
        self.stdscr.addstr(top, left, header + "─" * max(0, w - len(header) - 1) + "┐", c_cyan)

        if self.selected_playlist_idx >= len(playlist):
            self.selected_playlist_idx = max(0, len(playlist) - 1)

        content_rows = max(1, height - 2)
        if self.selected_playlist_idx < self.playlist_scroll_top:
            self.playlist_scroll_top = self.selected_playlist_idx
        elif self.selected_playlist_idx >= self.playlist_scroll_top + content_rows:
            self.playlist_scroll_top = self.selected_playlist_idx - content_rows + 1

        for r in range(content_rows):
            curr_y = top + 1 + r
            self.stdscr.addstr(curr_y, left, "│", c_cyan)
            self.stdscr.addstr(curr_y, left + w - 1, "│", c_cyan)

            item_idx = self.playlist_scroll_top + r
            if item_idx < len(playlist):
                t = playlist[item_idx]
                is_active = (item_idx == active_idx)
                is_selected = (item_idx == self.selected_playlist_idx)

                marker = "▶" if is_active else " "
                dur_str = getattr(t, "duration_str", "03:00")
                num_str = f"{item_idx + 1:2d}."
                text = f" {marker} {num_str} {t.artist} - {t.title}"

                max_text_w = w - len(dur_str) - 8
                display_line = f"{text[:max_text_w]:<{max_text_w}} {dur_str:>6s} "

                attr = c_highlight if is_selected else (c_green if is_active else c_white)
                self.stdscr.addstr(curr_y, left + 2, display_line[: w - 4], attr)
            else:
                self.stdscr.addstr(curr_y, left + 2, " " * (w - 4), c_white)

        bottom = "└" + "─" * (w - 2) + "┘"
        self.stdscr.addstr(top + content_rows + 1, left, bottom, c_cyan)

    def _draw_footer(self, y: int, left: int, width: int):
        c_yellow = curses.color_pair(2)
        c_green = curses.color_pair(1)

        if time.time() < self.status_msg_time and self.status_msg:
            msg = f"  >>> {self.status_msg} <<<"
            self.stdscr.addstr(y, left, msg[: width - 1], c_green | curses.A_BOLD)
            return

        keys = "[Z/B] Треки  [X/C/V] Плеер  [W] НАСТРОЕНИЕ ВОЛНЫ  [S] Shuffle  [L] Лайки  [/] Поиск  [Q] Выход"
        self.stdscr.addstr(y, left, keys[: width - 1], c_yellow)

    def _draw_wave_modal(self, max_y: int, max_x: int):
        """Draws centered pop-up modal to select wave mood directly in TUI."""
        c_cyan = curses.color_pair(4)
        c_yellow = curses.color_pair(2)
        c_highlight = curses.color_pair(5)
        c_white = curses.color_pair(6)

        box_w = 56
        box_h = len(WAVE_MOOD_ITEMS) + 5
        top = max(1, (max_y - box_h) // 2)
        left = max(2, (max_x - box_w) // 2)

        # Clear box area
        for r in range(box_h):
            self.stdscr.addstr(top + r, left, " " * box_w, curses.A_NORMAL)

        # Header
        header = "╔═════════════════ НАСТРОЕНИЕ «МОЕЙ ВОЛНЫ» ═════════════════╗"
        self.stdscr.addstr(top, left, header[:box_w], c_yellow | curses.A_BOLD)

        self.stdscr.addstr(top + 1, left, "║", c_yellow)
        self.stdscr.addstr(top + 1, left + box_w - 1, "║", c_yellow)

        # Items
        for idx, (_, _, label) in enumerate(WAVE_MOOD_ITEMS):
            y = top + 2 + idx
            self.stdscr.addstr(y, left, "║", c_yellow)
            self.stdscr.addstr(y, left + box_w - 1, "║", c_yellow)

            is_curr = (idx == self.wave_modal_idx)
            prefix = " ▸ " if is_curr else "   "
            num = f"[{idx + 1}] "
            line_text = f"{prefix}{num}{label}"
            display = f"{line_text:<{box_w - 4}}"

            attr = c_highlight if is_curr else c_white
            self.stdscr.addstr(y, left + 2, display[:box_w - 4], attr)

        # Footer
        bottom_y = top + 2 + len(WAVE_MOOD_ITEMS)
        self.stdscr.addstr(bottom_y, left, "║", c_yellow)
        self.stdscr.addstr(bottom_y, left + 2, " [↑/↓ / 1-8] Выбор   [Enter] Применить   [Esc] Отмена ", c_cyan)
        self.stdscr.addstr(bottom_y, left + box_w - 1, "║", c_yellow)

        footer = "╚" + "═" * (box_w - 2) + "╝"
        self.stdscr.addstr(bottom_y + 1, left, footer, c_yellow | curses.A_BOLD)
