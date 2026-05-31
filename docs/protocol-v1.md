**English** | [简体中文](protocol-v1.zh-CN.md)

# ClawTouch HID Wire Protocol — Epoch 1

> **Wire epoch:** `1` — the frame envelope in §2, frozen 2026-03-15. The
> epoch is a single integer; it bumps **only** on a breaking change to the
> frame envelope or to an existing opcode's meaning (by design, almost
> never). New opcodes are added *additively within* the epoch and never
> bump it.
> **Not SemVer.** The wire protocol is identified by its epoch, not a
> `major.minor.patch`. The thing with SemVer is the `clawtouch-hid-protocol`
> Python package that *describes* this epoch (currently `1.1.1`) — and,
> separately, the firmware (currently `1.1.2`). Do not confuse epoch with
> either package version. Where older notes say "protocol v1.0 / v1.1",
> read them as **opcode-set milestones** (module releases) within epoch 1,
> not wire-protocol versions.
> **Opcode-set history within epoch 1:** baseline opcodes frozen
> 2026-03-15; `MOUSE_BUTTON_DOWN` / `MOUSE_BUTTON_UP` (`0x13` / `0x14`)
> added additively 2026-05-28 for drag gestures + Anthropic Computer Use
> parity.
> **Scope:** Host (PC) ↔ ClawTouch HID device (Raspberry Pi Pico 2)

---

## 1. Overview

Wire protocol spoken between a host program running on a desktop OS
(Windows / macOS / Linux) and the ClawTouch HID firmware running on a
Raspberry Pi Pico 2. Transport is USB CDC (the "data" CDC channel; the
"console" channel is used for the CircuitPython REPL and is not
involved in the protocol).

### Design principles

- The firmware is a generic "HID executor" — it carries no business
  logic. All decisions live on the host.
- Every command (other than asynchronous notifications, of which there
  are none in v1.0) is acknowledged by either `ACK` or `ERROR`.
- Command-code space is reserved for forward-compatible additions
  (firmware update, batching, etc.) without changing the frame envelope.

---

## 2. Frame format

```
[Header:1] [SeqID:2] [CmdType:1] [PayloadLen:2] [Payload:N] [Checksum:1]
```

| Field      | Size    | Format    | Notes |
|------------|---------|-----------|-------|
| Header     | 1 byte  | `0xAA`    | Fixed value, used for frame resync |
| SeqID      | 2 bytes | uint16 LE | Sender-incremented sequence number |
| CmdType    | 1 byte  | uint8     | Command code (see §3) |
| PayloadLen | 2 bytes | uint16 LE | Payload length, 0–1024 |
| Payload    | N bytes | —         | Command parameters |
| Checksum   | 1 byte  | uint8     | `sum(all preceding bytes) & 0xFF` |

> **Maximum frame size:** 1 + 2 + 1 + 2 + 1024 + 1 = **1031 bytes**

All multi-byte integers are little-endian.

---

## 3. Command codes

### 3.1 Control

| Command          | Code   | Dir  | Payload                  | Notes |
|------------------|--------|------|--------------------------|-------|
| PING             | `0x01` | H→D  | empty                    | Liveness check |
| PONG             | `0x02` | D→H  | empty                    | Response to PING |
| STATUS_REQUEST   | `0xF0` | H→D  | empty                    | Request firmware status |
| STATUS_RESPONSE  | `0xF1` | D→H  | UTF-8 JSON               | Firmware version / state |
| ACK              | `0xFE` | D→H  | empty                    | Command succeeded |
| ERROR            | `0xFF` | D→H  | `[code:1] [msg:UTF-8]`   | Command failed |

`H→D` = host → device, `D→H` = device → host.

**STATUS_RESPONSE payload:**

```json
{"fw_ver": "1.1.2", "board": "pico2", "uptime_ms": 12345}
```

`fw_ver` is the running firmware's semantic version — the value shown is
illustrative; query `STATUS_REQUEST` for the live value.

**ERROR codes:**

| Code   | Meaning |
|--------|---------|
| `0x01` | Unknown command |
| `0x02` | Malformed payload |
| `0x03` | Checksum mismatch |
| `0x04` | Execution timeout |
| `0x05` | Device busy |

### 3.2 Mouse

| Command            | Code   | Payload                              | Since | Notes |
|--------------------|--------|--------------------------------------|-------|-------|
| MOUSE_MOVE         | `0x10` | `[x:int16 LE] [y:int16 LE] [flags:uint8]` | v1.0 | Move pointer |
| MOUSE_CLICK        | `0x11` | `[button:uint8] [flags:uint8]`       | v1.0 | Press + release (atomic) |
| MOUSE_SCROLL       | `0x12` | `[delta:int16 LE]`                   | v1.0 | Wheel scroll |
| MOUSE_BUTTON_DOWN  | `0x13` | `[button:uint8]`                     | v1.1 | Press, no release (drag start) |
| MOUSE_BUTTON_UP    | `0x14` | `[button:uint8]`                     | v1.1 | Release named button (drag end) |

**MOUSE_MOVE flags:**

