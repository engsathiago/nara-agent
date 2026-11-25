from __future__ import annotations

import shutil
from pathlib import Path

import extensions.nara_temporal_memory.nara_temporal as provider_source
from nara_constants import reset_nara_home_override, set_nara_home_override
from plugins.memory import list_memory_provider_names, load_memory_provider


def test_external_nara_temporal_is_discoverable_and_available(tmp_path):
    plugin_source = Path(provider_source.__file__).parent
    plugin_target = tmp_path / "plugins" / "nara_temporal"
    plugin_target.parent.mkdir(parents=True)
    shutil.copytree(plugin_source, plugin_target)
    token = set_nara_home_override(tmp_path)
    try:
        assert "nara_temporal" in list_memory_provider_names()
        provider = load_memory_provider("nara_temporal", register_skills=False)
        assert provider is not None
        assert provider.name == "nara_temporal"
        assert provider.is_available() is True
    finally:
        reset_nara_home_override(token)
