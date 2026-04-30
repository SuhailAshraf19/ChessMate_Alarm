"""
utils/sound_preview.py — Safe one-shot audio preview helpers.
"""

import os
import shutil
import subprocess
import wave

from kivy.clock import Clock
from kivy.core.audio import SoundLoader
from kivy.utils import platform

if platform == "android":
    from jnius import autoclass

    MediaPlayer = autoclass("android.media.MediaPlayer")
    AudioManager = autoclass("android.media.AudioManager")
    AudioAttributes = autoclass("android.media.AudioAttributes")
    Build = autoclass("android.os.Build")
else:
    MediaPlayer = None
    AudioManager = None
    AudioAttributes = None
    Build = None


class SoundPreviewManager:
    def __init__(self):
        self._sound = None
        self._effect_sound = None
        self._stop_ev = None
        self._proc = None
        self._loop_ev = None
        self._loop_alarm = None
        self._loop_volume = 80
        self._loop_max_duration = 2.5
        self._loop_interval = 2.5
        self._loop_path = None
        self._android_player = None

    def stop(self):
        self._stop_effect()
        self._stop_android_player()
        if self._loop_ev:
            Clock.unschedule(self._loop_ev)
            self._loop_ev = None
        self._loop_alarm = None
        self._loop_path = None
        if self._stop_ev:
            Clock.unschedule(self._stop_ev)
            self._stop_ev = None
        if self._proc:
            try:
                if self._proc.poll() is None:
                    self._proc.terminate()
            except Exception:
                pass
            self._proc = None
        if self._sound:
            try:
                self._sound.stop()
            except Exception:
                pass
            self._sound = None

    def _stop_android_player(self):
        if self._android_player:
            try:
                self._android_player.stop()
            except Exception:
                pass
            try:
                self._android_player.release()
            except Exception:
                pass
            self._android_player = None

    def _stop_effect(self):
        if self._effect_sound:
            try:
                self._effect_sound.stop()
            except Exception:
                pass
            self._effect_sound = None

    def play_path(self, path: str, volume: int = 80, max_duration: float = 2.5) -> bool:
        self.stop()
        return self._play_path_once(path, volume=volume, max_duration=max_duration)

    def _play_path_once(self, path: str, volume: int = 80, max_duration: float = 2.5) -> bool:
        if not path or not os.path.exists(path):
            return False
        if self._play_with_system_player(path, max_duration):
            return True
        return self._play_with_kivy(path, volume, max_duration)

    def _play_with_system_player(self, path: str, max_duration: float) -> bool:
        if platform in ("android", "ios"):
            return False
        if os.path.splitext(path)[1].lower() != ".wav":
            return False
        aplay = shutil.which("aplay")
        if not aplay:
            return False
        try:
            self._proc = subprocess.Popen(
                [aplay, "-q", path],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            self._stop_ev = Clock.schedule_once(lambda *_: self.stop(), max(0.5, max_duration))
            return True
        except Exception:
            self._proc = None
            return False

    def _play_with_kivy(self, path: str, volume: int, max_duration: float) -> bool:
        try:
            sound = SoundLoader.load(path)
            if not sound:
                return False
            sound.volume = max(0.0, min(1.0, volume / 100.0))
            sound.play()
            self._sound = sound

            length = getattr(sound, "length", 0) or 0
            stop_after = max_duration
            if length > 0:
                stop_after = min(max_duration, max(0.5, length + 0.1))
            self._stop_ev = Clock.schedule_once(lambda *_: self.stop(), stop_after)
            return True
        except Exception:
            self.stop()
            return False

    def play_alarm_preview(self, alarm: dict, volume: int = 80, max_duration: float = 2.5) -> bool:
        return False

    def start_alarm_loop(
        self,
        alarm: dict,
        volume: int = 80,
        max_duration: float = 2.2,
        interval: float | None = None,
    ) -> bool:
        return False

    def _loop_once(self):
        if not self._loop_alarm:
            return
        if self._stop_ev:
            Clock.unschedule(self._stop_ev)
            self._stop_ev = None
        if self._proc:
            try:
                if self._proc.poll() is None:
                    self._proc.terminate()
            except Exception:
                pass
            self._proc = None
        if self._sound:
            try:
                self._sound.stop()
            except Exception:
                pass
            self._sound = None

        path = self._loop_path
        if not path:
            path, _ = resolve_alarm_ringtone(self._loop_alarm)
            self._loop_path = path
        self._play_path_once(
            path,
            volume=self._loop_volume,
            max_duration=self._loop_max_duration,
        )

    def _estimate_duration(self, path: str) -> float:
        if not path or not os.path.exists(path):
            return 0.0
        try:
            with wave.open(path, "rb") as wav_file:
                frames = wav_file.getnframes()
                rate = wav_file.getframerate()
                if rate > 0:
                    return max(0.1, frames / float(rate))
        except Exception:
            pass

        try:
            sound = SoundLoader.load(path)
            if sound:
                length = getattr(sound, "length", 0) or 0
                try:
                    sound.unload()
                except Exception:
                    pass
                if length > 0:
                    return max(0.1, float(length))
        except Exception:
            pass
        return 0.0

    def play_effect(self, filename: str, volume: int = 80, max_duration: float = 1.2) -> bool:
        path = os.path.join(os.path.dirname(__file__), "..", "user_data", "ringtones", filename)
        path = os.path.abspath(path)
        if not path or not os.path.exists(path):
            return False
        self._stop_effect()
        try:
            sound = SoundLoader.load(path)
            if not sound:
                return False
            sound.volume = max(0.0, min(1.0, volume / 100.0))
            sound.play()
            self._effect_sound = sound

            length = getattr(sound, "length", 0) or 0
            stop_after = max_duration
            if length > 0:
                stop_after = min(max_duration, max(0.3, length + 0.05))
            Clock.schedule_once(lambda *_: self._stop_effect(), stop_after)
            return True
        except Exception:
            self._stop_effect()
            return False
