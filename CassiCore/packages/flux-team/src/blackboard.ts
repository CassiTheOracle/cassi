/**
 * Blackboard — Shared workspace for FluxTeam architecture.
 *
 * Provides structured communication channels, reactive subscriptions, and state management
 * for dynamic multi-agent teams. Replaces CellWorkspace with enhanced channel-based
 * communication and pattern-matching subscriptions.
 *
 * Features:
 *   - Five structured channels: findings, concerns, decisions, artifacts, requests
 *   - Reactive subscriptions with tag filtering
 *   - Scratchpad with TTL support (default 30 min)
 *   - Tool execution logging
 *   - Artifact tracking
 *   - Child results / parent context for hierarchy
 *   - Context assembly for Lumen sessions
 *   - Snapshot/restore for daemon restart persistence
 */

import { randomUUID } from 'crypto'
import type { ILogger } from '../../../types/interfaces.js'
import type { FileArtifactStore } from '../../file-artifact-store.js'
import type {
  BlackboardChannel,
  BlackboardEntry,
  BlackboardState,
  BlackboardSubscription,
  FluxScratchpadEntry,
  FluxToolRecord,
  ArtifactEntry,
  FluxCellResult,
  Plan,
  PlanStep,
  PlanStepStatus,
  Report,
  ReportSection,
  ReportSectionType,
  ReportSectionStatus,
  ReportQualityMetrics,
} from '../../../types/flux-team.js'
import type {
  PaginatedResult,
  ChannelSearchOptions,
  ScratchpadSearchOptions,
  ToolLogSearchOptions,
  ArtifactSearchOptions,
  PlanSearchOptions,
  ReportSearchOptions,
  CrossBoardSearchOptions,
  CrossBoardSearchResult,
  CrossBoardResultItem,
  BoardSearchResult,
  SearchableBoard,
  ChangeWindow,
  BoardChanges,
  BlackboardWatchResult,
  WatchSummary,
} from '../../../types/blackboard-search.js'
import {
  compilePattern,
  matchesAny,
  normalizeLimit,
  decodeCursor,
  encodeCursor,
  paginate,
  passesBaseFilters,
  decodeCompositeCursor,
  encodeCompositeCursor,
} from './blackboard-search.js'

// Constants

const CHANNEL_LIMIT = 500 // Max entries per channel (increased for large-scale teams)
const TOOL_LOG_LIMIT = 500 // Max tool records
const DEFAULT_SCRATCHPAD_TTL_MS = 30 * 60 * 1000 // 30 minutes

const CHANNELS: BlackboardChannel[] = [
  'findings',
  'concerns',
  'decisions',
  'artifacts',
  'requests',
  'bugs',
]

const ALL_SEARCHABLE_BOARDS: SearchableBoard[] = [
  'channel',
  'scratchpad',
  'toolLog',
  'artifact',
  'plan',
  'report',
]

// Blackboard

export class Blackboard {
  private readonly logger: ILogger
  private readonly cellId: string

  // Channel storage
  private readonly channels: Record<BlackboardChannel, BlackboardEntry[]>

  // Reactive subscriptions
  private readonly subscriptions: Map<string, BlackboardSubscription>
  private subscriptionCounter = 0

  // Scratchpad (key-value with TTL)
  private readonly scratchpad: Map<string, FluxScratchpadEntry>

  // Tool execution log
  private readonly toolLog: FluxToolRecord[]

  // Artifact tracking (path -> entry)
  private readonly artifacts: Map<string, ArtifactEntry>

  // Hierarchy support
  private readonly childResults: Map<string, FluxCellResult>
  private parentContext: string

  // Structured plan
  private plan: Plan | null

  // Incremental report
  private report: Report | null
  private reportSectionCounter = 0

  // Metadata
  private readonly createdAt: number
  private lastActivityAt: number
  private fileArtifactStore?: FileArtifactStore
  private artifactNamespace?: string
  private autoPersistArtifacts: boolean

  constructor(logger: ILogger, cellId: string) {
    this.logger = logger.child('blackboard')
    this.cellId = cellId

    // Initialize channels
    this.channels = {
      findings: [],
      concerns: [],
      decisions: [],
      artifacts: [],
      requests: [],
      bugs: [],
    }

    this.subscriptions = new Map()
    this.scratchpad = new Map()
    this.toolLog = []
    this.artifacts = new Map()
    this.childResults = new Map()
    this.parentContext = ''
    this.plan = null
    this.report = null

    this.createdAt = Date.now()
    this.lastActivityAt = Date.now()
    this.autoPersistArtifacts = true

    this.logger.debug('Blackboard created', { cellId })
  }

  setFileArtifactStore(store: FileArtifactStore, opts?: {
    namespace?: string
    autoPersist?: boolean
  }): void {
    this.fileArtifactStore = store
    this.artifactNamespace = opts?.namespace
    if (opts?.autoPersist !== undefined) this.autoPersistArtifacts = opts.autoPersist
  }

  getFileArtifactStore(): FileArtifactStore | undefined {
    return this.fileArtifactStore
  }

  getArtifactNamespace(): string | undefined {
    return this.artifactNamespace
  }

  getAutoPersistEnabled(): boolean {
    return this.autoPersistArtifacts
  }


  /**
   * Post an entry to a channel.
   * Notifies matching subscriptions after posting.
   *
   * @param channel - The channel to post to
   * @param entry - Entry content (id, timestamp, priority assigned automatically)
   * @returns The complete entry with generated fields
   */
  post(
    channel: BlackboardChannel,
    entry: Omit<BlackboardEntry, 'id' | 'timestamp' | 'channel'>,
  ): BlackboardEntry {
    const completeEntry: BlackboardEntry = {
      id: randomUUID(),
      channel,
      author: entry.author,
      content: entry.content,
      structured: entry.structured,
      priority: entry.priority ?? 0,
      tags: entry.tags ?? [],
      timestamp: Date.now(),
    }

    const channelEntries = this.channels[channel]
    channelEntries.push(completeEntry)

    // Enforce rolling limit
    if (channelEntries.length > CHANNEL_LIMIT) {
      const excess = channelEntries.length - CHANNEL_LIMIT
      channelEntries.splice(0, excess)
    }

    this.touch()

    // Notify subscriptions
    this.notifySubscriptions(channel, completeEntry)

    this.logger.debug('Posted to channel', {
      channel,
      author: entry.author,
      priority: completeEntry.priority,
      tags: completeEntry.tags,
    })

    return completeEntry
  }

  /**
   * Read entries from a channel.
   * Returns newest first, sorted by priority DESC then timestamp DESC.
   *
   * @param channel - The channel to read from
   * @param limit - Optional limit on number of entries (default: all)
   * @returns Array of entries, newest first
   */
  read(channel: BlackboardChannel, limit?: number): BlackboardEntry[] {
    const entries = [...this.channels[channel]]

    // Sort by priority DESC, then timestamp DESC
    entries.sort((a, b) => {
      if (b.priority !== a.priority) {
        return b.priority - a.priority
      }
      return b.timestamp - a.timestamp
    })

    if (limit && limit < entries.length) {
      return entries.slice(0, limit)
    }

    return entries
  }

  /**
   * Read all entries across all channels.
   * Useful for context assembly or full state inspection.
   *
   * @returns All entries from all channels, sorted by timestamp DESC
   */
  readAll(): BlackboardEntry[] {
    const allEntries: BlackboardEntry[] = []

    for (const channel of CHANNELS) {
      allEntries.push(...this.channels[channel])
    }

    // Sort by timestamp DESC (newest first)
    allEntries.sort((a, b) => b.timestamp - a.timestamp)

    return allEntries
  }


  /**
   * Subscribe to a channel with optional tag filtering.
   * Callback fires when a matching entry is posted.
   *
   * @param channel - The channel to watch
   * @param tags - Optional tags to filter by (entry must have ALL specified tags)
   * @param callback - Function called when matching entry is posted
   * @returns Unsubscribe function
   */
  subscribe(
    channel: BlackboardChannel,
    tags: string[] | undefined,
    callback: (entry: BlackboardEntry) => void,
  ): () => void {
    const id = `sub-${++this.subscriptionCounter}-${Date.now()}`

    const subscription: BlackboardSubscription = {
      id,
      channel,
      tags,
      callback,
    }

    this.subscriptions.set(id, subscription)

    this.logger.debug('Subscription created', {
      subscriptionId: id,
      channel,
      tags: tags ?? 'none',
    })

    return () => {
      this.subscriptions.delete(id)
      this.logger.debug('Subscription removed', { subscriptionId: id })
    }
  }

