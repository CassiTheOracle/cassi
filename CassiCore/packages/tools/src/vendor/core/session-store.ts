/**
 * VENDOR TYPE STUB — `core/session-store.ts` (host, P7).
 *
 * Type placeholder for the host-side session persistence surface consumed by
 * the tools (spawn-subagent-impl's `sessionStore.save(...)`). Owned by the host
 * package (P7). Re-pointed there.
 */
import type { Session } from '@cassicore/foundation'

/** Identity/indexed session persistence store (host-side). */
export interface SessionStore {
  save(session: Session): void
  load(sessionId: string): Session | undefined
  findBySender(channelId: string, senderId: string): Session | undefined
  listAll(): Session[]
  getVersion(sessionId: string): number | undefined
  remove(sessionId: string): void
  prune(maxAgeDays: number): number
  close(): void
}
