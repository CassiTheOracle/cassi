/**
 * Cross-Module Coherence Checker (N6) — verifies consistency between
 * cognitive modules (Aurora, Mnemic Field, Cortex, Affect Register).
 *
 * Each module holds its own representation of state. Over time, these
 * representations can drift: a memory stored in the Mnemic Field may not
 * match the embedding the Cortex uses, or the Affect Register's valence
 * may lag behind the signals in the Cortex.
 *
 * The coherence checker detects four categories of divergence:
 *   - EMBEDDING_MISMATCH: embedding vectors disagree between modules
 *   - TAG_DIVERGENCE: tags/labels assigned to the same content differ
 *   - SIGNAL_MISSING: a module is missing expected signals/state
 *   - TEMPORAL_DRIFT: timestamps indicate stale or out-of-sync state
 *
 * Bounded auto-correction is applied for known latency patterns (e.g.,
 * Cortex signals arriving before Mnemic Field has finished persisting).
 * Genuine divergences are surfaced as diagnostic signals for review.
 *
 * See: docs/design/aurora-cross-module-coherence.md
 */

import type { ILogger } from '../../../types/interfaces.js'
import type { CognitiveNode } from './types.js'
import { COHERENCE_MISMATCH_PHRASES } from '../phrase-prototypes.js'
import type { MnemicField } from '../mnemic-field/index.js'


export type CoherenceCategory =
  | 'EMBEDDING_MISMATCH'
  | 'TAG_DIVERGENCE'
  | 'SIGNAL_MISSING'
  | 'TEMPORAL_DRIFT'

export type CoherenceSeverity = 'info' | 'warn' | 'critical'


export interface CoherenceSignal {
  readonly id: string
  readonly detectedAt: string
  readonly category: CoherenceCategory
  readonly severity: CoherenceSeverity
  readonly description: string
  readonly modules: readonly string[]
  readonly details: Readonly<Record<string, unknown>>
  /** Whether the checker auto-corrected this signal. */
  readonly autoCorrected: boolean
}


export interface AuroraSnapshot {
  readonly nodes: ReadonlyArray<CognitiveNode>
  readonly nodeCount: number
  readonly edgeCount: number
  readonly focusStack: readonly string[]
  readonly momentum: number
  readonly lastUpdateTime: string
}

export interface MnemicFieldSnapshot {
  readonly engrams: ReadonlyArray<{
    readonly id: string
    readonly content: string
    readonly tags: readonly string[]
    readonly createdAt: string
    readonly potentiation: number
    readonly embeddingHash?: string
  }>
  readonly totalEngams: number
  readonly lastUpdateTime: string
}

export interface CortexSnapshot {
  readonly signals: ReadonlyArray<{
    readonly id: string
    readonly type: string
    readonly content: string
    readonly region: string
    readonly createdAt: string
    readonly tags?: readonly string[]
  }>
  readonly totalSignals: number
  readonly lastUpdateTime: string
}

export interface AffectSnapshot {
  readonly currentValence: number
  readonly currentArousal: number
  readonly labels: readonly string[]
  readonly lastUpdateTime: string
  readonly history: ReadonlyArray<{
    readonly valence: number
    readonly arousal: number
    readonly recordedAt: string
  }>
}

export interface CoherenceCheckInput {
  aurora?: AuroraSnapshot
  mnemicField?: MnemicFieldSnapshot
  cortex?: CortexSnapshot
  affect?: AffectSnapshot
}


export interface CoherenceCheckResult {
  readonly checkedAt: string
  readonly modulesChecked: readonly string[]
  readonly signals: readonly CoherenceSignal[]
  readonly autoCorrectedCount: number
  readonly byCategory: Readonly<Record<string, number>>
  readonly bySeverity: Readonly<Record<string, number>>
}


/**
 * N6.2 — corrector callback. Invoked when a known latency pattern is
 * detected and auto-correction is enabled. The corrector is responsible
 * for the actual sync action (e.g., trigger claustrum re-merge,
 * publish a Cortex signal). Synchronous return — async work should be
 * fire-and-forget or queued.
 *
 * Errors thrown by the corrector are caught and logged; they don't
 * block the auto-correction flag from landing on the signal.
 */
export type CoherenceCorrector = (signal: CoherenceSignal) => void

