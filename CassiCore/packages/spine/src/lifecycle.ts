/**
 * @cassicore/spine — session lifecycle → runtime mirror + appendEntry snapshots (plan §4.2).
 *
 * Hooks the session lifecycle post-events (`session_start`, `session_switch`,
 * `session_branch`, `session_compact`, `session_shutdown`) and mirrors a mind-session
 * id into the runtime (via `/v1/session/mirror`), using the opaque sessionId from
 * `ctx.sessionManager.getSessionId()`. On each lifecycle event it also writes an opaque
 * state snapshot into the session log via `pi.appendEntry('mind.runtime.state', …)` so
 * the mind's episodic state is reconstructable from the session tree. `mcp_notification`
 * is bridged into the runtime as a field/state event.
 */

import type {
  SessionBranchEvent,
  SessionCompactEvent,
  SessionShutdownEvent,
  SessionStartEvent,
  SessionSwitchEvent,
  ExtensionAPI,
  ExtensionContext,
  McpNotificationEvent,
} from './oh-my-pi-types.js'
import type { MindSnapshot, SessionMirrorEvent } from '@cassicore/mind-runtime'

import type { ChannelClient } from './channel/client.js'

/** Snapshot a mind-state into the session tree after a lifecycle event (plan §2.5). */
export async function snapshotMindState(pi: ExtensionAPI, client: ChannelClient, ctx: ExtensionContext): Promise<void> {
  try {
    const sn = await client.getSnapshot()
    pi.appendEntry('mind.runtime.state', {
      sessionId: ctx.sessionManager.getSessionId(),
      ts: Date.now(),
      state: sn.state satisfies MindSnapshot,
    })
  } catch {
    // Episodic snapshot is best-effort — a runtime hiccup must not break the session.
  }
}

function mirror(
  client: ChannelClient,
  ctx: ExtensionContext,
  event: SessionMirrorEvent,
  extra?: { branchFrom?: string; summary?: string },
): void {
  void client.mirrorSession({
    event,
    sessionId: ctx.sessionManager.getSessionId(),
    cwd: ctx.cwd,
    branchFrom: extra?.branchFrom,
    summary: extra?.summary,
  }).catch(() => {
    // Non-blocking mirror — runtime liveness is the supervisor's concern, not the spine's.
  })
}

/** Register all session lifecycle + mcp_notification handlers on the extension API. */
export function registerLifecycleHandlers(pi: ExtensionAPI, client: ChannelClient): void {
  pi.on('session_start', (e: SessionStartEvent, ctx: ExtensionContext) => {
    mirror(client, ctx, 'start')
    void snapshotMindState(pi, client, ctx)
  })

  pi.on('session_switch', (e: SessionSwitchEvent, ctx: ExtensionContext) => {
    mirror(client, ctx, 'switch')
    void snapshotMindState(pi, client, ctx)
  })

  // Plan §4.2: session_branch carries the branch point entryId. The retained runtime
  // mirrors it as `branchFrom` so it can attach branch context.
  pi.on('session_branch', (e: SessionBranchEvent, ctx: ExtensionContext) => {
    const branchFrom = (e as SessionBranchEvent & { entryId?: string }).entryId
    mirror(client, ctx, 'branch', { branchFrom })
    void snapshotMindState(pi, client, ctx)
  })

  pi.on('session_compact', (e: SessionCompactEvent, ctx: ExtensionContext) => {
    const summary = typeof (e as SessionCompactEvent & { summary?: string }).summary === 'string'
      ? (e as SessionCompactEvent & { summary?: string }).summary
      : undefined
    mirror(client, ctx, 'compact', { summary })
    void snapshotMindState(pi, client, ctx)
  })

  pi.on('session_shutdown', (e: SessionShutdownEvent, ctx: ExtensionContext) => {
    mirror(client, ctx, 'shutdown')
    void snapshotMindState(pi, client, ctx)
  })

  // Bridge every MCP JSON-RPC notification into the mind as a field/state event
  // (plan §4.2 / verdict 29: ohmypi owns the MCP client; the mind receives it via push).
  pi.on('mcp_notification', (e: McpNotificationEvent, ctx: ExtensionContext) => {
    const payload = e as McpNotificationEvent & { payload?: unknown }
    void client.postEvent({
      type: 'mcp_notification',
      payload: payload.payload ?? payload,
      sessionId: ctx.sessionManager.getSessionId(),
    }).catch(() => {
      // best-effort push
    })
  })
}
