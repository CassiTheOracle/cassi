/**
 * DmnObserver — two-layer DMN observer for a single attached session.
 *
 * Layer 1 (Scout): when the observer notices something worth investigating
 * (errors, unfamiliar APIs, decision points, stuck/looping states), it
 * spawns a research scout via the Scout service.  The scout runs as a
 * Hermes subagent with read-only tools and returns structured findings.
 *
 * Layer 2 (Observer): the observer sees the session's recent context
 * window AND the scout's findings.  It synthesizes both — plus
 * cross-session memory — into a DigestSynthesis that the DMN caches
 * and injects into the session via Hermes pre_llm_iteration.
 *
 * Pattern: follows the Constellation corpus-observer-layer and Helix
 * synapse patterns.  Autonomous, ambient observation — the observer
 * decides when to broadcast and what to investigate.
 *
 * Lifecycle: one instance per attached session.  Created by the DMN
 * onFire wiring in boot-intelligence-post.ts.  AGOP scheduling is
 * handled by DmnInstance — this class only handles the fire action.
 */

import { getScout, type ScoutFindings } from '@cassicore/tools'
import type { DigestSynthesis } from './digest-cache.js'
import { priorityToConfidence } from '@cassicore/constellation'
import { BroadcastDedupe } from '@cassicore/constellation'
import type { ILogger } from '@cassicore/foundation'
import type { ThinkingLevel } from '@cassicore/foundation'

export interface DmnObserverLLM {
  complete(opts: {
    prompt: string
    modelTier: string
    maxTokens: number
    timeoutMs: number
    thinking?: ThinkingLevel
  }): Promise<{ content: string; truncated?: boolean }>
}

export interface DmnObserverConfig {
  enabled: boolean
  modelTier: string
  maxTokens: number
  timeoutMs: number
  minBroadcastChars: number
  scoutEnabled: boolean
  /** Max time to wait for a scout investigation (ms). */
  scoutTimeoutMs: number
}

export const DEFAULT_CONFIG: DmnObserverConfig = {
  enabled: true,
  modelTier: 'sonnet',
  maxTokens: 1_200,
  timeoutMs: 45_000,
  minBroadcastChars: 40,
  scoutEnabled: true,
  scoutTimeoutMs: 90_000,
}

export interface DmnObserverOpts {
  sessionId: string
  logger: ILogger
  llm: DmnObserverLLM
  config?: Partial<DmnObserverConfig>
  crossSessionContext?: (query: string) => Promise<string>
  recallMemory?: (query: string) => Promise<string>
  eventBus?: { emit: (event: unknown) => void }
  persistObservation?: (content: string, metadata: Record<string, unknown>) => void
}

interface ParsedObservation {
  content: string
  priority: 'ambient' | 'normal' | 'urgent'
}

export class DmnObserver {
  readonly sessionId: string
  private logger: ILogger
  private llm: DmnObserverLLM
  private config: DmnObserverConfig
  private crossSessionContext?: (query: string) => Promise<string>
  private recallMemory?: (query: string) => Promise<string>
  private eventBus?: { emit: (event: unknown) => void }
  private persistObservation?: (content: string, metadata: Record<string, unknown>) => void
  private dedupe = new BroadcastDedupe({ ttlMs: 180_000, similarityThreshold: 0.80 })

  constructor(opts: DmnObserverOpts) {
    this.sessionId = opts.sessionId
    this.logger = opts.logger.child?.(`dmn-observer:${opts.sessionId.slice(0, 8)}`) ?? opts.logger
    this.llm = opts.llm
    this.config = { ...DEFAULT_CONFIG, ...opts.config }
    this.crossSessionContext = opts.crossSessionContext
    this.recallMemory = opts.recallMemory
    this.eventBus = opts.eventBus
    this.persistObservation = opts.persistObservation
  }

