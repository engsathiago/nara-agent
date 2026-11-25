import { describe, expect, it } from 'vitest'

import { isNaraCloudUrl } from './nara-cloud'

describe('isNaraCloudUrl', () => {
  it('recognises production and staging agent hosts, nothing else', () => {
    expect(isNaraCloudUrl('https://ares-3009.agents.nousresearch.com')).toBe(true)
    expect(isNaraCloudUrl('https://ares--app.agents.staging-nousresearch.com/')).toBe(true)
    expect(isNaraCloudUrl('https://agents.nousresearch.com.evil.example')).toBe(false)
    expect(isNaraCloudUrl('https://my-box.tailnet.ts.net')).toBe(false)
    expect(isNaraCloudUrl('not a url')).toBe(false)
    expect(isNaraCloudUrl(undefined)).toBe(false)
  })
})
