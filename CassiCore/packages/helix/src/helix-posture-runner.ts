/**
 * HelixPostureRunner — Posture execution thread for the Helix agent pattern.
 *
 * Extends BasePostureRunner to add dual-channel routing:
 * - Unity: Full tool access, posts work units to WorkStream, receives nudges
 * - Yang/Yin: Read-only tools, DialecticChannel (findings/challenges/concessions)
 *   + WorkStream (read work units, send nudges to Unity)
 *
 * The double-helix metaphor: Unity moves forward through the problem space.
 * Yang and Yin orbit it, their dialectic interaction stabilizing the output.
 */

import type { ILogger, IEventBus } from '../../../types/interfaces.js'
import type { Message, ContentBlock, CompletionOpts } from '../../../types/runtime.js'
import type { ModelHandle } from '../../model-pool/types.js'
import type { IModelDirective, ModelConfig } from '../../../types/model-routing.js'
import type { ToolExecutor } from '../../tools/executor.js'
import type { ToolRegistry } from '../../tools/registry.js'
import type { PlanHandler } from '../flux-team/plan-handler.js'
import type { Blackboard } from '../flux-team/blackboard.js'
import { WorkStream } from '../dyad/work-stream.js'
import type { UnityStatusThresholds } from '../dyad/work-stream.js'
import type { DialecticChannel } from '../lumen/dialectic-channel.js'
import { HelixWorkStream } from './helix-coordinator.js'
import type { HelixStore } from './helix-store.js'
import type { WorkUnit, FileChange, ToolCallSummary, ToolResultSummary } from '../dyad/types.js'
import type { Posture as LumenPostureType } from '../lumen/dialectic-channel.js'
import type { InferenceResult, ParsedToolCall } from '../../../types/cassi-agent.js'
import type { HelixRole, HelixPosture, HelixPostureResult } from './types.js'
import type { HelixBrainstem } from './brainstem.js'
import type { PendingGuidance } from './brainstem-types.js'
import { HelixResearcher } from './helix-researcher.js'
import {
  isHelixMetaTool,
  getHelixToolSchemas,
  UNITY_TOOL_NAMES,
  REVIEWER_TOOL_NAMES,
} from './helix-tools.js'
import {
  handleBlackboardToolCall,
  isBlackboardMetaTool,
  getBlackboardToolSchemas,
} from '../flux-team/blackboard-tools.js'
import {
  BasePostureRunner,
  isReadOnlyTool,
  isMemoryTool,
  findLastIndex,
} from '../cassi-agent/base-posture-runner.js'
import {
  getCodeConsolidatedToolSchema,
  getFilesystemConsolidatedToolSchema,
  WEB_CONSOLIDATED_TOOL,
  BROWSER_CONSOLIDATED_TOOL,
  executeCodeConsolidatedTool,
  executeFilesystemConsolidatedTool,
  executeBrowserConsolidatedTool,
  executeWebConsolidatedTool,
} from '../../../mcp/gateway/index.js'


// ─── Lazy-loaded optional tools ────────────────────────────────────────────

let isPlanMetaTool: (name: string) => boolean = () => false
let getPlanToolSchemas: (role: any) => any[] = () => []
let REPORT_TOOLS: any[] = []
let REPORT_TOOL_NAMES: Set<string> = new Set()
let _toolsInitPromise: Promise<void> | null = null

function initializeOptionalTools(): Promise<void> {
  if (_toolsInitPromise) return _toolsInitPromise
  _toolsInitPromise = (async () => {
    try {
      const planMod = await import('../lumen/plan-tools.js')
      isPlanMetaTool = planMod.isPlanMetaTool
      getPlanToolSchemas = planMod.getPlanToolSchemas
    } catch { /* plan tools not available */ }

    try {
      const reportMod = await import('../lumen/report-tools.js')
      REPORT_TOOLS = reportMod.REPORT_TOOLS ?? []
      REPORT_TOOL_NAMES = reportMod.REPORT_TOOL_NAMES ?? new Set()
    } catch { /* report tools not available */ }
  })().catch((err) => {
    _toolsInitPromise = null
    throw err
  })
  return _toolsInitPromise
}


// ─── Autonomous Posture Tool Blocklist ─────────────────────────────────────

/**
 * Tools that are useless or harmful to autonomous Helix postures.
 * These cause exploration loops (Serena activation), waste iterations,
 * or require interactive flows that autonomous agents cannot complete.
 */
const BLOCKED_TOOLS_FOR_AUTONOMOUS = new Set([
  // Serena activation tools — require interactive onboarding flow
  'serena_check_onboarding_performed',
  'serena_onboarding',
  'serena_initial_instructions',
  'serena_open_dashboard',
  // Playwright browser interaction — require interactive navigation
  'playwright_browser_install',
])

const EXTERNAL_MCP_PREFIXES = ['serena_', 'gitnexus_', 'playwright_browser_', 'duckduckgo_']
const EXTERNAL_MCP_SERVER_PREFIXES = ['serena__', 'gitnexus__', 'playwright__', 'playwright_browser__', 'duckduckgo__']
const CONSOLIDATED_GATEWAY_TOOL_NAMES = new Set(['code', 'file', 'web', 'browser'])

function toCanonicalExternalToolName(name: string): string {
  if (!name.includes('__')) return name
  const [serverId, toolName] = name.split('__', 2)
  if (!toolName) return name
  if (serverId === 'playwright' || serverId === 'playwright_browser') {
    return `playwright_browser_${toolName}`
  }
  return `${serverId}_${toolName}`
}

function isBlockedForAutonomousPostures(name: string): boolean {
  return BLOCKED_TOOLS_FOR_AUTONOMOUS.has(toCanonicalExternalToolName(name))
}

function isExternalMcpTool(name: string): boolean {
  const canonical = toCanonicalExternalToolName(name)
  return EXTERNAL_MCP_SERVER_PREFIXES.some(prefix => name.startsWith(prefix))
    || EXTERNAL_MCP_PREFIXES.some(prefix => canonical.startsWith(prefix))
}


// ─── Constants ─────────────────────────────────────────────────────────────

const DEFAULT_SESSION_ID = 'helix-session'
const REVIEWER_WORK_UNIT_TIMEOUT_MS = 3_000
const REVIEWER_DIALECTIC_BURST_LIMIT = 3
const REVIEWER_IDLE_DELAY_MS = 1_000


// ─── HelixPostureRunner ────────────────────────────────────────────────────

/**
 * Callback for spawning a research agent from the Mentor.
 * Fires asynchronously — results are posted to the Blackboard.
 */
export type ResearchSpawner = (opts: {
  query: string
  label: string
  context?: string
  priority?: 'low' | 'medium' | 'high'
  sessionId: string
}) => Promise<{ requestId: string; droneId: string }>

export interface HelixPostureRunnerOpts {
  role: HelixRole
  posture: HelixPosture
  handle: ModelHandle
  workStream: WorkStream
  /** DialecticChannel — required for Yang/Yin, optional for Unity */
  dialecticChannel?: DialecticChannel
  logger: ILogger
  sessionId?: string
  toolExecutor?: ToolExecutor
  toolRegistry?: ToolRegistry
  store?: HelixStore
  planHandler?: PlanHandler
  blackboard?: Blackboard
  eventBus?: IEventBus
  onActivity?: () => void
  modelDirective?: IModelDirective
  handleFactory?: (config: ModelConfig) => Promise<ModelHandle>
  jobId?: string
  postureSlot?: string
  moduleDebugSessionId?: string
  contextBudgetCoordinator?: import('../cassi-agent/context-budget-coordinator.js').ContextBudgetCoordinator
  /** Optional callback to spawn a research drone when the Mentor dispatches research */
  researchSpawner?: ResearchSpawner
  /** Configurable thresholds for UnityStatus proactive signals to reviewers */
  unityStatusThresholds?: UnityStatusThresholds
  /** Brainstem — cognitive organizer (replaces Mentor) */
  brainstem?: HelixBrainstem
  /** Callback fired when Unity posts a work unit */
  onWorkUnit?: (wu: import('../dyad/types.js').WorkUnit, iteration: number) => void
  /** Callback fired during streaming with real-time token activity */
  onStreamActivity?: (event: StreamActivityEvent) => void
}

/** Real-time token stream event — emitted during inference for Brainstem/Corpus visibility */
export interface StreamActivityEvent {
  /** Which posture is streaming */
  posture: HelixRole
  /** Tokens generated so far in this inference call */
  tokensSoFar: number
  /** Whether the LLM is currently producing text (vs tool calls) */
  isReasoning: boolean
  /** Last ~200 chars of text for content-aware assessment */
  textSnippet: string
  /** Whether tool calls have been seen in this inference */
  hasToolUse: boolean
  /** Timestamp */
  timestamp: number
}


export class HelixPostureRunner extends BasePostureRunner<HelixPosture> {
  private readonly role: HelixRole
  private readonly workStream: WorkStream
  private readonly dialecticChannel?: DialecticChannel
  private readonly researchSpawner?: ResearchSpawner
  private readonly unityStatusThresholds?: UnityStatusThresholds
  private readonly brainstem?: HelixBrainstem
  private readonly onWorkUnit?: (wu: WorkUnit, iteration: number) => void
  private readonly onStreamActivity?: (event: StreamActivityEvent) => void

  // Typed store
  protected declare store?: HelixStore

  // Review tracking
  private reviewedWorkUnitIds = new Set<string>()
  private dialecticCursor = 0
  private nudgesSent = 0
  private findingsShared = 0
  private challengesMade = 0
  private concessionsMade = 0
  private workUnitsProduced = 0

  // Synapse guidance tracking — latest guidance is appended to subsequent tool outputs
  private lastSynapseGuidance?: string

  // Mentor synthesis tracking — populated by mentor_synthesize handler
  private mentorSynthesis?: {
    recommendation: string
    confidence: number
    keyFindings: string[]
    remainingRisks: string[]
    synthesis: string
  }