- bit0: reserved for relative/absolute discrimination. **The v1.0
  firmware ignores this bit and always treats `(x, y)` as a relative
  pixel delta** — USB HID Boot Mouse, which this firmware implements,
  has no absolute-coordinate report. Absolute interpretation is the
  host's responsibility (e.g. `clawtouch-mcp` queries the OS cursor
  position and converts to a delta). The flag stays in the wire
  format so a future firmware revision targeting an HID Digitizer
  profile can switch on it without renumbering opcodes.

**MOUSE_CLICK button:**

- `0x01` = LEFT, `0x02` = RIGHT, `0x04` = MIDDLE

**MOUSE_CLICK flags:**

- bit0 = 1: double-click (firmware emits two `mouse.click` reports back-to-back)

**MOUSE_BUTTON_DOWN / MOUSE_BUTTON_UP (v1.1):**

- 1-byte payload: the button code (same encoding as `MOUSE_CLICK`).
- `BUTTON_DOWN` presses the button and does **not** release it. Subsequent
  `MOUSE_MOVE` frames produce a held-button drag.
- `BUTTON_UP` releases the named button. `BUTTON_UP` on a button that wasn't
  pressed is a no-op (idempotent, no error).
- A drag is `BUTTON_DOWN(left)` → one or more `MOUSE_MOVE` → `BUTTON_UP(left)`.
  `clawtouch-mcp` exposes this composition as the single `hid.drag` tool;
  the wire protocol stays primitive on purpose.
- `KEY_RELEASE(0, 0)` (release-all) also releases held mouse buttons —
  panic-stop semantics unchanged from v1.0.

### 3.3 Keyboard

| Command          | Code   | Payload                              | Notes |
|------------------|--------|--------------------------------------|-------|
| KEY_PRESS        | `0x20` | `[modifiers:uint8] [keycode:uint8]`  | Press key |
| KEY_RELEASE      | `0x21` | `[modifiers:uint8] [keycode:uint8]`  | Release key (all-zero = release-all) |
| KEY_TYPE_STRING  | `0x22` | UTF-8 string                         | Type as characters (US layout) |
| KEY_COMBO        | `0x23` | `[modifiers:uint8] [keycode:uint8]`  | Press + release shortcut |

All three keyboard commands share the same payload byte order —
`[modifiers, keycode]` — matching the USB HID keyboard report layout
(modifier byte first). All reference implementations (firmware,
`clawtouch_hid_protocol`, this spec) agree.

> **KEY_TYPE_STRING is US-layout character entry, not arbitrary Unicode
> input.** The payload is UTF-8 *transport*, but the firmware types each
> character through the US keyboard layout (`KeyboardLayoutUS`). ASCII /
> US-layout characters work; CJK, emoji, and other characters outside the
> US layout generally do **not** type correctly — they depend on the host's
> active IME and may fail or produce nothing. For non-ASCII text, drive the
> host IME or a clipboard path from the host layer instead.

### 3.4 Modifier bitmask

| Bit  | Modifier      | Value  |
|------|---------------|--------|
| bit0 | CTRL          | `0x01` |
| bit1 | SHIFT         | `0x02` |
| bit2 | ALT           | `0x04` |
| bit3 | GUI (Windows/Cmd) | `0x08` |

Composable, e.g. `Ctrl+Shift = 0x03`.

---

## 4. Sequence flows

### 4.1 Normal exchange

```
Host (H)                  Device (D)
  |                          |
  |-- PING ----------------->|
  |<-- PONG ------------------|
  |                          |
  |-- MOUSE_MOVE ----------->|
  |<-- ACK -------------------|
  |                          |
  |-- KEY_TYPE_STRING ------->|
  |<-- ACK -------------------|
```

### 4.2 Error handling

```
Host (H)                  Device (D)
  |                          |
  |-- Bad command ---------->|
  |<-- ERROR (code=0x01) -----|
```

### 4.3 Recommended timeouts

| Scenario               | Timeout | Retries |
|------------------------|---------|---------|
| PING / PONG            | 2 s     | 3       |
| Mouse / keyboard ops   | 5 s     | none — report failure |
| STATUS_REQUEST         | 3 s     | 2       |

---

## 5. Reserved (v2+)

The following codes are reserved for future use. v1.0 firmware will
respond to them with `ERROR / UNKNOWN_COMMAND`.

| Command                | Code   | Intended meaning |
|------------------------|--------|------------------|
| FIRMWARE_UPLOAD_START  | `0xE0` | Begin OTA firmware upload |
| FIRMWARE_UPLOAD_CHUNK  | `0xE1` | OTA chunk |
| FIRMWARE_UPLOAD_END    | `0xE2` | Finish OTA |
| FIRMWARE_REBOOT        | `0xE3` | Reboot firmware |

---

## 6. Changelog

| Version | Date        | Notes |
|---------|-------------|-------|
| v0.1    | 2026-03-12  | Initial draft |
| v1.0    | 2026-03-15  | Frozen: error code table, timeout recommendations, STATUS_RESPONSE schema, maximum frame size constraint |