export interface CoherenceCorrectors {
  /** Invoked when Mnemic→Cortex latency auto-correction fires. */
  mnemicCortexLatency?: CoherenceCorrector
  /** Invoked when Aurora↔Cortex latency auto-correction fires. */
  auroraCortexLatency?: CoherenceCorrector
}

export interface CoherenceConfig {
  /** Max staleness in seconds before flagging TEMPORAL_DRIFT. Default: 300 (5 min). */
  temporalDriftThresholdSec: number
  /** Max embedding hash mismatch ratio before flagging EMBEDDING_MISMATCH. Default: 0.3. */
  embeddingMismatchRatio: number
  /** Max tag divergence ratio before flagging TAG_DIVERGENCE. Default: 0.5. */
  tagDivergenceRatio: number
  /** Max signals to process in a single check. Default: 500. */
  maxSignalsPerCheck: number
  /** Whether to auto-correct known latency patterns. Default: true. */
  autoCorrectLatencyPatterns: boolean
  /** N6.2 — optional sync triggers invoked by auto-correction. */
  correctors?: CoherenceCorrectors
}

const COHERENCE_DEFAULTS: CoherenceConfig = {
  temporalDriftThresholdSec: 300,
  embeddingMismatchRatio: 0.3,
  tagDivergenceRatio: 0.5,
  maxSignalsPerCheck: 500,
  autoCorrectLatencyPatterns: true,
}


let signalSeq = 0

function makeSignalId(): string {
  signalSeq++
  return `coh-${Date.now()}-${signalSeq}`
}

function isoNow(): string {
  return new Date().toISOString()
}

function timeDiffSec(a: string, b: string): number {
  return Math.abs(new Date(a).getTime() - new Date(b).getTime()) / 1000
}

function tagOverlap(tagsA: readonly string[], tagsB: readonly string[]): number {
  if (tagsA.length === 0 && tagsB.length === 0) return 1
  if (tagsA.length === 0 || tagsB.length === 0) return 0
  const setA = new Set(tagsA)
  const shared = tagsB.filter(t => setA.has(t)).length
  return shared / Math.max(setA.size, tagsB.length)
}

function normalizeContentKey(content: string | null | undefined): string {
  if (!content) return ''
  return content.toLowerCase().trim().replace(/\s+/g, ' ')
}


/**
 * CoherenceChecker — detects and reports divergence between cognitive modules.
 *
 * Usage:
 *   const checker = new CoherenceChecker(logger)
 *   const result = checker.checkCoherence({ aurora, mnemicField, cortex, affect })
 *   for (const sig of result.signals) { ... }
 */
export class CoherenceChecker {
  private readonly logger: ILogger
  private readonly config: CoherenceConfig
  private readonly history: CoherenceSignal[] = []
  private readonly maxHistory = 100
  private mnemicField?: MnemicField

  constructor(logger: ILogger, config?: Partial<CoherenceConfig>) {
    this.logger = logger.child ? logger.child('coherence-checker') : logger
    this.config = { ...COHERENCE_DEFAULTS, ...config }
  }

  setMnemicField(field: MnemicField): void {
    this.mnemicField = field
  }

  async classifyMismatch(signal: CoherenceSignal): Promise<void> {
    if (!this.mnemicField || !signal.description) return
    const result = await this.mnemicField.classifyPhrase(signal.description, COHERENCE_MISMATCH_PHRASES).catch(() => null)
    if (result?.label && result.score > 0.35) {
      ;(signal.details as Record<string, unknown>).mismatchType = result.label
      ;(signal.details as Record<string, unknown>).mismatchScore = result.score
    }
  }


