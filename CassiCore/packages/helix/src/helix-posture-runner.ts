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
 *
 * TODO Phase 6: Active reviewer mode
 * - Change runAsReviewer() from "wait for work unit → investigate → wait" to active investigation
 * - Reviewers get goal + context upfront (like Unity)
 * - Work units from Unity serve as investigation seeds, not the primary driver
 * - Yang actively advocates for promising approaches and posts findings
 * - Yin actively stress-tests, searches for edge cases, and posts challenges
 */

import type { ILogger, IEventBus } from '../../../types/interfaces.js'
import type { Message, ContentBlock, CompletionOpts } from '../../../types/runtime.js'
import type { ModelHandle } from '../../model-pool/types.js'
import type { IModelDirective, ModelConfig } from '../../../types/model-routing.js'
import type { ToolExecutor } from '../../tools/executor.js'
import type { ToolRegistry } from '../../tools/registry.js'
import type { PlanHandler } from '../flux-team/plan-handler.js'
import type { Blackboard } from '../flux-team/blackboard.js'
import { WorkStream } from './work-stream.js'
import type { UnityStatusThresholds } from './work-stream.js'
import type { DialecticChannel } from './dialectic-channel.js'
import { HelixWorkStream } from './helix-coordinator.js'
import type { HelixStore } from './helix-store.js'
import type { WorkUnit, FileChange, ToolCallSummary, ToolResultSummary } from './work-types.js'
import type { Posture as LumenPostureType } from './dialectic-channel.js'
import type { InferenceResult, ParsedToolCall } from '../../../types/cassi-agent.js'
import type { HelixRole, HelixPosture, HelixPostureResult } from './types.js'
import type { HelixBrainstem } from './brainstem.js'
import type { PostureModule, PostureSignalOpts } from './posture-module.js'
import type { SignalType } from '../workspace/index.js'
import type { HelixTelemetry } from './helix-telemetry.js'
import type { Aurora } from '../aurora/index.js'
import type { HelixJournal } from './helix-journal.js'
import type { PendingGuidance } from './brainstem-types.js'
import { HelixResearcher } from './helix-researcher.js'
import {
  isHelixMetaTool,
  getHelixToolSchemas,
  UNITY_TOOL_NAMES,
  REVIEWER_TOOL_NAMES,
  TESTLOCK_TOOL_NAMES,
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
import { DriftDetector } from './drift-detector.js'
import { TestLock } from './testlock.js'
import type { TestLockPersistence, SealedTestSpec, TestLockVerificationStatus, TestLockVerification } from './testlock.js'
import { estimateTokens } from '../shared/token-estimation.js'
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



let isPlanMetaTool: (name: string) => boolean = () => false
let getPlanToolSchemas: (role: any) => any[] = () => []
let REPORT_TOOLS: any[] = []
let REPORT_TOOL_NAMES: Set<string> = new Set()
let _toolsInitPromise: Promise<void> | null = null

/**
 * @dep callers: runAsWorker (core/intelligence/helix/helix-posture-runner.ts), runAsReviewer (core/intelligence/helix/helix-posture-runner.ts), runAsMentor (core/intelligence/helix/helix-posture-runner.ts)
 * @dep module: Helix
 * @dep risk: LOW | 3 callers, 0 flows, 1 module
 */

function initializeOptionalTools(): Promise<void> {
  if (_toolsInitPromise) return _toolsInitPromise
  _toolsInitPromise = (async () => {
    try {
      const planMod = await import('./plan-tools.js')
      isPlanMetaTool = planMod.isPlanMetaTool
      getPlanToolSchemas = planMod.getPlanToolSchemas
    } catch { /* plan tools not available */ }

    try {
      const reportMod = await import('./report-tools.js')
      REPORT_TOOLS = reportMod.REPORT_TOOLS ?? []
      REPORT_TOOL_NAMES = reportMod.REPORT_TOOL_NAMES ?? new Set()
    } catch { /* report tools not available */ }
  })().catch((err) => {
    _toolsInitPromise = null
    throw err
  })
  return _toolsInitPromise
}



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
  // Plan approval workflow — causes planning trap (submit requires approval before claim)
  // These tools create a bottleneck: Unity submits steps but can't claim them without approval.
  // Removed from autonomous postures; direct implementation preferred over plan workflow.
  'plan_approve_step',
  'plan_reject_step',
  'plan_complete_step',
  'plan_report_progress',
  // Unused blackboard tools — minimal usage across c-26/27/28, add noise to tool list
  'bb_scratch_list',
  'bb_search_report',
  // TestLock verification — never called (blocked signal_done in c-23).
  // Yin seals specs but Unity never verifies, permanently blocking completion.
  // Disabled to remove the blocking path; TestLock remains for sealing only.
  'verify_test_lock',
])

const EXTERNAL_MCP_PREFIXES = ['serena_', 'gitnexus_', 'playwright_browser_', 'duckduckgo_']
const EXTERNAL_MCP_SERVER_PREFIXES = ['serena__', 'gitnexus__', 'playwright__', 'playwright_browser__', 'duckduckgo__']
const CONSOLIDATED_GATEWAY_TOOL_NAMES = new Set(['code', 'file', 'web', 'browser'])

/**
 * @dep callers: isBlockedForAutonomousPostures (core/intelligence/helix/helix-posture-runner.ts), isExternalMcpTool (core/intelligence/helix/helix-posture-runner.ts)
 * @dep module: Helix
 * @dep risk: LOW | 2 callers, 0 flows, 1 module
 */

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



