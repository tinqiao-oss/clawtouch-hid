# SPDX-License-Identifier: MIT
# SPDX-FileCopyrightText: 2026 Beijing Tinqiao Technology Co., Ltd.
"""Firmware HID-executor handler tests (hardware-free).

``firmware/code.py`` is CircuitPython firmware: its board-only imports
(``usb_hid`` / ``usb_cdc`` / ``supervisor``) and a ``while True`` hardware
loop normally make it un-importable under CPython. The firmware guards
those behind ``_ON_DEVICE`` and wraps the loop in ``_main()``, so with
``adafruit_hid`` stubbed we can import the module, build a ``HidExecutor``
with mock HID objects, and assert the handlers behave.

Regression target: ``KEY_RELEASE(0, 0)`` / ``hid.release_all`` panic-stop
must release held MOUSE buttons, not just keyboard keys (the documented
spec §3.3 contract). A button held by ``MOUSE_BUTTON_DOWN`` was previously
left physically pressed because the branch only called
``keyboard.release_all()``.
"""
from __future__ import annotations

import importlib.util
import sys
import types
from pathlib import Path

from clawtouch_hid_protocol import (
    MouseButton,
    build_key_release,
    build_mouse_button_down,
)

_REPO_ROOT = Path(__file__).resolve().parent.parent
_FIRMWARE_CODE = _REPO_ROOT / "firmware" / "code.py"


def _install_adafruit_hid_stubs() -> None:
    """Register minimal ``adafruit_hid`` stubs so ``code.py`` imports under
    CPython. The executor under test receives mock keyboard/mouse objects,
    so these stubs only need to satisfy module-load references
    (``MOUSE_BUTTON_MAP`` reads ``Mouse.*_BUTTON``; ``_collect_keys`` reads
    ``Keycode.*``). ``setdefault`` keeps a real adafruit_hid if present."""
    pkg = types.ModuleType("adafruit_hid")
    pkg.__path__ = []  # mark as a package

    mouse_mod = types.ModuleType("adafruit_hid.mouse")

    class Mouse:
        LEFT_BUTTON = 0x01
        RIGHT_BUTTON = 0x02
        MIDDLE_BUTTON = 0x04

    mouse_mod.Mouse = Mouse

    kbd_mod = types.ModuleType("adafruit_hid.keyboard")

    class Keyboard:  # not instantiated at module load (only inside _main)
        def __init__(self, *a, **k): ...

    kbd_mod.Keyboard = Keyboard

    keycode_mod = types.ModuleType("adafruit_hid.keycode")

    class Keycode:
        LEFT_CONTROL = 0xE0
        LEFT_SHIFT = 0xE1
        LEFT_ALT = 0xE2
        LEFT_GUI = 0xE3

    keycode_mod.Keycode = Keycode

    layout_mod = types.ModuleType("adafruit_hid.keyboard_layout_us")

    class KeyboardLayoutUS:
        def __init__(self, *a, **k): ...

    layout_mod.KeyboardLayoutUS = KeyboardLayoutUS

    sys.modules.setdefault("adafruit_hid", pkg)
    sys.modules.setdefault("adafruit_hid.mouse", mouse_mod)
    sys.modules.setdefault("adafruit_hid.keyboard", kbd_mod)
    sys.modules.setdefault("adafruit_hid.keycode", keycode_mod)
    sys.modules.setdefault("adafruit_hid.keyboard_layout_us", layout_mod)


def _load_firmware_module():
    _install_adafruit_hid_stubs()
    spec = importlib.util.spec_from_file_location("clawtouch_fw_code", _FIRMWARE_CODE)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


fw = _load_firmware_module()


class _RecKeyboard:
    def __init__(self):
        self.release_all_calls = 0
        self.pressed = []
        self.released = []

    def press(self, *keys):
        self.pressed.append(keys)

    def release(self, *keys):
        self.released.append(keys)

    def release_all(self):
        self.release_all_calls += 1


class _RecMouse:
    def __init__(self):
        self.release_all_calls = 0
        self.pressed = []
        self.released = []

    def press(self, button):
        self.pressed.append(button)

    def release(self, button):
        self.released.append(button)

    def release_all(self):
        self.release_all_calls += 1

    def move(self, **kw): ...

    def click(self, button): ...


def _make_executor():
    kbd, mouse = _RecKeyboard(), _RecMouse()
    ex = fw.HidExecutor(kbd, mouse, layout=None, serial_out=None)
    return ex, kbd, mouse


def test_module_imports_off_device():
    """Sanity: the _ON_DEVICE guard kept the hardware loop from running."""
    assert fw._ON_DEVICE is False


def test_panic_stop_releases_mouse_buttons():
    """REGRESSION: KEY_RELEASE(0, 0) must release held mouse buttons, not
    just keyboard keys. Hold the left button (drag start), then panic-stop."""
    ex, kbd, mouse = _make_executor()

    ex.process_packet(build_mouse_button_down(MouseButton.LEFT, seq_id=1).serialize())
    assert len(mouse.pressed) == 1  # a button is physically held

    ex.process_packet(build_key_release(seq_id=2).serialize())  # (0,0) panic stop
    assert kbd.release_all_calls == 1
    assert mouse.release_all_calls == 1  # <-- was 0 before the fix (the bug)


def test_panic_stop_releases_mouse_even_with_no_keys_held():
    ex, kbd, mouse = _make_executor()
    ex.process_packet(build_key_release(seq_id=1).serialize())
    assert mouse.release_all_calls == 1


