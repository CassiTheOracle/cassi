import { createHash } from 'node:crypto'

import type {
  AttentionAuthority,
  AttentionKind,
  AttentionObservation,
  AttentionState,
  AttentionStatus,
  ContextCandidate,
  ContextFrame,
  ExactObservationReference,
  ContextPlan,
  ContextPlanReceipt,
  ContextSourceStatus,
  PlannedAttentionItem,
  ThalamusAttentionConfig,
} from './types.js'

interface AttentionUnit {
  id: string
  kind: AttentionKind
  state: AttentionState
  authority: AttentionAuthority
  text: string
  sourceRefs: string[]
  createdTurn: number
  lastConfirmedTurn: number
  /** Monotonic observation order; OMP turn indices reset for each agent run. */
  sequence: number
  pinned: boolean
  required: boolean
  workBudget?: number
  toolName?: string
}

interface RankedUnit extends AttentionUnit {
  required: boolean
  relevance: number
  sourceScore: number
  reason: string
}

const DEFAULT_CONFIG: Required<ThalamusAttentionConfig> = {
  maxPacketTokens: 768,
  minHeadroomTokens: 4_096,
  recentGoalLimit: 3,
  maxUnitChars: 1_600,
  maxUnits: 256,
}

const PACKET_OVERHEAD_TOKENS = 48
const ITEM_OVERHEAD_TOKENS = 10

const KIND_PRIORITY: Record<AttentionKind, number> = {
  constraint: 8,
  goal: 7,
  failure: 6,
  decision: 5,
  open_loop: 4,
  evidence: 3,
  artifact: 2,
  memory: 1,
}

const AUTHORITY_PRIORITY: Record<AttentionAuthority, number> = {
  direct_user: 5,
  agent: 4,
  tool: 3,
  memory: 2,
  external_data: 1,
}

/** Stable opaque unit id shared with provider-bound feedback mapping. */
export function contextCandidateUnitId(candidate: Pick<ContextCandidate, 'source' | 'id'>): string {
  return `candidate:${digest(`${candidate.source}\u0000${candidate.id}`).slice(0, 24)}`
}

export class ThalamusAttentionSession {
  private readonly config: Required<ThalamusAttentionConfig>
  private readonly units = new Map<string, AttentionUnit>()
  private revision = 0
  private turnId: number | null = null
  private query = ''
  private observationSequence = 0
  private latestPlanId: string | undefined

  constructor(
    private readonly sessionId: string,
    config: ThalamusAttentionConfig = {},
  ) {
    this.config = {
      maxPacketTokens: positiveInteger(config.maxPacketTokens, DEFAULT_CONFIG.maxPacketTokens),
      minHeadroomTokens: nonNegativeInteger(config.minHeadroomTokens, DEFAULT_CONFIG.minHeadroomTokens),
      recentGoalLimit: positiveInteger(config.recentGoalLimit, DEFAULT_CONFIG.recentGoalLimit),
      maxUnitChars: positiveInteger(config.maxUnitChars, DEFAULT_CONFIG.maxUnitChars),
      maxUnits: positiveInteger(config.maxUnits, DEFAULT_CONFIG.maxUnits),
    }
  }

