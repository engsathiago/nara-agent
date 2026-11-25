"""Shared platform registry for Nara Agent."""

from collections import OrderedDict
from typing import NamedTuple


class PlatformInfo(NamedTuple):
    """Metadata for a single platform entry."""
    label: str
    default_toolset: str


# Ordered so that TUI menus are deterministic.
PLATFORMS: OrderedDict[str, PlatformInfo] = OrderedDict([
    ("cli",            PlatformInfo(label="🖥️  CLI",            default_toolset="nara-cli")),
    ("telegram",       PlatformInfo(label="📱 Telegram",        default_toolset="nara-telegram")),
    ("discord",        PlatformInfo(label="💬 Discord",         default_toolset="nara-discord")),
    ("slack",          PlatformInfo(label="💼 Slack",           default_toolset="nara-slack")),
    ("whatsapp",       PlatformInfo(label="📱 WhatsApp",        default_toolset="nara-whatsapp")),
    ("whatsapp_cloud", PlatformInfo(label="📱 WhatsApp Business (Cloud)", default_toolset="nara-whatsapp")),
    ("signal",         PlatformInfo(label="📡 Signal",          default_toolset="nara-signal")),
    ("bluebubbles",    PlatformInfo(label="💙 BlueBubbles",     default_toolset="nara-bluebubbles")),
    ("email",          PlatformInfo(label="📧 Email",           default_toolset="nara-email")),
    ("mattermost",     PlatformInfo(label="💬 Mattermost",      default_toolset="nara-mattermost")),
    ("matrix",         PlatformInfo(label="💬 Matrix",          default_toolset="nara-matrix")),
    ("dingtalk",       PlatformInfo(label="💬 DingTalk",        default_toolset="nara-dingtalk")),
    ("feishu",         PlatformInfo(label="🪽 Feishu",          default_toolset="nara-feishu")),
    ("wecom",          PlatformInfo(label="💬 WeCom",           default_toolset="nara-wecom")),
    ("wecom_callback", PlatformInfo(label="💬 WeCom Callback",  default_toolset="nara-wecom-callback")),
    ("weixin",         PlatformInfo(label="💬 Weixin",          default_toolset="nara-weixin")),
    ("qqbot",          PlatformInfo(label="💬 QQBot",           default_toolset="nara-qqbot")),
    ("webhook",        PlatformInfo(label="🔗 Webhook",         default_toolset="nara-webhook")),
    ("api_server",     PlatformInfo(label="🌐 API Server",      default_toolset="nara-api-server")),
    ("cron",           PlatformInfo(label="⏰ Cron",            default_toolset="nara-cron")),
])


def _plugin_label(entry) -> str:
    return f"{entry.emoji}  {entry.label}" if entry.emoji else entry.label


def platform_label(key: str, default: str = "") -> str:
    """Return the display label for a platform key (builtin, then plugin registry), or *default*."""
    info = PLATFORMS.get(key)
    if info is not None:
        return info.label
    try:
        from gateway.platform_registry import platform_registry
        entry = platform_registry.get(key)
        if entry:
            return _plugin_label(entry)
    except Exception:
        pass
    return default


def get_all_platforms() -> OrderedDict[str, PlatformInfo]:
    """PLATFORMS plus plugin-registered platforms (appended after builtins) — use for menus."""
    merged = OrderedDict(PLATFORMS)
    try:
        from gateway.platform_registry import platform_registry
        for entry in platform_registry.plugin_entries():
            if entry.name not in merged:
                merged[entry.name] = PlatformInfo(_plugin_label(entry), f"nara-{entry.name}")
    except Exception:
        pass
    return merged
