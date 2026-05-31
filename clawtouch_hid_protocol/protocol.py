# SPDX-License-Identifier: MIT
# SPDX-FileCopyrightText: 2026 Tinqiao Technology (Beijing) Co., Ltd.
"""ClawTouch HID wire protocol v1.1.

v1.0 baseline frozen on 2026-03-15. v1.1 (2026-05-28) adds two opcodes for
independent mouse button press/release — required for drag gestures and
Anthropic Computer Use compatibility. All v1.0 opcodes are byte-for-byte
stable forever; v1.1 is additive only.

Binary frame layout, little-endian:

    +------+--------+--------+---------+---------+----------+
    | 0xAA | seq:u16| cmd:u8 | plen:u16| payload | csum:u8  |
    +------+--------+--------+---------+---------+----------+
       1B     2B       1B       2B       plen       1B

Checksum is the low byte of the sum of all preceding bytes. Maximum
payload length is 1024 bytes. This module is dependency-free standard
library code; it has no runtime dependencies and runs on any Python
host. See :mod:`clawtouch_hid_protocol` for the public re-exports and
:doc:`/docs/protocol-v1` for the full specification.
"""
from __future__ import annotations

import struct
from dataclasses import dataclass
from enum import IntEnum

PROTOCOL_VERSION = "1.1.1"
FRAME_HEADER = 0xAA
MAX_PAYLOAD_LEN = 1024


class CommandType(IntEnum):
    """Wire command codes. Values are the source of truth — do not renumber."""
    PING = 0x01
    PONG = 0x02
    MOUSE_MOVE = 0x10
    MOUSE_CLICK = 0x11
    MOUSE_SCROLL = 0x12
    MOUSE_BUTTON_DOWN = 0x13   # v1.1, press only (no release)
    MOUSE_BUTTON_UP = 0x14     # v1.1, release only
    KEY_PRESS = 0x20
    KEY_RELEASE = 0x21
    KEY_TYPE_STRING = 0x22
    KEY_COMBO = 0x23
    STATUS_REQUEST = 0xF0
    STATUS_RESPONSE = 0xF1
    ACK = 0xFE
    ERROR = 0xFF


class MouseButton(IntEnum):
    LEFT = 0x01
    RIGHT = 0x02
    MIDDLE = 0x04


class ModifierKey(IntEnum):
    CTRL = 0x01
    SHIFT = 0x02
    ALT = 0x04
    GUI = 0x08  # Windows / Command key


class ErrorCode(IntEnum):
    """Error codes returned inside ERROR (0xFF) frames."""
    UNKNOWN_COMMAND = 0x01
    INVALID_PAYLOAD = 0x02
    CHECKSUM_MISMATCH = 0x03
    EXECUTION_TIMEOUT = 0x04
    DEVICE_BUSY = 0x05


MODIFIER_NAME_MAP: dict[str, ModifierKey] = {
    "ctrl": ModifierKey.CTRL,
    "control": ModifierKey.CTRL,
    "shift": ModifierKey.SHIFT,
    "alt": ModifierKey.ALT,
    "gui": ModifierKey.GUI,
    "win": ModifierKey.GUI,
    "cmd": ModifierKey.GUI,
}


class ProtocolError(ValueError):
    """Raised when a frame cannot be parsed or built."""


@dataclass
class HidCommand:
    """One framed protocol packet. Serialise with :meth:`serialize`.

    See module docstring for the binary layout. ``seq_id`` is the
    sender's monotonically increasing 16-bit counter; the firmware
    echoes it back on the matching ACK/PONG so the host can correlate
    responses.
    """
    cmd_type: CommandType
    payload: bytes = b""
    seq_id: int = 0

    def serialize(self) -> bytes:
        if len(self.payload) > MAX_PAYLOAD_LEN:
            raise ProtocolError(
                f"payload too large: {len(self.payload)} > {MAX_PAYLOAD_LEN}"
            )
        header = struct.pack("B", FRAME_HEADER)
        seq = struct.pack("<H", self.seq_id & 0xFFFF)
        cmd = struct.pack("B", int(self.cmd_type))
        plen = struct.pack("<H", len(self.payload))
        data = header + seq + cmd + plen + self.payload
        checksum = sum(data) & 0xFF
        return data + struct.pack("B", checksum)

    @classmethod
    def deserialize(cls, data: bytes) -> "HidCommand":
        if len(data) < 7 or data[0] != FRAME_HEADER:
            raise ProtocolError("invalid header / short frame")
        seq_id = struct.unpack("<H", data[1:3])[0]
        try:
            cmd_type = CommandType(data[3])
        except ValueError as e:
            raise ProtocolError(f"unknown command type 0x{data[3]:02x}") from e
        plen = struct.unpack("<H", data[4:6])[0]
        if plen > MAX_PAYLOAD_LEN:
            raise ProtocolError(f"payload too large: {plen}")
        if len(data) < 7 + plen:
            raise ProtocolError("truncated payload")
        payload = data[6:6 + plen]
        expected = data[6 + plen]
        actual = sum(data[:6 + plen]) & 0xFF
        if expected != actual:
            raise ProtocolError(
                f"checksum mismatch: expected 0x{expected:02x}, got 0x{actual:02x}"
            )
        return cls(cmd_type=cmd_type, payload=payload, seq_id=seq_id)


