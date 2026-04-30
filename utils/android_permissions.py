"""
utils/android_permissions.py — Runtime permission helpers for Android.
"""

from kivy.utils import platform
from kivy.logger import Logger

_PROMPTED_EXACT_ALARM = False
_PROMPTED_AUDIO_ACCESS = False
_PROMPTED_BATTERY_OPT = False
_PROMPTED_NOTIFICATION_ACCESS = False


def ensure_android_permissions() -> None:
    request_android_notification_permission()


def request_android_notification_permission() -> bool:
    if platform != "android":
        return False

    try:
        from android.permissions import check_permission, request_permissions, Permission

        notif_perm = getattr(Permission, "POST_NOTIFICATIONS", None)
        if notif_perm is None:
            return False

        if check_permission(notif_perm):
            global _PROMPTED_NOTIFICATION_ACCESS
            _PROMPTED_NOTIFICATION_ACCESS = True
            return True

        request_permissions([notif_perm])
        _PROMPTED_NOTIFICATION_ACCESS = True
        Logger.info("AndroidPermissions: requested notification permission")
        return True
    except Exception:
        Logger.exception("AndroidPermissions: failed to request notification permission")
        return False


def request_android_audio_permissions() -> None:
    if platform != "android":
        return False

    try:
        from android.permissions import request_permissions, Permission
        perms = _audio_permission_list(Permission)
        if perms:
            request_permissions(perms)
    except Exception:
        pass
    global _PROMPTED_AUDIO_ACCESS
    _PROMPTED_AUDIO_ACCESS = True
    return True


def request_android_background_access() -> None:
    return open_android_battery_settings()


def has_android_exact_alarm_access() -> bool:
    if platform != "android":
        return False

    try:
        from jnius import autoclass

        PythonActivity = autoclass("org.kivy.android.PythonActivity")
        Context = autoclass("android.content.Context")

        activity = getattr(PythonActivity, "mActivity", None)
        if activity is None:
            return False

        am = activity.getSystemService(Context.ALARM_SERVICE)
        if am is None:
            return False
        return bool(am.canScheduleExactAlarms())
    except Exception:
        return False


def ensure_exact_alarm_access() -> bool:
    if platform != "android":
        return False

    if has_android_exact_alarm_access():
        Logger.info("AndroidPermissions: exact alarm access already granted")
        return True

    Logger.warning("AndroidPermissions: exact alarm access is missing")
    return False


def open_android_battery_settings() -> None:
    global _PROMPTED_BATTERY_OPT
    if platform != "android":
        return False

    try:
        from jnius import autoclass

        PythonActivity = autoclass("org.kivy.android.PythonActivity")
        Intent = autoclass("android.content.Intent")
        Settings = autoclass("android.provider.Settings")
        Uri = autoclass("android.net.Uri")
        PowerManager = autoclass("android.os.PowerManager")
        Build = autoclass("android.os.Build")
        Context = autoclass("android.content.Context")

        activity = getattr(PythonActivity, "mActivity", None)
        if activity is None:
            return False

        if Build.VERSION.SDK_INT < 23:
            _PROMPTED_BATTERY_OPT = True
            return True

        pm = activity.getSystemService(Context.POWER_SERVICE)
        if pm and pm.isIgnoringBatteryOptimizations(activity.getPackageName()):
            _PROMPTED_BATTERY_OPT = True
            return True

        intent = Intent(Settings.ACTION_REQUEST_IGNORE_BATTERY_OPTIMIZATIONS)
        intent.setData(Uri.parse("package:" + activity.getPackageName()))
        intent.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
        activity.startActivity(intent)
        _PROMPTED_BATTERY_OPT = True
        return True
    except Exception:
        _PROMPTED_BATTERY_OPT = True
        return False


def open_android_exact_alarm_settings(force: bool = True) -> None:
    if platform != "android":
        return False

    try:
        from jnius import autoclass

        PythonActivity = autoclass("org.kivy.android.PythonActivity")
        Settings = autoclass("android.provider.Settings")
        Intent = autoclass("android.content.Intent")
        Build = autoclass("android.os.Build")
        Context = autoclass("android.content.Context")
        Uri = autoclass("android.net.Uri")
        Logger.info("AndroidPermissions: requesting exact alarm access")

        activity = getattr(PythonActivity, "mActivity", None)
        if activity is None:
            Logger.warning("AndroidPermissions: activity not ready for exact alarm settings")
            return False

        if Build.VERSION.SDK_INT < 31:
            Logger.info("AndroidPermissions: exact alarms do not require special access on this Android version")
            return True

        if not force:
            try:
                am = activity.getSystemService(Context.ALARM_SERVICE)
                if am and am.canScheduleExactAlarms():
                    Logger.info("AndroidPermissions: exact alarm access already available")
                    return True
            except Exception:
                pass

        pkg_uri = Uri.parse("package:" + activity.getPackageName())
        try:
            intent = Intent(Settings.ACTION_REQUEST_SCHEDULE_EXACT_ALARM)
            intent.setData(pkg_uri)
            intent.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
            activity.startActivity(intent)
            Logger.info("AndroidPermissions: opened exact alarm request screen")
            return True
        except Exception as exc:
            Logger.warning(f"AndroidPermissions: exact alarm request screen failed, falling back: {exc}")

        try:
            fallback = Intent(Settings.ACTION_APPLICATION_DETAILS_SETTINGS)
            fallback.setData(pkg_uri)
            fallback.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
            activity.startActivity(fallback)
            Logger.info("AndroidPermissions: opened app details fallback for exact alarm access")
            return True
        except Exception as exc:
            Logger.exception(f"AndroidPermissions: failed to open any exact alarm settings screen: {exc}")
            return False
    except Exception:
        return False


def _audio_permission_list(Permission):
    perms = []
    for perm_name in ("READ_MEDIA_AUDIO", "READ_EXTERNAL_STORAGE"):
        perm = getattr(Permission, perm_name, None)
        if perm is not None:
            perms.append(perm)
    return perms
