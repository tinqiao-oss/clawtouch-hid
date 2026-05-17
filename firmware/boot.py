"""USB descriptor setup for the ClawTouch HID firmware.

Runs once at boot on the Pico 2. Enables a composite USB device:
  * HID keyboard + HID mouse
  * CDC console (REPL / debug logs) + CDC data (command channel)

The data channel is what `code.py` reads framed protocol packets from.

Framework: CircuitPython 10.x
Hardware:  Raspberry Pi Pico 2 (RP2350)
"""

import usb_hid
import usb_cdc

# Composite USB HID (keyboard + mouse)
usb_hid.enable(
    (usb_hid.Device.KEYBOARD, usb_hid.Device.MOUSE)
)

# Two CDC channels: console (default REPL) + data (protocol command channel)
usb_cdc.enable(console=True, data=True)