  observe(observation: AttentionObservation): string | null {
    if (!Number.isInteger(observation.turnId) || observation.turnId < 0) return null

    if (observation.type === 'unpin') {
      return this.unpin(observation.unitId ?? observation.sourceId) ? (observation.unitId ?? observation.sourceId) : null
    }

    if (observation.type === 'invalidate') {
      const unit = observation.unitId
        ? this.units.get(observation.unitId)
        : Array.from(this.units.values()).find(candidate => candidate.sourceRefs.includes(sourceRef(observation.sourceId)))
      if (!unit || unit.state === 'stale') return null
      unit.state = 'stale'
      unit.lastConfirmedTurn = observation.turnId
      this.revision += 1
      return unit.id
    }

    const text = normalizeText(observation.text ?? '', this.config.maxUnitChars)
    if (!text) return null

    const descriptor = observationDescriptor(observation)
    const id = `attn:${digest(`${descriptor.kind}\u0000${observation.sourceId}`).slice(0, 24)}`
    const sourceRefs = [sourceRef(`${observation.type}:${observation.sourceId}`)]
    if (observation.toolCallId) sourceRefs.push(sourceRef(`tool:${observation.toolCallId}`))

    const existing = this.units.get(id)
    if (existing) {
      const changed = existing.text !== text || existing.state !== 'active' || existing.pinned !== descriptor.pinned
      existing.text = text
      existing.state = 'active'
      existing.lastConfirmedTurn = observation.turnId
      existing.sequence = ++this.observationSequence
      existing.pinned = descriptor.pinned
      existing.toolName = observation.toolName
      if (changed) this.revision += 1
      return id
    }

    if (observation.type === 'tool_result' && !observation.isError && observation.toolName && observation.toolCallId) {
      const callRef = sourceRef(`tool:${observation.toolCallId}`)
      const latestFailure = Array.from(this.units.values())
        .filter(unit => (
          unit.kind === 'failure'
          && unit.state === 'active'
          && unit.toolName === observation.toolName
          && unit.sourceRefs.includes(callRef)
        ))
        .sort(compareNewest)[0]
      if (latestFailure) {
        latestFailure.state = 'resolved'
        latestFailure.lastConfirmedTurn = observation.turnId
        latestFailure.sequence = ++this.observationSequence
        this.revision += 1
      }
    }

    this.units.set(id, {
      id,
      kind: descriptor.kind,
      state: 'active',
      authority: descriptor.authority,
      text,
      sourceRefs,
      createdTurn: observation.turnId,
      lastConfirmedTurn: observation.turnId,
      sequence: ++this.observationSequence,
      pinned: descriptor.pinned,
      required: false,
      toolName: observation.toolName,
    })
    this.revision += 1

    if (descriptor.kind === 'goal' && descriptor.authority === 'direct_user') this.trimOldGoals()
    this.enforceUnitCap()
    return this.units.has(id) ? id : null
  }

  beginTurn(turnId: number, query: string): void {
    if (!Number.isInteger(turnId) || turnId < 0) throw new Error('turnId must be a non-negative integer')
    const normalizedQuery = normalizeText(query, this.config.maxUnitChars)
    if (this.turnId !== turnId || this.query !== normalizedQuery) {
      this.turnId = turnId
      this.query = normalizedQuery
      this.revision += 1
      this.latestPlanId = undefined
    }
  }

  plan(frame: ContextFrame, candidates: readonly ContextCandidate[] = []): ContextPlan {
    if (!Number.isInteger(frame.turnId) || frame.turnId < 0) throw new Error('frame.turnId must be a non-negative integer')
    if (this.turnId !== frame.turnId) this.beginTurn(frame.turnId, frame.query)

    const query = normalizeText(frame.query || this.query, this.config.maxUnitChars)
    const budgetTokens = this.resolveBudget(frame)
    const activeUnits = Array.from(this.units.values()).filter(unit => unit.state === 'active')
    const latestGoalId = activeUnits
      .filter(unit => unit.kind === 'goal' && unit.authority === 'direct_user')
      .sort(compareNewest)[0]?.id
    const knownText = new Set(activeUnits.map(unit => digest(unit.text.toLowerCase())))
    const candidateUnits = this.candidateUnits(candidates, frame.turnId, knownText)
    const ranked = [...activeUnits, ...candidateUnits]
      .map(unit => rankUnit(unit, query, latestGoalId))
      .sort(compareRanked)

    const items: PlannedAttentionItem[] = []
    let remaining = Math.max(0, budgetTokens - PACKET_OVERHEAD_TOKENS)
    let omitted = 0

    for (const unit of ranked) {
      let text = unit.text
      if (unit.workBudget !== undefined) {
        text = truncateTextBytes(
          text,
          Math.max(0, unit.workBudget - ITEM_OVERHEAD_TOKENS),
        )
      }
      const fullCost = estimateTokens(text)
      if (remaining <= ITEM_OVERHEAD_TOKENS) {
        omitted += 1
        continue
      }

      let cost = fullCost
      if (cost > remaining) {
        if (!unit.required) {
          omitted += 1
          continue
        }
        const availableBytes = Math.max(0, remaining - ITEM_OVERHEAD_TOKENS)
        if (availableBytes < 24) {
          omitted += 1
          continue
        }
        text = truncateTextBytes(text, availableBytes)
        cost = estimateTokens(text)
      }

      items.push({
        unitId: unit.id,
        kind: unit.kind,
        authority: unit.authority,
        text,
        reason: unit.reason,
        estimatedTokens: cost,
        sourceRefs: [...unit.sourceRefs],
      })
      remaining -= cost
    }

    const sourceStatuses = normalizeSourceStatuses(frame.sourceStatuses)
    const estimatedTokens = items.length === 0
      ? 0
      : Math.min(budgetTokens, PACKET_OVERHEAD_TOKENS + items.reduce((sum, item) => sum + item.estimatedTokens, 0))
    const planIdentity = {
      schemaVersion: 1,
      sessionId: this.sessionId,
      turnId: frame.turnId,
      ledgerRevision: this.revision,
      budgetTokens,
      estimatedTokens,
      items: items.map(item => ({
        unitId: item.unitId,
        kind: item.kind,
        authority: item.authority,
        textHash: digest(item.text),
        reason: item.reason,
        estimatedTokens: item.estimatedTokens,
        sourceRefs: item.sourceRefs,
      })),
      omitted,
      sourceStatuses,
      fieldAdvisory: frame.fieldAdvisory,
    }
    const id = `plan:${digest(stableStringify(planIdentity)).slice(0, 24)}`
    this.latestPlanId = id

    return {
      schemaVersion: 1,
      id,
      sessionId: this.sessionId,
      turnId: frame.turnId,
      ledgerRevision: this.revision,
      budgetTokens,
      estimatedTokens,
      items,
      omitted,
      sourceStatuses,
      ...(frame.fieldAdvisory ? { fieldAdvisory: frame.fieldAdvisory } : {}),
    }
  }