  constructor(opts: HelixPostureRunnerOpts) {
    super({
      posture: opts.posture,
      handle: opts.handle,
      logger: opts.logger.child(`helix-agent:${opts.role}`),
      defaultSessionId: DEFAULT_SESSION_ID,
      sessionId: opts.sessionId,
      toolExecutor: opts.toolExecutor,
      toolRegistry: opts.toolRegistry,
      store: opts.store,
      planHandler: opts.planHandler,
      blackboard: opts.blackboard,
      onActivity: opts.onActivity,
      modelDirective: opts.modelDirective,
      handleFactory: opts.handleFactory,
      eventBus: opts.eventBus,
      jobId: opts.jobId,
      postureSlot: opts.postureSlot,
      moduleDebugSessionId: opts.moduleDebugSessionId,
      contextBudgetCoordinator: opts.contextBudgetCoordinator,
    })
    this.role = opts.role
    this.workStream = opts.workStream
    this.dialecticChannel = opts.dialecticChannel
    this.researchSpawner = opts.researchSpawner
    this.unityStatusThresholds = opts.unityStatusThresholds
    this.brainstem = opts.brainstem
    this.onWorkUnit = opts.onWorkUnit
    this.onStreamActivity = opts.onStreamActivity
    this.store = opts.store
  }


  // ── Abstract method implementations ─────────────────────────────────

  protected getAgentLabel(): string { return this.role }
  protected getSourceLabel(): string { return `helix:${this.role}` }
  protected getTriggerLabel(): string { return 'helix' }

  /**
   * Stream chunk hook — forward token stream events to the Brainstem/Corpus
   * via the onStreamActivity callback. This gives real-time visibility into
   * what the LLM is producing, not just tool call results.
   */
  protected override onStreamChunk(tokensSoFar: number, textAccumulated: string, hasToolUse: boolean): void {
    if (!this.onStreamActivity) return

    const snippet = textAccumulated.length > 200
      ? textAccumulated.slice(-200)
      : textAccumulated

    this.onStreamActivity({
      posture: this.role,
      tokensSoFar,
      isReasoning: !hasToolUse && textAccumulated.length > 0,
      textSnippet: snippet,
      hasToolUse,
      timestamp: Date.now(),
    })
  }


  // ── Unity Run Loop ──────────────────────────────────────────────────

  /**
   * Run as Unity — the worker posture.
   * Continuous tool loop: inference → tool calls → work unit posting → nudge processing.
   */
  async runAsWorker(goal: string, context?: string): Promise<HelixPostureResult> {
    const startTime = Date.now()
    this.logger.info('Unity starting as worker', { goal, maxIterations: this.posture.maxIterations })

    try {
      await initializeOptionalTools()
      this.messages = this.buildInitialMessages(goal, context, 'unity')
      const tools = this.buildToolSchemas('unity')

      while (!this.concluded && !this.cancelled) {
        this.iterationCount++
        if (this.iterationCount > this.maxIterations) {
          this.logger.warn('Unity hit max iterations', { maxIterations: this.maxIterations })
          break
        }

        // Backpressure — wait if reviewers are falling behind
        if (this.workStream.shouldApplyBackpressure()) {
          this.logger.debug('Unity backpressure — waiting for reviewers to catch up')
          await this.workStream.awaitBackpressureRelief()
        }

        // Context pressure management
        this.manageContextPressure()

        // Stream inference
        const result = await this.streamInference(tools)
        this.tokensUsed += result.tokensUsed
        // WorkStream only tracks DyadRole (yang|yin|apex|unity) — mentor is tracked via posture result
        if (this.role !== 'mentor') {
           // WorkStream only tracks DyadRole (yang|yin|apex|unity) — mentor tracked via posture result
           if ((this.role as string) !== 'mentor') {
             this.workStream.recordIteration(this.role as any, result.tokensUsed)
           }
        }
        this.onActivity?.()

        if (!result.hasToolUse) {
          // Capture text-only output as a "reasoning" work unit so the Brainstem
          // can see what the LLM is thinking, not just what tools it uses.
          const textContent = result.contentBlocks
            .filter((b: any) => b.type === 'text')
            .map((b: any) => b.text)
            .join('\n')
          if (textContent.length > 50) { // Only capture substantial text
            const reasoningUnit = this.captureReasoningWorkUnit(textContent)
            this.workStream.postWorkUnit(reasoningUnit as any)
            this.onWorkUnit?.(reasoningUnit as any, this.iterationCount)
          }

          if (!this.concluded) {
            this.messages.push({
              role: 'user',
              content: 'You must use your tools to do work. Call signal_done when your work is complete.',
            })
          }
          continue
        }

        // Extract and process tool calls
        const toolCalls = this.extractToolCalls(result.contentBlocks)
        if (toolCalls.length === 0) continue

        const toolResults = await this.processToolCalls(toolCalls)
        this.onActivity?.()

        // Auto-capture work unit from this iteration
        const workUnit = this.captureWorkUnit(result, toolCalls, toolResults)
        this.workStream.postWorkUnit(workUnit as any)
        this.workUnitsProduced++
        this.onWorkUnit?.(workUnit as any, this.iterationCount)

        // Inject nudges, Brainstem guidance, and Synapse guidance into tool results
        const enrichedResults = this.injectBrainstemGuidance(
          this.injectSynapseGuidance(
            this.injectNudgeMessages(toolResults)
          )
        )

        // Check for high-severity nudges — inject as blocking user message
        const highNudge = this.workStream.getNextHighNudge()
        if (highNudge) {
          this.messages.push({ role: 'assistant', content: result.contentBlocks })
          this.messages.push({ role: 'user', content: enrichedResults })
          this.messages.push({
            role: 'user',
            content: `⚠️ HIGH-SEVERITY REVIEW NUDGE from ${highNudge.from}:\n\n${highNudge.content}\n\n` +
              `You MUST call acknowledge_nudge with nudge_id="${highNudge.id}" before continuing your work.`,
          })
          continue
        }

        this.messages.push({ role: 'assistant', content: result.contentBlocks })
        this.messages.push({ role: 'user', content: enrichedResults })
      }

      this.workStream.signalWorkerDone()
      return this.buildPostureResult(startTime)
    } catch (err) {
      this.workStream.signalWorkerDone()
      return this.buildErrorResult(startTime, err)
    }
  }


  // ── Reviewer Run Loop (Yang/Yin) ────────────────────────────────────

