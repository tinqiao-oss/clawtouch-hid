# SPDX-License-Identifier: MIT
# SPDX-FileCopyrightText: 2026 Beijing Tinqiao Technology Co., Ltd.
"""USB descriptor setup for the ClawTouch HID firmware — PRODUCTION variant.

Runs once at boot on the Pico 2. Locks the device down to ONLY the two
interfaces ClawTouch needs on a deployed unit:
  * HID keyboard + HID mouse
  * CDC data (the protocol command channel `code.py` reads)

Compared to the development boot.py this DISABLES:
  * the CircuitPython ``CIRCUITPY`` USB mass-storage drive
    (``storage.disable_usb_drive()``) — so the controlled host sees no
    removable drive (avoids USB-storage policies / scans / audit entries),
  * the CDC REPL console (``usb_cdc.enable(console=False)``).

Use this on deployed / B2B devices so the target host's HID-input side
stays clean — it sees a standard USB keyboard + mouse and a single data
serial port, nothing else.

Trade-off: once this is active the firmware is no longer editable over USB
and the REPL is gone. To change the firmware again, re-enter BOOTSEL and
re-flash CircuitPython, which restores the editable CIRCUITPY drive.

CircuitPython only runs the file literally named ``boot.py``: copy this
file onto the board RENAMED to ``boot.py`` (overwriting the dev boot.py).
See docs/flash-guide.md → "Production (locked-down) firmware".

Framework: CircuitPython 10.x
Hardware:  Raspberry Pi Pico 2 (RP2350)
"""

import storage
import usb_hid
import usb_cdc

# Hide the CIRCUITPY mass-storage drive from the host.
storage.disable_usb_drive()

# Composite USB HID (keyboard + mouse) — same as the dev firmware.
usb_hid.enable(
    (usb_hid.Device.KEYBOARD, usb_hid.Device.MOUSE)
)

# Data channel only — no REPL console.
usb_cdc.enable(console=False, data=True)

# Provenance marker (kept here so anyone diffing a re-flashed unit still
# sees the upstream identity).
#   clawtouch-hid firmware (production) · Tinqiao Technology · MIT
#   github.com/tinqiao-oss/clawtouch-hid
