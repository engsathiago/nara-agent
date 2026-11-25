"""A native ticket binds its own home even when a foreign home override is ambient."""
from pathlib import Path
from types import SimpleNamespace


def test_launch_ticket_overrides_foreign_ambient_scope(tmp_path, monkeypatch):
    from agent.secret_scope import get_secret
    from nara_cli.dashboard_auth.native_http import native_profile_scope
    from nara_cli.web_server_profiles import _config_profile_scope
    from nara_constants import get_nara_home, reset_nara_home_override, set_nara_home_override
    home = tmp_path / '.nara'
    home.mkdir()
    monkeypatch.setenv('NARA_HOME', str(home))
    monkeypatch.setattr(Path, 'home', lambda: tmp_path)
    monkeypatch.setenv('SCOPE_SENTINEL', 'launch')
    beta = home / 'profiles' / 'beta'
    beta.mkdir(parents=True)
    (beta / '.env').write_text('SCOPE_SENTINEL=beta\n', encoding='utf-8')
    ambient = set_nara_home_override(str(beta))
    try:
        request = SimpleNamespace(state=SimpleNamespace(native_http_principal={'profile_id': str(home)}))
        with native_profile_scope(request), _config_profile_scope(None):
            seen = (get_nara_home(), get_secret('SCOPE_SENTINEL'))
    finally:
        reset_nara_home_override(ambient)
    assert seen == (home, 'launch')
