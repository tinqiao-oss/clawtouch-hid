# Changelog

All notable changes to `clawtouch-hid` (firmware + protocol module) are
documented here.

Wire-protocol changes follow a **frozen v1.0 baseline** — new commands
arrive as new opcodes inside the same envelope, never as breaking
edits to existing ones. The `clawtouch-hid-protocol` Python package
tracks the protocol version; the firmware version is tagged
separately on each release.

## [1.1.2] — 2026-05-31 — Panic-stop releases mouse buttons (firmware fix)

### Fixed — firmware

- `KEY_RELEASE(0, 0)` / `hid.release_all` (panic stop) now releases held
  **mouse buttons** as well as keyboard keys. The all-zero panic-stop
  branch previously called only `keyboard.release_all()`, so a button
  held via `MOUSE_BUTTON_DOWN` (drag start) — or stuck mid-drag if the
  host process died before its `MOUSE_BUTTON_UP` — stayed physically
  pressed, contradicting the documented spec §3.3 panic-stop contract
  and the `hid.release_all` description. The firmware now also calls
  `mouse.release_all()` on that branch.
- Added a firmware-side handler regression test
  (`tests/test_firmware_handlers.py`). The executor is now importable
  under CPython (board modules guarded by `_ON_DEVICE`, the hardware
  loop wrapped in `_main()`), so the panic-stop contract is verified
  without flashing. On-device behaviour is byte-for-byte unchanged.

Firmware only — **wire protocol unchanged (still v1.1)**,
`hid_firmware_min` stays `1.0.0`. Old hosts unaffected; flashing
firmware 1.1.2 is a recommended (non-breaking) upgrade.

## [1.1.1] - 2026-05-29
### Changed (BREAKING vs <= 1.1.0)
- Unified keyboard payload byte order to `[modifiers, keycode]`. KEY_PRESS (0x20) and KEY_RELEASE (0x21) previously used `[keycode, modifiers]`; they now match KEY_COMBO (0x23) and the USB HID keyboard report layout (modifier byte first). Breaking wire change for KEY_PRESS/KEY_RELEASE vs firmware <= 1.1.0 — flash firmware 1.1.1 in lockstep. Pre-publish correction; the protocol has not been publicly released.

## [1.1.0] — 2026-05-28 — Independent mouse button press/release (drag gestures + CUA compatibility)

### Added — protocol v1.1: `MOUSE_BUTTON_DOWN` (0x13) / `MOUSE_BUTTON_UP` (0x14)

Two new opcodes let a host program press a mouse button without
immediately releasing it (and release without pressing). v1.0
`MOUSE_CLICK` is atomic (press + release in one frame) and remains
unchanged — old hosts keep working.

Wire payload for both: single byte `[button:u8]`, same encoding as
`MOUSE_CLICK` (`0x01` LEFT / `0x02` RIGHT / `0x04` MIDDLE).

**Why this exists**:
- A *drag* in the physical sense is `BUTTON_DOWN` → one or more `MOUSE_MOVE`
  → `BUTTON_UP`. With only `MOUSE_CLICK` (atomic press+release), a host
  could not produce a drag at the wire layer.
- The Anthropic Computer Use action set includes `left_mouse_down` /
  `left_mouse_up` / `left_click_drag`. v1.1 lets a `clawtouch-mcp`
  server bridge those actions one-for-one. See
  `clawtouch-mcp` v0.3.0 release notes for the corresponding tool
  surface (`hid.mouse_button_down`, `hid.mouse_button_up`, `hid.drag`).

**Firmware semantics**:
- `BUTTON_UP` on a button that wasn't pressed is a **no-op** (idempotent,
  no error). This matches HID Boot Mouse behaviour and avoids spurious
  `ERR_INVALID_PAYLOAD` when a host releases defensively.
- `KEY_RELEASE(0, 0)` (release-all) still releases held mouse buttons —
  panic-stop semantics from v1.0 unchanged.

