"""
screens/home.py — Main alarm list screen.
"""

from kivy.uix.screenmanager import Screen
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.scrollview import ScrollView
from kivy.uix.label import Label
from kivy.uix.button import Button
from kivy.uix.switch import Switch
from kivy.graphics import Color, RoundedRectangle, Line
from kivy.clock import Clock
from kivy.app import App
from kivy.utils import platform
from datetime import datetime
from utils.android_permissions import (
    has_android_exact_alarm_access,
    open_android_exact_alarm_settings,
)
BG    = (0.07, 0.07, 0.10, 1)
CARD  = (0.12, 0.12, 0.17, 1)
AMBER = (1.00, 0.76, 0.22, 1)
WHITE = (0.95, 0.95, 0.97, 1)
GREY  = (0.55, 0.55, 0.60, 1)
RED   = (0.85, 0.25, 0.25, 1)


def _bg(widget, color):
    with widget.canvas.before:
        Color(*color)
        widget._bg_rect = RoundedRectangle(pos=widget.pos, size=widget.size, radius=[0])
    widget.bind(pos=lambda w, v: setattr(w._bg_rect, 'pos', v),
                size=lambda w, v: setattr(w._bg_rect, 'size', v))


class AlarmCard(BoxLayout):
    """One row representing a single alarm."""

    def __init__(self, alarm: dict, on_toggle, on_edit, on_solve, active=False, **kwargs):
        super().__init__(orientation="horizontal", size_hint_y=None,
                         height="80dp", padding="12dp", spacing="12dp", **kwargs)
        self.alarm = alarm
        self.active = active

        with self.canvas.before:
            Color(*(AMBER if active else CARD))
            self._card = RoundedRectangle(pos=self.pos, size=self.size, radius=[14])
            Color(*(WHITE if active else AMBER))
            self._border = Line(rounded_rectangle=[*self.pos, *self.size, 14], width=1)
        self.bind(pos=self._update_rect, size=self._update_rect)

        # ── left: time + days ─────────────────────────────────────────────
        left = BoxLayout(orientation="vertical", size_hint_x=0.38)
        tl = Label(
            text=f"{alarm['hour']:02d}:{alarm['minute']:02d}",
            font_size="28sp", bold=True, color=WHITE,
            font_name="DejaVuSans",
            halign="left", valign="middle"
        )
        tl.bind(size=tl.setter("text_size"))

        dl = Label(
            text=self._days_status_label(alarm),
            font_size="11sp", color=GREY,
            font_name="DejaVuSans",
            halign="left", valign="middle"
        )
        dl.bind(size=dl.setter("text_size"))

        left.add_widget(tl)
        left.add_widget(dl)

        # ── mid: alarm label ──────────────────────────────────────────────
        mid = BoxLayout(orientation="vertical", size_hint_x=0.28)
        ll = Label(
            text=alarm.get("label", "Alarm"), font_size="13sp",
            font_name="DejaVuSans",
            color=(0.06, 0.06, 0.08, 1) if active else AMBER, halign="left", valign="middle"
        )
        ll.bind(size=ll.setter("text_size"))
        mid.add_widget(ll)
        if active:
            ring_lbl = Label(
                text="Ringing now", font_size="11sp",
                font_name="DejaVuSans",
                color=(0.08, 0.08, 0.10, 1), halign="left", valign="middle"
            )
            ring_lbl.bind(size=ring_lbl.setter("text_size"))
            mid.add_widget(ring_lbl)

        # ── right: active solve button or toggle + update ────────────────
        right = BoxLayout(orientation="horizontal", size_hint_x=0.34,
                          spacing="2dp")

        if active:
            solve_btn = Button(
                text="Solve Puzzles", font_size="12sp",
                font_name="DejaVuSans",
                background_normal="", background_color=(0, 0, 0, 0),
                color=(0.08, 0.08, 0.10, 1)
            )
            with solve_btn.canvas.before:
                Color(*WHITE)
                solve_btn._bg = RoundedRectangle(pos=solve_btn.pos, size=solve_btn.size, radius=[12])
            solve_btn.bind(pos=lambda w, v: setattr(w._bg, 'pos', v),
                           size=lambda w, v: setattr(w._bg, 'size', v))
            solve_btn.bind(on_release=lambda *_: on_solve(alarm))
            right.add_widget(solve_btn)
        else:
            sw = Switch(active=alarm.get("enabled", True), size_hint_x=0.45)
            sw.bind(active=lambda inst, val: on_toggle(alarm["id"], val))

            edit_btn = Button(
                text="Update", font_size="11sp",
                font_name="DejaVuSans",
                size_hint_x=0.55,
                background_normal="", background_color=(0, 0, 0, 0),
                color=AMBER
            )
            edit_btn.bind(on_release=lambda *_: on_edit(alarm))

            right.add_widget(sw)
            right.add_widget(edit_btn)

        self.add_widget(left)
        self.add_widget(mid)
        self.add_widget(right)

    def _update_rect(self, *_):
        self._card.pos = self.pos
        self._card.size = self.size
        self._border.rounded_rectangle = [*self.pos, *self.size, 14]

    @staticmethod
    def _days_label(days):
        if not days:
            return "One-time"
        names = ["Mo", "Tu", "We", "Th", "Fr", "Sa", "Su"]
        if sorted(days) == list(range(7)):
            return "Every day"
        if sorted(days) == [0, 1, 2, 3, 4]:
            return "Weekdays"
        if sorted(days) == [5, 6]:
            return "Weekends"
        return "  ".join(names[d] for d in sorted(days))

    @staticmethod
    def _days_status_label(alarm):
        days = alarm.get("days", [])
        base = AlarmCard._days_label(days)
        snoozed = alarm.get("snoozed_until")
        snooze_count = alarm.get("snooze_count", 0) or 0
        if snoozed:
            # Show snoozed and count
            return f"Snoozed ({snooze_count}x)"
        return base


