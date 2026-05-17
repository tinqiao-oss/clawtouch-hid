"""Wire protocol v1.0 — locked frame layout.

THIS TEST FILE IS A CONTRACT. v1.0 is frozen (2026-03-15). If a test
here fails, you are either:
  (a) breaking compatibility with deployed firmware → revert the change
  (b) intentionally proposing v2.0 → discuss in an RFC issue first

Either way: do not "fix" the test. The numbers in this file are the
binary protocol spec.
"""
from __future__ import annotations

import pytest

from clawtouch_hid_protocol import (
    FRAME_HEADER,
    MAX_PAYLOAD_LEN,
    PROTOCOL_VERSION,
    CommandType,
    HidCommand,
    ModifierKey,
    MouseButton,
    ProtocolError,
    build_key_combo,
    build_key_press,
    build_key_release,
    build_mouse_click,
    build_mouse_move,
    build_mouse_scroll,
    build_ping,
    build_type_string,
    modifiers_to_mask,
)


class TestSpecConstants:
    def test_protocol_version_is_1_0_0(self):
        assert PROTOCOL_VERSION == "1.0.0"

    def test_frame_header_is_AA(self):
        assert FRAME_HEADER == 0xAA

    def test_max_payload_is_1024(self):
        assert MAX_PAYLOAD_LEN == 1024


class TestCommandTypeCodes:
    """Wire codes — values are the source of truth, do NOT renumber."""

    def test_canonical_command_codes(self):
        assert int(CommandType.PING) == 0x01
        assert int(CommandType.PONG) == 0x02
        assert int(CommandType.MOUSE_MOVE) == 0x10
        assert int(CommandType.MOUSE_CLICK) == 0x11
        assert int(CommandType.MOUSE_SCROLL) == 0x12
        assert int(CommandType.KEY_PRESS) == 0x20
        assert int(CommandType.KEY_RELEASE) == 0x21
        assert int(CommandType.KEY_TYPE_STRING) == 0x22
        assert int(CommandType.KEY_COMBO) == 0x23
        assert int(CommandType.STATUS_REQUEST) == 0xF0
        assert int(CommandType.STATUS_RESPONSE) == 0xF1
        assert int(CommandType.ACK) == 0xFE
        assert int(CommandType.ERROR) == 0xFF

    def test_mouse_button_codes(self):
        assert int(MouseButton.LEFT) == 0x01
        assert int(MouseButton.RIGHT) == 0x02
        assert int(MouseButton.MIDDLE) == 0x04

    def test_modifier_codes(self):
        assert int(ModifierKey.CTRL) == 0x01
        assert int(ModifierKey.SHIFT) == 0x02
        assert int(ModifierKey.ALT) == 0x04
        assert int(ModifierKey.GUI) == 0x08


class TestRoundtrip:
    def test_ping(self):
        wire = build_ping(seq_id=99).serialize()
        decoded = HidCommand.deserialize(wire)
        assert decoded.cmd_type == CommandType.PING
        assert decoded.seq_id == 99

    def test_type_string_utf8(self):
        wire = build_type_string("emoji 🦞").serialize()
        decoded = HidCommand.deserialize(wire)
        assert decoded.payload.decode("utf-8") == "emoji 🦞"

    def test_combo_byte_order_locked(self):
        """KEY_COMBO is [modifiers, keycode] — opposite of KEY_PRESS.

        This quirk is documented in README. Any reorder breaks the firmware
        silently. Keep this test.
        """
        wire = build_key_combo(int(ModifierKey.CTRL), 0x04).serialize()
        decoded = HidCommand.deserialize(wire)
        assert decoded.payload[0] == 0x01  # modifiers first
        assert decoded.payload[1] == 0x04

    def test_press_byte_order_locked(self):
        """KEY_PRESS is [keycode, modifiers] — opposite of KEY_COMBO."""
        wire = build_key_press(0x04, int(ModifierKey.CTRL)).serialize()
        decoded = HidCommand.deserialize(wire)
        assert decoded.payload[0] == 0x04  # keycode first
        assert decoded.payload[1] == 0x01

    def test_release_all_payload_is_two_zero_bytes(self):
        """KEY_RELEASE with default args is panic-stop: payload [0x00, 0x00].

        Firmware rejects KEY_RELEASE frames with len(payload) < 2, so a zero-
        length payload would fail with ERR_INVALID_PAYLOAD on real hardware.
        Spec (docs/protocol-v1.md §3.3): all-zero payload = release-all.
        """
        wire = build_key_release().serialize()
        decoded = HidCommand.deserialize(wire)
        assert decoded.cmd_type == CommandType.KEY_RELEASE
        assert decoded.payload == b"\x00\x00"

    def test_release_specific_keycode_modifiers(self):
        """KEY_RELEASE payload byte order matches KEY_PRESS: [keycode, modifiers]."""
        wire = build_key_release(0x04, int(ModifierKey.SHIFT), seq_id=3).serialize()
        decoded = HidCommand.deserialize(wire)
        assert decoded.cmd_type == CommandType.KEY_RELEASE
        assert decoded.seq_id == 3
        assert decoded.payload[0] == 0x04  # keycode first
        assert decoded.payload[1] == int(ModifierKey.SHIFT)


class TestErrors:
    def test_corrupted_checksum(self):
        wire = bytearray(build_ping().serialize())
        wire[-1] ^= 0xFF
        with pytest.raises(ProtocolError, match="checksum"):
            HidCommand.deserialize(bytes(wire))

    def test_short_frame(self):
        with pytest.raises(ProtocolError):
            HidCommand.deserialize(b"\xaa")

    def test_oversize_payload(self):
        cmd = HidCommand(CommandType.KEY_TYPE_STRING,
                          payload=b"x" * (MAX_PAYLOAD_LEN + 1))
        with pytest.raises(ProtocolError, match="too large"):
            cmd.serialize()


class TestModifierAliases:
    """cmd/win/gui all map to GUI — works on Mac/Windows/Linux without changes."""

    def test_cmd_equals_win_equals_gui(self):
        assert (modifiers_to_mask(["cmd"])
                == modifiers_to_mask(["win"])
                == modifiers_to_mask(["gui"])
                == int(ModifierKey.GUI))

    def test_ctrl_alias(self):
        assert modifiers_to_mask(["control"]) == modifiers_to_mask(["ctrl"])

    def test_unknown_raises(self):
        with pytest.raises(ProtocolError):
            modifiers_to_mask(["meta"])  # not an alias
