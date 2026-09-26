/**
 * VENDORED — faithful type surface of `core/intelligence/flux-team/blackboard.ts`.
 * Consumed by helix (helix-posture-runner.ts, index.ts, types.ts, work-types.ts):
 * `Blackboard`, `BlackboardSummary`.
 *
 * Self-contained stub: imports only builtins and shared types from `@cassicore/foundation`.
 */
import { randomUUID } from 'crypto'
import type { ILogger } from '@cassicore/foundation'
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
} from '@cassicore/foundation'
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
} from '@cassicore/foundation'

// ── Local pure helpers (ported from the D: blackboard-search module) ─────────

const MAX_PATTERN_LENGTH = 200
const DEFAULT_SEARCH_LIMIT = 50
const MAX_SEARCH_LIMIT = 500

interface SearchCursor { ts: number; id: string; sortValue?: number }

function normalizeLimit(limit?: number): number {
  if (limit === undefined || limit <= 0) return DEFAULT_SEARCH_LIMIT
  return Math.min(limit, MAX_SEARCH_LIMIT)
}

function compilePattern(pattern: string): RegExp {
  const safe = pattern.slice(0, MAX_PATTERN_LENGTH)
  return new RegExp(safe, 'i')
}

function matchesAny(regex: RegExp, texts: Array<string | undefined>): string[] {
  const matched: string[] = []
  for (const t of texts) {
    if (t && regex.test(t)) matched.push(t)
  }
  return matched
}

function encodeCursor(cursor: SearchCursor): string {
  return Buffer.from(JSON.stringify(cursor)).toString('base64')
}

function decodeCursor(cursor: string): SearchCursor | null {
  try {
    const parsed = JSON.parse(Buffer.from(cursor, 'base64').toString('utf8'))
    if (typeof parsed?.ts === 'number' && typeof parsed?.id === 'string') {
      return { ts: parsed.ts, id: parsed.id, sortValue: parsed.sortValue }
    }
  } catch { /* invalid cursor */ }
  return null
}

function paginate<T>(
  items: T[],
  limit: number,
  cursor: SearchCursor | null,
  idOf: (item: T) => string,
  tsOf: (item: T) => number,
  sortValueOf?: (item: T) => number,
  ascending = false,
): PaginatedResult<T> {
  const start = cursor
    ? cursor.sortValue !== undefined && sortValueOf
      ? items.findIndex(it => {
          const sv = sortValueOf(it)
          const ts = tsOf(it)
          return cursor.sortValue !== undefined && sv === cursor.sortValue && ts === cursor.ts && idOf(it) === cursor.id
        })
      : items.findIndex(it => tsOf(it) === cursor.ts && idOf(it) === cursor.id)
    : 0

  const from = start === -1 ? 0 : ascending ? start + 1 : start
  const page = items.slice(from, from + limit)
  const hasMore = from + page.length < items.length
  if (page.length === 0) {
    return { items: [], total: items.length, hasMore: false, pageSize: limit }
  }
  const last = page[page.length - 1]
  const nextCursor = hasMore
    ? encodeCursor({
        ts: tsOf(last),
        id: idOf(last),
        sortValue: sortValueOf ? sortValueOf(last) : undefined,
      })
    : undefined
  return { items: page, total: items.length, hasMore, cursor: nextCursor, pageSize: page.length }
}

interface BaseFilters {
  author?: string
  since?: number
  until?: number
}

function passesBaseFilters(
  opts: BaseFilters,
  author: string | undefined,
  ts: number,
): boolean {
  if (opts.author && author !== opts.author) return false
  if (opts.since !== undefined && ts < opts.since) return false
  if (opts.until !== undefined && ts > opts.until) return false
  return true
}

function encodeCompositeCursor(cursors: Record<string, string>): string {
  return Buffer.from(JSON.stringify(cursors)).toString('base64')
}

