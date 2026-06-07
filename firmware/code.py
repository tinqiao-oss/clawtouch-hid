# SPDX-License-Identifier: MIT
# SPDX-FileCopyrightText: 2026 Tinqiao Technology (Beijing) Co., Ltd.
"""ClawTouch HID firmware v1.1.2 — Raspberry Pi Pico 2.

Generic HID executor: reads framed protocol packets from the USB CDC data
channel and executes the corresponding HID action. The firmware does
nothing on its own — all decisions live on the host.

v1.1.2 (2026-05-31): panic-stop now releases mouse buttons too. The
all-zero ``KEY_RELEASE(0, 0)`` (a.k.a. ``hid.release_all``) branch used
to call only ``keyboard.release_all()``; a button held via
``MOUSE_BUTTON_DOWN`` (drag start) stayed physically pressed. It now also
calls ``mouse.release_all()`` so the documented panic-stop semantics
(spec §3.3) actually hold. Wire-compatible — old hosts unaffected.

v1.1.1 (2026-05-31): KEY_PRESS / KEY_RELEASE payload byte order unified
to ``[modifiers, keycode]`` (matching KEY_COMBO and the USB HID keyboard
report layout). Affects the two keyboard opcodes' payload only.

v1.1.0 (2026-05-28): implements two new opcodes from protocol v1.1 —
``MOUSE_BUTTON_DOWN`` (0x13) and ``MOUSE_BUTTON_UP`` (0x14). These
let a host program compose drag gestures (press → multiple moves →
release) and match the Anthropic Computer Use action set's
``left_mouse_down`` / ``left_mouse_up``. v1.0 opcodes are byte-for-byte
unchanged — old hosts keep working.

v1.0.2 (2026-05-26, round 5 audit): main loop frame-sync uses
``bytearray.find`` + ``del buf[:idx]`` instead of repeated ``buf.pop(0)``.
``pop(0)`` is O(n) per call: a noisy or adversarial USB stream (long
run of non-HEADER bytes) would memmove the entire buffer for every
byte, stalling USB interrupt response. Behaviour is byte-for-byte
identical, just bounded CPU usage on the worst case.

v1.0.1 (2026-05-26, round 4 audit): four defensive fixes —
``process_packet`` runs checksum verify on every frame (truncated frame
returns ERR_INVALID_PAYLOAD instead of falling through); KEY_TYPE_STRING
catches UnicodeDecodeError → ERR_INVALID_PAYLOAD (no more crash on
malformed UTF-8); MOUSE_CLICK rejects unknown button codes with
ERR_INVALID_PAYLOAD (was silently defaulting to LEFT_BUTTON and ACK-ing,
making the host believe a right-click had landed when only a left-click
happened); packet_parser switched from recursion to iteration (deep
nested payloads can no longer raise RecursionError and lock the Pico).

All v1.0.x revisions are wire-compatible with the v1.0 protocol —
older hosts keep working unchanged, hid_firmware_min stays at "1.0.0".

Framework: CircuitPython 10.x
Hardware:  Raspberry Pi Pico 2 (RP2350)
Protocol:  ClawTouch HID Protocol v1.1 (see ../docs/protocol-v1.md)
"""

import struct
import json
import time

try:
    # Board-only modules. On the Pico these import cleanly; under CPython
    # (unit tests) they are absent — or a same-named PyPI shim errors at
    # import — so the hardware entry point at the bottom (`_main`) is
    # skipped and only HidExecutor is exercised. Broad except on purpose:
    # any failure to load the board stack means "not on the device".
    import usb_hid
    import usb_cdc
    import supervisor
    _ON_DEVICE = True
except Exception:  # noqa: BLE001
    _ON_DEVICE = False

from adafruit_hid.keyboard import Keyboard
from adafruit_hid.keycode import Keycode
from adafruit_hid.keyboard_layout_us import KeyboardLayoutUS
from adafruit_hid.mouse import Mouse

# ════════════════════════════════════════════════════════════════════
# Protocol constants — must match clawtouch_hid_protocol/protocol.py
# ════════════════════════════════════════════════════════════════════

