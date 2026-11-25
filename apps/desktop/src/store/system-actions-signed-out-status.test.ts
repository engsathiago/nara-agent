import { afterEach, describe, expect, it, vi } from 'vitest'

import type * as NaraApi from '@/nara'

const getStatus = vi.fn()
const naraApi = vi.fn()
const confirm = vi.fn()

vi.mock('@/nara', async importOriginal => ({
  ...(await importOriginal<typeof NaraApi>()),
  getStatus: () => getStatus(),
  naraApi: (request: unknown) => naraApi(request)
}))

vi.mock('@/store/confirm', () => ({ confirm: (request: unknown) => confirm(request) }))

import { confirmSharedGatewayRestart } from './system-actions'

// The Webapp's body for a caller it does not count as signed in: a tab whose access token expired
// since its last gated request reads this until a gated request rotates its cookies.
const SIGNED_OUT_STATUS = { auth_required: true, gateway_running: true, overall: 'ok', version: '0.0.0' }

afterEach(() => {
  vi.resetAllMocks()
})

describe('confirmSharedGatewayRestart on a signed-out status read', () => {
  it('re-reads after a gated request and still asks before restarting the shared multiplexer', async () => {
    getStatus
      .mockResolvedValueOnce(SIGNED_OUT_STATUS)
      .mockResolvedValueOnce({ active_sessions: 0, gateway_shared_with: ['default', 'alpha'], install_id: 'i' })
    naraApi.mockResolvedValue({})
    confirm.mockResolvedValue(true)

    await expect(confirmSharedGatewayRestart()).resolves.toEqual(['default', 'alpha'])
    expect(naraApi).toHaveBeenCalledWith({ path: '/api/auth/me' })
    expect(confirm).toHaveBeenCalledTimes(1)
  })

  it('reads a full status once', async () => {
    getStatus.mockResolvedValueOnce({ active_sessions: 0, gateway_shared_with: null, install_id: 'i' })

    await expect(confirmSharedGatewayRestart()).resolves.toBeNull()
    expect(getStatus).toHaveBeenCalledTimes(1)
    expect(naraApi).not.toHaveBeenCalled()
  })
})