  /**
   * Notify all matching subscriptions when an entry is posted.
   * Private method called by post().
   */
  private notifySubscriptions(channel: BlackboardChannel, entry: BlackboardEntry): void {
    const subs = Array.from(this.subscriptions.values())
    for (const subscription of subs) {
      if (subscription.channel !== channel) continue

      // Check tag filter
      if (subscription.tags && subscription.tags.length > 0) {
        const hasAllTags = subscription.tags.every(tag => entry.tags.includes(tag))
        if (!hasAllTags) continue
      }

      // Fire callback
      try {
        subscription.callback(entry)
      } catch (err) {
        this.logger.error('Subscription callback failed', {
          subscriptionId: subscription.id,
          error: String(err),
        })
      }
    }
  }


  /**
   * Set a scratchpad entry with TTL.
   *
   * @param key - Unique key for the entry
   * @param value - Value to store
   * @param author - Node/agent that created this entry
   * @param ttlMs - Time-to-live in milliseconds (default: 30 min)
   */
  setScratchpad(key: string, value: string, author: string, ttlMs?: number): void {
    const entry: FluxScratchpadEntry = {
      key,
      value,
      author,
      createdAt: Date.now(),
      ttlMs: ttlMs ?? DEFAULT_SCRATCHPAD_TTL_MS,
    }

    this.scratchpad.set(key, entry)
    this.touch()

    this.logger.debug('Scratchpad entry set', { key, author, ttlMs: entry.ttlMs })
  }

  /**
   * Get a scratchpad entry.
   * Returns undefined if the entry doesn't exist or has expired.
   *
   * @param key - The key to look up
   * @returns The entry value or undefined
   */
  getScratchpad(key: string): string | undefined {
    const entry = this.scratchpad.get(key)
    if (!entry) return undefined

    // Check TTL
    const now = Date.now()
    if (now - entry.createdAt >= entry.ttlMs) {
      // Expired - remove it
      this.scratchpad.delete(key)
      return undefined
    }

    return entry.value
  }

  /**
   * Get all non-expired scratchpad entries.
   *
   * @returns Map of key to value for all valid entries
   */
  getAllScratchpad(): Map<string, string> {
    const result = new Map<string, string>()
    const now = Date.now()
    const entries = Array.from(this.scratchpad.entries())

    for (const [key, entry] of entries) {
      // Check TTL
      if (now - entry.createdAt < entry.ttlMs) {
        result.set(key, entry.value)
      } else {
        // Clean up expired entries
        this.scratchpad.delete(key)
      }
    }

    return result
  }


  /**
   * Add a tool execution record.
   *
   * @param record - Tool execution details (timestamp assigned automatically)
   */
  addToolRecord(record: Omit<FluxToolRecord, 'timestamp'>): void {
    const entry: FluxToolRecord = {
      ...record,
      timestamp: Date.now(),
    }

    this.toolLog.push(entry)

    // Enforce rolling limit
    if (this.toolLog.length > TOOL_LOG_LIMIT) {
      this.toolLog.shift()
    }

    this.touch()

    this.logger.debug('Tool record added', {
      tool: record.tool,
      nodeId: record.nodeId,
      isError: record.isError,
      durationMs: record.durationMs,
    })
  }

  /**
   * Get recent tool records.
   *
   * @param limit - Optional limit on number of records (default: all)
   * @returns Array of tool records, oldest first
   */
  getToolLog(limit?: number): FluxToolRecord[] {
    if (limit && limit < this.toolLog.length) {
      return this.toolLog.slice(-limit)
    }
    return [...this.toolLog]
  }


  /**
   * Track a file artifact.
   * Overwrites previous entry for the same path.
   *
   * @param entry - Artifact details (timestamp assigned automatically)
   */
  addArtifact(entry: Omit<ArtifactEntry, 'timestamp'>): void {
    const completeEntry: ArtifactEntry = {
      ...entry,
      timestamp: Date.now(),
    }

    this.artifacts.set(entry.path, completeEntry)
    this.touch()

    this.logger.debug('Artifact tracked', {
      path: entry.path,
      operation: entry.operation,
      author: entry.author,
    })
  }

  /**
   * Get all tracked artifacts.
   *
   * @returns Array of all artifact entries
   */
  getArtifacts(): ArtifactEntry[] {
    return Array.from(this.artifacts.values())
  }


  /**
   * Store a child cell result.
   *
   * @param childCellId - The child cell's ID
   * @param result - The child cell's execution result
   */
  setChildResult(childCellId: string, result: FluxCellResult): void {
    this.childResults.set(childCellId, result)
    this.touch()

    this.logger.debug('Child result stored', { childCellId })
  }

  /**
   * Get all child results.
   *
   * @returns Map of child cell ID to result
   */
  getChildResults(): Map<string, FluxCellResult> {
    return new Map(this.childResults)
  }

  /**
   * Set parent context string.
   *
   * @param context - Context from parent cell
   */
  setParentContext(context: string): void {
    this.parentContext = context
    this.touch()

    this.logger.debug('Parent context set', { length: context.length })
  }

  /**
   * Get parent context string.
   *
   * @returns The parent context
   */
  getParentContext(): string {
    return this.parentContext
  }


  /**
   * Initialize a new plan for this blackboard.
   * If a plan already exists, returns the existing plan.
   *
   * @param goal - The goal this plan addresses
   * @returns The new or existing plan
   */
  initPlan(goal: string): Plan {
    if (this.plan) {
      this.logger.debug('Plan already exists, returning existing', { planId: this.plan.id })
      return this.plan
    }

    const now = Date.now()
    this.plan = {
      id: `plan-${randomUUID().slice(0, 8)}`,
      goal,
      status: 'drafting',
      steps: [],
      createdAt: now,
      updatedAt: now,
    }

    this.touch()
    this.logger.debug('Plan initialized', { planId: this.plan.id, goal: goal.slice(0, 80) })
    return this.plan
  }

  /**
   * Get the current plan.
   *
   * @returns The plan or null if none exists
   */
  getPlan(): Plan | null {
    return this.plan
  }

  /**
   * Submit a new step to the plan.
   * Steps start as 'proposed' — only the Executive can approve them.
   *
   * @param step - Step details (id, createdAt, updatedAt assigned automatically)
   * @returns The complete step with generated fields
   */
  submitPlanStep(step: Omit<PlanStep, 'id' | 'createdAt' | 'updatedAt' | 'status'>): PlanStep {
    if (!this.plan) {
      throw new Error('No plan exists. Call initPlan() first.')
    }

    const now = Date.now()
    const completeStep: PlanStep = {
      id: `step-${randomUUID().slice(0, 8)}`,
      title: step.title,
      description: step.description,
      status: 'proposed',
      author: step.author,
      order: step.order,
      dependencies: step.dependencies ?? [],
      priority: step.priority ?? 'medium',
      outcome: step.outcome,
      rejectionReason: step.rejectionReason,
      tags: step.tags ?? [],
      createdAt: now,
      updatedAt: now,
    }

    this.plan.steps.push(completeStep)
    this.plan.updatedAt = now
    this.touch()

    this.logger.debug('Plan step submitted', {
      planId: this.plan.id,
      stepId: completeStep.id,
      title: step.title,
      author: step.author,
    })

    return completeStep
  }

  /**
   * Update a plan step's fields.
   *
   * @param stepId - The step to update
   * @param update - Partial step fields to change
   * @returns The updated step, or null if not found
   */
  updatePlanStep(stepId: string, update: Partial<Pick<PlanStep, 'title' | 'description' | 'status' | 'order' | 'dependencies' | 'priority' | 'outcome' | 'rejectionReason' | 'tags'>>): PlanStep | null {
    if (!this.plan) return null

    const step = this.plan.steps.find(s => s.id === stepId)
    if (!step) return null

    const now = Date.now()
    if (update.title !== undefined) step.title = update.title
    if (update.description !== undefined) step.description = update.description
    if (update.status !== undefined) step.status = update.status
    if (update.order !== undefined) step.order = update.order
    if (update.dependencies !== undefined) step.dependencies = update.dependencies
    if (update.priority !== undefined) step.priority = update.priority
    if (update.outcome !== undefined) step.outcome = update.outcome
    if (update.rejectionReason !== undefined) step.rejectionReason = update.rejectionReason
    if (update.tags !== undefined) step.tags = update.tags
    step.updatedAt = now
    this.plan.updatedAt = now
    this.touch()

    this.logger.debug('Plan step updated', {
      planId: this.plan.id,
      stepId,
      fields: Object.keys(update),
    })

    return step
  }

