"""
utils/scheduler.py — Background thread that watches for due alarms.
"""

import threading
from datetime import datetime
from kivy.clock import Clock
from kivy.logger import Logger


class AlarmScheduler:
    """Polls every 10 seconds; fires the ringing screen when an alarm is due."""

    CHECK_INTERVAL = 5  # seconds

    def __init__(self, screen_manager, store):
        self.sm = screen_manager
        self.store = store
        self._thread = None
        self._stop_event = threading.Event()
        self._active_alarm = None   # alarm dict currently ringing

    def start(self):
        self._stop_event.clear()
        Clock.schedule_interval(self._check, self.CHECK_INTERVAL)

    def stop(self):
        self._stop_event.set()
        Clock.unschedule(self._check)

    def _check(self, dt):
        if self._active_alarm or self.store.get_active_alarm_id() is not None:
            return  # already ringing

        now = datetime.now()
        trigger_key = now.strftime("%Y-%m-%d %H:%M")
        alarms = self.store.get_alarms()

        for alarm in alarms:
            try:
                if not alarm.get("enabled", True):
                    continue

                if alarm.get("last_triggered_key") == trigger_key:
                    continue

                # Check if alarm is currently snoozed
                snoozed_until = alarm.get("snoozed_until")
                if snoozed_until:
                    try:
                        snoozed_until_dt = datetime.fromisoformat(snoozed_until)
                    except Exception:
                        # If stored as datetime already or malformed, try to skip
                        Logger.warning(f'AlarmScheduler: invalid snoozed_until format for alarm {alarm.get("id")}: {snoozed_until}')
                        snoozed_until_dt = None
                    if snoozed_until_dt and now < snoozed_until_dt:
                        # Still snoozed, skip this alarm
                        continue
                    if snoozed_until_dt and now >= snoozed_until_dt:
                        # Ring once the snooze expires without creating a new alarm
                        # or changing the original scheduled time.
                        try:
                            self.store.update_alarm(alarm["id"], {"snoozed_until": None})
                            alarm["snoozed_until"] = None
                        except Exception:
                            Logger.exception(f'AlarmScheduler: failed clearing snooze for alarm {alarm.get("id")}')
                        self._fire(alarm)
                        break

                if alarm["hour"] == now.hour and alarm["minute"] == now.minute:
                    days = alarm.get("days", [])
                    if days:
                        # Recurring: check weekday (0=Monday in Python, 0=Monday here)
                        if now.weekday() not in days:
                            continue
                    else:
                        # One-time: do NOT disable here — dismissal will disable after puzzles solved.
                        pass

                    self._fire(alarm)
                    break
            except Exception:
                Logger.exception(f'AlarmScheduler: exception while checking alarm {alarm.get("id")}')

    def _fire(self, alarm):
        try:
            now = datetime.now()
            self.store.update_alarm(
                alarm["id"],
                {
                    "last_triggered_key": now.strftime("%Y-%m-%d %H:%M"),
                },
            )
            self.store.set_active_alarm(alarm)
        except Exception:
            Logger.exception(f'AlarmScheduler: failed to persist active alarm {alarm.get("id")}')
        self._active_alarm = alarm
        Clock.schedule_once(lambda dt: self._show_ringing(alarm), 0)

    def _show_ringing(self, alarm):
        try:
            ringing = self.sm.get_screen("ringing")
            ringing.set_alarm(alarm)
            self.sm.current = "ringing"
        except Exception:
            self.sm.current = "ringing"

    def clear_active(self):
        self._active_alarm = None
        try:
            self.store.clear_active_alarm()
        except Exception:
            Logger.exception("AlarmScheduler: failed clearing active alarm state")

    def set_active(self, alarm):
        self._active_alarm = alarm
        try:
            self.store.set_active_alarm(alarm)
        except Exception:
            Logger.exception(f'AlarmScheduler: failed setting active alarm {alarm.get("id")}')