  /**
   * Run as a reviewer (Yang or Yin).
   * Two-mode async loop:
   *   Primary: drain work units from WorkStream, investigate, post findings/nudges
   *   Secondary: engage in dialectic with the other reviewer when idle
   */
  async runAsReviewer(goal: string, context?: string): Promise<HelixPostureResult> {
    const startTime = Date.now()
    this.logger.info(`${this.role} starting as reviewer`, { goal, maxIterations: this.posture.maxIterations })

    try {
      await initializeOptionalTools()
      this.messages = this.buildInitialMessages(goal, context, this.role)
      const tools = this.buildToolSchemas(this.role)

      // Brief delay to let Unity start producing work units.
      // Don't await waitForYangDone() — that blocks until Unity FINISHES,
      // preventing concurrent review. The loop's nextWorkUnit() call
      // already blocks until a work unit is posted or Unity signals done.
      await new Promise(resolve => setTimeout(resolve, 2_000))

      while (!this.concluded && !this.cancelled) {
        this.iterationCount++
        if (this.iterationCount > this.maxIterations) {
          this.logger.warn(`${this.role} hit max iterations`, { maxIterations: this.maxIterations })
          break
        }

        // Check if Unity is done and we've reviewed everything.
        // Helix runs TWO concurrent reviewers sharing one WorkStream queue.
        // nextWorkUnit() is destructive (shift), so only one reviewer gets each
        // work unit from the queue. The other reviewer still reviews via dialectic
        // messages and UnityStatus injection. Check both local reviewed set AND
        // the WorkStream's global reviewed status to avoid the second reviewer
        // looping forever waiting for a work unit it will never dequeue.
        if (this.workStream.isWorkerDone()) {
          const allWUs = this.workStream.getAllWorkUnits()

          // Native coordinator: use per-reviewer broadcast cursors for clean termination.
          // With broadcast semantics, both reviewers can observe work units. But due to
          // timing (Unity posts faster than reviewers drain), reviewers may not have
          // consumed all WUs through nextWorkUnitForReviewer(). That's OK — they also
          // observe work via UnityStatus and dialectic messages. Once Unity is done and
          // the reviewer has had at least 2 iterations to contribute, it's safe to conclude.
          if (this.workStream instanceof HelixWorkStream) {
            const seenAll = this.workStream.hasReviewerSeenAll(this.role)
            if (seenAll && allWUs.length > 0) {
              this.workStream.signalReviewerReady(this.role)
              this.logger.info(`${this.role} — Unity done, all ${allWUs.length} work units observed via broadcast, concluding`)
              break
            }
            if (allWUs.length === 0) {
              this.logger.info(`${this.role} — Unity done with no work units, concluding`)
              break
            }
            // Even if not all WUs seen via broadcast, conclude after contributing enough.
            // Reviewers also see work via UnityStatus injection and dialectic messages.
            if (this.iterationCount >= 3) {
              this.workStream.signalReviewerReady(this.role)
              const cursor = this.workStream.getReviewerProgress(this.role)
              this.logger.info(`${this.role} — Unity done, concluding after ${this.iterationCount} iterations (broadcast: ${cursor.cursor}/${cursor.total} WUs)`)
              break
            }
            continue
          }

          // Legacy fallback: check local + global reviewed sets
          const allReviewedLocally = allWUs.length > 0 && allWUs.every(wu => this.reviewedWorkUnitIds.has(wu.id))
          const allReviewedGlobally = allWUs.length > 0 && allWUs.every(wu =>
            this.reviewedWorkUnitIds.has(wu.id) || this.workStream.isWorkUnitReviewed(wu.id),
          )
          if (allReviewedLocally) {
            this.logger.info(`${this.role} — Unity is done and all ${allWUs.length} work units reviewed locally, concluding`)
            break
          }
          if (allReviewedGlobally && this.iterationCount > 1) {
            this.logger.info(`${this.role} — Unity is done, all ${allWUs.length} work units reviewed globally, concluding after ${this.iterationCount} iterations`)
            break
          }
          if (allWUs.length === 0) {
            this.logger.info(`${this.role} — Unity is done with no work units, concluding`)
            break
          }
        }

        // Primary mode: drain next work unit
        // Use broadcast read when HelixWorkStream is available (each reviewer
        // sees ALL work units via per-reviewer cursors). Falls back to legacy
        // destructive nextWorkUnit() for backward compat.
        const workUnit = await Promise.race([
          (this.workStream instanceof HelixWorkStream
            ? this.workStream.nextWorkUnitForReviewer(this.role, REVIEWER_WORK_UNIT_TIMEOUT_MS)
            : this.workStream.nextWorkUnit(REVIEWER_WORK_UNIT_TIMEOUT_MS)
          ).catch(err => {
            this.logger.debug(`${this.role} — nextWorkUnit failed`, { error: String(err) })
            return null
          }),
          new Promise<null>(resolve => {
            if (this.cancelled) resolve(null)
            setTimeout(() => resolve(null), REVIEWER_WORK_UNIT_TIMEOUT_MS)
          }),
        ])

        if (workUnit && !this.reviewedWorkUnitIds.has(workUnit.id)) {
          // Review this work unit
          this.reviewedWorkUnitIds.add(workUnit.id)
          this.workStream.markWorkUnitReviewed(workUnit.id)

          // Inject work unit as context for the reviewer to investigate
          this.messages.push({
            role: 'user',
            content: this.formatWorkUnitForReview(workUnit),
          })
        } else {
          // Secondary mode: process dialectic messages
          if (this.dialecticChannel) {
            const injected = this.injectDialecticMessages()
            if (!injected) {
              // Fallback: no work unit and no dialectic — check UnityStatus as message injection
              const injectedStatus = this.injectUnityStatusAsMessage()
              if (!injectedStatus) {
                // Nothing to process — brief idle delay
                await new Promise(resolve => setTimeout(resolve, REVIEWER_IDLE_DELAY_MS))
                continue
              }
              // UnityStatus was injected as message — continue to inference so reviewer can act on it
            }
          } else {
            // Fallback: no dialectic channel — check UnityStatus as message injection
            const injectedStatus = this.injectUnityStatusAsMessage()
            if (!injectedStatus) {
              await new Promise(resolve => setTimeout(resolve, REVIEWER_IDLE_DELAY_MS))
              continue
            }
          }
        }

        // Context pressure management
        this.manageContextPressure()

        // Stream inference — reviewer investigates and decides on findings/nudges
        const result = await this.streamInference(tools)
        this.tokensUsed += result.tokensUsed
        // WorkStream only tracks DyadRole (yang|yin|apex|unity) — mentor is tracked via posture result
        if (this.role !== 'mentor') {
           // WorkStream only tracks DyadRole (yang|yin|apex|unity) — mentor tracked via posture result
           if ((this.role as string) !== 'mentor') {
             this.workStream.recordIteration(this.role as any, result.tokensUsed)
           }
        }
        this.onActivity?.()

        if (!result.hasToolUse && !this.concluded) {
          // No tool use — nudge towards action
          this.messages.push({
            role: 'user',
            content: 'You must use your tools to investigate and your meta-tools to share findings. ' +
              'Call signal_conclusion when you have completed your review.',
          })
          continue
        }

        // Extract and process tool calls
        const toolCalls = this.extractToolCalls(result.contentBlocks)
        if (toolCalls.length === 0) continue

        const toolResults = await this.processToolCalls(toolCalls)
        this.onActivity?.()

        // Inject dialectic messages into tool results
        const enrichedResults = this.injectDialecticIntoResults(toolResults)

        // Primary UnityStatus injection — piggyback on existing tool results (zero extra LLM calls)
        const statusResults = this.injectUnityStatusIntoResults(enrichedResults)

        // Inject Synapse guidance from previous collect_thoughts calls
        const withSynapse = this.injectSynapseGuidance(statusResults)

        // Inject Brainstem guidance (primary cognitive organizer)
        const finalResults = this.injectBrainstemGuidance(withSynapse)

        this.messages.push({ role: 'assistant', content: result.contentBlocks })
        this.messages.push({ role: 'user', content: finalResults })
      }

      return this.buildPostureResult(startTime)
    } catch (err) {
      return this.buildErrorResult(startTime, err)
    }
  }

  /**
   * Run as the Mentor — a meta-moderator loop, not a reviewer loop.
   *
   * Mentor does not drain work units directly. Instead it watches:
   * - DialecticChannel injections from Yang/Yin/Executive
   * - Blackboard state and review_progress
   * - Optional research dispatch results
   *
   * It intervenes only when there is something meaningful to steer, flag,
   * force toward conclusion, or synthesize.
   */
  async runAsMentor(goal: string, context?: string): Promise<HelixPostureResult> {
    const startTime = Date.now()
    this.logger.info('mentor starting as moderator', { goal, maxIterations: this.posture.maxIterations })

    try {
      await initializeOptionalTools()
      this.messages = this.buildInitialMessages(goal, context, 'mentor')
      const tools = this.buildToolSchemas('mentor')

      await new Promise(resolve => setTimeout(resolve, 3_000))

      while (!this.concluded && !this.cancelled) {
        this.iterationCount++
        if (this.iterationCount > this.maxIterations) {
          this.logger.warn('mentor hit max iterations', { maxIterations: this.maxIterations })
          break
        }

        const unityDone = this.workStream.isWorkerDone()
        const allWUs = this.workStream.getAllWorkUnits()
        const dialecticInjected = this.injectDialecticMessages()

        if (!dialecticInjected) {
          const progress = this.handleReviewProgress()
          this.messages.push({
            role: 'user',
            content:
              `--- Helix State ---\n\n${progress}\n\n---\n\n` +
              `You are the Mentor. Observe the state and intervene only if you can improve the quality of the session. ` +
              `If there is nothing meaningful to do yet, wait.`,
          })
        }

        if (unityDone && allWUs.length === 0) {
          this.logger.info('mentor — Unity finished without work units, concluding')
          break
        }

        this.manageContextPressure()

        const result = await this.streamInference(tools)
        this.tokensUsed += result.tokensUsed
        this.onActivity?.()

        if (!result.hasToolUse && !this.concluded) {
          if (unityDone) {
            this.messages.push({
              role: 'user',
              content: 'Unity appears done. If you have enough information, call mentor_synthesize now.',
            })
          } else {
            await new Promise(resolve => setTimeout(resolve, REVIEWER_IDLE_DELAY_MS))
          }
          continue
        }

        const toolCalls = this.extractToolCalls(result.contentBlocks)
        if (toolCalls.length === 0) continue

        const toolResults = await this.processToolCalls(toolCalls)
        this.onActivity?.()

        const enrichedResults = this.injectSynapseGuidance(
          this.injectDialecticIntoResults(toolResults)
        )

        this.messages.push({ role: 'assistant', content: result.contentBlocks })
        this.messages.push({ role: 'user', content: enrichedResults })
      }

      return this.buildPostureResult(startTime)
    } catch (err) {
      return this.buildErrorResult(startTime, err)
    }
  }


  // ── Tool Processing ─────────────────────────────────────────────────

  private async processToolCalls(toolCalls: ParsedToolCall[]): Promise<ContentBlock[]> {
    const results: ContentBlock[] = []

    // Classify each tool call
    const metaCalls: ParsedToolCall[] = []
    const blackboardCalls: ParsedToolCall[] = []
    const planCalls: ParsedToolCall[] = []
    const reportCalls: ParsedToolCall[] = []
    const executableCalls: ParsedToolCall[] = []
    const blockedCalls: ParsedToolCall[] = []

    for (const tc of toolCalls) {
      if (isHelixMetaTool(tc.name)) {
        metaCalls.push(tc)
      } else if (this.blackboard && isBlackboardMetaTool(tc.name)) {
        blackboardCalls.push(tc)
      } else if (this.planHandler && isPlanMetaTool(tc.name)) {
        planCalls.push(tc)
      } else if (REPORT_TOOL_NAMES.has(tc.name)) {
        reportCalls.push(tc)
      } else if (this.isToolAllowed(tc.name)) {
        executableCalls.push(tc)
      } else {
        blockedCalls.push(tc)
      }
    }

    // Process meta-tools
    for (const tc of metaCalls) {
      this.toolCallCount++
      const startMs = Date.now()
      const result = this.handleMetaTool(tc.name, tc.input)
      results.push({ type: 'tool_result', tool_use_id: tc.id, content: result })
      this.store?.saveToolCall(
        this.sessionId, this.role, tc.name, tc.id, true,
        tc.input, result, false, Date.now() - startMs, this.iterationCount,
      )
    }

    // Process blackboard calls (shared helper from base)
    if (blackboardCalls.length > 0) {
      results.push(...this.processBlackboardCalls(blackboardCalls))
    }

    // Process plan calls (shared helper from base)
    if (planCalls.length > 0) {
      results.push(...this.processPlanCalls(planCalls))
    }

    // Process report tools
    for (const tc of reportCalls) {
      this.toolCallCount++
      const startMs = Date.now()
      const result = this.handleReportTool(tc.name, tc.input)
      results.push({ type: 'tool_result', tool_use_id: tc.id, content: result })
      this.store?.saveToolCall(
        this.sessionId, this.role, tc.name, tc.id, true,
        tc.input, result, false, Date.now() - startMs, this.iterationCount,
      )
    }

    // Inject posture_energy into collect_thoughts calls for Synapse guidance
    // When running under Constellation (brainstem present), cap estimated_steps to reduce
    // provider contention — the Brainstem already provides cognitive organization.
    for (const tc of executableCalls) {
      if (tc.name === 'collect_thoughts') {
        if (!tc.input.posture_energy) {
          const energyMap: Record<string, string> = {
            unity: 'unifying',
            yang: 'expansive',
            yin: 'contractive',
          }
          tc.input.posture_energy = energyMap[this.role] ?? 'neutral'
        }
        // Cap thinking steps in constellation mode to prevent provider contention
        if (this.brainstem && (tc.input as any).estimated_steps > 3) {
          (tc.input as any).estimated_steps = 3
        }
      }
    }

    // Process real tools (shared helper from base)
    if (executableCalls.length > 0) {
      const toolResults = await this.executeRealTools(executableCalls)

      // Extract Synapse guidance from collect_thoughts results and store for injection
      for (const result of toolResults) {
        if (result.type === 'tool_result' && typeof result.content === 'string') {
          try {
            const parsed = JSON.parse(result.content)
            if (parsed.synapse?.observation || parsed.synapse?.branchSuggestion || parsed.synapse?.risk) {
              this.lastSynapseGuidance = this.formatSynapseReminder(parsed.synapse)
            }
          } catch { /* not JSON, skip */ }
        }
      }

      results.push(...toolResults)
    }

    // Process blocked tools (shared helper from base)
    if (blockedCalls.length > 0) {
      results.push(...this.processBlockedCalls(blockedCalls))
    }

    // Record to WorkStream (cast to DyadRole — WorkStream API expects DyadRole but data is string-keyed)
    for (const tc of toolCalls) {
      // WorkStream only tracks DyadRole — skip for mentor
      if (this.role !== 'mentor') {
        const argsSummary = this.extractArgsSummary(tc.name, tc.input)
        this.workStream.recordToolCall(this.role as any, tc.name, false, argsSummary)
      }
    }

    return results
  }

