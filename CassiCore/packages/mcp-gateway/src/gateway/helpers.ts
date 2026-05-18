#!/usr/bin/env node
/**
 * Shared helpers for CassiCore MCP Gateway
 * Common utilities used across all domain modules
 */

import type { ILogger } from '../../types/interfaces.js';
import { GATEWAY_VERSION } from '../../core/version.js';

// Re-export for consumers that already import from here
export { GATEWAY_VERSION };

// Configuration
export const DEFAULT_FETCH_TIMEOUT_MS = 30_000; // 30s default timeout for all fetch calls

// WHY: Exponential backoff with 5 retries covers ~8s total wait — enough for
// a daemon restart (typically 3-5s) while not blocking tool calls too long.
const TRANSIENT_FETCH_RETRY_DELAYS_MS = [250, 500, 1_000, 2_000, 4_000];

/**
 * Create a logger that writes to stderr (stdout reserved for MCP protocol)
 */
export function createLogger(): ILogger {
  return {
    debug: (msg: string, meta?: Record<string, unknown>) => log('debug', msg, meta),
    info: (msg: string, meta?: Record<string, unknown>) => log('info', msg, meta),
    warn: (msg: string, meta?: Record<string, unknown>) => log('warn', msg, meta),
    error: (msg: string, meta?: Record<string, unknown>) => log('error', msg, meta),
    child: () => createLogger(),
  };
}

function log(level: string, message: string, data?: any) {
  const timestamp = new Date().toISOString();
  const logLine = JSON.stringify({ timestamp, level, message, data });
  console.error(logLine); // contributing:ignore - MCP protocol requires stdout
}

/**
 * Extended Response type where .json() returns `any` instead of `unknown`.
 * All MCP gateway tools use dynamic JSON from the admin API — strict typing
 * at the HTTP boundary adds no safety but costs enormous boilerplate.
 */
export interface JsonResponse extends Response {
  json(): Promise<any>
}

/**
 * Fetch with timeout — wraps global fetch with AbortController to prevent
 * indefinite hangs when the daemon is slow or unresponsive.
 * @dep callers: createServer (mcp/cassicore-gateway.ts), startHttp (mcp/cassicore-gateway.ts), main (mcp/cassicore-gateway.ts), fetchTrainingStats (mcp/gateway/training-tools.ts), fetchTrainingSearch (mcp/gateway/training-tools.ts) [+49]
 * @dep module: Gateway
 * @dep risk: CRITICAL | 54 callers, 0 flows, 1 module
 */
export async function fetchWithTimeout(
  url: string | URL,
  init?: RequestInit & { timeoutMs?: number }
): Promise<JsonResponse> {
  const targetUrl = url.toString();
  const timeoutMs = init?.timeoutMs ?? DEFAULT_FETCH_TIMEOUT_MS;

  for (let attempt = 0; attempt <= TRANSIENT_FETCH_RETRY_DELAYS_MS.length; attempt++) {
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), timeoutMs);
    try {
      return await fetch(targetUrl, {
        ...init,
        signal: controller.signal,
      });
    } catch (err: any) {
      const isTimeout = err?.name === 'AbortError';
      const msg = String(err?.message ?? err ?? '');
      const lowerMsg = msg.toLowerCase();
      const isTransient =
        isTimeout ||
        lowerMsg.includes('fetch failed') ||
        lowerMsg.includes('econnrefused') ||
        lowerMsg.includes('econnreset') ||
        lowerMsg.includes('epipe') ||
        lowerMsg.includes('socket hang up') ||
        lowerMsg.includes('network');

      if (!isTransient || attempt >= TRANSIENT_FETCH_RETRY_DELAYS_MS.length) {
        if (isTimeout) {
          throw new Error(`Request to ${targetUrl} timed out after ${timeoutMs}ms (attempt ${attempt + 1})`);
        }
        throw err;
      }

      const delay = TRANSIENT_FETCH_RETRY_DELAYS_MS[attempt];
      // Log retries to stderr so intermittent failures are visible in MCP logs
      log('warn', `Transient error for ${targetUrl}, retrying in ${delay}ms (attempt ${attempt + 1}/${TRANSIENT_FETCH_RETRY_DELAYS_MS.length + 1})`, {
        error: msg.slice(0, 200),
        isTimeout,
      });
      await new Promise(resolve => setTimeout(resolve, delay));
    } finally {
      clearTimeout(timer);
    }
  }

  throw new Error(`Request to ${targetUrl} failed after ${TRANSIENT_FETCH_RETRY_DELAYS_MS.length + 1} retries`);
}

