"""
CS 350 Final Project - Smart Thermostat Prototype
Gerus Hays

Purpose:
    Reads temperature from an AHT20 sensor over I2C, controls heating/cooling
    indicator LEDs through GPIO, accepts button input for mode and set point,
    displays status on an LCD, and sends comma-delimited thermostat status over
    UART to simulate reporting to a remote server.

State machine:
    OFF  -> HEAT -> COOL -> OFF  (cycled by the mode button)
        OFF  : both LEDs off
        HEAT : red LED pulses while current temp < set point, solid when >=
        COOL : blue LED pulses while current temp > set point, solid when <=
    In every state the two side buttons raise/lower the set point and the LCD,
    sensor read, and UART report continue to run.

"""

from __future__ import annotations

from enum import Enum
from datetime import datetime
from time import sleep, monotonic

import board
import busio
import adafruit_ahtx0
import serial
from gpiozero import Button, PWMLED


# ---------------------------------------------------------------------------
# CONFIGURATION
# ---------------------------------------------------------------------------

MODE_BUTTON_PIN = 24       # Cycles OFF -> HEAT -> COOL
TEMP_UP_BUTTON_PIN = 25    # Increases set point (lab guide: GPIO 25)
TEMP_DOWN_BUTTON_PIN = 12  # Decreases set point (lab guide: GPIO 12)

RED_LED_PIN = 18           # Heating indicator
BLUE_LED_PIN = 23          # Cooling indicator

DEFAULT_SET_POINT_F = 72   # Starting set point in Fahrenheit
BUTTON_BOUNCE_SECONDS = 0.2  # Debounce window so one press = one event

UART_DEVICE = "/dev/serial0"
UART_BAUD_RATE = 9600      # 9600 8N1 - standard serial config for this project
UART_REPORT_SECONDS = 30   # How often to "report to the server"

LCD_ALTERNATE_SECONDS = 5  # How often line 2 of the LCD flips its content
LOOP_DELAY_SECONDS = 0.25  # Main loop period; small enough to feel responsive

# LED behavior labels, used by _set_led() to decide what a given LED should do.
LED_OFF = "off"
LED_SOLID = "solid"
LED_PULSE = "pulse"


class ThermostatState(Enum):
    """The three operating modes of the thermostat state machine."""
    OFF = "off"
    HEAT = "heat"
    COOL = "cool"


# ---------------------------------------------------------------------------
# LCD HELPERS
# ---------------------------------------------------------------------------
class ConsoleLCD:
    """
    Fallback "LCD" that prints to the console.

    Lets the program run on a machine where the physical
    LCD driver isn't installed, instead of crashing on import.
    """

    def clear(self) -> None:
        pass

    def display(self, line1: str, line2: str) -> None:
        # set to 16 chars so console output matches a 16x2 LCD.
        print(f"LCD: {line1[:16]:<16} | {line2[:16]:<16}")


def create_lcd():
    """
    Return the course LCD if its driver is available, otherwise a console
    fallback. Wrapping the driver in a tiny adapter class gives the rest of the
    program one consistent interface (clear/display) regardless of backend.
    """
    try:
        import drivers 

        lcd = drivers.Lcd()

        class CourseLCD:
            def clear(self) -> None:
                lcd.lcd_clear()

            def display(self, line1: str, line2: str) -> None:
                lcd.lcd_display_string(line1[:16].ljust(16), 1)
                lcd.lcd_display_string(line2[:16].ljust(16), 2)

        return CourseLCD()
    except Exception:
        # Driver missing or failed to init - fall back to console output.
        return ConsoleLCD()


def celsius_to_fahrenheit(temp_c: float) -> float:
    """Convert a Celsius reading from the AHT20 to Fahrenheit."""
    return (temp_c * 9.0 / 5.0) + 32.0


