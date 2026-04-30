"""
utils/android_alarm.py — Exact alarm scheduling helpers for Android.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Iterable, Optional

from kivy.utils import platform
from kivy.logger import Logger
from utils.ringtones import resolve_alarm_ringtone
from utils.android_permissions import (
    has_android_exact_alarm_access,
)

if platform == "android":
    from jnius import autoclass

    PythonActivity = autoclass("org.kivy.android.PythonActivity")
    PythonService = autoclass("org.kivy.android.PythonService")
    Intent = autoclass("android.content.Intent")
    PendingIntent = autoclass("android.app.PendingIntent")
    AlarmManager = autoclass("android.app.AlarmManager")
    AlarmClockInfo = autoclass("android.app.AlarmManager$AlarmClockInfo")
    Context = autoclass("android.content.Context")
    Build = autoclass("android.os.Build")
    AlarmReceiver = autoclass("org.chessmate.chessmatesalarm.AlarmReceiver")
    AlarmForegroundService = autoclass("org.chessmate.chessmatesalarm.AlarmForegroundService")
    SharedPreferences = autoclass("android.content.SharedPreferences")

    FLAG_UPDATE_CURRENT = getattr(PendingIntent, "FLAG_UPDATE_CURRENT")
    FLAG_IMMUTABLE = getattr(PendingIntent, "FLAG_IMMUTABLE", 0)
    PI_FLAGS = FLAG_UPDATE_CURRENT | FLAG_IMMUTABLE
else:
    PythonActivity = None
    PythonService = None
    Intent = None
    PendingIntent = None
    AlarmManager = None
    AlarmClockInfo = None
    Context = None
    Build = None
    AlarmReceiver = None
    AlarmForegroundService = None
    SharedPreferences = None
    PI_FLAGS = 0


def _context():
    if platform != "android":
        return None
    activity = getattr(PythonActivity, "mActivity", None)
    if activity is not None:
        return activity
    service = getattr(PythonService, "mService", None)
    return service


def _alarm_manager(ctx):
    if ctx is None:
        return None
    try:
        return ctx.getSystemService(Context.ALARM_SERVICE)
    except Exception:
        return None


def _launch_intent(ctx, alarm_id: int, alarm: Optional[dict] = None):
    intent = Intent(ctx, AlarmReceiver)
    intent.putExtra("alarm_id", int(alarm_id))
    if alarm:
        intent.putExtra("alarm_label", str(alarm.get("label", "Alarm")))
        intent.putExtra("alarm_hour", int(alarm.get("hour", 0)))
        intent.putExtra("alarm_minute", int(alarm.get("minute", 0)))
        days = alarm.get("days", []) or []
        intent.putExtra(
            "alarm_days",
            ",".join(str(int(day)) for day in days),
        )
        ringtone_path, _ = resolve_alarm_ringtone(alarm)
        intent.putExtra("ringtone_path", ringtone_path)
    return intent


def _pending_intent(ctx, alarm: dict):
    alarm_id = int(alarm.get("id", 0))
    intent = _launch_intent(ctx, alarm_id, alarm)
    return PendingIntent.getBroadcast(ctx, alarm_id, intent, PI_FLAGS)


def _next_datetime(alarm: dict, now: Optional[datetime] = None) -> Optional[datetime]:
    now = now or datetime.now()
    if not alarm.get("enabled", True):
        return None

    snoozed_until = alarm.get("snoozed_until")
    if snoozed_until:
        try:
            snooze_dt = datetime.fromisoformat(snoozed_until)
            if snooze_dt > now:
                return snooze_dt
        except Exception:
            pass

    hour = int(alarm.get("hour", 0))
    minute = int(alarm.get("minute", 0))
    days = alarm.get("days", []) or []

    candidate = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
    if not days:
        if candidate <= now:
            candidate += timedelta(days=1)
        return candidate

    for offset in range(8):
        test = candidate + timedelta(days=offset)
        if test.weekday() in days and test > now:
            return test
    return None


def schedule_alarm(alarm: dict) -> bool:
    if platform != "android":
        return False
    ctx = _context()
    am = _alarm_manager(ctx)
    if ctx is None or am is None:
        return False

    if not has_android_exact_alarm_access():
        Logger.warning(
            f"AndroidAlarm: exact alarm access is not available for alarm {alarm.get('id')}"
        )
        return False

    try:
        if hasattr(am, "canScheduleExactAlarms") and not am.canScheduleExactAlarms():
            Logger.warning(
                f'AndroidAlarm: exact alarm permission check returned false for alarm {alarm.get("id")}'
            )
            return False
    except Exception:
        pass

    alarm_id = int(alarm.get("id", 0))
    pending = _pending_intent(ctx, alarm)
    next_dt = _next_datetime(alarm)
    if next_dt is None:
        Logger.warning(f"AndroidAlarm: no next trigger time for alarm {alarm_id}")
        cancel_alarm(alarm_id)
        return False

    trigger_at = int(next_dt.timestamp() * 1000)
    Logger.info(
        f"AndroidAlarm: scheduling alarm {alarm_id} for {next_dt.isoformat()} ({trigger_at})"
    )
    try:
        try:
            alarm_clock = AlarmClockInfo(trigger_at, pending)
            am.setAlarmClock(alarm_clock, pending)
            Logger.info(f"AndroidAlarm: scheduled alarm {alarm_id} with setAlarmClock")
            return True
        except Exception:
            Logger.warning(f"AndroidAlarm: setAlarmClock failed for alarm {alarm_id}, falling back")
        am.setExactAndAllowWhileIdle(AlarmManager.RTC_WAKEUP, trigger_at, pending)
        Logger.info(f"AndroidAlarm: scheduled alarm {alarm_id} with setExactAndAllowWhileIdle")
        return True
    except Exception:
        try:
            am.setExact(AlarmManager.RTC_WAKEUP, trigger_at, pending)
            Logger.info(f"AndroidAlarm: scheduled alarm {alarm_id} with setExact fallback")
            return True
        except Exception as exc:
            Logger.exception(f"AndroidAlarm: failed to schedule alarm {alarm_id}: {exc}")
            return False


def cancel_alarm(alarm_id: int) -> bool:
    if platform != "android":
        return False
    ctx = _context()
    am = _alarm_manager(ctx)
    if ctx is None or am is None:
        return False
    intent = _launch_intent(ctx, alarm_id, None)
    pending = PendingIntent.getBroadcast(ctx, int(alarm_id), intent, PI_FLAGS)
    try:
        am.cancel(pending)
        pending.cancel()
        Logger.info(f"AndroidAlarm: cancelled alarm {alarm_id}")
        return True
    except Exception:
        Logger.exception(f"AndroidAlarm: failed to cancel alarm {alarm_id}")
        return False


def stop_alarm_service(alarm_id: int = 0) -> bool:
    if platform != "android":
        return False
    ctx = _context()
    if ctx is None:
        return False
    try:
        AlarmForegroundService.stop(ctx, int(alarm_id))
        return True
    except Exception:
        return False


def start_alarm_service_for_alarm(alarm: dict) -> bool:
    if platform != "android":
        return False
    ctx = _context()
    if ctx is None:
        return False

    alarm_id = int(alarm.get("id", 0))
    intent = _launch_intent(ctx, alarm_id, alarm)
    try:
        return bool(AlarmForegroundService.start(ctx, intent))
    except Exception:
        Logger.exception(f"AndroidAlarm: failed to start foreground service for alarm {alarm_id}")
        return False


def is_alarm_service_playing(alarm_id: int) -> bool:
    if platform != "android":
        return False
    ctx = _context()
    if ctx is None:
        return False
    try:
        return bool(AlarmForegroundService.isPlaying(ctx, int(alarm_id)))
    except Exception:
        return False


def reschedule_alarms(alarms: Iterable[dict]) -> None:
    if platform != "android":
        return
    for alarm in alarms:
        try:
            if alarm.get("enabled", True):
                schedule_alarm(alarm)
            else:
                cancel_alarm(int(alarm.get("id", 0)))
        except Exception:
            continue