function decodeCompositeCursor(cursor: string): Record<string, string> | null {
  try {
    const parsed = JSON.parse(Buffer.from(cursor, 'base64').toString('utf8'))
    if (parsed && typeof parsed === 'object') return parsed as Record<string, string>
  } catch { /* invalid */ }
  return null
}

// ── Blackboard constants ────────────────────────────────────────────────────

const CHANNEL_LIMIT = 500
const TOOL_LOG_LIMIT = 500
const DEFAULT_SCRATCHPAD_TTL_MS = 30 * 60 * 1000

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

// ── Blackboard ──────────────────────────────────────────────────────────────

export class Blackboard {
  private readonly logger: ILogger
  private readonly cellId: string

  private readonly channels: Record<BlackboardChannel, BlackboardEntry[]>
  private readonly subscriptions: Map<string, BlackboardSubscription>
  private subscriptionCounter = 0
  private readonly scratchpad: Map<string, FluxScratchpadEntry>
  private readonly toolLog: FluxToolRecord[]
  private readonly artifacts: Map<string, ArtifactEntry>
  private readonly childResults: Map<string, FluxCellResult>
  private parentContext: string
  private plan: Plan | null
  private report: Report | null
  private reportSectionCounter = 0
  private readonly createdAt: number
  private lastActivityAt: number
  private artifactNamespace?: string
  private autoPersistArtifacts: boolean

  constructor(logger: ILogger, cellId: string) {
    this.logger = logger.child('blackboard')
    this.cellId = cellId
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
  }

  getArtifactNamespace(): string | undefined {
    return this.artifactNamespace
  }

