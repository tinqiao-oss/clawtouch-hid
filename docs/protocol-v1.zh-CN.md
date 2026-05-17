[English](protocol-v1.md) | **简体中文**

# ClawTouch HID 通信协议 v1.0(冻结版)

> **状态:** v1.0 — 已冻结
> **冻结日期:** 2026-03-15
> **适用范围:** 宿主(PC)↔ ClawTouch HID 设备(Raspberry Pi Pico 2)

---

## 1. 概述

宿主程序(跑在 Windows / macOS / Linux 桌面 OS)与跑在 Raspberry Pi
Pico 2 上的 ClawTouch HID 固件之间的通信协议。传输层走 USB CDC
(其中 "data" 通道用于本协议;"console" 通道是 CircuitPython REPL
专用,跟协议无关)。

### 设计原则

- 固件是通用 "HID 执行器" —— 不含业务逻辑,所有决策在宿主侧。
- 每条命令(v1.0 没有异步通知)必须有 `ACK` 或 `ERROR` 应答。
- 命令码空间预留了向前兼容扩展(固件升级、批量等),不需要改帧信封。

---

## 2. 帧格式

```
[Header:1] [SeqID:2] [CmdType:1] [PayloadLen:2] [Payload:N] [Checksum:1]
```

| 字段       | 大小    | 格式      | 说明 |
|------------|---------|-----------|------|
| Header     | 1 byte  | `0xAA`    | 固定值,用于帧同步 |
| SeqID      | 2 bytes | uint16 LE | 发送方递增的序列号 |
| CmdType    | 1 byte  | uint8     | 命令码(见 §3) |
| PayloadLen | 2 bytes | uint16 LE | Payload 长度 0–1024 |
| Payload    | N bytes | —         | 命令参数 |
| Checksum   | 1 byte  | uint8     | `前面所有字节累加 & 0xFF` |

> **最大帧长度:** 1 + 2 + 1 + 2 + 1024 + 1 = **1031 bytes**

多字节整数全部小端。

---

## 3. 命令码

### 3.1 控制命令

| 命令             | 代码   | 方向 | Payload                  | 说明 |
|------------------|--------|------|--------------------------|------|
| PING             | `0x01` | H→D  | 空                       | 探活 |
| PONG             | `0x02` | D→H  | 空                       | PING 响应 |
| STATUS_REQUEST   | `0xF0` | H→D  | 空                       | 请求固件状态 |
| STATUS_RESPONSE  | `0xF1` | D→H  | UTF-8 JSON               | 固件版本/状态 |
| ACK              | `0xFE` | D→H  | 空                       | 命令执行成功 |
| ERROR            | `0xFF` | D→H  | `[code:1] [msg:UTF-8]`   | 命令执行失败 |

`H→D` = 宿主 → 设备,`D→H` = 设备 → 宿主。

**STATUS_RESPONSE payload:**

```json
{"fw_ver": "1.0.0", "board": "pico2", "uptime_ms": 12345}
```

**ERROR 错误码:**

| 代码   | 含义 |
|--------|------|
| `0x01` | 未知命令 |
| `0x02` | Payload 格式错误 |
| `0x03` | 校验和不一致 |
| `0x04` | 命令执行超时 |
| `0x05` | 设备繁忙 |

### 3.2 鼠标命令

| 命令          | 代码   | Payload                              | 说明 |
|---------------|--------|--------------------------------------|------|
| MOUSE_MOVE    | `0x10` | `[x:int16 LE] [y:int16 LE] [flags:uint8]` | 移动 |
| MOUSE_CLICK   | `0x11` | `[button:uint8] [flags:uint8]`       | 点击 |
| MOUSE_SCROLL  | `0x12` | `[delta:int16 LE]`                   | 滚轮 |

**MOUSE_MOVE flags:**

- bit0 = 1: 相对移动;bit0 = 0: 绝对移动

**MOUSE_CLICK button:**

- `0x01` = LEFT, `0x02` = RIGHT, `0x04` = MIDDLE

**MOUSE_CLICK flags:**

- bit0 = 1: 双击

### 3.3 键盘命令

| 命令             | 代码   | Payload                              | 说明 |
|------------------|--------|--------------------------------------|------|
| KEY_PRESS        | `0x20` | `[keycode:uint8] [modifiers:uint8]`  | 按键 |
| KEY_RELEASE      | `0x21` | `[keycode:uint8] [modifiers:uint8]`  | 松键(全 0 = 全部释放) |
| KEY_TYPE_STRING  | `0x22` | UTF-8 字符串                         | 逐字符输入(US 布局) |
| KEY_COMBO        | `0x23` | `[modifiers:uint8] [keycode:uint8]`  | 快捷键组合 |

> ⚠️ **`KEY_PRESS` 与 `KEY_COMBO` 的 payload 字节序不同。**
> `KEY_PRESS` 是 `[keycode, modifiers]`,`KEY_COMBO` 是
> `[modifiers, keycode]`。这是 v1.0 保留的历史小怪点。三处参考实现
> (固件、`clawtouch_hid_protocol`、本规范)一致。

### 3.4 Modifier 位掩码

| Bit  | 修饰键        | 值     |
|------|---------------|--------|
| bit0 | CTRL          | `0x01` |
| bit1 | SHIFT         | `0x02` |
| bit2 | ALT           | `0x04` |
| bit3 | GUI (Windows/Cmd) | `0x08` |

可组合,如 `Ctrl+Shift = 0x03`。

---

## 4. 交互流程

### 4.1 正常交互

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

### 4.2 错误处理

```
Host (H)                  Device (D)
  |                          |
  |-- 错误命令 -------------->|
  |<-- ERROR (code=0x01) -----|
```

### 4.3 推荐超时

| 场景                   | 超时    | 重试 |
|------------------------|---------|------|
| PING / PONG            | 2 秒    | 最多 3 次 |
| 鼠标 / 键盘命令        | 5 秒    | 不重试,直接报错 |
| STATUS_REQUEST         | 3 秒    | 最多 2 次 |

---

## 5. 预留命令(v2+)

下列命令码预留给未来使用。v1.0 固件收到会返回 `ERROR / UNKNOWN_COMMAND`。

| 命令                   | 代码   | 预期含义 |
|------------------------|--------|----------|
| FIRMWARE_UPLOAD_START  | `0xE0` | 开始 OTA 固件上传 |
| FIRMWARE_UPLOAD_CHUNK  | `0xE1` | OTA 数据块 |
| FIRMWARE_UPLOAD_END    | `0xE2` | 结束 OTA |
| FIRMWARE_REBOOT        | `0xE3` | 重启固件 |

---

## 6. 变更记录

| 版本 | 日期        | 变更内容 |
|------|-------------|---------|
| v0.1 | 2026-03-12  | 初始草案 |
| v1.0 | 2026-03-15  | 正式冻结:新增 ERROR 代码表、超时建议、STATUS_RESPONSE 格式、最大帧长约束 |