  protected override async executeRealTools(calls: ParsedToolCall[]): Promise<ContentBlock[]> {
    const localCalls: ParsedToolCall[] = []
    const delegatedCalls: ParsedToolCall[] = []

    for (const call of calls) {
      if (CONSOLIDATED_GATEWAY_TOOL_NAMES.has(call.name)) {
        localCalls.push(call)
      } else {
        delegatedCalls.push(call)
      }
    }

    const results: ContentBlock[] = []
    if (localCalls.length > 0) {
      results.push(...await this.executeConsolidatedGatewayTools(localCalls))
    }
    if (delegatedCalls.length > 0) {
      results.push(...await super.executeRealTools(delegatedCalls))
    }
    return results
  }

  private async executeConsolidatedGatewayTools(calls: ParsedToolCall[]): Promise<ContentBlock[]> {
    const results: ContentBlock[] = []
    const routeTool = async (toolName: string, toolArgs: unknown) => {
      const toolCall = {
        id: `helix-gateway-${Math.random().toString(36).slice(2)}`,
        name: toolName,
        input: (toolArgs ?? {}) as Record<string, unknown>,
      }
      const result = await this.toolExecutor!.execute(toolCall, this.sessionId)
      return {
        content: [{ type: 'text' as const, text: result.content }],
        ...(result.isError ? { isError: true as const } : {}),
      }
    }

    const settled = await Promise.allSettled(
      calls.map(async tc => {
        this.toolCallCount++
        const startMs = Date.now()
        try {
          let content = ''
          let isError = false
          if (tc.name === 'code') {
            const result = await executeCodeConsolidatedTool(tc.input, this.logger, routeTool)
            content = JSON.stringify(result)
            isError = !!result?.isError
          } else if (tc.name === 'file') {
            const result = await executeFilesystemConsolidatedTool(tc.input, this.logger, routeTool)
            content = JSON.stringify(result)
            isError = !!result?.isError
          } else if (tc.name === 'browser') {
            const result = await executeBrowserConsolidatedTool(tc.input, this.logger, routeTool)
            content = JSON.stringify(result)
            isError = !!result?.isError
          } else if (tc.name === 'web') {
            const result = await executeWebConsolidatedTool('http://localhost:7433', tc.input, this.logger, routeTool)
            content = JSON.stringify(result)
            isError = !!result?.isError
          } else {
            throw new Error(`Unsupported consolidated gateway tool: ${tc.name}`)
          }

          const durationMs = Date.now() - startMs
          this.store?.saveToolCall(
            this.sessionId, this.role, tc.name, tc.id, false,
            tc.input, this.truncateToolResult(content), isError,
            durationMs, this.iterationCount,
          )
          this.blackboard?.addToolRecord({
            tool: tc.name,
            nodeId: this.getAgentLabel(),
            params: tc.input,
            result: this.truncateToolResult(content),
            isError,
            durationMs,
          })
          return { id: tc.id, content: this.truncateToolResult(content), isError }
        } catch (err) {
          return {
            id: tc.id,
            content: `Tool execution failed: ${err instanceof Error ? err.message : String(err)}`,
            isError: true,
          }
        }
      }),
    )

    for (const item of settled) {
      if (item.status === 'fulfilled') {
        results.push({
          type: 'tool_result',
          tool_use_id: item.value.id,
          content: item.value.content,
          is_error: item.value.isError,
        })
      } else {
        results.push({
          type: 'tool_result',
          tool_use_id: 'unknown',
          content: `Tool execution rejected: ${String(item.reason)}`,
          is_error: true,
        })
      }
    }

    return results
  }

  /**
   * Format Synapse guidance into a concise reminder for tool output injection.
   */
  private formatSynapseReminder(synapse: { observation?: string; branchSuggestion?: string; risk?: string }): string {
    const parts: string[] = ['--- Synapse Guidance ---']
    if (synapse.observation) parts.push(`Observation: ${synapse.observation}`)
    if (synapse.branchSuggestion) parts.push(`Branch suggestion: ${synapse.branchSuggestion}`)
    if (synapse.risk) parts.push(`Risk: ${synapse.risk}`)
    parts.push('---')
    return parts.join('\n')
  }

  /**
   * Extract a short args summary from tool call input for pattern detection.
   * Returns file paths, search queries, or other identifying info.
   */
  private extractArgsSummary(toolName: string, input?: Record<string, unknown>): string | undefined {
    if (!input) return undefined
    // File operations — extract the path
    const pathVal = input.path ?? input.filePath ?? input.relative_path ?? input.file_path
    if (pathVal && typeof pathVal === 'string') {
      return pathVal
    }
    // Search operations — extract the query/pattern
    const queryVal = input.query ?? input.pattern ?? input.substring_pattern ?? input.command
    if (queryVal && typeof queryVal === 'string') {
      return queryVal.slice(0, 80)
    }
    return undefined
  }


  // ── Meta-Tool Handlers ──────────────────────────────────────────────

  private handleMetaTool(name: string, input: Record<string, unknown>): string {
    switch (name) {
      // Unity tools
      case 'acknowledge_nudge': return this.handleAcknowledgeNudge(input)
      case 'signal_done': return this.handleSignalDone(input)
      case 'report_to_brainstem': return this.handleReportToBrainstem(input)
      // Reviewer tools (dialectic)
      case 'share_finding': return this.handleShareFinding(input)
      case 'challenge': return this.handleChallenge(input)
      case 'concede': return this.handleConcede(input)
      case 'request_investigation': return this.handleRequestInvestigation(input)
      case 'stream_research_finding': return this.handleStreamResearchFinding(input)
      case 'post_research_signal': return this.handlePostResearchSignal(input)
      // Mentor tools
      case 'mentor_steer': return this.handleMentorSteer(input)
      case 'mentor_flag': return this.handleMentorFlag(input)
      case 'mentor_force_conclusion': return this.handleMentorForceConclusion(input)
      case 'mentor_dispatch_research': return this.handleMentorDispatchResearch(input)
      case 'mentor_synthesize': return this.handleMentorSynthesize(input)
      // Reviewer tools (WorkStream)
      case 'send_nudge': return this.handleSendNudge(input)
      case 'review_progress': return this.handleReviewProgress()
      // Edit proposal tools (Yang/Yin)
      case 'propose_edit': return this.handleProposeEdit(input)
      case 'review_edit_proposal': return this.handleReviewEditProposal(input)
      // Conclusion — tool schema is signal_conclusion (from Lumen dialectic-tools)
      case 'signal_conclusion': return this.handleSignalConclusion(input)
      default: return `Unknown meta-tool: ${name}`
    }
  }

  // ── Unity Handlers ──

  private handleAcknowledgeNudge(input: Record<string, unknown>): string {
    const nudgeId = String(input.nudge_id ?? '')
    const message = String(input.message ?? '')
    const acknowledged = this.workStream.acknowledgeNudge(nudgeId, message)
    if (!acknowledged) {
      return `Nudge ${nudgeId} could not be acknowledged (not found, already acknowledged, or expired). Continuing work.`
    }
    return `Nudge ${nudgeId} acknowledged. Continuing work.`
  }

  private handleSignalDone(input: Record<string, unknown>): string {
    const conclusion = String(input.conclusion ?? '')
    const confidence = typeof input.confidence === 'number' ? input.confidence : 0.5
    const keyPoints = Array.isArray(input.key_points) ? input.key_points.map(String) : []

    this.concluded = true
    this.workStream.recordRoleConclusion(this.role as any, false)

    return `Work complete. Conclusion recorded. Yang and Yin will do a final review pass.`
  }

