"""Tests for get_nara_home() profile-mode fallback warning.

Regression test for https://github.com/NousResearch/nara-agent/issues/18594.

When NARA_HOME is unset but an active_profile file indicates a non-default
profile is active, get_nara_home() should:
  1. STILL return ~/.nara (raising would brick 30+ module-level callers)
  2. Emit a loud one-shot warning to stderr so operators can diagnose
     cross-profile data contamination after the fact.

The warning goes to stderr directly (not through logging) because this
function is called at module-import time from 30+ sites, often before the
logging subsystem has been configured.
"""

from pathlib import Path

import pytest


@pytest.fixture
def fresh_constants(monkeypatch, tmp_path):
    """Import nara_constants fresh and reset the one-shot warn flag."""
    import importlib
    import nara_constants
    importlib.reload(nara_constants)
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    monkeypatch.delenv("NARA_HOME", raising=False)
    return nara_constants


class TestGetNaraHomeProfileWarning:
    @pytest.mark.platforms("linux")
    def test_classic_mode_no_active_profile_no_warning(
        self, fresh_constants, tmp_path, capsys
    ):
        """Classic mode: no active_profile file → silent, returns ~/.nara."""
        result = fresh_constants.get_nara_home()
        assert result == tmp_path / ".nara"
        assert "NARA_HOME fallback" not in capsys.readouterr().err
    @pytest.mark.platforms("linux")
    def test_named_profile_unset_home_warns_once(
        self, fresh_constants, tmp_path, capsys
    ):
        """active_profile=coder + NARA_HOME unset → warn loudly, still return fallback."""
        nara_dir = tmp_path / ".nara"
        nara_dir.mkdir()
        (nara_dir / "active_profile").write_text("coder\n")

        result = fresh_constants.get_nara_home()

        # 1. Still returns the fallback — no import-time crash
        assert result == tmp_path / ".nara"
        # 2. Stderr got the warning exactly once
        err = capsys.readouterr().err
        assert err.count("NARA_HOME fallback") == 1
        assert "'coder'" in err

        # 3. One-shot: second and third calls don't re-warn
        fresh_constants.get_nara_home()
        fresh_constants.get_nara_home()
        err2 = capsys.readouterr().err
        assert "NARA_HOME fallback" not in err2

    def test_nara_home_set_suppresses_warning(
        self, fresh_constants, tmp_path, capsys, monkeypatch
    ):
        """Even if active_profile is 'coder', setting NARA_HOME suppresses warning."""
        profile_dir = tmp_path / ".nara" / "profiles" / "coder"
        profile_dir.mkdir(parents=True)
        (tmp_path / ".nara" / "active_profile").write_text("coder\n")
        monkeypatch.setenv("NARA_HOME", str(profile_dir))

        result = fresh_constants.get_nara_home()

        assert result == profile_dir
        assert "NARA_HOME fallback" not in capsys.readouterr().err

    @pytest.mark.platforms("linux")
    def test_unreadable_active_profile_no_crash(
        self, fresh_constants, tmp_path, capsys
    ):
        """active_profile that can't be decoded → fall through silently."""
        nara_dir = tmp_path / ".nara"
        nara_dir.mkdir()
        # Write bytes that aren't valid utf-8
        (nara_dir / "active_profile").write_bytes(b"\xff\xfe\x00\x00")

        result = fresh_constants.get_nara_home()

        assert result == tmp_path / ".nara"
        # Shouldn't crash; shouldn't warn either (can't tell what profile was intended)
        assert "NARA_HOME fallback" not in capsys.readouterr().err


class TestBootReadersBeforeProfileOverride:
    """Readers that run before the CLI applies the sticky ``active_profile`` must not warn.

    ``nara_bootstrap`` points ``TMPDIR`` at the scratch dir of the *process* home during
    import, and ``main._apply_profile_override`` re-homes the process a few lines later. A
    caller that already resolved its home must not send the policy back through
    ``get_nara_home()``: for a sticky-profile user with ``NARA_HOME`` unset in a plain
    shell that lookup falls back to the default profile and warns, on every ``nara``
    command, while nothing lands in the wrong place. Same fix the parser's ``_cfg_path()``
    carries for the ``--no-config`` help string.
    """

    def test_scratch_export_uses_the_process_home_silently(
        self, fresh_constants, tmp_path, capsys
    ):
        """Boot scratch setup: silent, and pointed at the home the bootstrap resolved."""
        nara_dir = tmp_path / ".nara"
        (nara_dir / "profiles" / "coder").mkdir(parents=True)
        (nara_dir / "active_profile").write_text("coder\n")
        capsys.readouterr()  # drop anything the setup above printed

        env = {"PATH": "/usr/bin:/bin"}
        assert fresh_constants.apply_scratch_tmp_env(env) is True

        assert env["TMPDIR"] == str(nara_dir / "cache" / "scratch")
        assert "NARA_HOME fallback" not in capsys.readouterr().err

    def test_explicit_home_scratch_dir_never_reads_the_effective_home(
        self, fresh_constants, tmp_path, capsys
    ):
        """A caller that passes a home (`nara doctor` for another profile) stays silent."""
        nara_dir = tmp_path / ".nara"
        profile_dir = nara_dir / "profiles" / "coder"
        profile_dir.mkdir(parents=True)
        (nara_dir / "active_profile").write_text("coder\n")
        capsys.readouterr()  # drop anything the setup above printed

        scratch = fresh_constants.get_scratch_dir(profile_dir)

        assert scratch == profile_dir / "cache" / "scratch"
        assert scratch.is_dir()
        assert "NARA_HOME fallback" not in capsys.readouterr().err
