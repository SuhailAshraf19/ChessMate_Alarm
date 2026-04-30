"""
ChessMate Alarm — Wake up smarter.
A Kivy alarm app that requires solving chess puzzles to dismiss.
"""

import os
os.environ.setdefault("KIVY_NO_ENV_CONFIG", "1")

from kivy.utils import platform

# ── Font config MUST come before any other Kivy imports ──────────────────────
from kivy.config import Config
if platform not in ("android", "ios"):
    Config.set("kivy", "clipboard", "dummy")

from kivy.core.text import LabelBase
from kivy.resources import resource_find


APP_DIR = os.path.dirname(os.path.abspath(__file__))


def _first_existing(*paths):
    for path in paths:
        if path and os.path.exists(path):
            return path
    return ""


text_regular = _first_existing(
    resource_find("data/fonts/Roboto-Regular.ttf"),
    resource_find("data/fonts/DejaVuSans.ttf"),
)
text_bold = _first_existing(
    resource_find("data/fonts/Roboto-Bold.ttf"),
    text_regular,
)
text_italic = _first_existing(
    resource_find("data/fonts/Roboto-Italic.ttf"),
    text_regular,
)
text_bolditalic = _first_existing(
    resource_find("data/fonts/Roboto-BoldItalic.ttf"),
    text_bold,
)

if text_regular:
    Config.set("kivy", "default_font", [
        "DejaVuSans",
        text_regular,
        text_bold,
        text_italic,
        text_bolditalic,
    ])
    LabelBase.register(
        name="DejaVuSans",
        fn_regular=text_regular,
        fn_bold=text_bold,
        fn_italic=text_italic,
        fn_bolditalic=text_bolditalic,
    )

chess_symbols = os.path.join(APP_DIR, "data", "fonts", "NotoSansSymbols2-Regular.ttf")
if os.path.exists(chess_symbols):
    LabelBase.register(
        name="ChessSymbols",
        fn_regular=chess_symbols,
        fn_bold=chess_symbols,
        fn_italic=chess_symbols,
        fn_bolditalic=chess_symbols,
    )

# ── All other Kivy imports after font registration ────────────────────────────
from kivy.app import App
from kivy.uix.screenmanager import ScreenManager, SlideTransition
from kivy.core.window import Window
from kivy.utils import platform
from kivy.clock import Clock

# Set window size for desktop testing (mobile ignores this)
if platform not in ("android", "ios"):
    Window.size = (390, 844)

from screens.home import HomeScreen
from screens.add_alarm import AddAlarmScreen
from screens.settings import SettingsScreen
from screens.ringing import RingingScreen
from screens.puzzle import PuzzleScreen
from data.store import AlarmStore
from utils.sound_preview import SoundPreviewManager
from utils.android_permissions import (
    request_android_background_access,
    request_android_notification_permission,
)
from utils.android_alarm import is_alarm_service_playing
from data.lichess_puzzles import start_cache_monitor


