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

    this.logger.debug('Blackboard created', { cellId })
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
}
