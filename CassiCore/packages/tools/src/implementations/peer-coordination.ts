/**
 * Peer Coordination Tools — conscious inter-session communication.
 *
 * These tools give the LLM the ability to ACT on sibling session awareness
 * (which the injection aggregator already provides passively). They complement
 * the CognitiveBridge's automatic/subconscious signal routing with intentional,
 * addressed coordination.
 *
 * All tools execute locally (instant) within the free tool loop — zero
 * additional LLM requests on request-based billing providers.
 *
 * CONSOLIDATED DESIGN (Phase 1 of tool consolidation):
 * - `_coordinate`: Unified tool for all peer coordination actions (signal, broadcast, shared_note, link_brain)
 * - `_check_peers`: Kept separate (discovery is fundamentally different from actions)
 *
 * Tools:
 *   _coordinate   — Unified coordination tool with action parameter
 *   _check_peers  — Discover active peers, read unread messages, see bridge links
 */

import type { ToolDefinition, ToolHandler } from '../types.js'
import type { CognitiveBridge } from '../../intelligence/cognitive-bridge.js'
import type { ILogger } from '../../../types/interfaces.js'


export const coordinateDefinition: ToolDefinition = {
  name: '_coordinate',
  description:
    'Unified peer coordination tool. Use this to communicate with peer sessions through various actions:\n' +
    '- signal: Send a message to a specific peer session\n' +
    '- broadcast: Send a message to ALL active peers at once\n' +
    '- shared_note: Write/read/clear persistent shared scratchpad notes\n' +
    '- link_brain: Establish a cognitive bridge for subconscious signal sharing\n\n' +
    'Lightweight, instant execution. Use _check_peers to discover available peers.',
  parameters: {
    type: 'object',
    properties: {
      action: {
        type: 'string',
        description: 'Coordination action to perform',
        enum: ['signal', 'broadcast', 'shared_note', 'link_brain'],
      },
      // For 'signal' action
      to_session_id: {
        type: 'string',
        description: 'Target session ID (from _check_peers results) - required for "signal" action',
      },
      // For all actions
      message: {
        type: 'string',
        description: 'Message content (for "signal" and "broadcast" actions, max 500 chars)',
      },
      note: {
        type: 'string',
        description: 'Note content (for "shared_note" action with "write", max 300 chars)',
      },
      tag: {
        type: 'string',
        description: 'Message/note category',
        enum: ['discovery', 'request', 'status', 'blocker', 'complete', 'decision'],
      },
      // For 'link_brain' action
      peer_session_id: {
        type: 'string',
        description: 'Session ID of the peer to link with (for "link_brain" action)',
      },
    },
    required: ['action'],
  },
  timeoutMs: 5_000,
  requiredPermission: 'workspace-write',
}

export const checkPeersDefinition: ToolDefinition = {
  name: '_check_peers',
  description:
    'Discover active peer sessions and read unread messages. Returns session IDs, topics, ' +
    'recent activity, brain-link status, unread messages, and shared scratchpad notes. ' +
    'Call this when starting complex work or when you want to coordinate with parallel sessions.',
  parameters: {
    type: 'object',
    properties: {
      include_inactive: {
        type: 'string',
        description: 'Include recently-inactive sessions (default: false)',
        enum: ['true', 'false'],
      },
    },
    required: [],
  },
  timeoutMs: 5_000,
  requiredPermission: 'workspace-write',
}


interface ScratchpadNote {
  sessionId: string
  topic: string
  tag: string
  text: string
  timestamp: number
}

const SCRATCHPAD_KV_KEY = 'peer:scratchpad'
const MAX_SCRATCHPAD_NOTES = 30
const MAX_MESSAGE_LENGTH = 500
const MAX_NOTE_LENGTH = 300


export interface PeerToolDeps {
  /** SessionDigestStore — for mailbox messaging and sibling discovery */
  digestStore?: {
    getSiblings(sessionId: string, includeInactive?: boolean): Array<{
      sessionId: string
      topic?: string
      currentTask?: string
      filesActive?: string[]
      recentActions?: string[]
      lastActiveAt?: number
      isActive?: boolean
      mailbox?: Array<{ from: string; text: string; ts: number }>
    }>
    sendMessage(toSessionId: string, fromSessionId: string, message: string): void
    readMailbox(sessionId: string): Array<{ from: string; text: string; ts: number }>
    peekMailbox(sessionId: string): Array<{ from: string; text: string; ts: number }>
    get(sessionId: string): any | undefined
  }
  /** Memory KV store for shared scratchpad */
  memory?: {
    kv_get(key: string): Promise<unknown>
    kv_set(key: string, value: unknown): Promise<void>
  }
  /** CognitiveBridge for brain linking and status */
  cognitiveBridge?: CognitiveBridge
  logger: ILogger
}


