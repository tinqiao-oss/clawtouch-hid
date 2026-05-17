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

import serial                          # pip install pyserial
import serial.tools.list_ports

from clawtouch_hid_protocol import (
    CommandType,
    HidCommand,
    build_ping,
)

# Raspberry Pi USB VID; the Pico 2 advertises one of these PIDs
_PICO_VID = 0x2E8A
_PICO_PIDS = {0x0005, 0x000A, 0x000C, 0x0010}


def auto_detect_port() -> str | None:
    """Return the first port that looks like a Pico, else None."""
    for p in serial.tools.list_ports.comports():
        if p.vid == _PICO_VID and (p.pid in _PICO_PIDS or p.pid is not None):
            return p.device
    return None


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