  /**
   * Fire the observation cycle.  Called by DmnInstance when the AGOP
   * scheduler triggers.  The observation prompt is built by the caller
   * (boot-intelligence-post) and passed directly — no stale closure.
   *
   * Returns a DigestSynthesis for caching, or null when the observer
   * has nothing to say.
   */
  async fire(reason: string, observationPrompt: string): Promise<DigestSynthesis | null> {
    if (observationPrompt.length < 50) return null

    // Layer 1: spawn research scout if something looks interesting
    let scoutFindings: ScoutFindings | null = null
    if (this.config.scoutEnabled) {
      const researchQuestion = this.buildResearchQuestion(observationPrompt)
      if (researchQuestion) {
        try {
          const scout = getScout()
          scoutFindings = await scout.investigate({
            topic: researchQuestion,
            context: observationPrompt.slice(0, 2000),
            sessionId: this.sessionId,
            timeoutMs: this.config.scoutTimeoutMs,
          })
          this.logger.info('DMN scout investigation complete', {
            topic: researchQuestion.slice(0, 80),
            confidence: scoutFindings.confidence,
          })
        } catch (err) {
          this.logger.debug('DMN scout investigation failed (non-fatal)', { error: String(err) })
        }
      }
    }

    // Gather memory context
    const memoryQuery = [this.sessionId, observationPrompt.slice(0, 500)]
    if (scoutFindings) memoryQuery.push(scoutFindings.summary.slice(0, 300))
    const memoryContext = (await this.recallMemory?.(memoryQuery.join('\n'))) ?? ''
    const crossSession = (await this.crossSessionContext?.(observationPrompt.slice(0, 1_000))) ?? ''

    // Layer 2: synthesize observation
    const observerPrompt = this.buildObserverPrompt(
      observationPrompt,
      scoutFindings,
      memoryContext,
      crossSession,
    )

    let response: { content: string; truncated?: boolean }
    try {
      response = await Promise.race([
        this.llm.complete({
          prompt: observerPrompt,
          modelTier: this.config.modelTier,
          maxTokens: this.config.maxTokens,
          timeoutMs: this.config.timeoutMs,
          thinking: 'none',
        }),
        new Promise<never>((_, reject) =>
          setTimeout(() => reject(new Error('Observer LLM call timed out')), this.config.timeoutMs + 5_000),
        ),
      ])
    } catch (err) {
      this.logger.warn('Observer LLM call failed', { error: String(err) })
      return null
    }

    const parsed = this.parseResponse(response.content)
    if (!parsed) return null

    if (parsed.content.length < this.config.minBroadcastChars) return null

    const dedupeKey = `dmn:${this.sessionId}`
    const dedupeResult = this.dedupe.check(dedupeKey, parsed.content)
    if (dedupeResult.duplicate) return null
    this.dedupe.remember(dedupeKey, parsed.content)

    const confidence = priorityToConfidence(parsed.priority)

    this.persistObservation?.(parsed.content, {
      layer: 'dmn-observer',
      sessionId: this.sessionId,
      priority: parsed.priority,
      tags: ['dmn-observer', `session:${this.sessionId}`],
    })

    try {
      this.eventBus?.emit({
        type: 'dmn:observer:broadcast',
        sessionId: this.sessionId,
        preview: parsed.content.slice(0, 300),
        priority: parsed.priority,
        confidence,
        timestamp: Date.now(),
      })
    } catch { /* fire-and-forget */ }

    this.logger.info('DMN observation broadcast', {
      preview: parsed.content.slice(0, 160),
      priority: parsed.priority,
      hadScout: scoutFindings !== null,
    })

    return {
      hasSignal: true,
      signal: {
        type: 'ambient',
        content: parsed.content,
        confidence,
        urgency: parsed.priority,
      },
      completedAt: Date.now(),
      halfLifeMs: 5 * 60 * 1000,
    }
  }

  /**
   * Decide whether to spawn a research scout based on what the session
   * context contains.  Returns a research question string, or null
   * if nothing looks investigation-worthy.
   */
  private buildResearchQuestion(prompt: string): string | null {
    const lower = prompt.toLowerCase()

    // Errors and failures
    if (lower.includes('error') || lower.includes('fail') || lower.includes('exception')) {
      const errorIdx = Math.max(
        lower.indexOf('error'),
        lower.indexOf('fail'),
        lower.indexOf('exception'),
      )
      const snippet = prompt.slice(Math.max(0, errorIdx - 30), errorIdx + 150)
      return `Investigate this error: ${snippet.slice(0, 200)}`
    }

    // Stuck or looping states
    if (lower.includes('stuck') || lower.includes('loop') || lower.includes('repeating')) {
      return `The session appears stuck or looping. Research what might help: ${prompt.slice(0, 200)}`
    }

    // Unfamiliar or unknown territory
    if (lower.includes('unfamiliar') || lower.includes('unknown') || lower.includes('unsure')) {
      return `Research: ${prompt.slice(0, 200)}`
    }

    return null
  }

  private buildObserverPrompt(
    observationPrompt: string,
    scoutFindings: ScoutFindings | null,
    memoryContext: string,
    crossSessionContext: string,
  ): string {
    const parts = [
      `<identity>`,
      `I am the DMN observer for session ${this.sessionId}. I watch the session's recent activity and notice patterns, errors, decisions, and opportunities. I speak only when I have a useful observation — otherwise I rest.`,
      `</identity>`,
      '',
      `<session_context>`,
      observationPrompt.slice(0, 4_000),
      `</session_context>`,
    ]

    if (scoutFindings && scoutFindings.confidence >= 0.3) {
      parts.push(
        '',
        `<scout_findings>`,
        `Summary: ${scoutFindings.summary.slice(0, 1_000)}`,
        scoutFindings.sources.length > 0
          ? `Sources:\n${scoutFindings.sources.map(s => `- ${s}`).join('\n')}`
          : '',
        `Confidence: ${scoutFindings.confidence.toFixed(2)}`,
        `</scout_findings>`,
      )
    }

    if (memoryContext) {
      parts.push('', `<relevant_memory>`, memoryContext.slice(0, 1_500), `</relevant_memory>`)
    }

    if (crossSessionContext) {
      parts.push('', `<cross_session>`, crossSessionContext.slice(0, 1_500), `</cross_session>`)
    }

    parts.push(
      '',
      `<instructions>`,
      `Look at the session context and scout findings. Speak only if there is a useful observation: a pattern, an error trend, a decision that needs attention, a resource that would help, or a strategic insight.`,
      `If nothing useful to say, respond with REST.`,
      ``,
      `Respond in exactly one of these forms:`,
      ``,
      `REST: <brief reason>`,
      ``,
      `or`,
      ``,
      `PRIORITY: <ambient|normal|urgent>`,
      `BROADCAST: <1-4 sentences for the session>`,
      `</instructions>`,
    )

    return parts.join('\n')
  }

  private parseResponse(content: string): ParsedObservation | null {
    if (/^\s*REST\s*:/i.test(content)) return null

    const broadcastMatch = content.match(/BROADCAST:\s*([\s\S]+)$/i)
    const broadcast = (broadcastMatch?.[1] ?? content).trim()
    if (!broadcast) return null

    const priorityMatch = content.match(/PRIORITY:\s*(ambient|normal|urgent)/i)
    const priority = (priorityMatch?.[1]?.toLowerCase() as 'ambient' | 'normal' | 'urgent') ?? 'ambient'

    return { content: broadcast, priority }
  }
}