  checkCoherence(input: CoherenceCheckInput): CoherenceCheckResult {
    const checkedAt = isoNow()
    const signals: CoherenceSignal[] = []
    const modulesChecked: string[] = []

    if (input.aurora) {
      modulesChecked.push('aurora')
      if (input.mnemicField) {
        modulesChecked.push('mnemic-field')
        this.checkAuroraMnemicCoherence(input.aurora, input.mnemicField, signals)
      }
      if (input.cortex) {
        modulesChecked.push('cortex')
        this.checkAuroraCortexCoherence(input.aurora, input.cortex, signals)
      }
    }

    if (input.mnemicField && input.cortex) {
      if (!modulesChecked.includes('mnemic-field')) modulesChecked.push('mnemic-field')
      if (!modulesChecked.includes('cortex')) modulesChecked.push('cortex')
      this.checkMnemicCortexCoherence(input.mnemicField, input.cortex, signals)
    }

    if (input.affect && input.cortex) {
      if (!modulesChecked.includes('affect')) modulesChecked.push('affect')
      if (!modulesChecked.includes('cortex')) modulesChecked.push('cortex')
      this.checkAffectCortexCoherence(input.affect, input.cortex, signals)
    }

    if (input.affect && input.aurora) {
      if (!modulesChecked.includes('affect')) modulesChecked.push('affect')
      if (!modulesChecked.includes('aurora')) modulesChecked.push('aurora')
      this.checkAuroraAffectCoherence(input.aurora, input.affect, signals)
    }

    // Apply bounded auto-correction for latency patterns
    let autoCorrectedCount = 0
    if (this.config.autoCorrectLatencyPatterns) {
      autoCorrectedCount = this.autoCorrectLatencySignals(signals)
    }

    // Cap signals per check
    const capped = signals.slice(0, this.config.maxSignalsPerCheck)

    // Compute summary
    const byCategory: Record<string, number> = {}
    const bySeverity: Record<string, number> = {}
    for (const sig of capped) {
      byCategory[sig.category] = (byCategory[sig.category] ?? 0) + 1
      bySeverity[sig.severity] = (bySeverity[sig.severity] ?? 0) + 1
    }

    // Update history
    for (const sig of capped) {
      this.history.push(sig)
    }
    while (this.history.length > this.maxHistory) {
      this.history.shift()
    }

    if (capped.length > 0) {
      this.logger.info('Coherence check found signals', {
        total: capped.length,
        autoCorrected: autoCorrectedCount,
        byCategory,
        bySeverity,
      })
    }

    return {
      checkedAt,
      modulesChecked,
      signals: capped,
      autoCorrectedCount,
      byCategory,
      bySeverity,
    }
  }


  private checkAuroraMnemicCoherence(
    aurora: AuroraSnapshot,
    mnemic: MnemicFieldSnapshot,
    signals: CoherenceSignal[],
  ): void {
    // Lookup engrams by normalized content (lower, trim, collapse whitespace).
    // Without whitespace collapse, "foo bar" and "foo  bar" would not match
    // even though their semantic content is identical.
    const mnemicByContent = new Map<string, typeof mnemic.engrams[number]>()
    for (const eng of mnemic.engrams) {
      const key = normalizeContentKey(eng.content)
      if (key) mnemicByContent.set(key, eng)
    }

    let tagDivergences = 0

    for (const node of aurora.nodes) {
      if (node.source === 'memory' || node.source === 'both') {
        const key = normalizeContentKey(node.content ?? node.label)
        const engram = mnemicByContent.get(key)

        if (engram) {
          // Check temporal drift
          if (node.content && engram.createdAt) {
            const driftSec = timeDiffSec(aurora.lastUpdateTime, engram.createdAt)
            if (driftSec > this.config.temporalDriftThresholdSec) {
              signals.push({
                id: makeSignalId(),
                detectedAt: isoNow(),
                category: 'TEMPORAL_DRIFT',
                severity: driftSec > this.config.temporalDriftThresholdSec * 4 ? 'critical' : 'warn',
                description: `Aurora node '${node.label}' timestamp drifts ${Math.round(driftSec)}s from Mnemic Field engram`,
                modules: ['aurora', 'mnemic-field'],
                details: {
                  nodeId: node.id,
                  nodeLabel: node.label,
                  engramId: engram.id,
                  driftSec: Math.round(driftSec),
                  auroraUpdate: aurora.lastUpdateTime,
                  engramCreated: engram.createdAt,
                },
                autoCorrected: false,
              })
            }
          }

          // Check tag divergence
          const nodeTags = this.extractNodeTags(node)
          if (nodeTags.length > 0 && engram.tags.length > 0) {
            const overlap = tagOverlap(nodeTags, engram.tags)
            if (overlap < this.config.tagDivergenceRatio) {
              tagDivergences++
              signals.push({
                id: makeSignalId(),
                detectedAt: isoNow(),
                category: 'TAG_DIVERGENCE',
                severity: 'info',
                description: `Node '${node.label}' tags diverge from engram ${engram.id}`,
                modules: ['aurora', 'mnemic-field'],
                details: {
                  nodeId: node.id,
                  engramId: engram.id,
                  nodeTags,
                  engramTags: engram.tags,
                  overlapRatio: Math.round(overlap * 100) / 100,
                },
                autoCorrected: false,
              })
            }
          }
        } else {
          // Memory-sourced node with no matching engram
          signals.push({
            id: makeSignalId(),
            detectedAt: isoNow(),
            category: 'SIGNAL_MISSING',
            severity: 'warn',
            description: `Memory-sourced node '${node.label}' has no corresponding Mnemic Field engram`,
            modules: ['aurora', 'mnemic-field'],
            details: {
              nodeId: node.id,
              nodeLabel: node.label,
              nodeSource: node.source,
            },
            autoCorrected: false,
          })
        }
      }
    }

    // EMBEDDING_MISMATCH detection requires per-node embedding hashes on
    // AuroraSnapshot — currently unavailable, so the check is omitted rather
    // than emit a misleading always-zero signal.

    if (tagDivergences > 3) {
      signals.push({
        id: makeSignalId(),
        detectedAt: isoNow(),
        category: 'TAG_DIVERGENCE',
        severity: 'warn',
        description: `${tagDivergences} tag divergences between Aurora and Mnemic Field suggest systematic drift`,
        modules: ['aurora', 'mnemic-field'],
        details: { tagDivergences },
        autoCorrected: false,
      })
    }
  }


