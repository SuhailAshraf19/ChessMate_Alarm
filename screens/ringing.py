"""
screens/ringing.py — Fullscreen alarm ringing screen.
All labels and buttons use font_name="DejaVuSans" so no boxes appear.
"""

from kivy.uix.screenmanager import Screen
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.label import Label
from kivy.uix.button import Button
from kivy.graphics import Color, RoundedRectangle, Rectangle
from kivy.clock import Clock
from kivy.app import App
from kivy.animation import Animation
from datetime import datetime
from kivy.utils import platform
from kivy.clock import Clock

from utils.android_alarm import (
    start_alarm_service_for_alarm,
    stop_alarm_service,
)

BG    = (0.05, 0.05, 0.07, 1)
AMBER = (1.00, 0.76, 0.22, 1)
WHITE = (0.95, 0.95, 0.97, 1)
GREY  = (0.50, 0.50, 0.55, 1)


def _bg(widget, color):
    with widget.canvas.before:
        Color(*color)
        widget._bg_r = RoundedRectangle(pos=widget.pos, size=widget.size, radius=[0])
    widget.bind(pos=lambda w, _: setattr(w._bg_r, 'pos', w.pos),
                size=lambda w, _: setattr(w._bg_r, 'size', w.size))


class RingingScreen(Screen):

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._alarm    = None
        self._tick_ev  = None
        self._build()

    def _build(self):
        root = BoxLayout(orientation="vertical", padding="24dp", spacing="14dp")
        _bg(root, BG)

        root.add_widget(BoxLayout(size_hint_y=0.06))

        # ── alarm icon (text-based, NotoSans) ─────────────────────────────
        icon = Label(
            text="[ALARM]", font_size="18sp",
            font_name="DejaVuSans",
            color=AMBER, size_hint_y=None, height="30dp",
            bold=True, halign="center", valign="middle"
        )
        icon.bind(size=icon.setter("text_size"))
        root.add_widget(icon)

        # ── time display ──────────────────────────────────────────────────
        self.time_lbl = Label(
            text="07:00", font_size="72sp", bold=True,
            font_name="DejaVuSans",
            color=WHITE, size_hint_y=None, height="90dp",
            halign="center", valign="middle"
        )
        self.time_lbl.bind(size=self.time_lbl.setter("text_size"))
        root.add_widget(self.time_lbl)

        # ── alarm label ───────────────────────────────────────────────────
        self.alarm_lbl = Label(
            text="Good Morning!", font_size="22sp", bold=True,
            font_name="DejaVuSans",
            color=AMBER, size_hint_y=None, height="36dp",
            halign="center", valign="middle"
        )
        self.alarm_lbl.bind(size=self.alarm_lbl.setter("text_size"))
        root.add_widget(self.alarm_lbl)

        # ── tagline ───────────────────────────────────────────────────────
        tagline = Label(
            text="Solve chess puzzles to dismiss",
            font_size="14sp",
            font_name="DejaVuSans",
            color=GREY, size_hint_y=None, height="26dp",
            halign="center", valign="middle"
        )
        tagline.bind(size=tagline.setter("text_size"))
        root.add_widget(tagline)

        root.add_widget(BoxLayout())   # flexible spacer

        # ── puzzle count badge ────────────────────────────────────────────
        self.badge_lbl = Label(
            text="3 puzzles required", font_size="14sp",
            font_name="DejaVuSans",
            color=GREY, size_hint_y=None, height="28dp",
            halign="center", valign="middle"
        )
        self.badge_lbl.bind(size=self.badge_lbl.setter("text_size"))
        root.add_widget(self.badge_lbl)

        # ── solve button ──────────────────────────────────────────────────
        solve_btn = Button(
            text="Solve Puzzles", font_size="19sp", bold=True,
            font_name="DejaVuSans",
            size_hint_y=None, height="64dp",
            background_normal="", background_color=(0, 0, 0, 0),
            color=(0.05, 0.05, 0.08, 1)
        )
        with solve_btn.canvas.before:
            Color(*AMBER)
            solve_btn._bg = RoundedRectangle(
                pos=solve_btn.pos, size=solve_btn.size, radius=[16]
            )
        solve_btn.bind(
            pos=lambda w, _: setattr(w._bg, 'pos', w.pos),
            size=lambda w, _: setattr(w._bg, 'size', w.size)
        )
        solve_btn.bind(on_release=lambda *_: self._start_puzzles())
        root.add_widget(solve_btn)

        # ── snooze button ─────────────────────────────────────────────────
        self.snooze_btn = Button(
            text="Snooze (5 min)", font_size="15sp",
            font_name="DejaVuSans",
            size_hint_y=None, height="48dp",
            background_normal="", background_color=(0, 0, 0, 0),
            color=GREY
        )
        self.snooze_btn.bind(on_release=lambda *_: self._snooze())
        root.add_widget(self.snooze_btn)

        root.add_widget(BoxLayout(size_hint_y=0.04))
        self.add_widget(root)

    # ── lifecycle ─────────────────────────────────────────────────────────

    def set_alarm(self, alarm: dict):
        from kivy.logger import Logger
        Logger.info(f'RingingScreen: set_alarm called with id={alarm.get("id")}')
        self._alarm = alarm
        try:
            app = App.get_running_app()
            if alarm and isinstance(alarm, dict) and int(alarm.get("id", 0)) > 0:
                app.store.set_active_alarm(alarm)
                if hasattr(app, "scheduler"):
                    app.scheduler.set_active(alarm)
        except Exception:
            Logger.exception("RingingScreen: failed to persist active alarm")

    def on_enter(self, *_):
        self._tick_ev = Clock.schedule_interval(self._tick, 1)
        self._tick(0)

        app      = App.get_running_app()
        settings = app.store.get_settings()
        count    = settings.get("puzzle_count", 3)

        self.badge_lbl.text = (
            f"{count} puzzle{'s' if count != 1 else ''} to solve"
        )

        snooze = settings.get("snooze_enabled", False)
        self.snooze_btn.opacity  = 1 if snooze else 0
        self.snooze_btn.disabled = not snooze

        if self._alarm:
            self.alarm_lbl.text = self._alarm.get("label", "Alarm")
        Clock.schedule_once(lambda *_: self._start_ringtone(), 0.1)

    def on_leave(self, *_):
        if self._tick_ev:
            Clock.unschedule(self._tick_ev)

    # ── actions ───────────────────────────────────────────────────────────

    def _tick(self, *_):
        self.time_lbl.text = datetime.now().strftime("%H:%M")

    def _start_puzzles(self):
        app      = App.get_running_app()
        settings = app.store.get_settings()
        ps       = self.manager.get_screen("puzzle")
        ps.start_session(
            alarm        = self._alarm,
            player_score = app.store.get_score(),
            count        = settings.get("puzzle_count", 3),
        )
        self.manager.current = "puzzle"

    def _snooze(self):
        from datetime import timedelta
        self._stop_ringtone()
        app  = App.get_running_app()
        
        # Calculate snooze duration from settings
        snooze_minutes = app.store.get_setting("snooze_minutes", 5)
        snoozed_until = datetime.now() + timedelta(minutes=snooze_minutes)
        
        # Update the existing alarm with snooze info
        # Keep the original hour/minute so daily recurrence works correctly next day
        # Ensure alarm remains enabled while snoozed and increment snooze counter
        current_count = self._alarm.get("snooze_count", 0) or 0
        app.store.update_alarm(self._alarm["id"], {
            "snoozed_until": snoozed_until.isoformat(),
            "snooze_count": current_count + 1,
            "enabled": True,
        })
        
        app.scheduler.clear_active()
        self.manager.current = "home"

    def _start_ringtone(self):
        if not self._alarm:
            return
        from kivy.logger import Logger
        Logger.info(f'RingingScreen: starting ringtone for alarm id={self._alarm.get("id")}')
        if platform == "android":
            started = start_alarm_service_for_alarm(self._alarm)
            if started:
                Logger.info("RingingScreen: native alarm service requested")
            else:
                Logger.warning("RingingScreen: native alarm service request failed")
            return

    def _replay_ringtone(self):
        return

    def _stop_ringtone(self):
        app = App.get_running_app()
        alarm_id = int(self._alarm.get("id", 0)) if isinstance(self._alarm, dict) else 0
        if platform == "android":
            try:
                stop_alarm_service(alarm_id)
                from jnius import autoclass

                AlarmRinger = autoclass("org.chessmate.chessmatesalarm.AlarmRinger")
                AlarmRinger.stop()
            except Exception:
                pass
        if hasattr(app, "sound_preview"):
            app.sound_preview.stop()