HEADER = 0xAA
FIRMWARE_VERSION = "1.1.2"
BOARD_NAME = "pico2"
MAX_PAYLOAD_LEN = 1024

# Command codes
CMD_PING = 0x01
CMD_PONG = 0x02
CMD_MOUSE_MOVE = 0x10
CMD_MOUSE_CLICK = 0x11
CMD_MOUSE_SCROLL = 0x12
CMD_MOUSE_BUTTON_DOWN = 0x13    # v1.1
CMD_MOUSE_BUTTON_UP = 0x14      # v1.1
CMD_KEY_PRESS = 0x20
CMD_KEY_RELEASE = 0x21
CMD_KEY_TYPE = 0x22         # wire name: KEY_TYPE_STRING
CMD_KEY_COMBO = 0x23
CMD_STATUS_REQ = 0xF0       # wire name: STATUS_REQUEST
CMD_STATUS_RESP = 0xF1      # wire name: STATUS_RESPONSE
CMD_ACK = 0xFE
CMD_ERROR = 0xFF

# Error codes
ERR_UNKNOWN_COMMAND = 0x01
ERR_INVALID_PAYLOAD = 0x02
ERR_CHECKSUM_MISMATCH = 0x03
ERR_EXECUTION_TIMEOUT = 0x04
ERR_DEVICE_BUSY = 0x05

# Mouse button mapping
MOUSE_BUTTON_MAP = {
    0x01: Mouse.LEFT_BUTTON,
    0x02: Mouse.RIGHT_BUTTON,
    0x04: Mouse.MIDDLE_BUTTON,
}


# ════════════════════════════════════════════════════════════════════
# HID executor
# ════════════════════════════════════════════════════════════════════