  private checkAuroraCortexCoherence(
    aurora: AuroraSnapshot,
    cortex: CortexSnapshot,
    signals: CoherenceSignal[],
  ): void {
    // Check that activated Aurora nodes have corresponding Cortex signals
    const activatedNodes = aurora.nodes.filter(n => n.activated)
    const cortexContentSet = new Set(
      cortex.signals.map(s => s.content.toLowerCase().trim()),
    )

    let missingSignals = 0
    for (const node of activatedNodes) {
      const label = node.label.toLowerCase().trim()
      const found = cortexContentSet.has(label)
      if (!found) {
        // Check partial match — cortex content may contain node label
        let partialFound = false
        for (const content of Array.from(cortexContentSet)) {
          if (content.includes(label) || label.includes(content)) {
            partialFound = true
            break
          }
        }
        if (!partialFound) {
          missingSignals++
        }
      }
    }

    if (missingSignals > 0 && activatedNodes.length > 0) {
      const ratio = missingSignals / activatedNodes.length
      const severity: CoherenceSeverity = ratio > 0.5 ? 'warn' : 'info'
      signals.push({
        id: makeSignalId(),
        detectedAt: isoNow(),
        category: 'SIGNAL_MISSING',
        severity,
        description: `${missingSignals}/${activatedNodes.length} activated Aurora nodes have no Cortex signal`,
        modules: ['aurora', 'cortex'],
        details: {
          activatedNodes: activatedNodes.length,
          missingSignals,
          ratio: Math.round(ratio * 100) / 100,
        },
        autoCorrected: false,
      })
    }

    // Check temporal coherence
    if (aurora.lastUpdateTime && cortex.lastUpdateTime) {
      const driftSec = timeDiffSec(aurora.lastUpdateTime, cortex.lastUpdateTime)
      if (driftSec > this.config.temporalDriftThresholdSec) {
        signals.push({
          id: makeSignalId(),
          detectedAt: isoNow(),
          category: 'TEMPORAL_DRIFT',
          severity: driftSec > this.config.temporalDriftThresholdSec * 4 ? 'critical' : 'warn',
          description: `Aurora and Cortex timestamps drift by ${Math.round(driftSec)}s`,
          modules: ['aurora', 'cortex'],
          details: {
            driftSec: Math.round(driftSec),
            auroraUpdate: aurora.lastUpdateTime,
            cortexUpdate: cortex.lastUpdateTime,
          },
          autoCorrected: false,
        })
      }
    }
  }


