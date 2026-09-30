# SPDX-License-Identifier: MIT
# SPDX-FileCopyrightText: 2026 Beijing Tinqiao Technology Co., Ltd.
"""ClawTouch HID v1.1 wire protocol — host-side definitions.

Public surface re-exported from :mod:`clawtouch_hid_protocol.protocol`.
"""
from .protocol import (
    # Constants
    PROTOCOL_VERSION,
    FRAME_HEADER,
    MAX_PAYLOAD_LEN,
    # Enums
    CommandType,
    MouseButton,
    ModifierKey,
    ErrorCode,
    # Frame
    HidCommand,
    ProtocolError,
    # Builders
    build_ping,
    build_mouse_move,
    build_mouse_click,
    build_mouse_scroll,
    build_mouse_button_down,    # v1.1
    build_mouse_button_up,      # v1.1
    build_key_press,
    build_key_release,
    build_key_combo,
    build_type_string,
    # Helpers
    MODIFIER_NAME_MAP,
    modifiers_to_mask,
)

__all__ = [
    "PROTOCOL_VERSION",
    "FRAME_HEADER",
    "MAX_PAYLOAD_LEN",
    "CommandType",
    "MouseButton",
    "ModifierKey",
    "ErrorCode",
    "HidCommand",
    "ProtocolError",
    "build_ping",
    "build_mouse_move",
    "build_mouse_click",
    "build_mouse_scroll",
    "build_mouse_button_down",
    "build_mouse_button_up",
    "build_key_press",
    "build_key_release",
    "build_key_combo",
    "build_type_string",
    "MODIFIER_NAME_MAP",
    "modifiers_to_mask",
]

__version__ = PROTOCOL_VERSION