  /**
   * Finalize the plan (approve, complete, or abandon).
   *
   * @param status - Target status: 'approved', 'completed', or 'abandoned'
   * @param approver - Who finalized the plan
   * @param summary - Optional summary/notes
   * @returns The finalized plan, or null if no plan exists
   */
  finalizePlan(status: 'approved' | 'completed' | 'abandoned', approver?: string, summary?: string): Plan | null {
    if (!this.plan) return null

    const now = Date.now()
    this.plan.status = status
    this.plan.updatedAt = now

    if (approver) {
      this.plan.approvedBy = approver
      this.plan.approvedAt = now
    }
    if (summary) {
      this.plan.summary = summary
    }

    this.touch()

    this.logger.debug('Plan finalized', {
      planId: this.plan.id,
      status,
      approver,
      stepCount: this.plan.steps.length,
    })

    return this.plan
  }

  // Work-claiming TODO methods

  /** Default stall timeout: 30 minutes */
  private static readonly DEFAULT_STALL_TIMEOUT_MS = 30 * 60 * 1000

  /**
   * Claim an approved plan step for execution.
   *
   * Only steps with status 'approved' and no current assignee can be claimed.
   * Claiming auto-transitions the step to 'in_progress'.
   *
   * @param stepId - The step to claim
   * @param assignee - Agent/posture claiming the step
   * @param expectedStatus - Optimistic concurrency guard (default: 'approved')
   * @returns The claimed step, or null if claim failed
   */
  claimPlanStep(stepId: string, assignee: string, expectedStatus: PlanStepStatus = 'approved'): PlanStep | null {
    if (!this.plan) return null

    const step = this.plan.steps.find(s => s.id === stepId)
    if (!step) return null

    // Optimistic concurrency: reject if status changed since caller last checked
    if (step.status !== expectedStatus) {
      this.logger.debug('Claim rejected: status mismatch', {
        stepId, expected: expectedStatus, actual: step.status,
      })
      return null
    }

    // Only approved, unassigned steps can be claimed
    if (step.status !== 'approved' || step.assignee) {
      this.logger.debug('Claim rejected: step not available', {
        stepId, status: step.status, assignee: step.assignee,
      })
      return null
    }

    const now = Date.now()
    step.status = 'in_progress'
    step.assignee = assignee
    step.claimedAt = now
    step.lastActivityAt = now
    step.updatedAt = now
    this.plan.updatedAt = now
    this.touch()

    this.logger.debug('Plan step claimed', {
      planId: this.plan.id, stepId, assignee,
    })

    return step
  }

  /**
   * Release a claimed plan step, reverting it to 'approved'.
   *
   * Only the current assignee (or force=true) can release a step.
   *
   * @param stepId - The step to release
   * @param assignee - Agent requesting release (must match current assignee unless force)
   * @param force - Skip assignee check (for stall recovery)
   * @returns true if released, false otherwise
   */
  releasePlanStep(stepId: string, assignee: string, force = false): boolean {
    if (!this.plan) return false

    const step = this.plan.steps.find(s => s.id === stepId)
    if (!step) return false
    if (step.status !== 'in_progress') return false
    if (!force && step.assignee !== assignee) return false

    const now = Date.now()
    step.status = 'approved'
    step.assignee = undefined
    step.claimedAt = undefined
    step.lastActivityAt = undefined
    step.updatedAt = now
    this.plan.updatedAt = now
    this.touch()

    this.logger.debug('Plan step released', {
      planId: this.plan.id, stepId, releasedBy: assignee, force,
    })

    return true
  }

  /**
   * Report progress / heartbeat on a claimed step.
   *
   * Updates `lastActivityAt` to prevent stall detection from reclaiming the step.
   *
   * @param stepId - The step to report on
   * @param assignee - Must match current assignee
   * @param progress - Optional progress description
   * @returns The updated step, or null if not found / not assigned to caller
   */
  reportPlanStepProgress(stepId: string, assignee: string, progress?: string): PlanStep | null {
    if (!this.plan) return null

    const step = this.plan.steps.find(s => s.id === stepId)
    if (!step) return null
    if (step.status !== 'in_progress' || step.assignee !== assignee) return null

    const now = Date.now()
    step.lastActivityAt = now
    step.updatedAt = now
    if (progress) {
      step.outcome = progress
    }
    this.plan.updatedAt = now
    this.touch()

    this.logger.debug('Plan step progress reported', {
      planId: this.plan.id, stepId, assignee,
    })

    return step
  }

  /**
   * Get all available (claimable) plan steps.
   *
   * Returns approved steps with no assignee, sorted by priority then order.
   */
  getAvailableSteps(): PlanStep[] {
    if (!this.plan) return []
    return this.plan.steps
      .filter(s => s.status === 'approved' && !s.assignee)
      .sort((a, b) => {
        const prio = { high: 0, medium: 1, low: 2 }
        const pd = prio[a.priority] - prio[b.priority]
        return pd !== 0 ? pd : a.order - b.order
      })
  }

  /**
   * Get claimed (in-progress) plan steps, optionally filtered by assignee.
   *
   * @param assignee - If provided, only return steps claimed by this agent
   */
  getClaimedSteps(assignee?: string): PlanStep[] {
    if (!this.plan) return []
    return this.plan.steps.filter(s => {
      if (s.status !== 'in_progress' || !s.assignee) return false
      return assignee ? s.assignee === assignee : true
    })
  }

  /**
   * Reclaim stalled work — release steps whose assignee hasn't reported
   * activity within the stall timeout.
   *
   * @param maxAgeMs - Override default stall timeout (default: 30 min)
   * @returns Number of steps reclaimed
   */
  reclaimStalledWork(maxAgeMs: number = Blackboard.DEFAULT_STALL_TIMEOUT_MS): number {
    if (!this.plan) return 0

    const now = Date.now()
    let reclaimed = 0

    for (const step of this.plan.steps) {
      if (step.status !== 'in_progress' || !step.assignee) continue

      const timeout = step.stallTimeoutMs ?? maxAgeMs
      const lastActive = step.lastActivityAt ?? step.claimedAt ?? step.updatedAt
      if (now - lastActive > timeout) {
        this.logger.info('Reclaiming stalled plan step', {
          planId: this.plan.id,
          stepId: step.id,
          assignee: step.assignee,
          stalledForMs: now - lastActive,
        })

        step.status = 'approved'
        step.assignee = undefined
        step.claimedAt = undefined
        step.lastActivityAt = undefined
        step.updatedAt = now
        reclaimed++
      }
    }

    if (reclaimed > 0) {
      this.plan.updatedAt = now
      this.touch()
    }

    return reclaimed
  }

  /**
   * Format the plan as a readable text string for context injection.
   *
   * @returns Formatted plan text, or empty string if no plan
   */
  formatPlanForContext(): string {
    if (!this.plan || this.plan.steps.length === 0) return ''

    const lines: string[] = [
      `Plan: ${this.plan.goal}`,
      `Status: ${this.plan.status}`,
    ]

    if (this.plan.summary) {
      lines.push(`Summary: ${this.plan.summary}`)
    }

    // Work-claiming summary
    const available = this.plan.steps.filter(s => s.status === 'approved' && !s.assignee).length
    const claimed = this.plan.steps.filter(s => s.status === 'in_progress' && s.assignee).length
    const completed = this.plan.steps.filter(s => s.status === 'completed').length
    const total = this.plan.steps.length
    lines.push(`Progress: ${completed}/${total} completed, ${claimed} in-progress, ${available} available`)

    // Sort steps by order
    const sortedSteps = [...this.plan.steps].sort((a, b) => a.order - b.order)

    lines.push('')
    lines.push('Steps:')
    for (const step of sortedSteps) {
      const depStr = step.dependencies.length > 0 ? ` (deps: ${step.dependencies.join(', ')})` : ''
      const assigneeStr = step.assignee ? ` [assigned: ${step.assignee}]` : ''
      lines.push(`  ${step.order}. [${step.status.toUpperCase()}] ${step.title} (${step.priority})${depStr}${assigneeStr}`)
      lines.push(`     ${step.description}`)
      if (step.outcome) {
        lines.push(`     Outcome: ${step.outcome}`)
      }
      if (step.rejectionReason) {
        lines.push(`     Rejected: ${step.rejectionReason}`)
      }
    }

    return lines.join('\n')
  }


