[English](protocol-v1.md) | **简体中文**

# ClawTouch HID 通信协议 — Epoch 1(纪元 1)

> **线协议纪元 (epoch):** `1` — 即 §2 的帧信封, 2026-03-15 冻结. epoch 是单个
> 整数, **只**在"破坏帧信封 / 改既有 opcode 语义"时才 +1(设计上几乎不动). 新增
> opcode 是**纪元内的加法**, 永不升 epoch.
> **不用 SemVer.** 线协议靠 epoch 标识, 不是 `major.minor.patch`. 带 SemVer 的是
> *描述本 epoch* 的 `clawtouch-hid-protocol` Python 包(现 `1.1.1`), 以及单独的固件
> (现 `1.1.2`)—— epoch 跟这两个包版本都不是一回事. 历史文档里写的"协议 v1.0 / v1.1"
> 应理解为 epoch 1 内的 **opcode 集里程碑**(模块发布), 不是"线协议第 1.1 版".
> **epoch 1 内的 opcode 集历史:** 基线 opcode 2026-03-15 冻结;
> `MOUSE_BUTTON_DOWN` / `MOUSE_BUTTON_UP`(`0x13` / `0x14`)2026-05-28 累加,
> 用于拖拽手势 + 兼容 Anthropic Computer Use.
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
{"fw_ver": "1.1.2", "board": "pico2", "uptime_ms": 12345}
```

`fw_ver` 是运行中固件的语义版本号 —— 此处数值仅为示例; 发
`STATUS_REQUEST` 查实时值。

**ERROR 错误码:**

| 代码   | 含义 |
|--------|------|
| `0x01` | 未知命令 |
| `0x02` | Payload 格式错误 |
| `0x03` | 校验和不一致 |
| `0x04` | 命令执行超时 |
| `0x05` | 设备繁忙 |

### 3.2 鼠标命令

| 命令               | 代码   | Payload                              | 起始版本 | 说明 |
|--------------------|--------|--------------------------------------|---------|------|
| MOUSE_MOVE         | `0x10` | `[x:int16 LE] [y:int16 LE] [flags:uint8]` | v1.0 | 移动 |
| MOUSE_CLICK        | `0x11` | `[button:uint8] [flags:uint8]`       | v1.0 | 按下+松开(原子) |
| MOUSE_SCROLL       | `0x12` | `[delta:int16 LE]`                   | v1.0 | 滚轮 |
| MOUSE_BUTTON_DOWN  | `0x13` | `[button:uint8]`                     | v1.1 | 按下不松(拖拽起点) |
| MOUSE_BUTTON_UP    | `0x14` | `[button:uint8]`                     | v1.1 | 松开指定按钮(拖拽终点) |

**MOUSE_MOVE flags:**

- bit0: 保留用于 relative/absolute 区分. **v1.0 固件忽略本 bit, 始终
  把 `(x, y)` 当作相对像素 delta 处理** —— 本固件实现的是 USB HID
  Boot Mouse, 该协议本身没有绝对坐标报告能力. 绝对坐标语义由 host
  端负责 (例如 `clawtouch-mcp` 查询 OS 光标位置后换算成 delta). 本
  字段在线协议中保留, 让未来某个改用 HID Digitizer profile 的固件
  版本能直接启用而不必新增 opcode.

**MOUSE_CLICK button:**

- `0x01` = LEFT, `0x02` = RIGHT, `0x04` = MIDDLE

**MOUSE_CLICK flags:**

- bit0 = 1: 双击 (固件背靠背发两个 `mouse.click` 报告)

**MOUSE_BUTTON_DOWN / MOUSE_BUTTON_UP (v1.1):**

- 1 字节 payload: 按键代码 (跟 `MOUSE_CLICK` 同样的编码).
- `BUTTON_DOWN` 按下按键但**不**松开. 之后的 `MOUSE_MOVE` 帧会产生
  "按住拖拽"效果.
- `BUTTON_UP` 释放指定的按键. 对未按下的按键调用 `BUTTON_UP` 是 no-op
  (幂等, 不报错).
- 一次完整 drag = `BUTTON_DOWN(left)` → 若干 `MOUSE_MOVE` → `BUTTON_UP(left)`.
  `clawtouch-mcp` 把这个组合封装成 `hid.drag` 单个工具; 线协议层故意保持
  最小原语.
- `KEY_RELEASE(0, 0)` (release-all) 也会松开持有的鼠标按键 —— 紧急停止
  语义与 v1.0 保持不变.

### 3.3 键盘命令

| 命令             | 代码   | Payload                              | 说明 |
|------------------|--------|--------------------------------------|------|
| KEY_PRESS        | `0x20` | `[modifiers:uint8] [keycode:uint8]`  | 按键 |
| KEY_RELEASE      | `0x21` | `[modifiers:uint8] [keycode:uint8]`  | 松键(全 0 = 全部释放) |
| KEY_TYPE_STRING  | `0x22` | UTF-8 字符串                         | 逐字符输入(US 布局) |
| KEY_COMBO        | `0x23` | `[modifiers:uint8] [keycode:uint8]`  | 快捷键组合 |

三条键盘命令的 payload 字节序一致 —— 都是 `[modifiers, keycode]`,
与 USB HID 键盘报告布局一致(modifier 字节在前)。三处参考实现
(固件、`clawtouch_hid_protocol`、本规范)一致。

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
