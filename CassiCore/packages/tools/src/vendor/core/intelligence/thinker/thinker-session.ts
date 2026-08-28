/**
 * VENDOR TYPE STUB — `core/intelligence/thinker/thinker-session.ts` (`ThinkerSession`).
 *
 * Type-placeholder for the thinker session surface consumed by collect-thoughts.ts
 * (tools). Tools hold it via `deps.getThinkerSession?.(sessionId)` and call
 * `enqueueThought`/`waitForResponse`/`drainBuffer`. Not constructed by the tools
 * or their tests. Owned by the P5 brain package; re-pointed when it lands (Open-6).
 */

/** A queued reasoning thought heading into the Thinker processor. */
export interface ThinkerQueueItem {
  thought: string
  step: number
  estimatedSteps: number
  isRevision: boolean
  branchId: string
}

/** Response/guidance emitted by the Thinker for a step. */
export interface ThinkerResponse {
  content: string
  kind?: string
  step?: number
}

/**
 * Thinker session facade — enqueue thoughts, wait for + drain guidance
 * responses.
 */
export interface ThinkerSession {
  enqueueThought(thought: string, opts: {
    step: number
    estimatedSteps: number
    isRevision: boolean
    branchId: string
  }): void
  waitForResponse(timeoutMs?: number): Promise<boolean>
  drainBuffer(): ThinkerResponse[]
}