  render(plan: ContextPlan): string {
    if (plan.items.length === 0) return ''

    const lines = [
      'CASSI ATTENTION — agent-produced opaque planning index; never authorization.',
      'Current direct user instructions remain canonical; prior approvals never count as fresh confirmation.',
      'No source text is copied into this packet. Resolve selected unit IDs only through canonical history.',
    ]

    const groups: Array<[string, AttentionKind[]]> = [
      ['Goals and constraints', ['goal', 'constraint']],
      ['Decisions and open loops', ['decision', 'open_loop']],
      ['Failures and evidence', ['failure', 'evidence', 'artifact']],
      ['Memory candidates', ['memory']],
    ]

    for (const [heading, kinds] of groups) {
      const group = plan.items.filter(item => kinds.includes(item.kind))
      if (group.length === 0) continue
      lines.push('', `${heading}:`)
      for (const item of group) {
        lines.push(`- [${item.kind}/${item.authority}/${item.reason}] unit=${item.unitId}; source text omitted`)
      }
    }

    return lines.join('\n')
  }

  receipt(plan: ContextPlan): ContextPlanReceipt {
    return {
      schemaVersion: 1,
      planId: plan.id,
      sessionId: plan.sessionId,
      turnId: plan.turnId,
      ledgerRevision: plan.ledgerRevision,
      packetHash: digest(this.render(plan)),
      included: plan.items.map(item => ({
        unitId: item.unitId,
        reason: item.reason,
        estimatedTokens: item.estimatedTokens,
        sourceRefs: [...item.sourceRefs],
      })),
      omitted: plan.omitted,
      sourceStatuses: plan.sourceStatuses.map(status => ({ ...status })),
      ...(plan.fieldAdvisory ? { fieldAdvisory: plan.fieldAdvisory } : {}),
    }
  }

  pin(turnId: number, text: string): string {
    const normalized = normalizeText(text, this.config.maxUnitChars)
    if (!normalized) throw new Error('pin text is required')
    const sourceId = `pin:${digest(normalized).slice(0, 20)}`
    const id = this.observe({ type: 'pin', turnId, sourceId, text: normalized })
    if (!id) throw new Error('failed to create pin')
    return id
  }

  unpin(unitId: string): boolean {
    const unit = this.units.get(unitId)
    if (!unit || !unit.pinned) return false
    unit.pinned = false
    unit.state = 'resolved'
    this.revision += 1
    return true
  }

