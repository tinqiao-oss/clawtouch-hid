# Changelog

All notable changes to `clawtouch-hid` (firmware + protocol module) are
documented here.

Wire-protocol changes follow a **frozen v1.0 contract** — new commands
arrive as new opcodes inside the same envelope, never as breaking
edits to existing ones. The `clawtouch-hid-protocol` Python package
tracks the protocol version (`1.0.0`); the firmware version is tagged
separately on each release.

## [Unreleased]

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
