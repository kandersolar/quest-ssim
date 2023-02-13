"""Storage Sizing and Placement Kivy application"""
from contextlib import ExitStack
import itertools
import os
import re

from importlib_resources import files, as_file

from ssim.metrics import ImprovementType, Metric, MetricTimeAccumulator

import kivy
from kivymd.app import MDApp
from ssim.ui import Project, StorageOptions, is_valid_opendss_name
from kivy.logger import Logger, LOG_LEVELS
from kivy.uix.floatlayout import FloatLayout
from kivymd.uix.list import IRightBodyTouch, ILeftBodyTouch, TwoLineAvatarIconListItem, OneLineAvatarIconListItem
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.screenmanager import Screen, ScreenManager
from kivy.properties import ObjectProperty, StringProperty, NumericProperty
from kivy.uix.popup import Popup
from kivy.uix.boxlayout import BoxLayout
from kivy.core.text import LabelBase
from kivy.clock import Clock
from kivy.uix.behaviors import FocusBehavior
from kivymd.uix.menu import MDDropdownMenu
from kivymd.uix.button import MDFlatButton, MDRectangleFlatIconButton
from kivymd.uix.list import OneLineListItem
from kivy.uix.recycleview import RecycleView
from kivy.uix.recycleboxlayout import RecycleBoxLayout
from kivy.uix.recycleview.views import RecycleDataViewBehavior
from kivy.uix.scrollview import ScrollView

from kivymd.app import MDApp
from kivymd.uix.list import (
    TwoLineAvatarIconListItem,
    TwoLineIconListItem,
    ILeftBodyTouch,
    OneLineRightIconListItem,
    MDList
)
from kivymd.uix.selectioncontrol import MDCheckbox
from kivymd.uix.textfield import MDTextField

import tomli

from ssim.ui import Project, StorageOptions, is_valid_opendss_name

_FONT_FILES = {
    "exo_regular": "Exo2-Regular.ttf",
    "exo_bold": "Exo2-Bold.ttf",
    "exo_italic": "Exo2-Italic.ttf",
    "opensans_regular": "OpenSans-Regular.ttf",
    "opensans_bold": "OpenSans-Bold.ttf",
    "opensans_italic": "OpenSans-Italic.ttf"
}


_IMAGE_FILES = [
    "button_down.png", "button_normal.png", "gray.png", "white.png"
]


_KV_FILES = ["common.kv", "ssim.kv"]


def parse_float(strval):
    try:
        return float(strval)
    except ValueError:
        return None


class SSimApp(MDApp):

    def __init__(self, *args, **kwargs):
        self.project = Project("unnamed")
        super().__init__(*args, **kwargs)

    def build(self):

        screen_manager = ScreenManager()
        screen_manager.add_widget(SSimScreen(self.project, name="ssim"))
        screen_manager.add_widget(
            DERConfigurationScreen(self.project, name="der-config"))
        screen_manager.add_widget(
            LoadConfigurationScreen(self.project, name="load-config"))
        screen_manager.add_widget(
            MetricConfigurationScreen(self.project, name="metric-config"))
        screen_manager.add_widget(
            RunSimulationScreen(self.project, name="run-sim"))
        screen_manager.current = "ssim"

        return screen_manager

class SSimBaseScreen(Screen):
    """Base class for screens that holds the fundamental ssim data structures.

    Attributes:
        project : :py:class:`ssim.ui.Project`

    Parameters
    ----------
    project : ssim.ui.Project
        Project object where the simulation configuration is being constructed.
    """

    def __init__(self, project, *args, **kwargs):
        self.project = project
        super().__init__(*args, **kwargs)

class LeftCheckBox(ILeftBodyTouch, MDCheckbox):
    pass

