import fs from 'node:fs'
import http from 'node:http'
import os from 'node:os'
import path from 'node:path'


import { handleChannelsRoutes } from './admin-api/channels.js'
import { handleChatRoutes } from './admin-api/chat.js'
import { handleConfigRoutes } from './admin-api/config.js'
import { handleContextRoutes } from './admin-api/context.js'
import { handleCycleHooksRoutes } from './admin-api/cycle-hooks.js'
import { handleObservabilityRoutes } from './admin-api/observability.js'
import { handleOrchestrationRoutes } from './admin-api/orchestration.js'
import { handlePluginAPIRoutes } from './admin-api/plugin-api.js'
import { handlePluginsRoutes } from './admin-api/plugins.js'
import { handleDebugRoutes } from './admin-api/debug.js'
import { handleDelegationRoutes } from './admin-api/delegation.js'
import { handleDialecticRoutes } from './admin-api/dialectic.js'
import { handleEventsRoutes } from './admin-api/events.js'
import { handleHealthRoutes } from './admin-api/health.js'
import { handleIntelligenceRoutes } from './admin-api/intelligence.js'
import { handleMcpRoutes } from './admin-api/mcp.js'
import { handleMemoryRoutes } from './admin-api/memory.js'
import { handleModulesRoutes } from './admin-api/modules.js'
import { handleModelsRoutes } from './admin-api/models.js'
import { handlePermissionsRoutes } from './admin-api/permissions.js'
import { handleProvidersRoutes } from './admin-api/providers.js'
import { handleSessionsRoutes } from './admin-api/sessions.js'
import { handleSubagentsRoutes } from './admin-api/subagents.js'
import { handleTeamsRoutes } from './admin-api/teams.js'
import { handleToolsRoutes } from './admin-api/tools.js'
import { handleVerificationRoutes } from './admin-api/verification.js'
import { handleImprovementRoutes } from './admin-api/improvement.js'
import { handleHelixRoutes } from './admin-api/helix.js'
import { handleConstellationRoutes } from './admin-api/constellation.js'
import { handleMeditationRoutes } from './admin-api/meditation.js'
import { handleProactiveRoutes } from './admin-api/proactive.js'
import { handleDreamerRoutes } from './admin-api/dreamer.js'
import { handleModelDirectiveRoutes } from './admin-api/model-directive.js'
import { handleBlackboardRoutes } from './admin-api/blackboard.js'
import { handleCortexRoutes } from './admin-api/cortex.js'
import { handlePinealRoutes } from './admin-api/pineal.js'
import { handleFileArtifactRoutes } from './admin-api/file-artifacts.js'
import { handleCodeStoreRoutes } from './admin-api/code-store.js'
import { handleThalamusRoutes } from './admin-api/thalamus.js'
import { handleTrainingRoutes } from './admin-api/training.js'
import { handlePromptLogRoutes } from './admin-api/prompt-log.js'
import { handleTimelineRoutes } from './admin-api/timeline.js'
import { handleWarmProviderRoutes, shutdownWarmProvider } from './admin-api/warm-provider.js'
import { handlePrismRoutes } from './admin-api/prism.js'
import { createAdminRuntimeFacade } from './admin-api/runtime.js'
import { getModelSpec } from './config/system-settings.js'
import { assembleContext } from './intelligence/context-assembler.js'
import { createToolsApi } from './tools-api.js'
import { PluginAPI, PluginRegistry } from './plugins/index.js'

import type { DialecticStreamEvent } from '../types/dialectic.js'
import type { ILogger } from '../types/interfaces.js'
import type { Message } from '../types/runtime.js'

interface WSConnection {
  socket: any
  sessionId: string
  subscribed: boolean
}

interface DelegationRequest {
  id: string
  sessionId: string
  goal: string
  agentType: 'code' | 'explore' | 'general' | 'researcher' | 'search'
  priority: 'low' | 'medium' | 'high' | 'critical'
  reason: string
  estimatedComplexity: 'low' | 'moderate' | 'high' | 'very-high'
  contextPreamble: string
  createdAt: number
  expiresAt: number
}

type DelegationStatus = 'pending' | 'acknowledged' | 'executing' | 'completed' | 'failed' | 'expired'

interface DelegationTracking {
  request: DelegationRequest
  status: DelegationStatus
  spawnedSessionId?: string
  teamId?: string
  acknowledgedAt?: number
  completedAt?: number
  result?: string
}

interface SessionHierarchyEntry {
  parentId: string | null
  childIds: Set<string>
  startedAt?: number
  endedAt?: number
  agentType?: string
  steps?: number
  durationMs?: number
}

/**
 * @dep callers: start (core/daemon.ts), team-sse.test.ts (tests/team-sse.test.ts), admin-observability-boot.test.ts (tests/admin-observability-boot.test.ts), admin-model-api.test.ts (tests/admin-model-api.test.ts)
 * @dep calls: createAdminRuntimeFacade
 * @dep module: Unknown
 * @dep risk: MEDIUM | 4 callers, 0 flows, 1 module
 */

