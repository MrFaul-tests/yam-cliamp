"""
Headless browser player for Yandex Music.
Runs Chromium in hidden mode (--headless=new) with audio routed to PipeWire/PulseAudio.
Controls playback, track metadata, and 'Моя волна' via Chrome DevTools Protocol.
"""

import os
import time
import json
import asyncio
import subprocess
import urllib.request
import websockets
from yam_cliamp.auth import PROFILE_DIR, find_browser_executable


class BrowserPlayer:
    def __init__(self, port: int = 9229):
        self.port = port
        self.proc: subprocess.Popen | None = None
        self.ws = None
        self.msg_id = 0
        self.running = False
        self._current_state = {
            "title": "Yandex Music",
            "artist": "Загрузка...",
            "album": "",
            "isPlaying": False,
            "position": 0,
            "duration": 0,
            "volume": 80,
        }

    def start(self):
        """Spawns Chromium in hidden headless mode."""
        if self.proc and self.proc.poll() is None:
            return

        browser_bin = find_browser_executable()
        os.makedirs(PROFILE_DIR, exist_ok=True)

        cmd = [
            browser_bin,
            "--headless=new",
            f"--user-data-dir={PROFILE_DIR}",
            f"--remote-debugging-port={self.port}",
            "--autoplay-policy=no-user-gesture-required",
            "--disable-background-timer-throttling",
            "--disable-backgrounding-occluded-windows",
            "--disable-renderer-backgrounding",
            "--no-first-run",
            "--no-default-browser-check",
            "https://music.yandex.ru/home",
        ]

        self.proc = subprocess.Popen(
            cmd,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        self.running = True

    async def connect(self, timeout: float = 15.0) -> bool:
        """Connects to the page tab via WebSocket CDP."""
        start_t = time.time()
        page_ws_url = None

        while time.time() - start_t < timeout:
            try:
                with urllib.request.urlopen(f"http://127.0.0.1:{self.port}/json/list", timeout=1) as resp:
                    tabs = json.loads(resp.read().decode())
                    page_tab = next((t for t in tabs if t.get("type") == "page"), None)
                    if page_tab and "webSocketDebuggerUrl" in page_tab:
                        page_ws_url = page_tab["webSocketDebuggerUrl"]
                        break
            except Exception:
                pass
            await asyncio.sleep(0.3)

        if not page_ws_url:
            return False

        try:
            self.ws = await websockets.connect(page_ws_url, max_size=2**24)
            # Give page a moment to load SPA scripts
            await asyncio.sleep(2.0)
            return True
        except Exception:
            return False

    async def _evaluate(self, js: str) -> dict | None:
        if not self.ws:
            return None
        self.msg_id += 1
        payload = {
            "id": self.msg_id,
            "method": "Runtime.evaluate",
            "params": {
                "expression": js,
                "returnByValue": True,
            },
        }
        try:
            await self.ws.send(json.dumps(payload))
            res = await self.ws.recv()
            data = json.loads(res)
            return data.get("result", {}).get("result", {}).get("value")
        except Exception:
            return None

    async def update_state(self) -> dict:
        """Polls current track metadata and playback position."""
        js = """(() => {
            let title = '';
            let artist = '';
            let album = '';
            let isPlaying = false;
            let position = 0;
            let duration = 0;

            if (navigator.mediaSession && navigator.mediaSession.metadata) {
                title = navigator.mediaSession.metadata.title || '';
                artist = navigator.mediaSession.metadata.artist || '';
                album = navigator.mediaSession.metadata.album || '';
                isPlaying = navigator.mediaSession.playbackState === 'playing';
            }
            if (navigator.mediaSession && navigator.mediaSession.positionState) {
                position = navigator.mediaSession.positionState.position || 0;
                duration = navigator.mediaSession.positionState.duration || 0;
            }

            const audio = document.querySelector('audio');
            if (audio) {
                if (!isPlaying) isPlaying = !audio.paused;
                if (!position || isNaN(position)) position = audio.currentTime || 0;
                if (!duration || isNaN(duration)) duration = audio.duration || 0;
            }

            // Fallback from DOM if mediaSession not yet ready
            if (!title) {
                const trackEl = document.querySelector('[data-test-id=\"track-name\"], [class*=\"Track_title\"]');
                if (trackEl) title = trackEl.innerText.trim();
                const artistEl = document.querySelector('[data-test-id=\"artist-name\"], [class*=\"Track_artist\"]');
                if (artistEl) artist = artistEl.innerText.trim();
            }

            return {
                title: title || 'Моя волна',
                artist: artist || 'Яндекс Музыка',
                album: album || '',
                isPlaying: !!isPlaying,
                position: Math.floor(position || 0),
                duration: Math.floor(duration || 0)
            };
        })()"""
        val = await self._evaluate(js)
        if isinstance(val, dict):
            self._current_state.update(val)
        return self._current_state

    async def toggle_play(self):
        js = """(() => {
            const audio = document.querySelector('audio');
            if (audio) {
                if (audio.paused) audio.play(); else audio.pause();
                return;
            }
            const playBtn = document.querySelector('button[aria-label*=\"Воспроизвести\"], button[aria-label*=\"Пауза\"], [data-test-id=\"play-button\"]');
            if (playBtn) playBtn.click();
        })()"""
        await self._evaluate(js)

    async def next_track(self):
        js = """(() => {
            const nextBtn = document.querySelector('button[aria-label*=\"Следующий\"], button[aria-label*=\"Дальше\"], [data-test-id=\"next-button\"]');
            if (nextBtn) nextBtn.click();
        })()"""
        await self._evaluate(js)

    async def prev_track(self):
        js = """(() => {
            const prevBtn = document.querySelector('button[aria-label*=\"Предыдущий\"], button[aria-label*=\"Назад\"], [data-test-id=\"prev-button\"]');
            if (prevBtn) prevBtn.click();
        })()"""
        await self._evaluate(js)

    async def start_wave(self):
        """Starts 'Моя волна' (My Wave)."""
        js = """(() => {
            const waveBtn = Array.from(document.querySelectorAll('button, [role=\"button\"]')).find(el => {
                const t = (el.innerText || '') + (el.getAttribute('aria-label') || '');
                return t.includes('волн') || t.includes('Волна') || t.includes('Wave');
            });
            if (waveBtn) {
                waveBtn.click();
                return true;
            }
            return false;
        })()"""
        await self._evaluate(js)

    async def set_volume(self, vol_percent: int):
        vol_float = max(0.0, min(1.0, vol_percent / 100.0))
        js = f"""(() => {{
            const audio = document.querySelector('audio');
            if (audio) {{
                audio.volume = {vol_float};
            }}
        }})()"""
        await self._evaluate(js)
        self._current_state["volume"] = vol_percent

    async def seek(self, delta_seconds: int):
        js = f"""(() => {{
            const audio = document.querySelector('audio');
            if (audio) {{
                audio.currentTime = Math.max(0, audio.currentTime + {delta_seconds});
            }}
        }})()"""
        await self._evaluate(js)

    def stop(self):
        self.running = False
        if self.ws:
            try:
                asyncio.create_task(self.ws.close())
            except Exception:
                pass
            self.ws = None
        if self.proc:
            if self.proc.poll() is None:
                self.proc.terminate()
                try:
                    self.proc.wait(timeout=2)
                except subprocess.TimeoutExpired:
                    self.proc.kill()
            self.proc = None