/**
 * Helper to fetch JSON from an admin API endpoint.
 * Uses timeout to prevent indefinite hangs and validates Content-Type.
 * @dep callers: formatActivity (mcp/gateway/intelligence-tools.ts), formatThinker (mcp/gateway/intelligence-tools.ts), formatSubconscious (mcp/gateway/intelligence-tools.ts), formatConsciousness (mcp/gateway/intelligence-tools.ts), formatTrace (mcp/gateway/intelligence-tools.ts) [+12]
 * @dep calls: fetchWithTimeout
 * @dep module: Gateway
 * @dep risk: CRITICAL | 17 callers, 0 flows, 1 module
 */
export async function fetchIntelligence(
  baseUrl: string,
  path: string,
  params?: Record<string, string>
): Promise<any> {
  const url = new URL(path, baseUrl);
  if (params) {
    for (const [k, v] of Object.entries(params)) {
      if (v !== undefined && v !== null) url.searchParams.set(k, v);
    }
  }
  const response = await fetchWithTimeout(url.toString());
  if (!response.ok) {
    const text = await response.text().catch(() => '(unreadable body)');
    throw new Error(`Admin API error (${response.status}): ${text}`);
  }
  const contentType = response.headers.get('content-type') || '';
  if (!contentType.includes('json')) {
    const text = await response.text().catch(() => '');
    throw new Error(`Expected JSON from ${path}, got ${contentType}: ${text.slice(0, 200)}`);
  }
  return response.json();
}

/**
 * Resolve the most recent active session ID
 * @dep callers: formatSubconscious (mcp/gateway/intelligence-tools.ts), formatTrace (mcp/gateway/intelligence-tools.ts), formatEffectiveness (mcp/gateway/intelligence-tools.ts), formatDialectic (mcp/gateway/dialectic-tools.ts)
 * @dep calls: fetchIntelligence
 * @dep module: Gateway
 * @dep risk: MEDIUM | 4 callers, 0 flows, 1 module
 */
export async function resolveSessionId(
  baseUrl: string,
  sessionId?: string
): Promise<string | undefined> {
  if (sessionId) return sessionId;
  try {
    const data = await fetchIntelligence(baseUrl, '/sessions');
    const sessions = data?.sessions;
    if (Array.isArray(sessions) && sessions.length > 0) {
      const sorted = sessions.sort((a: any, b: any) => (b.lastActiveAt || 0) - (a.lastActiveAt || 0));
      return sorted[0]?.id;
    }
  } catch {
    // Sessions endpoint may not be available
  }
  return undefined;
}

/**
 * Format error response for MCP
 */
export function formatError(error: any): { content: Array<{ type: 'text'; text: string }>; isError: true } {
  return {
    content: [
      {
        type: 'text',
        text: JSON.stringify({ error: error.message ?? String(error) }, null, 2),
      },
    ],
    isError: true,
  };
}

/**
 * Format success response with JSON
 */
export function formatJsonResponse(data: any): { content: Array<{ type: 'text'; text: string }> } {
  return {
    content: [
      {
        type: 'text',
        text: JSON.stringify(data, null, 2),
      },
    ],
  };
}

/**
 * Format success response with markdown text
 * @dep callers: routeToolCall (mcp/cassicore-gateway.ts)
 * @dep flows: CreateHierarchyBridge → FormatTextResponse (4/4)
 * @dep module: Gateway
 * @dep risk: LOW | 1 caller, 1 flow, 1 module
 */
export function formatTextResponse(text: string): { content: Array<{ type: 'text'; text: string }> } {
  return {
    content: [
      {
        type: 'text',
        text,
      },
    ],
  };
}


/**
 * A normalized event collected by watchViaSSE.
 */
export interface CollectedEvent {
  type: string
  message: string
  timestamp: string
}

