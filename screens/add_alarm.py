"""
screens/add_alarm.py — Create or edit an alarm.

load_alarm(None)  → new alarm mode  (title = "New Alarm",  button = "Save Alarm")
load_alarm(dict)  → edit mode       (title = "Edit Alarm", button = "Update Alarm")
"""

import os
from datetime import datetime

from kivy.uix.screenmanager import Screen
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.label import Label
from kivy.uix.button import Button
from kivy.uix.textinput import TextInput
from kivy.uix.scrollview import ScrollView
from kivy.uix.popup import Popup
from kivy.uix.filechooser import FileChooserListView
from kivy.clock import Clock
from kivy.graphics import Color, RoundedRectangle, Line
from kivy.app import App
from kivy.utils import platform
from kivy.logger import Logger
from utils.ringtones import default_ringtone_id, ringtone_choices
from utils.android_permissions import request_android_audio_permissions

BG    = (0.07, 0.07, 0.10, 1)
CARD  = (0.12, 0.12, 0.17, 1)
AMBER = (1.00, 0.76, 0.22, 1)
WHITE = (0.95, 0.95, 0.97, 1)
GREY  = (0.45, 0.45, 0.50, 1)

DAY_NAMES = ["Mo", "Tu", "We", "Th", "Fr", "Sa", "Su"]


def _bg(w, c, r=0):
    with w.canvas.before:
        Color(*c)
        w._bg_r = RoundedRectangle(pos=w.pos, size=w.size, radius=[r])
    w.bind(pos=lambda w, _: setattr(w._bg_r, 'pos', w.pos),
           size=lambda w, _: setattr(w._bg_r, 'size', w.size))


class TimeSpinner(BoxLayout):
    """Editable two-digit time field for hour or minute."""

    def __init__(self, value: int, min_val: int, max_val: int, **kw):
        super().__init__(orientation="vertical", size_hint=(None, None),
                         size=("90dp", "110dp"), **kw)
        self.min_val = min_val
        self.max_val = max_val
        self.value = min(max(value, min_val), max_val)

        self.input = TextInput(
            text=f"{self.value:02d}",
            multiline=False,
            input_filter="int",
            font_size="36sp",
            font_name="DejaVuSans",
            foreground_color=WHITE,
            background_color=(0.18, 0.18, 0.24, 1),
            cursor_color=AMBER,
            halign="center",
            size_hint_y=None,
            height="60dp",
        )
        self.input.bind(text=self._on_text, focus=self._on_focus)

        self.add_widget(BoxLayout(size_hint_y=0.25))
        self.add_widget(self.input)
        self.add_widget(BoxLayout(size_hint_y=0.25))

    def _on_text(self, instance, text):
        digits = "".join(ch for ch in text if ch.isdigit())[:2]
        if text != digits:
            instance.text = digits
            return
        if digits:
            self.value = int(digits)

    def _on_focus(self, instance, focused):
        if not focused:
            self._normalize()

    def _normalize(self):
        raw = "".join(ch for ch in self.input.text if ch.isdigit())
        if raw == "":
            self.value = self.min_val
        else:
            self.value = min(max(int(raw), self.min_val), self.max_val)
        self.input.text = f"{self.value:02d}"

    def set_value(self, value: int):
        self.value = min(max(int(value), self.min_val), self.max_val)
        self.input.text = f"{self.value:02d}"


class DayToggle(Button):
    def __init__(self, day_index: int, **kw):
        super().__init__(
            text=DAY_NAMES[day_index], font_size="13sp",
            font_name="DejaVuSans",
            size_hint=(None, None), size=("40dp", "40dp"),
            background_normal="", background_color=(0, 0, 0, 0), **kw
        )
        self.day_index = day_index
        self._active = False
        self._redraw()
        self.bind(on_release=lambda *_: self._toggle())
        self.bind(pos=lambda *_: self._redraw(), size=lambda *_: self._redraw())

    def _toggle(self):
        self._active = not self._active
        self._redraw()

    def _redraw(self):
        self.canvas.before.clear()
        with self.canvas.before:
            if self._active:
                Color(*AMBER)
                RoundedRectangle(pos=self.pos, size=self.size, radius=[20])
            else:
                Color(*GREY)
                Line(rounded_rectangle=[*self.pos, *self.size, 20], width=1)
        self.color = (0.05, 0.05, 0.08, 1) if self._active else GREY

    def set_active(self, value: bool):
        self._active = value
        self._redraw()

    @property
    def selected(self):
        return self._active