  private checkMnemicCortexCoherence(
    mnemic: MnemicFieldSnapshot,
    cortex: CortexSnapshot,
    signals: CoherenceSignal[],
  ): void {
    // Check that recent engrams have corresponding Cortex signals
    const now = Date.now()
    const recentThresholdMs = this.config.temporalDriftThresholdSec * 1000

    const recentEngrams = mnemic.engrams.filter(eng => {
      const engMs = new Date(eng.createdAt).getTime()
      return (now - engMs) < recentThresholdMs
    })

    const cortexContentSet = new Set(
      cortex.signals.map(s => s.content.toLowerCase().trim()),
    )

    let missingCount = 0
    for (const eng of recentEngrams) {
      const content = eng.content.toLowerCase().trim()
      let found = cortexContentSet.has(content)
      if (!found) {
        // Partial match
        for (const c of Array.from(cortexContentSet)) {
          if (c.includes(content.substring(0, 30)) || content.includes(c.substring(0, 30))) {
            found = true
            break
          }
        }
      }
      if (!found) missingCount++
    }

    if (missingCount > 0 && recentEngrams.length > 0) {
      signals.push({
        id: makeSignalId(),
        detectedAt: isoNow(),
        category: 'SIGNAL_MISSING',
        severity: 'info',
        description: `${missingCount} recent engrams have no Cortex signal (may be latency)`,
        modules: ['mnemic-field', 'cortex'],
        details: {
          recentEngrams: recentEngrams.length,
          missing: missingCount,
        },
        autoCorrected: false,
      })
    }

    // Check temporal drift
    if (mnemic.lastUpdateTime && cortex.lastUpdateTime) {
      const driftSec = timeDiffSec(mnemic.lastUpdateTime, cortex.lastUpdateTime)
      if (driftSec > this.config.temporalDriftThresholdSec * 2) {
        signals.push({
          id: makeSignalId(),
          detectedAt: isoNow(),
          category: 'TEMPORAL_DRIFT',
          severity: 'warn',
          description: `Mnemic Field and Cortex drift by ${Math.round(driftSec)}s`,
          modules: ['mnemic-field', 'cortex'],
          details: {
            driftSec: Math.round(driftSec),
            mnemicUpdate: mnemic.lastUpdateTime,
            cortexUpdate: cortex.lastUpdateTime,
          },
          autoCorrected: false,
        })
      }
    }
  }


  private checkAffectCortexCoherence(
    affect: AffectSnapshot,
    cortex: CortexSnapshot,
    signals: CoherenceSignal[],
  ): void {
    // Check that affect signals in the Cortex align with the Affect Register
    const affectSignals = cortex.signals.filter(s =>
      s.type === 'anomaly' || s.type === 'concern' || s.tags?.some(t => t.includes('affect')),
    )

    if (affectSignals.length > 0 && affect.labels.length === 0 && affect.currentArousal < 0.3) {
      signals.push({
        id: makeSignalId(),
        detectedAt: isoNow(),
        category: 'SIGNAL_MISSING',
        severity: 'info',
        description: 'Cortex has affect-tagged signals but Affect Register shows low arousal and no labels',
        modules: ['affect', 'cortex'],
        details: {
          affectSignalsInCortex: affectSignals.length,
          affectArousal: affect.currentArousal,
          affectLabels: affect.labels,
        },
        autoCorrected: false,
      })
    }

    // Temporal drift check
    if (affect.lastUpdateTime && cortex.lastUpdateTime) {
      const driftSec = timeDiffSec(affect.lastUpdateTime, cortex.lastUpdateTime)
      if (driftSec > this.config.temporalDriftThresholdSec * 2) {
        signals.push({
          id: makeSignalId(),
          detectedAt: isoNow(),
          category: 'TEMPORAL_DRIFT',
          severity: 'info',
          description: `Affect Register and Cortex drift by ${Math.round(driftSec)}s`,
          modules: ['affect', 'cortex'],
          details: {
            driftSec: Math.round(driftSec),
            affectUpdate: affect.lastUpdateTime,
            cortexUpdate: cortex.lastUpdateTime,
          },
          autoCorrected: false,
        })
      }
    }
  }


