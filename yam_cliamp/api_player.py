"""
Native API player for Yandex Music using the official yandex-music API library
and an mpv subprocess controlled via JSON IPC.
Handles 'Моя волна' (with dynamic mood/character settings), Liked Tracks, Playlists, and Search.
"""

import os
import time
import json
import random
import socket
import subprocess
from dataclasses import dataclass
from yandex_music import Client


@dataclass
class TrackItem:
    id: str
    title: str
    artist: str
    album: str
    duration_ms: int
    direct_url: str | None = None

    @property
    def duration_str(self) -> str:
        sec = self.duration_ms // 1000
        return f"{sec // 60:02d}:{sec % 60:02d}"


class ApiPlayer:
    def __init__(self, token: str):
        self.token = token
        self.client: Client | None = None
        self.mpv_proc: subprocess.Popen | None = None
        self.sock_path = f"/tmp/yam_cliamp_mpv_{os.getpid()}.sock"
        self.playlist: list[TrackItem] = []
        self.current_index = 0
        self.is_playing = False
        self.is_paused = False
        self.volume = 80
        self.shuffle = False
        self.source_name = "Моя волна"
        self._current_wave_session = None

    def init_api(self):
        """Initializes Yandex Music API client."""
        self.client = Client(self.token).init()

    def start_mpv(self):
        """Starts background mpv process with IPC socket."""
        if os.path.exists(self.sock_path):
            try:
                os.remove(self.sock_path)
            except OSError:
                pass

        cmd = [
            "mpv",
            "--idle=yes",
            "--no-video",
            f"--input-ipc-server={self.sock_path}",
            f"--volume={self.volume}",
        ]
        self.mpv_proc = subprocess.Popen(
            cmd,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        for _ in range(30):
            if os.path.exists(self.sock_path):
                break
            time.sleep(0.05)

    def _send_mpv_cmd(self, cmd: list) -> dict | None:
        if not os.path.exists(self.sock_path):
            return None
        try:
            with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as s:
                s.settimeout(0.4)
                s.connect(self.sock_path)
                msg = json.dumps({"command": cmd}).encode() + b"\n"
                s.sendall(msg)
                res = s.recv(4096)
                if res:
                    return json.loads(res.decode())
        except Exception:
            return None
        return None

    def load_wave(self, mood: str = "all", diversity: str = "default", label: str = "Моя волна") -> list[TrackItem]:
        """Loads tracks for 'Моя волна' with optional mood and character seeds."""
        if not self.client:
            self.init_api()

        self.source_name = label
        seeds = ["user:onyourwave"]
        if mood and mood != "all":
            seeds.append(f"settingMoodEnergy:{mood}")
        if diversity and diversity != "default":
            seeds.append(f"settingDiversity:{diversity}")

        try:
            session = self.client.rotor_session_new(seeds=seeds)
            self._current_wave_session = session
            tracks = []
            for item in session.sequence:
                t = item.track
                artists = ", ".join([a.name for a in t.artists]) if t.artists else "Разные артисты"
                album = t.albums[0].title if t.albums else ""
                tracks.append(
                    TrackItem(
                        id=str(t.id),
                        title=t.title,
                        artist=artists,
                        album=album,
                        duration_ms=t.duration_ms or 180000,
                    )
                )
            self.playlist = tracks
            self.current_index = 0
            return self.playlist
        except Exception:
            # Fallback to simple station tracks
            try:
                st = self.client.rotor_station_tracks("user:onyourwave")
                tracks = []
                for item in st.sequence:
                    t = item.track
                    artists = ", ".join([a.name for a in t.artists]) if t.artists else "Разные артисты"
                    album = t.albums[0].title if t.albums else ""
                    tracks.append(
                        TrackItem(
                            id=str(t.id),
                            title=t.title,
                            artist=artists,
                            album=album,
                            duration_ms=t.duration_ms or 180000,
                        )
                    )
                self.playlist = tracks
                self.current_index = 0
                return self.playlist
            except Exception:
                return self.load_likes()

    def load_likes(self) -> list[TrackItem]:
        """Loads user's favorite / liked tracks."""
        if not self.client:
            self.init_api()
        self.source_name = "Любимые треки"
        try:
            liked = self.client.users_likes_tracks()
            tracks_data = liked.tracks[:50]
            tracks_full = self.client.tracks([t.track_id for t in tracks_data])
            tracks = []
            for t in tracks_full:
                artists = ", ".join([a.name for a in t.artists]) if t.artists else "Разные артисты"
                album = t.albums[0].title if t.albums else ""
                tracks.append(
                    TrackItem(
                        id=str(t.id),
                        title=t.title,
                        artist=artists,
                        album=album,
                        duration_ms=t.duration_ms or 180000,
                    )
                )
            self.playlist = tracks
            self.current_index = 0
            return self.playlist
        except Exception:
            return []

    def search(self, query: str) -> list[TrackItem]:
        """Searches Yandex Music catalogue."""
        if not self.client:
            self.init_api()
        self.source_name = f"Поиск: {query}"
        try:
            res = self.client.search(query, type_="track")
            tracks = []
            if res.tracks and res.tracks.results:
                for t in res.tracks.results[:30]:
                    artists = ", ".join([a.name for a in t.artists]) if t.artists else "Разные артисты"
                    album = t.albums[0].title if t.albums else ""
                    tracks.append(
                        TrackItem(
                            id=str(t.id),
                            title=t.title,
                            artist=artists,
                            album=album,
                            duration_ms=t.duration_ms or 180000,
                        )
                    )
            self.playlist = tracks
            self.current_index = 0
            return self.playlist
        except Exception:
            return []

    def _resolve_stream_url(self, track_id: str) -> str | None:
        try:
            t = self.client.tracks(track_id)[0]
            info = t.get_specific_download_info(codec="mp3")
            return info.get_direct_link()
        except Exception:
            try:
                infos = t.get_download_info()
                best = max(infos, key=lambda i: i.bitrate_in_kbps or 0)
                return best.get_direct_link()
            except Exception:
                return None

    def play_index(self, idx: int):
        if not self.playlist or idx < 0 or idx >= len(self.playlist):
            return

        self.current_index = idx
        track = self.playlist[idx]

        if not track.direct_url:
            track.direct_url = self._resolve_stream_url(track.id)

        if not track.direct_url:
            return

        if not self.mpv_proc or self.mpv_proc.poll() is not None:
            self.start_mpv()

        self._send_mpv_cmd(["loadfile", track.direct_url, "replace"])
        self._send_mpv_cmd(["set_property", "pause", False])
        self.is_playing = True
        self.is_paused = False

    def toggle_play(self):
        if not self.is_playing:
            self.play_index(self.current_index)
            return

        self.is_paused = not self.is_paused
        self._send_mpv_cmd(["set_property", "pause", self.is_paused])

    def stop(self):
        self._send_mpv_cmd(["stop"])
        self.is_playing = False
        self.is_paused = False

    def next_track(self):
        if not self.playlist:
            return
        if self.shuffle and len(self.playlist) > 1:
            next_idx = self.current_index
            while next_idx == self.current_index:
                next_idx = random.randint(0, len(self.playlist) - 1)
        else:
            next_idx = (self.current_index + 1) % len(self.playlist)
        self.play_index(next_idx)

    def prev_track(self):
        if not self.playlist:
            return
        if self.shuffle and len(self.playlist) > 1:
            prev_idx = self.current_index
            while prev_idx == self.current_index:
                prev_idx = random.randint(0, len(self.playlist) - 1)
        else:
            prev_idx = (self.current_index - 1) % len(self.playlist)
        self.play_index(prev_idx)

    def toggle_shuffle(self) -> bool:
        self.shuffle = not self.shuffle
        return self.shuffle

    def set_volume(self, delta_or_val: int, is_delta: bool = False):
        if is_delta:
            self.volume = max(0, min(100, self.volume + delta_or_val))
        else:
            self.volume = max(0, min(100, delta_or_val))
        self._send_mpv_cmd(["set_property", "volume", self.volume])

    def seek(self, delta_seconds: int):
        self._send_mpv_cmd(["seek", delta_seconds, "relative"])

    def get_playback_state(self) -> dict:
        """Returns position, duration, and playing status from mpv."""
        track = self.playlist[self.current_index] if self.playlist else None
        title = track.title if track else "Нет трека"
        artist = track.artist if track else "Яндекс Музыка"
        album = track.album if track else ""

        pos = 0
        dur = (track.duration_ms // 1000) if track else 0

        pos_resp = self._send_mpv_cmd(["get_property", "time-pos"])
        if pos_resp and "data" in pos_resp and pos_resp["data"] is not None:
            pos = int(pos_resp["data"])

        dur_resp = self._send_mpv_cmd(["get_property", "duration"])
        if dur_resp and "data" in dur_resp and dur_resp["data"] is not None:
            dur = int(dur_resp["data"])

        # Auto-advance track if reached the end
        if self.is_playing and not self.is_paused and dur > 0 and pos >= dur - 1:
            self.next_track()

        return {
            "title": title,
            "artist": artist,
            "album": album,
            "isPlaying": self.is_playing and not self.is_paused,
            "position": pos,
            "duration": dur,
            "volume": self.volume,
        }

    def close(self):
        if self.mpv_proc:
            self._send_mpv_cmd(["quit"])
            try:
                self.mpv_proc.terminate()
                self.mpv_proc.wait(timeout=1)
            except Exception:
                pass
            self.mpv_proc = None
        if os.path.exists(self.sock_path):
            try:
                os.remove(self.sock_path)
            except OSError:
                pass
