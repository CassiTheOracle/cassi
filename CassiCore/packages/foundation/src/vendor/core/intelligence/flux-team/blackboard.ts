/**
 * VENDOR TYPE STUB — `core/intelligence/flux-team/blackboard.ts`
 *
 * Type-only placeholder for the `Blackboard` surface consumed by the P1 live-set
 * (`types/cassi-agent.ts`, via `global-blackboard-registry`). Self-contained; builtin types
 * only; no runtime. Re-pointed to `@cassicore/flux-team` at P3.
 */

/** Channels a blackboard can post to. */
export type BlackboardChannel =
  | 'findings'
  | 'concerns'
  | 'decisions'
  | 'artifacts'
  | 'requests'
  | 'bugs'

/** An entry posted to a blackboard channel. */
export interface BlackboardEntry {
  id: string
  channel: BlackboardChannel
  author?: string
  content: string
  structured?: unknown
  priority: number
  tags: string[]
  timestamp: number
}

/** A named blackboard holding per-channel entries. */
export class Blackboard {
  /** Post an entry to a channel. */
  post(
    channel: BlackboardChannel,
    entry: Omit<BlackboardEntry, 'id' | 'timestamp' | 'channel'>,
  ): BlackboardEntry {
    throw new Error('vendor stub: no runtime implementation')
  }
}