  private handleReportToBrainstem(input: Record<string, unknown>): string {
    const reportType = String(input.type ?? 'progress')
    const message = String(input.message ?? '')
    const context = (input.context && typeof input.context === 'object') ? input.context as Record<string, unknown> : undefined

    if (!message) return 'ERROR: message is required.'

    // Queue as a special work unit so the Brainstem sees it in its next processing cycle
    if (this.brainstem) {
      this.brainstem.onUnityReport({
        type: reportType as 'phase_change' | 'blocker' | 'question' | 'progress' | 'completion',
        message,
        context,
        timestamp: Date.now(),
        iteration: this.iterationCount,
      })
    }

    this.logger.info('Unity report sent to Brainstem', {
      type: reportType,
      message: message.slice(0, 200),
    })

    return `Report (${reportType}) sent to Brainstem. It will be processed in the next evaluation cycle.`
  }

  // ── Reviewer Handlers (Dialectic) ──

  private handleShareFinding(input: Record<string, unknown>): string {
    if (!this.dialecticChannel) return 'ERROR: No dialectic channel available.'

    const finding = String(input.finding ?? '')
    const evidence = input.evidence ? String(input.evidence) : undefined
    const tags = Array.isArray(input.tags) ? input.tags.map(String) : []

    const id = this.dialecticChannel.postFinding(this.role as any, finding, evidence, tags)
    this.findingsShared++

    // Auto-draft to blackboard
    this.blackboard?.autoDraftFromFinding(this.role, String(id), finding, evidence ? [evidence] : undefined)

    return `Finding shared as #${id}. The other reviewer will see it in their next dialectic injection.`
  }

  private handleChallenge(input: Record<string, unknown>): string {
    if (!this.dialecticChannel) return 'ERROR: No dialectic channel available.'

    const findingId = String(input.finding_id ?? '')
    const counterargument = String(input.counterargument ?? '')
    const evidence = input.evidence ? String(input.evidence) : undefined

    try {
      const id = this.dialecticChannel.postChallenge(this.role as any, findingId, counterargument, evidence)
      this.challengesMade++

      this.blackboard?.autoDraftFromChallenge(this.role, String(id), counterargument, findingId)

      return `Challenge posted as #${id} against finding #${findingId}. They must address this before concluding.`
    } catch (err) {
      return `Challenge failed: ${err instanceof Error ? err.message : String(err)}`
    }
  }

  private handleConcede(input: Record<string, unknown>): string {
    if (!this.dialecticChannel) return 'ERROR: No dialectic channel available.'

    const challengeId = String(input.challenge_id ?? '')
    const reason = input.reason ? String(input.reason) : undefined

    try {
      this.dialecticChannel.postConcession(this.role as any, challengeId, reason)
      this.concessionsMade++

      if (reason) {
        this.blackboard?.autoDraftFromConcession(this.role, challengeId, reason, challengeId)
      }

      return `Concession recorded for challenge #${challengeId}. This creates a convergence point.`
    } catch (err) {
      return `Concession failed: ${err instanceof Error ? err.message : String(err)}`
    }
  }

  // ── Reviewer Handlers (WorkStream) ──

  private handleReviewProgress(): string {
    const stats = this.workStream.getStats()
    const allWUs = this.workStream.getAllWorkUnits()
    const reviewed = allWUs.filter(wu => this.reviewedWorkUnitIds.has(wu.id))
    const unreviewed = allWUs.filter(wu => !this.reviewedWorkUnitIds.has(wu.id))
    const unityDone = this.workStream.isWorkerDone()

    const lines: string[] = [
      `## Pipeline Progress`,
      `Unity status: ${unityDone ? 'DONE' : 'WORKING'}`,
      `Work units: ${allWUs.length} total, ${reviewed.length} reviewed, ${unreviewed.length} pending`,
      `Nudges sent: ${stats.nudges.low} low, ${stats.nudges.high} high`,
      `Refinements: ${stats.refinements}`,
    ]

    if (this.dialecticChannel) {
      const dStats = this.dialecticChannel.getStats()
      lines.push(`Dialectic: ${dStats.findings} findings, ${dStats.challenges} challenges, ${dStats.concessions} concessions`)
    }

    if (unreviewed.length > 0) {
      lines.push(`\nPending work units:`)
      for (const wu of unreviewed.slice(0, 5)) {
        lines.push(`- ${wu.id} (iter ${wu.iteration ?? 0}): ${(wu.reasoning ?? '').slice(0, 100)}`)
      }
    }

    return lines.join('\n')
  }

  private handleSendNudge(input: Record<string, unknown>): string {
    const severity = (input.severity as 'low' | 'high') ?? 'low'
    const content = String(input.content ?? '').slice(0, 500)
    const workUnitId = input.work_unit_id ? String(input.work_unit_id) : undefined

    try {
      this.workStream.postNudge({
        id: `nudge-${Date.now()}-${this.role}`,
        from: this.role as 'yang' | 'yin',
        to: 'unity' as const,
        severity,
        content,
        workUnitId,
        timestamp: Date.now(),
        acknowledged: false,
      } as any, this.iterationCount)
    } catch (err) {
      this.logger.warn('Reviewer nudge rejected', {
        role: this.role,
        severity,
        error: String(err),
      })
      return `Nudge not sent: ${String(err)}`
    }

    this.nudgesSent++

    return severity === 'high'
      ? `HIGH-severity nudge sent to Unity. Unity must acknowledge before continuing.`
      : `Low-severity nudge sent to Unity. Unity will see it in their next iteration.`
  }


  // ── Edit Proposal Handlers ──────────────────────────────────────────

  /**
   * Handle propose_edit — Yang or Yin proposes a file edit through the dialectic.
   */
  private handleProposeEdit(input: Record<string, unknown>): string {
    if (!this.dialecticChannel) return 'ERROR: No dialectic channel available.'
    if (this.role !== 'yang' && this.role !== 'yin') {
      return 'ERROR: Only Yang and Yin can propose edits.'
    }

    const filePath = String(input.file_path ?? '')
    const oldContent = String(input.old_content ?? '')
    const newContent = String(input.new_content ?? '')
    const reason = String(input.reason ?? '')

    if (!filePath || !oldContent || !newContent || !reason) {
      return 'ERROR: file_path, old_content, new_content, and reason are all required.'
    }

    const proposalId = this.dialecticChannel.postEditProposal(
      this.role,
      filePath,
      oldContent,
      newContent,
      reason,
    )

    return `Edit proposal ${proposalId} submitted for "${filePath}". ` +
      `The ${this.role === 'yang' ? 'Yin' : 'Yang'} reviewer must approve it, ` +
      `then the Brainstem will make the final decision before it's applied.`
  }

  /**
   * Handle review_edit_proposal — Peer posture reviews a proposed edit.
   */
  private handleReviewEditProposal(input: Record<string, unknown>): string {
    if (!this.dialecticChannel) return 'ERROR: No dialectic channel available.'
    if (this.role !== 'yang' && this.role !== 'yin') {
      return 'ERROR: Only Yang and Yin can review edit proposals.'
    }

    const proposalId = String(input.proposal_id ?? '')
    const approved = input.approved === true || input.approved === 'true'
    const reason = String(input.reason ?? '')
    const suggestedChanges = input.suggested_changes ? String(input.suggested_changes) : undefined

    if (!proposalId || !reason) {
      return 'ERROR: proposal_id and reason are required.'
    }

    // Find the proposal
    const proposals = this.dialecticChannel.getPendingEditProposals()
    const proposal = proposals.find((p) => p.id === proposalId)

    if (!proposal) {
      return `ERROR: Edit proposal ${proposalId} not found or not in a reviewable state.`
    }

    // Can't review your own proposal
    if (proposal.from === this.role) {
      return `ERROR: You cannot review your own edit proposal. The other reviewer must review it.`
    }

    const reviewId = this.dialecticChannel.postEditReview(
      this.role,
      proposalId,
      approved,
      reason,
      suggestedChanges,
    )

    if (approved) {
      return `Edit proposal ${proposalId} APPROVED (review ${reviewId}). ` +
        `It will now go to the Brainstem for final approval. Reason: ${reason}`
    } else {
      return `Edit proposal ${proposalId} REJECTED (review ${reviewId}). ` +
        `The edit will not be applied. Reason: ${reason}` +
        (suggestedChanges ? `\nSuggested changes: ${suggestedChanges}` : '')
    }
  }

  private handleRequestInvestigation(input: Record<string, unknown>): string {
    if (!this.dialecticChannel) return 'ERROR: No dialectic channel available.'

    const area = String(input.area ?? '')
    const reason = String(input.reason ?? '')

    // Post as a finding tagged as an investigation request so the other reviewer sees it
    const id = this.dialecticChannel.postFinding(
      this.role as any,
      `[Investigation Request] ${area}: ${reason}`,
      undefined,
      ['investigation-request'],
    )

    // Also post to blackboard via HelixResearcher for shared visibility
    if (this.blackboard) {
      try {
        const researcher = new HelixResearcher({
          sessionId: this.sessionId,
          blackboard: this.blackboard,
          query: area,
          label: `investigation-${this.role}`,
          requestedBy: this.role as 'yang' | 'yin',
          priority: 'high',
          context: reason,
          logger: this.logger,
        })

        // Fire-and-forget: post request to blackboard and log findings
        researcher.postRequest().catch((err) =>
          this.logger.warn('Failed to post research request to blackboard', { error: String(err) })
        )
      } catch (err) {
        this.logger.warn('Failed to create HelixResearcher', { error: String(err) })
      }
    }

    return `Investigation request posted as #${id}. The other reviewer will see your request to investigate "${area}" in their next dialectic injection. A research request has been posted to the blackboard for shared visibility.`
  }

