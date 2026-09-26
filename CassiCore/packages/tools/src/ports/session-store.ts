/**
 * TOOLS PORT — `SessionStore` (injected seam).
 *
 * The session persistence surface consumed by the tools (spawn-subagent-impl's
 * `sessionStore.save(...)`). This is a TYPE-ONLY port: the tools never construct
 * or own a session store — the host injects its real `SessionStore`
 * implementation at boot via `CoreToolDeps.sessionStore` (daemon builds
 * `SessionStore.open(...)` and passes it to `registerCoreTools`).
 *
 * Declared here (self-contained, no `@cassicore/host` import) so the tools
 * package compiles against a stable seam without depending on the host —
 * this is the P1 host↔tools|mcp cycle resolution: the runtime value flows
 * through the existing injection seam, the type lives in the retained port
 * surface.
 */
import type { Session } from '@cassicore/foundation'

/** Identity/indexed session persistence store (injected by the host). */
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
