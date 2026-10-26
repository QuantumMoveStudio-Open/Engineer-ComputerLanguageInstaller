# 📋 工程师-计算机语言安装器 | QuantumMoveStudio Installer

> 一个 **单文件、零依赖** 的跨平台开发环境一键安装器。
> 自动测速镜像源、智能选择安装方式、失败自动兜底 —— 让你在 Android 手机 / Windows / Linux / FreeBSD 上都能一条命令搭好开发环境。

![Platform](https://img.shields.io/badge/platform-Android%20%7C%20Windows%20%7C%20Debian%20%7C%20Ubuntu%20%7C%20FreeBSD-blue)
![Python](https://img.shields.io/badge/python-3.8%2B-green)
![License](https://img.shields.io/badge/license-MIT-orange)
![Size](https://img.shields.io/badge/size-%E5%8D%95%E6%96%87%E4%BB%B6%20.py-informational)

---

## ✨ 特性

- 📦 **单文件即用**：只有一个 `computer_language_installer.py`，标准库实现，无需预装任何第三方包
- 🌏 **镜像源自动测速**：内置阿里云、腾讯云、华为云、百度云、清华、中科大、上交、南大、复旦、浙大、武大、北大、中科院等 20 个国内镜像源，并发测速自动切换最快源（pip / npm / apt / Go / Maven / Cargo / Composer 全覆盖）
- 🔀 **多包管理器智能分发**：同一组件自动尝试 winget → npm → pip → cargo → go → composer → maven 等多条安装通道，一条失败自动换下一条
- 🛡️ **失败不中断**：任一组件安装失败时，打印官方下载地址并继续安装下一项，最后生成汇总报告
- 🖥️ **双模式交互**：Windows 自动弹出 tkinter 可视化多选窗口；其他平台使用控制台数字多选（「、」分隔）
- 🔍 **已装自动跳过**：安装前扫描环境中已存在的组件，只装缺的
- 💾 **磁盘扫描**：列出各磁盘/分区的盘符、名称、剩余空间、总容量、类型，安装前可选安装路径（回车默认 C 盘）
- 🧪 **干跑模式**：`--dry-run` 只演练流程，不真正执行安装命令

## 🖥️ 支持平台

| 平台 | 包管理器 |
| --- | --- |
| Android (Termux) | `pkg` / `pip` / `npm` / `cargo` / `go` / `composer` |
| Windows | `winget` / `npm` / `pip` / `cargo` / `go` / `composer` / `maven` |
| Debian / Ubuntu | `apt` / `snap` / `npm` / `pip` / `cargo` / `go` / `composer` / `maven` |
| FreeBSD | `pkg` / `npm` / `pip` / `cargo` / `go` / `composer` / `maven` |

## 📦 可安装组件（约 136 项）

| 分类 | 必选 | 示例 |
| --- | --- | --- |
| 语言 | ✅ 必选 | Java、Go、PHP、Rust |
| 运行环境 | 可选 | Node.js、Python、Deno、Bun、Conda … |
| 工具 | 可选 | Git、Docker、Nginx、Redis、MongoDB … |
| 中间件 | 可选 | Kafka、RabbitMQ、Etcd … |
| 框架 | 可选 | FastAPI、Django、Flask、Spring Boot、Gin … |
| 第三方库 | 可选 | NumPy、Pandas、Requests、serde、tokio … |

## 🚀 快速开始

### Android (Termux)

```bash
pkg install -y python
python computer_language_installer.py
```

### Windows

```powershell
python computer_language_installer.py
```

> 需要 Python 3.8+，tkinter 可视化窗口会自动弹出（可用 `--no-gui` 关闭）。

### Debian / Ubuntu

```bash
sudo python3 computer_language_installer.py
```

### FreeBSD

```sh
python3 computer_language_installer.py
```

## ⚙️ 命令行参数

| 参数 | 说明 |
| --- | --- |
| `-p` / `-t` / `--timeout` | 单条安装命令超时时间（秒），默认 900 |
| `-r` / `--root` | 指定安装根目录，跳过交互式路径输入 |
| `--no-gui` | Windows 下也使用控制台数字选择 |
| `--dry-run` | 只演练不真正执行安装命令 |
| `--no-mirror` | 跳过源测速，直接使用系统默认源 |

示例：

```bash
python computer_language_installer.py --dry-run
python computer_language_installer.py -r D:\\dev -t 1200
```

## 🔁 安装流程

```
启动横幅 → 平台检测 → 磁盘扫描 → 镜像源测速（自动最快源）
→ 生成组件清单（已安装自动跳过）→ 交互式多选
→ 逐项安装（多通道兜底，失败打印下载地址继续）
→ 输出安装报告
```

## 🧠 智能兜底机制（亮点）

- **pip 编译失败自适应**：检测到 `externally-managed` / 权限 / 编译错误时，自动以 `--break-system-packages`、`--user`、安装 Rust/编译工具链、`--no-build-isolation` 等策略逐级重试（Termux 上自动通过 TUR 仓库补齐 `maturin`）
- **apt 镜像非破坏性切换**：通过独立 sourcelist 临时文件切源，绝不修改系统 `/etc/apt/sources.list`，失败自动回落官方源
- **Go / Rust / Maven 依赖直装**：临时 module + `go get`、临时 cargo 工程 + `cargo add`、解析 `maven-metadata.xml` 直下 jar/pom，多级代理兜底
- **Cargo 镜像零污染**：使用一次性 `--config` 文件，不写入 `~/.cargo/config.toml`

## 📄 开源信息

- 🪪 开发者｜Developer：**量方易动工作室 | QuantumMoveStudio**
- 🌐 官网｜Official website：<https://quantummovestudio.dpdns.org>
- 🪧 开源平台｜Open-source platform：**Github**
- 🏢 开源部｜Open Source Department：<https://github.com/QuantumMoveStudio-Open/>
- 📦 合作方镜像站｜Partner mirror site：<https://sunworld-fuchuan-technology-organization.dnsglobalnodes.dpdns.org/Resources>

## ⚠️ 免责声明

本工具会调用系统包管理器执行安装命令，请在了解其行为后使用。安装过程产生的任何系统变更由使用者自行承担。建议先以 `--dry-run` 模式演练。

## 📜 License

[MIT](LICENSE) © 2026 量方易动工作室（QuantumMoveStudio）