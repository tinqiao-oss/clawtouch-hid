# SPDX-License-Identifier: MIT
# SPDX-FileCopyrightText: 2026 Tinqiao Technology (Beijing) Co., Ltd.
"""End-to-end smoke test: PING the ClawTouch HID firmware over USB CDC.

Usage:
    pip install clawtouch-hid-protocol pyserial
    python ping_test.py                 # auto-detect Pico data port
    python ping_test.py COM7            # explicit port (Windows)
    python ping_test.py /dev/ttyACM1    # explicit port (Linux/macOS)

Expected output on success:
    Sending PING to COM7 (115200) ...
    PONG received in 3.2 ms
"""
from __future__ import annotations

import sys
import time

import re

import serial                          # pip install pyserial
import serial.tools.list_ports

from clawtouch_hid_protocol import (
    CommandType,
    HidCommand,
    build_ping,
)

# Raspberry Pi USB VID. CircuitPython assigns the CDC PID dynamically
# (commonly 0x0005 / 0x000A / 0x000C / 0x0010), so we match on VID alone
# and let the highest-numbered CDC port within a serial group win. If
# auto-detect guesses wrong, pass the port explicitly.
_PICO_VID = 0x2E8A
_PORT_NUM_RE = re.compile(r"(\d+)$")


def _port_sort_key(device: str) -> int:
    """Trailing integer of a port name (COM7 → 7, /dev/ttyACM3 → 3)."""
    m = _PORT_NUM_RE.search(device or "")
    return int(m.group(1)) if m else -1


def auto_detect_port() -> str | None:
    """Return the data CDC port of the first Pico we find, else None.

    The Pico firmware enables a composite USB device with TWO CDC
    channels: a REPL **console** (lower-numbered port) and a **data**
    channel (higher-numbered port) that speaks the framed HID
    protocol. Both share VID/PID/serial — pyserial cannot tell them
    apart. The correct port to PING is the highest-numbered one
    within each shared-serial group; opening the console port and
    sending HID frames hits the REPL and times out silently.

    Single-CDC firmwares (or boards with only one port enumerated)
    degrade gracefully — the sole port wins.
    """
    pico_ports = [
        p for p in serial.tools.list_ports.comports()
        if p.vid == _PICO_VID
    ]
    if not pico_ports:
        return None
    # Group by serial_number; within each group the highest-numbered
    # device is the data channel.
    pico_ports.sort(key=lambda p: (p.serial_number or "", _port_sort_key(p.device)))
    # The last entry of each serial-group sort wins, but we just want
    # the first Pico's data port, so collapse to the highest of the
    # first serial group:
    first_serial = pico_ports[0].serial_number
    same_pico = [p for p in pico_ports if p.serial_number == first_serial]
    return max(same_pico, key=lambda p: _port_sort_key(p.device)).device


def ping(port: str, *, timeout: float = 2.0) -> None:
    print(f"Sending PING to {port} (115200) ...")
    with serial.Serial(port, 115200, timeout=timeout) as ser:
        time.sleep(0.2)                # let the CDC channel settle
        ser.reset_input_buffer()

        t0 = time.perf_counter()
        ser.write(build_ping(seq_id=1).serialize())
        ser.flush()

        # Smallest valid frame is 7 bytes (header + seq + cmd + plen + csum)
        raw = ser.read(7)
        elapsed_ms = (time.perf_counter() - t0) * 1000

        if not raw:
            raise SystemExit(f"No response within {timeout:.1f} s — is the port correct?")

        resp = HidCommand.deserialize(raw)
        if resp.cmd_type == CommandType.PONG:
            print(f"PONG received in {elapsed_ms:.1f} ms")
        else:
            raise SystemExit(f"Unexpected reply: {resp.cmd_type.name}")


if __name__ == "__main__":
    target = sys.argv[1] if len(sys.argv) > 1 else auto_detect_port()
    if not target:
        raise SystemExit(
            "No Pico detected. Pass the data port explicitly, e.g.:\n"
            "    python ping_test.py COM7"
        )
    ping(target)