/**
 * @dep callers: handleSharedNote (core/tools/implementations/peer-coordination.ts), makeCheckPeersHandler (core/tools/implementations/peer-coordination.ts)
 * @dep calls: now
 * @dep module: Implementations
 * @dep risk: LOW | 2 callers, 0 flows, 1 module
 */

function timeAgo(ms: number): string {
  const seconds = Math.floor((Date.now() - ms) / 1000)
  if (seconds < 5) return 'just now'
  if (seconds < 60) return `${seconds}s ago`
  if (seconds < 3600) return `${Math.floor(seconds / 60)}m ago`
  return `${Math.floor(seconds / 3600)}h ago`
}


/**
 * @dep callers: registerPeerCoordinationTools (core/tools/implementations/peer-coordination.ts), registerCoreTools (core/tools/implementations/index.ts)
 * @dep calls: child, handleLinkBrain, handleSharedNote, handleBroadcast, handleSignal
 * @dep module: Implementations
 * @dep risk: LOW | 2 callers, 0 flows, 1 module
 */

export function makeCoordinateHandler(deps: PeerToolDeps): ToolHandler {
  const log = deps.logger.child?.('_coordinate') ?? deps.logger

  return async (input, context) => {
    const action = String(input['action'] ?? '').trim().toLowerCase()

    // Route to appropriate handler based on action
    switch (action) {
      case 'signal':
        return handleSignal(input, context, deps, log)
      case 'broadcast':
        return handleBroadcast(input, context, deps, log)
      case 'shared_note':
        return handleSharedNote(input, context, deps, log)
      case 'link_brain':
        return handleLinkBrain(input, context, deps, log)
      default:
        return `Error: Unknown action "${action}". Valid actions: signal, broadcast, shared_note, link_brain`
    }
  }
}


async function handleSignal(
  input: any,
  context: any,
  deps: PeerToolDeps,
  log: ILogger
): Promise<string> {
  const toId = String(input['to_session_id'] ?? '').trim()
  const message = String(input['message'] ?? '').trim().slice(0, MAX_MESSAGE_LENGTH)
  const tag = String(input['tag'] ?? 'status')

  if (!toId) return 'Error: to_session_id is required for "signal" action.'
  if (!message) return 'Error: message is required for "signal" action.'
  if (!deps.digestStore) return 'Error: Peer messaging not available (digest store not wired).'

  try {
    const formatted = `[${tag}] ${message}`
    deps.digestStore.sendMessage(toId, context.sessionId, formatted)

    // Try to get the peer's topic for confirmation
    const peer = deps.digestStore.get(toId)
    const topic = peer?.topic ?? 'unknown'

    log.info('[_coordinate.signal] Delivered', {
      from: context.sessionId.slice(-8),
      to: toId.slice(-8),
      tag,
    })

    return `Message delivered to ${toId} (topic: "${topic}").`
  } catch (err) {
    return `Failed to send message: ${String(err)}`
  }
}

async function handleBroadcast(
  input: any,
  context: any,
  deps: PeerToolDeps,
  log: ILogger
): Promise<string> {
  const message = String(input['message'] ?? '').trim().slice(0, MAX_MESSAGE_LENGTH)
  const tag = String(input['tag'] ?? 'status')

  if (!message) return 'Error: message is required for "broadcast" action.'
  if (!deps.digestStore) return 'Error: Peer messaging not available.'

  const siblings = deps.digestStore.getSiblings(context.sessionId)
  if (siblings.length === 0) return 'No active peer sessions to broadcast to.'

  const formatted = `[${tag}] [broadcast] ${message}`
  let sent = 0
  for (const s of siblings) {
    try {
      deps.digestStore.sendMessage(s.sessionId, context.sessionId, formatted)
      sent++
    } catch { /* best-effort */ }
  }

  log.info('[_coordinate.broadcast] Sent', {
    from: context.sessionId.slice(-8),
    peerCount: sent,
    tag,
  })

  return `Broadcast sent to ${sent} peer session(s).`
}