const DEFAULT_SESSION_ID = 'helix-session'
const REVIEWER_WORK_UNIT_TIMEOUT_MS = 3_000
const REVIEWER_DIALECTIC_BURST_LIMIT = 3
const REVIEWER_IDLE_DELAY_MS = 1_000



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
  /** ContextChunkIndex for intelligent context management (pinning, eviction, scoring) */
  contextChunkIndex?: import('./context-chunk-index.js').ContextChunkIndex
  /** Thalamus for context curation during long-running sessions */
  thalamus?: import('../thalamus/index.js').ThalamusModule
  /** Callback fired when Unity posts a work unit */
  onWorkUnit?: (wu: import('./work-types.js').WorkUnit, iteration: number) => void
  /** Callback fired during streaming with real-time token activity */
  onStreamActivity?: (event: StreamActivityEvent) => void
  /**
   * Tool access level override from FlexPosture config.
   * WHY: Templates define per-posture tool access (e.g., 'read-only+memory' for reviewers),
   * but the old code hardcoded `role === 'unity'`. This lets posture config drive access.
   */
  flexToolAccess?: import('../constellation/types.js').ToolAccessLevel
  /**
   * Tool filter (allow/deny lists) from Constellation or Helix pipeline.
   * Applied on top of posture-level access restrictions.
   */
  toolFilter?: { allow?: string[]; deny?: string[] }
  /**
   * Tool profile — selects which subset of tools are exposed to this posture.
   * When absent, defaults to 'full' (all tools) for back-compat.
   *
   *   - 'full': All tools (legacy behavior)
   *   - 'implementation': Action-focused (~15 tools) — code, file, bash, signal_done
   *   - 'review': Audit-focused (~12 tools) — read-only + dialectic + signal_conclusion
   *   - 'exploration': Research-focused (~8 tools) — file, web, collect_thoughts
   */
  toolProfile?: import('./helix-pipeline.js').HelixToolProfile
  /**
   * Optional PostureModule wrapper for dual-publish into the GlobalWorkspace.
   * When set, this runner additionally emits CognitiveSignals alongside its
   * existing WorkStream / DialecticChannel writes. No-op when absent.
   */
  postureModule?: PostureModule
  /**
   * Optional HelixTelemetry sink. When set, signal submits are recorded for
   * per-session metrics and cross-posture correlation tracing.
   */
  telemetry?: HelixTelemetry
  /**
   * Optional Aurora reference. When set, posture reasoning text is piped
   * through `aurora.observeReasoning()` at turn boundaries so Aurora's
   * mental-state graph grows during the session and other postures see
   * a Thalamus context slice informed by collective reasoning.
   */
  aurora?: Aurora
  /**
   * Optional HelixJournal. When set alongside Aurora, `aurora.observe`
   * entries are appended so the observation cadence appears in the
   * session timeline.
   */
  journal?: HelixJournal
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
  private readonly contextChunkIndex?: import('./context-chunk-index.js').ContextChunkIndex
  private readonly onWorkUnit?: (wu: WorkUnit, iteration: number) => void
  private readonly onStreamActivity?: (event: StreamActivityEvent) => void
  private readonly flexToolAccess?: import('../constellation/types.js').ToolAccessLevel
  private readonly toolProfile?: import('./helix-pipeline.js').HelixToolProfile
  private readonly toolFilter?: { allow?: string[]; deny?: string[] }
  private readonly postureModule?: PostureModule
  private readonly telemetry?: HelixTelemetry
  private readonly aurora?: Aurora
  private readonly journal?: HelixJournal

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
  // Drift detection for shell commands
  private driftDetector: DriftDetector = new DriftDetector()
  // TestLock — sealed test paradigm for enforcing test-first discipline
  private testLock: TestLock

  // signal_done data — stored so buildPostureResult can return the actual conclusion
  private signalDoneConclusion?: string
  private signalDoneConfidence?: number
  private signalDoneKeyPoints?: string[]

  // Conversation persistence turn counter
  private conversationTurnIndex = 0

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
      thalamus: opts.thalamus,
    })
    this.role = opts.role
    this.workStream = opts.workStream
    this.dialecticChannel = opts.dialecticChannel
    this.researchSpawner = opts.researchSpawner
    this.unityStatusThresholds = opts.unityStatusThresholds
    this.brainstem = opts.brainstem
    this.contextChunkIndex = opts.contextChunkIndex
    this.onWorkUnit = opts.onWorkUnit
    this.onStreamActivity = opts.onStreamActivity
    this.flexToolAccess = opts.flexToolAccess
    this.toolProfile = opts.toolProfile
    this.toolFilter = opts.toolFilter
    this.postureModule = opts.postureModule
    this.telemetry = opts.telemetry
    this.aurora = opts.aurora
    this.journal = opts.journal
    this.store = opts.store

    // Wire TestLock with persistence callbacks
    const persistence: TestLockPersistence | undefined = opts.store && opts.sessionId
      ? {
          onSeal: (spec) => {
            opts.store!.saveTestLock(opts.sessionId!, {
              specId: spec.specId,
              description: spec.description,
              testFile: spec.testFile,
              testCommand: spec.testCommand,
              expectedOutcome: spec.expectedOutcome,
              severity: spec.severity,
              contentHash: spec.contentHash,
              sealedBy: spec.sealedBy,
              sealedAt: spec.sealedAt,
              verificationStatus: spec.verificationStatus,
              verifications: spec.verificationAttempts,
            })
          },
          onVerify: (specId, verificationStatus, verifications) => {
            opts.store!.updateTestLockVerification(opts.sessionId!, specId, verificationStatus, verifications)
          },
        }
      : undefined
    this.testLock = new TestLock(persistence)

    // Restore TestLock state from DB if available (crash recovery)
    if (opts.store && opts.sessionId) {
      try {
        const savedLocks = opts.store.getTestLocks(opts.sessionId)
        if (savedLocks.length > 0) {
          this.testLock.restore(savedLocks.map(row => ({
            specId: row.specId,
            description: row.description,
            testFile: row.testFile,
            testCommand: row.testCommand,
            expectedOutcome: row.expectedOutcome,
            severity: row.severity as 'critical' | 'important' | 'advisory',
            contentHash: row.contentHash,
            sealedBy: row.sealedBy,
            sealedAt: row.sealedAt,
            verificationStatus: row.verificationStatus as 'pending' | 'passed' | 'failed',
            verificationAttempts: row.verifications as TestLockVerification[],
          })))
          this.logger.info('Restored TestLock state from DB', { count: savedLocks.length })
        }
      } catch (err) {
        this.logger.warn('Failed to restore TestLock state', { error: String(err) })
      }
    }
  }



  protected getAgentLabel(): string { return this.role }
  protected getSourceLabel(): string { return `helix:${this.role}` }
  protected getTriggerLabel(): string { return 'helix' }

  /**
   * Phase C broadcast-consumption helper. Pops queued GlobalWorkspace
   * signals that landed in this posture's PostureModule since the last
   * call, formats them as a markdown block, and appends that block as a
   * user message so the next inference sees it.
   *
   * Legacy channel reads (WorkStream / DialecticChannel) continue to fire
   * in parallel during Phase C — both sources currently drive the runner.
   * Phase G will delete the legacy path once workspace coverage is proven.
   *
   * No-op when brainIntegration is off or the queue is empty.
   */
  private injectWorkspaceBroadcasts(): void {
    if (!this.postureModule) return
    const signals = this.postureModule.drainBroadcasts()
    if (signals.length === 0) return

    const lines: string[] = ['## GlobalWorkspace signals (from other postures)']
    for (const sig of signals) {
      const posture = String(sig.metadata?.posture ?? sig.source)
      const kind = String(sig.metadata?.kind ?? sig.type)
      const correlation = sig.metadata?.correlation
      const correlationTag = typeof correlation === 'string' && correlation.length > 0
        ? ` [corr:${correlation}]`
        : ''
      const preview = (sig.content ?? '').slice(0, 400)
      lines.push(`- **${posture}** · ${kind}${correlationTag}: ${preview}`)
    }

    this.messages.push({ role: 'user', content: lines.join('\n') })
    this.logger.debug('Injected workspace broadcasts', {
      role: this.role,
      count: signals.length,
    })
  }

  /**
   * Phase E — pipe posture reasoning text through Aurora so the unified
   * mental-state graph grows while the session runs. No-op when Aurora
   * isn't attached. Emits an `aurora.observe` journal entry when a journal
   * is wired alongside Aurora.
   */
  private observePostureReasoning(text: string): void {
    if (!this.aurora || !text || text.length < 20) return
    try {
      const update = this.aurora.observeReasoning(text)
      if (this.journal && this.postureModule) {
        this.journal.append({
          sessionId: this.postureModule.sessionId,
          eventType: 'aurora.observe',
          postureId: this.postureModule.name,
          payload: {
            conceptsExtracted: update.extractedConcepts?.length ?? 0,
            shiftType: update.shift?.type,
            momentumConfidence: update.momentum?.confidence,
          },
        })
      }
    } catch (err) {
      this.logger.debug('aurora.observeReasoning failed', { error: String(err) })
    }
  }

  /**
   * Phase A dual-publish helper. Emits a CognitiveSignal into the
   * GlobalWorkspace when a PostureModule is wired. Safe to call
   * unconditionally — returns false when brain-integration is off.
   */
  private publishSignal(
    type: SignalType,
    content: string,
    opts: PostureSignalOpts = {},
  ): boolean {
    if (!this.postureModule) return false
    try {
      const ignited = this.postureModule.publish(type, content, opts)
      this.telemetry?.recordSignalSubmit({
        sessionId: this.postureModule.sessionId,
        posture: this.postureModule.role,
        signalType: type,
        correlation: opts.correlation,
        recipient: opts.recipient,
        kind: opts.kind,
        ignited,
      })
      return ignited
    } catch (err) {
      this.logger.debug('[helix] dual-publish failed', { error: String(err), type })
      return false
    }
  }

  /**
   * Stream chunk hook — forward token stream events to the Brainstem/Corpus
   * via the onStreamActivity callback. This gives real-time visibility into
   * what the LLM is producing, not just tool call results.
   */

  /**
   * Override pushMessage to persist conversations to HelixStore for post-mortem.
   */
  protected override pushMessage(msg: import('../../../types/runtime.js').Message): void {
    super.pushMessage(msg)
    // Persist to HelixStore for forensic analysis
    if (this.store) {
      try {
        const turnIdx = this.conversationTurnIndex++
        this.store.saveConversation(
          this.sessionId, this.role, turnIdx,
          msg.role, msg.content,
        )
      } catch {
        // Non-fatal — conversation persistence must never break the runner
      }
    }
  }

  /**
   * Stream chunk handler — forwards real-time streaming tokens to Brainstem
   * via the onStreamActivity callback.
   */
  protected override onStreamChunk(tokensSoFar: number, textAccumulated: string, hasToolUse: boolean): void {

    // Pass the most recent 3000 chars so the brainstem can buffer live stream content
    // for heartbeat prompts. Each event is a growing slice of the current LLM iteration —
    // receivers should overwrite (not append) their buffer on each event.
    const snippet = textAccumulated.length > 3000
      ? textAccumulated.slice(-3000)
      : textAccumulated

    this.onStreamActivity?.({
      posture: this.role,
      tokensSoFar,
      isReasoning: !hasToolUse && textAccumulated.length > 0,
      textSnippet: snippet,
      hasToolUse,
      timestamp: Date.now(),
    })
  }



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

        // Phase C — pull cross-posture signals from the GlobalWorkspace
        // (reviewer findings/challenges, suggestion nudges, etc.). No-op
        // when brainIntegration is off.
        this.injectWorkspaceBroadcasts()

        // Backpressure — wait if reviewers are falling behind
        if (this.workStream.shouldApplyBackpressure()) {
          this.logger.debug('Unity backpressure — waiting for reviewers to catch up')
          await this.workStream.awaitBackpressureRelief()
        }

        // Context pressure management
        if (this.contextChunkIndex) { this.manageContextWithChunkIndex() } else { this.manageContextPressure() }

        // Stream inference
        const result = await this.streamInferenceWithRetry(tools)
        this.tokensUsed += result.tokensUsed
        // WorkStream tracks iterations for yang/yin reviewers
        this.workStream.recordIteration(this.role as any, result.tokensUsed)
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
            this.publishSignal('observation', textContent.slice(0, 2000), {
              kind: 'work-unit',
              correlation: (reasoningUnit as any)?.id,
              extra: {
                iteration: this.iterationCount,
                textOnly: true,
              },
            })
            this.observePostureReasoning(textContent)
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
        this.publishSignal(
          'observation',
          ((workUnit as any)?.reasoning ?? '').slice(0, 2000) || `work unit #${(workUnit as any)?.id}`,
          {
            kind: 'work-unit',
            correlation: (workUnit as any)?.id,
            extra: {
              iteration: this.iterationCount,
              toolCount: toolCalls.length,
              filesModified: ((workUnit as any)?.filesModified ?? []).length,
            },
          },
        )
        this.observePostureReasoning(((workUnit as any)?.reasoning ?? '') as string)
        this.workUnitsProduced++
        this.onWorkUnit?.(workUnit as any, this.iterationCount)

        // Inject nudges, Brainstem guidance, and Synapse guidance into tool results
        const enrichedResults = this.injectBrainstemGuidance(
          this.injectSynapseGuidance(
            this.injectNudgeMessages(toolResults)
          )
        )

        this.pushMessage({ role: 'assistant', content: result.contentBlocks })
        this.pushMessage({ role: 'user', content: enrichedResults })
      }

      this.workStream.signalWorkerDone()
      return this.buildPostureResult(startTime)
    } catch (err) {
      this.workStream.signalWorkerDone()
      return this.buildErrorResult(startTime, err)
    }
  }



  /**
   * Run as a reviewer (Yang or Yin).
   *
   * Active investigation mode: the reviewer independently investigates the goal
   * using read-only tools, posts findings and challenges through the dialectic,
   * and uses Unity's work units as investigation seeds (not as the sole trigger).
   *
   * Loop structure:
   *   1. Run LLM inference — reviewer investigates independently
   *   2. Process tool calls (read-only investigation + dialectic meta-tools)
   *   3. Inject new work units from Unity as additional context
   *   4. Inject dialectic messages from the other reviewer
   *   5. Inject brainstem guidance when available
   *   6. Continue until concluded or cancelled
   */
  async runAsReviewer(goal: string, context?: string): Promise<HelixPostureResult> {
    const startTime = Date.now()
    this.logger.info(`${this.role} starting as active reviewer`, { goal, maxIterations: this.posture.maxIterations })

    try {
      await initializeOptionalTools()
      this.messages = this.buildInitialMessages(goal, context, this.role)
      const tools = this.buildToolSchemas(this.role)

      // Posture independence: reviewers start their own investigation immediately.
      // Previously we waited 2s for Unity to seed work units, but reviewers now run
      // their own agenda — no need to gate on Unity's startup.
      this.injectAvailableWorkUnits()

      while (!this.concluded && !this.cancelled) {
        this.iterationCount++
        if (this.iterationCount > this.maxIterations) {
          this.logger.warn(`${this.role} hit max iterations`, { maxIterations: this.maxIterations })
          break
        }

        // Phase C — pull cross-posture signals from the GlobalWorkspace.
        // Reviewers see Unity's work units and the other reviewer's
        // findings/challenges here when brainIntegration is on.
        this.injectWorkspaceBroadcasts()

        // Posture independence: reviewers no longer auto-exit when Unity finishes.
        // Each posture decides its own completion via signal_conclusion. Unity finishing
        // is just one signal among many — Yang/Yin keep investigating until satisfied.
        // The legacy "Unity done → reviewers exit" early-exit logic was removed because
        // it caused reviewers to bail after just 2-5 iterations even when they hadn't
        // produced meaningful findings. Reviewers now run their full investigation loop
        // until they call signal_conclusion or hit maxIterations.
        if (this.workStream.isWorkerDone() && !(this.workStream instanceof HelixWorkStream)) {
          // Legacy WorkStream still uses the old reviewed-all check (back-compat path).
          const allWUs = this.workStream.getAllWorkUnits()
          const allReviewed = allWUs.every(wu => this.reviewedWorkUnitIds.has(wu.id))
          if ((allReviewed && allWUs.length > 0) || (allWUs.length === 0 && this.iterationCount > 1)) {
            this.logger.info(`${this.role} — Unity done, all work units reviewed, concluding (legacy path)`)
            break
          }
        }


        // Inject any new work units from Unity as context enrichment
        this.injectAvailableWorkUnits()

        // Inject dialectic messages from the other reviewer
        if (this.dialecticChannel) {
          this.injectDialecticMessages()
        }

        // Inject UnityStatus for situational awareness
        this.injectUnityStatusAsMessage()

        // Inject brainstem cognitive summary and pending guidance proposals.
        // More frequent when proposals need votes (every iteration),
        // otherwise periodic (every 5 iterations).
        const hasPendingProposals = this.brainstem?.getPendingProposals(this.role as 'yang' | 'yin').length ?? 0
        if (hasPendingProposals > 0 || this.iterationCount % 5 === 0) {
          this.injectCognitiveSummary()
        }

        // Context pressure management
        if (this.contextChunkIndex) { this.manageContextWithChunkIndex() } else { this.manageContextPressure() }

        const result = await this.streamInferenceWithRetry(tools)
        this.tokensUsed += result.tokensUsed
        // WorkStream tracks iterations for yang/yin reviewers
        this.workStream.recordIteration(this.role as any, result.tokensUsed)
        this.onActivity?.()

        if (!result.hasToolUse && !this.concluded) {
          // No tool use — nudge towards active investigation
          this.messages.push({
            role: 'user',
            content: this.role === 'yang'
              ? 'You should actively investigate the goal using your tools. Look for promising approaches, validate assumptions, and post findings through the dialectic. Use signal_conclusion when your review is complete.'
              : 'You should actively stress-test the work by reading files, checking edge cases, and looking for risks. Post challenges through the dialectic when you find issues. Use signal_conclusion when your review is complete.',
          })
          continue
        }

        // Extract and process tool calls
        const toolCalls = this.extractToolCalls(result.contentBlocks)
        if (toolCalls.length === 0) continue

        const toolResults = await this.processToolCalls(toolCalls)
        this.onActivity?.()

        // Posture independence: reviewers also produce work units from their
        // independent investigations. The Brainstem and Corpus see Yang/Yin's
        // findings as concrete units alongside Unity's, not just dialectic chatter.
        const reviewerWorkUnit = this.captureWorkUnit(result, toolCalls, toolResults)
        this.workStream.postWorkUnit(reviewerWorkUnit as any)
        this.publishSignal(
          'observation',
          ((reviewerWorkUnit as any)?.reasoning ?? '').slice(0, 2000) || `${this.role} work unit #${(reviewerWorkUnit as any)?.id}`,
          {
            kind: 'work-unit',
            correlation: (reviewerWorkUnit as any)?.id,
            extra: {
              iteration: this.iterationCount,
              toolCount: toolCalls.length,
              posture: this.role,
            },
          },
        )
        this.observePostureReasoning(((reviewerWorkUnit as any)?.reasoning ?? '') as string)
        this.workUnitsProduced++
        this.onWorkUnit?.(reviewerWorkUnit as any, this.iterationCount)

        // Inject dialectic messages into tool results
        const enrichedResults = this.injectDialecticIntoResults(toolResults)

        // Primary UnityStatus injection — piggyback on existing tool results (zero extra LLM calls)
        const statusResults = this.injectUnityStatusIntoResults(enrichedResults)

        // Inject Synapse guidance from previous collect_thoughts calls
        const withSynapse = this.injectSynapseGuidance(statusResults)

        // Inject Brainstem guidance (primary cognitive organizer)
        const finalResults = this.injectBrainstemGuidance(withSynapse)

        this.pushMessage({ role: 'assistant', content: result.contentBlocks })
        this.pushMessage({ role: 'user', content: finalResults })
      }

      return this.buildPostureResult(startTime)
    } catch (err) {
      return this.buildErrorResult(startTime, err)
    }
  }

  /**
   * Drain all available work units from the WorkStream and inject them as context.
   * Non-blocking: returns immediately if no work units are available.
   * Uses per-reviewer broadcast cursors (HelixWorkStream) when available.
   */
  private injectAvailableWorkUnits(): void {
    try {
      const allWUs = this.workStream.getAllWorkUnits()
      let injectedCount = 0

      for (const workUnit of allWUs) {
        if (this.reviewedWorkUnitIds.has(workUnit.id)) continue
        this.reviewedWorkUnitIds.add(workUnit.id)
        this.workStream.markWorkUnitReviewed(workUnit.id)

        this.messages.push({
          role: 'user',
          content: this.formatWorkUnitForReview(workUnit),
        })
        injectedCount++
      }

      if (injectedCount > 0) {
        this.logger.debug(`${this.role} — injected ${injectedCount} new work unit(s) as context`)
      }
    } catch {
      // Work unit injection failure is non-fatal
    }
  }

  /**
   * Inject brainstem's cognitive summary and pending guidance proposals.
   * The brainstem maintains a running model of discoveries, decisions, blockers,
   * quality trajectory, and detected patterns. Injecting this periodically
   * gives reviewers awareness of what the brainstem has identified.
   *
   * Also injects pending guidance proposals that need this reviewer's vote.
   */
  private injectCognitiveSummary(): void {
    if (!this.brainstem) return

    const parts: string[] = []

    // Cognitive model summary
    const summary = this.brainstem.getCognitiveSummary()
    if (summary) {
      parts.push(summary)
    }

    // Pending guidance proposals that need this reviewer's vote
    const pendingProposals = this.brainstem.getPendingProposals(this.role as 'yang' | 'yin')
    if (pendingProposals.length > 0) {
      const proposalLines = pendingProposals.map(p =>
        `- [${p.id}] (${p.urgency}): "${p.text.slice(0, 200)}"${p.text.length > 200 ? '...' : ''}` +
        `\n  Other reviewer: ${p.votes.yang && this.role === 'yin' ? (p.votes.yang.approved ? 'approved' : 'rejected') : p.votes.yin && this.role === 'yang' ? (p.votes.yin.approved ? 'approved' : 'rejected') : 'not yet voted'}`,
      )
      parts.push(
        `## Guidance Proposals Awaiting Your Vote\n\n` +
        `The brainstem has proposed the following guidance for the builder. ` +
        `Both reviewers must approve before it reaches Unity. ` +
        `Use approve_guidance(proposal_id, reason) or reject_guidance(proposal_id, reason).\n\n` +
        proposalLines.join('\n'),
      )
    }

    if (parts.length === 0) return

    this.messages.push({
      role: 'user',
      content: `--- Brainstem Context ---\n\n${parts.join('\n\n')}\n\n---`,
    })

    this.logger.debug(`${this.role} — injected brainstem context`, {
      hasSummary: !!summary,
      pendingProposals: pendingProposals.length,
    })
  }

  /** @deprecated Mentor path removed — use Brainstem instead. Retained for backward compat. */
  async runAsMentor(goal: string, context?: string): Promise<HelixPostureResult> {
    const startTime = Date.now()
    this.logger.info('mentor starting as moderator (DEPRECATED)', { goal, maxIterations: this.posture.maxIterations })

    try {
      await initializeOptionalTools()
      // Cast to any for backward compat — 'mentor' removed from HelixRole type
      this.messages = this.buildInitialMessages(goal, context, 'mentor' as any)
      const tools = this.buildToolSchemas('mentor' as any)

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

        if (this.contextChunkIndex) { this.manageContextWithChunkIndex() } else { this.manageContextPressure() }

        const result = await this.streamInferenceWithRetry(tools)
        this.tokensUsed += result.tokensUsed
        this.onActivity?.()

        if (!result.hasToolUse && !this.concluded) {
          if (unityDone) {
            this.messages.push({
              role: 'user',
              content: 'The worker appears done. If there is enough information, call mentor_synthesize now.',
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

        this.pushMessage({ role: 'assistant', content: result.contentBlocks })
        this.pushMessage({ role: 'user', content: enrichedResults })
      }

      return this.buildPostureResult(startTime)
    } catch (err) {
      return this.buildErrorResult(startTime, err)
    }
  }



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

      // Notify brainstem when Unity posts to high-signal channels
      // so it can trigger a heartbeat annotation capturing the updated context
      if (this.brainstem && this.role === 'unity') {
        for (const tc of blackboardCalls) {
          if (tc.name === 'bb_post') {
            const channel = (tc.input as Record<string, unknown>)?.channel as string
            if (channel && ['decisions', 'findings', 'concerns', 'bugs'].includes(channel)) {
              const content = ((tc.input as Record<string, unknown>)?.content as string) ?? ''
              this.brainstem.onSignificantBlackboardPost(channel, content)
            }
          }
        }
      }
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
      const argsSummary = this.extractArgsSummary(tc.name, tc.input)
      this.workStream.recordToolCall(this.role as any, tc.name, false, argsSummary)
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
      // Guidance proposal gate (Yang/Yin)
      case 'approve_guidance': return this.handleApproveGuidance(input)
      case 'reject_guidance': return this.handleRejectGuidance(input)
      // Edit proposal tools (Yang/Yin)
      case 'propose_edit': return this.handleProposeEdit(input)
      case 'review_edit_proposal': return this.handleReviewEditProposal(input)
      // TestLock tools (Sealed Test Paradigm)
      case 'seal_test_spec': return this.handleSealTestSpec(input)
      case 'verify_test_lock': return this.handleVerifyTestLock(input)
      case 'list_test_locks': return this.handleListTestLocks()
      // Conclusion — tool schema is signal_conclusion (from Lumen dialectic-tools)
      case 'signal_conclusion': return this.handleSignalConclusion(input)
      default: return `Unknown meta-tool: ${name}`
    }
  }


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

    // TestLock gate — check if sealed test specs are satisfied
    const lockCheck = this.testLock.canComplete()
    if (!lockCheck.allowed) {
      const blockerList = lockCheck.blockers
        .map(b => `  - ${b.specId}: ${b.description} (${b.severity}, ${b.verificationStatus})`)
        .join('\n')
      return (
        `BLOCKED by TestLock — ${lockCheck.blockers.length} sealed test spec(s) have not been verified as passing.\n` +
        `You must run the test commands and call verify_test_lock for each before signal_done.\n\n` +
        `Blocking specs:\n${blockerList}\n\n` +
        `Use list_test_locks for full details.`
      )
    }

    this.concluded = true
    this.signalDoneConclusion = conclusion
    this.signalDoneConfidence = confidence
    this.signalDoneKeyPoints = keyPoints
    this.workStream.recordRoleConclusion(this.role as any, false)

    const lockSummary = this.testLock.getSummary()
    const lockNote = lockSummary.total > 0
      ? ` All ${lockSummary.total} sealed test spec(s) verified.`
      : ''

    return `Work complete. Conclusion recorded.${lockNote} Yang and Yin will do a final review pass.`
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


  // --- TestLock Handlers (Sealed Test Paradigm) ---

  private handleSealTestSpec(input: Record<string, unknown>): string {
    // WHY: Only Yin (stress-tester) should seal specs.
    // Yang could bypass test-first discipline by sealing trivial specs.
    if (this.role !== 'yin') {
      return 'ERROR: Only Yin (stress-tester) can seal test specs. Yang and Unity cannot seal tests — this enforces separation of concerns.'
    }

    const specId = String(input.spec_id ?? '')
    const description = String(input.description ?? '')
    const testCommand = String(input.test_command ?? '')
    const severity = String(input.severity ?? 'important') as 'critical' | 'important' | 'advisory'

    if (!specId || !description || !testCommand) {
      return 'ERROR: spec_id, description, and test_command are required.'
    }

    const result = this.testLock.seal({
      specId,
      description,
      testFile: input.test_file ? String(input.test_file) : undefined,
      testCommand,
      expectedOutcome: input.expected_outcome ? String(input.expected_outcome) : undefined,
      severity,
      sealedBy: this.role,
    })

    if (!result.sealed) {
      return `ERROR: ${result.error}`
    }

    this.logger.info('Test spec sealed', {
      specId,
      severity,
      hash: result.spec!.contentHash.slice(0, 16),
      sealedBy: this.role,
    })

    return (
      `Test spec "${specId}" sealed successfully.\n` +
      `Hash: ${result.spec!.contentHash.slice(0, 16)}...\n` +
      `Severity: ${severity}${severity !== 'advisory' ? ' (BLOCKS signal_done until verified)' : ' (advisory, does not block)'}\n` +
      `Unity must run: ${testCommand}\n` +
      `Then call verify_test_lock with the result.`
    )
  }

  private handleVerifyTestLock(input: Record<string, unknown>): string {
    // WHY: Only Unity (the integrator) should verify — it's the one running tests.
    // Allowing Yin to self-verify would defeat the purpose of separation.
    if (this.role !== 'unity') {
      return 'ERROR: Only Unity (integrator) can verify test locks. Yin seals, Unity verifies — this enforces separation of concerns.'
    }

    const specId = String(input.spec_id ?? '')
    const passed = input.passed === true || input.passed === 'true'
    const output = input.output ? String(input.output) : undefined
    const notes = input.notes ? String(input.notes) : undefined

    if (!specId) {
      return 'ERROR: spec_id is required.'
    }

    const result = this.testLock.verify(specId, {
      passed,
      output,
      notes,
      verifiedBy: this.role,
    })

    if (!result.verified) {
      return `ERROR: ${result.error}`
    }

    const spec = result.spec!
    const lockCheck = this.testLock.canComplete()

    this.logger.info('Test lock verification', {
      specId,
      passed,
      remainingBlockers: lockCheck.blockers.length,
    })

    if (passed) {
      return (
        `Test spec "${specId}" verified as PASSING.\n` +
        `${lockCheck.allowed ? 'All sealed test specs satisfied — signal_done is now unblocked.' : `${lockCheck.blockers.length} blocking spec(s) remain.`}`
      )
    } else {
      return (
        `Test spec "${specId}" FAILED verification.\n` +
        `You need to fix the code and try again.\n` +
        `Command: ${spec.testCommand}\n` +
        `${output ? `Output: ${output.slice(0, 500)}` : ''}`
      )
    }
  }

  private handleListTestLocks(): string {
    return this.testLock.formatSummary()
  }


  private handleShareFinding(input: Record<string, unknown>): string {
    if (!this.dialecticChannel) return 'ERROR: No dialectic channel available.'

    const finding = String(input.finding ?? '')
    const evidence = input.evidence ? String(input.evidence) : undefined
    const tags = Array.isArray(input.tags) ? input.tags.map(String) : []

    const id = this.dialecticChannel.postFinding(this.role as any, finding, evidence, tags)
    this.findingsShared++
    this.publishSignal('observation', finding.slice(0, 2000), {
      kind: 'finding',
      correlation: String(id),
      extra: { findingId: String(id), tags, evidence: evidence?.slice(0, 500) },
    })

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
      this.publishSignal('tension', counterargument.slice(0, 2000), {
        kind: 'challenge',
        correlation: findingId,
        extra: { challengeId: String(id), findingId, evidence: evidence?.slice(0, 500) },
      })

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
      this.publishSignal('insight', (reason ?? `concession to #${challengeId}`).slice(0, 2000), {
        kind: 'concession',
        correlation: challengeId,
        extra: { challengeId, reason: reason?.slice(0, 500) },
      })

      if (reason) {
        this.blackboard?.autoDraftFromConcession(this.role, challengeId, reason, challengeId)
      }

      return `Concession recorded for challenge #${challengeId}. This creates a convergence point.`
    } catch (err) {
      return `Concession failed: ${err instanceof Error ? err.message : String(err)}`
    }
  }


  private handleReviewProgress(): string {
    const stats = this.workStream.getStats()
    const allWUs = this.workStream.getAllWorkUnits()
    const reviewed = allWUs.filter(wu => this.reviewedWorkUnitIds.has(wu.id))
    const unreviewed = allWUs.filter(wu => !this.reviewedWorkUnitIds.has(wu.id))
    const unityDone = this.workStream.isWorkerDone()

    const lines: string[] = [
      `## Pipeline Progress`,
      `Worker status: ${unityDone ? 'DONE' : 'WORKING'}`,
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

  private handleApproveGuidance(input: Record<string, unknown>): string {
    if (!this.brainstem) return 'No brainstem configured — guidance proposals are not available.'
    const proposalId = String(input.proposal_id ?? '')
    const reason = String(input.reason ?? '')
    if (!proposalId) return 'Error: proposal_id is required'
    if (!reason) return 'Error: reason is required — explain why this guidance should reach the builder'
    return this.brainstem.voteOnProposal(proposalId, this.role as 'yang' | 'yin', true, reason)
  }

  private handleRejectGuidance(input: Record<string, unknown>): string {
    if (!this.brainstem) return 'No brainstem configured — guidance proposals are not available.'
    const proposalId = String(input.proposal_id ?? '')
    const reason = String(input.reason ?? '')
    if (!proposalId) return 'Error: proposal_id is required'
    if (!reason) return 'Error: reason is required — explain why this guidance should NOT reach the builder'
    return this.brainstem.voteOnProposal(proposalId, this.role as 'yang' | 'yin', false, reason)
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
      this.publishSignal('suggestion', content, {
        kind: 'nudge',
        recipient: 'unity',
        correlation: workUnitId,
        urgencyHint: severity === 'high' ? 0.2 : 0,
        extra: { severity, workUnitId },
      })
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
    this.publishSignal('observation', `[Investigation Request] ${area}: ${reason}`.slice(0, 2000), {
      kind: 'investigation-request',
      correlation: String(id),
      extra: { findingId: String(id), area, reason },
    })

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
    this.workStream.recordRoleConclusion(this.role as any, false)
    // Posture independence: signal coordinator that this reviewer is ready,
    // so HelixWorkStream.isTerminationConsensus reflects voluntary completion.
    if (this.workStream instanceof HelixWorkStream) {
      this.workStream.signalReviewerReady(this.role)
    }

    this.logger.info(`${this.role} review complete`, {
      conclusion: conclusion.slice(0, 100),
      confidence,
      nudgesSent: this.nudgesSent,
      findingsShared: this.findingsShared,
    })

    return 'Review complete. Your conclusion has been recorded.'
  }



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
          this.publishSignal('suggestion', `[Mentor Guidance] ${directive}`, {
            kind: 'mentor-nudge',
            recipient: 'unity',
            urgencyHint: severity === 'high' ? 0.2 : 0,
            extra: { severity, source: 'mentor-steer' },
          })
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
        this.publishSignal('warning', `[Mentor Flag: ${issueType}] ${issue}`, {
          kind: 'mentor-flag',
          recipient: 'unity',
          urgencyHint: 0.25,
          extra: { issueType, source: 'mentor-flag' },
        })
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



  private buildInitialMessages(goal: string, context: string | undefined, role: HelixRole): Message[] {
    // WHY: The [session:] marker lets CentralizedProvider.extractSessionId()
    // give each Helix posture its own deduplication key. Without it, parallel
    // Helix branches with similar goals hash to the same sessionId and trigger
    // "Request already in progress" errors that kill Yin/Yang postures.
    // This matches the pattern used by DyadPostureRunner and LumenPostureRunner.
    const messages: Message[] = [
      { role: 'system', content: `[session:${this.sessionId}-${role}]\n\n${this.posture.systemPrompt}` },
    ]

    let userContent = `## Goal\n\n${goal}`

    if (context) {
      userContent += `\n\n## Context\n\n${context}`
    }

    if (role === 'unity') {
      userContent += '\n\n## Instructions\n\nBegin implementation work now. ' +
        'Read the goal carefully, then start making progress using the available tools. ' +
        'Yang and Yin are also investigating independently and will share findings via the dialectic. ' +
        'Call signal_done when your integration work is complete.'
    } else if (role === 'yang') {
      userContent += '\n\n## Instructions\n\nYou are an INDEPENDENT WORKER, not just a reviewer. ' +
        'Investigate the goal yourself with full energy — explore the problem space, generate options, ' +
        'validate assumptions by reading code and running read-only tools. ' +
        'Produce concrete findings, not generic observations. ' +
        'Cross-pollinate with Unity and Yin via the dialectic (share_finding, challenge, concede). ' +
        'Do NOT wait for Unity to finish before doing real work — start your own investigation immediately. ' +
        'Call signal_conclusion ONLY when you have produced substantial findings and are genuinely satisfied with your investigation.'
    } else {
      // yin
      userContent += '\n\n## Instructions\n\nYou are an INDEPENDENT WORKER, not just a reviewer. ' +
        'Investigate the goal yourself with critical energy — probe for risks, edge cases, and contradictions. ' +
        'Read code, audit assumptions, surface what could break. ' +
        'Produce concrete findings, not generic concerns. ' +
        'Cross-pollinate with Unity and Yang via the dialectic (share_finding, challenge, concede). ' +
        'Do NOT wait for Unity to finish before doing real work — start your own audit immediately. ' +
        'Call signal_conclusion ONLY when you have produced substantial findings and are genuinely satisfied with your audit.'
    }

    messages.push({ role: 'user', content: userContent })

    return messages
  }

  protected override isToolAllowed(name: string): boolean {
    const accessLevel = this.flexToolAccess ?? (this.role === 'unity' ? 'full' : 'read-only')
    const hasFullAccess = accessLevel === 'full'
    if (hasFullAccess) return true
    const hasMemoryAccess = accessLevel === 'read-only+memory'
    if (isReadOnlyTool(name, this.toolRegistry)) return true
    if (hasMemoryAccess && isMemoryTool(name)) return true
    return false
  }

  private buildToolSchemas(role: HelixRole): NonNullable<CompletionOpts['tools']> {
    const tools: NonNullable<CompletionOpts['tools']> = []

    // Add role-specific meta-tools (filtered by tool profile)
    tools.push(...getHelixToolSchemas(role, this.toolProfile))

    // Add blackboard tools (only when using 'full' profile — hard cut for focused profiles)
    if (!this.toolProfile || this.toolProfile === 'full') {
      tools.push(...this.getBlackboardSchemas())
    }

    // Add plan tools (only when using 'full' profile)
    if (this.planHandler && (!this.toolProfile || this.toolProfile === 'full')) {
      tools.push(...getPlanToolSchemas(role))
    }

    // Add report tools (only when using 'full' profile)
    if (REPORT_TOOLS.length > 0 && (!this.toolProfile || this.toolProfile === 'full')) {
      tools.push(...REPORT_TOOLS)
    }

    // Add real tools (filtered by access level)
    if (this.toolRegistry) {
      // WHY: Use flexToolAccess from posture config when available, falling back to
      // role-based heuristic. This lets templates define per-posture access levels
      // (e.g., 'read-only+memory' for reviewers) instead of hardcoding role === 'unity'.
      const accessLevel = this.flexToolAccess ?? (role === 'unity' ? 'full' : 'read-only')
      const hasFullAccess = accessLevel === 'full'
      const hasMemoryAccess = accessLevel === 'read-only+memory' || hasFullAccess

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

        // Apply toolFilter allow/deny lists (from Constellation or Helix pipeline)
        if (this.toolFilter) {
          if (this.toolFilter.allow && !this.toolFilter.allow.includes(schema.name)) continue
          if (this.toolFilter.deny?.includes(schema.name)) continue
        }

        if (accessLevel === 'none') continue
        if (hasFullAccess || isReadOnlyTool(schema.name, this.toolRegistry) || (hasMemoryAccess && isMemoryTool(schema.name))) {
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



  /**
   * Inject low-severity nudges from reviewers into Unity's tool results.
   */
  private injectNudgeMessages(toolResults: ContentBlock[]): ContentBlock[] {
    const parts: string[] = []

    // Drain normal-priority reviewer feedback
    const drained = this.workStream.drainForRole('yang')
    if (drained) parts.push(drained)

    // Drain high-severity nudges inline (no separate acknowledgement loop)
    let highNudge = this.workStream.getNextHighNudge()
    while (highNudge) {
      parts.push(`⚠️ HIGH-PRIORITY from ${highNudge.from}: ${highNudge.content}`)
      this.workStream.acknowledgeNudge(highNudge.id, 'auto-acknowledged (inline injection)')
      highNudge = this.workStream.getNextHighNudge()
    }

    if (parts.length === 0) return toolResults

    return [
      ...toolResults,
      {
        type: 'text' as const,
        text: `\n--- Reviewer Feedback ---\n${parts.join('\n\n')}\n---`,
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
        text: `\n${guidance}`,
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
      content: `--- Internal Guidance (${guidance.urgency}) ---\n\n${guidance.text}\n\nAct on this before continuing.`,
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
        text: `\n--- Note: ${guidance.text}\n`,
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
      content: `--- Dialectic Channel ---\n\n${drained}\n\n---\n\nProcess these messages: challenge findings where there is disagreement, concede valid challenges, and share new findings.`,
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
        text: `\n--- Dialectic Channel ---\n${drained}\n---`,
      },
    ]
  }



  /** Track last UnityStatus injection to avoid spamming reviewers */
  private lastUnityStatusInjectionIteration = 0

  /** Minimum iterations between UnityStatus injections to prevent spam */
  private static readonly MIN_UNITY_STATUS_GAP_ITERATIONS = 3

  /**
   * Primary: Inject UnityStatus into tool results — piggybacks on existing responses.
   * Zero extra LLM requests. Called during reviewer tool-processing path.
   */
  private injectUnityStatusIntoResults(toolResults: ContentBlock[]): ContentBlock[] {
    if (this.role === 'unity') return toolResults

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
        text: `\n--- Status Signal ---\n${WorkStream.formatUnityStatus(status)}\n---`,
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
    if (this.role === 'unity') return false

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
      content: `--- Status Signal (Proactive) ---\n\n${WorkStream.formatUnityStatus(status)}\n\n---\n\n` +
        'The worker may be stuck or off-track. Review the status above and decide whether to ' +
        'investigate further (use request_investigation) or send a nudge (use send_nudge).',
    })

    return true
  }



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
      if (
        tc.name === 'write' || tc.name === 'edit' ||
        tc.name === 'write_file' || tc.name === 'file_artifact_write' ||
        tc.name === 'cassi_write' || tc.name === 'cassi_edit'
      ) {
        const path = String(tc.input?.path ?? tc.input?.filePath ?? 'unknown')
        filesModified.push({
          path,
          action: (tc.name === 'edit' || tc.name === 'cassi_edit') ? 'modified' : 'created',
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
      id: `wu-${this.role}-${this.workUnitsProduced + 1}`,
      iteration: this.iterationCount,
      reasoning: textBlocks.slice(0, 500) || `Iteration ${this.iterationCount}: ${toolCalls.length} tool calls`,
      toolCalls: toolCallSummaries,
      toolResults: toolResultSummaries,
      filesModified,
      timestamp: Date.now(),
      posture: this.role,
    }
  }

  /**
   * Capture a "reasoning-only" work unit when the LLM produces text without tool calls.
   * This gives the Brainstem visibility into the LLM's thinking between tool use.
   */
  private captureReasoningWorkUnit(text: string): WorkUnit {
    return {
      id: `wu-reasoning-${this.role}-${this.workUnitsProduced + 1}`,
      iteration: this.iterationCount,
      reasoning: text.slice(0, 1000),
      toolCalls: [],
      toolResults: [],
      filesModified: [],
      timestamp: Date.now(),
      posture: this.role,
    }
  }


  /**
   * Format a work unit for reviewer inspection.
   */
  private formatWorkUnitForReview(workUnit: WorkUnit): string {
    let msg = `--- New Work Unit (${workUnit.id}) ---\n\n`
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

    msg += `\n---\n\nInvestigate this work unit with read-only tools. ` +
      `Share findings with the other reviewer, and send nudges if there is actionable feedback.`

    return msg
  }



  /**
   * Manage context pressure using the ContextChunkIndex.
   * Instead of crude truncation, this indexes messages into addressable chunks
   * and applies intelligent eviction based on relevance scores.
   * Pinned chunks (e.g., important file reads marked by brainstem) survive eviction.
   *
   * Coordination with layered compaction:
   * - If layered compaction already ran (detected by <summary> in system message),
   *   pin the compacted summary chunk to prevent eviction.
   */
  private manageContextWithChunkIndex(): void {
    const cci = this.contextChunkIndex!

    // Index any new messages since last indexing
    cci.indexMessages(this.messages)

    // Coordination: If layered compaction already ran, pin the compacted summary
    // to prevent it from being evicted by the chunk index
    if (this.messages[0]?.role === 'system' &&
        typeof this.messages[0]?.content === 'string' &&
        this.messages[0].content.includes('<summary>')) {
      // Pin the first chunk (system message with compacted summary)
      const systemChunks = cci.getChunksForMessage(0)
      if (systemChunks.length > 0) {
        cci.pin([systemChunks[0]!.id])
      }
    }

    // Check if we need to evict — based on estimated token count
    const snap = cci.snapshot()
    const estimatedTokens = estimateTokens(snap.totalChars)
    const maxTokens = 100_000

    if (estimatedTokens > maxTokens * 0.85) {
      // Use atRiskChunks from snapshot — these are the lowest-scoring unpinned chunks
      const atRisk = snap.atRiskChunks
      const evictionTarget = Math.max(1, Math.floor(atRisk.length * 0.5))
      const toEvict = atRisk.slice(0, evictionTarget).map(c => c.id)

      if (toEvict.length > 0) {
        cci.evict(toEvict)
        cci.applyEvictions(this.messages)

        this.logger.debug('Context chunk eviction applied', {
          role: this.role,
          evicted: toEvict.length,
          pinned: snap.pinnedCount,
          remaining: snap.totalChunks - toEvict.length,
        })
      }
    }
  }

  /**
   * Pin context chunks by IDs — prevents them from being evicted.
   * Called by brainstem when it determines certain context is critical.
   */
  pinContextChunks(chunkIds: string[]): void {
    if (!this.contextChunkIndex) return
    this.contextChunkIndex.pin(chunkIds)
    this.logger.debug('Context chunks pinned', { role: this.role, count: chunkIds.length })
  }

  /**
   * Unpin context chunks — allows them to be evicted again.
   */
  unpinContextChunks(chunkIds: string[]): void {
    if (!this.contextChunkIndex) return
    this.contextChunkIndex.unpin(chunkIds)
  }

  /**
   * Boost relevance of specific chunks.
   */
  boostContextChunks(chunkIds: string[], delta: number): void {
    if (!this.contextChunkIndex) return
    this.contextChunkIndex.boost(chunkIds, delta)
  }

  /**
   * Get a compact snapshot of the context chunk state for brainstem consumption.
   */
  getContextSnapshot(): import('./context-chunk-index.js').ChunkIndexSnapshot | undefined {
    return this.contextChunkIndex?.snapshot()
  }



  private buildPostureResult(startTime: number): HelixPostureResult {
    const durationMs = Date.now() - startTime

    // Mentor path removed — Brainstem is the cognitive organizer
    // Legacy mentorSynthesis field retained for backward compat but unused

    return {
      conclusion: this.signalDoneConclusion || (this.concluded ? `${this.role} completed` : `${this.role} stopped`),
      confidence: this.signalDoneConfidence ?? 0.7,
      keyPoints: this.signalDoneKeyPoints ?? [],
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

  // WHY: The provider layer retries 429s up to 5 times, but can still exhaust its
  // budget when multiple branches compete for the same provider. This second
  // retry layer uses longer backoffs (10s+) to survive sustained rate limiting
  // without immediately failing the entire posture/pipeline/branch.
  private static readonly INFERENCE_MAX_RETRIES = 3
  private static readonly INFERENCE_BASE_DELAY_MS = 10_000
  private static readonly RATE_LIMIT_PATTERN = /429|rate.?limit|rate_limit_exceeded|resource.?exhausted|quota.?exceeded|throttl|retry after/i

  private async streamInferenceWithRetry(tools: any[]): Promise<ReturnType<typeof this.streamInference>> {
    for (let attempt = 0; ; attempt++) {
      try {
        return await this.streamInference(tools)
      } catch (err) {
        const msg = err instanceof Error ? err.message : String(err)
        const isRateLimit = HelixPostureRunner.RATE_LIMIT_PATTERN.test(msg)

        if (!isRateLimit || attempt >= HelixPostureRunner.INFERENCE_MAX_RETRIES) {
          throw err
        }

        // HOW: Exponential backoff with jitter — 10s, 20s, 40s base + random 0-5s
        const delayMs = HelixPostureRunner.INFERENCE_BASE_DELAY_MS * Math.pow(2, attempt) + Math.random() * 5_000
        this.logger.warn(`${this.role} inference rate-limited, retrying`, {
          attempt: attempt + 1,
          maxRetries: HelixPostureRunner.INFERENCE_MAX_RETRIES,
          delayMs: Math.round(delayMs),
          error: msg,
        })
        await new Promise(resolve => setTimeout(resolve, delayMs))
      }
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
