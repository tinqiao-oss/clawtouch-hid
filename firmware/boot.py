# SPDX-License-Identifier: MIT
# SPDX-FileCopyrightText: 2026 Tinqiao Technology (Beijing) Co., Ltd.
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

# Provenance marker (boot.py runs before CDC0 is live, so the user-visible
# console banner lives in code.py). Kept here so anyone diffing boot.py
# of a re-flashed unit still sees the upstream identity.
#   clawtouch-hid firmware · Tinqiao Technology · MIT
#   github.com/tinqiao-oss/clawtouch-hid
