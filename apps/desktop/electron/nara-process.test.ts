import { describe, expect, it } from 'vitest'

import { commandLineIsNaraRuntime } from './nara-process'

// HX003: process identity comes from a whole argv TOKEN, never an argv substring.
describe('commandLineIsNaraRuntime (HX003 token matching)', () => {
  it('matches a real Nara gateway command line', () => {
    expect(commandLineIsNaraRuntime('nara\0gateway\0run')).toBe(true)
    expect(commandLineIsNaraRuntime('nara gateway run')).toBe(true)
    expect(commandLineIsNaraRuntime('nara --profile work gateway run')).toBe(true)
  })

  it('matches a Nara launched by an interpreter (basename of a path token)', () => {
    expect(commandLineIsNaraRuntime('/venv/bin/python\0/venv/bin/nara\0gateway\0run')).toBe(true)
    expect(commandLineIsNaraRuntime('C:\\Nara\\nara.exe gateway run')).toBe(true)
  })

  // The bug this replaces: a bare `.includes('nara')` matched any of these.
  it('does NOT match an unrelated process whose path merely contains "nara"', () => {
    expect(commandLineIsNaraRuntime('vim /home/user/nara-notes.txt')).toBe(false)
    expect(commandLineIsNaraRuntime('/opt/narabrew/bin/tool --run')).toBe(false)
    expect(commandLineIsNaraRuntime('node /srv/nara-dashboard/server.js')).toBe(false)
    expect(commandLineIsNaraRuntime('cat ~/.nara/config.yaml')).toBe(false)
  })

  // G2 (#150283): the real unmanaged-gateway launch is `python -m nara_cli.main … gateway
  // run`, which the executable-basename-only matcher REJECTED — so findRunningGatewayProfiles
  // missed a live gateway at first launch / profile repair. Mirror the canonical Python matcher
  // (gateway.status.looks_like_gateway_command_line): recognize the module entry point, by argv
  // TOKENS not a substring, carrying the gateway subcommand.
  it('matches a module-launched gateway (python -m nara_cli.main … gateway run)', () => {
    expect(commandLineIsNaraRuntime('python\0-m\0nara_cli.main\0-p\0x\0gateway\0run')).toBe(true)
    expect(commandLineIsNaraRuntime('python -m nara_cli.main -p x gateway run')).toBe(true)
    expect(commandLineIsNaraRuntime('/venv/bin/python /venv/lib/nara_cli/main.py gateway run')).toBe(true)
    expect(commandLineIsNaraRuntime('python -m nara_cli.main --profile work gateway run')).toBe(true)
  })

  it('does NOT match a module entry without the gateway subcommand, nor an unrelated nara-tool path', () => {
    // A nara_cli.main invocation that is not a gateway (e.g. `chat`) is not a running gateway.
    expect(commandLineIsNaraRuntime('python -m nara_cli.main chat')).toBe(false)
    // HX003: no substring; an unrelated tool whose path contains "nara" is never a runtime.
    expect(commandLineIsNaraRuntime('/opt/nara-tool/foo gateway run')).toBe(false)
    // `-p gateway` is a profile value, not a subcommand.
    expect(commandLineIsNaraRuntime('python -m nara_cli.main -p gateway chat')).toBe(false)
  })
})