  /**
   * Store the incremental report from a Lumen session.
   *
   * @param report - The report produced by Yang/Yin/Executive collaboration
   */
  setReport(report: Report): void {
    this.report = report
    this.touch()
    this.logger.debug('Report stored', { reportId: report.id, sections: report.sections.length })
  }

  /**
   * Get the current incremental report.
   *
   * @returns The report or null if none has been set
   */
  getReport(): Report | null {
    return this.report
  }

  /**
   * Initialize a new report for this session.
   * Resets the section counter and creates a fresh report object.
   *
   * @param goal - The goal this report is for
   */
  initReport(goal: string): Report {
    const now = Date.now()
    this.reportSectionCounter = 0
    this.report = {
      id: `report-${now}`,
      goal,
      sections: [],
      createdAt: now,
      updatedAt: now,
    }
    this.touch()
    return this.report
  }

  /**
   * Add a section to the incremental report.
   * If no report exists, one is auto-initialized with an empty goal.
   */
  addReportSection(section: {
    type: ReportSectionType
    status?: ReportSectionStatus
    title: string
    content: string
    author: string
    confidence?: number
    references?: string[]
    threadId?: string
    respondsTo?: string
    challenges?: string
    supports?: string
    supersedes?: string
  }): ReportSection {
    if (!this.report) this.initReport('')
    const now = Date.now()
    const id = `rs-${++this.reportSectionCounter}`
    const newSection: ReportSection = {
      id,
      type: section.type,
      status: section.status ?? 'active',
      title: section.title,
      content: section.content,
      author: section.author,
      confidence: section.confidence,
      references: section.references,
      threadId: section.threadId,
      respondsTo: section.respondsTo,
      challenges: section.challenges,
      supports: section.supports,
      supersedes: section.supersedes,
      createdAt: now,
      updatedAt: now,
    }
    this.report!.sections.push(newSection)
    this.report!.updatedAt = now
    this.touch()
    return newSection
  }

  /**
   * Auto-draft a report section from a dialectic finding.
   * Creates a section with status='draft' linked to the originating message.
   */
  autoDraftFromFinding(posture: string, findingId: string, text: string, evidence?: string[]): void {
    this.addReportSection({
      type: 'finding',
      status: 'draft',
      title: text.slice(0, 80),
      content: text,
      author: posture,
      references: evidence,
      threadId: findingId,
    })
  }

  /**
   * Auto-draft a concern section from a dialectic challenge.
   */
  autoDraftFromChallenge(posture: string, challengeId: string, text: string, targetFindingId: string): void {
    this.addReportSection({
      type: 'concern',
      status: 'draft',
      title: text.slice(0, 80),
      content: text,
      author: posture,
      threadId: targetFindingId,
      challenges: targetFindingId,
    })
  }

  /**
   * Auto-draft a decision section from a dialectic concession.
   */
  autoDraftFromConcession(posture: string, concessionId: string, text: string, challengeId: string): void {
    this.addReportSection({
      type: 'decision',
      status: 'draft',
      title: text.slice(0, 80),
      content: text,
      author: posture,
      threadId: challengeId,
      respondsTo: challengeId,
    })
  }

  /**
   * Revise an existing section — creates a new active section that supersedes the original.
   */
  reviseReportSection(sectionId: string, content: string, _reason?: string): ReportSection | null {
    if (!this.report) return null
    const original = this.report.sections.find(s => s.id === sectionId)
    if (!original) return null

    // Mark original as superseded
    original.superseded = true
    original.status = 'superseded'
    original.updatedAt = Date.now()

    // Create new section that supersedes the original
    return this.addReportSection({
      type: original.type,
      title: original.title,
      content,
      author: original.author,
      confidence: original.confidence,
      references: original.references,
      threadId: original.threadId,
      supersedes: sectionId,
    })
  }

  /**
   * Promote a draft section to active status.
   */
  promoteReportSection(sectionId: string): boolean {
    if (!this.report) return false
    const section = this.report.sections.find(s => s.id === sectionId && s.status === 'draft')
    if (!section) return false
    section.status = 'active'
    section.updatedAt = Date.now()
    this.report.updatedAt = Date.now()
    this.touch()
    return true
  }

  /**
   * Discard a draft section.
   * Cascades: clears references to the discarded section from other sections.
   */
  discardReportSection(sectionId: string): boolean {
    if (!this.report) return false
    const idx = this.report.sections.findIndex(s => s.id === sectionId && s.status === 'draft')
    if (idx === -1) return false
    this.report.sections.splice(idx, 1)

    // Cascading cleanup: remove references to the discarded section
    for (const s of this.report.sections) {
      if (s.respondsTo === sectionId) s.respondsTo = undefined
      if (s.challenges === sectionId) s.challenges = undefined
      if (s.supports === sectionId) s.supports = undefined
      if (s.supersedes === sectionId) s.supersedes = undefined
    }

    this.report.updatedAt = Date.now()
    this.touch()
    return true
  }

  /**
   * Get filtered report sections.
   */
  getReportView(opts?: {
    filterType?: string
    filterAuthor?: string
    filterStatus?: string
    since?: number
  }): ReportSection[] {
    if (!this.report) return []
    let sections = this.report.sections
    if (opts?.filterType) sections = sections.filter(s => s.type === opts.filterType)
    if (opts?.filterAuthor) sections = sections.filter(s => s.author === opts.filterAuthor)
    if (opts?.filterStatus) sections = sections.filter(s => s.status === opts.filterStatus)
    if (opts?.since) sections = sections.filter(s => s.updatedAt > opts.since!)
    return sections
  }

  /**
   * Calculate quality metrics for the report.
   */
  getReportMetrics(): ReportQualityMetrics {
    if (!this.report) {
      return {
        totalSections: 0, activeSections: 0, draftSections: 0,
        byType: {}, byAuthor: {}, avgConfidence: 0,
        threadCount: 0, unresolvedConcerns: 0, coverageScore: 0,
      }
    }

    const sections = this.report.sections
    const active = sections.filter(s => s.status === 'active')
    const drafts = sections.filter(s => s.status === 'draft')

    // Count by type
    const byType: Partial<Record<string, number>> = {}
    for (const s of active) {
      byType[s.type] = (byType[s.type] ?? 0) + 1
    }

    // Count by author
    const byAuthor: Record<string, number> = {}
    for (const s of active) {
      byAuthor[s.author] = (byAuthor[s.author] ?? 0) + 1
    }

    // Avg confidence
    const withConf = active.filter(s => s.confidence != null)
    const avgConfidence = withConf.length > 0
      ? withConf.reduce((sum, s) => sum + (s.confidence ?? 0), 0) / withConf.length
      : 0

    // Thread count
    const threads = new Set(active.filter(s => s.threadId).map(s => s.threadId))

    // Unresolved concerns: concerns without a linked decision in the same thread
    const decisionThreads = new Set(
      active.filter(s => s.type === 'decision').map(s => s.threadId).filter(Boolean)
    )
    const unresolvedConcerns = active.filter(
      s => s.type === 'concern' && (!s.threadId || !decisionThreads.has(s.threadId))
    ).length

    // Coverage: how many of the 3 core types are represented?
    const typesUsed = new Set(Object.keys(byType))
    const idealTypes = ['finding', 'concern', 'recommendation']
    const coverageScore = idealTypes.filter(t => typesUsed.has(t)).length / idealTypes.length

    return {
      totalSections: sections.length,
      activeSections: active.length,
      draftSections: drafts.length,
      byType,
      byAuthor,
      avgConfidence: Math.round(avgConfidence * 100) / 100,
      threadCount: threads.size,
      unresolvedConcerns,
      coverageScore: Math.round(coverageScore * 100) / 100,
    }
  }

