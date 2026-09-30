# SPDX-License-Identifier: MIT
# SPDX-FileCopyrightText: 2026 Beijing Tinqiao Technology Co., Ltd.
"""USB descriptor setup for the ClawTouch HID firmware — DEVELOPMENT variant.

Runs once at boot on the Pico 2. Enables a composite USB device:
  * HID keyboard + HID mouse
  * CDC console (REPL / debug logs) + CDC data (command channel)
  * the CircuitPython ``CIRCUITPY`` USB mass-storage drive (left mounted by
    default so the firmware stays editable in place)

The data channel is what `code.py` reads framed protocol packets from.

This is the DEV variant: it keeps both the CDC REPL console AND the
``CIRCUITPY`` USB drive exposed to the host, so the board stays debuggable
and the firmware editable. That means the controlled machine sees a
removable drive appear when the device is plugged in — fine for a dev box,
but on a locked-down / enterprise host it may trigger USB-storage policies,
scans, or audit entries. For a deployment that exposes ONLY HID + CDC data
(no ``CIRCUITPY`` drive, no REPL), copy ``boot_production.py`` onto the board
RENAMED to ``boot.py`` (CircuitPython only runs the file literally named
``boot.py``). See ``docs/flash-guide.md`` → "Production (locked-down) firmware".

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