class ChessAlarmApp(App):
    title = "ChessMate Alarm"

    def build(self):
        self.store = AlarmStore()
        self.sound_preview = SoundPreviewManager()
        start_cache_monitor(10)

        sm = ScreenManager(transition=SlideTransition())
        sm.add_widget(HomeScreen(name="home"))
        sm.add_widget(AddAlarmScreen(name="add_alarm"))
        sm.add_widget(SettingsScreen(name="settings"))
        sm.add_widget(RingingScreen(name="ringing"))
        sm.add_widget(PuzzleScreen(name="puzzle"))

        from utils.scheduler import AlarmScheduler
        self.scheduler = AlarmScheduler(sm, self.store)
        self.scheduler.start()

        return sm

    def on_start(self):
        # Try again once the Android activity is fully attached.
        request_android_notification_permission()
        request_android_background_access()
        Clock.schedule_once(lambda *_: self._handle_android_launch_intent(), 0)
        Clock.schedule_once(lambda *_: self._restore_active_alarm(), 0.1)

    def on_resume(self):
        if platform == "android":
            request_android_notification_permission()
            Clock.schedule_once(lambda *_: self._handle_android_launch_intent(), 0)
            Clock.schedule_once(lambda *_: self._restore_active_alarm(), 0.1)

    def on_pause(self):
        # Keep the app alive in the background so an active alarm is not tied
        # to the visible UI lifecycle. The actual alarm stop happens only when
        # the user dismisses it from the ringing screen.
        return True

    def on_new_intent(self, intent):
        if platform == "android":
            Clock.schedule_once(lambda *_: self._handle_android_launch_intent(intent), 0)

    def _handle_android_launch_intent(self, intent=None):
        if platform != "android":
            return
        try:
            from jnius import autoclass

            PythonActivity = autoclass("org.kivy.android.PythonActivity")
            activity = getattr(PythonActivity, "mActivity", None)
            if activity is None:
                return

            intent = intent or activity.getIntent()
            if intent is None:
                return

            extras = intent.getExtras()
            if extras is None or not extras.containsKey("alarm_id"):
                return

            alarm_id = int(extras.get("alarm_id"))
            alarm_label = extras.getString("alarm_label") if extras.containsKey("alarm_label") else "Alarm"
            open_screen = extras.getString("open_screen") if extras.containsKey("open_screen") else "ringing"
            alarm = None
            for item in self.store.get_alarms():
                if int(item.get("id", -1)) == alarm_id:
                    alarm = dict(item)
                    break

            if alarm is None:
                alarm = {
                    "id": alarm_id,
                    "label": alarm_label,
                    "hour": 0,
                    "minute": 0,
                    "days": [],
                    "enabled": True,
                }

            self.store.set_active_alarm(alarm)
            if hasattr(self, "scheduler"):
                self.scheduler.set_active(alarm)

            if open_screen == "puzzle":
                puzzle = self.root.get_screen("puzzle")
                settings = self.store.get_settings()
                puzzle.start_session(
                    alarm=alarm,
                    player_score=self.store.get_score(),
                    count=settings.get("puzzle_count", 3),
                )
                self.root.current = "puzzle"
            else:
                ringing = self.root.get_screen("ringing")
                ringing.set_alarm(alarm)
                self.root.current = "ringing"
        except Exception:
            pass

    def _restore_active_alarm(self):
        try:
            alarm = self._get_active_alarm_from_state()
            if alarm is None:
                return

            if hasattr(self, "scheduler"):
                self.scheduler.set_active(alarm)

            if self.root is None:
                return

            try:
                current = self.root.current
            except Exception:
                current = None

            if current == "puzzle":
                try:
                    puzzle_screen = self.root.get_screen("puzzle")
                    current_alarm = getattr(puzzle_screen, "_alarm", None)
                    if (
                        isinstance(current_alarm, dict)
                        and int(current_alarm.get("id", 0)) == int(alarm.get("id", 0))
                    ):
                        return
                except Exception:
                    pass

            ringing = self.root.get_screen("ringing")
            ringing.set_alarm(alarm)
            if current != "ringing":
                self.root.current = "ringing"
        except Exception:
            pass

    def _get_active_alarm_from_state(self):
        active = None
        try:
            active = self.store.get_active_alarm()
        except Exception:
            active = None

        if active and isinstance(active, dict) and int(active.get("id", 0)) > 0:
            return active

        if platform != "android":
            return None

        try:
            for alarm in self.store.get_alarms():
                alarm_id = int(alarm.get("id", 0))
                if alarm_id > 0 and is_alarm_service_playing(alarm_id):
                    self.store.set_active_alarm(alarm)
                    return dict(alarm)
        except Exception:
            pass

        return None

    def on_stop(self):
        # Do not stop alarm playback here. Android can call on_stop() when the
        # app is removed from recents, and that should not silence a live alarm.
        # The ringing screen and puzzle flow explicitly stop the ringer when the
        # user dismisses the alarm.
        current_screen = None
        try:
            if self.root is not None:
                current_screen = self.root.current
        except Exception:
            pass

        if hasattr(self, "sound_preview") and current_screen != "ringing":
            self.sound_preview.stop()
        if hasattr(self, "scheduler"):
            self.scheduler.stop()


if __name__ == "__main__":
    ChessAlarmApp().run()
