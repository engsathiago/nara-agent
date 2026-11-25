---
title: Official Nara sources
description: Where the Nara project publishes its source, documentation, and installers.
---

# Official Nara sources

Nara is developed in the public [engsathiago/nara-agent](https://github.com/engsathiago/nara-agent) repository. The source code, issue tracker, license, and [upstream attribution](https://github.com/engsathiago/nara-agent/blob/main/UPSTREAM_PROVENANCE.md) live there.

| Address | Purpose |
|---|---|
| [github.com/engsathiago/nara-agent](https://github.com/engsathiago/nara-agent) | Source code, issues, and reviewed changes |
| [engsathiago.github.io/nara-agent/docs](https://engsathiago.github.io/nara-agent/docs/) | Documentation and public skill/plugin catalogs |
| [raw.githubusercontent.com/.../install.sh](https://raw.githubusercontent.com/engsathiago/nara-agent/main/scripts/install.sh) | Source installer for macOS and Linux |
| [raw.githubusercontent.com/.../install.ps1](https://raw.githubusercontent.com/engsathiago/nara-agent/main/scripts/install.ps1) | Source installer for Windows |

## Installing from source

```bash
curl -fsSL https://raw.githubusercontent.com/engsathiago/nara-agent/main/scripts/install.sh | bash
```

```powershell
iex (irm https://raw.githubusercontent.com/engsathiago/nara-agent/main/scripts/install.ps1)
```

The repository's `main` branch is the current source channel. The project has not published a versioned stable release or an official signed desktop package. Local desktop builds are not Developer ID signed or Apple notarized. Do not treat an image, binary, token, subscription, or account offered under the Nara name as an official project release unless this repository links to it.

Nous Research and its domains are independent upstream or optional provider resources; they are not the owner of this Nara distribution. The project preserves its upstream license and attribution without using upstream download, Docker, or account infrastructure as its own.

If you receive an unexpected installer link or request for credentials, compare the full host name and repository owner with the addresses above. Report impersonation through the hosting platform or in the [Nara issue tracker](https://github.com/engsathiago/nara-agent/issues).
