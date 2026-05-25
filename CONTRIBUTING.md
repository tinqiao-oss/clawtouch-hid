# Contributing to clawtouch-hid

Thanks for your interest. This repository contains **firmware + a
frozen wire protocol** — different rules apply than for a typical
application repo. Knowing what we will and won't take a PR for saves
everyone's time.

## What we welcome

- **Documentation improvements** — typos, clarifications,
  flash-guide updates for new CircuitPython versions, README
  translations (non-English).
- **Hardware compatibility reports** — issues describing whether the
  firmware works on other RP2350 boards (Adafruit Feather RP2350,
  custom carriers). Include `boot.py` / `code.py` patches if needed,
  board photos, and dmesg / device-manager output.
- **Alternative protocol-module bindings** — `clawtouch_hid_protocol`
  is the canonical Python one; we'd happily link to Rust / Go / TS
  ports from the README. Open an issue and we'll discuss the
  cross-link rather than vendoring the binding here.
- **`packet_parser.py` improvements** — better resync, faster byte
  loops, fuzzing harnesses. The parser is the most fragile part of the
  firmware; tighten it.
- **Test additions** under `tests/` — adversarial byte streams,
  corruption patterns, edge cases.

## What we won't take

- **Breaking v1.0 protocol changes.** The frame layout (header /
  seq:u16 / cmd:u8 / plen:u16 / payload / csum:u8) and command opcodes
  are frozen as of 2026-03-15. We will close such PRs without review.
  New capabilities arrive as new opcodes inside the same envelope.
- **Application-level features** in the firmware — input pacing,
  behavior modeling, multi-step flows. Firmware translates frames to
  HID reports; nothing else. Higher logic lives on the host.
- **Renumbering of existing opcodes** to "make them more sensible".
  The numbers are the spec. The Python `IntEnum` names exist only for
  readability.
- **Vendor lock-in to a specific commercial HID library** in the
  firmware — `adafruit_hid` is bundled because it's MIT and battle-
  tested; we won't swap it for something with a stricter license.

## Development setup (hardware-free)

You can develop and test the protocol module + parser on any PC, no
Pico required:

```bash
git clone https://github.com/tinqiao-oss/clawtouch-hid
cd clawtouch-hid
python -m venv .venv
.venv/bin/activate                              # or .venv\Scripts\activate on Windows
pip install -e .
pip install pytest
pytest tests/ -q                                # 24 tests, ~0.1s
```

For firmware changes you'll need an actual Pico 2 + CircuitPython
10.x — see [docs/flash-guide.md](docs/flash-guide.md).

## PR checklist

Before opening a PR:

- [ ] `pytest tests/ -q` passes locally.
- [ ] Protocol-layer change? Updated **all three** sources of truth at
  once: `clawtouch_hid_protocol/protocol.py`, `firmware/code.py` (or
  parser), and `docs/protocol-v1.md`. The test suite enforces this.
- [ ] Firmware change touching `boot.py` / `code.py`? Tested on real
  Pico 2 hardware and noted board revision + CircuitPython version in
  the PR description.
- [ ] CHANGELOG.md `[Unreleased]` section has a one-line entry.

## Security

If you find a security issue — especially one that lets an attacker
inject HID reports via crafted protocol frames, bypass the checksum,
or trigger a parser DoS — please **do not** open a public issue.

See [SECURITY.md](SECURITY.md) for the private reporting process.

## License

By submitting a contribution you agree it is licensed under MIT (the
project license). No CLA, no copyright assignment. Your name stays on
your commits.

Adafruit's bundled HID library remains under MIT — see [NOTICE](NOTICE)
for full third-party attribution.