class HomeScreen(Screen):

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._build()

    def _build(self):
        root = BoxLayout(orientation="vertical")
        _bg(root, BG)

        # ── header ────────────────────────────────────────────────────────
        header = BoxLayout(orientation="horizontal", size_hint_y=None,
                           height="64dp", padding=["16dp", "8dp"])
        _bg(header, (0.09, 0.09, 0.13, 1))

        title = Label(
            text="ChessMate Alarm", font_size="22sp", bold=True,
            font_name="DejaVuSans",
            color=AMBER, halign="left", valign="middle", size_hint_x=0.72
        )
        title.bind(size=title.setter("text_size"))

        settings_btn = Button(
            text="Settings", font_size="13sp",
            font_name="DejaVuSans",
            background_normal="", background_color=(0, 0, 0, 0),
            color=AMBER, size_hint_x=0.28
        )
        settings_btn.bind(on_release=lambda *_: self._go_settings())

        header.add_widget(title)
        header.add_widget(settings_btn)

        # ── clock display ─────────────────────────────────────────────────
        self.clock_label = Label(
            text="00:00", font_size="52sp", bold=True,
            font_name="DejaVuSans",
            color=WHITE, size_hint_y=None, height="80dp"
        )
        Clock.schedule_interval(self._update_clock, 1)

        self.permission_banner = Label(
            text="",
            font_size="12sp",
            font_name="DejaVuSans",
            color=AMBER,
            halign="center",
            valign="middle",
            size_hint_y=None,
            height="0dp",
            opacity=0,
        )
        self.permission_banner.bind(size=self.permission_banner.setter("text_size"))

        self.exact_alarm_card = BoxLayout(
            orientation="horizontal",
            size_hint_y=None,
            height="64dp",
            padding=["12dp", "10dp"],
            spacing="10dp",
        )
        _bg(self.exact_alarm_card, CARD)
        self.exact_alarm_message = Label(
            text="",
            font_size="12sp",
            font_name="DejaVuSans",
            color=WHITE,
            halign="left",
            valign="middle",
        )
        self.exact_alarm_message.bind(size=self.exact_alarm_message.setter("text_size"))
        self.exact_alarm_button = Button(
            text="Grant Exact Alarm Access",
            font_size="12sp",
            font_name="DejaVuSans",
            background_normal="",
            background_color=(0, 0, 0, 0),
            color=AMBER,
            size_hint_x=None,
            width="180dp",
        )
        self.exact_alarm_button.bind(on_release=lambda *_: self._open_exact_alarm_settings())
        self.exact_alarm_card.add_widget(self.exact_alarm_message)
        self.exact_alarm_card.add_widget(self.exact_alarm_button)

        # ── alarm list ────────────────────────────────────────────────────
        self.scroll = ScrollView()
        self.alarm_grid = BoxLayout(orientation="vertical",
                                    spacing="10dp", padding="16dp",
                                    size_hint_y=None)
        self.alarm_grid.bind(minimum_height=self.alarm_grid.setter("height"))
        self.scroll.add_widget(self.alarm_grid)

        # ── add button ────────────────────────────────────────────────────
        add_btn = Button(
            text="+ Add Alarm", font_size="17sp", bold=True,
            font_name="DejaVuSans",
            size_hint_y=None, height="56dp",
            background_normal="", background_color=(0, 0, 0, 0),
            color=(0.05, 0.05, 0.08, 1)
        )
        with add_btn.canvas.before:
            Color(*AMBER)
            add_btn._bg = RoundedRectangle(pos=add_btn.pos, size=add_btn.size, radius=[14])
        add_btn.bind(pos=lambda w, v: setattr(w._bg, 'pos', v),
                     size=lambda w, v: setattr(w._bg, 'size', v))
        add_btn.bind(on_release=lambda *_: self._go_add())

        # Free-solve button
        test_btn = Button(
            text="Solve Puzzle", font_size="14sp",
            font_name="DejaVuSans",
            size_hint_y=None, height="56dp",
            background_normal="", background_color=(0, 0, 0, 0),
            color=WHITE
        )
        with test_btn.canvas.before:
            Color(0.2, 0.6, 0.3, 1)
            test_btn._bg = RoundedRectangle(pos=test_btn.pos, size=test_btn.size, radius=[14])
        test_btn.bind(pos=lambda w, v: setattr(w._bg, 'pos', v),
                      size=lambda w, v: setattr(w._bg, 'size', v))
        test_btn.bind(on_release=lambda *_: self._test_puzzles())

        btn_wrap = BoxLayout(size_hint_y=None, height="72dp",
                             padding=["16dp", "8dp"], spacing="8dp")
        btn_wrap.add_widget(add_btn)
        btn_wrap.add_widget(test_btn)

        root.add_widget(header)
        root.add_widget(self.clock_label)
        root.add_widget(self.permission_banner)
        root.add_widget(self.exact_alarm_card)
        root.add_widget(self.scroll)
        root.add_widget(btn_wrap)
        self.add_widget(root)

    def on_enter(self, *_):
        self._refresh_permission_banner()
        self._refresh_alarms()

    def _refresh_permission_banner(self):
        if has_android_exact_alarm_access():
            self.permission_banner.text = "Exact alarm access is ready."
            self.permission_banner.color = (0.65, 0.95, 0.65, 1)
            self.exact_alarm_message.text = "Android can schedule exact alarms now."
            self.exact_alarm_button.opacity = 0
            self.exact_alarm_button.disabled = True
            self.permission_banner.height = "28dp"
            self.permission_banner.opacity = 1
            self.exact_alarm_card.height = "0dp"
            self.exact_alarm_card.opacity = 0
        else:
            self.permission_banner.text = "Exact alarm access still needs approval."
            self.permission_banner.color = (1.00, 0.76, 0.22, 1)
            self.exact_alarm_message.text = "Grant exact alarm access so alarms can ring when the app is closed."
            self.exact_alarm_button.opacity = 1
            self.exact_alarm_button.disabled = False
            self.permission_banner.height = "28dp"
            self.permission_banner.opacity = 1
            self.exact_alarm_card.height = "64dp"
            self.exact_alarm_card.opacity = 1

    def _open_exact_alarm_settings(self):
        if platform != "android":
            return
        try:
            self.permission_banner.text = "Opening exact alarm settings..."
            self.permission_banner.color = (1.00, 0.76, 0.22, 1)
            opened = open_android_exact_alarm_settings(force=True)
            if not opened:
                self.permission_banner.text = "Could not open exact alarm settings."
            self._refresh_permission_banner()
        except Exception:
            self.permission_banner.text = "Exact alarm request failed."
            self.permission_banner.color = (0.85, 0.25, 0.25, 1)

    def _update_clock(self, *_):
        self.clock_label.text = datetime.now().strftime("%H:%M")

    def _refresh_alarms(self):
        self.alarm_grid.clear_widgets()
        app = App.get_running_app()
        alarms = app.store.get_alarms()

        if not alarms:
            empty = Label(
                text="No alarms yet.\nTap '+ Add Alarm' to create one.",
                font_size="15sp", color=GREY, halign="center",
                font_name="DejaVuSans",
                size_hint_y=None, height="120dp"
            )
            empty.bind(size=empty.setter("text_size"))
            self.alarm_grid.add_widget(empty)
            return

        alarms_sorted = sorted(
            alarms,
            key=lambda a: (
                0 if app.store.is_alarm_active(a.get("id", 0)) else 1,
                a["hour"],
                a["minute"],
            ),
        )
        for alarm in alarms_sorted:
            card = AlarmCard(
                alarm,
                on_toggle=self._on_toggle,
                on_edit=self._on_edit,
                on_solve=self._solve_alarm,
                active=app.store.is_alarm_active(alarm.get("id", 0)),
            )
            self.alarm_grid.add_widget(card)

    def _on_toggle(self, alarm_id, value):
        App.get_running_app().store.update_alarm(alarm_id, {"enabled": value})

    def _on_edit(self, alarm):
        edit_screen = self.manager.get_screen("add_alarm")
        edit_screen.load_alarm(alarm)
        self.manager.current = "add_alarm"

    def _go_add(self):
        edit_screen = self.manager.get_screen("add_alarm")
        edit_screen.load_alarm(None)
        self.manager.current = "add_alarm"

    def _go_settings(self):
        self.manager.current = "settings"

    def _solve_alarm(self, alarm):
        app = App.get_running_app()
        if alarm and isinstance(alarm, dict):
            try:
                app.store.set_active_alarm(alarm)
                if hasattr(app, "scheduler"):
                    app.scheduler.set_active(alarm)
            except Exception:
                pass
        puzzle = self.manager.get_screen("puzzle")
        settings = app.store.get_settings()
        puzzle.start_session(
            alarm=alarm,
            player_score=app.store.get_score(),
            count=settings.get("puzzle_count", 3),
        )
        self.manager.current = "puzzle"

    def _test_puzzles(self):
        app = App.get_running_app()
        ps = self.manager.get_screen("puzzle")
        ps.start_session(
            alarm={},
            player_score=app.store.get_score(),
            count=None,
        )
        self.manager.current = "puzzle"
