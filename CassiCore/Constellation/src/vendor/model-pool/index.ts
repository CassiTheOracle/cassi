/** VENDORED TYPE STUB — mirrors `model-pool/index.js`. Surface: ModelPool. */
import type { ModelHandle } from './types.js'

export interface ModelPool {
  getHandles?(): unknown[]
  acquire(purpose: string, tier: string, sessionId?: string, override?: unknown): Promise<ModelHandle>
  [key: string]: unknown
}
