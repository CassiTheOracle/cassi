/**
 * @cassicore/spine — FAKE ThalamusAttentionSession for context-controller contract tests.
 *
 * Structural mirror of the `@cassicore/thalamus/attention` contract (locked by Main):
 * `new ThalamusAttentionSession(sessionId, config?)` with observe / beginTurn / plan /
 * render / receipt / pin / unpin / compactContext / status / reset. The fake is
 * deterministic for the same frame/state (same observed units → same plan shape) and
 * records every call so tests can assert controller behavior. It intentionally uses
 * LOCAL structural types instead of importing the kernel module, so the test suite is
 * self-contained (the kernel subpath is still being landed by the core agent).
 *
 * Tests register this fake via `vi.mock('@cassicore/thalamus/attention', …)`.
 */

export type FakeThalamusMode = 'off' | 'observe' | 'inject'
export type FakeAttentionKind = 'goal' | 'constraint' | 'decision' | 'open_loop' | 'evidence' | 'artifact' | 'failure' | 'memory'
export type FakeAttentionAuthority = 'direct_user' | 'agent' | 'tool' | 'memory' | 'external_data'

export interface FakeAttentionObservation {
  type: 'user' | 'assistant' | 'tool_result' | 'compaction' | 'pin' | 'unpin' | 'invalidate'
  turnId: number
  sourceId: string
  text?: string
  timestamp?: number
  toolName?: string
  toolCallId?: string
  isError?: boolean
  unitId?: string
}

export interface FakeContextCandidate {
  id: string
  source: 'mnemic' | 'aurora' | 'pineal'
  text: string
  score: number
  sourceRefs?: string[]
  metadata?: Record<string, unknown>
}

export interface FakeContextSourceStatus {
  source: 'local' | 'mnemic' | 'aurora' | 'pineal' | 'field'
  status: 'ready' | 'timeout' | 'offline' | 'error' | 'disabled'
  latencyMs?: number
  error?: string
}

export interface FakeFieldAdvisory {
  mode: 'shadow'
  observedAt: number
  step: number | null
  time: number | null
  [k: string]: unknown
}

export interface FakeContextFrame {
  turnId: number
  query: string
  modelId?: string
  contextTokens?: number
  contextWindow?: number
  maxPacketTokens?: number
  sourceStatuses?: FakeContextSourceStatus[]
  fieldAdvisory?: FakeFieldAdvisory
}

export interface FakePlannedAttentionItem {
  unitId: string
  kind: FakeAttentionKind
  authority: FakeAttentionAuthority
  text: string
  reason: string
  estimatedTokens: number
  sourceRefs: readonly string[]
}

export interface FakeContextPlan {
  schemaVersion: 1
  id: string
  sessionId: string
  turnId: number
  ledgerRevision: number
  budgetTokens: number
  estimatedTokens: number
  items: readonly FakePlannedAttentionItem[]
  omitted: number
  sourceStatuses: readonly FakeContextSourceStatus[]
  fieldAdvisory?: FakeFieldAdvisory
}

export interface FakeContextPlanReceipt {
  schemaVersion: 1
  planId: string
  sessionId: string
  turnId: number
  ledgerRevision: number
  packetHash: string
  included: readonly { unitId: string; reason: string; estimatedTokens: number; sourceRefs: readonly string[] }[]
  omitted: number
  sourceStatuses: readonly FakeContextSourceStatus[]
  fieldAdvisory?: FakeFieldAdvisory
}

export interface FakeAttentionStatus {
  sessionId: string
  revision: number
  turnId: number | null
  units: number
  active: number
  resolved: number
  pinned: number
  latestPlanId?: string
}

export interface FakeThalamusAttentionConfig {
  maxPacketTokens?: number
  minHeadroomTokens?: number
  recentGoalLimit?: number
  maxUnitChars?: number
}

/** Module-level shared state so tests can inject failures and inspect instances. */
export const fakeState: {
  instances: FakeThalamusAttentionSession[]
  planError: Error | null
  renderError: Error | null
  planAuthority: FakeAttentionAuthority | null
} = {
  instances: [],
  planError: null,
  planAuthority: null,
  renderError: null,
}

export function fakeAttentionReset(): void {
  fakeState.instances = []
  fakeState.planError = null
  fakeState.renderError = null
  fakeState.planAuthority = null
}
export function contextCandidateUnitId(candidate: Pick<FakeContextCandidate, 'source' | 'id'>): string {
  return `candidate:${candidate.source}:${candidate.id}`
}


