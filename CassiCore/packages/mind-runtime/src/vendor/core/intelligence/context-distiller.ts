/**
 * Context Distiller — Phase Zero for agent/team spawning.
 *
 * Enriches a goal with context from the parent conversation before
 * passing it to a spawned team, Lumen analysis, or Dyad pipeline.
 * Ensures spawned agents understand *why* they were created and
 * what preceded them, rather than starting cold.
 *
 * Data sources (in priority order):
 *   1. PromptLogStore — full, untruncated prompts from the parent session
 *   2. Session history — runtime Message[] if available
 *   3. Memory search — past patterns relevant to the goal
 *
 * Output structure prepended to goal:
 *   ## Context from Parent
 *   ### Recent Exchange — last user + assistant messages verbatim
 *   ### Active Plan — extracted plan/task content
 *   ### Background — LLM-distilled summary of older context
 *   ### Relevant Memory — memory search results
 *   ---
 *   ## Goal — original goal text
 */

import type { ILogger } from '@cassicore/foundation'
import type { IMemory } from '@cassicore/foundation'
import type { IModelDirective } from '@cassicore/foundation'
import type { Message } from '@cassicore/foundation'
import type { RuntimeEvent } from '@cassicore/foundation'
import type { ModelPool } from '@cassicore/model-pool'
import type { ModuleSessionRegistry } from './module-session-registry.js'
import type {
  PromptLogStore,
  SerializedMessage,
} from '../prompt-log-store.js'
import type { GlobalBlackboardRegistry } from '@cassicore/flux-team'
import type { BlackboardChannel } from '@cassicore/foundation'



function formatTimeAgo(timestampMs: number): string {
  const diffMs = Date.now() - timestampMs
  const diffSec = Math.floor(diffMs / 1000)
  if (diffSec < 60) return `${diffSec}s ago`
  const diffMin = Math.floor(diffSec / 60)
  if (diffMin < 60) return `${diffMin}m ago`
  const diffHr = Math.floor(diffMin / 60)
  if (diffHr < 24) return `${diffHr}h ago`
  const diffDay = Math.floor(diffHr / 24)
  return `${diffDay}d ago`
}

/** Minimal event bus interface for parent session auto-detection */
export interface DistillerEventBus {
  getGlobalEventsSince(timestampMs: number): RuntimeEvent[]
}



export interface DistillContextOpts {
  /** The goal for the spawned agent/team */
  goal: string
  /** Explicit context from the caller */
  context?: string
  /** Session ID to pull conversation history from the prompt log */
  parentSessionId?: string
  /** Pre-fetched conversation history (alternative to parentSessionId) */
  parentHistory?: Message[]
  /** Max tokens for the distilled context block (default: 2000) */
  tokenBudget?: number
  /** Session ID for budget scoping of the LLM distillation call */
  sessionId?: string
  /** Job ID for model directive routing */
  jobId?: string
  /**
   * MCP tool name that triggered the spawn (e.g., 'flux_team').
   * Used for auto-detecting the parent session via tool-call fingerprinting
   * when parentSessionId is not explicitly provided.
   */
  spawnToolName?: string
  /** Artifact namespace for file sharing context injection (e.g. 'dyad:{id}', 'team:{id}') */
  artifactNamespace?: string
}

export interface DistilledContext {
  /** Goal with context prepended (combined single string) */
  enrichedGoal: string
  /** Just the distilled context block (no goal) — for callers that keep goal separate */
  distilledContext: string
  /** Individual sections for inspection/logging */
  sections: {
    recentExchange?: string
    plan?: string
    background?: string
    memoryContext?: string
    fileArtifacts?: string
  }
  /** Estimated tokens in the injected context (not counting goal) */
  contextTokenEstimate: number
  /** Time taken for distillation in ms */
  durationMs: number
}



