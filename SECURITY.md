# Security Policy

This repository contains **firmware** for a USB HID device and the
**Python definition** for its wire protocol. A bug in either could let
an attacker:

- send a crafted byte sequence over USB-CDC that crashes the firmware
  (parser DoS), forcing a power-cycle;
- bypass the v1.0 checksum and have malformed frames execute as if
  they were valid;
- exhaust Pico RAM by feeding payloads at the `MAX_PAYLOAD_LEN`
  boundary in a tight loop;
- (theoretically) trigger arbitrary HID reports on the host OS via a
  malicious local process that opens the CDC port.

Note: the host process that opens the CDC port already has full HID
access to the OS — the firmware is not a security boundary against a
malicious host. The boundary is between **firmware ↔ a well-behaved
host process** (e.g. `clawtouch-mcp`).

## Supported versions

Only the **latest 1.x firmware + 1.x protocol module** receive
security fixes. The wire protocol v1.0 baseline is frozen
(2026-03-15) — any subsequent revisions (v1.1 added drag opcodes
2026-05-28, future v1.2+ will follow the same pattern) only add new
opcodes inside the existing frame envelope. v1.0 opcodes never get
renumbered; old hosts keep working against newer firmware.

## How to report

Email **`support@tinqiao.com`** with subject prefix `[SECURITY]
clawtouch-hid`.

Please include:

- Firmware version (printed at boot on the CDC console channel).
- Protocol-module version (`pip show clawtouch-hid-protocol`).
- A minimal reproduction (byte sequence + expected vs actual
  behavior).
- The impact you observed.
- Whether you intend to publish a CVE / blog post and your preferred
  disclosure timeline.

We'll acknowledge within **3 business days**.

## What is NOT in scope

- **Physical access to the device.** Anyone with the device can
  re-flash it; that's a feature, not a bug.
- **Behavior of agents / scripts that use this hardware.** If a
  Claude / OpenClaw / Hermes agent uses the HID device to do something
  the user didn't intend, that's an agent / prompt issue, not a
  firmware bug — so it is out of scope for *this* vulnerability-
  reporting policy. It is still a real deployment risk: see the
  **Safety** section in this repo's [README](README.md) and
  the fuller disclosure + operator mitigations in the
  [`clawtouch-mcp` README](https://github.com/tinqiao-oss/clawtouch-mcp/blob/master/README.md).

## Disclosure

After a fix is released, we'll credit the reporter in the patch
release notes unless they request anonymity. Reports that turn out to
be intended behavior get a polite reply and a thank-you.
