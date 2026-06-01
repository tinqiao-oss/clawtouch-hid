[English](flash-guide.md) | **简体中文**

# ClawTouch HID 固件烧录指南

> 最后验证: 2026-03-14 — 在 CircuitPython 10.1.4 + Raspberry Pi Pico 2
> 上验证了**烧录流程**。同一流程适用于本仓库直到 v1.1.2 的所有固件:
> v1.1.0 的 drag opcode、v1.1.1 的键盘字节序统一、v1.1.2 的紧急停修复
> 都只改 `code.py`, 没动 boot.py 或 bootloader, 烧录步骤完全一样。

## 你需要

- 一块 **Raspberry Pi Pico 2** (RP2350 板)
- 一根 USB-C 数据线(不是只充电的线)
- 一台跑 Windows / macOS / Linux 的电脑

## 第一步:刷 CircuitPython

1. 从官方下载最新 **CircuitPython 10.x** 的 Pico 2 版 UF2:
   <https://circuitpython.org/board/raspberry_pi_pico2/>
   (最后验证版本: 10.1.4)
2. 按住 Pico 2 上的 **BOOTSEL** 按钮(板上唯一的按钮; ClawTouch 带壳成品上 =
   USB-C 口朝上时**左侧**那个),然后插上 USB(保持按住)。
3. 电脑会出现一个名为 `RPI-RP2` 的 USB 驱动器(内含 `INFO_UF2.TXT`)。
4. 把下载的 `.uf2` 文件拖入该驱动器。
5. Pico 2 自动重启,驱动器名变成 `CIRCUITPY`。

## 第二步:装 adafruit_hid 库

固件 import 了 Adafruit CircuitPython HID 库的键盘/鼠标类。两种装法:

**方案 A — 用本仓库内置副本(推荐):**

本仓库的 `firmware/lib/adafruit_hid/` 是已验证的副本。复制到 Pico 的
`lib/` 即可。

> 内置 `.mpy` 是 CircuitPython `mpy` 格式 v6 (ABI 6), CircuitPython 10.x
> 可直接加载 —— `.mpy` 格式在整个 10.x 系列未变。若开机报
> `incompatible .mpy file`, 改用方案 B 下载匹配的 10.x Bundle。

**方案 B — 自己从 Adafruit 拉新版:**

从 <https://circuitpython.org/libraries> 下载 **10.x** 版 Bundle,
解压后把 `lib/adafruit_hid/` 文件夹复制到 `CIRCUITPY/lib/adafruit_hid/`。

## 第三步:拷贝固件

可部署文件在本仓库 `firmware/` 目录下。在 Windows PowerShell 里
(把 `G:` 换成你实际的 `CIRCUITPY` 盘符):

```powershell
$pico = "G:"

Copy-Item "firmware\boot.py"          "$pico\boot.py"          -Force
Copy-Item "firmware\code.py"          "$pico\code.py"          -Force
Copy-Item "firmware\lib\adafruit_hid" "$pico\lib\adafruit_hid" -Recurse -Force
```

macOS / Linux 上(假设挂载在 `/Volumes/CIRCUITPY`):

```bash
PICO=/Volumes/CIRCUITPY        # Linux 上一般是 /media/$USER/CIRCUITPY

cp firmware/boot.py          "$PICO/boot.py"
cp firmware/code.py          "$PICO/code.py"
cp -R firmware/lib/adafruit_hid "$PICO/lib/adafruit_hid"
```

> **`boot.py` 上电只跑一次。** 拷完 `boot.py` 必须拔插一次 USB(或
> 在系统里 eject 后重连)。改 `code.py` 会自动重载,不用拔插。

## CIRCUITPY 上应有的布局

```
CIRCUITPY/
├── boot.py                          ← USB 描述符设置
├── code.py                          ← 固件主循环
├── boot_out.txt                     ← CircuitPython 自动生成
├── settings.toml                    ← CircuitPython 配置
└── lib/
    └── adafruit_hid/                ← HID 驱动库(.mpy)
        ├── __init__.mpy
        ├── keyboard.mpy
        ├── keycode.mpy
        ├── keyboard_layout_base.mpy
        ├── keyboard_layout_us.mpy
        ├── mouse.mpy
        ├── consumer_control.mpy
        └── consumer_control_code.mpy
```

## 第四步:冒烟测试

拔插后:

1. **LED 闪烁:** 板载 LED 每秒闪一次。一直亮或一直灭都说明固件没跑起来。
2. **COM 端口:** 多出两个串口(一个 console + 一个 data)。Windows 在
   设备管理器里看,macOS/Linux 看 `/dev/tty.usbmodem*` 或 `/dev/ttyACM*`。
3. **PING 测试:** 跑 [`examples/ping_test.py`](../examples/ping_test.py),
   对准 **data** 端口。应该看到 `PONG received`。

## 升级固件

CircuitPython 装好后,**升级固件不用再按 BOOTSEL** —— 直接覆盖 `code.py`:

```bash
cp firmware/code.py "$PICO/code.py"
```

CircuitPython 检测到文件变化会自动重载。要升级 CircuitPython 本身
(换 UF2),才需要再按 BOOTSEL。

## 故障排除

| 问题 | 解决 |
|------|------|
| 第一次没出现 `CIRCUITPY` 驱动器 | 按住 BOOTSEL 重新拔插,重刷 UF2 |
| `boot.py` 错误导致无法启动 | 快速按两次 reset 进入安全模式,修复 `boot.py` |
| USB HID 设备未被系统识别 | 确认 `boot.py` 启用了 HID 描述符;拔插一次 |
| 串口没数据 | 确认 `usb_cdc.enable(data=True)`;确认连的是 **data** 端口不是 console |
| LED 完全不闪 | `code.py` 有语法错误或崩了 —— 用 Thonny / `screen` / `minicom` 连到 console 端口看 traceback |
| 只出现一个 COM 端口 | `boot.py` 没执行 —— 拔插板子 |