const DEFAULT_TOKEN_BUDGET = 2000
const MAX_HISTORY_TURNS = 30
const LLM_MAX_INPUT_CHARS = 8000
const LLM_MAX_OUTPUT_TOKENS = 600
/** How far back (ms) to search for the tool event that triggered this spawn */
const PARENT_DETECT_WINDOW_MS = 15_000
const PLAN_KEYWORDS = /\b(plan|approach|strategy|steps|roadmap|phases?|milestones?|tasks?|implementation|todo)\b/i
const NUMBERED_LIST = /^\s*\d+[\.\)]\s+/m
const TODO_PATTERN = /[-*]\s+\[[ x✓✗]\]/i



export class ContextDistiller {
  private readonly logger: ILogger
  private modelPool?: ModelPool
  private modelDirective?: IModelDirective
  private memory?: IMemory
  private promptLogStore?: PromptLogStore
  private eventBus?: DistillerEventBus
  private moduleRegistry?: ModuleSessionRegistry
  private globalBlackboardRegistry?: GlobalBlackboardRegistry

  constructor(logger: ILogger) {
    this.logger = logger.child ? logger.child('context-distiller') : logger
  }

  setModelPool(pool: ModelPool): void { this.modelPool = pool }
  setModelDirective(directive: IModelDirective): void { this.modelDirective = directive }
  setMemory(memory: IMemory): void { this.memory = memory }
  setPromptLogStore(store: PromptLogStore): void { this.promptLogStore = store }
  setEventBus(bus: DistillerEventBus): void { this.eventBus = bus }

  /** Wire the module session registry for persistent debug sessions. */
  setModuleRegistry(registry: ModuleSessionRegistry): void {
    this.moduleRegistry = registry
    registry.getOrCreate('context-distiller')
  }

  /**
   * Distill context from the parent conversation and enrichment sources.
   * Always safe to call — gracefully degrades if dependencies are missing.
   */
  async distill(opts: DistillContextOpts): Promise<DistilledContext> {
    const start = Date.now()
    const {
      goal, context, parentHistory,
      tokenBudget = DEFAULT_TOKEN_BUDGET, sessionId, jobId,
      spawnToolName,
    } = opts
    let { parentSessionId } = opts
    const sections: DistilledContext['sections'] = {}

    // When no explicit parentSessionId is provided, use tool-call
    // fingerprinting to find the OpenCode session that spawned us.
    if (!parentSessionId && !parentHistory?.length && spawnToolName) {
      const detected = await this.resolveParentSession(spawnToolName)
      if (detected) {
        parentSessionId = detected
        this.logger.info('Auto-detected parent session via tool-call fingerprint', {
          parentSessionId: detected.slice(0, 16),
          spawnToolName,
        })
      }
    }

    // Priority: parentHistory (pre-fetched) > promptLogStore (by session ID)
    let conversationTurns: ConversationTurn[] = []

    if (parentHistory && parentHistory.length > 0) {
      conversationTurns = extractTurnsFromMessages(parentHistory)
      this.logger.debug('Using pre-fetched parent history', { turns: conversationTurns.length })
    } else if (parentSessionId && this.promptLogStore) {
      conversationTurns = this.extractTurnsFromPromptLog(parentSessionId)
      this.logger.debug('Extracted from prompt log', { sessionId: parentSessionId, turns: conversationTurns.length })
    }

    if (conversationTurns.length > 0) {
      const { recentExchange, plan, olderTurns } = partitionHistory(conversationTurns)
      sections.recentExchange = recentExchange
      if (plan) sections.plan = plan

      if (olderTurns.length > 0 && this.modelPool) {
        try {
          sections.background = await this.distillOlderContext(
            olderTurns, goal, sessionId, jobId,
          )
        } catch (err) {
          this.logger.warn('LLM distillation of older context failed', { error: String(err) })
        }
      }
    }

    if (this.memory) {
      try {
        const memoryContext = await this.searchMemory(goal)
        if (memoryContext) sections.memoryContext = memoryContext
      } catch (err) {
        this.logger.debug('Memory enrichment failed', { error: String(err) })
      }
    }

    const distilledContext = assembleContextBlock(context, sections, tokenBudget)
    const enrichedGoal = distilledContext
      ? `${distilledContext}\n\n---\n\n## Goal\n\n${goal}`
      : goal

    const durationMs = Date.now() - start
    const contextTokenEstimate = Math.ceil(Math.max(0, distilledContext.length) / 4)

    this.logger.info('Context distillation complete', {
      durationMs,
      contextTokenEstimate,
      parentSessionId: parentSessionId ?? '[none]',
      conversationTurns: conversationTurns.length,
      sections: Object.keys(sections),
    })

    return { enrichedGoal, distilledContext, sections, contextTokenEstimate, durationMs }
  }



