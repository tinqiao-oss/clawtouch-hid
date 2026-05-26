# Changelog

All notable changes to `clawtouch-hid` (firmware + protocol module) are
documented here.

Wire-protocol changes follow a **frozen v1.0 contract** — new commands
arrive as new opcodes inside the same envelope, never as breaking
edits to existing ones. The `clawtouch-hid-protocol` Python package
tracks the protocol version (`1.0.0`); the firmware version is tagged
separately on each release.

## [Unreleased]

### Added

- **`TRADEMARKS.md`** — bilingual (English + 简体中文) nominative
  trademark notice covering Tinqiao-owned marks (ClawTouch, Tinqiao)
  and third-party marks referenced for descriptive purposes
  (Raspberry Pi, Pico 2, RP2350, CircuitPython, Adafruit, Claude,
  Cline, OpenClaw, Hermes, USB, Windows, macOS, Linux). PRC
  Trademark Law Art. 59 nominative-fair-use disclaimer included.
- **`LICENSE.zh-CN.md`** — non-official Chinese translation of the
  MIT License with explicit "English version prevails in case of
  conflict" disclaimer; references PRC open-source contract-law
  precedents and points to NOTICE for the bundled Adafruit HID
  library.
- **README `## Acceptable use` section** — explicit prohibition on
  bypassing target platforms' anti-fraud / risk-control / rate-limit
  measures and on operating accounts the user does not lawfully
  own; references PRC *Anti-Unfair Competition Law* Art. 13 (as
  amended 2025-10-15). Includes statement that this firmware
  contains no AI/ML model and that AI-content-labeling obligations
  attach to upstream agents, not to the firmware itself.
- **README License section** — added cross-links to
  `LICENSE.zh-CN.md` and `TRADEMARKS.md`; clarified that MIT does
  not grant trademark rights.

### Fixed

- **`build_key_release()` now matches firmware + spec.** Previously
  sent an empty payload; firmware `_handle_key_release` requires
  `len(payload) >= 2` and would reject every release frame with
  `ERR_INVALID_PAYLOAD`. New signature: `build_key_release(keycode=0,
  modifiers=0)` — both zero is the all-zero "release-all" payload the
  spec describes; non-zero values release a specific key.
- Two new locked round-trip tests in `tests/test_protocol.py` for
  release-all and release-specific so the byte-order contract
  (`[keycode, modifiers]`, same as `KEY_PRESS`) cannot silently
  regress.

### Changed

- **Docs / scope wording softened.** Rewrote scope paragraphs in both
  READMEs to describe HID input neutrally — standard driver-stack
  routing, no software on target.

## [1.0.0] — 2026-05-17 — First public release (protocol frozen 2026-03-15)

First public release of the firmware + protocol definition. The wire
protocol was frozen 2026-03-15 after internal validation; this is the
first public bundle shipping it.

### Added

- **`firmware/`** — CircuitPython 10.x firmware for Raspberry Pi Pico 2
  (RP2350). Exposes itself as composite USB device: HID keyboard +
  HID mouse + USB-CDC console + USB-CDC data. Translates framed
  protocol commands into HID reports.
- **`clawtouch_hid_protocol/`** — dependency-free Python module
  defining the v1.0 wire protocol. Pip-installable, runs on any
  Python 3.10+, no hardware required.
- **`firmware/packet_parser.py`** — hardware-free byte-stream extractor
  for unit-testing firmware logic on a PC.
- **13 command opcodes**: PING / PONG / MOUSE_MOVE / MOUSE_CLICK /
  MOUSE_SCROLL / KEY_PRESS / KEY_RELEASE / KEY_TYPE_STRING /
  KEY_COMBO / STATUS_REQUEST / STATUS_RESPONSE / ACK / ERROR.
- **5 error codes**: UNKNOWN_COMMAND / INVALID_PAYLOAD /
  CHECKSUM_MISMATCH / EXECUTION_TIMEOUT / DEVICE_BUSY.
- **Modifier aliases** — `cmd` / `win` / `gui` all map to GUI modifier,
  so the same client code works on macOS / Windows / Linux.
- **Docs**: full byte-level [protocol spec](docs/protocol-v1.md) and
  three-step [flash guide](docs/flash-guide.md), both in English and
  Chinese.
- **Tests**: 24 tests lock the v1.0 frame layout, command opcodes,
  modifier aliases, and parser state machine.

### Known limitations

- Only keyboard + mouse HID profiles — no multi-touch yet (planned).
- Wired USB-CDC transport only; wireless transports are out of scope
  for this OSS release.
- Firmware is CircuitPython-only. RP2350 MicroPython / C SDK ports
  would be welcome contributions but are not maintained upstream.

### Protocol quirk worth knowing

`KEY_PRESS` (0x20) uses payload `[keycode, modifiers]`; `KEY_COMBO`
(0x23) uses `[modifiers, keycode]`. This asymmetry is intentional
(historical) and is locked by both the spec and the test suite —
any reorder breaks the firmware silently.

[Unreleased]: https://github.com/tinqiao-oss/clawtouch-hid/compare/v1.0.0...HEAD
[1.0.0]: https://github.com/tinqiao-oss/clawtouch-hid/releases/tag/v1.0.0
