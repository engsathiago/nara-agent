# Tests for install.ps1's NaraHome/InstallDir separation guard (#124526).
#
# Run from a PowerShell prompt:
#
#   pwsh -NoProfile -ExecutionPolicy Bypass -File scripts/tests/test-install-ps1-store-guard.ps1
#
# Background: passing -NaraHome and -InstallDir as the same path (or a
# NaraHome nested inside -InstallDir) makes the pm tool store land at
# <InstallDir>\tools, INSIDE the checkout. Two failures follow: the
# repository stage's occupied-directory preflight refuses every retry after
# the first run populated the folder ("exists and is not a Nara git
# checkout"), and `git stash --include-untracked` would sweep the toolchain
# into the stash. The installer now refuses the combination up front, before
# any download, unless NARA_RUNTIME_DIR parks the store elsewhere.
#
# HOW THIS RUNS THE CODE: by executing install.ps1 as a real subprocess with
# crafted -NaraHome / -InstallDir arguments. -ShowResolvedPaths is a
# side-effect-free early exit that runs AFTER Initialize-ResolvedPaths, so
# the guard executes exactly as during an install. The refusal is a `throw`,
# which under -File exits the child non-zero before the JSON is printed; the
# accepted configurations print the resolved-path JSON with the requested
# paths intact. Nothing here parses install.ps1's source (AGENTS.md bans
# source-reading tests: they pass on broken code and fail on correct
# refactors).

$ErrorActionPreference = "Stop"
$repoRoot = Split-Path -Parent (Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path))
$installScript = Join-Path $repoRoot "scripts/install.ps1"

if (-not (Test-Path $installScript)) {
    throw "Could not locate install.ps1 at $installScript"
}

$failures = 0

function Assert-True {
    param([bool]$Condition, [Parameter(Mandatory = $true)][string]$Label)
    if (-not $Condition) {
        Write-Host "FAIL: $Label" -ForegroundColor Red
        $script:failures++
    } else {
        Write-Host "OK: $Label" -ForegroundColor Green
    }
}

# Run install.ps1 -ShowResolvedPaths with explicit -NaraHome/-InstallDir and
# capture (exit code, stdout, stderr). The call operator, not Start-Process:
# `&` inherits this process's environment on every host, and stderr is merged
# so Windows PowerShell 5.1's NativeCommandError records cannot fail the lane.
function Invoke-ResolvedPaths {
    param([string[]]$ExtraArgs = @())

    $psExe = (Get-Process -Id $PID).Path
    $outFile = [System.IO.Path]::GetTempFileName()
    $savedRuntimeDir = [Environment]::GetEnvironmentVariable('NARA_RUNTIME_DIR')
    $savedNaraHome = [Environment]::GetEnvironmentVariable('NARA_HOME')
    try {
        if ($null -eq $savedRuntimeDir) {
            Remove-Item Env:NARA_RUNTIME_DIR -ErrorAction SilentlyContinue
        } else {
            $env:NARA_RUNTIME_DIR = $savedRuntimeDir
        }
        if ($null -eq $savedNaraHome) {
            Remove-Item Env:NARA_HOME -ErrorAction SilentlyContinue
        } else {
            $env:NARA_HOME = $savedNaraHome
        }
        $callArgs = @('-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', $installScript) + $ExtraArgs + @('-ShowResolvedPaths')
        $prevEAP = $ErrorActionPreference
        $ErrorActionPreference = 'Continue'
        $global:LASTEXITCODE = 0
        try {
            & $psExe @callArgs *> $outFile
        } finally {
            $ErrorActionPreference = $prevEAP
        }
        $exitCode = $LASTEXITCODE
        $raw = @(Get-Content -LiteralPath $outFile -ErrorAction SilentlyContinue)
        $stdout = ($raw | Where-Object { $_ -notlike '`[nara`]*' }) -join "`n"
        $stderr = ($raw | Where-Object { $_ -like '`[nara`]*' -or $_ -match 'NaraHome|install directory|tool store' }) -join "`n"
        return @{ ExitCode = $exitCode; Stdout = $stdout; All = ($raw -join "`n") }
    } finally {
        if ($null -eq $savedRuntimeDir) {
            Remove-Item Env:NARA_RUNTIME_DIR -ErrorAction SilentlyContinue
        } else {
            $env:NARA_RUNTIME_DIR = $savedRuntimeDir
        }
        if ($null -eq $savedNaraHome) {
            Remove-Item Env:NARA_HOME -ErrorAction SilentlyContinue
        } else {
            $env:NARA_HOME = $savedNaraHome
        }
        Remove-Item -LiteralPath $outFile -Force -ErrorAction SilentlyContinue
    }
}