  /**
   * Extract user/assistant conversation turns from the most recent
   * prompt log entry for a session. The most recent entry contains
   * the full accumulated conversation (since LLMs receive all history).
   */
  private extractTurnsFromPromptLog(sessionId: string): ConversationTurn[] {
    if (!this.promptLogStore) return []

    try {
      // Get the most recent prompt log entry for this session.
      // Source 'turn-pipeline' entries contain the main conversation.
      // Fall back to any source if 'turn-pipeline' has no entries.
      let entries = this.promptLogStore.list({
        sessionId,
        source: 'turn-pipeline',
        limit: 1,
      })
      if (entries.length === 0) {
        entries = this.promptLogStore.list({ sessionId, limit: 1 })
      }
      if (entries.length === 0) return []

      const entry = this.promptLogStore.getById(entries[0].id)
      if (!entry) return []

      return extractTurnsFromSerializedMessages(entry.messages)
    } catch (err) {
      this.logger.warn('Failed to extract from prompt log', {
        error: String(err), sessionId,
      })
      return []
    }
  }



  /**
   * Use a fast-tier LLM to summarize older conversation context
   * into a concise briefing for the spawned agent.
   */
  private async distillOlderContext(
    turns: ConversationTurn[],
    goal: string,
    sessionId?: string,
    jobId?: string,
  ): Promise<string> {
    if (!this.modelPool) return ''

    const override = this.modelDirective?.resolve(jobId, 'context-distiller')
    const handle = await this.modelPool.acquire('fast', undefined, sessionId, override)

    try {
      const historyText = turns
        .map(t => `[${t.role}]: ${t.text}`)
        .join('\n---\n')
        .slice(0, LLM_MAX_INPUT_CHARS)

      const messages: Message[] = [
        {
          role: 'user',
          content:
            `You are a context distiller. A new agent is about to be spawned to work on a goal. ` +
            `Summarize the preceding conversation into a concise briefing so the agent understands what led to this point.\n\n` +
            `**Goal being assigned:** ${goal.slice(0, 500)}\n\n` +
            `**Preceding conversation:**\n${historyText}\n\n` +
            `Produce a brief summary (3-6 sentences) covering:\n` +
            `1. What was being discussed/worked on\n` +
            `2. Key decisions, preferences, or constraints mentioned\n` +
            `3. Why this goal was spawned (the motivation)\n` +
            `4. Any relevant technical details or context\n\n` +
            `Be concise, factual, and directly useful. No greetings or filler.`,
        },
      ]

      const result = await handle.complete(messages, {
        model: handle.model,
        maxTokens: LLM_MAX_OUTPUT_TOKENS,
        temperature: 0.2,
        thinking: 'none',
        source: 'context-distiller',
        trigger: 'phase-zero',
        sessionId,
      })

      const response = result.response.trim()
      // Mirror to module debug session for Telegram observability
      if (this.moduleRegistry && response) {
        this.moduleRegistry.appendTurn('context-distiller', 'user', `[distill] goal: ${goal.slice(0, 150)}`)
        this.moduleRegistry.appendTurn('context-distiller', 'assistant', response.slice(0, 400))
      }
      return response
    } finally {
      handle.release()
    }
  }