class BusListItem(TwoLineIconListItem):

    def __init__(self, busname, busphases, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.text = busname
        self.secondary_text = str(busphases)

    def mark(self, check, the_list_item):
        """mark the task as complete or incomplete"""
        if check.active:
            self.parent.parent.parent.add_bus(the_list_item)
        else:
            self.parent.parent.parent.remove_bus(the_list_item)

    @property
    def active(self):
        return self.ids.selected.active

class TextFieldFloat(MDTextField):
    SIMPLE_FLOAT = re.compile(r"(\+|-)?\d*(\.\d*)?$")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper_text_mode = "on_focus"
        self.helper_text = "Input value and press enter"

    def text_valid(self):
        return TextFieldFloat.SIMPLE_FLOAT.match(self.text) is not None

    def set_text(self, instance, value):
        if value == "":
            return
        self.set_error_message()

    def set_error_message(self):
        if not self.text_valid():
            self.error = True
            self.helper_text = "You must enter a number."
        else:
            self.error = False
            self.helper_text = "Input value and press enter"

class TextFieldMultiFloat(MDTextField):
    SIMPLE_FLOAT = re.compile(r"(\+|-)?\d*(\.\d*)?$")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper_text_mode = "on_focus"
        self.helper_text = "Input numeric value"

    def text_valid(self):
        return TextFieldMultiFloat.SIMPLE_FLOAT.match(self.text) is not None

    def set_text(self, instance, value):
        if value == "":
            return
        self.set_error_message()

    def set_varied_mode(self):
        self.text = ""
        self.helper_text = "Multiple varied values"
        self.error = False

    def set_not_set_mode(self):
        self.text = ""
        self.helper_text = "No values set"
        self.error = False

    def set_error_message(self):
        if not self.text_valid():
            self.error = True
            self.helper_text = "You must enter a number."
        else:
            self.error = False
            self.helper_text = "Input numeric value"

class TextFieldPositiveFloat(MDTextField):
    POSITIVE_FLOAT = re.compile(r"\d*(\.\d*)?$")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper_text_mode = "on_focus"
        self.helper_text = "Input value and press enter"

    def text_valid(self):
        return TextFieldPositiveFloat.POSITIVE_FLOAT.match(self.text) is not None

    def set_text(self, instance, value):
        if value == "":
            return
        self.set_error_message()

    def set_error_message(self):
        if not self.text_valid():
            self.error = True
            self.helper_text = "You must enter a non-negative number."
        else:
            self.error = False
            self.helper_text = "Input value and press enter"

class TextFieldPositivePercentage(MDTextField):
    POSITIVE_FLOAT = re.compile(r"\d*(\.\d*)?$")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper_text_mode = "on_focus"
        self.helper_text = "Input percentage value (0-100)"

    def text_valid(self):
        if TextFieldPositivePercentage.POSITIVE_FLOAT.match(self.text) is None:
            return False

        value = float(self.text)
        if value < 0.0: return False
        if value > 100: return False
        return True

    def set_text(self, instance, value):
        if value == "":
            return
        self.set_error_message()

    def set_error_message(self):
        if not self.text_valid():
            self.error = True
            self.helper_text = "You must enter a value between 0 and 100."
        else:
            self.error = False
            self.helper_text = "Input percentage value"

    def percentage(self):
        return float(self.text)

    def fraction(self):
        return self.percentage() / 100.0

class EditableSetList(MDList):
    options = ObjectProperty(set())

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.bind(
            options=self._update_display
        )

    def _update_display(self, instance, options):
        self.clear_widgets()
        for item in sorted(options):
            self.add_widget(
                EditableSetListItem(item, text=str(item))
            )

    def add_item(self, item):
        """Add an item to the set."""
        self.options = self.options.union(set([item]))

    def remove_item(self, item):
        """Remove an item from the set."""
        # Don't use set.remove() since we must return a new object
        # to trigger the _update_display callback throug kivy
        self.options = self.options - set([item])

class EditableSetListItem(OneLineRightIconListItem):
    """List item with one line and a delete button"""

    def __init__(self, item, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._value = item
        self.ids.delete.bind(
            on_release=self._delete_item
        )

    def _delete_item(self, item):
        self.parent.remove_item(self._value)

class TextFieldOpenDSSName(MDTextField):
    """Text field that enforces OpenDSS name requirements."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def text_valid(self):
        return is_valid_opendss_name(self.text)

    def set_text(self, instance, value):
        if value == "":
            self.error = True
        else:
            self.set_error_message()

    def set_error_message(self):
        if not self.text_valid():
            self.error = True
        else:
            self.error = False

class StorageConfigurationScreen(SSimBaseScreen):
    """Configure a single energy storage device."""

    def __init__(self, der_screen, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._der_screen = der_screen
        self.ids.power_input.bind(
            on_text_validate=self._add_device_power
        )
        self.ids.duration_input.bind(
            on_text_validate=self._add_device_duration
        )
        self.ids.device_name.bind(
            on_text_validate=self._check_name
        )
        self.options = None
        self._editing = None

    @classmethod
    def edit(cls, der_screen, ess: StorageOptions, project):
        screen = cls(der_screen, name="configure-storage", project=project)
        screen._editing = ess
        for power in ess.power:
            screen.ids.power_list.add_item(power)
        for duration in ess.duration:
            screen.ids.duration_list.add_item(duration)
        screen.ids.device_name.text = ess.name
        for bus_list_item in screen.ids.bus_list.children:
            if bus_list_item.text in ess.busses:
                bus_list_item.ids.selected.active = True
        screen.ids.required.active = ess.required
        return screen

    def on_kv_post(self, base_widget):
        self.ids.bus_list.clear_widgets()
        for bus in self.project.bus_names:
            bus_list_item = BusListItem(bus, self.project.phases(bus))
            self.ids.bus_list.add_widget(bus_list_item)

    def _check_name(self, textfield):
        if not textfield.text_valid():
            textfield.helper_text = "invalid name"
            textfield.error = True
            return False
        existing_names = {name.lower() for name in self.project.storage_names}
        if textfield.text.lower() in existing_names:
            textfield.helper_text = "Name already exists"
            textfield.error = True
            return False
        textfield.error = False
        return True

    def _add_option(self, optionlist, textfield):
        if textfield.text_valid():
            value = float(textfield.text)
            optionlist.add_item(value)
            textfield.text = ""
            Clock.schedule_once(lambda dt: self._refocus_field(textfield), 0.05)
        else:
            textfield.set_error_message()

    def _refocus_field(self, textfield):
        textfield.focus = True

    def _add_device_duration(self, textfield):
        self._add_option(self.ids.duration_list, textfield)

    def _add_device_power(self, textfield):
        self._add_option(self.ids.power_list, textfield)

    @property
    def _ess_powers(self):
        return list(self.ids.power_list.options)

    @property
    def _ess_durations(self):
        return list(self.ids.duration_list.options)

    @property
    def _selected_busses(self):
        return list(
            bus_item.text
            for bus_item in self.ids.bus_list.children
            if bus_item.active
        )

    def edit_control_params(self):
        self._record_option_data()

        self.manager.add_widget(
            StorageControlConfigurationScreen(
                self, self.project, self.options, name="configure-storage-controls"
            )
        )

        self.manager.current = "configure-storage-controls"

    def _record_option_data(self) -> StorageOptions:

        if self.options:
            self.options.power = self._ess_powers
            self.options.duration = self._ess_durations
            self.options.busses = self._selected_busses
            self.options.required = self.ids.required.active
            self.options.name = self.ids.device_name.text
            self.options.phases = 3
        else:
            self.options = StorageOptions(
                self.ids.device_name.text,
                3,
                self._ess_powers,
                self._ess_durations,
                self._selected_busses,
                required=self.ids.required.active
            )

    def __show_invalid_input_values_popup(self, msg):
        content = MessagePopupContent()

        popup = Popup(
            title='Invalid Storage Input', content=content, auto_dismiss=False,
            size_hint=(0.4, 0.4)
            )
        content.ids.msg_label.text = str(msg)
        content.ids.dismissBtn.bind(on_press=popup.dismiss)
        popup.open()
        return

    def show_error(self, msg):
        if msg:
            self.__show_invalid_input_values_popup(msg)
            return True

        return False

    def save(self):
        self._record_option_data()

        if not self.options.valid:
            Logger.error(
                "invalid storage configuration - "
                f"name: {self.options.name}, "
                f"powers: {self.options.power}, "
                f"durations: {self.options.duration}, "
                f"busses: {self.options.busses}"
            )

        if self.show_error(self.options.validate_name()): return
        if self.show_error(self.options.validate_soc_values()): return
        if self.show_error(self.options.validate_power_values()):  return
        if self.show_error(self.options.validate_duration_values()): return
        if self.show_error(self.options.validate_busses()): return

        self._der_screen.add_ess(self.options)
        self.manager.current = "der-config"
        self.manager.remove_widget(self)

    def cancel(self):
        if self._editing is not None:
            # Restore the original device
            self._der_screen.add_ess(self._editing)
        self.manager.current = "der-config"
        self.manager.remove_widget(self)

    def on_enter(self, *args):
        return super().on_enter(*args)

class XYGridView(RecycleView):

    def extract_x_vals(self) -> list:
        return [float(child.x_value) for child in self.children[0].children]

    def extract_y_vals(self) -> list:
        return [float(child.y_value) for child in self.children[0].children]

class XYGridViewLayout(FocusBehavior, RecycleBoxLayout):
    pass

class XYGridViewItem(RecycleDataViewBehavior, BoxLayout):
    index = NumericProperty()

    @property
    def x_value(self) -> float:
        return float(self.ids.x_field.text)

    @property
    def y_value(self) -> float:
        return float(self.ids.y_field.text)

    def refresh_view_attrs(self, rv, index, data):
        self.index = index
        self.ids.x_field.text = str(data['x'])
        self.ids.y_field.text = str(data['y'])

    def on_delete_button(self):
        self.parent.parent.data.pop(self.index)

class XYGridHeader(BoxLayout):

    grid = ObjectProperty(None)

    def on_add_button(self):
        self.grid.data.append({'x': 1.0, 'y': 1.0})


class StorageControlConfigurationScreen(SSimBaseScreen):
    """Configure the control strategy of a single energy storage device."""
    def __init__(self, der_screen, config, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._der_screen = der_screen
        self._options = args[0]

        self.ids.min_soc.text = str(self._options.min_soc*100.0)
        self.ids.max_soc.text = str(self._options.max_soc*100.0)
        self.ids.init_soc.text = str(self._options.initial_soc*100.0)

        self._param_field_map = {}

        Clock.schedule_once(lambda dt: self.__set_focus_clear_sel(self.ids.max_soc), 0.05)
        Clock.schedule_once(lambda dt: self.__set_focus_clear_sel(self.ids.min_soc), 0.05)
        Clock.schedule_once(lambda dt: self.__set_focus_clear_sel(self.ids.init_soc), 0.05)

        self._def_btn_color = '#005376'

        if not self._options is None:
            if self._options.control.mode == "droop":
                self.set_droop_mode()
            elif self._options.control.mode == "voltvar":
                self.set_volt_var_mode()
            elif self._options.control.mode == "voltwatt":
                self.set_volt_watt_mode()
            elif self._options.control.mode == "varwatt":
                self.set_var_watt_mode()
            elif self._options.control.mode == "vv_vw":
                self.set_volt_var_and_volt_watt_mode()
            elif self._options.control.mode == "constantpf":
                self.set_const_power_factor_mode()
            else:
                self.set_droop_mode()

    @staticmethod
    def __set_focus_clear_sel(widget, value = True):
        widget.focus = value
        Clock.schedule_once(lambda dt: widget.cancel_selection(), 0.05)

    def set_mode_label_text(self):
        self.ids.mode_label.text = "Select a control mode for this storage asset: [b]" +\
            self.device_name + "[/b]"

    @property
    def device_name(self):
        return "" if self._options is None else self._options.name

    def set_droop_mode(self):
        self.set_mode("droop", self.ids.droop_mode)
        self.verify_control_param("p_droop", 500)
        self.verify_control_param("q_droop", -300)

        pfield = TextFieldFloat(
            hint_text="P Droop", text=str(self._options.control.params["p_droop"])
            )
        qfield = TextFieldFloat(
            hint_text="Q Droop", text=str(self._options.control.params["q_droop"])
            )
        self.ids.param_box.add_widget(pfield)
        self.ids.param_box.add_widget(qfield)
        self.ids.param_box.add_widget(BoxLayout(size_hint=(1.0, 0.8)))

        self._param_field_map.clear()
        self._param_field_map["p_droop"] = pfield
        self._param_field_map["q_droop"] = qfield

        Clock.schedule_once(lambda dt: self.__set_focus_clear_sel(pfield), 0.05)
        Clock.schedule_once(lambda dt: self.__set_focus_clear_sel(qfield), 0.05)

    def set_volt_var_mode(self):
        self.set_mode("voltvar", self.ids.vv_mode)
        self.verify_control_param("volt_vals", [0.5, 0.95, 1.0, 1.05, 1.5])
        self.verify_control_param("var_vals", [1.0, 1.0, 0.0, -1.0, -1.0])

        headers = self.make_xy_header("Voltage (p.u.)", "Reactive Power (kVAR)")
        vvs = self._options.control.params["volt_vals"]
        var = self._options.control.params["var_vals"]

        view = self.make_xy_grid(vvs, var)
        self.ids.voltvargrid = view
        headers.grid = view

        self.ids.param_box.add_widget(headers)
        self.ids.param_box.add_widget(view)

    def set_volt_watt_mode(self):
        self.set_mode("voltwatt", self.ids.vw_mode)
        self.verify_control_param("volt_vals", [0.5, 0.95, 1.0, 1.05, 1.5])
        self.verify_control_param("watt_vals", [1.0, 1.0, 0.0, -1.0, -1.0])

        headers = self.make_xy_header("Voltage (p.u.)", "Watts (kW)")
        vvs = self._options.control.params["volt_vals"]
        wvs = self._options.control.params["watt_vals"]

        view = self.make_xy_grid(vvs, wvs)
        self.ids.voltwattgrid = view
        headers.grid = view

        self.ids.param_box.add_widget(headers)
        self.ids.param_box.add_widget(view)

    def set_var_watt_mode(self):
        self.set_mode("varwatt", self.ids.var_watt_mode)
        self.verify_control_param("var_vals", [0.5, 0.95, 1.0, 1.05, 1.5])
        self.verify_control_param("watt_vals", [1.0, 1.0, 0.0, -1.0, -1.0])

        headers = self.make_xy_header("Reactive Power (kVAR)", "Watts (kW)")
        vvs = self._options.control.params["var_vals"]
        wvs = self._options.control.params["watt_vals"]

        view = self.make_xy_grid(vvs, wvs)
        self.ids.varwattgrid = view
        headers.grid = view

        self.ids.param_box.add_widget(headers)
        self.ids.param_box.add_widget(view)

    def set_volt_var_and_volt_watt_mode(self):
        self.set_mode("vv_vw", self.ids.vv_vw_mode)
        self.verify_control_param("vv_volt_vals", [0.5, 0.95, 1.0, 1.05, 1.5])
        self.verify_control_param("vw_volt_vals", [0.5, 0.95, 1.0, 1.05, 1.5])
        self.verify_control_param("var_vals", [1.0, 1.0, 0.0, -1.0, -1.0])
        self.verify_control_param("watt_vals", [1.0, 1.0, 0.0, -1.0, -1.0])

        vvheaders = self.make_xy_header("Voltage (p.u.)", "Reactive Power (kVAR)", (1.0, 0.07))
        vwheaders = self.make_xy_header("Voltage (p.u.)", "Watts (kW)", (1.0, 0.07))

        vvvs = self._options.control.params["vv_volt_vals"]
        vars = self._options.control.params["var_vals"]
        vwvs = self._options.control.params["vw_volt_vals"]
        watts = self._options.control.params["watt_vals"]

        vvview = self.make_xy_grid(vvvs, vars, (1.0, 0.93))
        self.ids.voltvargrid = vvview
        vvheaders.grid = vvview

        vwview = self.make_xy_grid(vwvs, watts, (1.0, 0.93))
        self.ids.voltwattgrid = vwview
        vwheaders.grid = vwview

        self.vwdata = vwview.data

        innerBox = BoxLayout(orientation="horizontal")
        self.ids.param_box.add_widget(innerBox)

        vvBox = BoxLayout(orientation="vertical")
        vwBox = BoxLayout(orientation="vertical")

        innerBox.add_widget(vvBox)
        innerBox.add_widget(vwBox)

        vvBox.add_widget(vvheaders)
        vvBox.add_widget(vvview)

        vwBox.add_widget(vwheaders)
        vwBox.add_widget(vwview)

    def set_const_power_factor_mode(self):
        self.set_mode("constantpf", self.ids.const_pf_mode)
        self.verify_control_param("pf_val", 0.99)

        pffield = TextFieldPositiveFloat(
            hint_text="Power Factor Value", text=str(self._options.control.params["pf_val"])
            )
        self.ids.param_box.add_widget(pffield)
        self.ids.param_box.add_widget(BoxLayout(size_hint=(1.0, 0.8)))

        self._param_field_map.clear()
        self._param_field_map["pf_val"] = pffield

        Clock.schedule_once(lambda dt: self.__set_focus_clear_sel(pffield), 0.05)

    def verify_control_param(self, label: str, def_val):
        if label not in self._options.control.params:
            self._options.control.params[label] = def_val

    def make_xy_grid(self, xs: list, ys: list, size_hint=(0.5, 0.93)) -> XYGridView:
        view = XYGridView(size_hint=size_hint)
        xs, ys = (list(t) for t in zip(*sorted(zip(xs, ys))))
        dat = [{'x': xs[i], 'y': ys[i]} for i in range(len(xs))]
        view.data = dat
        return view

    def make_xy_header(self, xlabel: str, ylabel: str, size_hint=(0.5, 0.07)) -> XYGridHeader:
        headers = XYGridHeader(size_hint=size_hint)
        headers.ids.x_label.text = xlabel
        headers.ids.y_label.text = ylabel
        return headers

    def set_mode(self, name, button) -> bool:
        self.manage_button_selection_states(button)
        self.ids.param_box.clear_widgets()
        if self._options.control.mode == name: return False
        self._options.control.mode = name
        self._options.control.params.clear()
        return True

    def manage_button_selection_states(self, selbutton):
        self.ids.droop_mode.md_bg_color =\
            "red" if selbutton is self.ids.droop_mode else self._def_btn_color
        self.ids.vv_mode.md_bg_color =\
            "red" if selbutton is self.ids.vv_mode else self._def_btn_color
        self.ids.vw_mode.md_bg_color =\
            "red" if selbutton is self.ids.vw_mode else self._def_btn_color
        self.ids.var_watt_mode.md_bg_color =\
            "red" if selbutton is self.ids.var_watt_mode else self._def_btn_color
        self.ids.vv_vw_mode.md_bg_color =\
            "red" if selbutton is self.ids.vv_vw_mode else self._def_btn_color
        self.ids.const_pf_mode.md_bg_color =\
            "red" if selbutton is self.ids.const_pf_mode else self._def_btn_color

    def save(self):
        self._options.min_soc = self.ids.min_soc.fraction()
        self._options.max_soc = self.ids.max_soc.fraction()
        self._options.initial_soc = self.ids.init_soc.fraction()

        self._options.control.params.clear()

        for key in self._param_field_map:
            self._options.control.params[key] =\
                float(self._param_field_map[key].text)

        if self._options.control.mode == "voltvar":
            self.__extract_data_lists(self.ids.voltvargrid, "volt_vals", "var_vals")

        if self._options.control.mode == "voltwatt":
            self.__extract_data_lists(self.ids.voltwattgrid, "volt_vals", "watt_vals")

        if self._options.control.mode == "varwatt":
            self.__extract_data_lists(self.ids.varwattgrid, "var_vals", "watt_vals")

        if self._options.control.mode == "vv_vw":
            self.__extract_data_lists(self.ids.voltvargrid, "vv_volt_vals", "var_vals")
            self.__extract_data_lists(self.ids.voltwattgrid, "vw_volt_vals", "watt_vals")

        self.manager.current = "configure-storage"
        self.manager.remove_widget(self)

    def cancel(self):
        self.manager.current = "configure-storage"
        self.manager.remove_widget(self)

    def __extract_data_lists(self, xyc: XYGridView, l1name, l2name):
        xl = xyc.extract_x_vals()
        yl = xyc.extract_y_vals()

        xl, yl = (list(t) for t in zip(*sorted(zip(xl, yl))))

        self._options.control.params[l1name] = xl
        self._options.control.params[l2name] = yl

class PVConfigurationScreen(SSimBaseScreen):
    """Configure a single PV system."""

    def __init__(self, *args, **kwargs):
        self.pvsystem = None
        super().__init__(*args, **kwargs)

    def save(self):
        # TODO add the new storage device to the project
        self.manager.current = "der-config"

    def cancel(self):
        self.manager.current = "der-config"

class DERConfigurationScreen(SSimBaseScreen):
    """Configure energy storage devices and PV generators."""

    def __init__(self, *args, **kwargs):
        # comes first so the manager is initialized
        super().__init__(*args, **kwargs)
        self.ids.delete_storage.bind(
            on_release=self.delete_ess
        )


    def load_project_data(self):
        self.ids.ess_list.clear_widgets()
        for so in self.project.storage_devices:
            self.ids.ess_list.add_widget(
                StorageListItem(so, self)
            )

    def new_storage(self):
        self.manager.add_widget(
            StorageConfigurationScreen(
                self, self.project, name="configure-storage")
        )

        self.manager.current = "configure-storage"

    def add_ess(self, ess):
        self.project.add_storage_option(ess)
        self.ids.ess_list.add_widget(
            StorageListItem(ess, self)
        )

    def delete_ess(self, button):
        to_remove = []
        for ess_list_item in self.ids.ess_list.children:
            if ess_list_item.selected:
                to_remove.append(ess_list_item)
                self.project.remove_storage_option(ess_list_item.ess)
        for widget in to_remove:
            self.ids.ess_list.remove_widget(widget)

    def on_pre_enter(self, *args):
        if self.project.grid_model is None:
            _show_no_grid_popup("ssim", self.manager)
        return super().on_pre_enter(*args)

    def edit_storage(self, ess_list_item):
        ess = ess_list_item.ess
        # Remove from the list so it can be re-added after editing
        self.project.remove_storage_option(ess)
        self.ids.ess_list.remove_widget(ess_list_item)
        self.manager.add_widget(
            StorageConfigurationScreen.edit(self, ess, self.project))
        self.manager.current = "configure-storage"


class StorageListItem(TwoLineAvatarIconListItem):
    def __init__(self, ess, der_screen, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.ess = ess
        self.text = ess.name
        self.secondary_text = str(ess.power)
        self.ids.edit.bind(
            on_release=self.edit
        )
        self._der_screen = der_screen

    @property
    def selected(self):
        return self.ids.selected.active

    def edit(self, icon_widget):
        self._der_screen.edit_storage(self)

class LoadConfigurationScreen(SSimBaseScreen):
    pass

class NoGridPopupContent(BoxLayout):
    pass

class NoGridPopupContent(BoxLayout):
    pass

class MissingMetricValuesPopupContent(BoxLayout):
    pass

class MessagePopupContent(BoxLayout):
    pass

class BusListItemWithCheckbox(OneLineAvatarIconListItem):
    '''Custom list item.'''
    icon = StringProperty("android")

    def __int__(self, bus):
        self.text = bus
        self.bus = bus

class MetricListItem(TwoLineAvatarIconListItem):
    pass

class RightCheckbox(IRightBodyTouch, MDCheckbox):
    pass

class LeftCheckbox(ILeftBodyTouch, MDCheckbox):
    pass

class MetricConfigurationScreen(SSimBaseScreen):

    _selBusses = []
    _currentMetricCategory = "None"
    _metricIcons = {"Bus Voltage": "lightning-bolt-circle", "Unassigned": "chart-line"}

    _def_btn_color = '#005376'

    def __reset_checked_bus_list(self):
        self._selBusses.clear()
        for wid in self.ids.interlist.children:
            if isinstance(wid, BusListItemWithCheckbox):
                cb = wid.ids.check
                if cb.active:
                    print(wid.text, wid.secondary_text)
                    self._selBusses.append(cb)

    def on_kv_post(self, base_widget):
        menu_items = [
            {
                "viewclass": "OneLineListItem",
                "text": "Minimize",
                "on_release": lambda x="Minimize": self.set_sense(x)
            },
            {
                "viewclass": "OneLineListItem",
                "text": "Maximize",
                "on_release": lambda x="Maximize": self.set_sense(x)
            },
            {
                "viewclass": "OneLineListItem",
                "text": "Seek Value",
                "on_release": lambda x="Seek Value": self.set_sense(x)
            }
        ]

        Clock.schedule_once(lambda dt: self._refocus_field(self.ids.upperLimitText), 0.05)
        Clock.schedule_once(lambda dt: self._refocus_field(self.ids.lowerLimitText), 0.05)
        Clock.schedule_once(lambda dt: self._refocus_field(self.ids.objectiveText), 0.05)

        #self.menu = MDDropdownMenu(
        #    caller=self.ids.caller, items=menu_items, width_mult=3
        #)

    def _refocus_field(self, textfield):
        textfield.focus = True

    def drop_sense_menu(self):
        pass
        #self.menu.open()

    def set_sense(self, value):
        self.ids.caller.text = value
        self.menu.dismiss()

    def manage_store_button_enabled_state(self):
        self.ids.btnStore.disabled = len(self._selBusses) == 0

    def reload_metric_values(self):
        metrics = []
        common_lower_limit = None
        common_upper_limit = None
        common_obj = None
        common_sense = None
        have_no_metric_busses = False

        self.ids.metricValueBox.disabled = len(self._selBusses) == 0
        self.ids.metricSenseBox.disabled = len(self._selBusses) == 0

        ''' Gather up the list of all metrics relevant to the selection'''
        for b in self._selBusses:
            m = self.project.get_metric(self._currentMetricCategory, b)
            if m is None:
                have_no_metric_busses = True
            else:
                metrics.append(m)

        if not have_no_metric_busses:
            for m in metrics:
                if common_lower_limit is None:
                    common_lower_limit = m.metric.lower_limit
                    common_upper_limit = m.metric.upper_limit
                    common_obj = m.metric.objective
                    common_sense = m.metric.improvement_type
                else:
                    if common_lower_limit != m.metric.lower_limit:
                        common_lower_limit = None
                        break
                    if common_upper_limit != m.metric.upper_limit:
                        common_upper_limit = None
                        break
                    if common_obj != m.metric.objective:
                        common_obj = None
                        break
                    if common_sense != m.metric.improvement_type:
                        common_sense = None
                        break
        else:
            common_lower_limit = None
            common_upper_limit = None
            common_obj = None
            common_sense = None

        is_varied = len(metrics) > 1

        if common_lower_limit is None:
            self.ids.lowerLimitText.set_varied_mode() if is_varied else\
                self.ids.lowerLimitText.set_not_set_mode()
        else:
            self.ids.lowerLimitText.text = str(common_lower_limit)
            Clock.schedule_once(lambda dt: self._refocus_field(self.ids.lowerLimitText), 0.05)

        if common_upper_limit is None:
            self.ids.upperLimitText.set_varied_mode() if is_varied else\
                self.ids.upperLimitText.set_not_set_mode()
        else:
            self.ids.upperLimitText.text = str(common_upper_limit)
            Clock.schedule_once(lambda dt: self._refocus_field(self.ids.upperLimitText), 0.05)

        if common_obj is None:
            self.ids.objectiveText.set_varied_mode() if is_varied else\
                self.ids.objectiveText.set_not_set_mode()
        else:
            self.ids.objectiveText.text = str(common_obj)
            Clock.schedule_once(lambda dt: self._refocus_field(self.ids.objectiveText), 0.05)

        if common_sense is None:
            self.manage_button_selection_states(None)
        else:
            self.__active_sense_button(common_sense)

    def __active_sense_button(self, sense: ImprovementType):
        if sense == ImprovementType.Minimize:
            self.set_minimize_sense()
        elif sense == ImprovementType.Maximize:
            self.set_maximize_sense()
        else:
            self.set_seek_value_sense()

    def set_minimize_sense(self):
        self.manage_button_selection_states(self.ids.min_btn)

    def set_maximize_sense(self):
        self.manage_button_selection_states(self.ids.max_btn)

    def set_seek_value_sense(self):
        self.manage_button_selection_states(self.ids.seek_btn)

    def manage_button_selection_states(self, selButton):
        self.ids.max_btn.selected = False
        self.ids.min_btn.selected = False
        self.ids.seek_btn.selected = False
        self.ids.max_btn.md_bg_color = self._def_btn_color
        self.ids.min_btn.md_bg_color = self._def_btn_color
        self.ids.seek_btn.md_bg_color = self._def_btn_color

        if selButton is self.ids.max_btn:
            self.ids.max_btn.md_bg_color = "red"
            self.ids.max_btn.selected = True
            #self.ids.lowerLimitText.disabled = False
            #self.ids.upperLimitText.disabled = True

        elif selButton is self.ids.min_btn:
            self.ids.min_btn.md_bg_color = "red"
            self.ids.min_btn.selected = True
            #self.ids.lowerLimitText.disabled = True
            #self.ids.upperLimitText.disabled = False

        elif selButton is self.ids.seek_btn:
            self.ids.seek_btn.md_bg_color = "red"
            self.ids.seek_btn.selected = True
            #self.ids.lowerLimitText.disabled = False
            #self.ids.upperLimitText.disabled = False

    def store_metrics(self):
        lower_limit = parse_float(self.ids.lowerLimitText.text)
        upper_limit = parse_float(self.ids.upperLimitText.text)
        obj = parse_float(self.ids.objectiveText.text)
        sense = None

        if self.ids.max_btn.selected:
            sense = ImprovementType.Maximize
        elif self.ids.min_btn.selected:
            sense = ImprovementType.Minimize
        elif self.ids.seek_btn.selected:
            sense = ImprovementType.SeekValue

        err = Metric.validate_metric_values(lower_limit, upper_limit, obj, sense, False)

        if err:
            self.__show_invalid_metric_value_popup(err)
            return

        for bus in self._selBusses:
            accum = MetricTimeAccumulator(Metric(lower_limit, upper_limit, obj, sense))
            self.project.add_metric(self._currentMetricCategory, bus, accum)

        self.reload_metric_list()

    def reset_metric_list_label(self):
        """Resets the label atop the list of all defined metrics to include, or
           not, the current metric category.
        """
        if self._currentMetricCategory is None:
            self.ids.currMetriclabel.text = "Defined Metrics"

        elif self._currentMetricCategory == "None":
            self.ids.currMetriclabel.text = "Defined Metrics"

        else:
            self.ids.currMetriclabel.text = \
                "Defined \"" + self._currentMetricCategory + "\" Metrics"

    def manage_selection_buttons_enabled_state(self):
        numCldrn = len(self.ids.interlist.children) == 0
        self.ids.btnSelectAll.disabled = numCldrn
        self.ids.btnDeselectAll.disabled = numCldrn

    def deselect_all_metric_objects(self):
        for wid in self.ids.interlist.children:
            if isinstance(wid, BusListItemWithCheckbox):
                wid.ids.check.active = False

    def select_all_metric_objects(self):
        self._selBusses.clear()
        for wid in self.ids.interlist.children:
            if isinstance(wid, BusListItemWithCheckbox):
                wid.ids.check.active = True
                self._selBusses.append(wid.text)

    def reload_metric_list(self):
        """Reloads the list of all defined metrics.

        This method creates a list item for all metrics previously defined for
        the current category.
        """
        self.ids.metriclist.clear_widgets()
        self.reset_metric_list_label()
        manager = self.project.get_manager(self._currentMetricCategory)

        if manager is None: return

        list = self.ids.metriclist
        list.active = False
        for key, m in manager.all_metrics.items():
            txt = self._currentMetricCategory + " Metric for " + key
            deets = ""

            if m.metric.improvement_type == ImprovementType.Minimize:
                deets = "Upper Limit=" + str(m.metric.upper_limit) + ", " + \
                    "Objective=" + str(m.metric.objective) + ", " + \
                    "Sense=Minimize"

            elif m.metric.improvement_type == ImprovementType.Maximize:
                deets = "Lower Limit=" + str(m.metric.lower_limit) + ", " + \
                    "Objective=" + str(m.metric.objective) + ", " + \
                    "Sense=Maximize"

            elif m.metric.improvement_type == ImprovementType.SeekValue:
                deets = "Lower Limit=" + str(m.metric.lower_limit) + ", " + \
                    "Upper Limit=" + str(m.metric.upper_limit) + ", " + \
                    "Objective=" + str(m.metric.objective) + ", " + \
                    "Sense=Seek Value"

            bItem = MetricListItem(text=txt, secondary_text=deets)
            bItem.bus = key
            bItem.ids.left_icon.icon = self._metricIcons[self._currentMetricCategory]
            bItem.ids.trash_can.bind(on_release=self.on_delete_metric)
            list.add_widget(bItem)

        list.active = True

    def on_delete_metric(self, data):
        bus = data.listItem.bus
        self.project.remove_metric(self._currentMetricCategory, bus)
        self.reload_metric_list()
        self.reload_metric_values()

    def on_item_check_changed(self, ckb, value):
        bus = ckb.listItem.text
        if value:
            self._selBusses.append(bus)
        else:
            self._selBusses.remove(bus)

        self.reload_metric_values()
        self.manage_store_button_enabled_state()

    def configure_voltage_metrics(self):
        self._currentMetricCategory = "Bus Voltage"
        self.ids.interlabel.text = "Busses"
        self.load_bussed_into_list()
        self.reload_metric_list()
        self.reload_metric_values()
        self.manage_selection_buttons_enabled_state()

    def configure_some_other_metrics(self):
        self._currentMetricCategory = "Unassigned"
        self._selBusses.clear()
        self.ids.interlist.clear_widgets()
        self.ids.interlabel.text = "Metric Objects"
        self.reload_metric_list()
        self.reload_metric_values()
        self.manage_selection_buttons_enabled_state()
        print("I'm passing on the other issue...")

    def _return_to_main_screen(self, dt):
        self.manager.current = "ssim"

    def __show_missing_metric_value_popup(self):
        content = MissingMetricValuesPopupContent()

        popup = Popup(
            title='Missing Metric Values', content=content, auto_dismiss=False,
            size_hint=(0.4, 0.4)
            )
        content.ids.dismissBtn.bind(on_press=popup.dismiss)
        popup.open()
        return

    def __show_invalid_metric_value_popup(self, msg):
        content = MessagePopupContent()

        popup = Popup(
            title='Invalid Metric Values', content=content, auto_dismiss=False,
            size_hint=(0.4, 0.4)
            )
        content.ids.msg_label.text = str(msg)
        content.ids.dismissBtn.bind(on_press=popup.dismiss)
        popup.open()
        return

    def __show_no_grid_model_popup(self):
        content = NoGridPopupContent()

        popup = Popup(
            title='No Grid Model', content=content, auto_dismiss=False,
            size_hint=(0.4, 0.4)
            )
        content.ids.dismissBtn.bind(on_press=popup.dismiss)
        content.ids.mainScreenBtn.bind(on_press=popup.dismiss)
        content.ids.mainScreenBtn.bind(on_press=self._return_to_main_screen)
        popup.open()
        return

    def load_bussed_into_list(self):
        self._selBusses.clear()
        list = self.ids.interlist
        list.clear_widgets()
        list.text = "Busses"

        if self.project._grid_model is None:
            self.__show_no_grid_model_popup()
            return

        busses = self.project._grid_model.bus_names
        list.active = False
        for x in busses:
            bItem = BusListItemWithCheckbox(text=str(x))
            bItem.ids.check.bind(active=self.on_item_check_changed)
            list.add_widget(bItem)

        list.active = True

class RunSimulationScreen(SSimBaseScreen):

    def on_enter(self):
        self.populate_confgurations()
        for i in range(20):
            # self.ids.config_list.add_widget(
            #     TwoLineIconListItem(text=f"Single-line item {i}",
            #                         secondary_text="Details")
            # )
            self.ids.config_list.add_widget(
                ListItemWithCheckbox(pk="pk",
                                     text=f"Single-line item {i}",
                                     secondary_text="Details")
            )

    def populate_confgurations(self):
        # item_list = self.ids.interlist
        # TODO: Need to populate the MDlist dynamically
        configs = self.project.configurations

class ListItemWithCheckbox(TwoLineAvatarIconListItem):

    def __init__(self, pk=None, **kwargs):
        super().__init__(**kwargs)
        self.pk = pk

    def delete_item(self, the_list_item):
        self.parent.remove_widget(the_list_item)

class LeftCheckbox(ILeftBodyTouch, MDCheckbox):
    '''Custom left container'''
    pass

class SelectGridDialog(FloatLayout):
    load = ObjectProperty(None)
    cancel = ObjectProperty(None)

class LoadSSIMTOMLDialog(FloatLayout):
    load = ObjectProperty(None)
    cancel = ObjectProperty(None)

class SaveSSIMTOMLDialog(FloatLayout):
    save = ObjectProperty(None)
    cancel = ObjectProperty(None)

    def manage_filename_field(self):
        sel = self.ids.filechooser.selection[0]
        if os.path.isdir(sel):
            self.ids.filenamefield.text = ""
        else:
            self.ids.filenamefield.text = os.path.basename(sel)

class SSimScreen(SSimBaseScreen):

    grid_path = ObjectProperty(None)
    bus_list = ObjectProperty(None)

    def report(self, message):
        Logger.debug("button pressed: %s", message)

    def dismiss_popup(self):
        self._popup.dismiss()

    def load_grid(self, path, filename):
        Logger.debug("loading file %s", filename[0])
        self.project.set_grid_model(filename[0])
        self.bus_list.text = '\n'.join(self.project.bus_names)
        self.dismiss_popup()

    def load_toml_file(self, path, filename):
        Logger.debug("loading file %s", filename[0])
        self.project.clear_metrics()
        self.project.clear_options()

        with open(filename[0], 'r') as f:
            toml = f.read()

        tdat = tomli.loads(toml)
        self.project.read_toml(tdat)
        self.bus_list.text = '\n'.join(self.project.bus_names)
        self.dismiss_popup()

    def save_toml_file(self, selection, filename):
        fullpath = selection[0]

        if os.path.isdir(fullpath):
            fullpath = os.path.join(fullpath, filename)

        split = os.path.splitext(fullpath)
        if split[1].lower() != ".toml":
            fullpath = os.path.join(split[0], ".toml")

        Logger.debug("loading file %s", fullpath)

        toml = self.project.write_toml()

        with open(fullpath, 'w') as f:
            f.write(toml)

        self.dismiss_popup()

    def read_toml(self):
        chooser = LoadSSIMTOMLDialog(
            load=self.load_toml_file, cancel=self.dismiss_popup)

        self._popup = Popup(title="select SSIM TOML file", content=chooser)
        self._popup.open()

    def write_toml(self):
        chooser = SaveSSIMTOMLDialog(
            save=self.save_toml_file, cancel=self.dismiss_popup)

        self._popup = Popup(title="select SSIM TOML file", content=chooser)
        self._popup.open()

    def select_grid_model(self):
        chooser = SelectGridDialog(
            load=self.load_grid, cancel=self.dismiss_popup)

        self._popup = Popup(title="select grid model", content=chooser)
        self._popup.open()

    def open_der_configuration(self):
        self.manager.current = "der-config"

    def open_load_configuration(self):
        self.manager.current = "load-config"

    def open_metric_configuration(self):
        self.manager.current = "metric-config"

    def do_run_simulation(self):
        self.manager.current = "run-sim"
        if self.project.grid_model is None:
            _show_no_grid_popup("ssim", self.manager)
            return


def _show_no_grid_popup(dismiss_screen=None, manager=None):
    """Show a popup dialog warning that no grid model is selected.

    Parameters
    ----------
    dismiss_screen : str, optional

    """
    poppup_content = NoGridPopupContent()
    poppup_content.orientation = "vertical"
    popup = Popup(title='No Grid Model', content=poppup_content,
                  auto_dismiss=False, size_hint=(0.4, 0.4))

    def dismiss(*args):
        popup.dismiss()
        if (dismiss_screen is not None) and (manager is not None):
            manager.current = dismiss_screen

    poppup_content.ids.dismissBtn.bind(on_press=dismiss)
    # open the popup
    popup.open()


def _configure_fonts(exo_regular, exo_bold, exo_italic,
                     opensans_regular, opensans_bold, opensans_italic):
    # Configure the fonts use but the quest style
    LabelBase.register(
        name='Exo 2',
        fn_regular=exo_regular,
        fn_bold=exo_bold,
        fn_italic=exo_italic
    )

    LabelBase.register(
        name='Open Sans',
        fn_regular=opensans_regular,
        fn_bold=opensans_bold,
        fn_italic=opensans_italic
    )


def _paths(package, names):
    basepath = files(package)
    # all names need to be referenced individually so that each file
    # is guaranteed to exist when they are referenced.  As far as I
    # can tell there is no way to just make a directory containing all
    # resources in a package using importlib_resources.
    return list(as_file(basepath.joinpath(name)) for name in names)


def _font_paths():
    return dict(
        zip(_FONT_FILES.keys(),
            _paths("ssim.ui.kivy.fonts", _FONT_FILES.values()))
    )


def _kv_paths():
    return _paths("ssim.ui.kivy", _KV_FILES)


def _image_paths():
    return _paths("ssim.ui.kivy.images", _IMAGE_FILES)


def main():
    """Run the storage-sim kivy application."""
    Logger.setLevel(LOG_LEVELS["debug"])
    with ExitStack() as stack:
        font_paths = {font_name: str(stack.enter_context(font_path))
                      for font_name, font_path in _font_paths().items()}
        kv_paths = [stack.enter_context(kv) for kv in _kv_paths()]
        image_paths = [stack.enter_context(img) for img in _image_paths()]
        _configure_fonts(**font_paths)
        resource_dirs = set(
            resource.parent
            for resource in itertools.chain(kv_paths, image_paths)
        )
        for resource_dir in resource_dirs:
            kivy.resources.resource_add_path(resource_dir)
        SSimApp().run()


if __name__ == '__main__':
    main()
