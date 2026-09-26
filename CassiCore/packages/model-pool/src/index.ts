/**
 * @cassicore/model-pool — RETAINED acquire-shim factory (CASSICORE-FOCUS §19 / §6 P4)
 *
 * CASSICORE-FOCUS P4 replaced the delegate `ModelPool` class (fallback chains,
 * budget scopes, provider map, capability cache, billing) with a thin
 * ohmypi-backed acquirer that keeps the retained `acquire/release → ModelHandle`
 * contract. ohmypi owns provider routing/quota/fallback; the retained shim is
 * the mind's cast over an ohmypi completion.
 *
 * Retained surface (unchanged shape):
 *   - `ModelHandle`, `ModelCompletionOpts`, `ModelCapabilities` (from ./ports)
 *   - `ModelHandleImpl` (the retained completion runtime, mind_complete-backed)
 *   - `ModelPool` (type) — the acquire-shim contract the mind injects via
 *     `setModelPool` (helix / constellation / mini-helix)
 *   - `createMindCompleteAcquirer(...)` — the P4 host-facing factory that
 *     builds a `ModelPool`-shaped acquirer over an injected `mind_complete`
 *     transport.
 */

// ── Retained port surface (the seam P4 preserves) ─────────────────────────
export type {
  ModelHandle,
  ModelCompletionOpts,
  ModelCapabilities,
} from './ports/index.js'
export { ModelHandleImpl } from './ports/index.js'
export type { ModelHandleImplOpts } from './model-handle.js'
export type {
  MindCompleteTransport,
  ResolvedModel,
} from './mind-complete.js'
export { defaultMindCompleteTransport } from './mind-complete.js'

import type { ILogger } from '@cassicore/foundation'
import type {
  ModelHandle,
  ModelCapabilities,
} from './types.js'
import { ModelHandleImpl } from './model-handle.js'
import type { MindCompleteTransport } from './mind-complete.js'

/** The retained acquire-shim contract — what the mind injects via setModelPool. */
export interface ModelPool {
  /**
   * Acquire a retained `ModelHandle` for a slot. `override` (provider + model)
   * selects the model the completion targets; otherwise a default slot model
   * is used. Returns the retained mind_complete-backed cast.
   */
  acquire(
    slotName: string,
    template?: string,
    sessionId?: string,
    override?: { provider?: string; model?: string },
  ): Promise<ModelHandle>
  /** Release a handle back to the acquirer (no-op bookkeeping; ohmypi owns the pool). */
  release(handle: ModelHandle): void
  /** Dispose the acquirer (releases tracked handles). */
  dispose(): void
}

/** Options for the retained mind_complete-backed acquirer. */
export interface MindCompleteAcquirerConfig {
  /** Logger for handle creation/usage. */
  logger: ILogger
  /** The retained completion transport (mind_complete bridge). */
  transport: MindCompleteTransport
  /** Per-slot default provider/model when no override is supplied. */
  defaultModel?: { provider: string; model: string }
  /** Default capabilities for handles created without an override resolution. */
  defaultCapabilities?: ModelCapabilities
}

function defaultCapabilities(): ModelCapabilities {
  return {
    contextWindow: 128_000,
    maxOutputTokens: 8_192,
    supportsTools: false,
    supportsImages: false,
    source: 'fallback',
    costTier: 'medium',
  }
}

/**
 * Build the retained acquirer — a thin ohmypi-backed `ModelPool` shim.
 * `acquire` returns a `ModelHandleImpl` whose complete()/stream() route through
 * the injected `mind_complete` transport.
 */
export function createMindCompleteAcquirer(config: MindCompleteAcquirerConfig): ModelPool {
  const activeHandles = new Set<ModelHandleImpl>()
  let disposed = false

  const release = (handle: ModelHandle) => {
    if (handle instanceof ModelHandleImpl) {
      activeHandles.delete(handle)
    }
  }

  return {
    async acquire(
      slotName: string,
      _template?: string,
      _sessionId?: string,
      override?: { provider?: string; model?: string },
    ): Promise<ModelHandle> {
      if (disposed) {
        throw new Error('mind_complete acquirer has been disposed')
      }

      const provider = override?.provider ?? config.defaultModel?.provider ?? 'mind_complete'
      const model = override?.model ?? config.defaultModel?.model ?? '@slow'

      const handle = new ModelHandleImpl({
        provider,
        model,
        capabilities: config.defaultCapabilities ?? defaultCapabilities(),
        transport: config.transport,
        logger: config.logger,
        slotName,
        onRelease: release,
      })

      activeHandles.add(handle)
      config.logger.debug('Model acquired via mind_complete acquirer', {
        slotName,
        provider,
        model,
      })

      return handle
    },

    release,

    dispose() {
      disposed = true
      activeHandles.clear()
    },
  }
}