  private async searchMemory(goal: string): Promise<string> {
    if (!this.memory) return ''

    const query = goal.slice(0, 150)
    const results = await this.memory.search(query, { limit: 5, minScore: 0.3 })
    if (results.length === 0) return ''

    const items = results.map(r => {
      const tags = (r.entry.metadata?.['tags'] as string[] | undefined) ?? []
      const tagStr = tags.length > 0 ? ` [${tags.join(', ')}]` : ''
      return `- (${Math.round(r.score * 100)}%${tagStr}) ${r.entry.content.slice(0, 300)}`
    })

    return items.join('\n')
  }




  //
  // When a team/Lumen/Dyad is spawned from OpenCode via MCP, there's no
  // CassiCore parentSessionId available. But the OpenCode channel worker
  // forwards tool events as channel:tool_update to the event bus.
  //
  // We use the spawn tool call itself as a fingerprint: find which oc:*
  // session recently called the spawn tool (e.g., flux_team). This
  // is deterministic even with multiple concurrent OpenCode sessions,
  // because the tool name + timing form a unique key.
  //
  // Race condition: The tool event from the SSE stream and the MCP tool
  // call are processed concurrently. The event might arrive slightly
  // after the MCP handler triggers context distillation. We retry up to
  // 3 times with 300ms delay to handle this.

  /**
   * Resolve the parent session ID by matching a recent channel:tool_update
   * event to the spawn tool name. Returns the oc:* session ID if found.
   */
  private async resolveParentSession(
    spawnToolName: string,
    maxRetries = 3,
    retryDelayMs = 300,
  ): Promise<string | undefined> {
    if (!this.eventBus) {
      this.logger.debug('No EventBus wired — cannot auto-detect parent session')
      return undefined
    }

    for (let attempt = 0; attempt < maxRetries; attempt++) {
      const cutoffMs = Date.now() - PARENT_DETECT_WINDOW_MS
      const recentEvents = this.eventBus.getGlobalEventsSince(cutoffMs)

      // Filter for channel:tool_update events matching the spawn tool name
      const matching = recentEvents.filter((e: RuntimeEvent) => {
        if (e.type !== 'channel:tool_update') return false
        const ev = e as Extract<RuntimeEvent, { type: 'channel:tool_update' }>
        return ev.toolName === spawnToolName
      })

      if (matching.length >= 1) {
        // Sort by timestamp descending to get the most recent
        type ToolUpdateEvent = Extract<RuntimeEvent, { type: 'channel:tool_update' }>
        matching.sort((a: RuntimeEvent, b: RuntimeEvent) =>
          (b as ToolUpdateEvent).timestamp.getTime() - (a as ToolUpdateEvent).timestamp.getTime()
        )
        const hit = matching[0] as ToolUpdateEvent
        const sessionId = hit.sessionId

        if (sessionId) {
          this.logger.debug('Parent session resolved via tool-call fingerprint', {
            sessionId: sessionId.slice(0, 16),
            spawnToolName,
            attempt,
            matchCount: matching.length,
          })
          return sessionId
        }
      }

      // No match yet — race condition. Wait and retry.
      if (attempt < maxRetries - 1) {
        this.logger.debug('No tool event match yet, retrying...', {
          spawnToolName,
          attempt: attempt + 1,
          delayMs: retryDelayMs,
        })
        await new Promise(resolve => setTimeout(resolve, retryDelayMs))
      }
    }

    this.logger.debug('Parent session auto-detection exhausted retries', {
      spawnToolName,
      maxRetries,
    })
    return undefined
  }
}



interface ConversationTurn {
  role: 'user' | 'assistant'
  text: string
}



