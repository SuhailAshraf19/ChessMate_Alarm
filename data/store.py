"""
data/store.py — Persistent storage for alarms, settings and puzzle rating.
"""

import json
import os
from datetime import datetime
from kivy.logger import Logger
from utils.ringtones import default_ringtone_id, ensure_default_ringtones, ensure_piece_sounds
from utils.android_alarm import reschedule_alarms, schedule_alarm, cancel_alarm

DATA_DIR      = os.path.join(os.path.dirname(__file__), "..", "user_data")
ALARMS_FILE   = os.path.join(DATA_DIR, "alarms.json")
SETTINGS_FILE = os.path.join(DATA_DIR, "settings.json")
SCORE_FILE    = os.path.join(DATA_DIR, "score.json")

SCORE_START       = 1000
SCORE_FLOOR       = 400
RATING_K_FACTOR   = 24


def _ensure_dir():
    os.makedirs(DATA_DIR, exist_ok=True)


class AlarmStore:

    DEFAULT_SETTINGS = {
        "puzzle_count":      3,
        "current_puzzle_rating": 1000,
        "snooze_enabled":    False,
        "snooze_minutes":    5,
        "vibrate":           True,
        "volume":            80,
        "active_alarm_id":   None,
        "active_alarm_label": "",
        "active_alarm_started_at": None,
    }

    def __init__(self):
        _ensure_dir()
        ensure_default_ringtones()
        ensure_piece_sounds(force=True)
        self._alarms   = self._load_json(ALARMS_FILE, default=[])
        self._settings = {
            **self.DEFAULT_SETTINGS,
            **self._load_json(SETTINGS_FILE, default={}),
        }
        sd = self._load_json(SCORE_FILE, default={})
        sd.setdefault("score",         SCORE_START)
        sd.setdefault("total_solved",  0)
        sd.setdefault("total_skipped", 0)
        sd.setdefault("total_wrong",   0)
        sd.setdefault("total_hints",   0)
        sd.pop("history", None)
        self._score_data = sd
        reschedule_alarms(self._alarms)

    # ── alarms ────────────────────────────────────────────────────────────

    def get_alarms(self):
        return list(self._alarms)

    def get_active_alarm_id(self):
        value = self._settings.get("active_alarm_id")
        try:
            return int(value) if value is not None else None
        except Exception:
            return None

    def is_alarm_active(self, alarm_id: int) -> bool:
        active_id = self.get_active_alarm_id()
        try:
            return active_id is not None and int(active_id) == int(alarm_id)
        except Exception:
            return False

    def get_active_alarm(self):
        active_id = self.get_active_alarm_id()
        if active_id is None:
            return None
        for alarm in self._alarms:
            try:
                if int(alarm.get("id", -1)) == active_id:
                    return dict(alarm)
            except Exception:
                continue
        return {
            "id": active_id,
            "label": self._settings.get("active_alarm_label", "Alarm"),
            "hour": 0,
            "minute": 0,
            "days": [],
            "enabled": True,
        }

    def set_active_alarm(self, alarm: dict):
        if not alarm:
            return
        try:
            alarm_id = int(alarm.get("id", 0))
        except Exception:
            return
        self._settings["active_alarm_id"] = alarm_id
        self._settings["active_alarm_label"] = alarm.get("label", "Alarm")
        self._settings["active_alarm_started_at"] = datetime.now().isoformat()
        self._save_settings()
        Logger.info(f'AlarmStore: active alarm set to {alarm_id}')

    def clear_active_alarm(self):
        self._settings["active_alarm_id"] = None
        self._settings["active_alarm_label"] = ""
        self._settings["active_alarm_started_at"] = None
        self._save_settings()
        Logger.info("AlarmStore: active alarm cleared")

    def add_alarm(self, alarm: dict):
        alarm.setdefault("id",      self._next_id())
        alarm.setdefault("enabled", True)
        alarm.setdefault("days",    [])
        alarm.setdefault("label",   "Alarm")
        alarm.setdefault("ringtone_id", default_ringtone_id())
        alarm.setdefault("ringtone_path", "")
        # Snooze metadata
        alarm.setdefault("snoozed_until", None)
        alarm.setdefault("snooze_count", 0)
        alarm.setdefault("last_triggered_key", None)
        self._alarms.append(alarm)
        self._save_alarms()
        if not schedule_alarm(alarm):
            Logger.warning(f'AlarmStore: failed to schedule alarm {alarm.get("id")}')
        else:
            Logger.info(f'AlarmStore: scheduled alarm {alarm.get("id")} after add')
        return alarm

    def update_alarm(self, alarm_id: int, updates: dict):
        for a in self._alarms:
            if a["id"] == alarm_id:
                a.update(updates)
                if a.get("enabled", True):
                    if not schedule_alarm(a):
                        Logger.warning(f'AlarmStore: failed to reschedule alarm {alarm_id}')
                    else:
                        Logger.info(f'AlarmStore: rescheduled alarm {alarm_id}')
                else:
                    cancel_alarm(alarm_id)
                break
        self._save_alarms()

    def delete_alarm(self, alarm_id: int):
        self._alarms = [a for a in self._alarms if a["id"] != alarm_id]
        self._save_alarms()
        cancel_alarm(alarm_id)
        if self.get_active_alarm_id() == alarm_id:
            self.clear_active_alarm()

    def toggle_alarm(self, alarm_id: int):
        if self.is_alarm_active(alarm_id):
            Logger.warning(f'AlarmStore: refusing to toggle active alarm {alarm_id}')
            return
        for a in self._alarms:
            if a["id"] == alarm_id:
                a["enabled"] = not a["enabled"]
                if a["enabled"]:
                    if not schedule_alarm(a):
                        Logger.warning(f'AlarmStore: failed to re-enable alarm {alarm_id}')
                    else:
                        Logger.info(f'AlarmStore: re-enabled alarm {alarm_id} and scheduled it')
                else:
                    cancel_alarm(alarm_id)
                break
        self._save_alarms()

    # ── settings ──────────────────────────────────────────────────────────

    def get_settings(self):
        return dict(self._settings)

    def set_setting(self, key: str, value):
        self._settings[key] = value
        self._save_settings()

    def get_setting(self, key: str, default=None):
        return self._settings.get(key, default)

    # ── scoring ───────────────────────────────────────────────────────────

    def get_score(self) -> int:
        return self._score_data["score"]

    def get_score_data(self) -> dict:
        return dict(self._score_data)

    def record_first_wrong_move(self, puzzle_rating: int) -> int:
        """
        Call this only on the FIRST wrong move of a puzzle.
        Returns the delta applied.
        """
        old = self._score_data["score"]
        expected = self._expected_score(old, puzzle_rating)
        delta = -max(1, round((RATING_K_FACTOR / 3) * expected))
        self._score_data["total_wrong"] += 1
        return self._apply_delta(delta, "first_wrong")

    def record_puzzle_hint(self, puzzle_rating: int) -> int:
        """
        Deduct a penalty when the player asks for a hint.
        """
        old = self._score_data["score"]
        expected = self._expected_score(old, puzzle_rating)
        delta = -max(1, round((RATING_K_FACTOR / 3) * expected))
        self._score_data["total_hints"] += 1
        return self._apply_delta(delta, "hint")

    def record_puzzle_solved(self, puzzle_rating: int, had_mistakes: bool) -> int:
        old = self._score_data["score"]
        expected = self._expected_score(old, puzzle_rating)
        clean_delta = max(2, round(RATING_K_FACTOR * (1 - expected)))
        delta = clean_delta if not had_mistakes else 0
        self._score_data["total_solved"] += 1
        return self._apply_delta(delta, "solved")

    def record_puzzle_skipped(self, puzzle_rating: int) -> int:
        old = self._score_data["score"]
        expected = self._expected_score(old, puzzle_rating)
        delta = -max(2, round(RATING_K_FACTOR * expected))
        self._score_data["total_skipped"] += 1
        return self._apply_delta(delta, "skipped")

    def preview_puzzle_skip_delta(self, puzzle_rating: int) -> int:
        """
        Return the score delta that would be applied for skipping a puzzle.
        """
        old = self._score_data["score"]
        expected = self._expected_score(old, puzzle_rating)
        return -max(2, round(RATING_K_FACTOR * expected))

    def _apply_delta(self, delta: int, event: str) -> int:
        old  = self._score_data["score"]
        new  = max(SCORE_FLOOR, old + delta)
        real = new - old          # actual change (may be less if floor hit)
        self._score_data["score"] = new
        self._save_score()
        return real

    @staticmethod
    def _expected_score(player_rating: int, puzzle_rating: int) -> float:
        return 1 / (1 + 10 ** ((puzzle_rating - player_rating) / 400))

    # ── helpers ───────────────────────────────────────────────────────────

    def _next_id(self):
        return max((a["id"] for a in self._alarms), default=0) + 1

    def _load_json(self, path, default):
        try:
            with open(path) as f:
                return json.load(f)
        except Exception:
            return default

    def _save_alarms(self):
        _ensure_dir()
        with open(ALARMS_FILE, "w") as f:
            json.dump(self._alarms, f, indent=2)

    def _save_settings(self):
        _ensure_dir()
        with open(SETTINGS_FILE, "w") as f:
            json.dump(self._settings, f, indent=2)

    def _save_score(self):
        _ensure_dir()
        with open(SCORE_FILE, "w") as f:
            json.dump(self._score_data, f, indent=2)