  private handleStreamResearchFinding(input: Record<string, unknown>): string {
    if (!this.blackboard) return 'ERROR: No blackboard available.'

    const content = String(input.content ?? '')
    const source = input.source ? String(input.source) : undefined
    const confidence = typeof input.confidence === 'number' ? input.confidence : undefined

    try {
      const researcher = new HelixResearcher({
        sessionId: this.sessionId,
        blackboard: this.blackboard,
        query: 'active-investigation',
        label: `research-${this.role}`,
        requestedBy: this.role as 'yang' | 'yin',
        logger: this.logger,
      })

      // Post the finding directly to blackboard findings channel
      researcher.postFinding(content, { source, confidence }).catch((err) =>
        this.logger.warn('Failed to stream research finding', { error: String(err) })
      )

      return `Research finding posted to blackboard findings channel. ${source ? `Source: ${source}` : ''}`
    } catch (err) {
      this.logger.error('Failed to stream research finding', { error: String(err) })
      return `ERROR: ${String(err)}`
    }
  }

  private handlePostResearchSignal(input: Record<string, unknown>): string {
    if (!this.blackboard) return 'ERROR: No blackboard available.'

    const signalType = String(input.signal_type ?? 'assumption')
    const content = String(input.content ?? '')
    const references = input.references ? String(input.references).split(',').map(s => s.trim()) : undefined

    const validTypes = ['edge_case', 'assumption', 'tension', 'gap', 'alternative']
    if (!validTypes.includes(signalType)) {
      return `ERROR: Invalid signal type "${signalType}". Must be one of: ${validTypes.join(', ')}`
    }

    try {
      const researcher = new HelixResearcher({
        sessionId: this.sessionId,
        blackboard: this.blackboard,
        query: 'active-investigation',
        label: `signal-${this.role}`,
        requestedBy: this.role as 'yang' | 'yin',
        logger: this.logger,
      })

      researcher.postSignal({
        type: signalType as any,
        content,
        references,
      }).catch((err) =>
        this.logger.warn('Failed to post research signal', { error: String(err) })
      )

      return `Dialectic signal (${signalType}) posted to blackboard concerns channel. All postures will see this.`
    } catch (err) {
      this.logger.error('Failed to post research signal', { error: String(err) })
      return `ERROR: ${String(err)}`
    }
  }

  private handleSignalConclusion(input: Record<string, unknown>): string {
    // Check for unresolved challenges (hard-gate from DialecticChannel)
    if (this.dialecticChannel) {
      const unresolved = this.dialecticChannel.getUnresolvedChallenges(this.role as any)
      if (unresolved.length > 0) {
        const ids = unresolved.map((c: any) => `#${c.id}`).join(', ')
        return `BLOCKED: You have ${unresolved.length} unresolved challenge(s): ${ids}. ` +
          'You must address each challenge (concede or provide counter-evidence) before concluding.'
      }
    }

    const conclusion = String(input.conclusion ?? '')
    const confidence = typeof input.confidence === 'number' ? input.confidence : 0.5

    this.concluded = true
    if (this.role !== 'mentor') {
      this.workStream.recordRoleConclusion(this.role as any, false)
    }

    this.logger.info(`${this.role} review complete`, {
      conclusion: conclusion.slice(0, 100),
      confidence,
      nudgesSent: this.nudgesSent,
      findingsShared: this.findingsShared,
    })

    return 'Review complete. Your conclusion has been recorded.'
  }


  // ── Report Tool Delegation ──────────────────────────────────────────

  private handleReportTool(name: string, input: Record<string, unknown>): string {
    if (!this.blackboard) return 'Report tools require a Blackboard — not available.'

    // Delegate to WorkStream report methods (same pattern as Dyad)
    switch (name) {
      case 'report_add_section': {
        const section = this.workStream.addReportSection({
          title: String(input.title ?? ''),
          content: String(input.content ?? ''),
          type: (input.type as any) ?? 'finding',
          author: this.role,
          confidence: typeof input.confidence === 'number' ? input.confidence : 0.7,
        })
        return `Report section added: "${section.title}" (id: ${section.id}).`
      }
      case 'report_view':
        return JSON.stringify(this.workStream.getReportView(), null, 2)
      default:
        return `Unknown report tool: ${name}`
    }
  }


  // ── Mentor Tool Handlers ────────────────────────────────────────────

  private handleMentorSteer(input: Record<string, unknown>): string {
    if (!this.dialecticChannel) return 'ERROR: No dialectic channel available.'

    const directive = String(input.directive ?? '')
    const target = (String(input.target ?? 'both') as 'yang' | 'yin' | 'both' | 'unity')
    const priority = String(input.priority ?? 'medium')

    try {
      this.dialecticChannel.injectMentorSteering(target, directive, 'steer')
      if (this.blackboard) {
        const postMethod = (this.blackboard as any).post?.bind(this.blackboard)
        postMethod?.('requests', {
          author: 'mentor',
          content: `**Mentor Steering [${target}]:** ${directive}`,
          tags: ['mentor', 'steering', `target:${target}`],
          priority: priority === 'high' ? 2 : priority === 'low' ? 0 : 1,
          structured: { type: 'mentor_steering', target, directive },
        })
      }

      // Bridge Unity-targeted steering into WorkStream as nudges
      // Unity doesn't participate in the dialectic channel — it reads nudges from WorkStream
      if (target === 'unity' || target === 'both') {
        const severity = priority === 'high' ? 'high' as const : 'low' as const
        try {
          this.workStream.postNudge({
            id: `mentor-nudge-${Date.now()}`,
            from: 'yang' as any, // WorkStream expects DyadRole — use yang as proxy for mentor
            to: 'unity' as any,
            severity,
            content: `[Mentor Guidance] ${directive}`,
            timestamp: Date.now(),
            acknowledged: false,
          } as any, this.iterationCount)
        } catch (nudgeErr) {
          this.logger.warn('Mentor steering nudge rejected', { error: String(nudgeErr) })
        }
      }
    } catch (err) {
      this.logger.error('Mentor steering injection failed', { error: String(err) })
      return `ERROR: ${String(err)}`
    }

    return `Mentor steering injected into the dialectic. Target: ${target}, Priority: ${priority}.`
  }

  private handleMentorFlag(input: Record<string, unknown>): string {
    if (!this.dialecticChannel) return 'ERROR: No dialectic channel available.'

    const issue = String(input.issue ?? '')
    const issueType = String(input.issue_type ?? 'missed_point')

    try {
      this.dialecticChannel.injectMentorSteering('both', issue, 'flag', issueType)
      const postMethod = (this.blackboard as any).post?.bind(this.blackboard)
      if (postMethod) {
        postMethod('concerns', {
          author: 'mentor',
          content: `**Mentor Flag [${issueType}]:** ${issue}`,
          tags: ['mentor', 'flag', issueType],
          priority: 2, // high — flags are always important
          structured: { type: 'mentor_flag', issueType, issue },
        })
      }

      // Bridge flags to Unity as high-severity nudges — Unity needs to know about flagged issues
      try {
        this.workStream.postNudge({
          id: `mentor-flag-${Date.now()}`,
          from: 'yang' as any, // WorkStream expects DyadRole
          to: 'unity' as any,
          severity: 'high',
          content: `[Mentor Flag: ${issueType}] ${issue}`,
          timestamp: Date.now(),
          acknowledged: false,
        } as any, this.iterationCount)
      } catch (nudgeErr) {
        this.logger.warn('Mentor flag nudge rejected', { error: String(nudgeErr) })
      }
    } catch (err) {
      this.logger.error('Mentor flag post failed', { error: String(err) })
      return `ERROR: ${String(err)}`
    }

    return `Issue flagged and injected into the dialectic: ${issueType}.`
  }

  private handleMentorForceConclusion(input: Record<string, unknown>): string {
    if (!this.blackboard || !this.dialecticChannel) return 'ERROR: Blackboard and dialectic channel required.'

    const summary = String(input.summary ?? '')
    const recommendation = String(input.recommendation ?? '')
    const confidence = typeof input.confidence === 'number' ? input.confidence : 0.5

    try {
      this.dialecticChannel.injectMentorSteering(
        'both',
        `Force conclusion. Current state: ${summary}\nRecommended convergence: ${recommendation}`,
        'force_conclusion',
      )
      const postMethod = (this.blackboard as any).post?.bind(this.blackboard)
      if (postMethod) {
        postMethod('decisions', {
          author: 'mentor',
          content: `**Mentor Decision — Force Conclusion**\n\n` +
            `**State:** ${summary}\n\n` +
            `**Recommendation:** ${recommendation}\n\n` +
            `**Confidence:** ${confidence}`,
          tags: ['mentor', 'force-conclusion', 'decision'],
          priority: 2,
          structured: { type: 'mentor_force_conclusion', summary, recommendation, confidence },
        })
      }

      // Also send a high-priority nudge to Unity
      try {
        this.workStream.sendNudge({
          id: `mentor-conclusion-${Date.now()}`,
          from: 'mentor' as any,
          to: 'unity',
          severity: 'high',
          content: `Mentor conclusion: ${recommendation} (confidence: ${confidence}). ${summary.slice(0, 200)}`,
          timestamp: Date.now(),
          acknowledged: false,
        }, 0)
      } catch (nudgeErr) {
        this.logger.warn('Mentor conclusion nudge failed', { error: String(nudgeErr) })
      }
    } catch (err) {
      this.logger.error('Mentor force conclusion failed', { error: String(err) })
      return `ERROR: ${String(err)}`
    }

    return `Conclusion forced. Decision posted, dialectic steered, nudge sent to Unity.`
  }