# ---------------------------------------------------------------------------
# MAIN CONTROLLER
# ---------------------------------------------------------------------------
class Thermostat:
    """Owns the hardware, the state machine, and the main run loop."""

    def __init__(self) -> None:
        # --- State machine data ---
        self.state = ThermostatState.OFF
        self.set_point = DEFAULT_SET_POINT_F
        self.current_temp_f = float(DEFAULT_SET_POINT_F)

        # --- I2C / AHT20 temperature sensor ---
        self.i2c = busio.I2C(board.SCL, board.SDA)
        self.sensor = adafruit_ahtx0.AHTx0(self.i2c)

        # --- LEDs (PWM so they can fade/pulse) ---
        self.red_led = PWMLED(RED_LED_PIN)
        self.blue_led = PWMLED(BLUE_LED_PIN)

        self._led_actions: dict[PWMLED, str] = {}

        # --- Buttons (GPIO interrupts via gpiozero callbacks) ---
        # pull_up=True pressing connects the pin to ground.
        # bounce_time debounces so a single press fires a single callback.
        self.mode_button = Button(
            MODE_BUTTON_PIN, pull_up=True, bounce_time=BUTTON_BOUNCE_SECONDS
        )
        self.temp_up_button = Button(
            TEMP_UP_BUTTON_PIN, pull_up=True, bounce_time=BUTTON_BOUNCE_SECONDS
        )
        self.temp_down_button = Button(
            TEMP_DOWN_BUTTON_PIN, pull_up=True, bounce_time=BUTTON_BOUNCE_SECONDS
        )

        # when_pressed registers interrupt-style callbacks: gpiozero watches the
        # pins on a background thread and calls these on each press.
        self.mode_button.when_pressed = self.toggle_mode
        self.temp_up_button.when_pressed = self.increase_set_point
        self.temp_down_button.when_pressed = self.decrease_set_point

        self.uart = serial.Serial(
            port=UART_DEVICE,
            baudrate=UART_BAUD_RATE,
            bytesize=serial.EIGHTBITS,
            parity=serial.PARITY_NONE,
            stopbits=serial.STOPBITS_ONE,
            timeout=1,
        )

        # --- LCD ---
        self.lcd = create_lcd()
        self.lcd.clear()

        # --- Timers for non-blocking, periodic tasks ---
        # monotonic() is used instead of time() because it never jumps backward
        # if the system clock is adjusted.
        self.last_uart_report = 0.0
        self.last_lcd_switch = 0.0
        self.show_temp_line = True

    # ----- Button callbacks (run on gpiozero's background thread) -----
    def toggle_mode(self) -> None:
        """Advance the state machine: OFF -> HEAT -> COOL -> OFF."""
        if self.state == ThermostatState.OFF:
            self.state = ThermostatState.HEAT
        elif self.state == ThermostatState.HEAT:
            self.state = ThermostatState.COOL
        else:
            self.state = ThermostatState.OFF

    def increase_set_point(self) -> None:
        """Raise the set point by 1 F."""
        self.set_point += 1

    def decrease_set_point(self) -> None:
        """Lower the set point by 1 F."""
        self.set_point -= 1

    # ----- Sensor -----
    def read_temperature(self) -> None:
        """Read room temperature from the AHT20 over I2C and store it in F."""
        temp_c = self.sensor.temperature
        self.current_temp_f = celsius_to_fahrenheit(temp_c)

    # ----- Outputs -----
    def _set_led(self, led: PWMLED, action: str) -> None:
        """
        Apply an LED action only when it changes.

        PWMLED.pulse() starts a background fade. If we called
        it every loop iteration the fade would restart ~4x/second and never
        complete, so the LED would flicker dimly instead of breathing smoothly.
        By remembering the last action per LED, we issue each command once.
        """
        if self._led_actions.get(led) == action:
            return  

        self._led_actions[led] = action
        if action == LED_PULSE:
            led.pulse(fade_in_time=1, fade_out_time=1, n=None, background=True)
        elif action == LED_SOLID:
            led.on()
        else:  # LED_OFF
            led.off()

    def update_outputs(self) -> None:
        """
        Drive the indicator LEDs from the current state and temperature.

            HEAT: red pulses while current < set point, solid when current >= set
            COOL: blue pulses while current > set point, solid when current <= set
            OFF : both off
        """
        if self.state == ThermostatState.HEAT:
            self._set_led(self.blue_led, LED_OFF)
            if self.current_temp_f < self.set_point:
                self._set_led(self.red_led, LED_PULSE)
            else:
                self._set_led(self.red_led, LED_SOLID)

        elif self.state == ThermostatState.COOL:
            self._set_led(self.red_led, LED_OFF)
            if self.current_temp_f > self.set_point:
                self._set_led(self.blue_led, LED_PULSE)
            else:
                self._set_led(self.blue_led, LED_SOLID)

        else:  # OFF
            self._set_led(self.red_led, LED_OFF)
            self._set_led(self.blue_led, LED_OFF)

    def update_lcd(self) -> None:
        """
        Line 1: date/time. Line 2: alternates between the current temperature
        and the mode + set point so all data fits on a 16x2 display.
        """
        now = monotonic()
        if now - self.last_lcd_switch >= LCD_ALTERNATE_SECONDS:
            self.show_temp_line = not self.show_temp_line
            self.last_lcd_switch = now

        line1 = datetime.now().strftime("%m/%d %H:%M:%S")
        if self.show_temp_line:
            line2 = f"Temp: {self.current_temp_f:.1f}F"
        else:
            line2 = f"{self.state.value.upper()} Set:{self.set_point}F"

        self.lcd.display(line1, line2)

    def send_uart_report(self) -> None:
        """
        Every UART_REPORT_SECONDS, send a comma-delimited status line over UART
        to simulate reporting to the server: state,current_temp,set_point.
        """
        now = monotonic()
        if now - self.last_uart_report >= UART_REPORT_SECONDS:
            message = (
                f"{self.state.value},{self.current_temp_f:.1f},{self.set_point}\n"
            )
            self.uart.write(message.encode("utf-8"))
            print(f"UART: {message.strip()}")
            self.last_uart_report = now

    # ----- Main loop -----
    def run(self) -> None:
        """
        Poll the sensor, update outputs, refresh the LCD, and report over UART
        on a fixed cadence until interrupted, then release hardware cleanly.
        """
        try:
            while True:
                self.read_temperature()
                self.update_outputs()
                self.update_lcd()
                self.send_uart_report()
                sleep(LOOP_DELAY_SECONDS)
        except KeyboardInterrupt:
            print("Thermostat stopped by user.")
        finally:
            # Always leave the hardware in a safe, known state.
            self.red_led.off()
            self.blue_led.off()
            self.uart.close()
            self.lcd.clear()


if __name__ == "__main__":
    thermostat = Thermostat()
    thermostat.run()