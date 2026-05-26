**English** | [简体中文](README.zh-CN.md)

# clawtouch-hid

> **The open hardware layer of ClawTouch.**
> CircuitPython firmware for a Raspberry Pi Pico 2, the frozen USB-CDC wire
> protocol it speaks, and a Python definition module for hosts that want to
> drive the board directly.

🌐 **[clawtouch.cn](https://clawtouch.cn)** — official site for hardware, docs, and commercial inquiries.

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Protocol: v1.0 (frozen)](https://img.shields.io/badge/protocol-v1.0_frozen-blue.svg)](docs/protocol-v1.md)
[![CircuitPython 10.x](https://img.shields.io/badge/CircuitPython-10.x-purple.svg)](https://circuitpython.org/)
[![Commercial: clawtouch.cn](https://img.shields.io/badge/commercial-clawtouch.cn-orange.svg)](https://clawtouch.cn)

---

## What is this?

This repository contains three things that together let a Raspberry Pi Pico 2
become a "ClawTouch HID device" — a USB-attached keyboard / mouse that an
external program (running on your PC) can drive over a serial command channel:

1. **`firmware/`** — the CircuitPython firmware that runs on the Pico 2. It
   exposes itself to the host operating system as a composite USB device:
   a HID keyboard + HID mouse + a USB-CDC serial pair. The firmware does
   **nothing on its own** — it waits for framed commands on the CDC data port
   and translates each one into a HID report.
2. **`clawtouch_hid_protocol/`** — a small, dependency-free Python module
   that defines the frozen v1.0 wire protocol (command codes, payload
   layouts, frame helpers). Use it from your own host program if you want
   to talk to the board directly without going through MCP or any other
   layer.
3. **`docs/`** — the [frozen v1.0 protocol specification](docs/protocol-v1.md)
   and a step-by-step [flash guide](docs/flash-guide.md).

The board is also the hardware that the [clawtouch-mcp](https://github.com/tinqiao-oss/clawtouch-mcp)
MCP server talks to. If all you want is "let Claude Desktop drive a real
mouse and keyboard," start there — you don't need to read any of this. This
repo is for **firmware hackers, protocol auditors, and anyone who wants to
build their own host stack on top of the same hardware**.

> 📦 MIT-licensed. No backend, no LLM, no agent logic on top — just the
> wire protocol and the firmware that speaks it.

## Why a physical HID device?

Most "AI controls your computer" demos run inside a sandbox or inject
synthetic events through OS-level APIs. Those paths don't apply in
locked-down kiosks, embedded test harnesses, or cross-machine RPA where
the target machine must stay clean. A USB HID peripheral routes input
through the standard OS HID driver stack — the same path as any plug-in
keyboard or mouse — and needs zero software installed on the target.
The firmware in this repository is the smallest amount of code that
turns a $8 Pico 2 into exactly that kind of peripheral.

## Scope — one device, one target

The hardware is a USB peripheral with a single host connection. The
firmware in this repo is the same — one Pico, one target machine.
That's by design. This is a **tethered control device, not a fleet
automation tool**. If you want to drive ten machines you flash ten
Picos.

Suitable for: RPA / automated testing of devices you can't install
software on, accessibility tooling (LLM agent + HID = real keyboard
for a user who can't use a regular one), cross-machine workflows
where the target machine must stay clean.

Not suitable for: mass account creation or multi-account operations on
consumer platforms (a single-host peripheral is the wrong shape; users
are responsible for applicable laws and platform policies), or
application-specific scripted shortcut layers (those belong in agent /
RPA frameworks built on top of this primitive layer).

## Acceptable use

This firmware translates host-issued protocol frames into HID
reports. It is **not** intended to, and you may not flash or
configure it to:

- Bypass, evade, or interfere with any target platform's anti-fraud,
  anti-abuse, rate-limiting, or risk-control measures.
- Operate accounts the user does not lawfully own or have explicit
  authorization to operate.
- Conduct activities prohibited by the target application's Terms
  of Service in the user's jurisdiction.
- Conduct activities that violate applicable law — including, but
  not limited to, PRC *Anti-Unfair Competition Law* Art. 13 (as
  amended 2025-10-15) on improper acquisition of others' data,
  *Personal Information Protection Law*, *Cybersecurity Law*, and
  equivalent laws in other jurisdictions.

Users are independently responsible for evaluating their specific
use case against applicable laws and the target platform's ToS.

This repository contains no AI / ML model and generates no text,
image, audio, or video content. Content-generation obligations
(e.g. PRC *AI Generated Content Labeling Measure* effective
2025-09-01) attach to whatever upstream agent drives this firmware,
not to the firmware itself.

## Hardware

| Item | Spec |
|------|------|
| Microcontroller | RP2350 (Raspberry Pi Pico 2 reference board) |
| Firmware framework | CircuitPython 10.x |
| Protocol version | v1.0 (frozen 2026-03-15) |
| USB interfaces | HID (keyboard + mouse) + CDC (console + data) |
| CDC baud rate | 115200 (data channel) |

You can buy the turnkey ClawTouch device at [clawtouch.cn](https://clawtouch.cn),
or grab a bare Pico 2 from any electronics retailer (~$8), flash it
yourself, and you have an equivalent unit.

## Quick start

1. **Flash the Pico 2 with CircuitPython** — see [docs/flash-guide.md](docs/flash-guide.md)
   for the three-step procedure (`BOOTSEL` → drop UF2 → drop firmware).
2. **Talk to it from Python** — install the host-side protocol module and
   send a `PING`:

   ```bash
   pip install clawtouch-hid-protocol pyserial
   ```

   ```python
   import serial
   from clawtouch_hid_protocol import build_ping, HidCommand

   ser = serial.Serial("COM7", 115200, timeout=2)   # use your CDC data port
   ser.write(build_ping(seq_id=1).serialize())
   resp = HidCommand.deserialize(ser.read(7))
   print(resp.cmd_type)                              # CommandType.PONG
   ```

3. **Or skip the wire protocol and use [clawtouch-mcp](https://github.com/tinqiao-oss/clawtouch-mcp)**
   — same firmware, same hardware, but exposed as a Model Context Protocol
   server that plugs straight into Claude Desktop / Cline / Continue /
   OpenClaw / Hermes.

A complete, runnable PING example lives at [`examples/ping_test.py`](examples/ping_test.py).

## Wire protocol at a glance

```
+------+--------+--------+---------+---------+----------+
| 0xAA | seq:u16| cmd:u8 | plen:u16| payload | csum:u8  |
+------+--------+--------+---------+---------+----------+
   1B     2B       1B       2B       plen       1B
```

* Little-endian for multi-byte integers.
* `csum` is the low byte of the sum of all preceding bytes.
* Maximum payload length is 1024 bytes.

Twelve command codes are defined: `PING/PONG`, `MOUSE_MOVE/CLICK/SCROLL`,
`KEY_PRESS/RELEASE/TYPE_STRING/COMBO`, `STATUS_REQUEST/RESPONSE`, plus
`ACK` and `ERROR`. Full byte-level layout in [docs/protocol-v1.md](docs/protocol-v1.md).

## Repository layout

```
clawtouch-hid/
├── clawtouch_hid_protocol/   ← Python protocol module (host-side, pip-installable)
├── firmware/                 ← CircuitPython firmware for the Pico 2
│   ├── boot.py               ← USB descriptor setup (runs once at boot)
│   ├── code.py               ← HID executor main loop
│   ├── packet_parser.py      ← Frame extractor, hardware-free for PC tests
│   └── lib/adafruit_hid/     ← Bundled HID library (MIT, see NOTICE)
├── docs/                     ← Protocol spec + flash guide (English + Chinese)
├── examples/                 ← Runnable smoke tests
├── pyproject.toml            ← Builds clawtouch-hid-protocol for PyPI
├── LICENSE                   ← MIT
├── NOTICE                    ← Third-party attribution
└── README.md / README.zh-CN.md
```

## Design philosophy

* **Firmware has no business logic.** It only translates framed bytes into
  HID reports. All decisions — what to type, when to click, how to pace
  multi-step actions — live on the host. This keeps the firmware tiny,
  auditable, and reusable across different host stacks.
* **The protocol is frozen.** v1.0 was published 2026-03-15 and is not
  changing. Future capabilities will arrive as new command codes inside
  the same envelope. Existing v1.0 commands keep working forever.
* **Protocol-by-value, not protocol-by-name.** The firmware, the
  `clawtouch_hid_protocol` module, and the protocol spec each list the
  command codes independently. The numbers are the source of truth; the
  Python names exist for readability only.

## Protocol quirk worth knowing

`KEY_PRESS` and `KEY_COMBO` use different payload byte orders:

* `KEY_PRESS` (0x20): `[keycode, modifiers]`
* `KEY_COMBO` (0x23): `[modifiers, keycode]`

This is documented behavior, not a bug — `KEY_COMBO` historically grew out
of a separate "send a shortcut" intent and kept its own layout. All three
implementations (firmware, protocol module, spec) agree. If you write a
fourth implementation, mind the order.

## Open source roadmap

ClawTouch follows an **open-core** model: hardware and protocol primitives
are open, the integrated commercial product stays closed.

| Component                                              | Status                   |
|--------------------------------------------------------|--------------------------|
| **clawtouch-hid** (this repo: firmware + protocol)     | ✅ Released              |
| **[clawtouch-mcp](https://github.com/tinqiao-oss/clawtouch-mcp)** (MCP server) | ✅ Released |
| **clawtouch-bridge-sdk** (Python + Node HID SDK)       | 🔵 Future                |
| Backend / desktop app / adapters / vision models       | 🔒 Closed source — contact `support@tinqiao.com` |

Star the org [@tinqiao-oss](https://github.com/tinqiao-oss) to follow new releases.

## FAQ

**Do I need ClawTouch's hardware to use this?**
No. A bare Raspberry Pi Pico 2 (~$8) flashed with the firmware in this
repo is a working ClawTouch HID device. The commercial product bundles
that same firmware in a nicer enclosure with QA, drop-shipping, and a
support contract — the wire protocol is identical.

**Do I need ClawTouch's backend / account / API key?**
No. Nothing in this repository talks to any network. The firmware speaks
USB to the host machine; the host speaks USB to the firmware. That is the
entire stack.

**Can I run any of this without a physical Pico?**
The `clawtouch_hid_protocol` module and `firmware/packet_parser.py` are
both hardware-free Python and run on any machine. `firmware/code.py` is
CircuitPython-only and needs the board's `usb_hid` / `usb_cdc` modules at
import time, so it cannot be run on a normal Python interpreter directly
— use the protocol module or the parser for offline tests.

**How is this different from the closed-source ClawTouch desktop app?**
This repo is the bottom layer only — raw HID primitives over a frozen
wire protocol — so other agent stacks can use ClawTouch hardware
without adopting the whole ClawTouch product. The closed-source
desktop product is a separate agent that runs on top of the same
hardware; contact `support@tinqiao.com` for details.

## Contributing

PRs are welcome for: documentation fixes, additional examples, new client
language bindings against the v1.0 protocol, English translations,
hardware compatibility reports.

We're _not_ taking PRs for: agent-loop logic or application-level
features (intentionally out of scope — firmware translates frames to
HID reports, nothing else), protocol changes that break v1.0
compatibility, or application-specific adapters (those live in the
closed-source desktop app).

## About

`clawtouch-hid` is maintained by **Tinqiao Technology** — the team behind
**ClawTouch** ([clawtouch.cn](https://clawtouch.cn)), building plug-in USB
devices that let LLM agents operate real Windows / macOS / Linux desktops
at the HID layer. This repository is the open, hardware-layer slice of
that stack.

## License

MIT © Tinqiao Technology (Beijing) Co., Ltd. — see [LICENSE](LICENSE)
(English, authoritative) and [LICENSE.zh-CN.md](LICENSE.zh-CN.md)
(non-official Chinese translation, for reference).

Third-party components bundled in this repository (the Adafruit
CircuitPython HID library) and their licenses are listed in
[NOTICE](NOTICE). Trademarks (ClawTouch, Tinqiao, and third-party
marks referenced in this repository) are covered separately in
[TRADEMARKS.md](TRADEMARKS.md) — the MIT License does **not** grant
any trademark rights.

For commercial deployments at scale, enterprise support, or OEM hardware
discussion: `support@tinqiao.com`.
