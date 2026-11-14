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

# Absolute pointer (firmware 1.2+, MOUSE_MOVE_ABS 0x15). A second mouse
# whose X/Y are absolute positions 0..32767 across the screen area the OS
# maps it to, so the host can put the pointer at a pixel in one report
# instead of nudging a relative mouse and reading the cursor back. Its
# buttons are never pressed: clicks stay on the relative mouse above.
# Report ID 4 (KEYBOARD uses 1, MOUSE 2). Keep this block byte-for-byte
# identical to boot.py — tests/test_firmware_handlers.py checks.
ABS_POINTER = usb_hid.Device(
    report_descriptor=bytes((
        0x05, 0x01,        # Usage Page (Generic Desktop)
        0x09, 0x02,        # Usage (Mouse)
        0xA1, 0x01,        # Collection (Application)
        0x85, 0x04,        #   Report ID (4)
        0x09, 0x01,        #   Usage (Pointer)
        0xA1, 0x00,        #   Collection (Physical)
        0x05, 0x09,        #     Usage Page (Button)
        0x19, 0x01,        #     Usage Minimum (1)
        0x29, 0x03,        #     Usage Maximum (3)
        0x15, 0x00,        #     Logical Minimum (0)
        0x25, 0x01,        #     Logical Maximum (1)
        0x95, 0x03,        #     Report Count (3)
        0x75, 0x01,        #     Report Size (1)
        0x81, 0x02,        #     Input (Data, Var, Abs)
        0x95, 0x01,        #     Report Count (1)
        0x75, 0x05,        #     Report Size (5)
        0x81, 0x03,        #     Input (Const) — padding
        0x05, 0x01,        #     Usage Page (Generic Desktop)
        0x09, 0x30,        #     Usage (X)
        0x09, 0x31,        #     Usage (Y)
        0x16, 0x00, 0x00,  #     Logical Minimum (0)
        0x26, 0xFF, 0x7F,  #     Logical Maximum (32767)
        0x75, 0x10,        #     Report Size (16)
        0x95, 0x02,        #     Report Count (2)
        0x81, 0x02,        #     Input (Data, Var, Abs)
        0xC0,              #   End Collection
        0xC0,              # End Collection
    )),
    usage_page=0x01,
    usage=0x02,
    report_ids=(4,),
    in_report_lengths=(5,),
    out_report_lengths=(0,),
)

# Composite USB HID (keyboard + relative mouse + absolute pointer) — same
# as the dev firmware. Order matters: code.py takes the FIRST mouse as the
# relative one.
usb_hid.enable(
    (usb_hid.Device.KEYBOARD, usb_hid.Device.MOUSE, ABS_POINTER)
)

# Data channel only — no REPL console.
usb_cdc.enable(console=False, data=True)

# Provenance marker (kept here so anyone diffing a re-flashed unit still
# sees the upstream identity).
#   clawtouch-hid firmware (production) · Tinqiao Technology · MIT
#   github.com/tinqiao-oss/clawtouch-hid