/**
 * Options for the shared SSE watch utility used by lumen_watch, dyad_watch, and flux_watch.
 */
export interface WatchViaSSEOptions {
  /** SSE endpoint to stream from */
  sseUrl: string
  /**
   * Fallback poll URL — if SSE unavailable, GET this URL every pollIntervalMs.
   * The response must include an `events` array.
   */
  pollUrl?: string
  /** Polling interval in ms (default: 15000) */
  pollIntervalMs?: number
  /** Max seconds to wait before resolving with reason='timeout' (10–600) */
  timeoutSecs: number
  /** If true, only return on significant events; if false return on any event (default: true) */
  interestingOnly: boolean
  /** MCP heartbeat — called every 15s to keep the MCP client connection alive */
  heartbeat?: () => void
  /** Logger instance */
  logger: ILogger
  /**
   * Predicate — is this event significant enough to trigger an early return?
   * @param eventType  Normalized event type string
   * @param parsed     Parsed JSON payload from the `data:` line (or null)
   */
  isSignificant: (eventType: string, parsed: any) => boolean
  /**
   * Extract a human-readable message from an SSE event for the report.
   */
  getEventMessage: (eventType: string, parsed: any) => string
  /**
   * Build the final MCP response once watching ends.
   * @param reason   Why we stopped: 'timeout', 'stream-ended', 'event:<type>', etc.
   * @param events   All events collected during the watch
   */
  buildSnapshot: (
    reason: string,
    events: CollectedEvent[],
  ) => Promise<{ content: Array<{ type: 'text'; text: string }> }>
}

/**
 * Shared SSE watch utility for lumen_watch, dyad_watch, and flux_watch.
 *
 * Connects to an SSE stream and resolves when:
 *   - A significant event fires (interestingOnly=true, default)
 *   - Any event fires (interestingOnly=false)
 *   - The timeout is reached
 *   - The SSE connection closes unexpectedly
 *
 * Falls back to polling `pollUrl` every 15s (configurable) when SSE is unavailable.
 * Sends heartbeats every 15s to prevent MCP client timeout.
 *
 * Handles both standard SSE format (`event: type\ndata: json\n\n`)
 * and simplified format (`data: json\n\n` where `json.type` is the event type).
 * @dep callers: executeLumenWatch (mcp/gateway/lumen-tools.ts), executeHelixTool (mcp/gateway/helix-tools.ts), executeFluxWatch (mcp/gateway/flux-tools.ts), executeDyadTool (mcp/gateway/dyad-tools.ts)
 * @dep calls: heartbeat, has, readLoop, onEvent, finish [+2]
 * @dep module: Gateway
 * @dep risk: MEDIUM | 4 callers, 0 flows, 1 module
 */