  getAutoPersistEnabled(): boolean {
    return this.autoPersistArtifacts
  }

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
    if (channelEntries.length > CHANNEL_LIMIT) {
      const excess = channelEntries.length - CHANNEL_LIMIT
      channelEntries.splice(0, excess)
    }
    this.touch()
    this.notifySubscriptions(channel, completeEntry)
    return completeEntry
  }

  read(channel: BlackboardChannel, limit?: number): BlackboardEntry[] {
    const entries = [...this.channels[channel]]
    entries.sort((a, b) => {
      if (b.priority !== a.priority) return b.priority - a.priority
      return b.timestamp - a.timestamp
    })
    if (limit && limit < entries.length) {
      return entries.slice(0, limit)
    }
    return entries
  }

  readAll(): BlackboardEntry[] {
    const allEntries: BlackboardEntry[] = []
    for (const channel of CHANNELS) {
      allEntries.push(...this.channels[channel])
    }
    allEntries.sort((a, b) => b.timestamp - a.timestamp)
    return allEntries
  }

  subscribe(
    channel: BlackboardChannel,
    tags: string[] | undefined,
    callback: (entry: BlackboardEntry) => void,
  ): () => void {
    const id = `sub-${++this.subscriptionCounter}-${Date.now()}`
    const subscription: BlackboardSubscription = { id, channel, tags, callback }
    this.subscriptions.set(id, subscription)
    return () => {
      this.subscriptions.delete(id)
    }
  }

  private notifySubscriptions(channel: BlackboardChannel, entry: BlackboardEntry): void {
    const subs = Array.from(this.subscriptions.values())
    for (const subscription of subs) {
      if (subscription.channel !== channel) continue
      if (subscription.tags && subscription.tags.length > 0) {
        const hasAllTags = subscription.tags.every(tag => entry.tags.includes(tag))
        if (!hasAllTags) continue
      }
      try {
        subscription.callback(entry)
      } catch { /* best-effort */ }
    }
  }

  setScratchpad(key: string, value: string, author: string, ttlMs?: number): void {
    const entry: FluxScratchpadEntry = {
      key, value, author, createdAt: Date.now(), ttlMs: ttlMs ?? DEFAULT_SCRATCHPAD_TTL_MS,
    }
    this.scratchpad.set(key, entry)
    this.touch()
  }

  getScratchpad(key: string): string | undefined {
    const entry = this.scratchpad.get(key)
    if (!entry) return undefined
    const now = Date.now()
    if (now - entry.createdAt >= entry.ttlMs) {
      this.scratchpad.delete(key)
      return undefined
    }
    return entry.value
  }

  getAllScratchpad(): Map<string, string> {
    const result = new Map<string, string>()
    const now = Date.now()
    const entries = Array.from(this.scratchpad.entries())
    for (const [key, entry] of entries) {
      if (now - entry.createdAt < entry.ttlMs) {
        result.set(key, entry.value)
      } else {
        this.scratchpad.delete(key)
      }
    }
    return result
  }

  addToolRecord(record: Omit<FluxToolRecord, 'timestamp'>): void {
    const entry: FluxToolRecord = { ...record, timestamp: Date.now() }
    this.toolLog.push(entry)
    if (this.toolLog.length > TOOL_LOG_LIMIT) {
      this.toolLog.shift()
    }
    this.touch()
  }

  getToolLog(limit?: number): FluxToolRecord[] {
    if (limit && limit < this.toolLog.length) {
      return this.toolLog.slice(-limit)
    }
    return [...this.toolLog]
  }

  addArtifact(entry: Omit<ArtifactEntry, 'timestamp'>): void {
    const completeEntry: ArtifactEntry = { ...entry, timestamp: Date.now() }
    this.artifacts.set(entry.path, completeEntry)
    this.touch()
  }

  getArtifacts(): ArtifactEntry[] {
    return Array.from(this.artifacts.values())
  }

  setChildResult(childCellId: string, result: FluxCellResult): void {
    this.childResults.set(childCellId, result)
    this.touch()
  }

  getChildResults(): Map<string, FluxCellResult> {
    return new Map(this.childResults)
  }

  setParentContext(context: string): void {
    this.parentContext = context
    this.touch()
  }

  getParentContext(): string {
    return this.parentContext
  }

  initPlan(goal: string): Plan {
    if (this.plan) return this.plan
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
    return this.plan
  }

  getPlan(): Plan | null {
    return this.plan
  }

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
    return completeStep
  }

  updatePlanStep(
    stepId: string,
    update: Partial<Pick<PlanStep, 'title' | 'description' | 'status' | 'order' | 'dependencies' | 'priority' | 'outcome' | 'rejectionReason' | 'tags'>>,
  ): PlanStep | null {
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
    return step
  }

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
    return this.plan
  }

  private static readonly DEFAULT_STALL_TIMEOUT_MS = 30 * 60 * 1000

  claimPlanStep(stepId: string, assignee: string, expectedStatus: PlanStepStatus = 'approved'): PlanStep | null {
    if (!this.plan) return null
    const step = this.plan.steps.find(s => s.id === stepId)
    if (!step) return null
    if (step.status !== expectedStatus) return null
    if (step.status !== 'approved' || step.assignee) return null
    const now = Date.now()
    step.status = 'in_progress'
    step.assignee = assignee
    step.claimedAt = now
    step.lastActivityAt = now
    step.updatedAt = now
    this.plan.updatedAt = now
    this.touch()
    return step
  }

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
    return true
  }

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
    return step
  }

  getAvailableSteps(): PlanStep[] {
    if (!this.plan) return []
    return this.plan.steps
      .filter(s => s.status === 'approved' && !s.assignee)
      .sort((a, b) => {
        const prio = { high: 0, medium: 1, low: 2 }
        const pd = (prio[a.priority] ?? 1) - (prio[b.priority] ?? 1)
        return pd !== 0 ? pd : a.order - b.order
      })
  }

  getClaimedSteps(assignee?: string): PlanStep[] {
    if (!this.plan) return []
    return this.plan.steps.filter(s => {
      if (s.status !== 'in_progress' || !s.assignee) return false
      return assignee ? s.assignee === assignee : true
    })
  }

  reclaimStalledWork(maxAgeMs: number = Blackboard.DEFAULT_STALL_TIMEOUT_MS): number {
    if (!this.plan) return 0
    const now = Date.now()
    let reclaimed = 0
    for (const step of this.plan.steps) {
      if (step.status !== 'in_progress' || !step.assignee) continue
      const timeout = step.stallTimeoutMs ?? maxAgeMs
      const lastActive = step.lastActivityAt ?? step.claimedAt ?? step.updatedAt
      if (now - lastActive > timeout) {
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

  formatPlanForContext(): string {
    if (!this.plan || this.plan.steps.length === 0) return ''
    const lines: string[] = [
      `Plan: ${this.plan.goal}`,
      `Status: ${this.plan.status}`,
    ]
    if (this.plan.summary) {
      lines.push(`Summary: ${this.plan.summary}`)
    }
    const available = this.plan.steps.filter(s => s.status === 'approved' && !s.assignee).length
    const claimed = this.plan.steps.filter(s => s.status === 'in_progress' && s.assignee).length
    const completed = this.plan.steps.filter(s => s.status === 'completed').length
    const total = this.plan.steps.length
    lines.push(`Progress: ${completed}/${total} completed, ${claimed} in-progress, ${available} available`)
    const sortedSteps = [...this.plan.steps].sort((a, b) => a.order - b.order)
    lines.push('')
    lines.push('Steps:')
    for (const step of sortedSteps) {
      const depStr = step.dependencies.length > 0 ? ` (deps: ${step.dependencies.join(', ')})` : ''
      const assigneeStr = step.assignee ? ` [assigned: ${step.assignee}]` : ''
      lines.push(`  ${step.order}. [${step.status.toUpperCase()}] ${step.title} (${step.priority})${depStr}${assigneeStr}`)
      lines.push(`     ${step.description}`)
      if (step.outcome) lines.push(`     Outcome: ${step.outcome}`)
      if (step.rejectionReason) lines.push(`     Rejected: ${step.rejectionReason}`)
    }
    return lines.join('\n')
  }

  setReport(report: Report): void {
    this.report = report
    this.touch()
  }

  getReport(): Report | null {
    return this.report
  }

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

  reviseReportSection(sectionId: string, content: string, _reason?: string): ReportSection | null {
    if (!this.report) return null
    const original = this.report.sections.find(s => s.id === sectionId)
    if (!original) return null
    original.superseded = true
    original.status = 'superseded'
    original.updatedAt = Date.now()
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

  discardReportSection(sectionId: string): boolean {
    if (!this.report) return false
    const idx = this.report.sections.findIndex(s => s.id === sectionId && s.status === 'draft')
    if (idx === -1) return false
    this.report.sections.splice(idx, 1)
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
    const byType: Partial<Record<string, number>> = {}
    for (const s of active) byType[s.type] = (byType[s.type] ?? 0) + 1
    const byAuthor: Record<string, number> = {}
    for (const s of active) byAuthor[s.author] = (byAuthor[s.author] ?? 0) + 1
    const withConf = active.filter(s => s.confidence != null)
    const avgConfidence = withConf.length > 0
      ? withConf.reduce((sum, s) => sum + (s.confidence ?? 0), 0) / withConf.length
      : 0
    const threads = new Set(active.filter(s => s.threadId).map(s => s.threadId))
    const decisionThreads = new Set(
      active.filter(s => s.type === 'decision').map(s => s.threadId).filter(Boolean)
    )
    const unresolvedConcerns = active.filter(
      s => s.type === 'concern' && (!s.threadId || !decisionThreads.has(s.threadId))
    ).length
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

  formatReportForContext(): string {
    if (!this.report || this.report.sections.length === 0) return ''
    const active = this.report.sections.filter(s => s.status === 'active')
    const drafts = this.report.sections.filter(s => s.status === 'draft')
    if (active.length === 0 && drafts.length === 0) return ''
    const parts: string[] = ['## Incremental Report']
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

  assembleContext(nodeId: string, tokenBudget: number): string {
    const charBudget = tokenBudget * 4
    const sections: string[] = []
    let currentLength = 0
    const addSection = (title: string, content: string): boolean => {
      if (!content) return true
      const section = `## ${title}\n${content}\n\n`
      if (currentLength + section.length > charBudget) return false
      sections.push(section)
      currentLength += section.length
      return true
    }
    if (this.parentContext) {
      if (!addSection('Parent Context', this.parentContext)) {
        const remaining = charBudget - currentLength - 20
        if (remaining > 0) {
          sections.push(`## Parent Context\n${this.parentContext.slice(0, remaining)}...\n\n`)
        }
        return sections.join('')
      }
    }
    const planText = this.formatPlanForContext()
    if (planText) addSection('Current Plan', planText)
    const allEntries = this.readAll()
    for (const entry of allEntries) {
      const entryText = this.formatChannelEntry(entry)
      if (!addSection(`${entry.channel.toUpperCase()}: ${entry.id.slice(0, 8)}`, entryText)) {
        return sections.join('')
      }
    }
    const scratchpad = this.getAllScratchpad()
    if (scratchpad.size > 0) {
      const scratchpadText = Array.from(scratchpad.entries())
        .map(([k, v]) => `- **${k}**: ${v}`)
        .join('\n')
      addSection('Scratchpad', scratchpadText)
    }
    if (this.childResults.size > 0) {
      const childLines: string[] = []
      for (const [childId, result] of Array.from(this.childResults.entries())) {
        const status = result.success ? 'SUCCESS' : 'FAILED'
        let line = `### ${childId} [${status}]`
        if (result.output) line += `\n${result.output.slice(0, 500)}`
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

  // Search & Pagination

  searchChannel(opts: ChannelSearchOptions = {}): PaginatedResult<BlackboardEntry> {
    const limit = normalizeLimit(opts.limit)
    const cursor = opts.cursor ? decodeCursor(opts.cursor) : null
    const regex = opts.pattern ? compilePattern(opts.pattern) : null
    let entries: BlackboardEntry[]
    if (opts.channel) {
      entries = [...this.channels[opts.channel]]
    } else {
      entries = CHANNELS.flatMap(ch => this.channels[ch])
    }
    entries.sort((a, b) => {
      const pd = b.priority - a.priority
      return pd !== 0 ? pd : b.timestamp - a.timestamp
    })
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

  searchScratchpad(opts: ScratchpadSearchOptions = {}): PaginatedResult<FluxScratchpadEntry> {
    const limit = normalizeLimit(opts.limit)
    const cursor = opts.cursor ? decodeCursor(opts.cursor) : null
    const regex = opts.pattern ? compilePattern(opts.pattern) : null
    const now = Date.now()
    const entries: FluxScratchpadEntry[] = []
    for (const [, entry] of this.scratchpad) {
      const expired = now - entry.createdAt >= entry.ttlMs
      if (expired && !opts.includeExpired) {
        this.scratchpad.delete(entry.key)
        continue
      }
      entries.push(entry)
    }
    entries.sort((a, b) => b.createdAt - a.createdAt)
    const filtered = entries.filter(entry => {
      if (!passesBaseFilters(opts, entry.author, entry.createdAt)) return false
      if (regex && matchesAny(regex, [entry.key, entry.value]).length === 0) return false
      return true
    })
    return paginate(filtered, limit, cursor, e => e.key, e => e.createdAt)
  }

  searchToolLog(opts: ToolLogSearchOptions = {}): PaginatedResult<FluxToolRecord> {
    const limit = normalizeLimit(opts.limit)
    const cursor = opts.cursor ? decodeCursor(opts.cursor) : null
    const regex = opts.pattern ? compilePattern(opts.pattern) : null
    const records = [...this.toolLog].reverse()
    const filtered = records.filter(record => {
      if (!passesBaseFilters(opts, undefined, record.timestamp)) return false
      if (opts.tool && record.tool !== opts.tool) return false
      if (opts.nodeId && record.nodeId !== opts.nodeId) return false
      if (opts.isError !== undefined && record.isError !== opts.isError) return false
      if (regex && matchesAny(regex, [record.tool, record.nodeId]).length === 0) return false
      return true
    })
    return paginate(
      filtered, limit, cursor,
      r => `${r.tool}:${r.nodeId}:${r.timestamp}`,
      r => r.timestamp,
    )
  }

  searchArtifacts(opts: ArtifactSearchOptions = {}): PaginatedResult<ArtifactEntry> {
    const limit = normalizeLimit(opts.limit)
    const cursor = opts.cursor ? decodeCursor(opts.cursor) : null
    const regex = opts.pattern ? compilePattern(opts.pattern) : null
    const entries = Array.from(this.artifacts.values())
    entries.sort((a, b) => b.timestamp - a.timestamp)
    const filtered = entries.filter(entry => {
      if (!passesBaseFilters(opts, entry.author, entry.timestamp)) return false
      if (opts.operation && entry.operation !== opts.operation) return false
      if (regex && matchesAny(regex, [entry.path, entry.author]).length === 0) return false
      return true
    })
    return paginate(filtered, limit, cursor, e => e.path, e => e.timestamp)
  }

  searchPlan(opts: PlanSearchOptions = {}): PaginatedResult<PlanStep> {
    if (!this.plan) {
      return { items: [], total: 0, hasMore: false, pageSize: 0 }
    }
    const limit = normalizeLimit(opts.limit)
    const cursor = opts.cursor ? decodeCursor(opts.cursor) : null
    const regex = opts.pattern ? compilePattern(opts.pattern) : null
    const steps = [...this.plan.steps].sort((a, b) => a.order - b.order)
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

  searchReport(opts: ReportSearchOptions = {}): PaginatedResult<ReportSection> {
    if (!this.report) {
      return { items: [], total: 0, hasMore: false, pageSize: 0 }
    }
    const limit = normalizeLimit(opts.limit)
    const cursor = opts.cursor ? decodeCursor(opts.cursor) : null
    const regex = opts.pattern ? compilePattern(opts.pattern) : null
    const sections = [...this.report.sections].sort((a, b) => b.createdAt - a.createdAt)
    const filtered = sections.filter(section => {
      if (!passesBaseFilters(opts, section.author, section.createdAt)) return false
      if (opts.type && section.type !== opts.type) return false
      if (opts.status && section.status !== opts.status) return false
      if (regex && matchesAny(regex, [section.title, section.content, section.author]).length === 0) return false
      return true
    })
    return paginate(filtered, limit, cursor, s => s.id, s => s.createdAt)
  }

  searchAll(opts: CrossBoardSearchOptions): CrossBoardSearchResult {
    const boards = opts.boards ?? ALL_SEARCHABLE_BOARDS
    const limitPerBoard = normalizeLimit(opts.limitPerBoard)
    const compositeCursors = opts.cursor ? decodeCompositeCursor(opts.cursor) : null
    const result: CrossBoardSearchResult = { boards: {}, totalMatches: 0, rankedBoards: [] }
    const boardCounts: Array<{ board: SearchableBoard; count: number }> = []
    const nextCursors: Record<string, string> = {}

    for (const board of boards) {
      const boardCursor = compositeCursors?.[board] ?? undefined
      switch (board) {
        case 'channel': {
          const r = this.searchChannel({ pattern: opts.pattern, limit: limitPerBoard, cursor: boardCursor, author: opts.author, since: opts.since, until: opts.until })
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
          const r = this.searchScratchpad({ pattern: opts.pattern, limit: limitPerBoard, cursor: boardCursor, author: opts.author, since: opts.since, until: opts.until })
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
          const r = this.searchToolLog({ pattern: opts.pattern, limit: limitPerBoard, cursor: boardCursor, since: opts.since, until: opts.until })
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
          const r = this.searchArtifacts({ pattern: opts.pattern, limit: limitPerBoard, cursor: boardCursor, author: opts.author, since: opts.since, until: opts.until })
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
          const r = this.searchPlan({ pattern: opts.pattern, limit: limitPerBoard, cursor: boardCursor, author: opts.author, since: opts.since, until: opts.until })
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
          const r = this.searchReport({ pattern: opts.pattern, limit: limitPerBoard, cursor: boardCursor, author: opts.author, since: opts.since, until: opts.until })
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

    result.totalMatches = boardCounts.reduce((sum, b) => sum + b.count, 0)
    result.rankedBoards = boardCounts.sort((a, b) => b.count - a.count)
    if (Object.keys(nextCursors).length > 0) {
      result.cursor = encodeCompositeCursor(nextCursors)
    }
    return result
  }

  getChangesSince(window: ChangeWindow): BoardChanges {
    const since = window.since
    const until = window.until ?? Date.now()
    const changes: BoardChanges = {
      channels: [], scratchpad: [], toolLog: [], artifacts: [], plan: [], report: [],
    }
    for (const ch of CHANNELS) {
      for (const entry of this.channels[ch]) {
        if (entry.timestamp >= since && entry.timestamp <= until) {
          changes.channels.push({ channel: ch, entry })
        }
      }
    }
    const now = Date.now()
    for (const [, entry] of this.scratchpad) {
      const expired = now - entry.createdAt >= entry.ttlMs
      if (expired) continue
      if (entry.createdAt >= since && entry.createdAt <= until) {
        changes.scratchpad.push(entry)
      }
    }
    for (const record of this.toolLog) {
      if (record.timestamp >= since && record.timestamp <= until) {
        changes.toolLog.push(record)
      }
    }
    for (const [, entry] of this.artifacts) {
      if (entry.timestamp >= since && entry.timestamp <= until) {
        changes.artifacts.push(entry)
      }
    }
    if (this.plan) {
      for (const step of this.plan.steps) {
        if (step.createdAt >= since && step.createdAt <= until) {
          changes.plan.push({ step, operation: 'created' })
        } else if (step.updatedAt >= since && step.updatedAt <= until) {
          changes.plan.push({ step, operation: 'updated' })
        }
      }
    }
    if (this.report) {
      for (const section of this.report.sections) {
        if (section.createdAt >= since && section.createdAt <= until) {
          changes.report.push({ section, operation: 'created' })
        } else if (section.updatedAt >= since && section.updatedAt <= until) {
          changes.report.push({ section, operation: section.status === 'superseded' ? 'superseded' : 'updated' })
        }
      }
    }
    return changes
  }

  buildWatchResult(
    boardName: string,
    window: ChangeWindow,
    boards?: SearchableBoard[],
    includeContent = true,
  ): BlackboardWatchResult {
    const pollTime = Date.now()
    const until = window.until ?? pollTime
    const changes = this.getChangesSince({ since: window.since, until })
    const filteredChanges: BoardChanges = {
      channels: boards && !boards.includes('channel') ? [] : changes.channels,
      scratchpad: boards && !boards.includes('scratchpad') ? [] : changes.scratchpad,
      toolLog: boards && !boards.includes('toolLog') ? [] : changes.toolLog,
      artifacts: boards && !boards.includes('artifact') ? [] : changes.artifacts,
      plan: boards && !boards.includes('plan') ? [] : changes.plan,
      report: boards && !boards.includes('report') ? [] : changes.report,
    }
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
    const outputChanges = includeContent ? filteredChanges : {
      channels: filteredChanges.channels.map(c => ({ channel: c.channel, entry: { ...c.entry, content: '' } })),
      scratchpad: filteredChanges.scratchpad.map(s => ({ ...s, value: '' })),
      toolLog: filteredChanges.toolLog.map(t => ({ ...t, input: undefined, output: undefined, result: '' })),
      artifacts: filteredChanges.artifacts,
      plan: filteredChanges.plan.map(p => ({ step: { ...p.step, description: '' }, operation: p.operation })),
      report: filteredChanges.report.map(r => ({ section: { ...r.section, content: '' }, operation: r.operation })),
    }
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
      changes: outputChanges as BoardChanges,
    }
  }

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

  restoreFromSnapshot(snapshot: BlackboardState): void {
    for (const channel of CHANNELS) {
      (this.channels[channel] as BlackboardEntry[]) = [...(snapshot.channels[channel] ?? [])]
    }
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
    this.toolLog.length = 0
    this.toolLog.push(...(snapshot.toolLog ?? []))
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
    this.parentContext = snapshot.parentContext ?? ''
    this.plan = snapshot.plan ?? null
    this.report = snapshot.report ?? null
    this.reportSectionCounter = 0
    if (this.report && this.report.sections.length > 0) {
      let maxCounter = 0
      for (const s of this.report.sections) {
        const m = s.id.match(/^rs-(\d+)$/)
        if (m) maxCounter = Math.max(maxCounter, parseInt(m[1], 10))
      }
      this.reportSectionCounter = maxCounter
    }
    this.lastActivityAt = Date.now()
  }

  private touch(): void {
    this.lastActivityAt = Date.now()
  }

  getChannelEntries(channel: BlackboardChannel, limit?: number): BlackboardEntry[] {
    return this.read(channel, limit)
  }

  getSummary(): BlackboardSummary {
    const channelCounts: Record<BlackboardChannel, number> = {
      findings: this.channels.findings.length,
      concerns: this.channels.concerns.length,
      decisions: this.channels.decisions.length,
      artifacts: this.channels.artifacts.length,
      requests: this.channels.requests.length,
      bugs: this.channels.bugs.length,
    }
    const latestEntries: Record<BlackboardChannel, Array<{ id: string; author: string; content: string; timestamp: number; priority: number }>> = {
      findings: [], concerns: [], decisions: [], artifacts: [], requests: [], bugs: [],
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
    const toolLogCount = this.toolLog.length
    const lastTools = this.toolLog.slice(-5).map(r => ({
      tool: r.tool,
      isError: r.isError,
      durationMs: r.durationMs,
    }))
    const scratchpadKeys = Array.from(this.scratchpad.keys()).map(key => {
      const entry = this.scratchpad.get(key)
      return { key, author: entry?.author ?? 'unknown', hasValue: true, sizeChars: entry?.value?.length ?? 0 }
    })
    const artifactList = Array.from(this.artifacts.entries()).map(([path, entry]) => ({
      path,
      operation: entry.operation,
    }))
    const planSummary = this.plan ? {
      exists: true,
      totalSteps: this.plan.steps.length,
      completedSteps: this.plan.steps.filter(s => s.status === 'completed').length,
      steps: this.plan.steps.map(s => ({ id: s.id, title: s.title, status: s.status })),
    } : { exists: false }
    const reportSummary = this.report ? {
      exists: true,
      totalSections: this.report.sections.length,
      sections: this.report.sections.map(s => ({ id: s.id, type: s.type, title: s.title, status: s.status })),
    } : { exists: false }
    const childResultsCount = this.childResults.size
    const totalSizeEstimateKB = this.estimateSnapshotSizeKB()
    return {
      cellId: this.cellId,
      createdAt: this.createdAt,
      lastActivityAt: this.lastActivityAt,
      channelCounts,
      latestEntries,
      toolLog: { count: toolLogCount, lastTools },
      scratchpad: { count: scratchpadKeys.length, keys: scratchpadKeys },
      artifacts: { count: artifactList.length, list: artifactList },
      plan: planSummary,
      report: reportSummary,
      childResultsCount,
      totalSizeEstimateKB,
    }
  }

  private estimateSnapshotSizeKB(): number {
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
