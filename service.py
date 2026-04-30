"""
service.py — Android background alarm service.
"""

import time
from datetime import datetime

from kivy import platform
from kivy.logger import Logger

if platform == "android":
    from jnius import autoclass
    from data.store import AlarmStore

    PythonService = autoclass("org.kivy.android.PythonService")
    Intent = autoclass("android.content.Intent")
    Context = autoclass("android.content.Context")
    Build = autoclass("android.os.Build")
    NotificationManager = autoclass("android.app.NotificationManager")

    def _service():
        return getattr(PythonService, "mService", None)

    def _start_foreground():
        service = _service()
        if service is None:
            Logger.warning("AlarmService: no PythonService instance available")
            return

        try:
            ctx = service.getApplicationContext()
            if Build.VERSION.SDK_INT >= 26:
                channel_id = "chessmate_alarm_channel"
                NotificationChannel = autoclass("android.app.NotificationChannel")
                NotificationBuilder = autoclass("android.app.Notification$Builder")
                nm = ctx.getSystemService(Context.NOTIFICATION_SERVICE)
                chan = NotificationChannel(
                    channel_id,
                    "ChessMate Alarms",
                    NotificationManager.IMPORTANCE_LOW,
                )
                nm.createNotificationChannel(chan)
                nb = NotificationBuilder(ctx, channel_id)
            else:
                NotificationBuilder = autoclass("android.app.Notification$Builder")
                nb = NotificationBuilder(ctx)

            nb.setContentTitle("ChessMate Alarm")
            nb.setContentText("Alarm scheduler running")
            try:
                nb.setSmallIcon(ctx.getApplicationInfo().icon)
            except Exception:
                pass
            service.startForeground(1, nb.build())
        except Exception:
            Logger.exception("AlarmService: failed to start foreground")

    def _launch_main_activity():
        service = _service()
        if service is None:
            return
        try:
            ctx = service.getApplicationContext()
            package_name = ctx.getPackageName()
            pm = ctx.getPackageManager()
            intent = pm.getLaunchIntentForPackage(package_name)
            if intent is None:
                intent = Intent()
                intent.setAction(Intent.ACTION_MAIN)
                intent.addCategory(Intent.CATEGORY_LAUNCHER)
                intent.setPackage(package_name)
            intent.setFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
            service.startActivity(intent)
        except Exception:
            Logger.exception("AlarmService: failed to launch main activity")

    def _should_fire_alarm(alarm: dict, now: datetime) -> bool:
        if not alarm.get("enabled", True):
            return False

        snoozed_until = alarm.get("snoozed_until")
        if snoozed_until:
            try:
                snoozed_until_dt = datetime.fromisoformat(snoozed_until)
            except Exception:
                snoozed_until_dt = None

            if snoozed_until_dt and now < snoozed_until_dt:
                return False

            if snoozed_until_dt and now >= snoozed_until_dt:
                return True

        if alarm.get("hour") != now.hour or alarm.get("minute") != now.minute:
            return False

        days = alarm.get("days", [])
        return not days or now.weekday() in days

    def run_service():
        Logger.info("AlarmService: background service starting")
        store = AlarmStore()
        try:
            Logger.info(
                f"AlarmService: loaded {len(store.get_alarms())} alarms and rescheduled them"
            )
        except Exception:
            pass
        _start_foreground()

        while True:
            try:
                now = datetime.now()
                for alarm in store.get_alarms():
                    if not _should_fire_alarm(alarm, now):
                        continue

                    snoozed_until = alarm.get("snoozed_until")
                    if snoozed_until:
                        try:
                            snoozed_until_dt = datetime.fromisoformat(snoozed_until)
                        except Exception:
                            snoozed_until_dt = None
                        if snoozed_until_dt and now >= snoozed_until_dt:
                            try:
                                store.update_alarm(alarm["id"], {"snoozed_until": None})
                            except Exception:
                                Logger.exception(
                                    f"AlarmService: failed clearing snooze for alarm {alarm.get('id')}"
                                )

                    Logger.info(f"AlarmService: firing alarm {alarm.get('id')}")
                    _launch_main_activity()
                    break
            except Exception:
                Logger.exception("AlarmService: scheduler loop failed")

            time.sleep(10)

    run_service()
else:
    Logger.info("AlarmService: non-Android platform, service disabled")