export function createAdminApi(daemon: any, logger: ILogger) {
  const runtime = createAdminRuntimeFacade(daemon)
  const pluginRegistry = new PluginRegistry(logger)
  const unixPath = path.join(os.homedir(), '.cassicore', 'admin.sock')
  const tcpHost = (daemon?.config?.get?.('admin.host', '127.0.0.1')) ?? '127.0.0.1'
  const baseTcpPort = Number(daemon?.config?.get?.('admin.port', 7433)) || 7433
  let currentTcpPort = baseTcpPort
  let unixSocketInode: number | null = null
  const pluginEventStreams = new Map<string, Set<http.ServerResponse>>()

  // WebSocket connections store
  const wsConnections = new Map<string, WSConnection>()
  let wsConnectionId = 0

  // WHY: Tracks ingested user/assistant messages per OpenCode session to assemble a PREVIOUS CONTEXT block without needing the session manager.
  interface OcMessage { role: 'user' | 'assistant'; content: string; timestamp: number; importance: number }
  const ocConversationHistory = new Map<string, OcMessage[]>()

  // HOW: Fast heuristic importance scorer — no LLM call, runs synchronously. Returns 0–1; higher = more important to preserve in context.
  const DECISION_PATTERNS = /\b(decided|decision|let'?s use|we'?ll go with|the fix is|solution is|approach is|plan is|agreed|choosing|switched to|changed to|replaced|we should|must|critical)\b/i
  const ERROR_PATTERNS = /\b(error|failed|failure|bug|crash|broken|exception|stack ?trace|panic|ENOENT|EADDRINUSE|TypeError|SyntaxError|ReferenceError|segfault|SIGKILL|SIGABRT|cannot|couldn'?t)\b/i
  const FILE_CHANGE_PATTERNS = /\b(created|wrote|edited|modified|deleted|renamed|moved|refactored|added file|updated file|new file)\b/i
  const CODE_BLOCK_PATTERN = /```/

  function scoreImportance(msg: OcMessage): number {
    const text = msg.content
    const len = text.length

    // Very short messages are usually acknowledgments → low
    if (len < 20) return 0.1

    let score = 0.3 // baseline

    if (DECISION_PATTERNS.test(text)) score += 0.3
    if (ERROR_PATTERNS.test(text)) score += 0.25
    if (FILE_CHANGE_PATTERNS.test(text)) score += 0.2
    if (CODE_BLOCK_PATTERN.test(text)) score += 0.1

    // Long assistant messages with substantial content are more valuable
    if (msg.role === 'assistant' && len > 500) score += 0.1

    // User messages that are questions or detailed instructions
    if (msg.role === 'user' && len > 100) score += 0.1

    return Math.min(score, 1.0)
  }

  // HOW: Extracts focus topics from recent conversation messages using keyword frequency. No LLM call — fast enough to run on every /context request.
  const STOP_WORDS = new Set([
    'the','a','an','is','are','was','were','be','been','being','have','has','had',
    'do','does','did','will','would','shall','should','may','might','can','could',
    'i','you','we','they','he','she','it','me','my','your','our','their','his','her',
    'this','that','these','those','what','which','who','whom','how','when','where','why',
    'not','no','yes','ok','let','just','also','but','and','or','if','then','so','for',
    'to','of','in','on','at','by','with','from','about','into','through','during',
    'before','after','above','below','between','under','again','further','all','each',
    'any','some','few','more','most','very','too','here','there','now','then','already',
    'still','well','really','actually','basically','literally','probably','maybe',
    'sure','right','think','know','want','need','like','look','make','go','get','see',
    'come','take','use','try','run','set','put','help','keep','start','move','give',
  ])

  function extractTopics(history: OcMessage[], windowSize = 10): string[] {
    // Take the most recent N messages
    const recent = history.slice(-windowSize)
    const freq = new Map<string, number>()

    for (const msg of recent) {
      // Extract meaningful tokens: identifiers, file paths, technical terms
      const tokens = msg.content
        .replace(/```[\s\S]*?```/g, '') // strip code blocks
        .replace(/https?:\/\/\S+/g, '') // strip URLs
        .split(/[\s,.;:!?()[\]{}"'`]+/)
        .filter(t => t.length > 2 && t.length < 60)
        .map(t => t.toLowerCase())

      for (const token of tokens) {
        if (STOP_WORDS.has(token)) continue
        if (/^\d+$/.test(token)) continue // pure numbers
        freq.set(token, (freq.get(token) || 0) + 1)
      }
    }

    // Sort by frequency, take top terms as topics
    return [...freq.entries()]
      .filter(([, count]) => count >= 2) // must appear at least twice
      .sort((a, b) => b[1] - a[1])
      .slice(0, 5)
      .map(([term]) => term)
  }

  // HOW: Extracts file paths mentioned in conversation for activeFiles / semantic weighting.
  const FILE_PATH_PATTERN = /(?:^|\s|['"`(])([a-zA-Z0-9_./-]+\.[a-zA-Z]{1,8})(?:\s|['"`):,]|$)/g
  const BINARY_EXTENSIONS = new Set(['png','jpg','jpeg','gif','svg','ico','woff','woff2','ttf','eot','mp3','mp4','zip','gz','tar','pdf'])

  function extractActiveFiles(history: OcMessage[], windowSize = 8): string[] {
    const recent = history.slice(-windowSize)
    const fileCounts = new Map<string, number>()

    for (const msg of recent) {
      // Reset regex
      FILE_PATH_PATTERN.lastIndex = 0
      let match
      while ((match = FILE_PATH_PATTERN.exec(msg.content)) !== null) {
        const filePath = match[1]
        // Filter out obvious non-files
        const ext = filePath.split('.').pop()?.toLowerCase() || ''
        if (BINARY_EXTENSIONS.has(ext)) continue
        if (filePath.length < 5) continue
        if (/^[0-9.]+$/.test(filePath)) continue // version numbers like "5.3.0"
        fileCounts.set(filePath, (fileCounts.get(filePath) || 0) + 1)
      }
    }

    return [...fileCounts.entries()]
      .sort((a, b) => b[1] - a[1])
      .slice(0, 10)
      .map(([f]) => f)
  }

  // HOW: Detects task boundaries in the conversation for PREVIOUS CONTEXT compression. A boundary is signaled by: explicit transition phrases ("let's move on", "next task", "ok done"), large time gaps (>5 min silence), or file cluster switches (working on entirely different files).
  const TRANSITION_PHRASES = /\b(let'?s move on|next task|moving on|done with|finished|let'?s switch|on to|now let'?s|different topic|new feature|start working on)\b/i

  interface Episode {
    startIdx: number
    endIdx: number
    messages: OcMessage[]
    topic: string // inferred from keywords
    importance: number // avg importance of messages
  }

  function detectEpisodes(history: OcMessage[]): Episode[] {
    if (history.length < 4) return [{ startIdx: 0, endIdx: history.length - 1, messages: history, topic: '', importance: 0.3 }]

    const boundaries: number[] = [0] // first message is always a boundary

    for (let i = 1; i < history.length; i++) {
      const prev = history[i - 1]
      const curr = history[i]

      // Time gap > 5 min
      const gap = curr.timestamp - prev.timestamp
      if (gap > 5 * 60 * 1000) {
        boundaries.push(i)
        continue
      }

      // Explicit transition phrase in user message
      if (curr.role === 'user' && TRANSITION_PHRASES.test(curr.content)) {
        boundaries.push(i)
        continue
      }

      // File cluster switch: extract files from curr and prev windows
      if (i > 3 && curr.role === 'user') {
        const prevFiles = extractActiveFiles(history.slice(Math.max(0, i - 4), i), 4)
        const currFiles = extractActiveFiles([curr], 1)
        if (currFiles.length > 0 && prevFiles.length > 0) {
          const overlap = currFiles.filter(f => prevFiles.some(p => f.includes(p) || p.includes(f)))
          if (overlap.length === 0) {
            boundaries.push(i)
          }
        }
      }
    }

    // Build episodes from boundaries
    const episodes: Episode[] = []
    for (let b = 0; b < boundaries.length; b++) {
      const start = boundaries[b]
      const end = b < boundaries.length - 1 ? boundaries[b + 1] - 1 : history.length - 1
      const msgs = history.slice(start, end + 1)

      const avgImportance = msgs.length > 0
        ? msgs.reduce((sum, m) => sum + m.importance, 0) / msgs.length
        : 0.3

      // Infer topic from most frequent terms in this episode
      const topics = extractTopics(msgs, msgs.length)
      const topic = topics.slice(0, 3).join(', ')

      episodes.push({ startIdx: start, endIdx: end, messages: msgs, topic, importance: avgImportance })
    }

    return episodes
  }

  /** Compress an episode into a dense one-line summary for PREVIOUS CONTEXT. */
  function summarizeEpisode(ep: Episode): string {
    // Find the most important message in the episode as the representative
    let bestMsg = ep.messages[0]
    for (const m of ep.messages) {
      if (m.importance > bestMsg.importance) bestMsg = m
    }
    const representative = bestMsg.content.length > 200
      ? `${bestMsg.content.slice(0, 200)  }...`
      : bestMsg.content
    const topicStr = ep.topic ? ` [${ep.topic}]` : ''
    return `Episode (${ep.messages.length} msgs, importance ${(ep.importance * 100).toFixed(0)}%)${topicStr}: ${representative}`
  }

  /** Max messages to retain per session (older ones are dropped). */
  const OC_MAX_HISTORY = 200
  /** Recent messages passed raw — everything older goes into PREVIOUS CONTEXT. */
  const OC_RAW_WINDOW = 10

  // Subscribe to events/ingest-emitted events so we accumulate conversation turns.
  // We use daemon.bus (the core EventBus) directly instead of the CassiCoreEventBus singleton,
  // because events from admin-api/events.ts may go through a different event bus instance.
  // Additionally, we hook into the admin-api handler() to intercept ingest calls directly.
  const _ocIngestInterceptor = (events: any[], sessionId: string) => {
    for (const event of events) {
      if (event.source !== 'opencode') continue
      if (event.type !== 'user_message' && event.type !== 'assistant_message') continue

      const sid: string = event.sessionId || sessionId
      if (!ocConversationHistory.has(sid)) {
        // Eagerly load from KV on first sight (fire-and-forget, non-blocking for sync path)
        ocConversationHistory.set(sid, [])
        const mem = daemon.intelligence?.memory
        if (mem?.kv_get) {
          mem.kv_get(`oc-conv:${sid}`).then((saved: any) => {
            if (Array.isArray(saved) && saved.length > 0) {
              // Prepend saved history before any events we already captured
              const current = ocConversationHistory.get(sid) || []
              ocConversationHistory.set(sid, [...saved, ...current])
            }
          }).catch(() => {})
        }
      }

      const history = ocConversationHistory.get(sid)!

      const msg: OcMessage = {
        role: event.type === 'user_message' ? 'user' : 'assistant',
        content: typeof event.content === 'string' ? event.content : '',
        timestamp: event.timestamp ?? Date.now(),
        importance: 0,
      }
      msg.importance = scoreImportance(msg)
      history.push(msg)

      // Cap to avoid unbounded growth
      if (history.length > OC_MAX_HISTORY) {
        ocConversationHistory.set(sid, history.slice(-OC_MAX_HISTORY))
      }

      // On each complete exchange: persist to KV and archive for semantic recall
      if (event.type === 'assistant_message') {
        const mem = daemon.intelligence?.memory
        // Persist to KV so history survives daemon restarts
        if (mem?.kv_set) {
          mem.kv_set(`oc-conv:${sid}`, ocConversationHistory.get(sid)!).catch(() => {})
        }
        // Archive for semantic recall (searchArchives)
        if (mem && typeof mem.archiveConversation === 'function') {
          const lastUser = [...history].reverse().find((m) => m.role === 'user')
          if (lastUser) {
            mem.archiveConversation(sid, lastUser.content, event.content ?? '', undefined, {
              source: 'opencode',
            }).catch(() => {})
          }
        }
      }
    }
  }

  const sessionHierarchyMap = new Map<string, SessionHierarchyEntry>()
  const subagentToTeamMap = new Map<string, string>()

  const delegationTracker = new Map<string, DelegationTracking>()
  let lastDelegationComputeTime = 0
  const DELEGATION_COMPUTE_INTERVAL_MS = 5000
  const DELEGATION_EXPIRY_MS = 60_000
  const DELEGATION_MAX_PENDING = 3

  const sseConnections = new Map<string, { res: http.ServerResponse; sessionId: string; connectedAt: number }>()
  const sseConnectionId = { value: 0 }

  /** Ensure a hierarchy entry exists for the given session ID. */
  function ensureHierarchyEntry(sid: string): SessionHierarchyEntry {
    let entry = sessionHierarchyMap.get(sid)
    if (!entry) {
      entry = { parentId: null, childIds: new Set() }
      sessionHierarchyMap.set(sid, entry)
    }
    return entry
  }

  /** Process a subagent lifecycle event to update the hierarchy map. */
  function processHierarchyEvent(event: any): void {
    if (event.type === 'subagent_start') {
      const childId = event.childSessionId || event.sessionId
      const parentId = event.parentSessionId || event.parentId
      if (!childId || !parentId) return

      const childEntry = ensureHierarchyEntry(childId)
      childEntry.parentId = parentId
      childEntry.startedAt = event.timestamp || Date.now()
      if (event.agentType) childEntry.agentType = event.agentType

      const parentEntry = ensureHierarchyEntry(parentId)
      parentEntry.childIds.add(childId)

      logger.debug('Session hierarchy updated', { childId, parentId, agentType: event.agentType })

      const to = daemon.intelligence?.teamOrchestrator as any
      if (to?.createTeam) {
        try {
          const goalText = event.taskPrompt
            || event.taskDescription
            || `OpenCode subagent task (${event.agentType || 'general'})`

          const teamName = event.taskDescription
            ? `Subagent: ${event.taskDescription.slice(0, 60)}`
            : `Subagent: ${event.agentType || 'task'}`

          const team = to.createTeam({
            name: teamName,
            goal: goalText,
            external: true,
            externalSessionId: childId,
            externalParentSessionId: parentId,
            checkpoint: { mode: 'none' },
            budget: {
              maxTokens: 200_000,
              maxAgents: 1,
              maxDepth: 1,
              maxDurationMs: 30 * 60 * 1000,
            },
            metadata: {
              agentType: event.agentType,
              source: 'opencode-subagent',
            },
          })

          subagentToTeamMap.set(childId, team.id)

          for (const tracking of delegationTracker.values()) {
            if (tracking.spawnedSessionId === childId && !tracking.teamId) {
              tracking.teamId = team.id
              logger.debug('T3: Linked delegation to team', {
                delegationId: tracking.request.id,
                teamId: team.id,
              })
            }
          }

          logger.info('External team created for subagent', {
            teamId: team.id,
            childId,
            parentId,
            agentType: event.agentType,
            goalPreview: goalText.slice(0, 100),
          })
        } catch (err) {
          logger.error('Failed to create external team for subagent', {
            childId,
            parentId,
            error: String(err),
          })
        }
      }
    } else if (event.type === 'subagent_end') {
      const childId = event.childSessionId || event.sessionId
      if (!childId) return

      const entry = sessionHierarchyMap.get(childId)
      if (entry) {
        entry.endedAt = event.timestamp || Date.now()
        if (event.steps != null) entry.steps = event.steps
        if (event.durationMs != null) entry.durationMs = event.durationMs
      }

      const teamId = subagentToTeamMap.get(childId)
      if (teamId) {
        const to = daemon.intelligence?.teamOrchestrator as any
        if (to?.completeExternalTeam) {
          try {
            to.completeExternalTeam(teamId, {
              summary: event.resultSummary || event.taskDescription || undefined,
              output: event.resultText || undefined,
              error: event.error || undefined,
              tokensUsed: event.tokensUsed || 0,
              durationMs: event.durationMs || (entry ? (entry.endedAt! - (entry.startedAt || 0)) : undefined),
              success: !event.error,
            })

            logger.info('External team completed for subagent', {
              teamId,
              childId,
              success: !event.error,
              tokensUsed: event.tokensUsed,
            })
          } catch (err) {
            logger.error('Failed to complete external team', {
              teamId,
              childId,
              error: String(err),
            })
          }
        }

        subagentToTeamMap.delete(childId)
      }

      for (const tracking of delegationTracker.values()) {
        if (tracking.spawnedSessionId === childId && tracking.status === 'executing') {
          tracking.status = 'completed'
          tracking.completedAt = Date.now()
          tracking.result = event.resultSummary || event.resultText || 'Subagent completed'
          logger.info('T3: Delegation completed via subagent_end', {
            delegationId: tracking.request.id,
            childId,
          })
          break
        }
      }
    } else if (event.type === 'subagent_prompt_captured') {
      const childId = event.sessionId
      if (!childId) return

      const teamId = subagentToTeamMap.get(childId)
      if (teamId) {
        const to = daemon.intelligence?.teamOrchestrator as any
        const team = to?.teams?.get?.(teamId)
        if (team && event.taskPrompt) {
          team.config.goal = event.taskPrompt
          const goalTree = to.goalTrees?.get?.(teamId)
          const rootGoal = goalTree?.get?.(team.rootGoalId)
          if (rootGoal) {
            rootGoal.description = event.taskPrompt
            if (event.taskDescription) {
              rootGoal.title = event.taskDescription
            }
          }
          if (event.taskDescription) {
            team.config.name = `Subagent: ${event.taskDescription.slice(0, 60)}`
          }

          logger.debug('External team goal enriched with task prompt', {
            teamId,
            childId,
            promptLength: event.taskPrompt.length,
            description: event.taskDescription?.slice(0, 80),
          })
        }
      }
    }
  }

  /** Serialize the hierarchy map for inject.json. */
  function serializeSessionHierarchy(): Record<string, { parentId?: string; childIds: string[] }> {
    const result: Record<string, { parentId?: string; childIds: string[] }> = {}
    for (const [sid, entry] of sessionHierarchyMap) {
      result[sid] = {
        ...(entry.parentId ? { parentId: entry.parentId } : {}),
        childIds: Array.from(entry.childIds),
      }
    }
    return result
  }

  function sendJSON(res: http.ServerResponse, code: number, obj: unknown) {
    const s = JSON.stringify(obj)
    res.writeHead(code, { 'Content-Type': 'application/json' })
    res.end(s)
  }

  function getFirstUserMessage(history: any[]): string {
    for (const msg of history) {
      if (msg.role === 'user') {
        const content = typeof msg.content === 'string' ? msg.content : JSON.stringify(msg.content)
        return content.slice(0, 200) || '(empty message)'
      }
    }
    return '(no messages)'
  }

  function getLastUserMessage(history: any[]): string {
    let lastMessage = '(no messages)'
    for (const msg of history) {
      if (msg.role === 'user') {
        const content = typeof msg.content === 'string' ? msg.content : JSON.stringify(msg.content)
        lastMessage = content.slice(0, 200) || '(empty message)'
      }
    }
    return lastMessage
  }

  /**
   * Build state snapshot from event history
   */
  function buildStateSnapshot(sessionId: string, events: any[]): any {
    const snapshot: any = {
      sessionId,
      connected: true,
      lastEventTimestamp: 0,
      turnIndex: 0,
      isStreaming: false,
      messageCount: 0,
      activeTools: [],
      activeToolCalls: [],
      totalTokensUsed: 0,
    }

    const activeToolCalls = new Map<string, { toolCallId: string; toolName: string; startTime: number }>()

    for (const event of events) {
      snapshot.lastEventTimestamp = Math.max(snapshot.lastEventTimestamp, event.timestamp || 0)

      switch (event.type) {
        case 'session_start':
          snapshot.sessionStartTime = event.timestamp
          break
        case 'agent_start':
          snapshot.turnIndex = event.turnIndex || 0
          snapshot.model = event.model
          break
        case 'streaming_start':
          snapshot.isStreaming = true
          break
        case 'streaming_end':
          snapshot.isStreaming = false
          break
        case 'user_message':
          snapshot.messageCount++
          break
        case 'assistant_message':
          snapshot.messageCount++
          snapshot.totalTokensUsed += (event.inputTokens || 0) + (event.outputTokens || 0)
          break
        case 'tool_execution_start':
          activeToolCalls.set(event.toolCallId, {
            toolCallId: event.toolCallId,
            toolName: event.toolName,
            startTime: event.timestamp,
          })
          break
        case 'tool_execution_end':
          activeToolCalls.delete(event.toolCallId)
          break
        case 'model_select':
          snapshot.model = event.model
          break
        case 'context_usage':
          snapshot.contextUsage = {
            tokens: event.tokens,
            contextWindow: event.contextWindow,
            percent: event.percent,
          }
          break
      }
    }

    snapshot.activeToolCalls = Array.from(activeToolCalls.values())
    return snapshot
  }

  function broadcastSSE(sessionId: string, event: any): void {
    const data = JSON.stringify(event)
    const message = [
      `id: ${event.eventId || `evt_${Date.now()}`}`,
      `event: ${event.type}`,
      `data: ${data}`,
      '',
    ].join('\n')

    for (const [id, conn] of sseConnections) {
      if (conn.sessionId === sessionId) {
        try {
          conn.res.write(`${message  }\n`)
        } catch {
          sseConnections.delete(id)
        }
      }
    }
  }

  function parseBody(req: http.IncomingMessage): Promise<any> {
    const MAX_BODY_SIZE = 10 * 1024 * 1024 // 10 MB limit
    return new Promise((resolve, reject) => {
      const chunks: Buffer[] = []
      let totalSize = 0
      req.on('data', (c) => {
        const buf = Buffer.from(c)
        totalSize += buf.length
        if (totalSize > MAX_BODY_SIZE) {
          req.destroy(new Error('Request body too large'))
          reject(new Error(`Request body exceeds ${MAX_BODY_SIZE} byte limit`))
          return
        }
        chunks.push(buf)
      })
      req.on('end', () => {
        if (chunks.length === 0) return resolve(undefined)
        try {
          const s = Buffer.concat(chunks).toString('utf8')
          resolve(JSON.parse(s))
        } catch (err) {
          reject(err)
        }
      })
      req.on('error', reject)
    })
  }

  function normalizePluginSessionId(sessionId: string): string {
    return sessionId.includes(':') ? sessionId : sessionId
  }

  function extractTextContent(content: string | Array<{ type: string; text?: string }>): string {
    if (typeof content === 'string') return content
    if (!Array.isArray(content)) return ''
    return content
      .filter((part) => part.type === 'text')
      .map((part) => part.text ?? '')
      .join('\n')
  }

  async function memorySearch(query: string, limit?: number): Promise<unknown[]> {
    if (!daemon.intelligence?.memory?.search) return []
    return daemon.intelligence.memory.search(query, { limit: limit ?? 10 })
  }

  async function memoryStore(content: string, tags?: string[]): Promise<string> {
    if (!daemon.intelligence?.memory?.store) return ''
    return daemon.intelligence.memory.store({
      type: 'conversation',
      content,
      metadata: { tags: tags ?? [], source: 'plugin-api' },
    })
  }

  async function contextArchive(sessionId: string, messages: unknown[]): Promise<void> {
    if (!daemon.intelligence?.memory?.indexSession) return
    const normalized = Array.isArray(messages)
      ? messages.map((msg) => {
          const m = msg as { role?: string; content?: string | Array<{ type: string; text?: string }> }
          return {
            role: (m.role ?? 'user') as Message['role'],
            content: extractTextContent(m.content ?? ''),
          }
        })
      : []
    daemon.intelligence.memory.indexSession(sessionId, normalized)
  }

  async function contextCompact(sessionId: string, messages: unknown[]): Promise<unknown> {
    const memory = daemon.intelligence?.memory as any
    const aggregator = daemon.intelligence?.injectionAggregator as any

    const cognitiveParts = aggregator?.aggregateForExternal
      ? await aggregator.aggregateForExternal(sessionId)
      : []
    const cognitiveContext = Array.isArray(cognitiveParts)
      ? cognitiveParts
          .filter((p: any) => p.content && p.charCount > 0)
          .map((p: any) => String(p.content))
          .join('\n\n')
      : ''

    let memoryContext = ''
    let lastUserQuery = ''
    if (memory?.search) {
      const lastUser = [...(messages as Array<{ role?: string; content?: string | Array<{ type: string; text?: string }> }>)]
        .reverse()
        .find((m) => m.role === 'user')
      lastUserQuery = extractTextContent(lastUser?.content ?? '').slice(0, 200)
      if (lastUserQuery) {
        const results = await memory.search(lastUserQuery, { limit: 6, minScore: 0.25 })
        if (Array.isArray(results) && results.length > 0) {
          const items = results.map((r: any) => {
            const score = Math.round((r.score ?? 0) * 100)
            return `- (${score}%) ${String(r.entry?.content ?? r.content ?? '').slice(0, 400)}`
          })
          memoryContext = `### Relevant Memory\n${items.join('\n')}`
        }
      }
    }

    const { SmartCompactionEngine } = await import('./intelligence/smart-compaction.js')
    const COMPACTION_MODEL = 'gpt-5-mini'
    const COMPACTION_PROVIDER = 'github-copilot'
    let summarizer: ((content: string, instruction: string) => Promise<string>) | undefined
    let modelLabel = 'heuristic-only'

    const modelPool = runtime.getLumenModelPool()
    if (modelPool && typeof modelPool.acquire === 'function') {
      summarizer = async (content: string, instruction: string): Promise<string> => {
        let handle: any
        try {
          handle = await modelPool.acquire('compaction', undefined, sessionId, {
            provider: COMPACTION_PROVIDER,
            model: COMPACTION_MODEL,
          })
        } catch {
          return ''
        }
        try {
          const result = await handle.complete(
            [{ role: 'user', content: `${instruction}\n\n---\n\n${content}` }],
            {
              model: COMPACTION_MODEL,
              maxTokens: 2000,
              temperature: 0.2,
              thinking: 'none',
              reasoning: 'none',
              systemPrompt: 'You are a concise summarizer. Follow the instruction exactly. Output only the summary, no preamble or reasoning.',
              source: 'smart-compaction-cluster',
              trigger: 'compact',
              sessionId,
              allowConcurrent: true,
              timeoutMs: 30000,
            },
          )
          return SmartCompactionEngine.stripThinkingArtifacts((result.response ?? '').trim())
        } finally {
          try { handle.release() } catch {}
        }
      }
      modelLabel = `${COMPACTION_PROVIDER}/${COMPACTION_MODEL}`
    }

    const normalized = Array.isArray(messages)
      ? messages.map((msg) => {
          const m = msg as { role?: string; content?: string | Array<{ type: string; text?: string }> }
          return {
            role: (m.role ?? 'user') as Message['role'],
            content: typeof m.content === 'string'
              ? m.content
              : Array.isArray(m.content)
                ? m.content.map((part) => ({ type: part.type, text: part.text }))
                : '',
          }
        })
      : []

    const engine = new SmartCompactionEngine(
      {
        outputCharBudget: 80000,
        preserveRecentCount: 8,
        minMessagesForCompaction: 12,
        summarizer,
      },
      logger,
    )

    const result = await engine.compact(normalized, {
      memoryContext,
      cognitiveContext,
      lastUserQuery,
    })

    if (memory?.store && result.summary) {
      await memory.store({
        content: `[Compaction summary — session ${sessionId}]\n\n${result.summary.slice(0, 8000)}`,
        type: 'conversation',
        tags: ['compaction', 'session', sessionId],
      }).catch(() => {})
    }

    return {
      sessionId,
      summary: result.summary,
      model: modelLabel,
      strategy: result.strategy,
      stats: {
        keptVerbatim: result.keptVerbatim,
        summarized: result.summarized,
        pruned: result.pruned,
        durationMs: result.durationMs,
      },
      hasMemory: !!memoryContext,
      hasCognitive: !!cognitiveContext,
    }
  }

  function contextIndex(sessionId: string, messages: unknown[]): void {
    if (!daemon.intelligence?.memory?.indexSession) return
    const normalized = Array.isArray(messages)
      ? messages.map((msg) => {
          const m = msg as { role?: string; content?: string | Array<{ type: string; text?: string }> }
          return {
            role: (m.role ?? 'user') as Message['role'],
            content: extractTextContent(m.content ?? ''),
          }
        })
      : []
    daemon.intelligence.memory.indexSession(sessionId, normalized)
  }

  async function contextResolveRef(ref: string): Promise<unknown> {
    const memory = daemon.intelligence?.memory
    if (!memory?.resolveRef) return []
    return memory.resolveRef(ref)
  }

  async function contextSearchIndex(query: string, sessionId?: string): Promise<unknown> {
    const memory = daemon.intelligence?.memory
    if (!memory?.searchIndex) return []
    return memory.searchIndex(query, sessionId ? { sessionId, limit: 10 } : { limit: 10 })
  }

  function buildCognitiveStatus(): unknown {
    const activity = daemon.intelligence?.all?.map((mod: any) => ({
      name: mod?.name,
      status: 'active',
    })) ?? []
    return {
      modules: activity,
      thinker: daemon.intelligence?.thinker?.getStats?.() ?? null,
      dialectic: daemon.intelligence?.dialectic?.getStats?.() ?? null,
      memory: daemon.intelligence?.memory?.getStats?.() ?? null,
      teams: daemon.intelligence?.teamOrchestrator?.listAllTeams?.() ?? [],
      lumen: daemon.intelligence?.lumen?.listJobs?.() ?? [],
    }
  }

  const pluginApi = new PluginAPI({
    logger,
    registry: pluginRegistry,
    sessions: {
      create: (stableId: string, opts) => thisSessionsCreate(stableId, opts),
      get: (id: string) => {
        const session = daemon.sessions?.get?.(id)
        return session ? { id: session.id, status: 'active' } : null
      },
      destroy: (id: string) => {
        daemon.sessions?.delete?.(id)
      },
      append: (id: string, message: Message) => {
        daemon.sessions?.addTurn?.(id, message)
      },
    },
    context: {
      fetchContext: buildInjectPayload,
      inject: async (sessionId: string) => {
        const aggregator = daemon.intelligence?.injectionAggregator as any
        if (!aggregator?.aggregateForExternal) return []
        const parts = await aggregator.aggregateForExternal(sessionId)
        return Array.isArray(parts) ? parts.filter((p: any) => p.content && p.charCount > 0).map((p: any) => p.content) : []
      },
      cognitiveStatus: async () => buildCognitiveStatus(),
      storeChunks: async (sessionId: string, chunks: unknown[]) => {
        const memory = daemon.intelligence?.memory as any
        if (!memory?.kv_set) return { stored: 0 }
        let stored = 0
        for (const chunk of chunks as Array<Record<string, unknown>>) {
          if (!chunk.id || !chunk.content) continue
          await memory.kv_set(`chunk:${sessionId}:${chunk.id}`, {
            content: chunk.content,
            role: chunk.role || 'unknown',
            type: chunk.type || 'text',
            toolName: chunk.toolName,
            tokens: chunk.tokens || 0,
            preview: chunk.preview || '',
            storedAt: Date.now(),
          })
          stored++
        }
        const existingIndex = await memory.kv_get(`chunk-index:${sessionId}`) as string[] | undefined
        const index = new Set(existingIndex || [])
        for (const chunk of chunks as Array<Record<string, unknown>>) {
          if (typeof chunk.id === 'string') index.add(chunk.id)
        }
        await memory.kv_set(`chunk-index:${sessionId}`, [...index])
        return { stored }
      },
      expandChunks: async (sessionId: string, ids: string[]) => {
        const memory = daemon.intelligence?.memory as any
        if (!memory?.kv_get) return []
        const results: unknown[] = []
        for (const id of ids) {
          const data = await memory.kv_get(`chunk:${sessionId}:${id}`)
          if (data) results.push({ id, ...(data as Record<string, unknown>) })
        }
        return results
      },
      archive: contextArchive,
      compact: contextCompact,
      index: contextIndex,
      resolveRef: contextResolveRef,
      searchIndex: contextSearchIndex,
      ingestEvents: async (sessionId: string, events: unknown[]) => {
        const bus = daemon.bus
        for (const event of events as Array<Record<string, unknown>>) {
          const normalized = {
            ...event,
            sessionId,
            timestamp: event.timestamp instanceof Date ? event.timestamp : new Date(Number(event.timestamp ?? Date.now())),
          }
          processHierarchyEvent(normalized)
          await bus.emit(normalized)
        }
      },
      forwardTurnStart: (sessionId: string, message: string) => {
        void daemon.bus.emit({
          type: 'turn:start',
          sessionId,
          message,
          timestamp: new Date(),
        } as any)
      },
      forwardTurnEnd: (sessionId: string) => {
        void daemon.bus.emit({
          type: 'worker:message',
          pluginId: `session:${sessionId}`,
          payload: { type: 'turn:done', sessionId },
        } as any)
      },
      forwardToken: (sessionId: string, delta: string, kind: string) => {
        void daemon.bus.emit({
          type: 'worker:message',
          pluginId: `session:${sessionId}`,
          payload: { type: kind === 'thinking' ? 'turn:thinking' : 'turn:token', sessionId, token: delta },
        } as any)
      },
      forwardToolCall: (sessionId: string, toolName: string, meta?: Record<string, unknown>) => {
        void daemon.bus.emit({
          type: 'worker:message',
          pluginId: `session:${sessionId}`,
          payload: { type: 'turn:tool_call', sessionId, tool: toolName, input: meta },
        } as any)
      },
      forwardToolResult: (sessionId: string, callId: string, isError: boolean) => {
        void daemon.bus.emit({
          type: 'worker:message',
          pluginId: `session:${sessionId}`,
          payload: { type: 'turn:tool_result', sessionId, toolCallId: callId, isError, content: '' },
        } as any)
      },
    },
    memory: {
      search: memorySearch,
      store: memoryStore,
      kvGet: async (key: string) => daemon.intelligence?.memory?.kv_get?.(key),
      kvSet: async (key: string, value: unknown) => daemon.intelligence?.memory?.kv_set?.(key, value),
    },
    intelligence: {
      status: async () => buildCognitiveStatus(),
      enrich: async (query: string) => daemon.intelligence?.memory?.universalSearch?.(query, { limit: 10 }) ?? [],
    },
    eventBus: {
      on: (type, handler) => daemon.bus.on(type as any, handler as any),
      emit: (event) => daemon.bus.emit(event as any),
    },
    toolRegistry: {
      register: (tool) => {
        const registry = daemon.toolRegistry ?? daemon.pipeline?.toolRegistry
        registry?.register?.({
          name: tool.name,
          description: tool.description,
          parameters: tool.parameters,
          visibleToAgent: true,
          category: 'extended',
        }, async (input: Record<string, unknown>, context: unknown) => {
          const result = await tool.execute(input, context)
          return typeof result === 'string' ? result : JSON.stringify(result)
        })
      },
    },
  })

  function thisSessionsCreate(stableId: string, opts?: { channelId?: string; meta?: Record<string, unknown> }) {
    const session = daemon.sessions.getOrCreateById(
      normalizePluginSessionId(stableId),
      opts?.channelId ?? 'plugin',
      normalizePluginSessionId(stableId),
      opts?.meta ? { ...(opts.meta as Record<string, unknown>) } : undefined,
    )
    return { id: session.id }
  }

  function attachPluginEventStream(pluginId: string, res: http.ServerResponse, req: http.IncomingMessage): void {
    res.writeHead(200, {
      'Content-Type': 'text/event-stream',
      'Cache-Control': 'no-cache, no-transform',
      'Connection': 'keep-alive',
    })
    res.write(': connected\n\n')

    let streams = pluginEventStreams.get(pluginId)
    if (!streams) {
      streams = new Set()
      pluginEventStreams.set(pluginId, streams)
    }
    streams.add(res)

    const heartbeatTimer = setInterval(() => {
      if (res.destroyed || res.writableEnded) {
        clearInterval(heartbeatTimer)
        return
      }
      try {
        res.write(': heartbeat\n\n')
        pluginRegistry.heartbeat(pluginId)
      } catch {
        clearInterval(heartbeatTimer)
      }
    }, 15_000)

    const cleanup = () => {
      clearInterval(heartbeatTimer)
      streams?.delete(res)
      if (streams && streams.size === 0) {
        pluginEventStreams.delete(pluginId)
      }
      pluginRegistry.setStatus(pluginId, 'disconnected')
    }

    req.on('close', cleanup)
    res.on('close', cleanup)
  }

  daemon.bus.onAll((event: any) => {
    if (pluginEventStreams.size === 0) return
    const payload = `event: ${event.type}\ndata: ${JSON.stringify(event)}\n\n`
    for (const [pluginId, streams] of pluginEventStreams) {
      if (event?.type === 'worker:message' && event?.pluginId && event.pluginId !== pluginId) {
        continue
      }

      const filters = pluginApi.getEventFilters(pluginId)
      const matches = filters.includes('*') || filters.some((filter) => {
        if (filter === event.type) return true
        if (filter.endsWith('*')) return event.type.startsWith(filter.slice(0, -1))
        return false
      })
      if (!matches) continue

      for (const stream of streams) {
        if (stream.destroyed || stream.writableEnded) continue
        try {
          stream.write(payload)
        } catch {
          streams.delete(stream)
        }
      }
      if (streams.size === 0) {
        pluginEventStreams.delete(pluginId)
      }
    }
  })

  function authOk(req: http.IncomingMessage) {
    try {
      const token = daemon.config?.get?.('admin.token', undefined as string | undefined)
      if (!token) return true // No token configured — local-only access
      const h = req.headers['authorization']
      if (!h || Array.isArray(h)) return false
      return h === `Bearer ${token}`
    } catch (err) {
      // Fail closed: if config is broken, reject requests requiring auth
      return false
    }
  }

  /** Resolve latest active team ID when none is specified */
  function resolveLatestTeamId(to: any): string | undefined {
    const all = to.listAllTeams()
    const active = all.find((t: any) => t.status === 'running' || t.status === 'paused')
    return active?.id || all[all.length - 1]?.id
  }

  /**
   * Set up WebSocket connection handling
   */
  async function handleWebSocketUpgrade(req: http.IncomingMessage, socket: any, head: Buffer) {
    const url = new URL(req.url || '', `http://${tcpHost}:${currentTcpPort}`)
    
    // Route /ws paths to the new WebSocket handler
    if (url.pathname.startsWith('/ws')) {
      // The new handler will take over - don't destroy the socket here
      // The createWebSocketHandler already registered its own upgrade listener
      // This should not be reached if the handler is properly set up
      logger.debug('WebSocket upgrade for /ws path - should be handled by createWebSocketHandler', { path: url.pathname })
      return
    }
    
    const parts = url.pathname.split('/').filter(Boolean)

    if (parts[0] !== 'dialectic' || parts.length !== 3 || parts[2] !== 'stream') {
      socket.destroy()
      return
    }

    const sessionId = parts[1]
    if (!sessionId) {
      socket.destroy()
      return
    }

    const key = req.headers['sec-websocket-key']
    if (!key) {
      socket.destroy()
      return
    }

    const crypto = await import('node:crypto')
    const acceptKey = crypto.createHash('sha1')
      .update(`${key  }258EAFA5-E914-47DA-95CA-C5AB0DC85B11`)
      .digest('base64')

    socket.write(
      'HTTP/1.1 101 Switching Protocols\r\n' +
      'Upgrade: websocket\r\n' +
      'Connection: Upgrade\r\n' +
      `Sec-WebSocket-Accept: ${acceptKey}\r\n` +
      '\r\n'
    )

    const connId = `ws-${++wsConnectionId}`
    const conn: WSConnection = { socket, sessionId, subscribed: true }
    wsConnections.set(connId, conn)

    logger.info(`WebSocket connected for dialectic stream: ${sessionId}`)

    const unsubscribe = daemon.intelligence?.dialectic?.subscribeToStream?.(sessionId, (event: DialecticStreamEvent) => {
      if (!conn.subscribed || socket.destroyed) return
      try {
        const message = JSON.stringify(event)
        sendWebSocketMessage(socket, message)
      } catch (err) {
        logger.warn(`WebSocket send error: ${String(err)}`)
      }
    })

    socket.on('close', () => {
      conn.subscribed = false
      wsConnections.delete(connId)
      unsubscribe?.()
      logger.info(`WebSocket disconnected: ${sessionId}`)
    })

    socket.on('error', (err: any) => {
      logger.warn(`WebSocket error: ${String(err)}`)
      socket.destroy()
    })
  }

  /**
   * Send a text message over WebSocket
   */
  function sendWebSocketMessage(socket: any, message: string) {
    const msgBuf = Buffer.from(message, 'utf8')
    const len = msgBuf.length

    let frame: Buffer
    if (len < 126) {
      frame = Buffer.allocUnsafe(2 + len)
      frame[0] = 0x81
      frame[1] = len
      msgBuf.copy(frame, 2)
    } else if (len < 65536) {
      frame = Buffer.allocUnsafe(4 + len)
      frame[0] = 0x81
      frame[1] = 126
      frame.writeUInt16BE(len, 2)
      msgBuf.copy(frame, 4)
    } else {
      frame = Buffer.allocUnsafe(10 + len)
      frame[0] = 0x81
      frame[1] = 127
      frame.writeBigUInt64BE(BigInt(len), 2)
      msgBuf.copy(frame, 10)
    }

    socket.write(frame)
  }

  function isObject(v: unknown): v is Record<string, unknown> {
    return typeof v === 'object' && v !== null && !Array.isArray(v)
  }

  function mergeDeep(target: any, src: any): any {
    if (!isObject(target) || !isObject(src)) return src
    const out: any = { ...target }
    for (const k of Object.keys(src)) {
      if (isObject(src[k])) {
        out[k] = mergeDeep(out[k] ?? {}, src[k])
      } else {
        out[k] = src[k]
      }
    }
    return out
  }

  /**
   * Map MentalModel ConversationPhase → bridge-friendly mode string.
   */
  function phaseToMode(phase: string, intentType?: string, topic?: string): 'exploration' | 'planning' | 'execution' | 'debugging' {
    if (intentType === 'debug' || intentType === 'fix' || intentType === 'troubleshoot') return 'debugging'
    if (topic && /\b(bug|error|fix|debug|crash|fail|broken|issue)\b/i.test(topic)) return 'debugging'

    switch (phase) {
      case 'initial':
      case 'clarifying':
        return 'exploration'
      case 'synthesizing':
        return 'planning'
      case 'executing':
        return 'execution'
      case 'concluding':
        return 'planning'
      default:
        return 'exploration'
    }
  }

  /**
   * Determine pruning aggressiveness based on session characteristics.
   */
  function computePruneAdvice(
    turnCount: number,
    complexity: number,
    mode: string,
    focusTopics: string[],
  ): { aggressiveness: string; staleAfterTurns: number; keepToolOutputs: string[]; focusTopics: string[] } {
    const keepToolOutputs = ['skill', 'activity']

    if (turnCount < 5 || complexity < 0.2) {
      return { aggressiveness: 'none', staleAfterTurns: 50, keepToolOutputs, focusTopics }
    }
    if (turnCount < 15 && complexity < 0.6) {
      return { aggressiveness: 'light', staleAfterTurns: 20, keepToolOutputs, focusTopics }
    }
    if (turnCount < 30) {
      return { aggressiveness: 'moderate', staleAfterTurns: 12, keepToolOutputs, focusTopics }
    }
    return { aggressiveness: 'aggressive', staleAfterTurns: 8, keepToolOutputs, focusTopics }
  }

  /**
   * Build a unified focusState for a single session.
   */
  function buildFocusState(sessionId: string, opts?: { includeParentFocus?: boolean }): Record<string, any> | null {
    const digestStore = daemon.sessionDigestStore

    const digest = digestStore?.get?.(sessionId)

    if (!digest) {
      // Fallback for OpenCode sessions: infer focus state from accumulated conversation history.
      // This enables pruneAdvice to scale with session length even without the subconscious module.
      const ocHistory = ocConversationHistory.get(sessionId)
      if (!ocHistory || ocHistory.length < 2) return null

      const turnCount = Math.floor(ocHistory.length / 2)
      // Complexity grows gently with session length (capped at 0.85)
      const complexity = Math.min(0.3 + turnCount * 0.04, 0.85)

      // Feature 1: Extract focus topics from recent conversation
      const focusTopics = extractTopics(ocHistory)

      // Feature 3: Extract active files for semantic recall weighting
      const activeFiles = extractActiveFiles(ocHistory)

      // Infer mode from recent message patterns
      const recentText = ocHistory.slice(-6).map(m => m.content).join(' ')
      const hasErrors = ERROR_PATTERNS.test(recentText)
      const mode: 'exploration' | 'planning' | 'execution' | 'debugging' =
        hasErrors ? 'debugging' :
        turnCount < 6 ? 'exploration' : 'execution'

      const topicStr = focusTopics.slice(0, 3).join(', ')
      const pruneAdvice = computePruneAdvice(turnCount, complexity, mode, focusTopics)
      return {
        mode,
        topic: topicStr,
        intent: null,
        activeFiles,
        filesActive: activeFiles,
        activeSkills: [],
        recentActions: [],
        turnCount,
        complexity,
        pruneAdvice,
        compactionContext: topicStr ? `Topic: ${topicStr}` : null,
      }
    }

    const topic = digest?.topic || ''
    const phase = digest?.phase || 'initial'

    const mode = phaseToMode(phase, '', topic)

    const activeFilesSet = new Set<string>()
    if (digest?.filesActive) {
      for (const f of digest.filesActive) activeFilesSet.add(f)
    }

    const focusTopics: string[] = []
    if (topic) focusTopics.push(topic)
    if (digest?.currentTask && digest.currentTask !== topic) focusTopics.push(digest.currentTask)

    const turnCount = digest?.turnCount ?? 0
    const complexity = 0.5

    const pruneAdvice = computePruneAdvice(turnCount, complexity, mode, focusTopics)

    const compactionParts: string[] = []
    if (topic) compactionParts.push(`Topic: ${topic}`)
    if (digest?.currentTask) compactionParts.push(`Current task: ${digest.currentTask}`)
    if (mode) compactionParts.push(`Mode: ${mode}`)
    if (digest?.decisions?.length) compactionParts.push(`Key decisions: ${digest.decisions.slice(-3).join('; ')}`)
    if (digest?.learnings?.length) compactionParts.push(`Learnings: ${digest.learnings.slice(-3).join('; ')}`)

    const result: Record<string, any> = {
      mode,
      topic,
      intent: null,
      complexity,
      activeFiles: Array.from(activeFilesSet).slice(0, 20),
      activeSkills: [],
      recentActions: digest?.recentActions ?? [],
      turnCount,
      filesActive: digest?.filesActive ?? [],
      pruneAdvice,
      compactionContext: compactionParts.length > 0 ? compactionParts.join('. ') : null,
    }

    if (opts?.includeParentFocus) {
      const hierarchyEntry = sessionHierarchyMap.get(sessionId)
      if (hierarchyEntry?.parentId) {
        const parentFocus = buildFocusState(hierarchyEntry.parentId)
        if (parentFocus) {
          result.parentFocus = {
            topic: parentFocus.topic,
            mode: parentFocus.mode,
            intent: parentFocus.intent,
            activeFiles: parentFocus.activeFiles?.slice(0, 10),
            turnCount: parentFocus.turnCount,
          }
        }
      }
    }

    return result
  }

  /**
   * Build a structured context package from the current session state.
   */
  async function buildHandoffContext(sessionId: string): Promise<string> {
    const parts: string[] = []

    const focus = buildFocusState(sessionId)
    if (focus) {
      if (focus.topic) parts.push(`**Topic:** ${focus.topic}`)
      if (focus.intent?.description) parts.push(`**Intent:** ${focus.intent.description}`)
      if (focus.mode) parts.push(`**Working mode:** ${focus.mode}`)
      if (focus.activeFiles?.length > 0) {
        parts.push(`**Active files:** ${focus.activeFiles.slice(0, 15).join(', ')}`)
      }
    }

    const digest = daemon.sessionDigestStore?.get?.(sessionId)
    if (digest) {
      if (digest.currentTask) parts.push(`**Current task:** ${digest.currentTask}`)
      if (digest.decisions?.length > 0) {
        parts.push(`**Key decisions so far:**\n${digest.decisions.slice(-5).map((d: string) => `- ${d}`).join('\n')}`)
      }
      if (digest.learnings?.length > 0) {
        parts.push(`**Learnings:**\n${digest.learnings.slice(-5).map((l: string) => `- ${l}`).join('\n')}`)
      }
      if (digest.filesActive?.length > 0) {
        parts.push(`**Files being worked on:** ${digest.filesActive.slice(0, 15).join(', ')}`)
      }
    }

    const mem = daemon.intelligence?.memory
    if (mem?.search) {
      try {
        const searchTerms = [focus?.topic, focus?.intent?.description, digest?.currentTask].filter(Boolean)
        const seen = new Set<string>()
        const memResults: string[] = []
        for (const term of searchTerms.slice(0, 2)) {
          const results = await mem.search(term!, 3) as any[]
          for (const r of results) {
            const key = r.key || r.content?.slice(0, 50)
            if (key && !seen.has(key)) {
              seen.add(key)
              const snippet = typeof r.content === 'string' ? r.content.slice(0, 200) : String(r.content).slice(0, 200)
              memResults.push(`- ${snippet}`)
            }
          }
        }
        if (memResults.length > 0) {
          parts.push(`**Relevant memory context:**\n${memResults.slice(0, 5).join('\n')}`)
        }
      } catch {}
    }

    if (parts.length === 0) return ''
    return `## Session Context (auto-packaged from handoff)\n\n${parts.join('\n\n')}\n\n---\n\n`
  }

  /**
   * Compute a complexity score and handoff suggestion for a session.
   */
  function computeHandoffSuggestion(sessionId: string): {
    suggested: boolean
    reason: string
    proposedGoal: string
    estimatedComplexity: 'low' | 'moderate' | 'high' | 'very-high'
  } | null {
    const digest = daemon.sessionDigestStore?.get?.(sessionId)

    if (!digest) return null

    const turnCount = digest?.turnCount ?? 0
    const complexity = 0.5
    const fileCount = digest?.filesActive?.length ?? 0
    const topic = digest?.topic || ''
    const intent = digest?.currentTask || ''

    if (turnCount < 3) return null

    let score = 0
    const reasons: string[] = []

    if (complexity > 0.7) {
      score += 0.3
      reasons.push('high cognitive complexity detected')
    }

    if (fileCount >= 5) {
      score += 0.2
      reasons.push(`${fileCount} files actively involved`)
    }
    if (fileCount >= 10) {
      score += 0.15
    }

    if (turnCount > 15) {
      score += 0.15
      reasons.push(`${turnCount} turns without completion`)
    }
    if (turnCount > 30) {
      score += 0.15
    }

    const handoffKeywords = /\b(implement|refactor|migrate|redesign|overhaul|rewrite|add feature|build out|set up|create.*system|across.*files|multiple.*components)\b/i
    if (handoffKeywords.test(intent) || handoffKeywords.test(topic)) {
      score += 0.25
      reasons.push('task language suggests multi-step work')
    }

    const optimizer = daemon.intelligence?.optimizer
    if (optimizer?.scoreSession) {
      try {
        const health = optimizer.scoreSession(sessionId)
        if (health?.stuckScore > 0) {
          score += 0.3
          reasons.push('stuck pattern detected')
        }
        if (health?.loopScore > 0.4) {
          score += 0.2
          reasons.push('potential loop detected')
        }
      } catch {}
    }

    let estimatedComplexity: 'low' | 'moderate' | 'high' | 'very-high' = 'low'
    if (score >= 0.7) estimatedComplexity = 'very-high'
    else if (score >= 0.5) estimatedComplexity = 'high'
    else if (score >= 0.3) estimatedComplexity = 'moderate'

    if (score < 0.5) return null

    const goalParts: string[] = []
    if (intent) goalParts.push(intent)
    else if (topic) goalParts.push(topic)
    else goalParts.push('Continue current task')
    if (digest?.currentTask && digest.currentTask !== intent) {
      goalParts.push(`(${digest.currentTask})`)
    }

    return {
      suggested: true,
      reason: reasons.join('; '),
      proposedGoal: goalParts.join(' '),
      estimatedComplexity,
    }
  }

  /**
   * Compute delegation requests for a session.
   */
  function computeDelegationRequests(sessionId: string): DelegationRequest[] {
    const requests: DelegationRequest[] = []
    const now = Date.now()

    const pendingForSession = [...delegationTracker.values()].filter(
      t => t.request.sessionId === sessionId && (t.status === 'pending' || t.status === 'executing')
    )
    if (pendingForSession.length >= 2) return requests

    const digest = daemon.sessionDigestStore?.get?.(sessionId)

    if (!digest) return requests

    const turnCount = digest?.turnCount ?? 0
    const complexity = 0.5
    const intent = digest?.currentTask || ''
    const topic = digest?.topic || ''

    if (turnCount < 5) return requests

    const optimizer = daemon.intelligence?.optimizer
    let stuckScore = 0
    let loopScore = 0
    if (optimizer?.scoreSession) {
      try {
        const health = optimizer.scoreSession(sessionId)
        stuckScore = health?.stuckScore ?? 0
        loopScore = health?.loopScore ?? 0
      } catch {}
    }

    if (loopScore > 0.6 && intent) {
      const delegationId = `del_${now}_stuck_${sessionId.replace(/[^a-zA-Z0-9]/g, '').slice(-8)}`

      const alreadyHasStuck = [...delegationTracker.values()].some(
        t => t.request.sessionId === sessionId && t.request.reason.includes('stuck/looping') && t.status !== 'completed' && t.status !== 'failed' && t.status !== 'expired'
      )
      if (!alreadyHasStuck) {
        requests.push({
          id: delegationId,
          sessionId,
          goal: `The parent session is stuck in a loop. Take a fresh approach to: ${intent}`,
          agentType: 'code',
          priority: 'high',
          reason: `Session stuck/looping (loopScore=${loopScore.toFixed(2)}, stuckScore=${stuckScore.toFixed(2)})`,
          estimatedComplexity: 'high',
          contextPreamble: '',
          createdAt: now,
          expiresAt: now + DELEGATION_EXPIRY_MS,
        })
      }
    }

    if (complexity > 0.85 && turnCount > 10) {
      const fileCount = digest?.filesActive?.length ?? 0
      if (fileCount >= 8) {
        const delegationId = `del_${now}_complex_${sessionId.replace(/[^a-zA-Z0-9]/g, '').slice(-8)}`

        const alreadyHasComplex = [...delegationTracker.values()].some(
          t => t.request.sessionId === sessionId && t.request.reason.includes('High complexity') && t.status !== 'completed' && t.status !== 'failed' && t.status !== 'expired'
        )
        if (!alreadyHasComplex) {
          requests.push({
            id: delegationId,
            sessionId,
            goal: intent || topic || 'Continue current multi-file task',
            agentType: 'code',
            priority: 'medium',
            reason: `High complexity (${complexity.toFixed(2)}) with ${fileCount} active files`,
            estimatedComplexity: 'very-high',
            contextPreamble: '',
            createdAt: now,
            expiresAt: now + DELEGATION_EXPIRY_MS,
          })
        }
      }
    }

    const thinker = daemon.intelligence?.thinker as any
    if (thinker?.getRecentInsights) {
      try {
        const insights = thinker.getRecentInsights?.(5) as any[] ?? []
        for (const insight of insights) {
          if (insight.trigger === 'subconscious_opportunity_subagent' && insight.timestamp > now - 30000) {
            const delegationId = `del_${now}_thinker_${sessionId.replace(/[^a-zA-Z0-9]/g, '').slice(-8)}`

            const alreadyHasThinker = [...delegationTracker.values()].some(
              t => t.request.sessionId === sessionId && t.request.reason.includes('Thinker') && now - t.request.createdAt < 30000
            )
            if (!alreadyHasThinker) {
              requests.push({
                id: delegationId,
                sessionId,
                goal: insight.insight || intent || 'Complex task requiring subagent assistance',
                agentType: 'code',
                priority: 'medium',
                reason: 'Thinker recommended subagent delegation',
                estimatedComplexity: complexity > 0.7 ? 'high' : 'moderate',
                contextPreamble: '',
                createdAt: now,
                expiresAt: now + DELEGATION_EXPIRY_MS,
              })
            }
          }
        }
      } catch {}
    }

    for (const req of requests) {
      try {
        const parts: string[] = []
        if (topic) parts.push(`Topic: ${topic}`)
        if (intent) parts.push(`Current task: ${intent}`)
        if (digest?.filesActive?.length) {
          parts.push(`Active files: ${digest.filesActive.slice(0, 10).join(', ')}`)
        }
        if (digest?.currentTask) parts.push(`Task context: ${digest.currentTask}`)
        req.contextPreamble = parts.join('\n')
      } catch {}
    }

    return requests
  }

  /**
   * Build the full context payload for the bridge plugin.
   */
  async function buildInjectPayload(): Promise<Record<string, unknown>> {
    const mem = daemon.intelligence?.memory
    const subconscious = daemon.intelligence?.subconscious

    let insight: string | null = null
    if (mem) {
      try {
        const history = await mem.kv_get('thinker:insight-history') as any[] | undefined
        if (history && history.length > 0) {
          insight = history[history.length - 1]?.insight ?? null
        }
      } catch {}
    }

    let learnings: Array<{ clusterLabel: string; summary: string; occurrences: number }> = []
    if (mem) {
      try {
        const raw = await mem.kv_get('subconscious:learnings') as any[] | undefined
        if (raw) {
          learnings = raw
            .sort((a: any, b: any) => (b.occurrences || 0) - (a.occurrences || 0))
            .slice(0, 10)
            .map((l: any) => ({
              clusterLabel: l.clusterLabel || '',
              summary: l.summary || '',
              occurrences: l.occurrences || 0,
            }))
        }
      } catch {}
    }

    const sessions: Record<string, { items: any[] }> = {}

    const focusStates: Record<string, any> = {}
    const allSessionIds = new Set<string>()
    if (subconscious?.getSessionIds) {
      for (const sid of subconscious.getSessionIds()) allSessionIds.add(sid)
    }
    if (daemon.sessionDigestStore) {
      for (const d of daemon.sessionDigestStore.all()) allSessionIds.add(d.sessionId)
    }
    // Include OpenCode sessions that have accumulated conversation history
    for (const sid of ocConversationHistory.keys()) allSessionIds.add(sid)

    for (const sid of allSessionIds) {
      const focus = buildFocusState(sid, { includeParentFocus: true })
      if (focus) focusStates[sid] = focus
    }

    const sessionHealth: Record<string, any> = {}
    const optimizer = daemon.intelligence?.optimizer
    if (optimizer?.scoreSession) {
      for (const sid of allSessionIds) {
        try {
          const health = await optimizer.scoreSession(sid)
          if (health) {
            sessionHealth[sid] = {
              loopScore: health.loopScore,
              stuckScore: health.stuckScore,
              tokenVelocity: health.tokenVelocity,
              estimatedTokens: health.estimatedTokens,
              interventionCount: health.interventionCount,
              lastAction: health.lastAction ?? null,
            }
          }
        } catch {}
      }
    }

    let anomalies: any[] = []
    if (mem) {
      try {
        const raw = await mem.kv_get('subconscious:anomalies') as any[] | undefined
        if (raw) {
          anomalies = raw
            .filter((a: any) => !a.acknowledged)
            .slice(0, 10)
            .map((a: any) => ({
              id: a.id || a.summary,
              type: a.type || 'unknown',
              summary: a.summary || '',
              severity: a.severity || 'low',
              detectedAt: a.detectedAt || a.timestamp,
              sessionId: a.sessionId || null,
            }))
        }
      } catch {}
    }

    if (mem?.search) {
      for (const sid of allSessionIds) {
        if (!sid.startsWith('oc:') || sessions[sid]) continue
        const focus = focusStates[sid]
        if (!focus?.topic && !focus?.intent?.description) continue

        try {
          const queries: string[] = []
          if (focus.topic) queries.push(focus.topic)
          if (focus.intent?.description && focus.intent.description !== focus.topic) {
            queries.push(focus.intent.description)
          }

          const allItems: any[] = []
          for (const q of queries.slice(0, 2)) {
            const results = await mem.search(q, { limit: 3 })
            for (const r of results) {
              if (r.score && r.score < 0.3) continue
              allItems.push({
                source: 'memory',
                content: typeof r.content === 'string' ? r.content.slice(0, 500) : String(r.content || '').slice(0, 500),
                relevance: r.score ?? 0,
                query: q,
              })
            }
          }

          if (allItems.length > 0) {
            const seen = new Set<string>()
            const deduped = allItems.filter(item => {
              const key = item.content.slice(0, 100)
              if (seen.has(key)) return false
              seen.add(key)
              return true
            }).slice(0, 5)

            sessions[sid] = { items: deduped }
          }
      } catch {}
      }
    }

    // HOW: Uses episodic boundary detection + importance scoring to build a compressed context block. Low-importance episodes are collapsed into single-line summaries. High-importance episodes preserve individual messages with importance-weighted content budgets.
    const PREV_CTX_CHAR_BUDGET = 12000
    const EPISODE_COLLAPSE_THRESHOLD = 0.35 // episodes below this avg importance get collapsed

    for (const [sid, history] of ocConversationHistory) {
      if (history.length <= OC_RAW_WINDOW) continue
      const olderMessages = history.slice(0, history.length - OC_RAW_WINDOW)

      // Detect episodic boundaries
      const episodes = detectEpisodes(olderMessages)

      const lines: string[] = ['PREVIOUS CONTEXT (older than recent messages):']
      let charCount = 0

      for (const ep of episodes) {
        // Low-importance episodes get collapsed to a single summary line
        if (ep.importance < EPISODE_COLLAPSE_THRESHOLD && ep.messages.length > 2) {
          const summary = summarizeEpisode(ep)
          const cost = summary.length + 5
          if (charCount + cost > PREV_CTX_CHAR_BUDGET && lines.length > 1) continue
          lines.push(summary)
          charCount += cost
          continue
        }

        // High-importance episodes: keep individual messages with importance weighting
        // Add episode header if there are multiple episodes
        if (episodes.length > 1 && ep.topic) {
          lines.push(`--- ${ep.topic} ---`)
          charCount += ep.topic.length + 10
        }

        // Sort by importance, greedily select within remaining budget
        const indexed = ep.messages.map((msg, i) => ({ msg, i }))
        indexed.sort((a, b) => b.msg.importance - a.msg.importance)

        const selected = new Set<number>()
        for (const { msg, i } of indexed) {
          const maxLen = msg.importance >= 0.5 ? 600 : msg.importance >= 0.3 ? 300 : 120
          const snippet = msg.content.length > maxLen
            ? `${msg.content.slice(0, maxLen)  }...`
            : msg.content
          const cost = snippet.length + 15
          if (charCount + cost > PREV_CTX_CHAR_BUDGET && selected.size > 0) break
          selected.add(i)
          charCount += cost
        }

        // Rebuild in chronological order within the episode
        let lastIncluded = -1
        for (let i = 0; i < ep.messages.length; i++) {
          if (!selected.has(i)) continue
          if (lastIncluded >= 0 && i > lastIncluded + 1) {
            const skipped = i - lastIncluded - 1
            lines.push(`  [...${skipped} message${skipped > 1 ? 's' : ''} omitted...]`)
          }
          lastIncluded = i
          const msg = ep.messages[i]
          const prefix = msg.role === 'user' ? 'User' : 'Assistant'
          const maxLen = msg.importance >= 0.5 ? 600 : msg.importance >= 0.3 ? 300 : 120
          const snippet = msg.content.length > maxLen
            ? `${msg.content.slice(0, maxLen)  }...`
            : msg.content
          const tag = msg.importance >= 0.5 ? ' [important]' : ''
          lines.push(`${prefix}${tag}: ${snippet}`)
        }
      }

      const prevCtx = lines.join('\n')
      if (!sessions[sid]) {
        sessions[sid] = { items: [] }
      }
      ;(sessions[sid] as any).previousContext = prevCtx
    }

    const sessionHierarchy = serializeSessionHierarchy()

    let teams: { active: any[]; pendingCheckpoints: any[]; recentlyCompleted?: any[] } | undefined
    const to = daemon.intelligence?.teamOrchestrator as any
    if (to?.listActiveTeams) {
      try {
        const activeTeams = to.listActiveTeams() as any[]
        const pendingCheckpoints = (to.listPendingCheckpoints?.() ?? []) as any[]

        let recentlyCompleted: any[] = []
        if (to.listAllTeams) {
          const allTeams = to.listAllTeams() as any[]
          const thirtyMinAgo = Date.now() - 30 * 60_000
          recentlyCompleted = allTeams
            .filter((t: any) => (t.status === 'completed' || t.status === 'failed') && (t.completedAt || 0) > thirtyMinAgo)
            .map((t: any) => {
              let completedGoals: Array<{ title: string; summary: string }> = []
              let filesModified: string[] = []
              try {
                const status = to.getTeamStatus?.(t.id)
                if (status?.goals) {
                  completedGoals = (status.goals as any[])
                    .filter((g: any) => g.status === 'completed')
                    .map((g: any) => ({ title: g.title || '', summary: g.result?.slice(0, 300) || '' }))
                    .slice(0, 20)
                }
              } catch {}

              if (t.agentIds && daemon.sessionDigestStore) {
                const filesSet = new Set<string>()
                for (const agentId of t.agentIds) {
                  try {
                    const agentDigest = daemon.sessionDigestStore.get(agentId)
                    if (agentDigest?.filesActive) {
                      for (const f of agentDigest.filesActive) filesSet.add(f)
                    }
                  } catch {}
                }
                filesModified = Array.from(filesSet).slice(0, 30)
              }

              return {
                id: t.id,
                name: t.config?.name ?? null,
                status: t.status,
                goal: t.config?.goal?.slice(0, 500) ?? '',
                finalResult: t.finalResult?.slice(0, 1000) ?? null,
                external: !!t.external,
                externalSessionId: t.externalSessionId ?? null,
                externalParentSessionId: t.externalParentSessionId ?? null,
                completedGoals,
                filesModified,
                completedAt: t.completedAt,
                budget: {
                  tokensUsed: t.budget?.tokensUsed ?? 0,
                  maxTokens: t.budget?.maxTokens ?? 0,
                  agentsSpawned: t.budget?.agentsSpawned ?? 0,
                },
              }
            })
            .slice(0, 5)
        }

        if (activeTeams.length > 0 || pendingCheckpoints.length > 0 || recentlyCompleted.length > 0) {
          teams = {
            active: activeTeams.map((t: any) => {
              let progress: any = null
              let activeAgents: any[] = []
              let goalTreeStr: string | null = null
              try {
                const status = to.getTeamStatus?.(t.id)
                if (status) {
                  progress = status.progress ?? null
                  activeAgents = (status.activeAgents ?? []).slice(0, 10)
                  goalTreeStr = status.goalTree ?? null
                }
              } catch {}

              return {
                id: t.id,
                name: t.config?.name ?? null,
                status: t.status,
                goal: t.config?.goal ?? '',
                checkpointMode: t.config?.checkpoint?.mode ?? 'none',
                external: !!t.external,
                externalSessionId: t.externalSessionId ?? null,
                externalParentSessionId: t.externalParentSessionId ?? null,
                budget: {
                  tokensUsed: t.budget?.tokensUsed ?? 0,
                  maxTokens: t.budget?.maxTokens ?? 0,
                  agentsSpawned: t.budget?.agentsSpawned ?? 0,
                  maxAgents: t.budget?.maxAgents ?? 0,
                  elapsedMs: t.budget?.startedAt ? Date.now() - t.budget.startedAt : 0,
                  maxDurationMs: t.budget?.maxDurationMs ?? 0,
                },
                agentCount: t.agentIds?.length ?? 0,
                progress: progress ? {
                  completed: progress.completed ?? 0,
                  total: progress.total ?? 0,
                  inProgress: progress.inProgress ?? 0,
                  blocked: progress.blocked ?? 0,
                } : null,
                activeAgents: activeAgents.map((a: any) => ({
                  agentId: a.agentId,
                  goalTitle: a.goalTitle,
                })),
                goalTree: goalTreeStr,
                createdAt: t.createdAt,
              }
            }),
            pendingCheckpoints: pendingCheckpoints.map((cp: any) => ({
              id: cp.id,
              teamId: cp.teamId,
              trigger: cp.trigger,
              status: cp.status,
              progressSummary: cp.progressSummary ?? '',
              completedGoals: cp.completedGoals ?? 0,
              totalGoals: cp.totalGoals ?? 0,
              budget: cp.budgetSnapshot ?? null,
              createdAt: cp.createdAt,
            })),
            ...(recentlyCompleted.length > 0 ? { recentlyCompleted } : {}),
          }
        }
      } catch {}
    }

    let siblingLearnings: Record<string, {
      topic: string
      learnings: string[]
      decisions: string[]
      filesActive: string[]
      lastActiveAt: number
      turnCount: number
    }> | undefined
    if (daemon.sessionDigestStore) {
      try {
        const allDigests = daemon.sessionDigestStore.all()
        const withContent = allDigests.filter(
          (d: any) => d.isActive && (d.learnings.length > 0 || d.decisions.length > 0)
        )
        if (withContent.length > 0) {
          siblingLearnings = {}
          for (const d of withContent) {
            siblingLearnings[d.sessionId] = {
              topic: d.topic || '',
              learnings: d.learnings.slice(-5),
              decisions: d.decisions.slice(-5),
              filesActive: d.filesActive.slice(0, 5),
              lastActiveAt: d.lastActiveAt,
              turnCount: d.turnCount,
            }
          }
        }
      } catch {}
    }

    let crossSessionPatterns: Array<{
      category: string
      description: string
      confidence: number
      sessionCount: number
    }> | undefined
    if (daemon.crossSessionCorrelator) {
      try {
        const patterns = daemon.crossSessionCorrelator.getPatterns({
          minConfidence: 0.5,
          limit: 10,
        })
        if (patterns.length > 0) {
          crossSessionPatterns = patterns.map((p: any) => ({
            category: p.category,
            description: p.description,
            confidence: p.confidence,
            sessionCount: p.sessionCount,
          }))
        }
      } catch {}
    }

    let dialecticLatest: Record<string, {
      hasSignal: boolean
      signal?: {
        type: string
        content: string
        confidence: number
        urgency: string
      }
      yangBranchCount: number
      yinCritiqueCount: number
      dialecticTension: number
      synthesisConfidence: number
      timestamp: number
    }> | undefined
    const dialectic = daemon.intelligence?.dialectic as any
    if (dialectic?.getRecent) {
      try {
        const dialecticResults: Record<string, any> = {}
        for (const sid of allSessionIds) {
          const recent = await dialectic.getRecent(sid, 1) as any[]
          if (recent.length === 0) continue
          const r = recent[0]
          const synthesis = r.serenity?.synthesis
          if (!synthesis) continue

          dialecticResults[sid] = {
            hasSignal: synthesis.hasSignal ?? false,
            ...(synthesis.hasSignal && synthesis.signal ? {
              signal: {
                type: synthesis.signal.type,
                content: synthesis.signal.content,
                confidence: synthesis.signal.confidence,
                urgency: synthesis.signal.urgency ?? 'background',
              },
            } : {}),
            yangBranchCount: r.yang?.branches?.length ?? 0,
            yinCritiqueCount: r.yin?.baselineBranches?.length ?? r.yin?.critiques?.length ?? 0,
            dialecticTension: r.quality?.dialecticTension ?? r.serenity?.meta?.dialecticQuality ?? 0,
            synthesisConfidence: r.quality?.synthesisConfidence ?? 0,
            timestamp: r.timestamp,
          }
        }
        if (Object.keys(dialecticResults).length > 0) {
          dialecticLatest = dialecticResults
        }
      } catch {}
    }

    let handoffSuggestions: Record<string, {
      suggested: boolean
      reason: string
      proposedGoal: string
      estimatedComplexity: 'low' | 'moderate' | 'high' | 'very-high'
    }> | undefined
    try {
      const suggestions: Record<string, any> = {}
      for (const sid of allSessionIds) {
        if (!sid.startsWith('oc:')) continue
        const suggestion = computeHandoffSuggestion(sid)
        if (suggestion) suggestions[sid] = suggestion
      }
      if (Object.keys(suggestions).length > 0) {
        handoffSuggestions = suggestions
      }
    } catch {}

    // WHY: Includes ALL recent session digests (not just active ones) so that a newly opened session can be primed with knowledge of what was worked on recently. Capped at the 10 most-recent sessions.
    let recentSessionRecap: Array<{
      sessionId: string
      topic: string
      currentTask: string
      decisions: string[]
      learnings: string[]
      filesActive: string[]
      recentActions: string[]
      turnCount: number
      lastActiveAt: number
      isActive: boolean
    }> | undefined
    if (daemon.sessionDigestStore) {
      try {
        const allDigests = daemon.sessionDigestStore.all()
        const withContent = allDigests
          .filter((d: any) => d.topic || d.currentTask || d.learnings.length > 0 || d.decisions.length > 0)
          .sort((a: any, b: any) => (b.lastActiveAt || 0) - (a.lastActiveAt || 0))
          .slice(0, 10)
        if (withContent.length > 0) {
          recentSessionRecap = withContent.map((d: any) => ({
            sessionId: d.sessionId,
            topic: d.topic || '',
            currentTask: d.currentTask || '',
            decisions: (d.decisions || []).slice(-5),
            learnings: (d.learnings || []).slice(-5),
            filesActive: (d.filesActive || []).slice(0, 10),
            recentActions: (d.recentActions || []).slice(-5),
            turnCount: d.turnCount || 0,
            lastActiveAt: d.lastActiveAt || 0,
            isActive: !!d.isActive,
          }))
        }
      } catch {}
    }

    let delegationRequests: DelegationRequest[] | undefined
    try {
      const now = Date.now()

      for (const [id, tracking] of delegationTracker) {
        if (tracking.status === 'pending' && now > tracking.request.expiresAt) {
          tracking.status = 'expired'
          logger.debug('Delegation request expired', { id })
        }
        if (['completed', 'failed', 'expired'].includes(tracking.status) && now - tracking.request.createdAt > 5 * 60 * 1000) {
          delegationTracker.delete(id)
        }
      }

      if (now - lastDelegationComputeTime >= DELEGATION_COMPUTE_INTERVAL_MS) {
        lastDelegationComputeTime = now

        const totalPending = [...delegationTracker.values()].filter(t => t.status === 'pending').length

        if (totalPending < DELEGATION_MAX_PENDING) {
          for (const sid of allSessionIds) {
            if (!sid.startsWith('oc:')) continue
            const newRequests = computeDelegationRequests(sid)
            for (const req of newRequests) {
              if (totalPending + delegationTracker.size >= DELEGATION_MAX_PENDING + 5) break
              delegationTracker.set(req.id, { request: req, status: 'pending' })
              logger.info('New delegation request', {
                id: req.id,
                sessionId: req.sessionId,
                reason: req.reason,
                priority: req.priority,
              })
            }
          }
        }
      }

      const pending = [...delegationTracker.values()]
        .filter(t => t.status === 'pending')
        .map(t => t.request)

      if (pending.length > 0) {
        delegationRequests = pending
      }
    } catch {}

    return {
      updatedAt: Date.now(),
      insight,
      learnings,
      sessions,
      focusStates,
      sessionHealth,
      anomalies,
      ...(Object.keys(sessionHierarchy).length > 0 ? { sessionHierarchy } : {}),
      ...(teams ? { teams } : {}),
      ...(siblingLearnings ? { siblingLearnings } : {}),
      ...(crossSessionPatterns ? { crossSessionPatterns } : {}),
      ...(dialecticLatest ? { dialecticLatest } : {}),
      ...(handoffSuggestions ? { handoffSuggestions } : {}),
      ...(delegationRequests ? { delegationRequests } : {}),
      ...(recentSessionRecap ? { recentSessionRecap } : {}),
    }
  }

  async function handler(req: http.IncomingMessage, res: http.ServerResponse) {
    const url = new URL(req.url || '', `http://${tcpHost}:${currentTcpPort}`)
    const parts = url.pathname.split('/').filter(Boolean)
    const pathname = url.pathname
    const method = req.method || 'GET'

    const pluginRoute = pathname.startsWith('/plugin/')
    const pluginBearerAuth = typeof req.headers.authorization === 'string' && req.headers.authorization.startsWith('Bearer cpk_')
    const pluginRegisterRoute = pluginRoute && pathname === '/plugin/register'
    const pluginAuthenticatedRoute = pluginRoute && (
      pathname === '/plugin/message'
      || pathname === '/plugin/heartbeat'
      || pathname === '/plugin/events'
      || (method === 'DELETE' && parts.length === 2)
    )

    if (!authOk(req) && !(pluginAuthenticatedRoute && pluginBearerAuth) && !pluginRegisterRoute) {
      sendJSON(res, 401, { error: 'unauthorized' })
      return
    }

    try {
      // HOW: GET /context is a special case that uses buildInjectPayload directly
      if (method === 'GET' && pathname === '/context') {
        try {
          const payload = await buildInjectPayload()
          sendJSON(res, 200, payload)
          return
        } catch (err) {
          logger.error('GET /context failed', { error: String(err) })
          sendJSON(res, 500, { error: 'Failed to build context payload' })
          return
        }
      }

      // HOW: GET /intelligence/context-focus is a special case that uses buildFocusState directly
      if (method === 'GET' && pathname === '/intelligence/context-focus') {
        try {
          const sessionId = url.searchParams.get('sessionId')
          if (!sessionId) {
            sendJSON(res, 400, { error: 'sessionId query parameter is required' })
            return
          }
          const focus = buildFocusState(sessionId, { includeParentFocus: true })
          if (!focus) {
            sendJSON(res, 200, { sessionId, focusState: null, message: 'no focus data available for this session' })
            return
          }
          sendJSON(res, 200, { sessionId, focusState: focus })
          return
        } catch (err) {
          sendJSON(res, 500, { error: String(err) })
          return
        }
      }

      const routeHandlers = [
        // OpenAI-compatible warm provider endpoint — checked first since /v1/* is a distinct prefix
        () => handleWarmProviderRoutes({ daemon, logger, sendJSON, parseBody }, req, res, method, pathname),
        () => handleHealthRoutes({ daemon, logger, sendJSON }, req, res, method, pathname),
        () => handleConfigRoutes({ daemon, logger, sendJSON, parseBody }, req, res, method, pathname, parts),
        () => handleChannelsRoutes({ daemon, logger, sendJSON, parseBody }, req, res, method, pathname),
        () => handleDebugRoutes({ daemon, logger, sendJSON, parseBody, url, pathname, sseConnections, sseConnectionId }, req, res, method),
        () => handleEventsRoutes({ daemon, logger, sendJSON, parseBody, buildStateSnapshot, processHierarchyEvent, onEventsIngested: _ocIngestInterceptor, url, pathname, sseConnections, sseConnectionId }, req, res, method),
        () => handleOrchestrationRoutes({ daemon, logger, sendJSON, parseBody, parts }, req, res, method),
        () => handlePluginAPIRoutes({ logger, registry: pluginRegistry, pluginAPI: pluginApi, sendJSON, readBody: parseBody, parts, attachEventStream: attachPluginEventStream }, req, res, method),
        () => handlePluginsRoutes({ daemon, logger, sendJSON, parts }, req, res, method),
        () => handleIntelligenceRoutes({ daemon, logger, sendJSON, parseBody, url, parts }, req, res, method, pathname),
        () => handleCycleHooksRoutes({ daemon, logger, sendJSON, parseBody, url, pathname }, req, res, method),
        () => handleProvidersRoutes({ runtime, logger, sendJSON, parseBody, isObject, mergeDeep }, req, res, method, pathname),
        () => handleSubagentsRoutes({ daemon, logger, sendJSON, parseBody, url, parts }, req, res, method),
        () => handleDelegationRoutes({ daemon, logger, sendJSON, parseBody, delegationTracker, subagentToTeamMap }, req, res, method, pathname),
        () => handleTeamsRoutes({ daemon, logger, sendJSON, parseBody, url, parts, sseConnections, sseConnectionId, resolveLatestTeamId, buildHandoffContext }, req, res, method),
         () => handleSessionsRoutes({ runtime, logger, sendJSON, parseBody, getFirstUserMessage, getLastUserMessage, tcpHost, currentTcpPort }, req, res, method, pathname, parts),
         () => handleModulesRoutes({ runtime, logger, sendJSON, parseBody }, req, res, method, pathname, parts),
         () => handleMemoryRoutes({ daemon, logger, sendJSON, parseBody, url, parts }, req, res, method),
        () => handleDialecticRoutes({ runtime, logger, sendJSON, parseBody, url, parts }, req, res, method),
        () => handleObservabilityRoutes({ daemon, logger, sendJSON, url, pathname }, req, res, method),
        () => handleChatRoutes({ runtime, logger, sendJSON, parseBody, parts }, req, res, method, pathname),
        () => handleModelsRoutes({ runtime, logger, sendJSON }, req, res, method, pathname),
        () => handleMcpRoutes({ daemon, logger, sendJSON }, req, res, method, pathname),
        () => handleToolsRoutes({ runtime, logger, sendJSON, parseBody, pathname }, req, res, method),
        () => handleThalamusRoutes({ daemon, logger, sendJSON, parseBody }, req, res, method),
        () => handleContextRoutes({ runtime, logger, sendJSON, parseBody, parts }, req, res, method, pathname),
        () => handlePermissionsRoutes({ daemon, logger, sendJSON, parseBody, url, parts }, req, res, method, pathname),
        () => handleVerificationRoutes({ daemon, logger, sendJSON, parseBody, url, pathname }, req, res, method),
         () => handleImprovementRoutes({ daemon, logger, sendJSON, parseBody, url, pathname }, req, res, method),
         () => handleHelixRoutes({ daemon, logger, sendJSON, parseBody }, req, res, method),
         () => handleConstellationRoutes({ daemon, logger, sendJSON, parseBody }, req, res, method),
         () => handleMeditationRoutes({ daemon, logger, sendJSON, parseBody }, req, res, method),
         () => handleProactiveRoutes({ proactive: daemon.intelligence?.proactiveEnricher, logger, sendJSON, parseBody }, req, res, method),
         () => handleDreamerRoutes({ daemon, logger, sendJSON, parseBody, url, pathname }, req, res, method),
         () => handleModelDirectiveRoutes({
           daemon,
           logger,
           sendJSON,
           parseBody,
           persistRuntimeOverrides: async () => {
             const layered = daemon.config as any
             if (typeof layered?.persistOverrides === 'function') {
               await layered.persistOverrides()
             }
           },
         }, req, res, method, pathname),
         () => handleCortexRoutes({ daemon, logger, sendJSON, parseBody }, req, res, method),
        () => handlePinealRoutes({ daemon, logger, sendJSON, parseBody }, req, res, method),
        () => handleBlackboardRoutes({ daemon, logger, sendJSON, parseBody }, req, res, method),
         () => handleFileArtifactRoutes({ daemon, logger, sendJSON, parseBody }, req, res, method),
         () => handleCodeStoreRoutes({ daemon, logger, sendJSON, parseBody }, req, res, method),
         () => handleTrainingRoutes({ daemon, logger, sendJSON, parseBody, url, pathname }, req, res, method),
         () => handlePromptLogRoutes({ daemon, logger, sendJSON, url, pathname }, req, res, method),
         () => handleTimelineRoutes({ daemon, logger, sendJSON, parseBody, url, pathname, sseConnections, sseConnectionId }, req, res, method),
         () => handlePrismRoutes({ daemon, logger, sendJSON, parseBody, url, parts }, req, res, method),
      ]

      for (const routeHandler of routeHandlers) {
        const handled = await routeHandler()
        if (handled) return
      }

      // HOW: tools/fs fallback uses createToolsApi for file system operations
      if (parts[0] === 'tools' || parts[0] === 'fs') {
        const toolsApi = createToolsApi(logger)
        return toolsApi.handler(req, res)
      }

      sendJSON(res, 404, { error: 'not_found' })
    } catch (err) {
      logger.warn(`admin-api error: ${String(err)}`)
      sendJSON(res, 500, { error: String(err) })
    }
  }

  let unixServer: http.Server | null = null
  let tcpServer: http.Server | null = null

  return {
    async start() {
      if (unixServer || tcpServer) return { tcpPort: currentTcpPort, unixPath }

      try {
        if (fs.existsSync(unixPath)) fs.unlinkSync(unixPath)
      } catch {}

      unixServer = http.createServer(handler)
      unixServer.on('upgrade', (req, socket, head) => { void handleWebSocketUpgrade(req, socket, head) })
      unixServer.on('error', (e) => logger.warn(`unix server error: ${String(e)}`))
      unixServer.on('clientError', (_err, socket) => {
        if (socket.writable) socket.end('HTTP/1.1 400 Bad Request\r\n\r\n')
      })
      await new Promise<void>((resolve, reject) => {
        unixServer!.listen(unixPath, () => {
          try {
            fs.chmodSync(unixPath, 0o660)
            if (!fs.existsSync(unixPath)) {
              throw new Error(`unix socket missing after bind: ${unixPath}`)
            }
            unixSocketInode = fs.statSync(unixPath).ino
          } catch (err) {
            logger.warn(`unix socket verification failed: ${String(err)}`)
          }
          logger.info(`listening on unix:${unixPath}`)
          resolve()
        })
        unixServer!.on('error', reject)
      })

      let boundPort: number | null = null
      for (let i = 0; i < 10; i++) {
        const tryPort = baseTcpPort + i
        const s = http.createServer(handler)
        s.on('upgrade', (req, socket, head) => { void handleWebSocketUpgrade(req, socket, head) })
        s.on('clientError', (_err, socket) => {
          if (socket.writable) socket.end('HTTP/1.1 400 Bad Request\r\n\r\n')
        })

        try {
          await new Promise<void>((resolve, reject) => {
            s.listen(tryPort, tcpHost, () => resolve())
            s.once('error', (err) => reject(err))
          })
          // Add persistent runtime error handler after successful bind
          s.on('error', (err) => {
            logger.error(`TCP server runtime error on port ${tryPort}: ${String(err)}`)
          })
          tcpServer = s
          boundPort = tryPort
          currentTcpPort = tryPort
          logger.info(`listening on http://${tcpHost}:${tryPort}`)
          break
        } catch (err: any) {
          if (err && err.code === 'EADDRINUSE') {
            logger.warn(`port ${tryPort} in use; trying ${tryPort + 1}`)
            try { s.close?.(); } catch {}
            continue
          }
          try { s.close?.(); } catch {}
          throw err
        }
      }

      if (!boundPort) {
        logger.warn('failed to bind TCP admin port (no available port found)')
      }

      // HOW: WebSocket support pending implementation (Lumen design complete, see /tmp/lumen-ws-design.json)

      logger.info('context available via GET /context on unix socket')

      return { tcpPort: boundPort, unixPath, tcpServer, unixServer }
    },
    async stop() {
      if (unixServer) {
        await new Promise<void>((resolve) => unixServer!.close(() => resolve()))
        unixServer = null
      }
      if (tcpServer) {
        await new Promise<void>((resolve) => tcpServer!.close(() => resolve()))
        tcpServer = null
      }
      pluginRegistry.destroy()
      try {
        if (fs.existsSync(unixPath)) {
          const stat = fs.statSync(unixPath)
          if (unixSocketInode === null || stat.ino === unixSocketInode) {
            fs.unlinkSync(unixPath)
          }
        }
      } catch {}
      unixSocketInode = null
      
      logger.info('stopped')
    }
  }
}