async function handleSharedNote(
  input: any,
  context: any,
  deps: PeerToolDeps,
  log: ILogger
): Promise<string> {
  // Extract nested action for shared_note
  const noteAction = String(input['message'] ?? 'read').trim().toLowerCase()
  const noteText = String(input['note'] ?? '').trim().slice(0, MAX_NOTE_LENGTH)
  const tag = String(input['tag'] ?? 'status')

  if (!deps.memory) return 'Error: Shared scratchpad not available (memory not wired).'

  if (noteAction === 'read') {
    try {
      const data = await deps.memory.kv_get(SCRATCHPAD_KV_KEY)
      if (!data || typeof data !== 'object' || !Array.isArray((data as any).notes)) {
        return 'SHARED SCRATCHPAD: empty'
      }
      const notes = (data as any).notes as ScratchpadNote[]
      if (notes.length === 0) return 'SHARED SCRATCHPAD: empty'

      const lines = notes.map(n =>
        `  [${n.tag}] ${n.sessionId.slice(-8)} (${n.topic}): ${n.text} (${timeAgo(n.timestamp)})`
      )
      return `SHARED SCRATCHPAD (${notes.length} note(s)):\n${lines.join('\n')}`
    } catch {
      return 'SHARED SCRATCHPAD: empty'
    }
  }

  if (noteAction === 'write') {
    if (!noteText) return 'Error: note text is required for "shared_note" action with "write".'

    // Get topic for this session
    let topic = 'unknown'
    if (deps.digestStore) {
      const digest = deps.digestStore.get(context.sessionId)
      if (digest?.topic) topic = digest.topic
    }

    const newNote: ScratchpadNote = {
      sessionId: context.sessionId,
      topic,
      tag,
      text: noteText,
      timestamp: Date.now(),
    }

    try {
      const existing = await deps.memory.kv_get(SCRATCHPAD_KV_KEY)
      let notes: ScratchpadNote[] = []
      if (existing && typeof existing === 'object' && Array.isArray((existing as any).notes)) {
        notes = (existing as any).notes
      }

      notes.push(newNote)

      // FIFO eviction
      if (notes.length > MAX_SCRATCHPAD_NOTES) {
        notes = notes.slice(-MAX_SCRATCHPAD_NOTES)
      }

      await deps.memory.kv_set(SCRATCHPAD_KV_KEY, { notes, updatedAt: Date.now() })

      log.info('[_coordinate.shared_note] Written', {
        sessionId: context.sessionId.slice(-8),
        tag,
      })

      return `Note posted to shared scratchpad. (${notes.length} total notes)`
    } catch (err) {
      return `Failed to write note: ${String(err)}`
    }
  }

  if (noteAction === 'clear_mine') {
    try {
      const existing = await deps.memory.kv_get(SCRATCHPAD_KV_KEY)
      let notes: ScratchpadNote[] = []
      if (existing && typeof existing === 'object' && Array.isArray((existing as any).notes)) {
        notes = (existing as any).notes
      }

      const before = notes.length
      notes = notes.filter(n => n.sessionId !== context.sessionId)
      const removed = before - notes.length

      await deps.memory.kv_set(SCRATCHPAD_KV_KEY, { notes, updatedAt: Date.now() })

      return `Cleared ${removed} of your notes from the shared scratchpad. (${notes.length} notes remaining)`
    } catch (err) {
      return `Failed to clear notes: ${String(err)}`
    }
  }

  return 'Error: For "shared_note" action, use message parameter with values: "read", "write", or "clear_mine". For "write", also provide "note" parameter.'
}

async function handleLinkBrain(
  input: any,
  context: any,
  deps: PeerToolDeps,
  log: ILogger
): Promise<string> {
  const peerId = String(input['peer_session_id'] ?? '').trim()

  if (!peerId) return 'Error: peer_session_id is required for "link_brain" action.'
  if (!deps.cognitiveBridge) return 'Error: Cognitive bridge not available.'

  if (peerId === context.sessionId) return 'Error: Cannot link a session to itself.'

  // Check peer exists
  if (deps.digestStore) {
    const peer = deps.digestStore.get(peerId)
    if (!peer) {
      return `Error: No active session found with ID "${peerId}". Use _check_peers to discover available sessions.`
    }
  }

  const already = deps.cognitiveBridge.isLinked(context.sessionId, peerId)
  if (already) {
    return `Already brain-linked with ${peerId}. Cognitive signals are flowing bidirectionally.`
  }

  const success = deps.cognitiveBridge.linkSessions(context.sessionId, peerId, 'tool-initiated')
  if (!success) {
    return `Failed to establish brain link. Maximum links may have been reached.`
  }

  // Notify the peer via mailbox
  if (deps.digestStore) {
    let topic = 'unknown'
    const digest = deps.digestStore.get(context.sessionId)
    if (digest?.topic) topic = digest.topic

    deps.digestStore.sendMessage(
      peerId,
      context.sessionId,
      `[brain-link] Session "${topic}" has established a cognitive bridge with you. ` +
      `Your thinking signals will now flow bidirectionally — edge cases, assumptions, ` +
      `tensions, and insights are shared automatically.`
    )
  }

  log.info('[_coordinate.link_brain] Linked', {
    from: context.sessionId.slice(-8),
    to: peerId.slice(-8),
  })

  return (
    `Brain link established with ${peerId}. ` +
    `Cognitive signals will now flow bidirectionally between your sessions. ` +
    `Edge cases, assumptions, tensions, and insights you discover will automatically ` +
    `appear in the peer's context, and theirs in yours. ` +
    `The bridge also detects resonance (independent convergence) and tension (disagreement).`
  )
}

