/**
 * @nara belongs to the default bot only while its source has no real
 * (pre-reservation) `nara` profile. With one, the roster shows exactly one
 * @nara — the real profile — and the default answers to @default, so a
 * typed @nara reaches the same profile the backend's message_agent does.
 */

import { describe, expect, it, vi } from 'vitest'

import { botHandle, botMentionTag, claimDefaultHandles, mergeMultiSourceRoster, resolveRosterMentions } from './data'
import { previewKind } from './row-helpers'
import type { RosterRow } from './types'

vi.mock('@nara/plugin-sdk', async () => {
  const { atom } = await import('nanostores')

  return { atom, host: {}, queryClient: undefined, useQuery: vi.fn(), useValue: vi.fn() }
})

vi.mock('./shared', () => ({ getPluginCtx: () => null, ID: 'nara-bots' }))

function roster(names: string[]): RosterRow[] {
  const local = { profiles: names.map(name => ({ name })) }

  // What Electron's buildAgentRoster reports for a single local source: bare-name handles.
  const union = {
    agents: names.map(profile => ({
      connectionId: 'local',
      connectionKind: 'local' as const,
      connectionLabel: 'This device',
      handle: profile,
      profile,
      targetProfile: profile
    })),
    primaryConnectionId: 'local'
  }

  return mergeMultiSourceRoster(local, union, 'local').profiles as RosterRow[]
}

describe('the @nara handle', () => {
  it.each([
    [['default', 'researcher'], 'default'],
    [['default', 'nara', 'researcher'], 'nara']
  ])('roster %j shows one @nara and a typed @nara reaches %s', (names, owner) => {
    const rows = roster(names)
    const handles = rows.map(row => botHandle(row.name, row))

    expect(handles.filter(handle => handle === 'nara')).toHaveLength(1)
    expect(rows.map(row => botMentionTag(row)).filter(tag => tag === 'nara')).toHaveLength(1)
    expect(resolveRosterMentions('@nara ping', rows, { name: 'researcher' }).map(row => row.name)).toEqual([owner])
  })

  it('names the default @default once a real nara profile holds the handle', () => {
    const rows = roster(['default', 'nara', 'researcher'])
    const byName = Object.fromEntries(rows.map(row => [row.name, botHandle(row.name, row)]))

    expect(byName).toEqual({ default: 'default', nara: 'nara', researcher: 'researcher' })
    expect(resolveRosterMentions('@default ping', rows, { name: 'researcher' }).map(row => row.name)).toEqual(['default'])
  })

  it('keeps each source separate: a remote nara profile does not rename the local default', () => {
    const rows = claimDefaultHandles<Partial<RosterRow>>([
      { connectionId: 'local', name: 'default' },
      { connectionId: 'mini', name: 'default' },
      { connectionId: 'mini', name: 'nara' }
    ])

    expect(rows.map(row => botHandle(String(row.name), row))).toEqual(['nara', 'default', 'nara'])
  })

  it("never lets a source's stale 'nara' handle on its default answer @nara", () => {
    // An older backend labels its default @nara even beside a real nara profile.
    const rows = claimDefaultHandles<RosterRow>([
      { connectionId: 'mini', handle: 'nara', name: 'default', remoteSource: true },
      { connectionId: 'mini', handle: 'nara', name: 'nara', remoteSource: true },
      { connectionId: 'local', name: 'researcher' }
    ])

    expect(resolveRosterMentions('@nara ping', rows, { name: 'researcher' }).map(row => row.name)).toEqual(['nara'])
  })

  it('names a DM sender in a row preview by its roster handle', () => {
    const rows = claimDefaultHandles<RosterRow>(
      ['default', 'nara', 'researcher'].map(name => ({ connectionId: 'local', name }))
    )

    const sender = (name: string, list: RosterRow[]) =>
      previewKind(`Message from 🤖 ${name} (@x): hi`, list, 'local').fromBot

    expect([sender('default', rows), sender('nara', rows)]).toEqual(['default', 'nara'])
    // No real nara profile: the default is still @nara (#89484).
    expect(sender('default', claimDefaultHandles<RosterRow>([{ connectionId: 'local', name: 'default' }]))).toBe(
      'nara'
    )
  })
})
