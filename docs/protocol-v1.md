**English** | [简体中文](protocol-v1.zh-CN.md)

# ClawTouch HID Wire Protocol v1.0 (Frozen)

> **Status:** v1.0 — frozen
> **Frozen on:** 2026-03-15
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
{"fw_ver": "1.0.0", "board": "pico2", "uptime_ms": 12345}
```

**ERROR codes:**

| Code   | Meaning |
|--------|---------|
| `0x01` | Unknown command |
| `0x02` | Malformed payload |
| `0x03` | Checksum mismatch |
| `0x04` | Execution timeout |
| `0x05` | Device busy |

### 3.2 Mouse

| Command       | Code   | Payload                              | Notes |
|---------------|--------|--------------------------------------|-------|
| MOUSE_MOVE    | `0x10` | `[x:int16 LE] [y:int16 LE] [flags:uint8]` | Move pointer |
| MOUSE_CLICK   | `0x11` | `[button:uint8] [flags:uint8]`       | Click |
| MOUSE_SCROLL  | `0x12` | `[delta:int16 LE]`                   | Wheel scroll |

**MOUSE_MOVE flags:**

- bit0 = 1: relative; bit0 = 0: absolute

**MOUSE_CLICK button:**

- `0x01` = LEFT, `0x02` = RIGHT, `0x04` = MIDDLE

**MOUSE_CLICK flags:**

- bit0 = 1: double-click

### 3.3 Keyboard

| Command          | Code   | Payload                              | Notes |
|------------------|--------|--------------------------------------|-------|
| KEY_PRESS        | `0x20` | `[keycode:uint8] [modifiers:uint8]`  | Press key |
| KEY_RELEASE      | `0x21` | `[keycode:uint8] [modifiers:uint8]`  | Release key (all-zero = release-all) |
| KEY_TYPE_STRING  | `0x22` | UTF-8 string                         | Type as characters (US layout) |
| KEY_COMBO        | `0x23` | `[modifiers:uint8] [keycode:uint8]`  | Press + release shortcut |

> ⚠️ **Payload byte order differs between `KEY_PRESS` and `KEY_COMBO`.**
> `KEY_PRESS` is `[keycode, modifiers]`; `KEY_COMBO` is
> `[modifiers, keycode]`. This is a known historical quirk preserved
> for v1.0 compatibility. All reference implementations (firmware,
> `clawtouch_hid_protocol`, this spec) agree.

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
