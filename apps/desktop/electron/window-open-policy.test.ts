// @vitest-environment node
import { describe, expect, it, vi } from 'vitest'

import {
  isNaraHubClipboardWrite,
  isNaraHubExternalUrl,
  isNaraHubOrigin,
  NARA_HUB_ORIGIN
} from './hub-iframe-policy'
import { createWindowOpenHandler, describeDeniedUrl } from './window-open-policy'

describe('hub-iframe-policy predicates', () => {
  it('admits only the owned hub origin', () => {
    expect(isNaraHubOrigin(NARA_HUB_ORIGIN)).toBe(true)
    expect(isNaraHubOrigin('https://nousresearch.github.io')).toBe(false)

    // Opaque sandboxed frames, data URLs, look-alikes, and absent origins
    // never qualify.
    expect(isNaraHubOrigin('null')).toBe(false)
    expect(isNaraHubOrigin('')).toBe(false)
    expect(isNaraHubOrigin(null)).toBe(false)
    expect(isNaraHubOrigin(undefined)).toBe(false)
    expect(isNaraHubOrigin('https://engsathiago.github.io.evil.example')).toBe(false)
    expect(isNaraHubOrigin('https://evil.example')).toBe(false)
    expect(isNaraHubOrigin('file://')).toBe(false)
  })

  it('delegates only http/https/mailto external URLs', () => {
    expect(isNaraHubExternalUrl('https://github.com/engsathiago/nara-agent')).toBe(true)
    expect(isNaraHubExternalUrl('http://example.com/docs')).toBe(true)
    expect(isNaraHubExternalUrl('mailto:support@example.com')).toBe(true)

    expect(isNaraHubExternalUrl('file:///etc/passwd')).toBe(false)
    expect(isNaraHubExternalUrl('javascript:alert(1)')).toBe(false)
    expect(isNaraHubExternalUrl('nara://internal')).toBe(false)
    expect(isNaraHubExternalUrl('not a url')).toBe(false)
  })

  it('grants clipboard-write to the owned hub origin only', () => {
    expect(isNaraHubClipboardWrite(NARA_HUB_ORIGIN)).toBe(true)
    expect(isNaraHubClipboardWrite('https://nousresearch.github.io')).toBe(false)
    expect(isNaraHubClipboardWrite('null')).toBe(false)
    expect(isNaraHubClipboardWrite('https://artifact-preview.invalid')).toBe(false)
    expect(isNaraHubClipboardWrite(null)).toBe(false)
  })
})

describe('createWindowOpenHandler trusted-hub delegation', () => {
  const baseDetails = { url: 'https://github.com/engsathiago/nara-agent' }

  it('still denies artifact frames (opaque origin) with NO external open', () => {
    const openExternalUrl = vi.fn()

    const handler = createWindowOpenHandler(undefined, {
      getOpenerOrigin: () => 'null',
      openExternalUrl
    })

    expect(handler(baseDetails)).toEqual({ action: 'deny' })
    expect(openExternalUrl).not.toHaveBeenCalled()
  })

  it('delegates a hub-origin http(s) open but still denies the window', () => {
    const openExternalUrl = vi.fn()

    const handler = createWindowOpenHandler(undefined, {
      getOpenerOrigin: () => NARA_HUB_ORIGIN,
      openExternalUrl
    })

    expect(handler(baseDetails)).toEqual({ action: 'deny' })
    expect(openExternalUrl).toHaveBeenCalledExactlyOnceWith('https://github.com/engsathiago/nara-agent')
  })

  it('never delegates from the former upstream hub origin', () => {
    const openExternalUrl = vi.fn()

    const handler = createWindowOpenHandler(undefined, {
      getOpenerOrigin: () => 'https://nousresearch.github.io',
      openExternalUrl
    })

    expect(handler({ url: 'https://docs.example.com/x' })).toEqual({ action: 'deny' })
    expect(openExternalUrl).not.toHaveBeenCalled()
  })

  it('never delegates file:// or unknown schemes from a hub-origin opener', () => {
    const openExternalUrl = vi.fn()

    const handler = createWindowOpenHandler(undefined, {
      getOpenerOrigin: () => NARA_HUB_ORIGIN,
      openExternalUrl
    })

    expect(handler({ url: 'file:///C:/x.html' })).toEqual({ action: 'deny' })
    expect(handler({ url: 'javascript:alert(1)' })).toEqual({ action: 'deny' })
    expect(handler({ url: 'not a url' })).toEqual({ action: 'deny' })
    expect(openExternalUrl).not.toHaveBeenCalled()
  })

  it('never delegates when the opener origin is not exactly the hub', () => {
    const openExternalUrl = vi.fn()

    const handler = createWindowOpenHandler(undefined, {
      getOpenerOrigin: () => 'https://engsathiago.github.io.evil.example',
      openExternalUrl
    })

    expect(handler(baseDetails)).toEqual({ action: 'deny' })
    expect(openExternalUrl).not.toHaveBeenCalled()
  })

  it('a throwing opener probe or external open stays deny-only', () => {
    const openExternalUrl = vi.fn(() => {
      throw new Error('boom')
    })

    const throwingProbe = createWindowOpenHandler(undefined, {
      getOpenerOrigin: () => {
        throw new Error('probe failed')
      },
      openExternalUrl
    })

    expect(throwingProbe(baseDetails)).toEqual({ action: 'deny' })
    expect(openExternalUrl).not.toHaveBeenCalled()

    const throwingOpen = createWindowOpenHandler(undefined, {
      getOpenerOrigin: () => NARA_HUB_ORIGIN,
      openExternalUrl
    })

    expect(throwingOpen(baseDetails)).toEqual({ action: 'deny' })
  })

  it('a throwing logging observer cannot change the decision or the delegation', () => {
    const openExternalUrl = vi.fn()

    const handler = createWindowOpenHandler(
      () => {
        throw new Error('log failed')
      },
      { getOpenerOrigin: () => NARA_HUB_ORIGIN, openExternalUrl }
    )

    expect(handler(baseDetails)).toEqual({ action: 'deny' })
    expect(openExternalUrl).toHaveBeenCalledOnce()
  })

  it('without trusted options the handler is side-effect-free deny (CVE-2026-70608 posture)', () => {
    const handler = createWindowOpenHandler()

    expect(handler({ url: 'https://anything.example' })).toEqual({ action: 'deny' })
  })
})

describe('describeDeniedUrl', () => {
  it('logs origin only, never the full URL', () => {
    expect(describeDeniedUrl('https://example.com/path?token=secret')).toBe('https://example.com')
    expect(describeDeniedUrl('data:text/html,foo')).toBe('data:')
    expect(describeDeniedUrl('not a url')).toBe('<unparseable>')
  })
})