  /**
   * Text-free compaction hints. The compaction hook's `context` strings bypass
   * OMP's normal per-message secret obfuscator, so raw unit text must never be
   * duplicated here. Canonical messages already carry the content into the
   * compaction request through OMP's protected provider boundary.
   */
  compactContext(): string[] {
    const active = Array.from(this.units.values())
      .filter(unit => unit.state === 'active')
      .sort((a, b) => compareRanked(rankUnit(a, this.query, undefined), rankUnit(b, this.query, undefined)))
      .slice(0, 10)
    if (active.length === 0) return []
    return [
      'Cassi attention checkpoint: agent-produced index only; current user instructions win and historical approval is not confirmation.',
      ...active.map(unit => {
        const pin = unit.pinned ? ' pinned' : ''
        return `- [${unit.kind}/${unit.authority}${pin}] ${unit.id}; confirmedTurn=${unit.lastConfirmedTurn}`
      }),
    ]
  }

  status(): AttentionStatus {
    const values = Array.from(this.units.values())
    const result: AttentionStatus = {
      sessionId: this.sessionId,
      revision: this.revision,
      turnId: this.turnId,
      units: values.length,
      active: values.filter(unit => unit.state === 'active').length,
      resolved: values.filter(unit => unit.state !== 'active').length,
      pinned: values.filter(unit => unit.pinned && unit.state === 'active').length,
    }
    if (this.latestPlanId) result.latestPlanId = this.latestPlanId
    return result
  }

  reset(): void {
    this.units.clear()
    this.turnId = null
    this.query = ''
    this.observationSequence = 0
    this.latestPlanId = undefined
    this.revision += 1
  }

  private resolveBudget(frame: ContextFrame): number {
    const requested = nonNegativeInteger(frame.maxPacketTokens, this.config.maxPacketTokens)
    if (
      typeof frame.contextTokens !== 'number' ||
      typeof frame.contextWindow !== 'number' ||
      !Number.isFinite(frame.contextTokens) ||
      !Number.isFinite(frame.contextWindow) ||
      frame.contextWindow <= 0
    ) return requested

    const available = Math.floor(frame.contextWindow - frame.contextTokens - this.config.minHeadroomTokens)
    return Math.max(0, Math.min(requested, available))
  }

  private candidateUnits(
    candidates: readonly ContextCandidate[],
    turnId: number,
    knownText: Set<string>,
  ): AttentionUnit[] {
    const out: AttentionUnit[] = []
    const seenIds = new Set<string>()
    for (const candidate of candidates) {
      if (
        !candidate
        || candidate.eligible === false
        || typeof candidate.id !== 'string'
        || !candidate.id
        || seenIds.has(candidate.id)
      ) continue
      const observation = validObservationReference(candidate.observation)
      if (candidate.observation && !observation) continue
      const text = normalizeText(candidate.text, this.config.maxUnitChars)
      if (!text && !observation) continue
      const textHash = digest(text.toLowerCase() || observation!.viewSha256)
      const workingKind = candidate.source === 'field' ? candidate.workingKind : undefined
      if (knownText.has(textHash)) continue
      const workBudget = candidate.workBudget
      if (
        workBudget !== undefined
        && (!Number.isInteger(workBudget) || workBudget < ITEM_OVERHEAD_TOKENS)
      ) continue
      knownText.add(textHash)
      seenIds.add(candidate.id)
      const kind = candidate.kind ?? workingKind ?? 'memory'
      const authority = candidate.authority
        ?? (workingKind === 'goal' ? 'direct_user' : workingKind ? 'tool' : 'memory')
      out.push({
        id: contextCandidateUnitId(candidate),
        kind,
        state: 'active',
        authority,
        text,
        sourceRefs: observation
          ? [
              `record:${observation.recordId}@${observation.revision}`,
              `packet:${observation.packetSha256}`,
              `packet-object:${observation.packetObjectSha256}`,
              `payload-manifest:${observation.payloadManifestSha256}`,
              `journal:${observation.journalHeadSha256}`,
              `view:${observation.viewSha256}`,
            ]
          : (candidate.sourceRefs?.length ? candidate.sourceRefs : [candidate.id])
              .map(ref => sourceRef(ref, candidate.source)),
        createdTurn: turnId,
        lastConfirmedTurn: turnId,
        sequence: this.observationSequence,
        pinned: false,
        required: candidate.required === true,
        ...(workBudget === undefined ? {} : { workBudget }),
        toolName: Number.isFinite(candidate.score) ? `score:${candidate.score}` : undefined,
      })
    }
    return out
  }

