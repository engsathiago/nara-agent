import { describe, expect, it } from 'vitest'

import {
  normalizeNaraOpenString,
  pathFromNaraDeepLink,
  pathFromOpenDeepLink,
  resolveNaraOpenPath
} from './nara-open-target'

describe('normalizeNaraOpenString', () => {
  it('accepts hash-router paths and strips a leading hash', () => {
    expect(normalizeNaraOpenString('/index-network/intent/1')).toBe('/index-network/intent/1')
    expect(normalizeNaraOpenString('#/index-network/intent/1')).toBe('/index-network/intent/1')
  })

  it('maps plugin-scoped nara:// deep links to the same path', () => {
    expect(normalizeNaraOpenString('nara://index-network/intent/1')).toBe('/index-network/intent/1')
    expect(normalizeNaraOpenString('nara://index-network/intent/1?focus=true')).toBe(
      '/index-network/intent/1?focus=true'
    )
  })

  it('maps nara://open/… deep links by stripping the open host', () => {
    expect(normalizeNaraOpenString('nara://open/index-network/intent/1')).toBe('/index-network/intent/1')
    expect(normalizeNaraOpenString('nara://open/settings/plugins')).toBe('/settings/plugins')
  })

  it('rejects reserved nara kinds and unsafe paths', () => {
    expect(normalizeNaraOpenString('nara://blueprint/morning-brief')).toBeNull()
    expect(normalizeNaraOpenString('nara://plugin/install')).toBeNull()
    expect(normalizeNaraOpenString('https://example.com/x')).toBeNull()
    expect(normalizeNaraOpenString('/../etc/passwd')).toBeNull()
    expect(normalizeNaraOpenString('index-network')).toBeNull()
  })
})

describe('resolveNaraOpenPath', () => {
  it('merges structured path + params', () => {
    expect(resolveNaraOpenPath({ path: '/index-network/intent/1', params: { focus: 'true' } })).toBe(
      '/index-network/intent/1?focus=true'
    )
  })

  it('resolves href the same as a bare string', () => {
    expect(resolveNaraOpenPath({ href: 'nara://index-network/intent/1' })).toBe('/index-network/intent/1')
  })
})

describe('pathFromNaraDeepLink', () => {
  it('builds the navigate path from a plugin-scoped deep-link payload', () => {
    expect(pathFromNaraDeepLink('index-network', 'intent/1')).toBe('/index-network/intent/1')
  })

  it('builds the navigate path from nara://open/… payloads', () => {
    expect(pathFromOpenDeepLink('index-network/intent/1')).toBe('/index-network/intent/1')
    expect(pathFromNaraDeepLink('open', 'agent/42')).toBe('/agent/42')
  })

  it('ignores reserved kinds', () => {
    expect(pathFromNaraDeepLink('blueprint', 'morning-brief')).toBeNull()
    expect(pathFromNaraDeepLink('plugin', 'install')).toBeNull()
  })
})