# ── Convenience builders ──

def build_ping(seq_id: int = 0) -> HidCommand:
    return HidCommand(CommandType.PING, b"", seq_id)


def build_mouse_move(x: int, y: int, *, relative: bool, seq_id: int = 0) -> HidCommand:
    flags = 0x01 if relative else 0x00
    payload = struct.pack("<hhB", int(x), int(y), flags)
    return HidCommand(CommandType.MOUSE_MOVE, payload, seq_id)


def build_mouse_click(
    button: MouseButton, *, double: bool = False, seq_id: int = 0
) -> HidCommand:
    flags = 0x01 if double else 0x00
    payload = struct.pack("BB", int(button), flags)
    return HidCommand(CommandType.MOUSE_CLICK, payload, seq_id)


def build_mouse_scroll(delta: int, *, seq_id: int = 0) -> HidCommand:
    payload = struct.pack("<h", int(delta))
    return HidCommand(CommandType.MOUSE_SCROLL, payload, seq_id)


def build_mouse_button_down(button: MouseButton, *, seq_id: int = 0) -> HidCommand:
    """v1.1: press a mouse button and do NOT release it. Pair with
    :func:`build_mouse_button_up` to compose a drag (with
    :func:`build_mouse_move` frames in between)."""
    payload = struct.pack("B", int(button))
    return HidCommand(CommandType.MOUSE_BUTTON_DOWN, payload, seq_id)


def build_mouse_button_up(button: MouseButton, *, seq_id: int = 0) -> HidCommand:
    """v1.1: release a previously-pressed mouse button. Idempotent —
    releasing a non-held button is a no-op (no error)."""
    payload = struct.pack("B", int(button))
    return HidCommand(CommandType.MOUSE_BUTTON_UP, payload, seq_id)


def build_key_press(keycode: int, modifiers: int = 0, *, seq_id: int = 0) -> HidCommand:
    """KEY_PRESS payload is ``[modifiers, keycode]`` (unified v1.1.1 — same
    as :func:`build_key_release` and :func:`build_key_combo`; matches the
    USB HID keyboard report layout where the modifier byte comes first).

    .. warning::
       The *positional* parameter order is ``(keycode, modifiers)`` — the
       **opposite** of :func:`build_key_combo`'s ``(modifiers, keycode)``.
       The wire payload is identical either way, but a positional call
       written by analogy to ``build_key_combo`` would silently swap the
       two values. Prefer keyword arguments (``keycode=``, ``modifiers=``)."""
    payload = struct.pack("BB", int(modifiers), int(keycode))
    return HidCommand(CommandType.KEY_PRESS, payload, seq_id)


def build_key_release(keycode: int = 0, modifiers: int = 0, *, seq_id: int = 0) -> HidCommand:
    """KEY_RELEASE payload is ``[modifiers, keycode]`` — same byte order
    as :func:`build_key_press` and :func:`build_key_combo` (unified v1.1.1).
    Both arguments zero (the default) is panic-stop semantics: firmware
    releases every held key and mouse button. Pass explicit
    keycode/modifiers to release a specific key.

    Like :func:`build_key_press`, the *positional* order is
    ``(keycode, modifiers)`` — opposite of :func:`build_key_combo`. Prefer
    keyword arguments."""
    payload = struct.pack("BB", int(modifiers), int(keycode))
    return HidCommand(CommandType.KEY_RELEASE, payload, seq_id)


def build_key_combo(modifiers: int, keycode: int, *, seq_id: int = 0) -> HidCommand:
    """KEY_COMBO payload is ``[modifiers, keycode]`` — same byte order as
    :func:`build_key_press` and :func:`build_key_release` (unified v1.1.1).

    Note the *positional* order here is ``(modifiers, keycode)`` — the
    reverse of :func:`build_key_press` / :func:`build_key_release`, whose
    first positional argument is the keycode. Prefer keyword arguments."""
    payload = struct.pack("BB", int(modifiers), int(keycode))
    return HidCommand(CommandType.KEY_COMBO, payload, seq_id)


def build_type_string(text: str, *, seq_id: int = 0) -> HidCommand:
    return HidCommand(CommandType.KEY_TYPE_STRING, text.encode("utf-8"), seq_id)


def modifiers_to_mask(names: list[str]) -> int:
    """Translate names like ``["ctrl", "shift"]`` to a modifier bitmask."""
    mask = 0
    for n in names:
        key = n.strip().lower()
        mod = MODIFIER_NAME_MAP.get(key)
        if mod is None:
            raise ProtocolError(f"unknown modifier: {n!r}")
        mask |= int(mod)
    return mask