  private handleMentorDispatchResearch(input: Record<string, unknown>): string {
    if (!this.blackboard || !this.dialecticChannel) return 'ERROR: Blackboard and dialectic channel required.'

    const query = String(input.query ?? '').trim()
    const target = (String(input.target ?? 'both') as 'yang' | 'yin' | 'both')
    const rationale = String(input.rationale ?? '').trim()
    const priority = (String(input.priority ?? 'medium') as 'low' | 'medium' | 'high')

    if (!query) return 'ERROR: query is required.'

    try {
      const targets = target === 'both' ? (['yang', 'yin'] as const) : ([target] as const)
      for (const requestedBy of targets) {
        const researcher = new HelixResearcher({
          sessionId: this.sessionId,
          blackboard: this.blackboard,
          query,
          label: `mentor-${requestedBy}`,
          requestedBy,
          priority,
          context: rationale || 'Mentor-directed research mission',
          logger: this.logger,
        })
        void researcher.postRequest().catch((err) =>
          this.logger.warn('Failed to post mentor research request', { error: String(err), requestedBy })
        )

        // Spawn a research drone if the spawner is wired
        if (this.researchSpawner) {
          const label = `mentor-research-${requestedBy}-${Date.now()}`
          void this.researchSpawner({
            query,
            label,
            context: rationale || `Mentor-directed research for ${requestedBy}: ${query}`,
            priority,
            sessionId: this.sessionId,
          }).then(({ requestId, droneId }) => {
            this.logger.info('Research drone spawned', { requestId, droneId, query: query.slice(0, 100), requestedBy })
          }).catch((err) => {
            this.logger.warn('Research drone spawn failed — falling back to blackboard request only', {
              error: String(err), query: query.slice(0, 100), requestedBy,
            })
          })
        }
      }

      this.dialecticChannel.injectMentorSteering(
        target,
        `Research mission assigned: ${query}${rationale ? `\nWhy: ${rationale}` : ''}`,
        'steer',
        'research_dispatch',
      )
    } catch (err) {
      this.logger.error('Mentor research dispatch failed', { error: String(err) })
      return `ERROR: ${String(err)}`
    }

    const spawnerStatus = this.researchSpawner ? ' A research drone has been dispatched to execute the investigation.' : ' (No research drone available — request posted to blackboard only.)'
    return `Research mission dispatched to ${target}: ${query}${spawnerStatus}`
  }

  private handleMentorSynthesize(input: Record<string, unknown>): string {
    if (!this.blackboard) return 'ERROR: No blackboard available.'

    const synthesis = String(input.synthesis ?? '')
    const recommendation = String(input.recommendation ?? 'proceed')
    const confidence = typeof input.confidence === 'number' ? input.confidence : 0.7
    const keyFindings = Array.isArray(input.key_findings) ? input.key_findings.map(String) : []
    const remainingRisks = Array.isArray(input.remaining_risks) ? input.remaining_risks.map(String) : []

    try {
      const postMethod = (this.blackboard as any).post?.bind(this.blackboard)
      if (postMethod) {
        const content = [
          `## Mentor Synthesis`,
          '',
          `**Recommendation:** ${recommendation} (confidence: ${confidence})`,
          '',
          synthesis,
          '',
        ]

        if (keyFindings.length > 0) {
          content.push('### Key Findings', '')
          keyFindings.forEach((f, i) => content.push(`${i + 1}. ${f}`))
          content.push('')
        }
        if (remainingRisks.length > 0) {
          content.push('### Remaining Risks', '')
          remainingRisks.forEach((r, i) => content.push(`${i + 1}. ${r}`))
          content.push('')
        }

        postMethod('findings', {
          author: 'mentor',
          content: content.join('\n'),
          tags: ['mentor', 'synthesis', 'final', recommendation],
          priority: 2,
          structured: {
            type: 'mentor_synthesis',
            recommendation,
            confidence,
            keyFindings,
            remainingRisks,
          },
        })
      }
    } catch (err) {
      this.logger.error('Mentor synthesis failed', { error: String(err) })
      return `ERROR: ${String(err)}`
    }

    this.concluded = true
    // Mentor is not tracked in WorkStream — its conclusion is recorded in posture result

    // Store synthesis data for extraction into HelixPostureResult
    this.mentorSynthesis = { recommendation, confidence, keyFindings, remainingRisks, synthesis }

    this.logger.info('Mentor synthesis complete', {
      recommendation,
      confidence,
      keyFindings: keyFindings.length,
      remainingRisks: remainingRisks.length,
    })

    return `Synthesis posted to findings channel. Recommendation: ${recommendation} (${confidence}).`
  }


  // ── Message Construction ────────────────────────────────────────────

  private buildInitialMessages(goal: string, context: string | undefined, role: HelixRole): Message[] {
    const messages: Message[] = [
      { role: 'system', content: this.posture.systemPrompt },
    ]

    let userContent = `## Goal\n\n${goal}`

    if (context) {
      userContent += `\n\n## Context\n\n${context}`
    }

    if (role === 'unity') {
      userContent += '\n\n## Instructions\n\nBegin your implementation work now. ' +
        'Read the goal carefully, then start making progress using your tools. ' +
        'Yang and Yin will review your work asynchronously and send nudges if needed.'
    } else if (role === 'mentor') {
      userContent += '\n\n## Instructions\n\nYou are the Mentor. Watch the Yang↔Yin dialectic and Unity\'s work stream. ' +
        'Intervene only when you can materially improve the session: steer, flag, dispatch research, force conclusion, or synthesize.'
    } else {
      userContent += `\n\n## Instructions\n\nYou are reviewing Unity's implementation work as ${role.toUpperCase()}. ` +
        'Unity is working right now — their work units will appear as they make progress. ' +
        'Investigate each work unit with your read-only tools, share findings with the other reviewer, ' +
        'and send nudges to Unity when you have actionable feedback.'
    }

    messages.push({ role: 'user', content: userContent })

    return messages
  }

  private buildToolSchemas(role: HelixRole): NonNullable<CompletionOpts['tools']> {
    const tools: NonNullable<CompletionOpts['tools']> = []

    // Add role-specific meta-tools
    tools.push(...getHelixToolSchemas(role))

    // Add blackboard tools
    tools.push(...this.getBlackboardSchemas())

    // Add plan tools
    if (this.planHandler) {
      tools.push(...getPlanToolSchemas(role))
    }

    // Add report tools
    if (REPORT_TOOLS.length > 0) {
      tools.push(...REPORT_TOOLS)
    }

    // Add real tools (filtered by access level)
    if (this.toolRegistry) {
      const hasFullAccess = role === 'unity'
      const allSchemas = this.toolRegistry.toAnthropicSchema()
      for (const schema of allSchemas) {
        if (isHelixMetaTool(schema.name)) continue
        if (isBlackboardMetaTool(schema.name)) continue
        if (isPlanMetaTool(schema.name)) continue
        if (REPORT_TOOL_NAMES.has(schema.name)) continue
        // Filter out tools that trap autonomous postures in useless loops
        if (isBlockedForAutonomousPostures(schema.name)) continue
        // Hide raw external MCP tools and consolidated gateway tools; inject curated variants below
        if (isExternalMcpTool(schema.name)) continue
        if (CONSOLIDATED_GATEWAY_TOOL_NAMES.has(schema.name)) continue

        if (hasFullAccess || isReadOnlyTool(schema.name, this.toolRegistry) || isMemoryTool(schema.name)) {
          tools.push(schema as any)
        }
      }

      const readOnly = !hasFullAccess
      tools.push(getCodeConsolidatedToolSchema(readOnly) as any)
      tools.push(getFilesystemConsolidatedToolSchema(readOnly) as any)
      tools.push(WEB_CONSOLIDATED_TOOL as any)
      if (hasFullAccess) {
        tools.push(BROWSER_CONSOLIDATED_TOOL as any)
      }
    }

    return tools
  }


  // ── Channel Message Injection ───────────────────────────────────────

  /**
   * Inject low-severity nudges from reviewers into Unity's tool results.
   */
  private injectNudgeMessages(toolResults: ContentBlock[]): ContentBlock[] {
    // drainForRole returns formatted string | null
    const drained = this.workStream.drainForRole('yang')
    if (!drained) return toolResults

    return [
      ...toolResults,
      {
        type: 'text' as const,
        text: `\n--- Reviewer Feedback ---\n${drained}\n---`,
      },
    ]
  }

  /**
   * Inject Synapse guidance into tool results and consume it (one-shot).
   * The guidance was captured from a previous collect_thoughts call.
   */
  private injectSynapseGuidance(toolResults: ContentBlock[]): ContentBlock[] {
    if (!this.lastSynapseGuidance) return toolResults

    const guidance = this.lastSynapseGuidance
    this.lastSynapseGuidance = undefined // Consume — don't repeat

    return [
      ...toolResults,
      {
        type: 'text' as const,
        text: `\n${guidance}\nRemember: use collect_thoughts for complex analysis steps.`,
      },
    ]
  }

  /**
   * Inject Brainstem guidance into tool results (low/medium urgency).
   * Escalating model: low/medium → tool result injection, high/critical → user message.
   * One-shot: consumes the latest pending guidance from the Brainstem.
   */
  private injectBrainstemGuidance(toolResults: ContentBlock[]): ContentBlock[] {
    if (!this.brainstem) return toolResults

    const guidance = this.brainstem.getLatestGuidance()
    if (!guidance) return toolResults

    // Critical/high urgency: inject as blocking user message instead
    if (guidance.urgency === 'critical' || guidance.urgency === 'high') {
      this.logger.info('Brainstem escalating guidance to user message', {
        urgency: guidance.urgency,
        triggeredBy: guidance.triggeredBy,
        text: guidance.text.slice(0, 100),
      })
      this.messages.push({
        role: 'user',
        content: `🧠 Brainstem Guidance (${guidance.urgency} — ${guidance.triggeredBy}):\n\n${guidance.text}\n\nAct on this immediately before continuing.`,
      })
      return toolResults // Guidance is now a separate user message
    }

    // Low/medium urgency: inject into tool results
    this.logger.debug('Brainstem injecting guidance into tool results', {
      urgency: guidance.urgency,
      triggeredBy: guidance.triggeredBy,
    })

    return [
      ...toolResults,
      {
        type: 'text' as const,
        text: `\n🧠 Brainstem: ${guidance.text}\n`,
      },
    ]
  }