class AddAlarmScreen(Screen):

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._editing_id = None   # None = new alarm, int = editing existing
        self._ringtone_id = default_ringtone_id()
        self._ringtone_path = ""
        self._build()

    def _build(self):
        root = BoxLayout(orientation="vertical")
        _bg(root, BG)

        # ── header ────────────────────────────────────────────────────────
        header = BoxLayout(size_hint_y=None, height="56dp",
                           padding=["12dp", "8dp"], spacing="8dp")
        _bg(header, (0.09, 0.09, 0.13, 1))

        back = Button(
            text="Back", font_size="15sp",
            font_name="DejaVuSans",
            size_hint_x=None, width="60dp",
            background_normal="", background_color=(0, 0, 0, 0), color=AMBER
        )
        back.bind(on_release=lambda *_: self._cancel())

        self.header_title = Label(
            text="New Alarm", font_size="18sp", bold=True,
            font_name="DejaVuSans",
            color=WHITE
        )

        header.add_widget(back)
        header.add_widget(self.header_title)

        # ── scrollable content ────────────────────────────────────────────
        sv = ScrollView()
        content = BoxLayout(orientation="vertical", spacing="16dp",
                            padding="20dp", size_hint_y=None)
        content.bind(minimum_height=content.setter("height"))

        # ── time picker ───────────────────────────────────────────────────
        tp_card = BoxLayout(orientation="vertical", size_hint_y=None,
                            height="170dp", padding="12dp")
        _bg(tp_card, CARD, r=16)

        tp_title = Label(
            text="TIME", font_size="11sp", bold=True, color=AMBER,
            font_name="DejaVuSans",
            size_hint_y=None, height="20dp", halign="left"
        )
        tp_title.bind(size=tp_title.setter("text_size"))

        tp_row = BoxLayout(orientation="horizontal", spacing="0dp")
        tp_row.add_widget(BoxLayout())   # left spacer

        self.hour_spin   = TimeSpinner(7, 0, 23)
        self.minute_spin = TimeSpinner(0, 0, 59)

        colon = Label(
            text=":", font_size="36sp", bold=True, color=WHITE,
            font_name="DejaVuSans",
            size_hint=(None, None), size=("24dp", "110dp")
        )

        tp_row.add_widget(self.hour_spin)
        tp_row.add_widget(colon)
        tp_row.add_widget(self.minute_spin)
        tp_row.add_widget(BoxLayout())   # right spacer

        tp_card.add_widget(tp_title)
        tp_card.add_widget(tp_row)

        # ── label input ───────────────────────────────────────────────────
        label_card = BoxLayout(orientation="vertical", size_hint_y=None,
                               height="90dp", padding="12dp", spacing="8dp")
        _bg(label_card, CARD, r=16)

        label_title = Label(
            text="LABEL", font_size="11sp", bold=True, color=AMBER,
            font_name="DejaVuSans",
            size_hint_y=None, height="20dp", halign="left"
        )
        label_title.bind(size=label_title.setter("text_size"))

        self.label_input = TextInput(
            text="Good Morning!", multiline=False, font_size="15sp",
            font_name="DejaVuSans",
            foreground_color=WHITE,
            background_color=(0.18, 0.18, 0.24, 1),
            cursor_color=AMBER,
            size_hint_y=None, height="38dp",
        )
        label_card.add_widget(label_title)
        label_card.add_widget(self.label_input)

        # ── day repeat ────────────────────────────────────────────────────
        days_card = BoxLayout(orientation="vertical", size_hint_y=None,
                              height="110dp", padding="12dp", spacing="8dp")
        _bg(days_card, CARD, r=16)

        days_title = Label(
            text="REPEAT", font_size="11sp", bold=True, color=AMBER,
            font_name="DejaVuSans",
            size_hint_y=None, height="20dp", halign="left"
        )
        days_title.bind(size=days_title.setter("text_size"))

        days_row = BoxLayout(orientation="horizontal", spacing="6dp",
                             size_hint_y=None, height="50dp")
        self.day_toggles = [DayToggle(i) for i in range(7)]
        for dt in self.day_toggles:
            days_row.add_widget(dt)

        days_note = Label(
            text="No days = one-time alarm",
            font_size="10sp", color=GREY,
            font_name="DejaVuSans",
            size_hint_y=None, height="18dp", halign="left"
        )
        days_note.bind(size=days_note.setter("text_size"))

        days_card.add_widget(days_title)
        days_card.add_widget(days_row)
        days_card.add_widget(days_note)

        ringtone_card = BoxLayout(orientation="vertical", size_hint_y=None,
                                  height="118dp", padding="12dp", spacing="8dp")
        _bg(ringtone_card, CARD, r=16)

        ringtone_title = Label(
            text="RINGTONE", font_size="11sp", bold=True, color=AMBER,
            font_name="DejaVuSans",
            size_hint_y=None, height="20dp", halign="left"
        )
        ringtone_title.bind(size=ringtone_title.setter("text_size"))

        self.ringtone_value = Label(
            text="", font_size="14sp", color=WHITE,
            font_name="DejaVuSans",
            size_hint_y=None, height="24dp", halign="left", valign="middle"
        )
        self.ringtone_value.bind(size=self.ringtone_value.setter("text_size"))

        ringtone_row = BoxLayout(orientation="horizontal", size_hint_y=None,
                                 height="38dp", spacing="8dp")
        pick_default_btn = Button(
            text="Choose Tone", font_size="13sp", font_name="DejaVuSans",
            background_normal="", background_color=(0, 0, 0, 0), color=AMBER
        )
        pick_default_btn.bind(on_release=lambda *_: self._open_ringtone_picker())

        local_btn = Button(
            text="Choose File", font_size="13sp", font_name="DejaVuSans",
            background_normal="", background_color=(0, 0, 0, 0), color=WHITE
        )
        local_btn.bind(on_release=lambda *_: self._open_file_picker())

        ringtone_row.add_widget(pick_default_btn)
        ringtone_row.add_widget(local_btn)

        ringtone_card.add_widget(ringtone_title)
        ringtone_card.add_widget(self.ringtone_value)
        ringtone_card.add_widget(ringtone_row)

        # ── save / update button ──────────────────────────────────────────
        self.save_btn = Button(
            text="Save Alarm", font_size="17sp", bold=True,
            font_name="DejaVuSans",
            size_hint_y=None, height="56dp",
            background_normal="", background_color=(0, 0, 0, 0),
            color=(0.05, 0.05, 0.08, 1)
        )
        with self.save_btn.canvas.before:
            Color(*AMBER)
            self.save_btn._bg = RoundedRectangle(
                pos=self.save_btn.pos, size=self.save_btn.size, radius=[14]
            )
        self.save_btn.bind(
            pos=lambda w, _: setattr(w._bg, 'pos', w.pos),
            size=lambda w, _: setattr(w._bg, 'size', w.size)
        )
        self.save_btn.bind(on_release=lambda *_: self._save())

        # ── delete button (only shown in edit mode) ───────────────────────
        self.delete_btn = Button(
            text="Delete Alarm", font_size="15sp",
            font_name="DejaVuSans",
            size_hint_y=None, height="48dp",
            background_normal="", background_color=(0, 0, 0, 0),
            color=WHITE, opacity=0
        )
        with self.delete_btn.canvas.before:
            Color(0.75, 0.18, 0.18, 1)
            self.delete_btn._bg = RoundedRectangle(
                pos=self.delete_btn.pos, size=self.delete_btn.size, radius=[14]
            )
        self.delete_btn.bind(
            pos=lambda w, _: setattr(w._bg, 'pos', w.pos),
            size=lambda w, _: setattr(w._bg, 'size', w.size)
        )
        self.delete_btn.bind(on_release=lambda *_: self._delete())

        content.add_widget(tp_card)
        content.add_widget(label_card)
        content.add_widget(days_card)
        content.add_widget(ringtone_card)
        content.add_widget(self.save_btn)
        content.add_widget(self.delete_btn)

        sv.add_widget(content)
        root.add_widget(header)
        root.add_widget(sv)
        self.add_widget(root)

    # ── public: called by HomeScreen ──────────────────────────────────────

    def load_alarm(self, alarm):
        """
        Pass alarm=None for new alarm, or an alarm dict to edit it.
        """
        if alarm is None:
            # ── new alarm mode ────────────────────────────────────────────
            self._editing_id = None
            self.header_title.text = "New Alarm"
            self.save_btn.text = "Save Alarm"
            self.delete_btn.opacity = 0
            self.delete_btn.disabled = True
            # Reset to defaults
            self.hour_spin.set_value(7)
            self.minute_spin.set_value(0)
            self.label_input.text = "Good Morning!"
            self._ringtone_id = default_ringtone_id()
            self._ringtone_path = ""
            self._refresh_ringtone_text()
            for dt in self.day_toggles:
                dt.set_active(False)
        else:
            # ── edit mode ─────────────────────────────────────────────────
            self._editing_id = alarm["id"]
            self.header_title.text = "Edit Alarm"
            self.save_btn.text = "Update Alarm"
            self.delete_btn.opacity = 1
            self.delete_btn.disabled = False
            # Populate fields from alarm
            self.hour_spin.set_value(alarm["hour"])
            self.minute_spin.set_value(alarm["minute"])
            self.label_input.text = alarm.get("label", "Alarm")
            self._ringtone_id = alarm.get("ringtone_id", default_ringtone_id())
            self._ringtone_path = alarm.get("ringtone_path", "")
            self._refresh_ringtone_text()
            selected_days = alarm.get("days", [])
            for dt in self.day_toggles:
                dt.set_active(dt.day_index in selected_days)

    # ── private ───────────────────────────────────────────────────────────

    def _save(self):
        app = App.get_running_app()
        selected_days = [dt.day_index for dt in self.day_toggles if dt.selected]
        data = {
            "hour":    self.hour_spin.value,
            "minute":  self.minute_spin.value,
            "label":   self.label_input.text.strip() or "Alarm",
            "days":    selected_days,
            "enabled": True,
            "ringtone_id": self._ringtone_id,
            "ringtone_path": self._ringtone_path,
        }

        if self._editing_id is None:
            # New alarm
            app.store.add_alarm(data)
        else:
            # Update existing
            app.store.update_alarm(self._editing_id, data)

        self.manager.current = "home"

    def _delete(self):
        if self._editing_id is not None:
            App.get_running_app().store.delete_alarm(self._editing_id)
        self.manager.current = "home"

    def _cancel(self):
        self.manager.current = "home"

    def _refresh_ringtone_text(self):
        if self._ringtone_path:
            self.ringtone_value.text = f"Local file: {os.path.basename(self._ringtone_path)}"
            return
        for ringtone in ringtone_choices():
            if ringtone["id"] == self._ringtone_id:
                self.ringtone_value.text = f"Default: {ringtone['label']}"
                return
        self.ringtone_value.text = "Default: Device Alarm Tone"

    def _open_ringtone_picker(self):
        content = BoxLayout(orientation="vertical", spacing="8dp", padding="12dp")
        for ringtone in ringtone_choices():
            btn = Button(
                text=ringtone["label"],
                font_size="14sp",
                font_name="DejaVuSans",
                background_normal="",
                background_color=(0.18, 0.18, 0.24, 1),
                color=WHITE,
                size_hint_y=None,
                height="44dp",
            )
            btn.bind(on_release=lambda _, rid=ringtone["id"]: self._select_default_ringtone(rid))
            content.add_widget(btn)

        popup = Popup(
            title="Choose Alarm Tone",
            content=content,
            size_hint=(0.86, 0.55),
            title_font="DejaVuSans",
        )
        self._ringtone_popup = popup
        popup.open()

    def _select_default_ringtone(self, ringtone_id: str):
        self._ringtone_id = ringtone_id
        self._ringtone_path = ""
        self._refresh_ringtone_text()
        if hasattr(self, "_ringtone_popup"):
            self._ringtone_popup.dismiss()

    def _open_file_picker(self):
        if platform == "android":
            request_android_audio_permissions()
        chooser = FileChooserListView(
            path=self._default_file_picker_path(),
            filters=["*.mp3", "*.wav", "*.ogg", "*.m4a", "*.flac", "*.aac"],
            font_name="DejaVuSans",
        )
        controls = BoxLayout(orientation="horizontal", size_hint_y=None, height="44dp", spacing="8dp")
        choose_btn = Button(
            text="Use Selected", font_name="DejaVuSans",
            background_normal="", background_color=(0.18, 0.18, 0.24, 1), color=AMBER
        )
        cancel_btn = Button(
            text="Cancel", font_name="DejaVuSans",
            background_normal="", background_color=(0.18, 0.18, 0.24, 1), color=WHITE
        )
        content = BoxLayout(orientation="vertical", spacing="8dp", padding="12dp")
        controls.add_widget(choose_btn)
        controls.add_widget(cancel_btn)
        content.add_widget(chooser)
        content.add_widget(controls)

        popup = Popup(
            title="Choose Local Ringtone",
            content=content,
            size_hint=(0.94, 0.88),
            title_font="DejaVuSans",
        )
        choose_btn.bind(on_release=lambda *_: self._select_local_ringtone(chooser.selection, popup))
        cancel_btn.bind(on_release=lambda *_: popup.dismiss())
        popup.open()

    def _select_local_ringtone(self, selection, popup):
        if selection:
            self._ringtone_path = selection[0]
            self._ringtone_id = default_ringtone_id()
            self._refresh_ringtone_text()
        popup.dismiss()

    def _default_file_picker_path(self):
        candidates = []
        if platform == "android":
            candidates.extend([
                "/storage/emulated/0/Music",
                "/storage/emulated/0/Download",
                "/storage/emulated/0",
            ])
        candidates.extend([
            os.path.expanduser("~"),
            os.path.dirname(__file__),
        ])
        for path in candidates:
            if path and os.path.exists(path):
                return path
        return os.path.expanduser("~")
