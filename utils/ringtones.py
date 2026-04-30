"""
utils/ringtones.py — Default ringtone generation and alarm ringtone helpers.
"""

import math
import os
import struct
import wave

from kivy.utils import platform

BASE_DIR = os.path.join(os.path.dirname(__file__), "..", "user_data", "ringtones")
SYSTEM_ALARM_ID = "system_alarm_tone"

DEFAULT_RINGTONES = [
    {
        "id": "classic_bell",
        "label": "Classic Bell",
        "segments": [(880, 0.16), (0, 0.08), (1046, 0.16), (0, 0.30)],
    },
    {
        "id": "rapid_alert",
        "label": "Rapid Alert",
        "segments": [(988, 0.10), (0, 0.06), (988, 0.10), (0, 0.06), (1318, 0.14), (0, 0.24)],
    },
    {
        "id": "soft_chime",
        "label": "Soft Chime",
        "segments": [(659, 0.20), (784, 0.20), (988, 0.28), (0, 0.32)],
    },
]

PIECE_SOUND_SPECS = {
    "move.wav": {
        "segments": [
            (740, 0.012, 0.24),
            (930, 0.016, 0.18),
        ],
        "silence": 0.02,
    },
    "capture.wav": {
        "segments": [
            (520, 0.014, 0.28),
            (310, 0.020, 0.26),
            (180, 0.022, 0.22),
        ],
        "silence": 0.025,
    },
}


def ensure_default_ringtones():
    os.makedirs(BASE_DIR, exist_ok=True)
    for ringtone in DEFAULT_RINGTONES:
        path = _default_path(ringtone["id"])
        if not os.path.exists(path):
            _write_wave(path, ringtone["segments"])
    ensure_piece_sounds(force=False)


def ringtone_choices():
    ensure_default_ringtones()
    choices = [
        {
            "id": SYSTEM_ALARM_ID,
            "label": "Device Alarm Tone",
            "path": SYSTEM_ALARM_ID,
        },
    ]
    choices.extend([
        {
            "id": ringtone["id"],
            "label": ringtone["label"],
            "path": _default_path(ringtone["id"]),
        }
        for ringtone in DEFAULT_RINGTONES
    ])
    return choices


def default_ringtone_id() -> str:
    return SYSTEM_ALARM_ID


def resolve_alarm_ringtone(alarm: dict) -> tuple[str, str]:
    ensure_default_ringtones()
    local_path = alarm.get("ringtone_path") or ""
    if local_path and os.path.exists(local_path):
        return os.path.abspath(local_path), os.path.basename(local_path)

    selected_id = alarm.get("ringtone_id") or default_ringtone_id()
    if selected_id == SYSTEM_ALARM_ID:
        if platform == "android":
            return SYSTEM_ALARM_ID, "Device Alarm Tone"
        fallback = ringtone_choices()[1]
        return os.path.abspath(fallback["path"]), "Device Alarm Tone"

    for ringtone in ringtone_choices():
        if ringtone["id"] == selected_id:
            return os.path.abspath(ringtone["path"]), ringtone["label"]

    fallback = ringtone_choices()[0]
    return os.path.abspath(fallback["path"]), fallback["label"]

    
def _default_path(ringtone_id: str) -> str:
    return os.path.join(BASE_DIR, f"{ringtone_id}.wav")


def ensure_piece_sounds(force: bool = True):
    os.makedirs(BASE_DIR, exist_ok=True)
    for filename, spec in PIECE_SOUND_SPECS.items():
        path = os.path.join(BASE_DIR, filename)
        if force or not os.path.exists(path):
            _write_piece_wave(
                path,
                spec["segments"],
                silence=spec.get("silence", 0.02),
            )


def _write_wave(path: str, segments: list[tuple[int, float]], sample_rate: int = 22050):
    frames = []
    amplitude = 0.35
    for frequency, duration in segments:
        total = max(1, int(sample_rate * duration))
        for i in range(total):
            if frequency <= 0:
                sample = 0.0
            else:
                t = i / sample_rate
                envelope = 1.0 - min(1.0, i / total) * 0.15
                sample = math.sin(2 * math.pi * frequency * t) * amplitude * envelope
            frames.append(struct.pack("<h", int(sample * 32767)))

    with wave.open(path, "wb") as wav_file:
        wav_file.setnchannels(1)
        wav_file.setsampwidth(2)
        wav_file.setframerate(sample_rate)
        wav_file.writeframes(b"".join(frames))


def _write_piece_wave(
    path: str,
    segments: list[tuple[int, float, float]],
    sample_rate: int = 22050,
    silence: float = 0.02,
):
    frames = []
    for frequency, duration, amplitude in segments:
        total = max(1, int(sample_rate * duration))
        for i in range(total):
            t = i / sample_rate
            envelope = 1.0 - min(1.0, i / total) * 0.45
            sample = math.sin(2 * math.pi * frequency * t) * amplitude * envelope
            sample += math.sin(2 * math.pi * (frequency * 0.5) * t) * amplitude * 0.12
            frames.append(struct.pack("<h", int(max(-1.0, min(1.0, sample)) * 32767)))

        rest = max(0, int(sample_rate * silence))
        if rest:
            frames.extend([struct.pack("<h", 0)] * rest)

    with wave.open(path, "wb") as wav_file:
        wav_file.setnchannels(1)
        wav_file.setsampwidth(2)
        wav_file.setframerate(sample_rate)
        wav_file.writeframes(b"".join(frames))
