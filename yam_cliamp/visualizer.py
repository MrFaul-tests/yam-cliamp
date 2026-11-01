"""
Visualizer engine for the Winamp / cliamp retro TUI.
Implements the classic Winamp spectrum analyzer with floating peak caps,
apex hold, gravity fall physics, and oscilloscope mode.
"""

import math
import random
import time


class WinampVisualizer:
    def __init__(self, bands: int = 24, max_height: int = 6):
        self.bands = bands
        self.max_height = max_height
        self.bar_heights = [0.0] * bands
        self.peak_positions = [0.0] * bands
        self.peak_hold = [0] * bands
        self.peak_velocities = [0.0] * bands
        self.mode = "spectrum"  # 'spectrum' or 'scope'
        self.last_update = time.time()
        self.phase = 0.0

    def toggle_mode(self):
        self.mode = "scope" if self.mode == "spectrum" else "spectrum"

    def update(self, is_playing: bool, position: float = 0.0):
        now = time.time()
        dt = min(0.1, now - self.last_update)
        self.last_update = now
        self.phase += dt * 4.0

        if not is_playing:
            # Decay to zero smoothly
            for i in range(self.bands):
                self.bar_heights[i] = max(0.0, self.bar_heights[i] - 0.25)
                if self.peak_positions[i] > self.bar_heights[i]:
                    self.peak_positions[i] = max(0.0, self.peak_positions[i] - 0.3)
            return

        # Generate responsive pseudo-FFT frequency spectrum based on time and audio bands
        # Bass in lower bands (0..4), mids (5..14), treble (15..bands-1)
        beat1 = math.sin(self.phase * 3.1)
        beat2 = math.cos(self.phase * 1.7 + 0.5)
        snare = math.sin(self.phase * 6.28)

        for i in range(self.bands):
            # Frequency envelope (bass tends higher, treble sparkles)
            band_ratio = i / float(self.bands)
            if band_ratio < 0.25:  # Bass
                raw = 0.5 + 0.45 * math.sin(self.phase * 2.0 + i * 0.4) + 0.3 * beat1
            elif band_ratio < 0.65:  # Mids
                raw = 0.4 + 0.35 * math.cos(self.phase * 3.5 + i * 0.8) + 0.25 * beat2
            else:  # Highs
                raw = 0.3 + 0.35 * math.sin(self.phase * 5.0 + i * 1.2) + 0.35 * (snare if snare > 0.3 else 0)

            # Add gentle randomness for organic music flutter
            jitter = random.uniform(-0.08, 0.08)
            target = max(0.0, min(float(self.max_height), (raw + jitter) * self.max_height))

            # Rise fast, fall moderately
            if target > self.bar_heights[i]:
                self.bar_heights[i] += (target - self.bar_heights[i]) * 0.65
            else:
                self.bar_heights[i] = max(0.0, self.bar_heights[i] - 0.35)

            # Floating peak cap physics
            curr_h = self.bar_heights[i]
            if curr_h >= self.peak_positions[i]:
                self.peak_positions[i] = curr_h
                self.peak_hold[i] = 4  # Hold at apex for 4 ticks
                self.peak_velocities[i] = 0.0
            else:
                if self.peak_hold[i] > 0:
                    self.peak_hold[i] -= 1
                else:
                    self.peak_velocities[i] -= 0.18  # Gravity acceleration
                    self.peak_positions[i] += self.peak_velocities[i]
                    if self.peak_positions[i] < curr_h:
                        self.peak_positions[i] = curr_h
                        self.peak_velocities[i] = 0.0

    def render_rows(self) -> list[str]:
        """
        Renders the visualizer as a list of strings (one per row, from top to bottom).
        Uses ANSI colors for Winamp retro look:
        Green at bottom, yellow in mid, red at top.
        """
        if self.mode == "scope":
            return self._render_oscilloscope()
        return self._render_spectrum()

    def _render_spectrum(self) -> list[str]:
        rows = []
        H = self.max_height
        # Block glyphs for sub-cell rendering
        blocks = [" ", " ", "▂", "▃", "▄", "▅", "▆", "▇", "█"]
        peak_glyph = "⎺"

        for row in range(H - 1, -1, -1):
            row_chars = []
            # Color based on height: top = red, mid = yellow, bottom = green
            row_ratio = row / float(max(1, H - 1))
            if row_ratio > 0.66:
                color_code = "\033[38;5;196m"  # Red
            elif row_ratio > 0.33:
                color_code = "\033[38;5;220m"  # Yellow / Amber
            else:
                color_code = "\033[38;5;46m"   # Winamp Neon Green

            for i in range(self.bands):
                bar_val = self.bar_heights[i]
                peak_val = self.peak_positions[i]

                # Check if peak is at this row
                has_peak = (int(math.floor(peak_val)) == row) and (peak_val > 0.1)

                if bar_val >= row + 1:
                    cell = "█"
                elif bar_val > row:
                    fraction = bar_val - row
                    idx = int(fraction * 8)
                    cell = blocks[max(1, min(8, idx))]
                elif has_peak:
                    cell = peak_glyph
                else:
                    cell = " "

                row_chars.append(color_code + cell + "\033[0m")
            rows.append("".join(row_chars))
        return rows

    def _render_oscilloscope(self) -> list[str]:
        """Classic Winamp green oscilloscope wave line."""
        rows = []
        H = self.max_height
        grid = [[" " for _ in range(self.bands)] for _ in range(H)]
        green = "\033[38;5;46m"
        reset = "\033[0m"

        mid = (H - 1) / 2.0
        for i in range(self.bands):
            wave = math.sin(self.phase * 3.0 + i * 0.45) * 0.8 + math.sin(self.phase * 7.0 + i * 0.9) * 0.2
            y = int(round(mid + wave * mid * 0.85))
            y = max(0, min(H - 1, y))
            grid[y][i] = green + "━" + reset

        for row in range(H - 1, -1, -1):
            rows.append("".join(grid[row]))
        return rows
