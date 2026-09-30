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
