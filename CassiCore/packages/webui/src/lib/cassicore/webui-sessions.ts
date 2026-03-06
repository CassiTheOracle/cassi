/**
 * webui-sessions.ts
 *
 * In-memory registry of webui sessions created this process lifetime.
 * Bridges the gap: the daemon persists webui turns in sessions.db but
 * GET /sessions only queries the daemon session store.
 *
 * The BFF registers sessions here when created, and the sessions route
 * merges them with daemon sessions for display in the sidebar.
 */

export interface WebuiSession {
  id: string
  firstMessage: string
  createdAt: number  // unix ms
  lastActiveAt: number
  messageCount: number
}

// Module-level registry — survives HMR in dev via the global trick
const SESSION_REGISTRY_KEY = '__cassicore_webui_sessions__'

function getRegistry(): Map<string, WebuiSession> {
  // Survive Next.js hot reloads by attaching to globalThis
  const g = globalThis as Record<string, unknown>
  if (!g[SESSION_REGISTRY_KEY]) {
    g[SESSION_REGISTRY_KEY] = new Map<string, WebuiSession>()
  }
  return g[SESSION_REGISTRY_KEY] as Map<string, WebuiSession>
}

export function registerSession(session: WebuiSession): void {
  getRegistry().set(session.id, session)
}

export function updateSession(id: string, updates: Partial<WebuiSession>): void {
  const reg = getRegistry()
  const existing = reg.get(id)
  if (existing) {
    reg.set(id, { ...existing, ...updates })
  }
}

export function getSession(id: string): WebuiSession | undefined {
  return getRegistry().get(id)
}

export function listSessions(): WebuiSession[] {
  return [...getRegistry().values()].sort((a, b) => b.lastActiveAt - a.lastActiveAt)
}

export function deleteSession(id: string): void {
  getRegistry().delete(id)
}
