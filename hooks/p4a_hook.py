from pathlib import Path

from pythonforandroid.logger import info


SCHEDULE_EXACT_ALARM = (
    '<uses-permission android:name="android.permission.SCHEDULE_EXACT_ALARM" />'
)
SCHEDULE_EXACT_ALARM_LIMITED = (
    '<uses-permission android:name="android.permission.SCHEDULE_EXACT_ALARM" '
    'android:maxSdkVersion="32" />'
)
USE_EXACT_ALARM = '<uses-permission android:name="android.permission.USE_EXACT_ALARM" />'

RECEIVER_XML = """
        <receiver
            android:name="org.chessmate.chessmatesalarm.AlarmReceiver"
            android:exported="false" />
"""

SERVICE_XML = """
        <service
            android:name="org.chessmate.chessmatesalarm.AlarmForegroundService"
            android:enabled="true"
            android:exported="false"
            android:process=":alarm"
            android:foregroundServiceType="mediaPlayback" />
"""

BOOT_RECEIVER_XML = """
        <receiver
            android:name="org.chessmate.chessmatesalarm.BootReceiver"
            android:enabled="true"
            android:exported="false">
            <intent-filter>
                <action android:name="android.intent.action.BOOT_COMPLETED" />
                <action android:name="android.intent.action.LOCKED_BOOT_COMPLETED" />
            </intent-filter>
        </receiver>
"""


def after_apk_build(toolchain):
    manifest = Path(toolchain._dist.dist_dir) / "src" / "main" / "AndroidManifest.xml"
    if not manifest.exists():
        info(f"Hook: manifest not found at {manifest}")
        return

    content = manifest.read_text(encoding="utf-8")
    updated = content

    if SCHEDULE_EXACT_ALARM in updated and SCHEDULE_EXACT_ALARM_LIMITED not in updated:
        updated = updated.replace(SCHEDULE_EXACT_ALARM, SCHEDULE_EXACT_ALARM_LIMITED, 1)
        info("Hook: limited SCHEDULE_EXACT_ALARM to API 32")

    if USE_EXACT_ALARM not in updated:
        app_marker = "<application"
        if app_marker in updated:
            updated = updated.replace(app_marker, USE_EXACT_ALARM + "\n\n    " + app_marker, 1)
            info("Hook: injected USE_EXACT_ALARM permission")

    app_close = "</application>"
    if app_close in updated:
        insert_xml = ""
        if "org.chessmate.chessmatesalarm.AlarmReceiver" not in updated:
            insert_xml += RECEIVER_XML
        if "org.chessmate.chessmatesalarm.BootReceiver" not in updated:
            insert_xml += BOOT_RECEIVER_XML
        if "org.chessmate.chessmatesalarm.AlarmForegroundService" not in updated:
            insert_xml += SERVICE_XML

        if insert_xml:
            updated = updated.replace(
                app_close,
                insert_xml + "\n    " + app_close,
                1,
            )
            info("Hook: injected Android alarm components into AndroidManifest.xml")
    else:
        info("Hook: application close tag not found, receivers not injected")

    if updated != content:
        manifest.write_text(updated, encoding="utf-8")