export function watchViaSSE(
  opts: WatchViaSSEOptions,
): Promise<{ content: Array<{ type: 'text'; text: string }> }> {
  const {
    sseUrl,
    pollUrl,
    pollIntervalMs = 15_000,
    timeoutSecs,
    interestingOnly,
    heartbeat,
    logger,
    isSignificant,
    getEventMessage,
    buildSnapshot,
  } = opts

  const collectedEvents: CollectedEvent[] = []
  let resolved = false
  const controller = new AbortController()

  return new Promise(async (resolve) => {
    let heartbeatTimer: ReturnType<typeof setInterval> | null = null
    let timeoutTimer: ReturnType<typeof setTimeout> | null = null
    let pollTimer: ReturnType<typeof setInterval> | null = null

    function cleanup() {
      if (heartbeatTimer) { clearInterval(heartbeatTimer); heartbeatTimer = null }
      if (timeoutTimer) { clearTimeout(timeoutTimer); timeoutTimer = null }
      if (pollTimer) { clearInterval(pollTimer); pollTimer = null }
      controller.abort()
    }

    async function finish(reason: string) {
      cleanup()
      try {
        resolve(await buildSnapshot(reason, collectedEvents))
      } catch (err) {
        resolve({ content: [{ type: 'text', text: `Watch ended (${reason}). Snapshot failed: ${err}` }] })
      }
    }

    // Heartbeat — prevents MCP client from declaring a timeout during long waits
    if (heartbeat) {
      heartbeatTimer = setInterval(() => { if (!resolved) heartbeat() }, 15_000)
    }

    // Hard timeout — resolves the watch if nothing significant happens in time
    timeoutTimer = setTimeout(() => {
      if (resolved) return
      resolved = true
      finish('timeout')
    }, timeoutSecs * 1000)

    // Process one complete SSE event (called once per blank-line separator in the stream)
    function onEvent(eventType: string, dataStr: string) {
      if (!eventType || eventType === 'ping' || eventType === 'heartbeat') return
      let parsed: any = null
      try { parsed = JSON.parse(dataStr) } catch { return }

      const message = getEventMessage(eventType, parsed)
      const timestamp = String(parsed?.timestamp ?? new Date().toISOString())
      collectedEvents.push({ type: eventType, message, timestamp })

      if (!resolved) {
        if (isSignificant(eventType, parsed) || !interestingOnly) {
          resolved = true
          finish(`event:${eventType}`)
        }
      }
    }

    let res: Response | null = null
    try {
      res = await fetch(sseUrl, {
        signal: controller.signal,
        headers: { Accept: 'text/event-stream' },
      })
    } catch (err: any) {
      if (err?.name !== 'AbortError') {
        logger.warn('watchViaSSE: SSE connect failed', { sseUrl, error: String(err) })
      }
    }

    if (!res || !res.ok || !res.body) {
      if (res && !res.ok) {
        logger.warn('watchViaSSE: SSE unavailable, falling back to poll', { sseUrl, status: res.status })
      }
      if (!pollUrl) return   // No fallback configured; wait for timeout
      const seen = new Set<string>()
      pollTimer = setInterval(async () => {
        if (resolved) { clearInterval(pollTimer!); pollTimer = null; return }
        try {
          const resp = await fetchWithTimeout(pollUrl, { timeoutMs: 10_000 })
          if (!resp.ok) return
          const data = await resp.json()
          const events = (data as any)?.events ?? []
          for (const evt of events) {
            if (!evt.type) continue
            const key = `${evt.type}|${evt.message ?? ''}|${evt.timestamp ?? ''}`
            if (seen.has(key)) continue
            seen.add(key)
            onEvent(evt.type, JSON.stringify(evt))
            if (resolved) return
          }
        } catch { /* ignore transient poll errors */ }
      }, pollIntervalMs)
      return
    }

    const reader = res.body.getReader()
    const decoder = new TextDecoder()
    let buffer = ''

    const readLoop = async () => {
      try {
        let curEventType = ''
        let curData = ''
        while (!resolved) {
          const { done, value } = await reader.read()
          if (done) break
          buffer += decoder.decode(value, { stream: true })
          const lines = buffer.split('\n')
          buffer = lines.pop() ?? ''
          for (const line of lines) {
            if (line.startsWith('event: ')) {
              curEventType = line.slice(7).trim()
            } else if (line.startsWith('data: ')) {
              curData = line.slice(6)
            } else if (line === '') {
              // Blank line = end of SSE event block
              if (curData) {
                let eventType = curEventType
                // If no explicit 'event:' header, fall back to json.type
                if (!eventType) {
                  try { eventType = JSON.parse(curData)?.type ?? '' } catch {}
                }
                if (eventType) onEvent(eventType, curData)
              }
              curEventType = ''
              curData = ''
            }
          }
        }
      } catch (err: any) {
        if (err?.name !== 'AbortError') {
          logger.warn('watchViaSSE: SSE read error', { error: String(err) })
        }
      }
      if (!resolved) {
        resolved = true
        finish('stream-ended')
      }
    }

    readLoop()
  })
}

/** Safe config keys that can be modified via cassi_config_set */
export const SAFE_CONFIG_KEYS = [
  'intelligence.',
  'providers.*.model',
  'providers.*.enabled',
  'channels.*.enabled',
  'logging.level',
];

export function isConfigKeySafe(key: string): boolean {
  return SAFE_CONFIG_KEYS.some(pattern => {
    if (pattern.endsWith('.')) return key.startsWith(pattern);
    // Convert wildcard pattern to regex
    const regex = new RegExp('^' + pattern.replace(/\./g, '\\.').replace(/\*/g, '[^.]+') + '$');
    return regex.test(key);
  });
}
