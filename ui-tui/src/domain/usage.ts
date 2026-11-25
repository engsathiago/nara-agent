import type { Usage } from '@nara/shared/gateway-events'

export { usageFromTick } from '@nara/shared/usage-tick'

export const ZERO: Usage = { calls: 0, input: 0, output: 0, total: 0 }
