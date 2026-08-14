/**
 * CassiCore Admin API client for Next.js BFF routes.
 *
 * Communicates with the CassiCore daemon over HTTP (port 7433 by default).
 * The CASSICORE_API_URL env var overrides the base URL.
 */

export const CASSICORE_URL = process.env.CASSICORE_API_URL ?? 'http://localhost:7433'

/** Fetch wrapper that throws on non-OK responses. */
/**
 * @dep callers: POST (webui/src/app/api/cassicore/sessions/[sessionId]/command/route.ts), POST (webui/src/app/api/cassicore/system-prompt/sections/[label]/route.ts), POST (webui/src/app/api/agents/[agentId]/runs/route.ts), GET (webui/src/app/api/cassicore/context/injections/route.ts), GET (webui/src/app/api/cassicore/dialectic/[sessionId]/route.ts) [+14]
 * @dep module: Cassicore
 * @dep risk: CRITICAL | 19 callers, 0 flows, 1 module
 */

export async function cassiFetch(
  path: string,
  init?: RequestInit
): Promise<Response> {
  const url = `${CASSICORE_URL}${path}`
  const res = await fetch(url, {
    ...init,
    headers: {
      'Content-Type': 'application/json',
      ...(init?.headers ?? {}),
    },
  })
  return res
}

/** Fetch and parse JSON from the daemon. */
export async function cassiJSON<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await cassiFetch(path, init)
  if (!res.ok) {
    const text = await res.text().catch(() => res.statusText)
    throw new Error(`CassiCore ${res.status}: ${text}`)
  }
  return res.json() as Promise<T>
}