  /**
   * Inject dialectic messages from the other reviewer.
   * Uses DialecticChannel.drainForPosture() which returns formatted string.
   * Returns true if any messages were injected.
   */
  private injectDialecticMessages(): boolean {
    if (!this.dialecticChannel) return false

    // drainForPosture returns a formatted string of new messages from other postures
    const drained = this.dialecticChannel.drainForPosture(this.role as LumenPostureType)
    if (!drained) return false

    this.messages.push({
      role: 'user',
        content: this.role === 'mentor'
          ? `--- Dialectic Channel ---\n\n${drained}\n\n---\n\nProcess these messages as Mentor: decide whether to steer, flag, dispatch research, force conclusion, or synthesize.`
          : `--- Dialectic Channel ---\n\n${drained}\n\n---\n\nProcess these messages: challenge findings you disagree with, concede valid challenges, and share your own findings.`,
    })

    return true
  }

  /**
   * Inject dialectic messages into tool results (for reviewer iterations with tool calls).
   */
  private injectDialecticIntoResults(toolResults: ContentBlock[]): ContentBlock[] {
    if (!this.dialecticChannel) return toolResults

    const drained = this.dialecticChannel.drainForPosture(this.role as LumenPostureType)
    if (!drained) return toolResults

    return [
      ...toolResults,
      {
        type: 'text' as const,
        text: this.role === 'mentor'
          ? `\n--- Mentor Channel ---\n${drained}\n---`
          : `\n--- Dialectic Channel ---\n${drained}\n---`,
      },
    ]
  }


  // ── UnityStatus Injection ─────────────────────────────────────────────

  /** Track last UnityStatus injection to avoid spamming reviewers */
  private lastUnityStatusInjectionIteration = 0

  /** Minimum iterations between UnityStatus injections to prevent spam */
  private static readonly MIN_UNITY_STATUS_GAP_ITERATIONS = 3

  /**
   * Primary: Inject UnityStatus into tool results — piggybacks on existing responses.
   * Zero extra LLM requests. Called during reviewer tool-processing path.
   */
  private injectUnityStatusIntoResults(toolResults: ContentBlock[]): ContentBlock[] {
    if (this.role === 'unity' || this.role === 'mentor') return toolResults

    // Rate limit: don't inject every iteration
    if (this.iterationCount - this.lastUnityStatusInjectionIteration < HelixPostureRunner.MIN_UNITY_STATUS_GAP_ITERATIONS) {
      return toolResults
    }

    const status = this.workStream.getUnityStatus(this.unityStatusThresholds)
    if (!status) return toolResults

    this.lastUnityStatusInjectionIteration = this.iterationCount
    this.logger.debug('Injecting UnityStatus into reviewer tool results', {
      role: this.role,
      triggeredBy: status.triggeredBy,
      iterationsSinceWu: status.iterationsSinceWu,
      secondsSinceWu: status.secondsSinceWu,
    })

    return [
      ...toolResults,
      {
        type: 'text' as const,
        text: `\n--- Unity Status Signal ---\n${WorkStream.formatUnityStatus(status)}\n---`,
      },
    ]
  }

  /**
   * Fallback: Inject UnityStatus as a user message — used when reviewer has
   * no work unit and no dialectic messages. This costs one LLM round-trip
   * but only fires as a last resort when tool injection isn't possible.
   *
   * Returns true if a status message was injected.
   */
  private injectUnityStatusAsMessage(): boolean {
    if (this.role === 'unity' || this.role === 'mentor') return false

    // Rate limit
    if (this.iterationCount - this.lastUnityStatusInjectionIteration < HelixPostureRunner.MIN_UNITY_STATUS_GAP_ITERATIONS) {
      return false
    }

    const status = this.workStream.getUnityStatus(this.unityStatusThresholds)
    if (!status) return false

    this.lastUnityStatusInjectionIteration = this.iterationCount
    this.logger.debug('Injecting UnityStatus as fallback message', {
      role: this.role,
      triggeredBy: status.triggeredBy,
      iterationsSinceWu: status.iterationsSinceWu,
      secondsSinceWu: status.secondsSinceWu,
    })

    this.messages.push({
      role: 'user',
      content: `--- Unity Status Signal (Proactive) ---\n\n${WorkStream.formatUnityStatus(status)}\n\n---\n\n` +
        'Unity may be stuck or off-track. Review the status above and decide whether to ' +
        'investigate further (use request_investigation) or send a nudge (use send_nudge).',
    })

    return true
  }


  // ── Work Unit Capture ───────────────────────────────────────────────

  /**
   * Capture a work unit from Unity's tool loop iteration.
   * Extracts file changes and tool summary from the results.
   */
  private captureWorkUnit(
    inference: InferenceResult,
    toolCalls: ParsedToolCall[],
    toolResults: ContentBlock[],
  ): WorkUnit {
    const filesModified: FileChange[] = []

    for (const tc of toolCalls) {
      if (tc.name === 'write' || tc.name === 'edit' || tc.name === 'cassi_write' || tc.name === 'cassi_edit') {
        const path = String(tc.input?.path ?? tc.input?.filePath ?? 'unknown')
        filesModified.push({
          path,
          action: tc.name.includes('write') ? 'created' : 'modified',
          summary: `${tc.name} on ${path}`,
        })
      }
    }

    const textBlocks = inference.contentBlocks
      .filter(b => b.type === 'text')
      .map(b => (b as any).text)
      .join('\n')
      .slice(0, 2000)

    const toolCallSummaries: ToolCallSummary[] = toolCalls.map(tc => ({
      name: tc.name,
      callId: tc.id,
      input: tc.input,
    }))

    const toolResultSummaries: ToolResultSummary[] = toolResults
      .filter(b => b.type === 'tool_result')
      .map(b => ({
        callId: (b as any).tool_use_id,
        content: String((b as any).content ?? '').slice(0, 500),
        isError: (b as any).is_error ?? false,
      }))

    return {
      id: `wu-${this.workUnitsProduced + 1}`,
      iteration: this.iterationCount,
      reasoning: textBlocks.slice(0, 500) || `Iteration ${this.iterationCount}: ${toolCalls.length} tool calls`,
      toolCalls: toolCallSummaries,
      toolResults: toolResultSummaries,
      filesModified,
      timestamp: Date.now(),
    }
  }

  /**
   * Capture a "reasoning-only" work unit when the LLM produces text without tool calls.
   * This gives the Brainstem visibility into the LLM's thinking between tool use.
   */
  private captureReasoningWorkUnit(text: string): WorkUnit {
    return {
      id: `wu-reasoning-${this.workUnitsProduced + 1}`,
      iteration: this.iterationCount,
      reasoning: text.slice(0, 1000),
      toolCalls: [],
      toolResults: [],
      filesModified: [],
      timestamp: Date.now(),
    }
  }


  /**
   * Format a work unit for reviewer inspection.
   */
  private formatWorkUnitForReview(workUnit: WorkUnit): string {
    let msg = `--- NEW WORK UNIT from Unity (${workUnit.id}) ---\n\n`
    msg += `Reasoning: ${workUnit.reasoning}\n`

    if (workUnit.toolCalls?.length) {
      msg += `Tools used: ${workUnit.toolCalls.map(tc => tc.name).join(', ')}\n`
    }

    if (workUnit.filesModified?.length) {
      msg += `Files changed:\n`
      for (const fc of workUnit.filesModified) {
        msg += `  - ${fc.action}: ${fc.path}\n`
      }
    }

    msg += `\n---\n\nInvestigate this work unit with your read-only tools. ` +
      `Share findings with the other reviewer, and send nudges to Unity if you have feedback.`

    return msg
  }


  // ── Result Building ─────────────────────────────────────────────────

  private buildPostureResult(startTime: number): HelixPostureResult {
    const durationMs = Date.now() - startTime

    // Mentor: extract synthesis data into structured result
    if (this.role === 'mentor' && this.mentorSynthesis) {
      return {
        conclusion: this.mentorSynthesis.synthesis.slice(0, 500) || `Mentor synthesized: ${this.mentorSynthesis.recommendation}`,
        confidence: this.mentorSynthesis.confidence,
        keyPoints: this.mentorSynthesis.keyFindings,
        iterationCount: this.iterationCount,
        toolCallCount: this.toolCallCount,
        tokensUsed: this.tokensUsed,
        durationMs,
        recommendation: this.mentorSynthesis.recommendation,
        remainingRisks: this.mentorSynthesis.remainingRisks,
      }
    }

    return {
      conclusion: this.concluded ? `${this.role} completed` : `${this.role} stopped`,
      confidence: 0.7,
      keyPoints: [],
      iterationCount: this.iterationCount,
      toolCallCount: this.toolCallCount,
      tokensUsed: this.tokensUsed,
      durationMs,
      workUnitsProduced: this.role === 'unity' ? this.workUnitsProduced : undefined,
      nudgesSent: this.role !== 'unity' ? this.nudgesSent : undefined,
      findingsShared: this.role !== 'unity' ? this.findingsShared : undefined,
      challengesMade: this.role !== 'unity' ? this.challengesMade : undefined,
      concessionsMade: this.role !== 'unity' ? this.concessionsMade : undefined,
    }
  }

  private buildErrorResult(startTime: number, err: unknown): HelixPostureResult {
    const durationMs = Date.now() - startTime
    this.logger.error(`${this.role} errored`, {
      error: String(err),
      iterationCount: this.iterationCount,
      durationMs,
    })
    return {
      conclusion: `${this.role} errored: ${err instanceof Error ? err.message : String(err)}`,
      confidence: 0,
      keyPoints: [],
      iterationCount: this.iterationCount,
      toolCallCount: this.toolCallCount,
      tokensUsed: this.tokensUsed,
      durationMs,
      error: err instanceof Error ? err.message : String(err),
    }
  }
}
