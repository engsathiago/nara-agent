---
sidebar_position: 3
title: "Android / Termux"
description: "Status of the planned Nara Agent package for Android / Termux"
---

# Nara on Android with Termux

:::danger Termux package unavailable
Nara has not published its own signed Termux APT repository or signing key.
Do not install a package or trust a key from the original project's archive
as if it were a Nara release. This page describes the intended packaging
contract; installation commands will be added after a signed Nara package
passes device testing.
:::

The planned package targets **aarch64 (arm64-v8a)** Android devices.
Two APT channels are defined by the build code, but neither is published yet:

| Channel | APT suite | Contents |
| --- | --- | --- |
| `stable` | `nara-stable` | Tagged `vMAJOR.MINOR.PATCH` releases that passed the stable release gate |
| `canary` | `nara-canary` | Prerelease builds from canary tags; versions carry `~canary.<timestamp>` |

When published, `stable` will carry releases and `canary` will carry prereleases.

The package includes Python, Node.js, npm, uv, ripgrep, ffmpeg, and their runtime libraries.
The first `nara dashboard` downloads pnpm and installs the web UI's JavaScript dependencies.
CI builds the native Python wheels and the TUI before it creates the package.
The device does not compile core dependencies or assemble its base Python
environment during installation. The package uses Python 3.14 with the bionic
interpreter pin; it does not require the same patch version as desktop CPython.
The wheel closure is core plus `acp`, not all desktop extras.

## Installation status

Use the standard [Termux](https://termux.dev/) application when a Nara package
is available. The planned package requires its standard prefix,
`/data/data/com.termux/files/usr`, and targets Android API 24
(`android_24_arm64_v8a`). Other architectures and renamed Termux application
packages are outside the current build contract. The desktop/server
`install.sh` and glibc Linux archives do not target Termux.

There is no Nara-owned APT URL, public key fingerprint, or verified install
command to publish yet.

The `nara`, `nara-agent`, and `nara-acp` commands use the packaged runtimes.
They do not require Termux's `python` or `nodejs` packages.

## Files and updates

| Contents | Location |
| --- | --- |
| Package files | `$PREFIX/lib/nara-agent/` |
| Command symlinks | `$PREFIX/bin/nara`, `$PREFIX/bin/nara-agent`, `$PREFIX/bin/nara-acp` |
| Configuration and user data | `~/.nara/`, or the selected `NARA_HOME` |

After publication, updates will use APT:

```bash
pkg update
pkg upgrade nara-agent
```

`nara update` refuses to modify an APT-owned installation.
It prints the package-manager command instead.
Canary versions contain `~canary.<timestamp>` and sort before the corresponding
stable version. Each suite only lists its own channel's packages; to move
between channels, edit the channel path and suite in `nara-agent.list`, then
`pkg update && pkg upgrade nara-agent`.

## Gateway

This APT installation does not use systemd, launchd, or Windows Scheduled Tasks.
Run the gateway in a Termux session:

```bash
nara gateway run
```

For a background process:

```bash
mkdir -p "${NARA_HOME:-$HOME/.nara}/logs"
nohup nara gateway run >> "${NARA_HOME:-$HOME/.nara}/logs/gateway.log" 2>&1 &
```

:::warning Android process limits
Android can suspend or terminate background Termux processes.
Battery optimization exemptions and `termux-wake-lock` can help, but do not guarantee persistent operation.
:::

## Limits

The package does not include the `nemo-relay` exporter. Its vendored build
toolchain does not support this target.

The package does not include Electron, a bundled Chromium, or desktop
computer-use tools. The browser tool launches a system `chromium` when one is on
`PATH` (`pkg install chromium`, where your repository provides it); without one,
browsing is unavailable and the browser tool says so. A local Docker daemon is not part of the Termux environment. Remote
services have their own requirements and connectivity limits.

Phone-native Termux:API microphone and clipboard adapters are not provided by
this package path. The prebuilt CLI/TUI is not proof of local voice or wake-word
support. Optional integrations and third-party plugins can require dependencies
that do not support Android.

Python 3.14 on this target reports `sys.platform == "android"`. A dependency
or skill gated only to `linux` is not automatically available on Android.

## Uninstall

```bash
pkg uninstall nara-agent
```

APT removes the package and its command symlinks. It preserves your configuration, sessions, skills, and memories.

## Troubleshooting

- **Package not found:** verify the repository entry, then run `pkg update`.
- **Signature error:** verify the public key fingerprint. Do not use an unsigned repository or bypass the error.
- **Missing command:** verify that `$PREFIX/bin` is on `PATH`, or reinstall the package.
- **Missing library or TUI bundle:** report `nara --version` and the complete error. The core package must not require a local rebuild.
- **Gateway stops with the screen off:** review Android's battery and background-process limits.

For general diagnostics, run `nara doctor`.
