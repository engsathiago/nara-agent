import { vi } from 'vitest'

import type { NaraApiRequest } from '@/global'

/** Install a fake `window.naraDesktop.api`, the preload bridge every REST helper sends through. */
export function installRestBridge(answer: (request: NaraApiRequest) => object) {
  const api = vi.fn(async (request: NaraApiRequest) => answer(request))

  Object.defineProperty(window, 'naraDesktop', { configurable: true, value: { api } })

  return api
}
