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

# Absolute pointer (firmware 1.2+, MOUSE_MOVE_ABS 0x15). A second mouse
# whose X/Y are absolute positions 0..32767 across the screen area the OS
# maps it to, so the host can put the pointer at a pixel in one report
# instead of nudging a relative mouse and reading the cursor back. Its
# buttons are never pressed: clicks stay on the relative mouse above.
# Report ID 4 (KEYBOARD uses 1, MOUSE 2). Keep this block byte-for-byte
# identical to boot_production.py — tests/test_firmware_handlers.py checks.
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

# Composite USB HID (keyboard + relative mouse + absolute pointer). Order
# matters: code.py takes the FIRST mouse as the relative one.
usb_hid.enable(
    (usb_hid.Device.KEYBOARD, usb_hid.Device.MOUSE, ABS_POINTER)
)

# Two CDC channels: console (default REPL) + data (protocol command channel)
usb_cdc.enable(console=True, data=True)

# Provenance marker (boot.py runs before CDC0 is live, so the user-visible
# console banner lives in code.py). Kept here so anyone diffing boot.py
# of a re-flashed unit still sees the upstream identity.
#   clawtouch-hid firmware · Tinqiao Technology · MIT
#   github.com/tinqiao-oss/clawtouch-hid