  private trimOldGoals(): void {
    const goals = Array.from(this.units.values())
      .filter(unit => unit.kind === 'goal' && unit.authority === 'direct_user' && unit.state === 'active' && !unit.pinned)
      .sort(compareNewest)
    for (const unit of goals.slice(this.config.recentGoalLimit)) {
      unit.state = 'resolved'
      this.revision += 1
    }
  }

  /** Deterministic hard cap: stale/incidental units go before live safety state. */
  private enforceUnitCap(): void {
    while (this.units.size > this.config.maxUnits) {
      const latestGoalId = Array.from(this.units.values())
        .filter(unit => unit.kind === 'goal' && unit.authority === 'direct_user' && unit.state === 'active')
        .sort(compareNewest)[0]?.id
      const victim = Array.from(this.units.values()).sort((a, b) =>
        retentionPriority(a, latestGoalId) - retentionPriority(b, latestGoalId)
        || a.lastConfirmedTurn - b.lastConfirmedTurn
        || a.createdTurn - b.createdTurn
        || a.id.localeCompare(b.id)
      )[0]
      if (!victim) return
      this.units.delete(victim.id)
    }
  }
}

function observationDescriptor(observation: AttentionObservation): {
  kind: AttentionKind
  authority: AttentionAuthority
  pinned: boolean
} {
  switch (observation.type) {
    case 'user': return { kind: 'goal', authority: 'direct_user', pinned: false }
    case 'assistant': return { kind: 'decision', authority: 'agent', pinned: false }
    case 'tool_result': return { kind: observation.isError ? 'failure' : 'evidence', authority: 'tool', pinned: false }
    case 'compaction': return { kind: 'decision', authority: 'agent', pinned: false }
    case 'pin': return { kind: 'constraint', authority: 'direct_user', pinned: true }
    default: return { kind: 'open_loop', authority: 'agent', pinned: false }
  }
}

function rankUnit(unit: AttentionUnit, query: string, latestGoalId: string | undefined): RankedUnit {
  const required = unit.required || unit.pinned || unit.id === latestGoalId
  const candidateScore = unit.toolName?.startsWith('score:') ? Number(unit.toolName.slice(6)) : 0
  return {
    ...unit,
    required,
    relevance: lexicalRelevance(query, unit.text),
    sourceScore: Number.isFinite(candidateScore) ? candidateScore : 0,
    reason: unit.pinned
      ? 'explicit-user-pin'
      : unit.id === latestGoalId
        ? 'current-user-goal'
        : unit.kind === 'failure'
          ? 'unresolved-failure'
          : unit.kind === 'memory'
            ? 'relevant-memory'
            : `active-${unit.kind}`,
  }
}

function compareRanked(a: RankedUnit, b: RankedUnit): number {
  return Number(b.required) - Number(a.required)
    || KIND_PRIORITY[b.kind] - KIND_PRIORITY[a.kind]
    || AUTHORITY_PRIORITY[b.authority] - AUTHORITY_PRIORITY[a.authority]
    || b.sourceScore - a.sourceScore
    || b.relevance - a.relevance
    || b.sequence - a.sequence
    || a.id.localeCompare(b.id)
}

function compareNewest(a: AttentionUnit, b: AttentionUnit): number {
  return b.sequence - a.sequence
    || a.id.localeCompare(b.id)
}

function validObservationReference(
  value: ExactObservationReference | undefined,
): ExactObservationReference | null {
  if (!value) return null
  const digestFields = [
    value.revision,
    value.packetSha256,
    value.packetObjectSha256,
    value.payloadManifestSha256,
    value.journalHeadSha256,
    value.viewSha256,
  ]
  if (
    !value.recordId
    || digestFields.some(item => !/^[0-9a-f]{64}$/.test(item))
    || !/^[A-Za-z0-9._:+-]{1,128}$/.test(value.codecId)
    || !value.sourceStreamId
    || !Number.isInteger(value.sourceSequence)
    || value.sourceSequence < 0
  ) return null
  if (
    value.sourcePath
    && (
      value.sourcePath.length > 64
      || value.sourcePath.some(segment => (
        typeof segment === 'number'
          ? !Number.isInteger(segment) || segment < 0
          : typeof segment !== 'string' || Buffer.byteLength(segment) > 256
      ))
    )
  ) return null
  if (
    value.sourceSpan
    && (
      value.sourceSpan.length !== 2
      || !Number.isInteger(value.sourceSpan[0])
      || !Number.isInteger(value.sourceSpan[1])
      || value.sourceSpan[0] < 0
      || value.sourceSpan[1] < value.sourceSpan[0]
    )
  ) return null
  return value
}