**Spec status**: v1.1 — additive over v1.0 frozen baseline. v1.0
opcodes are byte-for-byte stable forever (no renumbers, no payload
edits). Hosts speaking v1.0 keep working against v1.1 firmware; hosts
speaking v1.1 against v1.0 firmware get `ERR_UNKNOWN_COMMAND` (0x01) on
the new opcodes and can fall back to `MOUSE_CLICK`.

### Changed

- `clawtouch_hid_protocol.PROTOCOL_VERSION`: `1.0.0` → `1.1.0`
- Firmware version: `1.0.2` → `1.1.0` (both `firmware/code.py` and the
  deploy package's `code.py` synced)
- `docs/protocol-v1.{md,zh-CN.md}`: §3.2 Mouse table gains two rows
  with `Since v1.1`; new sub-section spells out the drag composition
  pattern and idempotent-release semantics
- README "Wire protocol at a glance": "Thirteen command codes" →
  "Fifteen command codes" (English + Chinese)
- New protocol roundtrip tests
  (`test_mouse_button_down_v11` / `test_mouse_button_up_v11` /
  `test_mouse_button_opcodes_locked_at_13_14`) — lock the 0x13/0x14
  opcode numbering so any future renumber breaks CI

## [Unreleased]

### Added — Related Work section in README (EN + zh-CN)

New `## Related work` / `## 相关工作` section between "Open source
roadmap" and "FAQ" positions this repo against
[PiKVM Pico HID](https://docs.pikvm.org/pico_hid/),
[`sjmf/kvm-serial`](https://github.com/sjmf/kvm-serial) +
[`sunasaji/mcp-serial-hid-kvm`](https://github.com/sunasaji/mcp-serial-hid-kvm)
(the closest direct architectural peer — fixed-function ASIC instead
of user-modifiable Pico firmware), and CMU's
[HIDAgent](https://arxiv.org/abs/2602.00492) (closest peer in hardware
budget and design intent). Avoids any "first / only" claims that would
ignore prior art.

### Fixed — README typo (external audit, codex)

- `README.md:169` — protocol summary said "Twelve command codes" but
  the `CommandType` enum defines **thirteen** opcodes (PING, PONG,
  MOUSE_MOVE, MOUSE_CLICK, MOUSE_SCROLL, KEY_PRESS, KEY_RELEASE,
  KEY_TYPE_STRING, KEY_COMBO, STATUS_REQUEST, STATUS_RESPONSE, ACK,
  ERROR). `README.md:216` already says "13 command opcodes"; this fix
  makes line 169 consistent.

### Fixed — internal deep audit (round 4)

A clean-up audit (four parallel agents, no specific external prompt)
surfaced ~5 firmware / spec issues on top of codex rounds 1-3. All
fixed in this commit.

- **`firmware/packet_parser.py::_try_extract` converted from
  recursion to iteration.** A noisy CDC line — or an attacker
  streaming N consecutive bogus `0xAA` headers each with
  `plen > MAX_PAYLOAD_LEN` — used to recurse N times via the
  `pop(0) → return self._try_extract()` tail call. CircuitPython
  has no `sys.setrecursionlimit` lever and the Pico's stack is
  tiny; ~1000 bogus headers in a burst produced `RecursionError`
  and locked the firmware. Now: single `while True:` loop with
  O(1) call depth. Also swapped `bytearray.pop(0)` (O(N) memmove
  per byte) for `bytearray.find(HEADER)` + slice — drops the
  resync cost on a K-byte garbage prefix from O(K²) to O(K).
- **`firmware/code.py::process_packet` now mandatorily verifies
  checksum.** The `if len(data) >= 7 + payload_len:` gate used to
  skip checksum verify for truncated frames and silently dispatch
  a (sliced-short) payload. The main loop guarded this in
  practice, but `process_packet` is a public method also called
  from tests. Truncated frames now return
  `ERR_INVALID_PAYLOAD` ("Truncated").
- **`KEY_TYPE_STRING` UTF-8 decode failures now return the correct
  error code.** A malformed payload used to raise `UnicodeDecodeError`,
  caught by the generic wrapper as `ERR_EXECUTION_TIMEOUT` — hosts
  treated it as a transient firmware stall and retried. Spec §3.3
  says malformed payload is `ERR_INVALID_PAYLOAD`; now reported as
  such, with explicit `try/except UnicodeDecodeError`.
- **`MOUSE_CLICK` unknown button code now returns an error instead
  of silently defaulting to LEFT.** `MOUSE_BUTTON_MAP.get(button_code,
  Mouse.LEFT_BUTTON)` used to swallow any garbage button code and
  ACK a left click — host thought its right-click landed when
  actually a left-click happened. Now: unknown button → no click,
  `ERR_INVALID_PAYLOAD` returned to host.
- **`examples/ping_test.py::_PICO_PIDS` set was dead code:** the
  `or p.pid is not None` clause downstream accepted any non-None
  PID, so the curated set was never consulted. Comment kept; the
  set is now a docstring-only reference matching `bridge.py`'s
  "VID-only" stance.

(Companion fix on the host side: `clawtouch-mcp` v0.2.4 wires the
`ErrorCode` returned by these handlers into its `last_error_detail`
diagnostic so the agent sees the specific code name instead of a
bare `ok=False`. See the matching CHANGELOG entry there.)

### Documented — firmware is relative-only (codex round 3 P0/P1 #1)

- **`firmware/code.py` `_handle_mouse_move` flag semantics clarified.**
  Protocol v1 §3.2 previously read "bit0 = 1 relative, bit0 = 0
  absolute" — but USB HID Boot Mouse (which this firmware
  implements) has no absolute-coordinate report, so the firmware
  always treated `(x, y)` as a relative delta no matter what bit0
  said. This is now documented as the v1.0 invariant in both
  `docs/protocol-v1.md` (English) and `docs/protocol-v1.zh-CN.md`
  (Chinese): bit0 is reserved at the wire-format level for a future
  firmware revision that targets an HID Digitizer profile, but the
  v1.0 firmware ignores it. Absolute interpretation moves to the
  host side — `clawtouch-mcp` v0.2.4 (next release) queries the OS
  cursor and converts to a delta before sending. The firmware code
  path drops the `flags` value with an explicit `del flags` and a
  block comment, so static analysis won't flag it as an unused
  binding and future maintainers see the design rationale inline.
- **`docs/protocol-v1.md` and `docs/protocol-v1.zh-CN.md`** updated
  to reword the MOUSE_MOVE flags table and to note that MOUSE_CLICK
  bit0 = double-click is now correctly emitted by the firmware as
  two back-to-back `mouse.click` reports (see the round-3 fix above).

### Fixed — second-pass code audit (codex round 3)

- **`firmware/code.py` — MOUSE_CLICK `flags` bit0 (double-click) was
  silently dropped.** Protocol v1 §3.2 defines `bit0 = double-click`,
  but the handler parsed `flags` and never branched on it, so
  `hid.click(double=true)` was a silent single click. Now: if
  `flags & 0x01`, the handler emits a second `mouse.click(button)`
  after the first.
- **`examples/ping_test.py` — `auto_detect_port()` opened the REPL
  console of a dual-CDC Pico, not the data channel.** The function
  used to return the first matching port from `comports()` ordering,
  which on every OS exposes the lower-numbered (console) CDC
  interface first; the framed PING then hit the REPL and timed out.
  Now mirrors the dual-CDC handling that `clawtouch-mcp`'s
  `list_pico_ports()` already does — group by `serial_number`,
  return the highest-numbered port within the first group, fall back
  gracefully on single-CDC firmwares.
- **`NOTICE` — Adafruit bundle dates corrected + SHA-256 reproducibility
  table added.** Previous text claimed v6.1.10 was the "most recent
  release as of 2024-04-23"; per PyPI v6.1.10 actually shipped
  2026-04-23, and our bundle (on or about 2026-03-20) predates it —
  the closest tagged PyPI release at bundle time was v6.1.8
  (2025-10-20). The exact upstream commit was not recorded at
  vendoring time, so the NOTICE now: (a) lists the four nearby PyPI
  release dates inline as a timeline; (b) records the byte-level
  SHA-256 of each bundled `.mpy` file so future maintainers can
  bisect the upstream commit if needed.

### Terminology

- **Outward-facing copy: "LLM agent" → "AI agent"** in the README
  Scope · Accessibility use case and the `## About` section. Tracks
  the broader 2025 industry shift to "AI agent" as the default
  outward-facing term (Anthropic / OpenAI / Cursor / Cline all
  defaulted to it during 2024-2025).
- **Technical / cross-link copy unchanged.** "LLM agents" retained
  in the `clawtouch-skills` cross-link row on the Open source
  roadmap (matches the skills repo's internal wording, since
  markdown skills are LLM-specific by design).

### Docs trim

- Removed redundant `🌐 clawtouch.cn` top-of-README link line.
- Removed the "🎥 a real screen-recording GIF will land here..."
  placeholder under `## See it in action`. The annotated REPL
  transcript stands on its own; no GIF promise to deliver on.
- Removed the "Star the org @tinqiao-oss to follow new releases."
  sentence under `## Open source roadmap` — boilerplate, no info.
- Rewrote the `## Hardware` purchase sentence. Was "You can buy
  the turnkey ClawTouch device at clawtouch.cn, or grab a bare
  Pico 2..." — the turnkey device is currently B2B-only and not
  generally retail-available, so the parallel "or grab a Pico"
  framing was misleading. Now reads "use any RP2350 board (e.g.
  a Raspberry Pi Pico 2 from electronics retailers), flash this
  firmware..." with a clean separation between this OSS path and
  the separate commercial product.
- **Added `clawtouch-skills` row to the `## Open source roadmap`
  table** — was missing in this repo (present in `clawtouch-mcp`'s
  roadmap table). Now all three open repos are listed in all
  three READMEs consistently.

### Visual / docs uplift

- **`docs/assets/hero.svg`** — flat-design hero diagram (host
  program → Pico 2 + firmware → target OS) embedded at the top of
  the English and Chinese READMEs. The right pane shows the frozen
  v1.0 wire frame layout (preamble / seq / cmd / plen / payload /
  csum) at a glance, with `Pico 2 + firmware` highlighted as the
  this-repo node.
- **New `## See it in action` section.** Annotated Python REPL
  transcript using `clawtouch-hid-protocol` + `pyserial` against a
  real Pico 2: PING/PONG handshake (with the 7 hex bytes of the
  outgoing frame called out byte-by-byte for orientation), one
  `MOUSE_CLICK`, one `KEY_TYPE_STRING`. Acts as a text-based demo
  until a real screen-recording GIF lands.

### Compliance — second-pass audit (codex round 2)

A follow-up codex audit on the first compliance pass surfaced six
issues, all fixed below. The compliance scope is unchanged; wording
and packaging metadata are now stricter:

- **`## Acceptable use` reworded to scope-of-support, not a use
  restriction.** Replaced "you may not flash or configure it to"
  with "this project does not support, document, or assist with".
  Added an explicit sentence that the section describes maintainer
  support scope only and is **not** an additional restriction on
  top of the MIT License's grant of code-level rights. Avoids the
  "MIT + use ban" structural conflict.
- **PRC Anti-Unfair Competition Law Art. 13 dating corrected.**
  Was "as amended 2025-10-15", which conflates promulgation and
  effective dates. Now reads "promulgated 2025-06-27, effective
  2025-10-15" (the latter is when the amendment takes effect, per
  the SPC publication). The substantive description was also
  broadened from the narrow "improper acquisition of others' data"
  to the statutory phrasing covering circumvention of technical
  management measures, fraud, and coercion as means.
- **`firmware/lib/adafruit_hid/LICENSE` added** — the upstream MIT
  license text for the bundled Adafruit CircuitPython HID library
  (Copyright (c) 2017 Scott Shawcroft for Adafruit Industries),
  reproduced verbatim from
  https://github.com/adafruit/Adafruit_CircuitPython_HID/blob/main/LICENSE.
  Required by the MIT license's attribution clause for
  redistributions and previously absent from this repo (NOTICE
  mentioned it but the actual license text was not bundled).
- **`NOTICE` expanded for the Adafruit bundle.** Added: upstream
  copyright holder name (Scott Shawcroft for Adafruit Industries),
  SPDX identifier, vendoring date (on or about 2026-03-20),
  reference to the closest upstream stable release at that time
  (v6.1.10, 2024-04-23), the complete list of bundled `.mpy` files,
  the relative path to the bundled LICENSE copy, and a note asking
  contributors to retain the LICENSE when refreshing the bundle.
- **`pyproject.toml` upgraded to PEP 639 license metadata.** Replaced
  `license = { text = "MIT" }` (deprecated table form) with
  `license = "MIT"` (SPDX expression). Added `license-files =
  ["LICENSE", "LICENSE.zh-CN.md", "NOTICE", "TRADEMARKS.md"]` so the
  four root-level legal documents ship in the PyPI sdist/wheel
  `.dist-info/` directory. (The bundled
  `firmware/lib/adafruit_hid/LICENSE` is intentionally excluded — the
  `firmware/` tree is excluded from the PyPI distribution and the
  file ships with the GitHub source tree only.) Bumped
  `setuptools>=77` (PEP 639 baseline). Removed the legacy
  `License :: OSI Approved :: MIT License` classifier per PyPA's PEP
  639 migration guidance.
- **TRADEMARKS — owned-mark policy reworded to separate copyright
  and trademark grants.** The previous "interoperability under the
  frozen v1.0 spec is permitted under MIT" wording was ambiguous and
  could be read as making implementation rights flow from the
  trademark notice. Now states explicitly that MIT grants full
  commercial rights to the source code (including the right to
  implement the wire protocol in third-party firmware), that the
  marks are governed separately by trademark law, and that the only
  practical constraint on commercial firmware distributions is the
  trademark / naming requirement (do not call it "ClawTouch HID
  firmware" without permission, do not imply endorsement).
- **TRADEMARKS — official mark-owner attribution statements added.**
  New `### Official trademark attribution` subsection cites the
  attribution wording requested by Raspberry Pi Ltd., Adafruit
  Industries, USB Implementers Forum, Microsoft, Apple, Linus
  Torvalds (Linux), and Anthropic per their respective trademark
  policies. Bilingual (English + 简体中文).

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
  (same as `KEY_PRESS`) cannot silently regress. (The shared keyboard
  byte order was later unified to `[modifiers, keycode]` in 1.1.1 —
  see the entry at the top of this file.)

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

### Keyboard payload byte order

`KEY_PRESS` (0x20) and `KEY_RELEASE` (0x21) used payload
`[keycode, modifiers]` in this release, while `KEY_COMBO` (0x23) used
`[modifiers, keycode]`. (This pre-publish inconsistency was later
unified to `[modifiers, keycode]` across all three keyboard commands
in 1.1.1 — see the entry at the top of this file.)

[Unreleased]: https://github.com/tinqiao-oss/clawtouch-hid/compare/v1.1.2...HEAD
[1.1.2]: https://github.com/tinqiao-oss/clawtouch-hid/compare/v1.1.1...v1.1.2
[1.1.1]: https://github.com/tinqiao-oss/clawtouch-hid/compare/v1.1.0...v1.1.1
[1.1.0]: https://github.com/tinqiao-oss/clawtouch-hid/compare/v1.0.0...v1.1.0
[1.0.0]: https://github.com/tinqiao-oss/clawtouch-hid/releases/tag/v1.0.0