  /**
   * Format the report for context injection at synthesis time.
   */
  formatReportForContext(): string {
    if (!this.report || this.report.sections.length === 0) return ''

    const active = this.report.sections.filter(s => s.status === 'active')
    const drafts = this.report.sections.filter(s => s.status === 'draft')

    if (active.length === 0 && drafts.length === 0) return ''

    const parts: string[] = ['## Incremental Report']

    // Group active sections by type
    const byType = new Map<string, ReportSection[]>()
    for (const s of active) {
      if (!byType.has(s.type)) byType.set(s.type, [])
      byType.get(s.type)!.push(s)
    }

    for (const [type, typeSections] of byType) {
      parts.push(`\n### ${type.charAt(0).toUpperCase() + type.slice(1)}s`)
      for (const s of typeSections) {
        const conf = s.confidence != null ? ` (confidence: ${s.confidence})` : ''
        const refs = s.references?.length ? `\n  References: ${s.references.join(', ')}` : ''
        const thread = s.threadId ? ` [thread: ${s.threadId}]` : ''
        parts.push(`- **${s.title}** — by ${s.author}${conf}${thread}\n  ${s.content}${refs}`)
      }
    }

    if (drafts.length > 0) {
      parts.push(`\n### Drafts (${drafts.length} pending review)`)
      for (const s of drafts) {
        parts.push(`- [DRAFT] **${s.title}** — ${s.type} by ${s.author}`)
      }
    }

    return parts.join('\n')
  }


  /**
   * Assemble context for a Lumen session.
   * Produces the most relevant blackboard content for a node, respecting token budget.
   * Uses ~4 chars per token approximation.
   *
   * Priority order:
   *   1. Parent context (if available)
   *   2. High-priority channel entries (by priority field)
   *   3. Scratchpad entries
   *   4. Child results
   *
   * @param nodeId - The node ID assembling context (for logging)
   * @param tokenBudget - Maximum tokens allowed
   * @returns Context string truncated to fit budget
   */
  assembleContext(nodeId: string, tokenBudget: number): string {
    const charBudget = tokenBudget * 4
    const sections: string[] = []
    let currentLength = 0

    // Helper to add a section if it fits
    const addSection = (title: string, content: string): boolean => {
      if (!content) return true

      const section = `## ${title}\n${content}\n\n`
      if (currentLength + section.length > charBudget) {
        return false
      }

      sections.push(section)
      currentLength += section.length
      return true
    }

    // 1. Parent context (highest priority)
    if (this.parentContext) {
      if (!addSection('Parent Context', this.parentContext)) {
        // Truncate to fit
        const remaining = charBudget - currentLength - 20
        if (remaining > 0) {
          sections.push(`## Parent Context\n${this.parentContext.slice(0, remaining)}...\n\n`)
        }
        return sections.join('')
      }
    }

    // 2. Plan (if exists)
    const planText = this.formatPlanForContext()
    if (planText) {
      addSection('Current Plan', planText)
    }

    // 3. Channel entries (sorted by priority)
    const allEntries = this.readAll()
    for (const entry of allEntries) {
      const entryText = this.formatChannelEntry(entry)
      if (!addSection(`${entry.channel.toUpperCase()}: ${entry.id.slice(0, 8)}`, entryText)) {
        // Budget exhausted
        return sections.join('')
      }
    }

    // 4. Scratchpad entries
    const scratchpad = this.getAllScratchpad()
    if (scratchpad.size > 0) {
      const scratchpadText = Array.from(scratchpad.entries())
        .map(([k, v]) => `- **${k}**: ${v}`)
        .join('\n')
      addSection('Scratchpad', scratchpadText)
    }

    // 5. Child results
    if (this.childResults.size > 0) {
      const childLines: string[] = []
      for (const [childId, result] of Array.from(this.childResults.entries())) {
        const status = result.success ? 'SUCCESS' : 'FAILED'
        let line = `### ${childId} [${status}]`
        if (result.output) {
          line += `\n${result.output.slice(0, 500)}`
        }
        childLines.push(line)
      }
      addSection('Child Results', childLines.join('\n\n'))
    }

    this.logger.debug('Context assembled', {
      nodeId,
      tokenBudget,
      charLength: currentLength,
      sections: sections.length,
    })

    return sections.join('')
  }

  /**
   * Format a channel entry for context inclusion.
   */
  private formatChannelEntry(entry: BlackboardEntry): string {
    const lines: string[] = [
      `Author: ${entry.author}`,
      `Priority: ${entry.priority}`,
      `Tags: ${entry.tags.join(', ') || 'none'}`,
      `Content: ${entry.content}`,
    ]

    if (entry.structured && Object.keys(entry.structured).length > 0) {
      lines.push(`Data: ${JSON.stringify(entry.structured)}`)
    }

    return lines.join('\n')
  }


  // Search & Pagination Methods

  /**
   * Search channel entries with regex pattern matching and cursor-based pagination.
   * Existing read() / readAll() methods are preserved for backward compatibility.
   *
   * Pattern matches against: content, author, tags (space-joined).
   * Results sorted by priority DESC, timestamp DESC.
   */
  searchChannel(opts: ChannelSearchOptions = {}): PaginatedResult<BlackboardEntry> {
    const limit = normalizeLimit(opts.limit)
    const cursor = opts.cursor ? decodeCursor(opts.cursor) : null
    const regex = opts.pattern ? compilePattern(opts.pattern) : null

    // Collect entries from specified channel or all channels
    let entries: BlackboardEntry[]
    if (opts.channel) {
      entries = [...this.channels[opts.channel]]
    } else {
      entries = CHANNELS.flatMap(ch => this.channels[ch])
    }

    // Sort: priority DESC, timestamp DESC
    entries.sort((a, b) => {
      const pd = b.priority - a.priority
      return pd !== 0 ? pd : b.timestamp - a.timestamp
    })

    // Apply filters
    entries = entries.filter(entry => {
      if (!passesBaseFilters(opts, entry.author, entry.timestamp)) return false
      if (opts.tags?.length && !opts.tags.every(t => entry.tags.includes(t))) return false
      if (opts.minPriority !== undefined && entry.priority < opts.minPriority) return false
      if (opts.maxPriority !== undefined && entry.priority > opts.maxPriority) return false
      if (regex && matchesAny(regex, [entry.content, entry.author, entry.tags.join(' ')]).length === 0) return false
      return true
    })

    return paginate(entries, limit, cursor, e => e.id, e => e.timestamp, e => e.priority)
  }

  /**
   * Search scratchpad entries with regex pattern matching and cursor-based pagination.
   * Pattern matches against: key, value.
   * Results sorted by createdAt DESC.
   */
  searchScratchpad(opts: ScratchpadSearchOptions = {}): PaginatedResult<FluxScratchpadEntry> {
    const limit = normalizeLimit(opts.limit)
    const cursor = opts.cursor ? decodeCursor(opts.cursor) : null
    const regex = opts.pattern ? compilePattern(opts.pattern) : null
    const now = Date.now()

    // Collect entries, optionally filtering expired
    const entries: FluxScratchpadEntry[] = []
    for (const [, entry] of this.scratchpad) {
      const expired = now - entry.createdAt >= entry.ttlMs
      if (expired && !opts.includeExpired) {
        this.scratchpad.delete(entry.key)
        continue
      }
      entries.push(entry)
    }

    // Sort: createdAt DESC
    entries.sort((a, b) => b.createdAt - a.createdAt)

    // Apply filters
    const filtered = entries.filter(entry => {
      if (!passesBaseFilters(opts, entry.author, entry.createdAt)) return false
      if (regex && matchesAny(regex, [entry.key, entry.value]).length === 0) return false
      return true
    })

    return paginate(filtered, limit, cursor, e => e.key, e => e.createdAt)
  }

  /**
   * Search tool log records with regex pattern matching and cursor-based pagination.
   * Pattern matches against: tool name, nodeId.
   * Results sorted by timestamp DESC (newest first).
   */
  searchToolLog(opts: ToolLogSearchOptions = {}): PaginatedResult<FluxToolRecord> {
    const limit = normalizeLimit(opts.limit)
    const cursor = opts.cursor ? decodeCursor(opts.cursor) : null
    const regex = opts.pattern ? compilePattern(opts.pattern) : null

    // Copy and sort DESC (newest first)
    const records = [...this.toolLog].reverse()

    // Apply filters
    const filtered = records.filter(record => {
      if (!passesBaseFilters(opts, undefined, record.timestamp)) return false
      if (opts.tool && record.tool !== opts.tool) return false
      if (opts.nodeId && record.nodeId !== opts.nodeId) return false
      if (opts.isError !== undefined && record.isError !== opts.isError) return false
      if (regex && matchesAny(regex, [record.tool, record.nodeId]).length === 0) return false
      return true
    })

    // FluxToolRecord has no natural ID — use tool:nodeId:timestamp as pseudo-ID
    return paginate(
      filtered, limit, cursor,
      r => `${r.tool}:${r.nodeId}:${r.timestamp}`,
      r => r.timestamp,
    )
  }