class HidExecutor:
    """Parses one protocol packet and executes the corresponding HID action."""

    def __init__(self, keyboard, mouse, layout, serial_out):
        self.keyboard = keyboard
        self.mouse = mouse
        self.layout = layout
        self.serial_out = serial_out
        self._uptime_ms = 0

        self._handlers = {
            CMD_PING: self._handle_ping,
            CMD_MOUSE_MOVE: self._handle_mouse_move,
            CMD_MOUSE_CLICK: self._handle_mouse_click,
            CMD_MOUSE_SCROLL: self._handle_mouse_scroll,
            CMD_MOUSE_BUTTON_DOWN: self._handle_mouse_button_down,   # v1.1
            CMD_MOUSE_BUTTON_UP: self._handle_mouse_button_up,       # v1.1
            CMD_KEY_PRESS: self._handle_key_press,
            CMD_KEY_RELEASE: self._handle_key_release,
            CMD_KEY_TYPE: self._handle_key_type,
            CMD_KEY_COMBO: self._handle_key_combo,
            CMD_STATUS_REQ: self._handle_status_request,
        }

    def process_packet(self, data: bytes):
        """Parse and dispatch one framed packet."""
        if len(data) < 7 or data[0] != HEADER:
            self._send_error(0, ERR_INVALID_PAYLOAD, "Bad header")
            return

        seq_id = struct.unpack_from("<H", data, 1)[0]
        cmd_type = data[3]
        payload_len = struct.unpack_from("<H", data, 4)[0]

        if payload_len > MAX_PAYLOAD_LEN:
            self._send_error(seq_id, ERR_INVALID_PAYLOAD, "Too large")
            return

        # Checksum verification — MUST run for every frame. Previously
        # the verify was inside ``if len(data) >= 7 + payload_len`` so
        # a truncated frame fell straight through to the slice below
        # (silently shorter than payload_len) and got dispatched. The
        # main loop guarded this in practice but ``process_packet`` is
        # public API and callable from tests / future entry points.
        if len(data) < 7 + payload_len:
            self._send_error(seq_id, ERR_INVALID_PAYLOAD, "Truncated")
            return
        expected_checksum = data[6 + payload_len]
        actual_checksum = sum(data[:6 + payload_len]) & 0xFF
        if actual_checksum != expected_checksum:
            self._send_error(seq_id, ERR_CHECKSUM_MISMATCH, "Checksum")
            return

        payload = data[6:6 + payload_len]

        handler = self._handlers.get(cmd_type)
        if handler:
            try:
                handler(seq_id, payload)
            except Exception as e:
                self._send_error(seq_id, ERR_EXECUTION_TIMEOUT, str(e)[:50])
        else:
            self._send_error(seq_id, ERR_UNKNOWN_COMMAND, f"{cmd_type:#x}")

    # ── Command handlers ──

    def _handle_ping(self, seq_id, payload):
        self._send_response(CMD_PONG, seq_id, b"")

    def _handle_mouse_move(self, seq_id, payload):
        if len(payload) < 5:
            self._send_error(seq_id, ERR_INVALID_PAYLOAD, "MOVE:5B")
            return
        x, y, flags = struct.unpack("<hhB", payload[:5])
        # The protocol-v1 spec reserves the `flags` field's bit0 to
        # distinguish relative vs absolute coordinates, but the v1.0
        # firmware always treats (x, y) as a relative pixel delta —
        # this is a hard constraint of USB HID Boot Mouse (which has
        # no absolute-coordinate report). Absolute interpretation
        # lives on the host side: clawtouch-mcp queries the OS cursor
        # position and converts to a delta before sending. The flag
        # is read here so the field stays addressable for a future
        # firmware revision that switches to a HID Digitizer profile.
        del flags  # explicitly unused at the v1.0 firmware layer
        # x/y are signed int16 deltas (+/-32767), but a USB HID Boot Mouse
        # report carries only a signed int8 per axis (-127..127). Adafruit
        # HID's Mouse.move() bridges the gap: it splits any |delta| > 127
        # into successive Boot Mouse reports, so a large delta is delivered
        # in full, just across multiple reports. We deliberately do NOT
        # clamp here -- the host converge loop emits whatever magnitude it
        # needs (a cross-monitor first hop is routinely > 127 px) and relies
        # on this split. See docs/protocol-v1.md (MOUSE_MOVE magnitude).
        self.mouse.move(x=x, y=y)
        self._send_ack(seq_id)

    def _handle_mouse_click(self, seq_id, payload):
        if len(payload) < 2:
            self._send_error(seq_id, ERR_INVALID_PAYLOAD, "CLICK:2B")
            return
        button_code, flags = struct.unpack("BB", payload[:2])
        button = MOUSE_BUTTON_MAP.get(button_code)
        if button is None:
            # Unknown button code used to silently default to LEFT and
            # ACK — the host then thought its right-click landed when
            # actually a left-click happened. Spec §3.2 only defines
            # 0x01 / 0x02 / 0x04.
            self._send_error(seq_id, ERR_INVALID_PAYLOAD, "btn")
            return
        self.mouse.click(button)
        if flags & 0x01:
            # bit0 = double-click (per protocol-v1 §3.2). Adafruit HID's
            # mouse.click is the smallest atomic unit; emit a second one.
            self.mouse.click(button)
        self._send_ack(seq_id)

    def _handle_mouse_scroll(self, seq_id, payload):
        if len(payload) < 2:
            self._send_error(seq_id, ERR_INVALID_PAYLOAD, "SCROLL:2B")
            return
        delta = struct.unpack("<h", payload[:2])[0]
        self.mouse.move(wheel=delta)
        self._send_ack(seq_id)

    def _handle_mouse_button_down(self, seq_id, payload):
        """v1.1: press a mouse button and do NOT release it. Pair with
        MOUSE_BUTTON_UP (and MOUSE_MOVE frames in between) for drag."""
        if len(payload) < 1:
            self._send_error(seq_id, ERR_INVALID_PAYLOAD, "DOWN:1B")
            return
        button = MOUSE_BUTTON_MAP.get(payload[0])
        if button is None:
            self._send_error(seq_id, ERR_INVALID_PAYLOAD, "btn")
            return
        self.mouse.press(button)
        self._send_ack(seq_id)

    def _handle_mouse_button_up(self, seq_id, payload):
        """v1.1: release a previously-pressed mouse button. Idempotent
        (releasing a non-held button is a no-op, no error)."""
        if len(payload) < 1:
            self._send_error(seq_id, ERR_INVALID_PAYLOAD, "UP:1B")
            return
        button = MOUSE_BUTTON_MAP.get(payload[0])
        if button is None:
            self._send_error(seq_id, ERR_INVALID_PAYLOAD, "btn")
            return
        self.mouse.release(button)
        self._send_ack(seq_id)

    def _handle_key_press(self, seq_id, payload):
        if len(payload) < 2:
            self._send_error(seq_id, ERR_INVALID_PAYLOAD, "PRESS:2B")
            return
        # KEY_PRESS payload is [modifiers, keycode] — same as KEY_RELEASE/KEY_COMBO (unified v1.1.1)
        modifiers, keycode = struct.unpack("BB", payload[:2])
        keys = self._collect_keys(modifiers, keycode)
        if keys:
            self.keyboard.press(*keys)
        self._send_ack(seq_id)

    def _handle_key_release(self, seq_id, payload):
        if len(payload) < 2:
            self._send_error(seq_id, ERR_INVALID_PAYLOAD, "REL:2B")
            return
        modifiers, keycode = struct.unpack("BB", payload[:2])
        if keycode == 0 and modifiers == 0:
            # Panic-stop semantics (spec §3.3): release every held key AND
            # mouse button. keyboard and mouse are separate HID objects, so
            # a button held via MOUSE_BUTTON_DOWN (drag start) must be
            # cleared here too — otherwise release-all leaves it physically
            # pressed and the documented panic stop fails to lift a drag.
            self.keyboard.release_all()
            self.mouse.release_all()
        else:
            for k in self._collect_keys(modifiers, keycode):
                self.keyboard.release(k)
        self._send_ack(seq_id)

    def _handle_key_type(self, seq_id, payload):
        # Malformed UTF-8 used to surface as UnicodeDecodeError → caught
        # by the generic wrapper in process_packet and reported as
        # ERR_EXECUTION_TIMEOUT, which made hosts retry as if the
        # firmware had stalled. Spec §3.3 says malformed payload is
        # ERR_INVALID_PAYLOAD.
        try:
            text = payload.decode("utf-8")
        except UnicodeDecodeError:
            self._send_error(seq_id, ERR_INVALID_PAYLOAD, "utf8")
            return
        self.layout.write(text)
        self._send_ack(seq_id)

    def _handle_key_combo(self, seq_id, payload):
        if len(payload) < 2:
            self._send_error(seq_id, ERR_INVALID_PAYLOAD, "COMBO:2B")
            return
        # KEY_COMBO payload is [modifiers, keycode] — same as KEY_PRESS/KEY_RELEASE (unified v1.1.1)
        modifiers, keycode = struct.unpack("BB", payload[:2])
        keys = self._collect_keys(modifiers, keycode)
        if keys:
            self.keyboard.press(*keys)
            time.sleep(0.05)
            self.keyboard.release(*keys)
        self._send_ack(seq_id)

    def _handle_status_request(self, seq_id, payload):
        status = json.dumps({
            "fw_ver": FIRMWARE_VERSION,
            "board": BOARD_NAME,
            "uptime_ms": self._uptime_ms,
        }).encode("utf-8")
        self._send_response(CMD_STATUS_RESP, seq_id, status)

    # ── Helpers ──

    @staticmethod
    def _collect_keys(modifiers, keycode):
        """Translate a modifier bitmask + a keycode into a list of Keycode values."""
        keys = []
        if modifiers & 0x01:
            keys.append(Keycode.LEFT_CONTROL)
        if modifiers & 0x02:
            keys.append(Keycode.LEFT_SHIFT)
        if modifiers & 0x04:
            keys.append(Keycode.LEFT_ALT)
        if modifiers & 0x08:
            keys.append(Keycode.LEFT_GUI)
        if keycode:
            keys.append(keycode)
        return keys

    # ── Response framing ──

    def _send_ack(self, seq_id):
        self._send_response(CMD_ACK, seq_id, b"")

    def _send_error(self, seq_id, error_code, msg):
        payload = struct.pack("B", error_code) + msg.encode("utf-8")
        self._send_response(CMD_ERROR, seq_id, payload)

    def _send_response(self, cmd_type, seq_id, payload):
        header = bytes([HEADER])
        seq = struct.pack("<H", seq_id)
        cmd = bytes([cmd_type])
        plen = struct.pack("<H", len(payload))
        data = header + seq + cmd + plen + payload
        checksum = bytes([sum(data) & 0xFF])
        packet = data + checksum

        if self.serial_out:
            self.serial_out.write(packet)