/**
 * @dep callers: registerPeerCoordinationTools (core/tools/implementations/peer-coordination.ts), registerCoreTools (core/tools/implementations/index.ts), peer-coordination-tools.test.ts (tests/peer-coordination-tools.test.ts)
 * @dep calls: kv_get, child, readMailbox, getSiblings, timeAgo [+2]
 * @dep module: Implementations
 * @dep risk: LOW | 3 callers, 0 flows, 1 module
 */

export function makeCheckPeersHandler(deps: PeerToolDeps): ToolHandler {
  const log = deps.logger.child?.('_check_peers') ?? deps.logger

  return async (input, context) => {
    const includeInactive = input['include_inactive'] === 'true'
    const parts: string[] = []

    // 1. Discover peers
    if (deps.digestStore) {
      const siblings = deps.digestStore.getSiblings(context.sessionId, includeInactive)

      if (siblings.length > 0) {
        const lines: string[] = []
        for (const s of siblings) {
          const linked = deps.cognitiveBridge?.isLinked(context.sessionId, s.sessionId) ? ' [BRAIN-LINKED]' : ''
          const activity = s.lastActiveAt ? timeAgo(s.lastActiveAt) : 'unknown'
          const files = s.filesActive?.slice(0, 3).join(', ') ?? 'none'
          const task = s.currentTask ?? s.topic ?? 'unknown'
          lines.push(`  [${s.sessionId}] "${task}" | files: ${files} | ${activity}${linked}`)
        }
        parts.push(`ACTIVE PEERS (${siblings.length}):\n${lines.join('\n')}`)
      } else {
        parts.push('ACTIVE PEERS: none')
      }

      // 2. Read unread messages
      const messages = deps.digestStore.readMailbox(context.sessionId)
      if (messages.length > 0) {
        const lines = messages.map(m => {
          const fromDigest = deps.digestStore!.get(m.from)
          const fromTopic = fromDigest?.topic ?? 'unknown'
          return `  From "${fromTopic}" [${m.from}]: ${m.text}`
        })
        parts.push(`UNREAD MESSAGES (${messages.length}):\n${lines.join('\n')}`)
      }
    } else {
      parts.push('Peer discovery not available (digest store not wired).')
    }

    // 3. Brain link info
    if (deps.cognitiveBridge) {
      const peers = deps.cognitiveBridge.getLinkedPeers(context.sessionId)
      if (peers.length > 0) {
        const lines = peers.map(p => `  ${p.peerId} (${p.mode}, linked ${timeAgo(p.linkedAt)})`)
        parts.push(`BRAIN-LINKED PEERS (${peers.length}):\n${lines.join('\n')}`)
      }
    }

    // 4. Shared scratchpad (quick peek)
    if (deps.memory) {
      try {
        const data = await deps.memory.kv_get(SCRATCHPAD_KV_KEY)
        if (data && typeof data === 'object' && Array.isArray((data as any).notes)) {
          const notes = (data as any).notes as ScratchpadNote[]
          if (notes.length > 0) {
            const lines = notes.slice(-5).map(n =>
              `  [${n.tag}] ${n.sessionId.slice(-8)} (${n.topic}): ${n.text} (${timeAgo(n.timestamp)})`
            )
            parts.push(`SHARED SCRATCHPAD (latest ${Math.min(5, notes.length)} of ${notes.length}):\n${lines.join('\n')}`)
          }
        }
      } catch { /* scratchpad not yet created */ }
    }

    if (parts.length === 0) {
      return 'No peer information available.'
    }

    log.info('[_check_peers] Checked', { sessionId: context.sessionId.slice(-8) })
    return parts.join('\n\n')
  }
}


export function registerPeerCoordinationTools(
  registry: any,
  deps: PeerToolDeps
): void {
  registry.register(coordinateDefinition, makeCoordinateHandler(deps))
  registry.register(checkPeersDefinition, makeCheckPeersHandler(deps))
}
