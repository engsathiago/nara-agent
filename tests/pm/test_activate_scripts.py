"""``activate`` / ``activate.ps1``: an interactive shell takes on the environment and gives it back.

What a process launched under ``scripts/run-in-nara-env`` sees is covered in
tests/scripts/test_run_in_nara_env.py; how the environment is composed, in
test_environment_script.py; the fish port, in test_activate_fish.py.
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

from tests.pm.activation_support import (
    ACTIVATE, ACTIVATE_PS1, CANARY, SETUP_NARA_PS1, SETUP_NARA_SH, bash, bash_env,
    child_env, fake_store, isolated_checkout, posix, powershell, spawnable_python,
)


def test_bash_scripts_pass_syntax_check():
    for script in (ACTIVATE, SETUP_NARA_SH):
        result = subprocess.run(
            [bash(), "-n", posix(script)], capture_output=True, text=True, env=child_env(),
            check=False,
        )
        assert result.returncode == 0, f"{script.name}: {result.stderr}"


@pytest.mark.platforms("windows")
def test_source_activate_exports_the_pm_env(tmp_path: Path):
    root = isolated_checkout(tmp_path)
    store, _ = fake_store(tmp_path)
    script = (
        f'source "{posix(root / "activate")}" && '
        f'test -n "$__NARA_ACTIVATED" && '
        f'printf "%s" "${CANARY}"'
    )
    result = subprocess.run(
        [bash(), "-c", script],
        capture_output=True,
        text=True,
        cwd=posix(tmp_path),
        env=bash_env(store),
        check=False,
    )
    assert result.returncode == 0, result.stderr
    assert result.stdout == "env-ok"


@pytest.mark.platforms("windows")
def test_activate_exports_the_sentinel_to_child_processes(tmp_path: Path):
    """Repo scripts read activation from the environment, so the sentinel must
    survive into an exec'd child (a plain shell variable would not), and
    deactivate must take it back out."""
    root = isolated_checkout(tmp_path)
    store, _ = fake_store(tmp_path)
    script = (
        f'source "{posix(root / "activate")}" && '
        f'"$BASH" -c \'test -n "$__NARA_ACTIVATED"\' && '
        f'deactivate && '
        f'! "$BASH" -c \'test -n "$__NARA_ACTIVATED"\' && '
        f'echo exported-then-cleared'
    )
    result = subprocess.run(
        [bash(), "-c", script],
        capture_output=True,
        text=True,
        cwd=posix(tmp_path),
        env=bash_env(store),
        check=False,
    )
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "exported-then-cleared"


@pytest.mark.platforms("windows")
def test_deactivate_restores_the_prior_shell(tmp_path: Path):
    root = isolated_checkout(tmp_path)
    store, _ = fake_store(tmp_path)
    script = (
        f'source "{posix(root / "activate")}" && deactivate && '
        f'test -z "${{{CANARY}+set}}" && '
        f'test -z "${{__NARA_ACTIVATED+set}}" && '
        f"! declare -F deactivate >/dev/null && "
        f'echo restored'
    )
    result = subprocess.run(
        [bash(), "-c", script],
        capture_output=True,
        text=True,
        cwd=posix(tmp_path),
        env=bash_env(store),
        check=False,
    )
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "restored"


@pytest.mark.platforms("windows")
def test_activate_leaves_the_shell_paths_in_posix_form(tmp_path: Path):
    """The pm env is read by a native Windows Python, which sees PATH, HOME and
    the temp variables in Windows form. Exported verbatim, `C:\\a;C:\\b` left
    bash without a usable PATH, so every command after activation failed."""
    root = isolated_checkout(tmp_path)
    store, _ = fake_store(tmp_path)
    script = (
        'prior_home="$HOME" prior_tmp="$TMP" && '
        f'source "{posix(root / "activate")}" && '
        'command -v basename >/dev/null && '
        'case "$PATH" in *";"*|*"\\\\"*) exit 3;; esac && '
        'test "$HOME" = "$prior_home" && test "$TMP" = "$prior_tmp" && '
        'echo posix'
    )
    result = subprocess.run(
        [bash(), "-c", script],
        capture_output=True,
        text=True,
        cwd=posix(tmp_path),
        env=bash_env(store),
        check=False,
    )
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "posix"


def test_activate_fails_cleanly_without_a_store(tmp_path: Path):
    env = bash_env(tmp_path / "empty-store")
    isolated = isolated_checkout(tmp_path) / "activate"
    script = (
        f'source "{posix(isolated)}" 2>/dev/null; '
        f'test $? -ne 0 && echo refused'
    )
    result = subprocess.run(
        [bash(), "-c", script],
        capture_output=True,
        text=True,
        cwd=posix(tmp_path),
        env=env,
        check=False,
    )
    # Without any provisioned python the source must refuse — never
    # silently no-op with a half-activated shell.
    assert "refused" in result.stdout


@pytest.mark.platforms("posix")
def test_zsh_bootstrap_skips_unmatched_candidate_stores(tmp_path: Path):
    """A missing earlier store must not make zsh abort before a valid later one."""

    zsh = shutil.which("zsh")
    if zsh is None:
        pytest.skip("zsh is unavailable")
    root = isolated_checkout(tmp_path)
    home = tmp_path / "home"
    store, _ = fake_store(home / ".nara")
    tools = home / ".nara" / "tools"
    store.rename(tools)
    env = bash_env(tools)
    env.pop("NARA_RUNTIME_DIR", None)
    env["NARA_HOME"] = posix(home / ".nara")
    script = (
        f'source "{posix(root / "scripts/_activation.sh")}" && '
        f'nara_bootstrap_python "{posix(root)}"'
    )

    result = subprocess.run(
        [zsh, "-c", script], capture_output=True, text=True,
        cwd=posix(tmp_path), env=env, check=False,
    )

    assert result.returncode == 0, result.stderr
    assert result.stdout.strip().endswith("/bin/python3")


@pytest.mark.platforms("posix")
def test_zsh_activation_and_deactivation_support_space_in_checkout(tmp_path: Path):
    zsh = shutil.which("zsh")
    if zsh is None:
        pytest.skip("zsh is unavailable")
    root = isolated_checkout(tmp_path)
    store, _ = fake_store(tmp_path)
    script = (
        f'source "{posix(root / "activate")}" && '
        f'test "${{{CANARY}}}" = env-ok && '
        'deactivate && '
        f'test -z "${{{CANARY}+set}}"'
    )

    result = subprocess.run(
        [zsh, "-c", script], capture_output=True, text=True,
        cwd=posix(tmp_path), env=bash_env(store), check=False,
    )

    assert result.returncode == 0, result.stdout + result.stderr


def test_powershell_scripts_parse():
    """Parse-check the PowerShell entry points; skip gracefully when no
    PowerShell host is available."""
    ps = powershell()
    if ps is None:
        pytest.skip("no PowerShell host available")
    for script in (ACTIVATE_PS1, SETUP_NARA_PS1):
        result = subprocess.run(
            [
                ps,
                "-NoProfile",
                "-NonInteractive",
                "-ExecutionPolicy",
                "Bypass",
                "-Command",
                f"$errs = $null; $null = [System.Management.Automation.Language.Parser]::ParseFile("
                f"'{script}', [ref]$null, [ref]$errs); "
                f"if ($errs.Count) {{ $errs | ForEach-Object {{ $_.Message }}; exit 1 }}",
            ],
            capture_output=True,
            text=True,
            check=False,
        )
        assert result.returncode == 0, f"{script.name}: {result.stdout}{result.stderr}"


@pytest.mark.platforms("windows")
def test_powershell_activate_exports_and_deactivates(tmp_path: Path):
    # Native venv redirectors resolve the base DLLs/stdlib without copying CPython.
    root = isolated_checkout(tmp_path)
    env = bash_env(tmp_path / "store")
    subprocess.run(
        [str(spawnable_python()), "-m", "venv", "--without-pip", str(root / ".venv")],
        check=True, capture_output=True, env=env, timeout=60,
    )
    ps = powershell()
    assert ps, "native Windows test requires PowerShell"
    result = subprocess.run(
        [ps, "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass", "-Command",
         f"$ErrorActionPreference='Stop'; $env:PYTHONPATH='caller-original'; "
         f". '{root / 'activate.ps1'}'; "
         "Write-Output ('active=' + $env:PYTHONPATH); deactivate; "
         "Write-Output ('after=' + $env:PYTHONPATH)"],
        capture_output=True, text=True, cwd=str(tmp_path), env=env, timeout=40,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    # Nothing is committed, so the checkout alone: the bootstrap .venv's packages never leak in.
    assert f"active={root}\n" in result.stdout
    assert "after=caller-original" in result.stdout