  /**
   * Search artifact entries with regex pattern matching and cursor-based pagination.
   * Pattern matches against: path, author.
   * Results sorted by timestamp DESC.
   */
  searchArtifacts(opts: ArtifactSearchOptions = {}): PaginatedResult<ArtifactEntry> {
    const limit = normalizeLimit(opts.limit)
    const cursor = opts.cursor ? decodeCursor(opts.cursor) : null
    const regex = opts.pattern ? compilePattern(opts.pattern) : null

    // Collect and sort DESC
    const entries = Array.from(this.artifacts.values())
    entries.sort((a, b) => b.timestamp - a.timestamp)

    // Apply filters
    const filtered = entries.filter(entry => {
      if (!passesBaseFilters(opts, entry.author, entry.timestamp)) return false
      if (opts.operation && entry.operation !== opts.operation) return false
      if (regex && matchesAny(regex, [entry.path, entry.author]).length === 0) return false
      return true
    })

    return paginate(filtered, limit, cursor, e => e.path, e => e.timestamp)
  }

  /**
   * Search plan steps with regex pattern matching and cursor-based pagination.
   * Pattern matches against: title, description, tags (space-joined).
   * Results sorted by order ASC (execution order).
   */
  searchPlan(opts: PlanSearchOptions = {}): PaginatedResult<PlanStep> {
    if (!this.plan) {
      return { items: [], total: 0, hasMore: false, pageSize: 0 }
    }

    const limit = normalizeLimit(opts.limit)
    const cursor = opts.cursor ? decodeCursor(opts.cursor) : null
    const regex = opts.pattern ? compilePattern(opts.pattern) : null

    // Sort by order ASC
    const steps = [...this.plan.steps].sort((a, b) => a.order - b.order)

    // Apply filters
    const filtered = steps.filter(step => {
      if (!passesBaseFilters(opts, step.author, step.createdAt)) return false
      if (opts.status && step.status !== opts.status) return false
      if (opts.assignee && step.assignee !== opts.assignee) return false
      if (opts.priority && step.priority !== opts.priority) return false
      if (regex && matchesAny(regex, [step.title, step.description, step.tags?.join(' ')]).length === 0) return false
      return true
    })

    return paginate(filtered, limit, cursor, s => s.id, s => s.createdAt, s => s.order, true)
  }

  /**
   * Search report sections with regex pattern matching and cursor-based pagination.
   * Pattern matches against: title, content, author.
   * Results sorted by createdAt DESC.
   */
  searchReport(opts: ReportSearchOptions = {}): PaginatedResult<ReportSection> {
    if (!this.report) {
      return { items: [], total: 0, hasMore: false, pageSize: 0 }
    }

    const limit = normalizeLimit(opts.limit)
    const cursor = opts.cursor ? decodeCursor(opts.cursor) : null
    const regex = opts.pattern ? compilePattern(opts.pattern) : null

    // Sort by createdAt DESC
    const sections = [...this.report.sections].sort((a, b) => b.createdAt - a.createdAt)

    // Apply filters
    const filtered = sections.filter(section => {
      if (!passesBaseFilters(opts, section.author, section.createdAt)) return false
      if (opts.type && section.type !== opts.type) return false
      if (opts.status && section.status !== opts.status) return false
      if (regex && matchesAny(regex, [section.title, section.content, section.author]).length === 0) return false
      return true
    })

    return paginate(filtered, limit, cursor, s => s.id, s => s.createdAt)
  }

  /**
   * Cross-board unified search.
   * Searches all (or specified) boards with a single regex pattern.
   * Returns results grouped by board type with per-board pagination.
   */
  searchAll(opts: CrossBoardSearchOptions): CrossBoardSearchResult {
    const boards = opts.boards ?? ALL_SEARCHABLE_BOARDS
    const limitPerBoard = normalizeLimit(opts.limitPerBoard)
    const compositeCursors = opts.cursor ? decodeCompositeCursor(opts.cursor) : null

    const result: CrossBoardSearchResult = {
      boards: {},
      totalMatches: 0,
      rankedBoards: [],
    }

    const boardCounts: Array<{ board: SearchableBoard; count: number }> = []
    const nextCursors: Record<string, string> = {}

    for (const board of boards) {
      const boardCursor = compositeCursors?.[board] ?? undefined

      switch (board) {
        case 'channel': {
          const r = this.searchChannel({
            pattern: opts.pattern,
            limit: limitPerBoard,
            cursor: boardCursor,
            author: opts.author,
            since: opts.since,
            until: opts.until,
          })
          if (r.total > 0) {
            const regex = compilePattern(opts.pattern)
            const items: Array<CrossBoardResultItem & { board: 'channel' }> = r.items.map(item => ({
              board: 'channel' as const,
              channel: item.channel,
              item,
              matchedFields: matchesAny(regex, [item.content, item.author, item.tags.join(' ')]),
            }))
            result.boards.channel = { items, total: r.total, hasMore: r.hasMore, cursor: r.cursor }
            boardCounts.push({ board: 'channel', count: r.total })
            if (r.cursor) nextCursors.channel = r.cursor
          }
          break
        }
        case 'scratchpad': {
          const r = this.searchScratchpad({
            pattern: opts.pattern,
            limit: limitPerBoard,
            cursor: boardCursor,
            author: opts.author,
            since: opts.since,
            until: opts.until,
          })
          if (r.total > 0) {
            const regex = compilePattern(opts.pattern)
            const items: Array<CrossBoardResultItem & { board: 'scratchpad' }> = r.items.map(item => ({
              board: 'scratchpad' as const,
              item,
              matchedFields: matchesAny(regex, [item.key, item.value]),
            }))
            result.boards.scratchpad = { items, total: r.total, hasMore: r.hasMore, cursor: r.cursor }
            boardCounts.push({ board: 'scratchpad', count: r.total })
            if (r.cursor) nextCursors.scratchpad = r.cursor
          }
          break
        }
        case 'toolLog': {
          const r = this.searchToolLog({
            pattern: opts.pattern,
            limit: limitPerBoard,
            cursor: boardCursor,
            since: opts.since,
            until: opts.until,
          })
          if (r.total > 0) {
            const regex = compilePattern(opts.pattern)
            const items: Array<CrossBoardResultItem & { board: 'toolLog' }> = r.items.map(item => ({
              board: 'toolLog' as const,
              item,
              matchedFields: matchesAny(regex, [item.tool, item.nodeId]),
            }))
            result.boards.toolLog = { items, total: r.total, hasMore: r.hasMore, cursor: r.cursor }
            boardCounts.push({ board: 'toolLog', count: r.total })
            if (r.cursor) nextCursors.toolLog = r.cursor
          }
          break
        }
        case 'artifact': {
          const r = this.searchArtifacts({
            pattern: opts.pattern,
            limit: limitPerBoard,
            cursor: boardCursor,
            author: opts.author,
            since: opts.since,
            until: opts.until,
          })
          if (r.total > 0) {
            const regex = compilePattern(opts.pattern)
            const items: Array<CrossBoardResultItem & { board: 'artifact' }> = r.items.map(item => ({
              board: 'artifact' as const,
              item,
              matchedFields: matchesAny(regex, [item.path, item.author]),
            }))
            result.boards.artifact = { items, total: r.total, hasMore: r.hasMore, cursor: r.cursor }
            boardCounts.push({ board: 'artifact', count: r.total })
            if (r.cursor) nextCursors.artifact = r.cursor
          }
          break
        }
        case 'plan': {
          const r = this.searchPlan({
            pattern: opts.pattern,
            limit: limitPerBoard,
            cursor: boardCursor,
            author: opts.author,
            since: opts.since,
            until: opts.until,
          })
          if (r.total > 0) {
            const regex = compilePattern(opts.pattern)
            const items: Array<CrossBoardResultItem & { board: 'plan' }> = r.items.map(item => ({
              board: 'plan' as const,
              item,
              matchedFields: matchesAny(regex, [item.title, item.description, item.tags?.join(' ')]),
            }))
            result.boards.plan = { items, total: r.total, hasMore: r.hasMore, cursor: r.cursor }
            boardCounts.push({ board: 'plan', count: r.total })
            if (r.cursor) nextCursors.plan = r.cursor
          }
          break
        }
        case 'report': {
          const r = this.searchReport({
            pattern: opts.pattern,
            limit: limitPerBoard,
            cursor: boardCursor,
            author: opts.author,
            since: opts.since,
            until: opts.until,
          })
          if (r.total > 0) {
            const regex = compilePattern(opts.pattern)
            const items: Array<CrossBoardResultItem & { board: 'report' }> = r.items.map(item => ({
              board: 'report' as const,
              item,
              matchedFields: matchesAny(regex, [item.title, item.content, item.author]),
            }))
            result.boards.report = { items, total: r.total, hasMore: r.hasMore, cursor: r.cursor }
            boardCounts.push({ board: 'report', count: r.total })
            if (r.cursor) nextCursors.report = r.cursor
          }
          break
        }
      }
    }

    // Compute totals and ranking
    result.totalMatches = boardCounts.reduce((sum, b) => sum + b.count, 0)
    result.rankedBoards = boardCounts.sort((a, b) => b.count - a.count)

    // Build composite cursor if any board has more pages
    if (Object.keys(nextCursors).length > 0) {
      result.cursor = encodeCompositeCursor(nextCursors)
    }

    return result
  }