export class FakeThalamusAttentionSession {
  readonly sessionId: string
  readonly config: FakeThalamusAttentionConfig | undefined
  readonly calls: {
    observe: FakeAttentionObservation[]
    beginTurn: Array<{ turnId: number; query: string }>
    plan: Array<{ frame: FakeContextFrame; candidates: FakeContextCandidate[] | undefined }>
    render: string[]
    receipt: string[]
    pin: Array<{ turnId: number; text: string }>
    unpin: string[]
    compact: number
    reset: number
  } = {
    observe: [],
    beginTurn: [],
    plan: [],
    render: [],
    receipt: [],
    pin: [],
    unpin: [],
    compact: 0,
    reset: 0,
  }

  private units: Array<{ unitId: string; text: string }> = []
  private pinned: Array<{ unitId: string; text: string }> = []
  private counter = 0
  private revision = 1
  private currentTurnId: number | null = null
  private lastPlanId: string | undefined

  constructor(sessionId: string, config?: FakeThalamusAttentionConfig) {
    this.sessionId = sessionId
    this.config = config
    fakeState.instances.push(this)
  }

  observe(observation: FakeAttentionObservation): string | null {
    this.calls.observe.push(observation)
    if (!observation.text) return null
    const unitId = `u-${++this.counter}`
    this.units.push({ unitId, text: observation.text })
    this.revision++
    return unitId
  }

  beginTurn(turnId: number, query: string): void {
    this.calls.beginTurn.push({ turnId, query })
    this.currentTurnId = turnId
  }

  plan(frame: FakeContextFrame, candidates?: FakeContextCandidate[]): FakeContextPlan {
    this.calls.plan.push({ frame, candidates })
    if (fakeState.planError) throw fakeState.planError
    const items: FakePlannedAttentionItem[] = this.units.slice(-3).map(u => ({
      unitId: u.unitId,
      kind: 'goal',
      authority: fakeState.planAuthority ?? 'direct_user',
      text: u.text,
      reason: 'recent user goal',
      estimatedTokens: 10,
      sourceRefs: [],
    }))
    if (candidates && candidates.length > 0) {
      const c = candidates[0]
      items.push({
        unitId: contextCandidateUnitId(c),
        kind: 'evidence',
        authority: fakeState.planAuthority ?? 'memory',
        text: c.text,
        reason: 'runtime candidate',
        estimatedTokens: 8,
        sourceRefs: [c.id],
      })
    }
    const planId = `plan-${this.sessionId}-${frame.turnId}-${this.calls.plan.length}`
    this.lastPlanId = planId
    return {
      schemaVersion: 1,
      id: planId,
      sessionId: this.sessionId,
      turnId: frame.turnId,
      ledgerRevision: this.revision,
      budgetTokens: frame.maxPacketTokens ?? 4000,
      estimatedTokens: items.reduce((n, i) => n + i.estimatedTokens, 0),
      items,
      omitted: Math.max(0, this.units.length - 3),
      sourceStatuses: frame.sourceStatuses ?? [],
      fieldAdvisory: frame.fieldAdvisory,
    }
  }

  render(plan: FakeContextPlan): string {
    this.calls.render.push(plan.id)
    if (fakeState.renderError) throw fakeState.renderError
    return `packet:${plan.id}`
  }

  receipt(plan: FakeContextPlan): FakeContextPlanReceipt {
    this.calls.receipt.push(plan.id)
    return {
      schemaVersion: 1,
      planId: plan.id,
      sessionId: this.sessionId,
      turnId: plan.turnId,
      ledgerRevision: plan.ledgerRevision,
      packetHash: `h-${plan.id}`,
      included: plan.items.map(i => ({ unitId: i.unitId, reason: i.reason, estimatedTokens: i.estimatedTokens, sourceRefs: i.sourceRefs })),
      omitted: plan.omitted,
      sourceStatuses: plan.sourceStatuses,
      fieldAdvisory: plan.fieldAdvisory,
    }
  }

  pin(turnId: number, text: string): string {
    this.calls.pin.push({ turnId, text })
    const unitId = `pin-${++this.counter}`
    this.pinned.push({ unitId, text })
    this.revision++
    return unitId
  }

  unpin(unitId: string): boolean {
    this.calls.unpin.push(unitId)
    const idx = this.pinned.findIndex(p => p.unitId === unitId)
    if (idx < 0) return false
    this.pinned.splice(idx, 1)
    this.revision++
    return true
  }

  compactContext(): string[] {
    this.calls.compact++
    return [`compact:${this.sessionId}`, ...this.pinned.map(p => `pinned:${p.unitId}`)]
  }

  status(): FakeAttentionStatus {
    return {
      sessionId: this.sessionId,
      revision: this.revision,
      turnId: this.currentTurnId,
      units: this.units.length,
      active: this.units.length,
      resolved: 0,
      pinned: this.pinned.length,
      latestPlanId: this.lastPlanId,
    }
  }

  reset(): void {
    this.calls.reset++
    this.units = []
    this.pinned = []
    this.revision = 1
    this.currentTurnId = null
    this.lastPlanId = undefined
  }
}
