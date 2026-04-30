"""
screens/settings.py — App settings screen.
"""

from kivy.uix.screenmanager import Screen
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.label import Label
from kivy.uix.button import Button
from kivy.uix.slider import Slider
from kivy.uix.switch import Switch
from kivy.uix.scrollview import ScrollView
from kivy.graphics import Color, RoundedRectangle
from kivy.app import App
from kivy.utils import platform
from kivy.logger import Logger

from utils.android_permissions import (
    has_android_exact_alarm_access,
    open_android_battery_settings,
    open_android_exact_alarm_settings,
    request_android_audio_permissions,
)

BG    = (0.07, 0.07, 0.10, 1)
CARD  = (0.12, 0.12, 0.17, 1)
AMBER = (1.00, 0.76, 0.22, 1)
WHITE = (0.95, 0.95, 0.97, 1)
GREY  = (0.55, 0.55, 0.60, 1)


def _bg(widget, color, radius=0):
    with widget.canvas.before:
        Color(*color)
        widget._bg_r = RoundedRectangle(pos=widget.pos, size=widget.size, radius=[radius])
    widget.bind(pos=lambda w, _: setattr(w._bg_r, 'pos', w.pos),
                size=lambda w, _: setattr(w._bg_r, 'size', w.size))


class SectionHeader(Label):
    def __init__(self, text, **kw):
        super().__init__(text=text, font_size="11sp", bold=True, color=AMBER,
                         font_name="DejaVuSans",
                         size_hint_y=None, height="28dp",
                         halign="left", valign="middle", **kw)
        self.bind(size=self.setter("text_size"))


class RowLabel(Label):
    def __init__(self, text, **kw):
        super().__init__(text=text, font_size="14sp", font_name="DejaVuSans", color=WHITE,
                         halign="left", valign="middle", **kw)
        self.bind(size=self.setter("text_size"))