  // Change Tracking (for bb_global_watch)

  /**
   * Get all changes across all boards within a time window.
   * Returns items created or updated between `since` and `until` (inclusive).
   * Used by the `bb_global_watch` MCP tool for accumulated change polling.
   */
  getChangesSince(window: ChangeWindow): BoardChanges {
    const since = window.since
    const until = window.until ?? Date.now()

    const changes: BoardChanges = {
      channels: [],
      scratchpad: [],
      toolLog: [],
      artifacts: [],
      plan: [],
      report: [],
    }

    // Channels — filter by timestamp
    for (const ch of CHANNELS) {
      for (const entry of this.channels[ch]) {
        if (entry.timestamp >= since && entry.timestamp <= until) {
          changes.channels.push({ channel: ch, entry })
        }
      }
    }

    // Scratchpad — filter by createdAt
    const now = Date.now()
    for (const [, entry] of this.scratchpad) {
      const expired = now - entry.createdAt >= entry.ttlMs
      if (expired) continue
      if (entry.createdAt >= since && entry.createdAt <= until) {
        changes.scratchpad.push(entry)
      }
    }

    // Tool log — filter by timestamp
    for (const record of this.toolLog) {
      if (record.timestamp >= since && record.timestamp <= until) {
        changes.toolLog.push(record)
      }
    }

    // Artifacts — filter by timestamp
    for (const [, entry] of this.artifacts) {
      if (entry.timestamp >= since && entry.timestamp <= until) {
        changes.artifacts.push(entry)
      }
    }

    // Plan steps — filter by createdAt or updatedAt
    if (this.plan) {
      for (const step of this.plan.steps) {
        if (step.createdAt >= since && step.createdAt <= until) {
          changes.plan.push({ step, operation: 'created' })
        } else if (step.updatedAt >= since && step.updatedAt <= until) {
          changes.plan.push({ step, operation: 'updated' })
        }
      }
    }

    // Report sections — filter by createdAt or updatedAt
    if (this.report) {
      for (const section of this.report.sections) {
        if (section.createdAt >= since && section.createdAt <= until) {
          changes.report.push({ section, operation: 'created' })
        } else if (section.updatedAt >= since && section.updatedAt <= until) {
          if (section.status === 'superseded') {
            changes.report.push({ section, operation: 'superseded' })
          } else {
            changes.report.push({ section, operation: 'updated' })
          }
        }
      }
    }

    return changes
  }

  /**
   * Build a complete watch result with summary statistics and cursor.
   */
  buildWatchResult(
    boardName: string,
    window: ChangeWindow,
    boards?: SearchableBoard[],
    includeContent = true,
  ): BlackboardWatchResult {
    const pollTime = Date.now()
    const until = window.until ?? pollTime
    const changes = this.getChangesSince({ since: window.since, until })

    // Filter to requested boards
    const filteredChanges: BoardChanges = {
      channels: boards && !boards.includes('channel') ? [] : changes.channels,
      scratchpad: boards && !boards.includes('scratchpad') ? [] : changes.scratchpad,
      toolLog: boards && !boards.includes('toolLog') ? [] : changes.toolLog,
      artifacts: boards && !boards.includes('artifact') ? [] : changes.artifacts,
      plan: boards && !boards.includes('plan') ? [] : changes.plan,
      report: boards && !boards.includes('report') ? [] : changes.report,
    }

    // Compute summary
    const byBoard: Record<string, number> = {}
    const byOperation: Record<string, number> = { created: 0, updated: 0, deleted: 0 }
    let totalChanges = 0

    if (filteredChanges.channels.length) { byBoard.channel = filteredChanges.channels.length; totalChanges += filteredChanges.channels.length; byOperation.created += filteredChanges.channels.length }
    if (filteredChanges.scratchpad.length) { byBoard.scratchpad = filteredChanges.scratchpad.length; totalChanges += filteredChanges.scratchpad.length; byOperation.created += filteredChanges.scratchpad.length }
    if (filteredChanges.toolLog.length) { byBoard.toolLog = filteredChanges.toolLog.length; totalChanges += filteredChanges.toolLog.length; byOperation.created += filteredChanges.toolLog.length }
    if (filteredChanges.artifacts.length) { byBoard.artifact = filteredChanges.artifacts.length; totalChanges += filteredChanges.artifacts.length; byOperation.created += filteredChanges.artifacts.length }
    if (filteredChanges.plan.length) {
      byBoard.plan = filteredChanges.plan.length; totalChanges += filteredChanges.plan.length
      for (const p of filteredChanges.plan) byOperation[p.operation] = (byOperation[p.operation] ?? 0) + 1
    }
    if (filteredChanges.report.length) {
      byBoard.report = filteredChanges.report.length; totalChanges += filteredChanges.report.length
      for (const r of filteredChanges.report) {
        const op = r.operation === 'superseded' ? 'deleted' : r.operation
        byOperation[op] = (byOperation[op] ?? 0) + 1
      }
    }

    // Strip content if not requested
    const outputChanges = includeContent ? filteredChanges : {
      channels: filteredChanges.channels.map(c => ({ channel: c.channel, entry: { ...c.entry, content: '' } })),
      scratchpad: filteredChanges.scratchpad.map(s => ({ ...s, value: '' })),
      toolLog: filteredChanges.toolLog.map(t => ({ ...t, input: undefined, output: undefined, result: '' })),
      artifacts: filteredChanges.artifacts,
      plan: filteredChanges.plan.map(p => ({ step: { ...p.step, description: '' }, operation: p.operation })),
      report: filteredChanges.report.map(r => ({ section: { ...r.section, content: '' }, operation: r.operation })),
    }

    // Build cursor encoding the window end
    const nextCursor = encodeCursor({ ts: until, id: 'watch-poll' })

    return {
      boardName,
      pollTime,
      windowStart: window.since,
      windowEnd: until,
      nextCursor,
      summary: {
        totalChanges,
        byBoard: byBoard as Record<SearchableBoard, number>,
        byOperation: byOperation as Record<'created' | 'updated' | 'deleted', number>,
      },
      changes: outputChanges,
    }
  }


  /**
   * Get a full snapshot of the blackboard state.
   * Used for persistence across daemon restarts.
   *
   * @returns Complete blackboard state
   */
  getSnapshot(): BlackboardState {
    return {
      id: `bb-${this.cellId}-${this.createdAt}`,
      cellId: this.cellId,
      channels: {
        findings: [...this.channels.findings],
        concerns: [...this.channels.concerns],
        decisions: [...this.channels.decisions],
        artifacts: [...this.channels.artifacts],
        requests: [...this.channels.requests],
        bugs: [...this.channels.bugs],
      },
      scratchpad: Object.fromEntries(this.scratchpad.entries()),
      toolLog: [...this.toolLog],
      artifacts: Object.fromEntries(this.artifacts.entries()),
      childResults: Object.fromEntries(this.childResults.entries()),
      parentContext: this.parentContext,
      plan: this.plan ?? undefined,
      report: this.report ?? undefined,
      createdAt: this.createdAt,
      lastActivityAt: this.lastActivityAt,
    }
  }