function normalizeSourceStatuses(statuses: ContextSourceStatus[] | undefined): ContextSourceStatus[] {
  const normalized = (statuses ?? []).map(status => ({
    source: status.source,
    status: status.status,
    ...(typeof status.latencyMs === 'number' && Number.isFinite(status.latencyMs)
      ? { latencyMs: Math.max(0, Math.round(status.latencyMs)) }
      : {}),
    ...(status.error ? { error: `${status.source}-${status.status}` } : {}),
  }))
  if (!normalized.some(status => status.source === 'local')) {
    normalized.unshift({ source: 'local', status: 'ready' })
  }
  return normalized
}

function lexicalRelevance(query: string, text: string): number {
  const queryTerms = terms(query)
  if (queryTerms.size === 0) return 0
  const textTerms = terms(text)
  if (textTerms.size === 0) return 0
  let overlap = 0
  for (const term of queryTerms) if (textTerms.has(term)) overlap += 1
  return overlap / Math.sqrt(queryTerms.size * textTerms.size)
}

function terms(text: string): Set<string> {
  return new Set((text.toLowerCase().match(/[a-z0-9_]{2,}/g) ?? []).slice(0, 256))
}

function normalizeText(text: string, maxChars: number): string {
  const normalized = text
    .replace(/[\u0000-\u0008\u000b\u000c\u000e-\u001f\u007f]/g, '')
    .replace(/\s+/g, ' ')
    .trim()
  return truncateText(normalized, maxChars)
}

function truncateText(text: string, maxChars: number): string {
  if (text.length <= maxChars) return text
  if (maxChars <= 1) return text.slice(0, Math.max(0, maxChars))
  return `${text.slice(0, maxChars - 1).trimEnd()}…`
}

function truncateTextBytes(text: string, maxBytes: number): string {
  if (Buffer.byteLength(text) <= maxBytes) return text
  const suffix = '…'
  const suffixBytes = Buffer.byteLength(suffix)
  const contentBytes = Math.max(0, maxBytes - suffixBytes)
  const prefix = new TextDecoder()
    .decode(Buffer.from(text).subarray(0, contentBytes))
    .replace(/\uFFFD$/u, '')
    .trimEnd()
  return maxBytes >= suffixBytes ? `${prefix}${suffix}` : prefix
}


function estimateTokens(text: string): number {
  return ITEM_OVERHEAD_TOKENS + Buffer.byteLength(text)
}

function digest(text: string): string {
  return createHash('sha256').update(text).digest('hex')
}

function sourceRef(value: string, namespace = 'source'): string {
  return `ref:${digest(`${namespace}\u0000${value}`).slice(0, 24)}`
}

function retentionPriority(unit: AttentionUnit, latestGoalId: string | undefined): number {
  if (unit.id === latestGoalId) return 5
  if (unit.pinned) return 4
  if (unit.state === 'active' && unit.kind === 'failure') return 3
  if (unit.state === 'active') return 2
  return 1
}

function stableStringify(value: unknown): string {
  if (Array.isArray(value)) return `[${value.map(stableStringify).join(',')}]`
  if (value && typeof value === 'object') {
    const record = value as Record<string, unknown>
    return `{${Object.keys(record).sort().map(key => `${JSON.stringify(key)}:${stableStringify(record[key])}`).join(',')}}`
  }
  return JSON.stringify(value)
}

function positiveInteger(value: number | undefined, fallback: number): number {
  return typeof value === 'number' && Number.isInteger(value) && value > 0 ? value : fallback
}

function nonNegativeInteger(value: number | undefined, fallback: number): number {
  return typeof value === 'number' && Number.isInteger(value) && value >= 0 ? value : fallback
}
