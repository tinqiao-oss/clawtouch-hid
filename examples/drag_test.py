# SPDX-License-Identifier: MIT
# SPDX-FileCopyrightText: 2026 Tinqiao Technology (Beijing) Co., Ltd.
"""End-to-end drag smoke test for protocol v1.1.

Verifies the new MOUSE_BUTTON_DOWN (0x13) / MOUSE_BUTTON_UP (0x14)
opcodes on real hardware by composing a one-second drag from the
current cursor position 400 px to the right.

Usage:
    pip install clawtouch-hid-protocol pyserial
    python drag_test.py                 # auto-detect Pico data port
    python drag_test.py COM7            # explicit port (Windows)
    python drag_test.py /dev/ttyACM1    # explicit port (Linux/macOS)

Expected behaviour on success:
    1. The mouse cursor on the host machine moves 400 px to the right.
    2. While it moves, the LEFT button is held down — so any selectable
       text under the path gets selected, or an icon gets dragged.
    3. The button releases at the end.
    4. Three ACK frames return in <100 ms each.

If you see "Test failed: ERR_UNKNOWN_COMMAND" instead, the Pico is
running pre-v1.1 firmware (1.0.x) — flash firmware/code.py from
this repo (v1.1.0+) and try again.

**Before running**: focus a window where dragging won't do damage.
A blank text editor with a few lines of text is a good target — the
drag should highlight some text. Do NOT run this with a draggable
file/icon under the cursor unless you know where it would end up.
"""
from __future__ import annotations

import sys
import time

# Reuse port auto-detect from ping_test for consistency.
sys.path.insert(0, str(__import__("pathlib").Path(__file__).parent))
from ping_test import auto_detect_port  # noqa: E402

import serial  # pip install pyserial  # noqa: E402

from clawtouch_hid_protocol import (  # noqa: E402
    CommandType,
    HidCommand,
    MouseButton,
    build_mouse_button_down,
    build_mouse_button_up,
    build_mouse_move,
)


def _send_and_expect_ack(ser: serial.Serial, frame: bytes, label: str) -> None:
    """Write one framed packet, read one ACK frame, verify cmd_type==ACK."""
    t0 = time.perf_counter()
    ser.write(frame)
    ser.flush()
    # Header (1) + seq (2) + cmd (1) + plen (2) + payload (0 for ACK) + csum (1) = 7 bytes.
    resp_bytes = ser.read(7)
    dt_ms = (time.perf_counter() - t0) * 1000
    if len(resp_bytes) < 7:
        raise RuntimeError(
            f"{label}: short frame ({len(resp_bytes)} bytes in {dt_ms:.1f} ms) — "
            "firmware may be unresponsive or not running v1.1"
        )
    resp = HidCommand.deserialize(resp_bytes)
    if resp.cmd_type == CommandType.ERROR:
        err_code = resp.payload[0] if resp.payload else 0
        err_msg = resp.payload[1:].decode("utf-8", "replace") if len(resp.payload) > 1 else ""
        if err_code == 0x01:  # ERR_UNKNOWN_COMMAND
            raise RuntimeError(
                f"{label}: firmware does not recognise this opcode. "
                "Most likely cause: Pico is running pre-v1.1 firmware "
                "(v1.0.x). Flash firmware/code.py from this repo "
                "(>=1.1.0) and rerun."
            )
        raise RuntimeError(f"{label}: ERROR 0x{err_code:02x} {err_msg!r}")
    if resp.cmd_type != CommandType.ACK:
        raise RuntimeError(
            f"{label}: expected ACK (0xFE), got {resp.cmd_type.name} "
            f"(0x{int(resp.cmd_type):02x})"
        )
    print(f"  {label:18s} ACK in {dt_ms:.1f} ms")


def run_drag(port: str) -> None:
    print(f"Opening {port} @ 115200 ...")
    with serial.Serial(port, 115200, timeout=2) as ser:
        # Brief settle so the data CDC channel is fully up.
        time.sleep(0.2)
        ser.reset_input_buffer()

        print("Performing 400 px rightward drag with LEFT button held ...")

        # Step 1: press LEFT button (no release).
        _send_and_expect_ack(
            ser,
            build_mouse_button_down(MouseButton.LEFT, seq_id=1).serialize(),
            "BUTTON_DOWN",
        )

        # Step 2: glide the cursor over ~1 s in 40 small relative moves
        # (10 px each). 25 ms per step keeps host event handlers
        # comfortably ahead of any debounce while the button is held.
        STEPS = 40
        STEP_PX = 10
        STEP_INTERVAL_S = 0.025
        for i in range(STEPS):
            ser.write(build_mouse_move(STEP_PX, 0, relative=True, seq_id=10 + i).serialize())
            ser.flush()
            # Drain the ACK; ignore the round-trip for these intermediate
            # moves to keep the path smooth.
            ser.read(7)
            time.sleep(STEP_INTERVAL_S)
        print(f"  {'MOUSE_MOVE x' + str(STEPS):18s} sent ({STEPS} × {STEP_PX} px = {STEPS * STEP_PX} px)")

        # The intermediate moves above drain only 7 bytes per ACK; if the
        # firmware returned a longer ERROR frame for any of them the input
        # buffer could be misaligned. Resync before the framed release.
        ser.reset_input_buffer()

        # Step 3: release LEFT button.
        _send_and_expect_ack(
            ser,
            build_mouse_button_up(MouseButton.LEFT, seq_id=100).serialize(),
            "BUTTON_UP",
        )

        # Step 4: idempotent release — verify firmware accepts a second
        # BUTTON_UP without erroring (a non-held button release is a no-op).
        _send_and_expect_ack(
            ser,
            build_mouse_button_up(MouseButton.LEFT, seq_id=101).serialize(),
            "BUTTON_UP (2nd)",
        )

    print("\nDrag complete. On the host, look for:")
    print("  - text selection extending ~400 px to the right of where")
    print("    the cursor was when you started this script, OR")
    print("  - an icon / window dragged 400 px to the right of its origin.")
    print("\nIf nothing visible happened, the host probably wasn't focused")
    print("on a drag-aware surface — try again with a text editor focused.")


def main() -> int:
    port = sys.argv[1] if len(sys.argv) > 1 else None
    if port is None:
        port = auto_detect_port()
    if port is None:
        print("ERROR: no Pico HID port detected.", file=sys.stderr)
        print("  Plug the Pico in via USB, or pass the port explicitly:", file=sys.stderr)
        print("    python drag_test.py COM7              # Windows", file=sys.stderr)
        print("    python drag_test.py /dev/ttyACM1      # Linux/macOS", file=sys.stderr)
        return 1
    try:
        run_drag(port)
    except RuntimeError as e:
        print(f"\nTest failed: {e}", file=sys.stderr)
        return 2
    except serial.SerialException as e:
        print(f"\nSerial error on {port}: {e}", file=sys.stderr)
        print("  Possible causes:", file=sys.stderr)
        print("  - Port held by another process (close Arduino IDE / ClawTouch).", file=sys.stderr)
        print("  - Wrong port: try the higher-numbered CDC channel (data, not console).", file=sys.stderr)
        return 3
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