  /**
   * Restore the blackboard from a persisted snapshot.
   * Used when resuming after daemon restart.
   *
   * @param snapshot - Previously saved state
   */
  restoreFromSnapshot(snapshot: BlackboardState): void {
    // Restore channels
    for (const channel of CHANNELS) {
      this.channels[channel] = [...(snapshot.channels[channel] ?? [])]
    }

    // Restore scratchpad (handle both Map and plain object from deserialization)
    this.scratchpad.clear()
    if (snapshot.scratchpad instanceof Map) {
      for (const [key, entry] of Array.from(snapshot.scratchpad.entries())) {
        this.scratchpad.set(key, entry)
      }
    } else if (snapshot.scratchpad && typeof snapshot.scratchpad === 'object') {
      for (const [key, entry] of Object.entries(snapshot.scratchpad)) {
        this.scratchpad.set(key, entry as FluxScratchpadEntry)
      }
    }

    // Restore tool log
    this.toolLog.length = 0
    this.toolLog.push(...(snapshot.toolLog ?? []))

    // Restore artifacts
    this.artifacts.clear()
    if (snapshot.artifacts instanceof Map) {
      for (const [path, entry] of Array.from(snapshot.artifacts.entries())) {
        this.artifacts.set(path, entry)
      }
    } else if (snapshot.artifacts && typeof snapshot.artifacts === 'object') {
      for (const [path, entry] of Object.entries(snapshot.artifacts)) {
        this.artifacts.set(path, entry as ArtifactEntry)
      }
    }

    // Restore child results
    this.childResults.clear()
    if (snapshot.childResults instanceof Map) {
      for (const [id, result] of Array.from(snapshot.childResults.entries())) {
        this.childResults.set(id, result)
      }
    } else if (snapshot.childResults && typeof snapshot.childResults === 'object') {
      for (const [id, result] of Object.entries(snapshot.childResults)) {
        this.childResults.set(id, result as FluxCellResult)
      }
    }

    // Restore parent context
    this.parentContext = snapshot.parentContext ?? ''

    // Restore plan
    this.plan = snapshot.plan ?? null

    // Restore report (and recover section counter from highest rs- index)
    this.report = snapshot.report ?? null
    if (this.report && this.report.sections.length > 0) {
      let maxCounter = 0
      for (const s of this.report.sections) {
        const m = s.id.match(/^rs-(\d+)$/)
        if (m) maxCounter = Math.max(maxCounter, parseInt(m[1], 10))
      }
      this.reportSectionCounter = maxCounter
    } else {
      this.reportSectionCounter = 0
    }

    // Update activity timestamp
    this.lastActivityAt = Date.now()

    this.logger.debug('Blackboard restored from snapshot', {
      cellId: this.cellId,
      channelEntries: CHANNELS.reduce((sum, ch) => sum + this.channels[ch].length, 0),
      scratchpadEntries: this.scratchpad.size,
      toolLogEntries: this.toolLog.length,
      artifacts: this.artifacts.size,
      childResults: this.childResults.size,
    })
  }


  /**
   * Update last activity timestamp.
   */
  private touch(): void {
    this.lastActivityAt = Date.now()
  }


  // Summary & Filtering Methods

  /**
   * Get entries from a specific channel with optional limit.
   * Used for targeted channel queries via API.
   *
   * @param channel - The channel to read from
   * @param limit - Optional limit on number of entries (default: all)
   * @returns Array of entries, newest first, sorted by priority DESC then timestamp DESC
   */
  getChannelEntries(channel: BlackboardChannel, limit?: number): BlackboardEntry[] {
    return this.read(channel, limit)
  }

  /**
   * Get a compact, human-readable summary of the blackboard state.
   * Returns counts, latest entries (truncated), and key metrics.
   *
   * Used for MCP tools and API endpoints where full snapshots are too large.
   *
   * @returns Summary object with counts and sample entries
   */
  getSummary(): BlackboardSummary {
    const channelCounts: Record<BlackboardChannel, number> = {
      findings: this.channels.findings.length,
      concerns: this.channels.concerns.length,
      decisions: this.channels.decisions.length,
      artifacts: this.channels.artifacts.length,
      requests: this.channels.requests.length,
      bugs: this.channels.bugs.length,
    }

    // Get latest 3 entries per channel with truncated content
    const latestEntries: Record<BlackboardChannel, Array<{ id: string; author: string; content: string; timestamp: number; priority: number }>> = {
      findings: [],
      concerns: [],
      decisions: [],
      artifacts: [],
      requests: [],
      bugs: [],
    }

    for (const channel of CHANNELS) {
      const entries = this.read(channel, 3)
      latestEntries[channel] = entries.map(e => ({
        id: e.id,
        author: e.author ?? 'unknown',
        content: e.content.length > 200 ? e.content.slice(0, 200) + '...' : e.content,
        timestamp: e.timestamp,
        priority: e.priority,
      }))
    }

    // Tool log summary
    const toolLogCount = this.toolLog.length
    const lastTools = this.toolLog.slice(-5).map(r => ({
      tool: r.tool,
      isError: r.isError,
      durationMs: r.durationMs,
    }))

    // Scratchpad key listing
    const scratchpadKeys = Array.from(this.scratchpad.keys()).map(key => {
      const entry = this.scratchpad.get(key)
      return {
        key,
        author: entry?.author ?? 'unknown',
        hasValue: true,
        sizeChars: entry?.value?.length ?? 0,
      }
    })

    // Artifact listing (paths + operation, no content)
    const artifactList = Array.from(this.artifacts.entries()).map(([path, entry]) => ({
      path,
      operation: entry.operation,
    }))

    // Plan summary
    const planSummary = this.plan ? {
      exists: true,
      totalSteps: this.plan.steps.length,
      completedSteps: this.plan.steps.filter(s => s.status === 'completed').length,
      steps: this.plan.steps.map(s => ({
        id: s.id,
        title: s.title,
        status: s.status,
      })),
    } : { exists: false }

    // Report summary
    const reportSummary = this.report ? {
      exists: true,
      totalSections: this.report.sections.length,
      sections: this.report.sections.map(s => ({
        id: s.id,
        type: s.type,
        title: s.title,
        status: s.status,
      })),
    } : { exists: false }

    // Child results count
    const childResultsCount = this.childResults.size

    // Estimate full snapshot size
    const totalSizeEstimateKB = this.estimateSnapshotSizeKB()

    return {
      cellId: this.cellId,
      createdAt: this.createdAt,
      lastActivityAt: this.lastActivityAt,
      channelCounts,
      latestEntries,
      toolLog: {
        count: toolLogCount,
        lastTools,
      },
      scratchpad: {
        count: scratchpadKeys.length,
        keys: scratchpadKeys,
      },
      artifacts: {
        count: artifactList.length,
        list: artifactList,
      },
      plan: planSummary,
      report: reportSummary,
      childResultsCount,
      totalSizeEstimateKB,
    }
  }

  /**
   * Estimate the size of a full snapshot in kilobytes.
   * Used to inform callers how large the full data would be.
   */
  private estimateSnapshotSizeKB(): number {
    // Rough estimation based on JSON serialization
    const snapshot = this.getSnapshot()
    const jsonStr = JSON.stringify(snapshot)
    return Math.ceil(jsonStr.length / 1024)
  }
}

/**
 * Summary type returned by Blackboard.getSummary().
 * Compact representation for API responses.
 */
export interface BlackboardSummary {
  cellId: string
  createdAt: number
  lastActivityAt: number
  channelCounts: Record<BlackboardChannel, number>
  latestEntries: Record<BlackboardChannel, Array<{
    id: string
    author: string
    content: string
    timestamp: number
    priority: number
  }>>
  toolLog: {
    count: number
    lastTools: Array<{ tool: string; isError?: boolean; durationMs?: number }>
  }
  scratchpad: {
    count: number
    keys: Array<{ key: string; author: string; hasValue: boolean; sizeChars: number }>
  }
  artifacts: {
    count: number
    list: Array<{ path: string; operation: string }>
  }
  plan: {
    exists: boolean
    totalSteps?: number
    completedSteps?: number
    steps?: Array<{ id: string; title: string; status: string }>
  }
  report: {
    exists: boolean
    totalSections?: number
    sections?: Array<{ id: string; type: string; title: string; status: string }>
  }
  childResultsCount: number
  totalSizeEstimateKB: number
}
