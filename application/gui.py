import asyncio
import tkinter as tk
from utils import Color, State, BatteryState, TemperatureScale, TemperatureConversion

from tkcolorpicker import askcolor

import sys
sys.path.append('..')
from logger import logger

ORANGE = '#ffba2e'
DORANGE = '#b28220'
GRAY = '#555555'


class Application(tk.Frame):
    def __init__(self, controller: 'Controller', master=None):
        super().__init__(master)

        self.master = master
        # self.master.overrideredirect(True)  # turns off title bar, geometry
        screen_width = self.master.winfo_screenwidth()
        screen_height = self.master.winfo_screenheight()
        self.master.geometry('500x355+{}+{}'.format(screen_width - 500, screen_height - 335 - 100))
        # self.master.configure(bg=ORANGE)
        self.master.resizable(False, False)
        self.topmost = False  # only to know if root is minimized

        self.controller = controller
        self.pack()
        self.create_widgets()

        self.prev_state = State.Empty

        self.prev_battery = BatteryState(100, False)

        self.alive = True

        self.temperature_scale = TemperatureScale.Celsius

    def close(self):
        print('called')
        self.alive = False
        self.master.destroy()
        print('destroy')

    def create_widgets(self):
        self.canvas = tk.Canvas(self.master, width=500, height=325, bd=-2)
        self.canvas.pack(expand=False)

        self.color_button = tk.Button(self.canvas,
                                      # width=30, height=10,
                                      text='change color', borderwidth=0,
                                      relief='flat',
                                      bg='#ff0000', command=self.pick_color)
        self.color_button.place(x=2, y=2)

        self.brightness_value = tk.DoubleVar()

        self.brightness_slider = tk.Scale(self.canvas,
                                          orient=tk.HORIZONTAL,
                                           # from=0, to=100
                                          variable=self.brightness_value,
                                          )
        self.brightness_slider.place(x=2, y=30)

        self.brightness_button = tk.Button(self.canvas,
                                          # width=30, height=10,
                                          text='set brightness', borderwidth=0,
                                          relief='flat',
                                          bg='#ff0000', command=self.set_brightness)

        self.brightness_button.place(x=110, y=50)


    def update_(self):
        if self.controller.battery is not None:
            self.battery.set('{}%'.format(self.controller.battery.battery_charge))
            if self.prev_battery.is_charging != self.controller.battery.is_charging:
                if self.controller.battery.is_charging:
                    self.canvas.itemconfig(self.battery_canvas, image=self.charging)
                elif self.controller.battery.battery_charge > 20:
                    self.canvas.itemconfig(self.battery_canvas, image=self.normal)
                else:
                    self.canvas.itemconfig(self.battery_canvas, image=self.low)
            elif not self.controller.battery.is_charging:
                if self.prev_battery.battery_charge <= 20 and self.controller.battery.battery_charge > 20:
                    self.canvas.itemconfig(self.battery_canvas, image=self.normal)
                elif self.prev_battery.battery_charge > 20 and self.controller.battery.battery_charge <= 20:
                    self.canvas.itemconfig(self.battery_canvas, image=self.low)
            self.prev_battery = self.controller.battery
        if self.controller.temperature is not None:
            if self.temperature_scale is TemperatureScale.Celsius:
                self.temperature.set('{}°'.format(self.controller.temperature))
            else:
                self.temperature.set('{}°'.format(int(TemperatureConversion.c2f(self.controller.temperature))))
        if self.controller.setting_temperature is not None:
            if self.temperature_scale is TemperatureScale.Celsius:
                self.setting_temperature.set('{}°'.format(self.controller.setting_temperature))
            else:
                self.setting_temperature.set('{}°'.format(int(TemperatureConversion.c2f(self.controller.setting_temperature))))
        if self.controller.temperature_scale != self.temperature_scale:
            if self.controller.temperature_scale == TemperatureScale.Celsius:
                self.temperature_scale_button.config(text=" °C ")
            else:
                self.temperature_scale_button.config(text=" °F ")
            self.temperature_scale = self.controller.temperature_scale
        if self.controller.color is not None:
            self.color_button.configure(bg=self.controller.color.as_rgb)
        if self.controller.state is not None:
            self.state.set(self.controller.state.name)

            if self.controller.state in (State.Empty, State.FinishDrinking) and \
                    self.prev_state in (State.Poured, State.Cooling, State.Heating, State.Keeping):
                self.canvas.itemconfig(self.mug_canvas, image=self.empty)
                self.prev_state = self.controller.state

            elif self.prev_state in (State.Empty, State.FinishDrinking, State.Cooling, State.Keeping) and \
                    self.controller.state in (State.Poured, State.Heating, State.Off):
                self.canvas.itemconfig(self.mug_canvas, image=self.heating)
                self.prev_state = self.controller.state

            elif self.prev_state in (State.Empty, State.FinishDrinking, State.Off, State.Heating) and \
                    self.controller.state in (State.Cooling, State.Keeping):
                self.canvas.itemconfig(self.mug_canvas, image=self.complete)
                self.prev_state = self.controller.state

    def pick_color(self):
        color = askcolor((255, 255, 0), self, alpha=True)
        if not color:
            return
        asyncio.gather(self.controller.set_color(Color(*color[0])))

    def set_brightness(self):
        brightness = self.brightness_value.get()
        brightness = int(brightness)
        logger.info(f"brightness_value: {brightness}")
        asyncio.gather(self.controller.set_brightness(brightness))