def test_targeted_key_release_does_not_touch_mouse():
    """A non-panic KEY_RELEASE(modifiers, keycode) releases only those keys
    and must NOT release the mouse."""
    ex, kbd, mouse = _make_executor()
    # modifiers=0x01 (Ctrl) is non-zero -> else branch, not the panic path
    ex.process_packet(build_key_release(keycode=0, modifiers=0x01, seq_id=1).serialize())
    assert mouse.release_all_calls == 0
    assert kbd.released  # at least one targeted key release recorded


# ── v1.2: absolute pointer (MOUSE_MOVE_ABS 0x15) ──

import json  # noqa: E402
import re  # noqa: E402

from clawtouch_hid_protocol import (  # noqa: E402
    CommandType,
    ErrorCode,
    HidCommand,
    build_mouse_move_abs,
)


class _RecSerial:
    def __init__(self):
        self.frames = []

    def write(self, data):
        self.frames.append(HidCommand.deserialize(bytes(data)))


class _RecAbsPointer:
    def __init__(self):
        self.reports = []

    def send_report(self, report):
        self.reports.append(bytes(report))


def _make_abs_executor(with_abs=True):
    out = _RecSerial()
    ptr = _RecAbsPointer() if with_abs else None
    ex = fw.HidExecutor(_RecKeyboard(), _RecMouse(), layout=None,
                        serial_out=out, abs_pointer=ptr)
    return ex, out, ptr


def test_move_abs_sends_one_report_and_acks():
    ex, out, ptr = _make_abs_executor()
    ex.process_packet(build_mouse_move_abs(16387, 3, seq_id=9).serialize())
    # [buttons=0][x LE][y LE] - the 5-byte input report the descriptor declares
    assert ptr.reports == [bytes([0x00, 0x03, 0x40, 0x03, 0x00])]
    assert out.frames[-1].cmd_type == CommandType.ACK
    assert out.frames[-1].seq_id == 9


def test_move_abs_without_pointer_answers_like_old_firmware():
    """code.py 1.2 under a pre-1.2 boot.py has no absolute pointer. It must
    answer exactly as a pre-1.2 firmware answers an unknown opcode, so the
    host takes one fallback path for both."""
    ex, out, _ = _make_abs_executor(with_abs=False)
    ex.process_packet(build_mouse_move_abs(100, 100, seq_id=3).serialize())
    err = out.frames[-1]
    assert err.cmd_type == CommandType.ERROR
    assert err.payload[0] == ErrorCode.UNKNOWN_COMMAND
    assert err.payload[1:] == b"0x15"  # what the generic unknown branch sends


def test_move_abs_rejects_out_of_range_without_moving():
    ex, out, ptr = _make_abs_executor()
    frame = HidCommand(CommandType.MOUSE_MOVE_ABS, bytes([0x00, 0x80, 0x00, 0x00]), 4)
    ex.process_packet(frame.serialize())
    assert ptr.reports == []
    assert out.frames[-1].payload[0] == ErrorCode.INVALID_PAYLOAD


def test_move_abs_rejects_short_payload():
    ex, out, ptr = _make_abs_executor()
    ex.process_packet(HidCommand(CommandType.MOUSE_MOVE_ABS, bytes([1, 2]), 6).serialize())
    assert ptr.reports == []
    assert out.frames[-1].payload[0] == ErrorCode.INVALID_PAYLOAD


def test_status_reports_abs_cap_only_when_present():
    for with_abs, expected in ((True, ["abs"]), (False, None)):
        ex, out, _ = _make_abs_executor(with_abs=with_abs)
        ex.process_packet(HidCommand(CommandType.STATUS_REQUEST, b"", 1).serialize())
        info = json.loads(out.frames[-1].payload.decode("utf-8"))
        assert info["fw_ver"] == fw.FIRMWARE_VERSION
        assert info.get("caps") == expected


class _Dev:
    def __init__(self, page, usage):
        self.usage_page, self.usage = page, usage


def test_find_abs_pointer_is_the_second_mouse():
    kbd, rel, abs_ = _Dev(1, 6), _Dev(1, 2), _Dev(1, 2)
    assert fw.find_abs_pointer((kbd, rel, abs_)) is abs_
    assert fw.find_abs_pointer((kbd, rel)) is None  # pre-1.2 boot.py


def _abs_block(path):
    text = (_REPO_ROOT / "firmware" / path).read_text(encoding="utf-8")
    m = re.search(r"ABS_POINTER = usb_hid\.Device\((.*?)\n\)\n", text, re.S)
    assert m, f"no ABS_POINTER block in {path}"
    return m.group(1)


def test_dev_and_production_boot_declare_the_same_abs_pointer():
    """Both boot files carry the descriptor inline (boot.py cannot rely on
    an extra module being copied). A drift would make the production
    firmware behave differently from the one that was tested."""
    assert _abs_block("boot.py") == _abs_block("boot_production.py")


def test_abs_descriptor_matches_the_handler():
    """The descriptor's report must be the 5 bytes the handler packs: one
    button byte, then 16-bit X and Y with logical max 32767."""
    block = _abs_block("boot.py")
    assert "report_ids=(4,)" in block and "in_report_lengths=(5,)" in block
    assert "0x26, 0xFF, 0x7F" in block  # Logical Maximum (32767)
    assert "0x75, 0x10" in block and "0x95, 0x02" in block  # 2 x 16 bits
