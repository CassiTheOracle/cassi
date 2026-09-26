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
 *   7. Runs the attention context controller (`ThalamusAttentionSession` per OMP session,
 *      `/cassi-context` command; observe by default, inject on explicit `attentionMode`).
 */

import { randomBytes } from 'node:crypto'
import { setTimeout as delay } from 'node:timers/promises'

import { spawn, type ChildProcess } from 'node:child_process'

import type { ExtensionAPI } from './oh-my-pi-types.js'

import { ChannelClient, resolveChannelUrl } from './channel/client.js'
import { registerMindToolDelegates } from './tools/register.js'
import { registerMindCompleteTool, type MindCompleteTransport } from './tools/mind-complete.js'
import { registerLifecycleHandlers } from './lifecycle.js'
import { registerContextController, type ContextControllerOptions } from './context-controller.js'
import { MnemicMemoryBackend } from './memory-backend.js'
import type { ThalamusMode } from '@cassicore/thalamus/attention'

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
  /**
   * `observe` (default) builds attention without touching provider context, `inject`
   * inserts one opaque synthetic agent packet before the latest direct-user message.
   * Mode + the candidate wait deadline live in SpineOptions, not the kernel config.
   */
  attentionMode?: ThalamusMode
  /** Short deadline (ms) waited on the first context event for prefetched candidates. Default 75. */
  attentionCandidateWaitMs?: number
  /** Further context-controller options (bounds, kernel config, …). */
  context?: ContextControllerOptions
}

let spawnedRuntime: ChildProcess | undefined
let spawnedRuntimeToken: string | undefined

function nonEmptyRuntimeToken(value: string | undefined): string | undefined {
  const token = value?.trim()
  return token || undefined
}

/**
 * Locate the runtime: use `CASSI_MIND_URL` if set; else spawn `cassi-mind` (detached,
 * stdio ignored) and wait on `GET /v1/health` with a short timeout. Supervisor hosts
 * (hub `start`) own restart; this spawn fallback re-spawns only if the health probe
 * fails at factory time (Open Item 1/4).
 */
export function connectToRuntime(opts: SpineOptions = {}): ChannelClient {
  const explicitUrl = opts.baseUrl ?? (process.env.CASSI_MIND_URL && resolveChannelUrl())
  if (explicitUrl || opts.noAutoSpawn || opts.client) {
    // Explicit/supervised runtimes own their authentication policy. Injected
    // clients are already fully configured by their host/test.
    return opts.client ?? new ChannelClient({ baseUrl: opts.baseUrl, token: opts.token })
  }

  const token = spawnedRuntimeToken
    ?? nonEmptyRuntimeToken(opts.token)
    ?? nonEmptyRuntimeToken(process.env.CASSI_MIND_TOKEN)
    ?? randomBytes(32).toString('hex')
  const client = new ChannelClient({ baseUrl: opts.baseUrl, token })
  try {
    if (!spawnedRuntime || spawnedRuntime.exitCode !== null) {
      spawnedRuntimeToken = token
      spawnedRuntime = spawnMindRuntime(token)
    }
    const deadline = Date.now() + 15_000
    const poll = (): Promise<void> => client.ping().then(ok => {
      if (ok) return
      if (Date.now() >= deadline) throw new Error('cassi-mind did not become healthy in time')
      return delay(250).then(poll)
    })
    // Kick off a best-effort identity-checked health wait; individual requests
    // also prove the server before transmitting any context.
    poll().catch(() => { /* runtime liveness is the supervisor's concern */ })
  } catch {
    // fall through — the client will fail individual calls if the runtime is down
  }
  return client
}

function spawnMindRuntime(token: string): ChildProcess {
  const bin = process.env.CASSI_MIND_BIN ?? 'cassi-mind'
  return spawn(bin, [], {
    detached: true,
    stdio: 'ignore',
    env: { ...process.env, CASSI_MIND_TOKEN: token },
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

  // Off/observe leave provider context untouched; inject adds one opaque synthetic packet.
  const envAttentionMode = process.env.CASSI_THALAMUS_MODE
  const attentionMode = options.attentionMode
    ?? (envAttentionMode === 'off' || envAttentionMode === 'observe' || envAttentionMode === 'inject'
      ? envAttentionMode
      : undefined)
    ?? 'observe'
  registerContextController(pi, client, {
    mode: attentionMode,
    candidateWaitMs: options.attentionCandidateWaitMs
      ?? (process.env.CASSI_FI_PROVIDER_URL ? 2_500 : undefined),
    includeFieldShadow: process.env.CASSI_THALAMUS_FIELD_SHADOW === '1',
    ...(options.context ?? {}),
  })

  // (Memory-backend adapter: exported as MnemicMemoryBackend for ohmypi backend
  //  resolution; `ctx.memory` is read-only on ExtensionContext so the adapter is not
  //  substituted in-process — see memory-backend.ts [VERIFY].)
}

export { ChannelClient } from './channel/client.js'
export { MnemicMemoryBackend } from './memory-backend.js'
export { registerContextController, ContextController } from './context-controller.js'
export type { ContextControllerOptions } from './context-controller.js'
export type { MindCompleteSpec, MindCompleteTransport } from './tools/mind-complete.js'
export { createLlamaServerTransport } from './tools/llama-server-transport.js'
export type { LlamaServerTransportConfig } from './tools/llama-server-transport.js'
