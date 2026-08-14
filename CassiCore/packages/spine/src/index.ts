/**
 * @cassicore/spine — the ohmypi extension ('cassisspine').
 *
 * Default factory: `export default function cassiSpine(pi: ExtensionAPI)`. It is the
 * mouth and ears of the focused CassiCore mind inside ohmypi — it never hosts fragile
 * background loops (recon §5.6). It:
 *   1. Connects to the mind runtime over the localhost channel (`CASSI_MIND_URL` wins;
 *      else auto-spawns `cassi-mind` detached and health-probes — Open Item 1).
 *   2. Registers the retained mind tools as thin delegates (plan §4.2).
 *   3. Registers `mind_complete`, the model-access bridge (plan §2.3).
 *   4. Mirrors session lifecycle → runtime + writes appendEntry episodic snapshots.
 *   5. Bridges `mcp_notification` into the mind.
 *   6. Exports the MnemicField memory-backend adapter (`MnemicMemoryBackend`).
 */

import { spawn, type ChildProcess } from 'node:child_process'

import type { ExtensionAPI } from './oh-my-pi-types.js'

import { ChannelClient, resolveChannelUrl } from './channel/client.js'
import { registerMindToolDelegates } from './tools/register.js'
import { registerMindCompleteTool, type MindCompleteTransport } from './tools/mind-complete.js'
import { registerLifecycleHandlers } from './lifecycle.js'
import { MnemicMemoryBackend } from './memory-backend.js'

/** Options for the spine factory (used by tests + embedding hosts). */
export interface SpineOptions {
  /** Base URL override (default: `CASSI_MIND_URL` → 127.0.0.1:7273). */
  baseUrl?: string
  /** Bearer token override (default: `CASSI_MIND_TOKEN`). */
  token?: string
  /** Disable auto-spawning `cassi-mind` when the runtime is unreachable (tests use this). */
  noAutoSpawn?: boolean
  /** Override the mind_complete transport (tests). */
  mindCompleteTransport?: MindCompleteTransport
  /** Provide an injected client (tests). */
  client?: ChannelClient
}

let spawnedRuntime: ChildProcess | undefined

/**
 * Locate the runtime: use `CASSI_MIND_URL` if set; else spawn `cassi-mind` (detached,
 * stdio ignored) and wait on `GET /v1/health` with a short timeout. Supervisor hosts
 * (hub `start`) own restart; this spawn fallback re-spawns only if the health probe
 * fails at factory time (Open Item 1/4).
 */
export function connectToRuntime(opts: SpineOptions = {}): ChannelClient {
  const client = opts.client ?? new ChannelClient({ baseUrl: opts.baseUrl, token: opts.token })
  const explicitUrl = opts.baseUrl ?? (process.env.CASSI_MIND_URL && resolveChannelUrl())
  if (explicitUrl) {
    // Explicit URL — do NOT auto-spawn (the host owns the process).
    return client
  }
  if (opts.noAutoSpawn) return client
  // Auto-spawn fallback (Open Item 1): spawn cassi-mind detached, wait for health.
  try {
    spawnedRuntime = spawnMindRuntime()
    const deadline = Date.now() + 15_000
    const poll = (): Promise<void> => client.ping().then(ok => {
      if (ok) return
      if (Date.now() >= deadline) throw new Error('cassi-mind did not become healthy in time')
      return new Promise(res => setTimeout(res, 250)).then(poll)
    })
    // Kick off a best-effort health wait; not blocking factory return.
    poll().catch(() => { /* runtime liveness is the supervisor's concern */ })
  } catch {
    // fall through — the client will fail individual calls if the runtime is down
  }
  return client
}

function spawnMindRuntime(): ChildProcess {
  const bin = process.env.CASSI_MIND_BIN ?? 'cassi-mind'
  return spawn(bin, [], {
    detached: true,
    stdio: 'ignore',
    env: { ...process.env },
  })
}

// ── The default factory (ohmypi extension entry) ─────────────────────────────
export default function cassiSpine(pi: ExtensionAPI, options: SpineOptions = {}): void {
  const client = connectToRuntime(options)

  // ── 2.4 Retained mind tools (execute delegates to runtime channel) ──
  registerMindToolDelegates(pi, client)

  // ── 2.5 Model-access bridge (mind_complete) ──
  registerMindCompleteTool(pi, options.mindCompleteTransport)

  // ── 2.6 Session lifecycle → runtime mirror + appendEntry snapshots ──
  registerLifecycleHandlers(pi, client)

  // (Memory-backend adapter: exported as MnemicMemoryBackend for ohmypi backend
  //  resolution; `ctx.memory` is read-only on ExtensionContext so the adapter is not
  //  substituted in-process — see memory-backend.ts [VERIFY].)
}

export { ChannelClient } from './channel/client.js'
export { MnemicMemoryBackend } from './memory-backend.js'
export type { MindCompleteSpec, MindCompleteTransport } from './tools/mind-complete.js'