class SettingsScreen(Screen):

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._build()

    def _build(self):
        root = BoxLayout(orientation="vertical")
        _bg(root, BG)

        # Header
        header = BoxLayout(size_hint_y=None, height="56dp",
                           padding=["12dp", "8dp"], spacing="8dp")
        _bg(header, (0.09, 0.09, 0.13, 1))
        back = Button(text="←", font_size="22sp", size_hint_x=None, width="44dp",
                      font_name="DejaVuSans",
                      background_normal="", background_color=(0, 0, 0, 0), color=AMBER)
        back.bind(on_release=lambda *_: setattr(self.manager, "current", "home"))
        htitle = Label(text="Settings", font_size="18sp", font_name="DejaVuSans", bold=True, color=WHITE)
        header.add_widget(back)
        header.add_widget(htitle)

        sv = ScrollView()
        content = BoxLayout(orientation="vertical", spacing="10dp",
                            padding="16dp", size_hint_y=None)
        content.bind(minimum_height=content.setter("height"))

        app = App.get_running_app()
        s = app.store.get_settings()

        # ── PUZZLE section ────────────────────────────────────────────────
        content.add_widget(SectionHeader(text="CHESS PUZZLES"))

        # Puzzle count
        count_card = BoxLayout(orientation="vertical", size_hint_y=None,
                               height="100dp", padding="12dp", spacing="4dp")
        _bg(count_card, CARD, radius=14)

        count_row = BoxLayout(orientation="horizontal", size_hint_y=None, height="28dp")
        count_row.add_widget(RowLabel(text="Puzzles to solve"))
        self.count_lbl = Label(
            text=str(s.get("puzzle_count", 3)),
            font_size="18sp", bold=True, color=AMBER,
            size_hint_x=None, width="40dp"
        )
        count_row.add_widget(self.count_lbl)

        self.count_slider = Slider(
            min=1, max=10, step=1, value=s.get("puzzle_count", 3),
            cursor_size=("20dp", "20dp"),
        )
        self.count_slider.bind(value=self._on_count)

        count_card.add_widget(count_row)
        count_card.add_widget(self.count_slider)

        score_card = BoxLayout(orientation="vertical", size_hint_y=None,
                               height="96dp", padding="12dp", spacing="6dp")
        _bg(score_card, CARD, radius=14)
        score_card.add_widget(RowLabel(
            text="Current score",
            size_hint_y=None,
            height="22dp",
        ))
        self.score_value_lbl = Label(
            text=str(app.store.get_score()),
            font_size="28sp",
            font_name="DejaVuSans",
            bold=True,
            color=AMBER,
            halign="left",
            valign="middle",
        )
        self.score_value_lbl.bind(size=self.score_value_lbl.setter("text_size"))
        score_note = Label(
            text="This changes when you solve, skip, or miss puzzles.",
            font_size="12sp",
            font_name="DejaVuSans",
            color=GREY,
            halign="left",
            valign="middle",
        )
        score_note.bind(size=score_note.setter("text_size"))
        score_card.add_widget(self.score_value_lbl)
        score_card.add_widget(score_note)

        content.add_widget(count_card)
        content.add_widget(score_card)

        # ── ALARM section ────────────────────────────────────────────────
        content.add_widget(SectionHeader(text="ALARM"))

        # Permissions / background access
        perm_card = BoxLayout(orientation="vertical", size_hint_y=None,
                              height="150dp", padding="12dp", spacing="8dp")
        _bg(perm_card, CARD, radius=14)
        perm_card.add_widget(RowLabel(
            text="Background & permissions",
            size_hint_y=None,
            height="22dp",
        ))
        perm_note = Label(
            text="Open the Android screens needed for alarms, battery, and ringtone access.",
            font_size="12sp", font_name="DejaVuSans", color=GREY,
            halign="left", valign="middle", size_hint_y=None, height="36dp"
        )
        perm_note.bind(size=perm_note.setter("text_size"))
        perm_card.add_widget(perm_note)

        self.perm_status = Label(
            text="Tap a button below to open the system screen.",
            font_size="11sp", font_name="DejaVuSans", color=GREY,
            halign="left", valign="middle", size_hint_y=None, height="22dp"
        )
        self.perm_status.bind(size=self.perm_status.setter("text_size"))
        perm_card.add_widget(self.perm_status)

        perm_row = BoxLayout(orientation="horizontal", spacing="8dp", size_hint_y=None, height="40dp")
        exact_btn = Button(
            text="Exact Alarms", font_size="12sp", font_name="DejaVuSans",
            background_normal="", background_color=(0, 0, 0, 0), color=AMBER
        )
        exact_btn.bind(on_release=lambda *_: self._request_exact_alarm_access())

        battery_btn = Button(
            text="Battery", font_size="12sp", font_name="DejaVuSans",
            background_normal="", background_color=(0, 0, 0, 0), color=WHITE
        )
        battery_btn.bind(on_release=lambda *_: self._request_battery_access())

        ringtone_btn = Button(
            text="Ringtone Access", font_size="12sp", font_name="DejaVuSans",
            background_normal="", background_color=(0, 0, 0, 0), color=WHITE
        )
        ringtone_btn.bind(on_release=lambda *_: self._request_ringtone_access())

        perm_row.add_widget(exact_btn)
        perm_row.add_widget(battery_btn)
        perm_row.add_widget(ringtone_btn)
        perm_card.add_widget(perm_row)
        content.add_widget(perm_card)

        # Volume
        vol_card = BoxLayout(orientation="vertical", size_hint_y=None,
                             height="100dp", padding="12dp", spacing="4dp")
        _bg(vol_card, CARD, radius=14)

        vol_row = BoxLayout(orientation="horizontal", size_hint_y=None, height="28dp")
        vol_row.add_widget(RowLabel(text="Volume"))
        self.vol_lbl = Label(
            text=f"{s.get('volume', 80)}%",
            font_size="16sp", font_name="DejaVuSans", color=AMBER, size_hint_x=None, width="50dp"
        )
        vol_row.add_widget(self.vol_lbl)
        self.vol_slider = Slider(min=0, max=100, step=5, value=s.get("volume", 80))
        self.vol_slider.bind(value=self._on_volume)

        vol_card.add_widget(vol_row)
        vol_card.add_widget(self.vol_slider)
        content.add_widget(vol_card)

        # Snooze
        snooze_card = BoxLayout(orientation="horizontal", size_hint_y=None,
                                height="56dp", padding="12dp", spacing="12dp")
        _bg(snooze_card, CARD, radius=14)
        snooze_card.add_widget(RowLabel(text="Allow snooze (5 min)"))
        snooze_sw = Switch(active=s.get("snooze_enabled", False))
        snooze_sw.bind(active=lambda inst, v:
                       App.get_running_app().store.set_setting("snooze_enabled", v))
        snooze_card.add_widget(snooze_sw)
        content.add_widget(snooze_card)

        # Vibrate
        vib_card = BoxLayout(orientation="horizontal", size_hint_y=None,
                             height="56dp", padding="12dp", spacing="12dp")
        _bg(vib_card, CARD, radius=14)
        vib_card.add_widget(RowLabel(text="Vibrate"))
        vib_sw = Switch(active=s.get("vibrate", True))
        vib_sw.bind(active=lambda inst, v:
                    App.get_running_app().store.set_setting("vibrate", v))
        vib_card.add_widget(vib_sw)
        content.add_widget(vib_card)

        preview_card = BoxLayout(orientation="vertical", size_hint_y=None,
                                 height="118dp", padding="12dp", spacing="8dp")
        _bg(preview_card, CARD, radius=14)
        preview_card.add_widget(RowLabel(
            text="Sound test",
            size_hint_y=None,
            height="22dp",
        ))

        preview_row = BoxLayout(orientation="horizontal", spacing="8dp")
        move_btn = Button(
            text="Test Move", font_size="13sp", font_name="DejaVuSans",
            background_normal="", background_color=(0, 0, 0, 0), color=WHITE
        )
        move_btn.bind(on_release=lambda *_: self._test_effect_sound("move.wav"))

        capture_btn = Button(
            text="Test Capture", font_size="13sp", font_name="DejaVuSans",
            background_normal="", background_color=(0, 0, 0, 0), color=WHITE
        )
        capture_btn.bind(on_release=lambda *_: self._test_effect_sound("capture.wav"))

        preview_row.add_widget(move_btn)
        preview_row.add_widget(capture_btn)
        preview_card.add_widget(preview_row)
        content.add_widget(preview_card)

        # ── INFO ──────────────────────────────────────────────────────────
        content.add_widget(SectionHeader(text="ABOUT"))
        info_card = BoxLayout(orientation="vertical", size_hint_y=None,
                              height="80dp", padding="12dp")
        _bg(info_card, CARD, radius=14)
        info_card.add_widget(Label(
            text="Puzzles powered by Lichess (lichess.org)\nCC0 Public Domain  •  ChessMate Alarm v1.0",
            font_size="12sp", font_name="DejaVuSans", color=GREY, halign="left", valign="middle"
        ))
        content.add_widget(info_card)

        sv.add_widget(content)
        root.add_widget(header)
        root.add_widget(sv)
        self.add_widget(root)

    def _on_count(self, slider, value):
        v = int(value)
        self.count_lbl.text = str(v)
        App.get_running_app().store.set_setting("puzzle_count", v)

    def _on_volume(self, slider, value):
        v = int(value)
        self.vol_lbl.text = f"{v}%"
        App.get_running_app().store.set_setting("volume", v)

    def on_pre_enter(self, *_):
        score = App.get_running_app().store.get_score()
        if hasattr(self, "score_value_lbl"):
            self.score_value_lbl.text = str(score)
        self._refresh_permission_status()

    def _refresh_permission_status(self):
        if not hasattr(self, "perm_status"):
            return
        if has_android_exact_alarm_access():
            self.perm_status.text = "Exact alarm access is enabled."
            self.perm_status.color = (0.65, 0.95, 0.65, 1)
        else:
            self.perm_status.text = "Exact alarm access is still needed."
            self.perm_status.color = GREY

    def _test_effect_sound(self, filename: str):
        app = App.get_running_app()
        volume = app.store.get_setting("volume", 80)
        app.sound_preview.play_effect(filename, volume=volume)

    def _request_exact_alarm_access(self):
        if platform != "android":
            return
        try:
            opened = open_android_exact_alarm_settings(force=True)
            self.perm_status.text = (
                "Exact alarms screen opened."
                if opened else "Could not open exact alarms screen."
            )
            self._refresh_permission_status()
        except Exception:
            self.perm_status.text = "Exact alarms request failed."
            Logger.exception("SettingsScreen: exact alarm prompt failed")

    def _request_battery_access(self):
        if platform != "android":
            return
        try:
            opened = open_android_battery_settings()
            self.perm_status.text = (
                "Battery settings opened."
                if opened else "Could not open battery settings."
            )
        except Exception:
            self.perm_status.text = "Battery request failed."
            Logger.exception("SettingsScreen: battery prompt failed")

    def _request_ringtone_access(self):
        if platform != "android":
            return
        try:
            opened = request_android_audio_permissions()
            self.perm_status.text = (
                "Ringtone permissions requested."
                if opened else "Could not request ringtone permissions."
            )
        except Exception:
            self.perm_status.text = "Ringtone permission request failed."
            Logger.exception("SettingsScreen: audio permission prompt failed")
