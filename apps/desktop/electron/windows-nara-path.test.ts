// Unit tests for the pure Windows `nara` resolution helpers extracted from
// main.ts's findOnPath(), handOffWindowsBootstrapRecovery(), and
// unwrapWindowsVenvNaraCommand(). These pin the two Windows resolution bugs
// that caused desktop reinstall loops:
//   1. buildPathExtCandidates() — PATHEXT extensions must be tried BEFORE the
//      empty extension, or an extensionless Git-Bash `nara` shim shadows
//      the real nara.cmd/nara.exe.
//   2. chooseUpdaterArgs() — must distinguish a runnable updater from stale
//      install provenance. The bootstrap marker can outlive the venv, and a
//      partial venv cannot run the updater; those states require --repair.
//   3. resolveVenvNaraCommand() — must probe the venv python via
//      canImportNaraCli() before trusting it, or a broken venv gets
//      re-selected forever instead of falling through to bootstrap.

import assert from 'node:assert/strict'

import { test } from 'vitest'

import { buildPathExtCandidates, chooseUpdaterArgs, resolveVenvNaraCommand } from './windows-nara-path'

test('buildPathExtCandidates: Windows tries PATHEXT extensions before the empty extension', () => {
  const extensions = buildPathExtCandidates('.COM;.EXE;.BAT;.CMD', true)

  assert.deepEqual(extensions, ['.COM', '.EXE', '.BAT', '.CMD', ''])
  assert.equal(extensions[extensions.length - 1], '', 'empty extension must be last, not first')
  assert.notEqual(extensions[0], '', 'the buggy empty-extension-first order must not return')
})

test('buildPathExtCandidates: defaults to .COM;.EXE;.BAT;.CMD when PATHEXT is unset on Windows', () => {
  assert.deepEqual(buildPathExtCandidates(undefined, true), ['.COM', '.EXE', '.BAT', '.CMD', ''])
})

test('buildPathExtCandidates: respects a custom PATHEXT, still empty-last', () => {
  assert.deepEqual(buildPathExtCandidates('.EXE;.PS1', true), ['.EXE', '.PS1', ''])
})

test('buildPathExtCandidates: non-Windows only tries the bare name', () => {
  assert.deepEqual(buildPathExtCandidates('.COM;.EXE;.BAT;.CMD', false), [''])
  assert.deepEqual(buildPathExtCandidates(undefined, false), [''])
})

test('chooseUpdaterArgs preserves the target and requires a usable runtime, not a marker', () => {
  assert.deepEqual(chooseUpdaterArgs({ runtimeUsable: true }, 'release/1.2'), ['--update', '--branch', 'release/1.2'])
  assert.deepEqual(chooseUpdaterArgs({ runtimeUsable: false }, 'release/1.2'), ['--repair', '--branch', 'release/1.2'])
})

function makeDeps(overrides: Partial<Parameters<typeof resolveVenvNaraCommand>[2]> = {}) {
  return {
    isWindows: true,
    isCommandScript: () => false,
    fileExists: () => true,
    directoryExists: () => false,
    canImportNaraCli: async () => true,
    getVenvPython: (venvRoot: string) => `${venvRoot}/Scripts/python.exe`,
    buildDesktopBackendEnv: () => ({ FAKE_ENV: '1' }),
    resolvePath: (...segments: string[]) => segments.join('/').replace(/\/+/g, '/'),
    dirname: (p: string) => p.slice(0, p.lastIndexOf('/')) || '/',
    basename: (p: string) => p.slice(p.lastIndexOf('/') + 1),
    rememberLog: () => {},
    ...overrides
  }
}

test('resolveVenvNaraCommand: returns null off Windows', async () => {
  const deps = makeDeps({ isWindows: false })

  assert.equal(await resolveVenvNaraCommand('/root/venv/Scripts/nara.exe', [], deps), null)
})

test('resolveVenvNaraCommand: returns null for a .cmd/.bat script command', async () => {
  const deps = makeDeps({ isCommandScript: () => true })

  assert.equal(await resolveVenvNaraCommand('/root/venv/Scripts/nara.cmd', [], deps), null)
})

test('resolveVenvNaraCommand: returns null when the basename is not nara/nara.exe', async () => {
  const deps = makeDeps()

  assert.equal(await resolveVenvNaraCommand('/root/venv/Scripts/python.exe', [], deps), null)
})

test('resolveVenvNaraCommand: returns null when the parent dir is not Scripts', async () => {
  const deps = makeDeps()

  assert.equal(await resolveVenvNaraCommand('/root/venv/bin/nara.exe', [], deps), null)
})

test('resolveVenvNaraCommand: returns null when the venv python does not exist on disk', async () => {
  const deps = makeDeps({ fileExists: () => false })

  assert.equal(await resolveVenvNaraCommand('/root/venv/Scripts/nara.exe', [], deps), null)
})

test('resolveVenvNaraCommand: probes the venv python before trusting it (returns null on failed probe)', async () => {
  let probed = false

  const deps = makeDeps({
    canImportNaraCli: async (python: string) => {
      probed = true
      assert.equal(python, '/root/venv/Scripts/python.exe')

      return false
    }
  })

  const result = await resolveVenvNaraCommand('/root/venv/Scripts/nara.exe', ['serve'], deps)

  assert.equal(probed, true, 'must probe the venv interpreter; a broken venv must not be re-selected forever')
  assert.equal(result, null, 'a failed probe must fall through (return null) so the resolver reaches bootstrap')
})

test('resolveVenvNaraCommand: returns the resolved python backend descriptor when the probe passes', async () => {
  const deps = makeDeps()
  const result = await resolveVenvNaraCommand('/root/venv/Scripts/nara.exe', ['serve', '--port', '0'], deps)

  assert.ok(result, 'a passing probe must return a backend descriptor, not null')
  assert.equal(result.command, '/root/venv/Scripts/python.exe')
  assert.deepEqual(result.args, ['-m', 'nara_cli.main', 'serve', '--port', '0'])
  assert.equal(result.bootstrap, false)
  assert.equal(result.kind, 'python')
  assert.equal(result.shell, false)
  assert.deepEqual(result.env, { FAKE_ENV: '1' })
})

test('resolveVenvNaraCommand: is case-insensitive on nara.exe and the Scripts dir name', async () => {
  const deps = makeDeps()

  assert.ok(await resolveVenvNaraCommand('/root/venv/Scripts/NARA.EXE', [], deps))
  assert.ok(await resolveVenvNaraCommand('/root/venv/SCRIPTS/nara.exe', [], deps))
})