/** Extract conversation turns from runtime Message[] (session history). */
/**
 * @dep callers: distill (core/intelligence/context-distiller.ts)
 * @dep calls: messageToText
 * @dep flows: Project → MessageToText (3/4), Project → MessageToText (3/4), Project → MessageToText (3/4)
 * @dep module: Intelligence
 * @dep risk: MEDIUM | 1 caller, 3 flows, 1 module
 */

function extractTurnsFromMessages(messages: Message[]): ConversationTurn[] {
  const turns: ConversationTurn[] = []
  for (const msg of messages.slice(-MAX_HISTORY_TURNS)) {
    if (msg.role !== 'user' && msg.role !== 'assistant') continue
    const text = messageToText(msg)
    if (!text.trim()) continue
    turns.push({ role: msg.role, text })
  }
  return turns
}

/** Extract conversation turns from PromptLogStore serialized messages. */
/**
 * @dep callers: extractTurnsFromPromptLog (core/intelligence/context-distiller.ts)
 * @dep calls: serializedMessageToText
 * @dep flows: Project → SerializedMessageToText (4/5), Project → SerializedMessageToText (4/5), Project → SerializedMessageToText (4/5)
 * @dep module: Intelligence
 * @dep risk: MEDIUM | 1 caller, 3 flows, 1 module
 */

function extractTurnsFromSerializedMessages(messages: SerializedMessage[]): ConversationTurn[] {
  const turns: ConversationTurn[] = []
  for (const msg of messages.slice(-MAX_HISTORY_TURNS)) {
    if (msg.role !== 'user' && msg.role !== 'assistant') continue
    const text = serializedMessageToText(msg)
    if (!text.trim()) continue
    turns.push({ role: msg.role as 'user' | 'assistant', text })
  }
  return turns
}

/** Convert a runtime Message to plain text. */
/**
 * @dep callers: extractTurnsFromMessages (core/intelligence/context-distiller.ts)
 * @dep flows: Project → MessageToText (4/4), Project → MessageToText (4/4), Project → MessageToText (4/4)
 * @dep module: Unknown
 * @dep risk: MEDIUM | 1 caller, 3 flows, 1 module
 */

function messageToText(msg: Message): string {
  if (typeof msg.content === 'string') return msg.content
  if (!Array.isArray(msg.content)) return ''
  return (msg.content as Array<{ type: string; text?: string }>)
    .filter(b => b.type === 'text' && b.text)
    .map(b => b.text!)
    .join('\n')
}

/** Convert a SerializedMessage to plain text (text blocks only, skips tool noise). */
/**
 * @dep callers: extractTurnsFromSerializedMessages (core/intelligence/context-distiller.ts)
 * @dep flows: Project → SerializedMessageToText (5/5), Project → SerializedMessageToText (5/5), Project → SerializedMessageToText (5/5)
 * @dep module: Unknown
 * @dep risk: MEDIUM | 1 caller, 3 flows, 1 module
 */

function serializedMessageToText(msg: SerializedMessage): string {
  if (typeof msg.content === 'string') return msg.content
  if (!Array.isArray(msg.content)) return ''
  return msg.content
    .filter(b => b.type === 'text' && b.text)
    .map(b => b.text!)
    .join('\n')
}



/**
 * Partition conversation turns into:
 *   - recentExchange: Last user + assistant messages (verbatim)
 *   - plan: Most recent plan-like content (if not already in recent exchange)
 *   - olderTurns: Everything else (for LLM summarization)
 * @dep callers: distill (core/intelligence/context-distiller.ts)
 * @dep calls: has, isPlanContent
 * @dep flows: Project → IsPlanContent (3/4), Project → IsPlanContent (3/4), Project → IsPlanContent (3/4)
 * @dep module: Intelligence
 * @dep risk: MEDIUM | 1 caller, 3 flows, 1 module
 */
