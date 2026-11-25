---
sidebar_position: 2
title: "安装"
description: "在 Linux、macOS、WSL2 或原生 Windows 上安装 Nara Agent"
---

# 安装

从公开源码仓库安装 Nara。首次安装需要下载固定版本的工具，可能需要几分钟。

## 快速安装

### 一行安装命令（Linux / macOS / WSL2）

基于 git 的安装方式，跟踪 `main` 分支，可立即获取最新变更：

```bash
curl -fsSL https://raw.githubusercontent.com/engsathiago/nara-agent/main/scripts/install.sh | bash
```

### Windows（原生，PowerShell）

原生 Windows 无需 WSL 即可运行 Nara——CLI、gateway、TUI 和工具均可原生运行。（原生安装与 WSL2 安装可干净共存；唯一仅限 WSL2 的功能见下方功能说明。）遇到 bug 请[提交 issue](https://github.com/engsathiago/nara-agent/issues)。

打开 PowerShell 并运行：

```powershell
iex (irm https://raw.githubusercontent.com/engsathiago/nara-agent/main/scripts/install.ps1)
```

源码安装脚本克隆仓库，再由 PM 准备 Python 3.14、Node.js、npm、pnpm、ripgrep、FFmpeg 和 Python 依赖。
缺少 Git 时，脚本下载经过 SHA-256 验证的 Git for Windows 到工具存储目录。
它不替换系统 Git，也不再使用 MinGit 或 `nara\node` 的旧布局。
安装完成后，打开新终端以读取用户 PATH。

**当前发行状态：** 本项目尚未发布正式签名的桌面包、Termux APT 仓库、Docker 镜像或稳定版本。桌面应用可在本地从源码构建；参见[官方来源](./official-domains.md)。

### 功能与安装目录

Windows 的 CLI、TUI、gateway 和桌面应用可原生运行。
Dashboard 终端使用 `pywinpty`/ConPTY，不再是尚未实现的 POSIX-only 功能。
部分可选依赖仍受架构限制，请参阅 [Windows 指南](../user-guide/windows-native.md)。

| 安装方式 | 代码 | 命令入口 | 默认数据目录 |
|---|---|---|---|
| POSIX 源码脚本 | `~/.nara/nara-agent/` | `~/.local/bin/nara` 包装器 | `~/.nara/` |
| Windows 源码脚本 | `%LOCALAPPDATA%\nara\nara-agent\` | `%LOCALAPPDATA%\nara\bin\` | `%LOCALAPPDATA%\nara\` |

`NARA_HOME` 选择数据目录。POSIX 的 `--dir` 单独选择源码目录。
以 root 身份运行不再自动选择 `/usr/local/lib` 的 FHS 布局。
PM 的工具和 Python 环境代际位于独立目录，详见 [包管理](../reference/package-management.md)。
不要为了修复应用而删除整个数据目录。

### 安装后

重新加载 shell 并开始聊天：

```bash
source ~/.bashrc   # 或：source ~/.zshrc
nara             # 开始聊天！
```

如需稍后重新配置单项设置，使用以下专用命令：

```bash
nara model          # 选择 LLM 提供商和模型
nara tools          # 配置启用的工具
nara gateway setup  # 配置消息平台
nara config set     # 设置单个配置项
nara setup          # 或运行完整的设置向导一次性配置所有内容
```



---

## 前置条件

POSIX 源码脚本需要 Git、curl、tar 和 SHA-256 工具。源码构建还可能需要编译器和系统库。
Nara 要求 Python 3.14（`>=3.14,<3.15`），工具版本由 `pm/lock.json` 决定。
自包含桌面软件包不要求用户自行编译基础依赖。

:::tip Nix 用户
如果你使用 Nix（在 NixOS、macOS 或 Linux 上），有专门的配置路径，包含 Nix flake、声明式 NixOS 模块和可选容器模式。请参阅 **[Nix & NixOS 配置](./nix-setup.md)** 指南。
:::

---

## 手动 / 开发者安装

如果你想克隆仓库并从源码安装——用于贡献代码、从特定分支运行或完全控制虚拟环境——请参阅贡献指南中的[开发环境配置](../developer-guide/contributing.md)章节。

---

## 非 Sudo / 系统服务用户安装

以目标服务用户运行源码安装脚本。由管理员预先安装构建所需工具和 Chromium 的系统库。
当前脚本不运行 Playwright 的 `--with-deps`，也不提供按发行版选择的 sudo 回退。

安装后，将 `$HOME/.local/bin` 加入服务用户的 PATH，并运行 `nara doctor`。
请使用脚本生成的包装器，不要硬编码 `venv/bin/nara`。
Linux 用户服务需要在注销后继续运行时，由管理员为该用户启用 lingering。
详见 [消息 Gateway](../user-guide/messaging/index.md)。

---

## 故障排查

| 问题                        | 解决方案                                                                           |
| --------------------------- | ---------------------------------------------------------------------------------- |
| `nara: command not found` | 重新加载 shell（`source ~/.bashrc`）或检查 PATH                                    |
| `API key not set`           | 运行 `nara model` 配置提供商，或 `nara config set OPENROUTER_API_KEY your_key` |
| 更新后配置丢失              | 运行 `nara config check`，然后运行 `nara config migrate`                       |

如需更多诊断信息，运行 `nara doctor`——它会告诉你确切缺少什么以及如何修复。

## 安装方式自动检测

Nara 会自动检测安装方式（git 安装程序、Docker 或 NixOS），`nara update` 会打印对应路径的更新命令。无需设置任何环境变量——检测基于安装目录结构（`~/.nara/nara-agent/` 检出、Docker 镜像标记或 Nix store 路径）。`nara doctor` 也会在其环境摘要中显示检测到的安装方式。