$base = Join-Path ([System.IO.Path]::GetTempPath()) ("nara-store-guard-" + [guid]::NewGuid())
$home1 = Join-Path $base 'home1'
$dir1 = Join-Path $base 'checkout1'
$insideHome = Join-Path $base 'checkout2'      # NaraHome nested inside InstallDir
$insideDir = Join-Path $base 'checkout2'       # the InstallDir that contains it

try {
    # 1. Same path for both: refused, before any download.
    $r = Invoke-ResolvedPaths @('-NaraHome', $home1, '-InstallDir', $home1)
    Assert-True ($r.ExitCode -ne 0) 'same NaraHome and InstallDir is refused (non-zero exit)'
    Assert-True ($r.All -match 'tool store would land inside the checkout') 'refusal names the tool-store cause'

    # 2. NaraHome nested inside InstallDir: refused for the same reason.
    $r = Invoke-ResolvedPaths @('-NaraHome', $insideHome, '-InstallDir', $insideDir)
    Assert-True ($r.ExitCode -ne 0) 'NaraHome inside InstallDir is refused (non-zero exit)'

    # 3. Distinct paths: accepted, and the caller's paths survive verbatim.
    $r = Invoke-ResolvedPaths @('-NaraHome', $home1, '-InstallDir', $dir1)
    Assert-True ($r.ExitCode -eq 0) "distinct paths are accepted (exit $($r.ExitCode))"
    $paths = $null
    try { $paths = $r.Stdout | ConvertFrom-Json } catch { $paths = $null }
    Assert-True ($null -ne $paths) 'accepted run prints the resolved-path JSON'
    if ($paths) {
        Assert-True ("$($paths.nara_home)" -eq $home1) 'nara_home echoes the requested -NaraHome'
        Assert-True ("$($paths.install_dir)" -eq $dir1) 'install_dir echoes the requested -InstallDir'
    }

    # 4. NARA_RUNTIME_DIR outside the checkout lifts the refusal: the store
    #    no longer lands inside InstallDir, so the configuration is legitimate.
    $storeElsewhere = Join-Path $base 'store'
    $saved = $env:NARA_RUNTIME_DIR
    try {
        $env:NARA_RUNTIME_DIR = $storeElsewhere
        $r = Invoke-ResolvedPaths @('-NaraHome', $home1, '-InstallDir', $home1)
        Assert-True ($r.ExitCode -eq 0) "NARA_RUNTIME_DIR outside lifts the refusal (exit $($r.ExitCode))"
    } finally {
        if ($null -eq $saved) {
            Remove-Item Env:NARA_RUNTIME_DIR -ErrorAction SilentlyContinue
        } else {
            $env:NARA_RUNTIME_DIR = $saved
        }
    }

    # 5. Default derivation never trips the guard: InstallDir defaults to
    #    <NaraHome>\nara-agent, which is a child, not a parent.
    $r = Invoke-ResolvedPaths @('-NaraHome', $home1)
    Assert-True ($r.ExitCode -eq 0) "default -InstallDir under -NaraHome stays accepted (exit $($r.ExitCode))"
    $paths = $null
    try { $paths = $r.Stdout | ConvertFrom-Json } catch { $paths = $null }
    if ($paths) {
        Assert-True ("$($paths.install_dir)" -eq (Join-Path $home1 'nara-agent')) 'default install_dir derives under nara_home'
    }
} finally {
    Remove-Item -LiteralPath $base -Recurse -Force -ErrorAction SilentlyContinue
}

if ($failures -gt 0) {
    Write-Host "$failures assertion(s) failed." -ForegroundColor Red
    exit 1
}
Write-Host 'NaraHome/InstallDir separation guard tests passed.' -ForegroundColor Green
exit 0