function partitionHistory(turns: ConversationTurn[]): {
  recentExchange: string
  plan?: string
  olderTurns: ConversationTurn[]
} {
  // Find last user and assistant turns
  let lastUserIdx = -1
  let lastAssistantIdx = -1
  for (let i = turns.length - 1; i >= 0; i--) {
    if (lastUserIdx < 0 && turns[i].role === 'user') lastUserIdx = i
    if (lastAssistantIdx < 0 && turns[i].role === 'assistant') lastAssistantIdx = i
    if (lastUserIdx >= 0 && lastAssistantIdx >= 0) break
  }

  // Build recent exchange (verbatim — no summarization)
  const recentParts: string[] = []
  if (lastUserIdx >= 0) {
    recentParts.push(`**User:** ${turns[lastUserIdx].text}`)
  }
  if (lastAssistantIdx >= 0) {
    recentParts.push(`**Assistant:** ${turns[lastAssistantIdx].text}`)
  }
  const recentExchange = recentParts.join('\n\n')

  // Scan for plan content (skip messages already in recent exchange)
  const recentIndices = new Set(
    [lastUserIdx, lastAssistantIdx].filter(i => i >= 0),
  )
  let plan: string | undefined
  for (let i = turns.length - 1; i >= 0; i--) {
    if (recentIndices.has(i)) continue
    if (isPlanContent(turns[i].text)) {
      plan = turns[i].text
      break
    }
  }

  // Older turns = everything before the recent exchange pair
  const cutoff = Math.min(
    lastUserIdx >= 0 ? lastUserIdx : turns.length,
    lastAssistantIdx >= 0 ? lastAssistantIdx : turns.length,
  )
  const olderTurns = turns.slice(0, cutoff)

  return { recentExchange, plan, olderTurns }
}

/**
 * Check if text contains plan-like content.
 * Requires both a keyword AND structural elements (numbered list or todos).
 * @dep callers: partitionHistory (core/intelligence/context-distiller.ts)
 * @dep calls: test
 * @dep flows: Project → IsPlanContent (4/4), Project → IsPlanContent (4/4), Project → IsPlanContent (4/4)
 * @dep module: Unknown
 * @dep risk: MEDIUM | 1 caller, 3 flows, 1 module
 */
function isPlanContent(text: string): boolean {
  if (!PLAN_KEYWORDS.test(text)) return false
  return NUMBERED_LIST.test(text) || TODO_PATTERN.test(text)
}



/**
 * Assemble the distilled context block (without the goal).
 * Returns empty string if no context was distilled.
 */
function assembleContextBlock(
  explicitContext: string | undefined,
  sections: DistilledContext['sections'],
  tokenBudget: number,
): string {
  const contextParts: string[] = []

  if (sections.recentExchange) {
    contextParts.push(`### Recent Exchange\n${sections.recentExchange}`)
  }
  if (sections.plan) {
    contextParts.push(`### Active Plan\n${sections.plan}`)
  }
  if (sections.background) {
    contextParts.push(`### Background\n${sections.background}`)
  }
  if (sections.memoryContext) {
    contextParts.push(`### Relevant Memory\n${sections.memoryContext}`)
  }
  if (sections.fileArtifacts) {
    contextParts.push(sections.fileArtifacts)
  }

  // If nothing was distilled and no explicit context, return empty
  if (contextParts.length === 0 && !explicitContext) {
    return ''
  }

  const parts: string[] = []

  if (contextParts.length > 0) {
    parts.push(`## Context from Parent\n\n${contextParts.join('\n\n')}`)
  }

  if (explicitContext) {
    parts.push(`## Additional Context\n\n${explicitContext}`)
  }

  const assembled = parts.join('\n\n')

  // Apply token budget (rough: 1 token ≈ 4 chars)
  const charBudget = tokenBudget * 4
  if (assembled.length > charBudget) {
    return assembled.slice(0, charBudget).trimEnd()
      + '\n\n*[...context truncated due to token budget]*'
  }

  return assembled
}