# ════════════════════════════════════════════════════════════════════
# Console banner (CDC0 / REPL)
# Printed once at startup. Visible via `mpremote connect auto repl`,
# screen /dev/cu.usbmodemXXX, PuTTY on the console COM port, etc.
# Provenance line travels with the binary — anyone reverse-engineering
# a flashed unit sees the upstream identity in the CDC console.
# ════════════════════════════════════════════════════════════════════

# ════════════════════════════════════════════════════════════════════
# Main loop (CircuitPython entry point)
# Wrapped in _main() + guarded by _ON_DEVICE so the module can be
# imported under CPython for unit tests (HidExecutor handler tests)
# without spinning the hardware loop. On the Pico _ON_DEVICE is True and
# behaviour is byte-for-byte unchanged.
# ════════════════════════════════════════════════════════════════════

def _main():
    print()
    print(" ╔═╗╦  ╔═╗╦ ╦╦═╗╔═╗╦ ╦╔═╗╦ ╦")
    print(" ║  ║  ╠═╣║║║ ║ ║ ║║ ║║  ╠═╣")
    print(" ╚═╝╩═╝╩ ╩╚╩╝ ╩ ╚═╝╚═╝╚═╝╩ ╩")
    print(" clawtouch-hid firmware v" + FIRMWARE_VERSION + " · Tinqiao Technology")
    print(" MIT · github.com/tinqiao-oss/clawtouch-hid")
    print()

    # Onboard LED indicator (1Hz heartbeat once running)
    try:
        import digitalio
        import board
        led = digitalio.DigitalInOut(board.LED)
        led.direction = digitalio.Direction.OUTPUT
        led.value = True
    except Exception:
        led = None

    # Initialise HID devices
    keyboard = Keyboard(usb_hid.devices)
    mouse = Mouse(usb_hid.devices)
    layout = KeyboardLayoutUS(keyboard)
    serial = usb_cdc.data

    executor = HidExecutor(keyboard, mouse, layout, serial)

    buf = bytearray()

    while True:
        if serial and serial.in_waiting:
            incoming = serial.read(serial.in_waiting)
            if incoming:
                buf.extend(incoming)

                # Extract complete frames.
                # Frame sync uses bytearray.find + del [:idx] instead of pop(0)
                # in a loop: pop(0) is O(n) memmove per call. A noisy or
                # adversarial USB stream (e.g. a long run of non-HEADER bytes)
                # would spend CPU time linearly memmove-ing the whole buffer
                # for each byte, stalling USB interrupt response on the Pico.
                # find+del covers the same range in a single O(n) memmove.
                # (round 4 fixed this in packet_parser.py; this main loop is
                # the same-source bug that was missed there — round 5 fix.)
                while len(buf) >= 7:
                    if buf[0] != HEADER:
                        idx = buf.find(HEADER)
                        if idx < 0:
                            buf = bytearray()
                            break
                        del buf[:idx]
                        if len(buf) < 7:
                            break

                    payload_len = struct.unpack_from("<H", buf, 4)[0]
                    if payload_len > MAX_PAYLOAD_LEN:
                        # Skip this HEADER and resync from the next byte.
                        del buf[:1]
                        continue

                    total_len = 7 + payload_len
                    if len(buf) < total_len:
                        break

                    packet = bytes(buf[:total_len])
                    buf = buf[total_len:]
                    executor.process_packet(packet)

        executor._uptime_ms = supervisor.ticks_ms()

        # LED heartbeat (1Hz)
        if led:
            led.value = (executor._uptime_ms // 500) % 2 == 0


if _ON_DEVICE:
    _main()
