[English](README.md) | **简体中文**

# clawtouch-hid

> **ClawTouch 的开源硬件层。**
> Raspberry Pi Pico 2 上的 CircuitPython 固件、它说的冻结版 USB-CDC 通信协议,
> 以及给宿主端直接驱动这块板子用的 Python 协议模块。

🌐 **[clawtouch.cn](https://clawtouch.cn)** — 官网,购买硬件 / 查文档 / 商务咨询都在这里。

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Protocol: v1.0 (frozen)](https://img.shields.io/badge/protocol-v1.0_frozen-blue.svg)](docs/protocol-v1.zh-CN.md)
[![CircuitPython 10.x](https://img.shields.io/badge/CircuitPython-10.x-purple.svg)](https://circuitpython.org/)

---

## 这是什么?

本仓库包含三样东西,加在一起就能把一块 Raspberry Pi Pico 2 变成"ClawTouch
HID 设备"—— 一台 USB 接入的键鼠,可以让另一台 PC 上跑的程序通过串口
指令通道驱动它:

1. **`firmware/`** —— 跑在 Pico 2 上的 CircuitPython 固件。它把自己作为
   USB 复合设备(HID 键盘 + HID 鼠标 + USB-CDC 串口对)挂载给宿主操作系统。
   固件**自己不做任何决策** —— 它等 CDC data 端口收到带帧的命令,然后把
   每条命令翻译成一个 HID 报告。
2. **`clawtouch_hid_protocol/`** —— 一个小巧、零依赖的 Python 模块,
   定义了冻结版 v1.0 通信协议(命令码、payload 格式、构帧 helper)。
   如果你想跳过 MCP 直接驱动板子,从这个模块开始。
3. **`docs/`** —— [冻结版 v1.0 协议规范](docs/protocol-v1.zh-CN.md) 和
   [烧录指南](docs/flash-guide.zh-CN.md)。

这块板子也是 [clawtouch-mcp](https://github.com/tinqiao-oss/clawtouch-mcp)
MCP server 跟它对话的硬件。如果你只想"让 Claude Desktop 控制真实键鼠",
从那个仓库开始就行 —— 不必读本仓库。**本仓库是给固件玩家、协议审计者、
和想在同一块硬件上自己造宿主栈的人**。

> 📦 MIT 协议。没有后端,没有 LLM,没有输入节奏修饰层。只有协议本身和
> 跟它对话的固件。

## 为啥要用物理 HID 设备?

大部分"AI 控制电脑"的 demo 都要求在目标机上跑 agent 进程,并走 OS 层
合成输入 API。这类路径在 kiosk 锁机环境、嵌入式测试台架、跨设备 RPA
等"目标机必须保持干净"的场景里有局限。USB HID 物理外设走标准 OS HID
驱动栈,跟任何插上的键盘鼠标走同一条数据通路 —— 目标机零安装。本仓库
里的固件就是把一块 ¥55 的 Pico 2 变成这种外设需要的最少代码。

## 适用范围 —— 一台设备只对应一个目标

硬件是 USB 外设,只有单一宿主连接。本仓库里的固件也是 —— 一块 Pico
对应一台目标机。这是设计本身决定的:**单设备单宿主的对位控制硬件**,
要控 10 台机器就烧 10 块 Pico。

**适合**: RPA / 装不了软件的设备自动化测试 / 无障碍辅助 (LLM agent +
HID = 残障用户的真实键盘) / 跨机工作流 (目标机必须保持干净不装 agent)。

**不适合**: 批量账号注册 / 消费平台多账号运营 (多数司法辖区属于监管
红线,而且单设备单宿主结构上就不合) / 针对特定应用的脚本化适配层
(选择器、固定流程脚本 —— 这些该在上层 agent / RPA 框架做,本仓库
只做底层 HID 原语)。

## 硬件

| 项 | 规格 |
|------|------|
| 主控 | RP2350 (Raspberry Pi Pico 2 参考板) |
| 固件框架 | CircuitPython 10.x |
| 协议版本 | v1.0 (2026-03-15 冻结) |
| USB 接口 | HID (键盘 + 鼠标) + CDC (console + data) |
| CDC 波特率 | 115200 (data 通道) |

你可以在 [clawtouch.cn](https://clawtouch.cn) 买成品 ClawTouch 设备,
或者从任意电子件零售商买一块裸 Pico 2(¥55 起),自己烧固件,功能等价。

## 快速上手

1. **给 Pico 2 烧 CircuitPython** —— 见 [docs/flash-guide.zh-CN.md](docs/flash-guide.zh-CN.md)
   的三步流程(按 `BOOTSEL` → 拖入 UF2 → 拖入固件)。
2. **从 Python 跟它对话** —— 装宿主端协议模块,发一条 `PING`:

   ```bash
   pip install clawtouch-hid-protocol pyserial
   ```

   ```python
   import serial
   from clawtouch_hid_protocol import build_ping, HidCommand

   ser = serial.Serial("COM7", 115200, timeout=2)   # 用你的 CDC data 端口
   ser.write(build_ping(seq_id=1).serialize())
   resp = HidCommand.deserialize(ser.read(7))
   print(resp.cmd_type)                              # CommandType.PONG
   ```

3. **或者跳过线协议,直接用 [clawtouch-mcp](https://github.com/tinqiao-oss/clawtouch-mcp)**
   —— 同样的固件、同样的硬件,但暴露为 Model Context Protocol server,
   可直接插入 Claude Desktop / Cline / Continue / OpenClaw / Hermes 等。

完整可运行的 PING 示例见 [`examples/ping_test.py`](examples/ping_test.py)。

## 通信协议速览

```
+------+--------+--------+---------+---------+----------+
| 0xAA | seq:u16| cmd:u8 | plen:u16| payload | csum:u8  |
+------+--------+--------+---------+---------+----------+
   1B     2B       1B       2B       plen       1B
```

* 多字节整数用小端
* `csum` = 前面所有字节累加和 & 0xFF
* payload 最大 1024 字节

定义了 12 个命令码:`PING/PONG`、`MOUSE_MOVE/CLICK/SCROLL`、
`KEY_PRESS/RELEASE/TYPE_STRING/COMBO`、`STATUS_REQUEST/RESPONSE`,
外加 `ACK` 和 `ERROR`。完整字节级布局见
[docs/protocol-v1.zh-CN.md](docs/protocol-v1.zh-CN.md)。

## 无线传输(可选)

默认情况下宿主通过上面的 USB-CDC 串口通道驱动板子。
[`firmware-wifi/`](firmware-wifi/) 是给 Raspberry Pi Pico 2 **W** 的可选
**双通道**固件:同一套冻结版 v1.0 协议,USB-CDC 和 Wi-Fi TCP server 两条
通道并行接收。这样板子可以插在一台宿主上做 HID 输出,同时由一台 PC 隔着
局域网发命令。

HID 设备是**宿主无关**的 —— 它插着的宿主可以是 Windows / macOS / Linux
PC,也可以是手机(安卓 / iOS)。详见
[docs/wifi-transport.zh-CN.md](docs/wifi-transport.zh-CN.md)。

## 仓库布局

```
clawtouch-hid/
├── clawtouch_hid_protocol/   ← Python 协议模块(宿主端,pip 可装)
├── firmware/                 ← Pico 2 的 CircuitPython 固件
│   ├── boot.py               ← USB 描述符设置(上电只跑一次)
│   ├── code.py               ← HID 执行器主循环
│   ├── packet_parser.py      ← 帧提取器,无硬件依赖,可在 PC 上测
│   └── lib/adafruit_hid/     ← 捆绑的 HID 库 (MIT,见 NOTICE)
├── firmware-wifi/            ← 可选的 Wi-Fi 变体(Pico 2 W)— 见 docs/wifi-transport.zh-CN.md
├── docs/                     ← 协议 spec + 烧录指南(中英双语)
├── examples/                 ← 可运行的冒烟测试
├── pyproject.toml            ← 构建 clawtouch-hid-protocol 上 PyPI
├── LICENSE                   ← MIT
├── NOTICE                    ← 第三方组件出处
└── README.md / README.zh-CN.md
```

## 设计哲学

* **固件不含业务逻辑。** 只做"把带帧字节翻译成 HID 报告"。一切决策 ——
  打什么字、什么时候点击、多步操作怎么编排 —— 都在宿主侧。这让固件
  小、可审、可被不同宿主栈复用。
* **协议是冻结的。** v1.0 在 2026-03-15 发布后不再改。未来新能力以新
  命令码的形式加进同一个信封,既有的 v1.0 命令永远兼容。
* **以值为准,不以名为准。** 固件、`clawtouch_hid_protocol` 模块、协议
  spec 三处各列了一份命令码。数值是真理,Python 名称只是为了可读。

## 协议小怪点(知道了就行)

`KEY_PRESS` 和 `KEY_COMBO` 的 payload 字节序不一样:

* `KEY_PRESS` (0x20):`[keycode, modifiers]`
* `KEY_COMBO` (0x23):`[modifiers, keycode]`

这是文档化的行为,不是 bug —— `KEY_COMBO` 历史上是从单独的"发快捷键"
意图长出来的,保留了自己的布局。三处实现(固件、协议模块、spec)
一致。如果你写第四份实现,注意顺序。

## 开源路线图

ClawTouch 采用 **open-core** 模式:硬件与协议层开源,集成的商业产品闭源。

| 组件                                              | 状态                  |
|---------------------------------------------------|-----------------------|
| **clawtouch-hid** (本仓库:固件 + 协议)           | ✅ 已发布             |
| **[clawtouch-mcp](https://github.com/tinqiao-oss/clawtouch-mcp)** (MCP server) | ✅ 已发布 |
| **clawtouch-bridge-sdk** (Python + Node SDK)      | 🔵 规划中             |
| 后端服务 / 桌面端 / 应用适配器 / 视觉模型         | 🔒 闭源 — [详细对比](https://github.com/tinqiao-oss/clawtouch-mcp/blob/master/docs/COMMERCIAL_PRODUCT.zh-CN.md) |

关注组织 [@tinqiao-oss](https://github.com/tinqiao-oss) 接收新版本通知。

## 常见问题

**必须买 ClawTouch 硬件才能用吗?**
不用。一块裸 Raspberry Pi Pico 2(¥55 左右)刷上本仓库的固件就是一台
能用的 ClawTouch HID 设备。商业产品在此基础上做了外壳、QA、配送和
售后支持 —— 线协议完全一致。

**需要 ClawTouch 后端 / 账号 / API key 吗?**
不需要。本仓库里没有任何东西访问网络。固件通过 USB 跟宿主对话,宿主
通过 USB 跟固件对话 —— 全部栈就这两层。

**没有物理 Pico 也能跑哪些?**
`clawtouch_hid_protocol` 模块和 `firmware/packet_parser.py` 都是无
硬件依赖的纯 Python,任何机器都能跑。`firmware/code.py` 只能跑在
CircuitPython 上,因为它在 import 时就依赖板上的 `usb_hid` / `usb_cdc`
模块,普通 Python 解释器跑不起来 —— 离线测试请用协议模块或 packet_parser。

**跟闭源的 ClawTouch 桌面端有什么区别?**
本仓库只是最底层 —— 纯 HID 原语 + 冻结线协议 —— 让其他 agent 框架
能在不绑定 ClawTouch 完整产品的前提下使用硬件。→ 桌面端额外做什么
(视觉识别 / 多步编排 / 应用适配器 / B2B 层), 完整分层对比 + 截图见
[`COMMERCIAL_PRODUCT.zh-CN.md`](https://github.com/tinqiao-oss/clawtouch-mcp/blob/master/docs/COMMERCIAL_PRODUCT.zh-CN.md)
(在 `clawtouch-mcp` 姊妹仓)。

## 参与贡献

欢迎 PR:文档修订、新示例、针对 v1.0 协议的新语言绑定、英文翻译、
硬件兼容性报告。

**不接受**的 PR:输入节奏 / 行为修饰层(故意排除在范围外)、破坏 v1.0
兼容性的协议改动、应用专属适配器(这部分在闭源桌面端)。

## 关于项目

`clawtouch-hid` 由 **北京亭桥科技** 维护 —— ClawTouch 产品团队
([clawtouch.cn](https://clawtouch.cn)),做即插即用的 USB 设备,让 LLM
agent 在 HID 层操控真实的 Windows / macOS / Linux 桌面。本仓库是
整个产品栈的开源硬件层。

## License

MIT © 北京亭桥科技有限公司. 见 [LICENSE](LICENSE) 与 [NOTICE](NOTICE).

商业部署 / 企业支持 / OEM 硬件合作咨询:`support@tinqiao.com`