  private checkAuroraAffectCoherence(
    aurora: AuroraSnapshot,
    affect: AffectSnapshot,
    signals: CoherenceSignal[],
  ): void {
    // High momentum with low arousal may indicate a stuck reasoning loop
    if (aurora.momentum > 0.8 && affect.currentArousal < 0.2) {
      signals.push({
        id: makeSignalId(),
        detectedAt: isoNow(),
        category: 'SIGNAL_MISSING',
        severity: 'warn',
        description: 'High Aurora momentum with low affect arousal — possible stuck reasoning loop',
        modules: ['aurora', 'affect'],
        details: {
          momentum: aurora.momentum,
          arousal: affect.currentArousal,
          valence: affect.currentValence,
        },
        autoCorrected: false,
      })
    }

    // Strongly negative valence should appear in Aurora's focus stack
    if (affect.currentValence < -0.5 && aurora.focusStack.length === 0) {
      signals.push({
        id: makeSignalId(),
        detectedAt: isoNow(),
        category: 'SIGNAL_MISSING',
        severity: 'info',
        description: 'Strong negative valence but Aurora has empty focus stack — affect not reflected in reasoning',
        modules: ['aurora', 'affect'],
        details: {
          valence: affect.currentValence,
          arousal: affect.currentArousal,
          focusStackSize: aurora.focusStack.length,
        },
        autoCorrected: false,
      })
    }
  }


  private autoCorrectLatencySignals(signals: CoherenceSignal[]): number {
    let corrected = 0
    const correctors = this.config.correctors
    for (let i = 0; i < signals.length; i++) {
      const sig = signals[i]
      if (sig.autoCorrected) continue

      // Mnemic Field ↔ Cortex latency: engrams arriving before Cortex signals
      // is a known pattern — Cortex signals are ephemeral and may not have
      // arrived yet for recently stored engrams.
      if (
        sig.category === 'SIGNAL_MISSING' &&
        sig.modules.includes('mnemic-field') &&
        sig.modules.includes('cortex') &&
        sig.description.includes('recent engrams')
      ) {
        signals[i] = { ...sig, autoCorrected: true }
        corrected++
        this.logger.debug('Auto-corrected Mnemic-Cortex latency signal', { signalId: sig.id })
        this.invokeCorrector('mnemicCortexLatency', correctors?.mnemicCortexLatency, signals[i])
        continue
      }

      // Aurora ↔ Cortex latency: Cortex signals are ephemeral and may have
      // already decayed for older activated nodes.
      if (
        sig.category === 'SIGNAL_MISSING' &&
        sig.modules.includes('aurora') &&
        sig.modules.includes('cortex') &&
        sig.severity === 'info'
      ) {
        signals[i] = { ...sig, autoCorrected: true }
        corrected++
        this.logger.debug('Auto-corrected Aurora-Cortex latency signal', { signalId: sig.id })
        this.invokeCorrector('auroraCortexLatency', correctors?.auroraCortexLatency, signals[i])
      }
    }
    return corrected
  }

  /** Wrap corrector invocation in try/catch — corrector failures don't block flagging. */
  private invokeCorrector(
    name: string,
    fn: CoherenceCorrector | undefined,
    signal: CoherenceSignal,
  ): void {
    if (!fn) return
    try {
      fn(signal)
    } catch (err) {
      this.logger.warn('Coherence corrector threw', {
        corrector: name,
        signalId: signal.id,
        error: String(err),
      })
    }
  }


  private extractNodeTags(node: CognitiveNode): string[] {
    const tags: string[] = []
    if (node.source) tags.push(`source:${node.source}`)
    if (node.nodeType) tags.push(`type:${node.nodeType}`)
    if (node.modelLayers && node.modelLayers.length > 0) {
      tags.push(`layers:${node.modelLayers.join(',')}`)
    }
    return tags
  }


  getHistory(limit = 20): readonly CoherenceSignal[] {
    return this.history.slice(-limit)
  }

  getHistoryByCategory(category: CoherenceCategory, limit = 20): readonly CoherenceSignal[] {
    return this.history
      .filter(s => s.category === category)
      .slice(-limit)
  }

  getHistoryByModule(moduleName: string, limit = 20): readonly CoherenceSignal[] {
    return this.history
      .filter(s => s.modules.includes(moduleName))
      .slice(-limit)
  }

  clearHistory(): void {
    this.history.length = 0
  }
}
