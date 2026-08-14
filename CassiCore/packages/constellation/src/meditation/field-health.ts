/**
 * Field Health Analyzer — Metrics-driven organizing intelligence.
 *
 * Computes fragmentation scores, tracks region health over time,
 * captures before/after snapshots, and identifies which regions
 * need the most attention. This module drives the organizing
 * meditation mode's auto-triggering and progressive coverage.
 *
 * Health metrics:
 *   - fragmentationScore: 0-1 (0 = well-connected, 1 = totally fragmented)
 *   - connectionDensity:  synapses per engram
 *   - abstractionCoverage: fraction of clusters with summary engrams
 *   - potentiationSpread: variance in potentiation (high = uneven attention)
 *   - orphanRatio:        fraction of engrams not in any cluster
 *   - tensionLoad:        number of unresolved contradictions
 *
 * Progressive tracking:
 *   - Each organizing session records which regions (nuclei) it touched
 *   - Neglect score: how long since a region was last organized
 *   - The analyzer recommends which regions to prioritize next
 */

import type { MnemicField } from '../vendor/mnemic-field/index.js'
import type { MeditationStore } from './meditation-store.js'
import type { ILogger } from '../vendor/types/interfaces.js'


export interface FieldHealthSnapshot {
  timestamp: number
  engramCount: number
  synapseCount: number
  nucleusCount: number
  avgPotentiation: number
  connectionDensity: number
  abstractionCoverage: number
  potentiationSpread: number
  orphanRatio: number
  tensionCount: number
  fragmentationScore: number
  filamentCount: number
  regions: RegionHealth[]
}


export interface RegionHealth {
  nucleusId: string
  label: string
  memberCount: number
  avgPotentiation: number
  hasAbstraction: boolean
  /** Timestamp of last organizing session that touched this region */
  lastOrganizedAt: number | null
  /** Higher = more neglected, needs attention first */
  neglectScore: number
}


export interface OrganizingDelta {
  before: FieldHealthSnapshot
  after: FieldHealthSnapshot
  improvements: {
    fragmentationDelta: number
    connectionDensityDelta: number
    abstractionCoverageDelta: number
    tensionDelta: number
    newNuclei: number
    newSynapses: number
    newAbstractions: number
  }
  summary: string
}


export interface OrganizingSessionRecord {
  sessionId: string
  timestamp: number
  regionsOrganized: string[]
  /** Lightweight summary — full snapshots are NOT persisted to avoid bloat */
  before: { fragmentationScore: number; engramCount: number; synapseCount: number; nucleusCount: number; tensionCount: number }
  after: { fragmentationScore: number; engramCount: number; synapseCount: number; nucleusCount: number; tensionCount: number }
  deltaSummary: string
}

const FRAGMENTATION_THRESHOLD = 0.6

const ORGANIZING_HARD_FLOOR_MS = 15 * 60 * 1000
const WEAK_DELTA_THRESHOLD = 0.02
const WEAK_STREAK_STEP = 0.05
const MAX_BACKOFF_INCREMENT = 0.20

/**
 * Stop firing organizing entirely after this many consecutive weak sessions,
 * regardless of which trigger path (high fragmentation / growth / neglected
 * regions) wants to fire. The high-fragmentation path uses the threshold
 * raise above; the growth and neglected-regions paths bypass that, so this
 * floor catches them.
 *
 * Background: the daemon was firing through the neglected-regions path
 * every cooldown window (~30 min), each session doing zero useful work
 * (`regionsOrganized=0`, `bridgesCreated=0`, fragmentation unchanged), and
 * eating 85-300s of event-loop time per session — long enough to queue
 * unrelated HTTP requests behind it for tens of seconds.
 */
const NOOP_SUPPRESSION_FLOOR = 3

const META_KEY_LAST_HEALTH = 'organizing_last_health'
const META_KEY_REGION_HISTORY = 'organizing_region_history'
const META_KEY_SESSION_HISTORY = 'organizing_session_history'


export class FieldHealthAnalyzer {
  private mnemicField: MnemicField
  private store: MeditationStore | undefined
  private logger: ILogger


  constructor(mnemicField: MnemicField, logger: ILogger, store?: MeditationStore) {
    this.mnemicField = mnemicField
    this.store = store
    this.logger = logger.child ? logger.child('field-health') : logger
  }


  /**
   * Take a complete health snapshot of the mnemic field.
   * This is the foundation for both auto-triggering and before/after comparison.
   */
  snapshot(): FieldHealthSnapshot {
    const stats = this.mnemicField.stats()
    const nuclei = this.mnemicField.listNuclei()
    const abstractions = this.mnemicField.listAbstractions(200)
    const tensions = this.mnemicField.tensions(0.1, 100)

    const connectionDensity = stats.engramCount > 0
      ? stats.synapseCount / stats.engramCount
      : 0

    const abstractionIds = new Set(
      abstractions
        .map(a => a.clusterId)
        .filter((id): id is string => id !== null && id !== undefined)
    )
    const abstractionCoverage = nuclei.length > 0
      ? nuclei.filter(n => abstractionIds.has(n.id) || n.abstractionId !== null).length / nuclei.length
      : 1.0

    const potentiationSpread = this.computePotentiationSpread(nuclei)

    // Orphan ratio: engrams not assigned to any nucleus
    const clusteredCount = nuclei.reduce((sum, n) => sum + n.memberCount, 0)
    const orphanRatio = stats.engramCount > 0
      ? Math.max(0, (stats.engramCount - clusteredCount) / stats.engramCount)
      : 0

    const fragmentationScore = this.computeFragmentationScore({
      connectionDensity,
      abstractionCoverage,
      potentiationSpread,
      orphanRatio,
      tensionCount: tensions.length,
      engramCount: stats.engramCount,
      nucleusCount: stats.nucleusCount,
    })

    // Build region health with neglect scores
    const regionHistory = this.loadRegionHistory()
    const regions: RegionHealth[] = nuclei.map(n => {
      const lastOrganized = regionHistory[n.id] ?? null
      const neglectMs = lastOrganized ? Date.now() - lastOrganized : Infinity
      const neglectScore = lastOrganized
        ? Math.min(1.0, neglectMs / (7 * 24 * 60 * 60 * 1000))
        : 1.0

      return {
        nucleusId: n.id,
        label: n.label,
        memberCount: n.memberCount,
        avgPotentiation: n.avgPotentiation,
        hasAbstraction: n.abstractionId !== null || abstractionIds.has(n.id),
        lastOrganizedAt: lastOrganized,
        neglectScore,
      }
    })

    return {
      timestamp: Date.now(),
      engramCount: stats.engramCount,
      synapseCount: stats.synapseCount,
      nucleusCount: stats.nucleusCount,
      avgPotentiation: stats.avgPotentiation,
      connectionDensity,
      abstractionCoverage,
      potentiationSpread,
      orphanRatio,
      tensionCount: tensions.length,
      fragmentationScore,
      filamentCount: stats.filamentCount ?? 0,
      regions,
    }
  }


  /**
   * Compute the composite fragmentation score (0-1).
   *
   * Weighted combination of:
   *   - Connection density (low = fragmented)        weight: 0.30
   *   - Abstraction coverage (low = unorganized)     weight: 0.20
   *   - Orphan ratio (high = fragmented)             weight: 0.25
   *   - Potentiation spread (high = uneven)          weight: 0.15
   *   - Tension load (high = contradictory)          weight: 0.10
   */
  private computeFragmentationScore(metrics: {
    connectionDensity: number
    abstractionCoverage: number
    potentiationSpread: number
    orphanRatio: number
    tensionCount: number
    engramCount: number
    nucleusCount: number
  }): number {
    // Normalize connection density: < 0.5 = fully fragmented, > 3 = well-connected
    const densityScore = 1 - Math.min(1, metrics.connectionDensity / 3)

    // Abstraction coverage is already 0-1
    const abstractionScore = 1 - metrics.abstractionCoverage

    // Orphan ratio is already 0-1
    const orphanScore = metrics.orphanRatio

    // Potentiation spread: normalize against expected range
    const spreadScore = Math.min(1, metrics.potentiationSpread / 0.5)

    // Tension load: normalize by engram count
    const tensionScore = metrics.engramCount > 0
      ? Math.min(1, metrics.tensionCount / (metrics.engramCount * 0.1))
      : 0

    const score =
      densityScore * 0.30 +
      abstractionScore * 0.20 +
      orphanScore * 0.25 +
      spreadScore * 0.15 +
      tensionScore * 0.10

    return Math.max(0, Math.min(1, score))
  }


  /**
   * Compute potentiation variance across nuclei.
   * High variance means some clusters get lots of attention while others are dormant.
   */
  private computePotentiationSpread(nuclei: Array<{ avgPotentiation: number }>): number {
    if (nuclei.length < 2) return 0

    const values = nuclei.map(n => n.avgPotentiation)
    const mean = values.reduce((s, v) => s + v, 0) / values.length
    const variance = values.reduce((s, v) => s + (v - mean) ** 2, 0) / values.length
    return Math.sqrt(variance)
  }


  /**
   * Should organizing mode auto-trigger?
   *
   * Returns true when fragmentation exceeds threshold or when the field
   * has grown significantly since the last organizing session.
   */
  shouldOrganize(): { trigger: boolean; reason: string; score: number } {
    const current = this.snapshot()

    if (current.engramCount < 10) {
      return { trigger: false, reason: 'field too small', score: current.fragmentationScore }
    }

    const backoff = this.computeOrganizingBackoff()
    if (backoff.lastSessionAgeMs < ORGANIZING_HARD_FLOOR_MS) {
      const minutesAgo = Math.round(backoff.lastSessionAgeMs / 60_000)
      return {
        trigger: false,
        reason: `cooldown (last organized ${minutesAgo}m ago)`,
        score: current.fragmentationScore,
      }
    }

    if (backoff.weakStreak >= NOOP_SUPPRESSION_FLOOR) {
      return {
        trigger: false,
        reason: `suppressed: ${backoff.weakStreak} consecutive weak sessions (organizing isn't helping)`,
        score: current.fragmentationScore,
      }
    }

    if (current.fragmentationScore > backoff.threshold) {
      const noteSuffix = backoff.weakStreak > 0
        ? ` — threshold raised to ${backoff.threshold.toFixed(2)} after ${backoff.weakStreak} weak sessions`
        : ''
      return {
        trigger: true,
        reason: `high fragmentation (${current.fragmentationScore.toFixed(2)})${noteSuffix}`,
        score: current.fragmentationScore,
      }
    }

    // Check growth since last session
    const lastHealth = this.loadLastHealth()
    if (lastHealth) {
      const growth = current.engramCount - lastHealth.engramCount
      const growthRatio = lastHealth.engramCount > 0 ? growth / lastHealth.engramCount : 0
      if (growthRatio > 0.3) {
        return {
          trigger: true,
          reason: `significant growth (${growth} new engrams, ${(growthRatio * 100).toFixed(0)}% increase)`,
          score: current.fragmentationScore,
        }
      }
    }

    // Check if any regions have extreme neglect
    const severelyNeglected = current.regions.filter(r => r.neglectScore > 0.9)
    if (severelyNeglected.length > current.regions.length * 0.5) {
      return {
        trigger: true,
        reason: `${severelyNeglected.length} of ${current.regions.length} regions severely neglected`,
        score: current.fragmentationScore,
      }
    }

    if (backoff.weakStreak > 0 && current.fragmentationScore > FRAGMENTATION_THRESHOLD) {
      return {
        trigger: false,
        reason: `below threshold ${backoff.threshold.toFixed(2)} — threshold raised to ${backoff.threshold.toFixed(2)} after ${backoff.weakStreak} weak sessions`,
        score: current.fragmentationScore,
      }
    }

    return { trigger: false, reason: 'field healthy', score: current.fragmentationScore }
  }


  /**
   * Compute organizing-mode backoff state from recent session history.
   *
   * Three protections against runaway organizing:
   *   1. Hard floor — never re-fire within ORGANIZING_HARD_FLOOR_MS of the last
   *      session, regardless of fragmentation.
   *   2. Weak-streak threshold raise — when consecutive recent sessions failed
   *      to reduce fragmentation by at least WEAK_DELTA_THRESHOLD, raise the
   *      trigger threshold by WEAK_STREAK_STEP per weak session (capped).
   *      A successful session resets the streak.
   *   3. NOOP_SUPPRESSION_FLOOR — once the weak streak crosses this floor,
   *      `shouldOrganize()` suppresses **all** trigger paths (high-frag,
   *      growth, neglected-regions). Closes the gap where the
   *      neglected-regions path bypassed the threshold raise and kept firing
   *      every cooldown window with zero useful work done.
   *
   * **Weak session definition:** either fragmentation moved by less than
   * `WEAK_DELTA_THRESHOLD` *or* the session reported `regionsOrganized=0`.
   * The latter catches "explorer ran but found nothing to do" sessions
   * which can't possibly have moved fragmentation but were observable in
   * the live daemon log as repeated 85-300s no-ops.
   */
  private computeOrganizingBackoff(): {
    lastSessionAgeMs: number
    weakStreak: number
    threshold: number
  } {
    const sessions = this.getRecentSessions(50)
    if (sessions.length === 0) {
      return { lastSessionAgeMs: Infinity, weakStreak: 0, threshold: FRAGMENTATION_THRESHOLD }
    }

    const last = sessions[sessions.length - 1]
    const lastSessionAgeMs = Date.now() - last.timestamp

    let weakStreak = 0
    for (let i = sessions.length - 1; i >= 0; i--) {
      const s = sessions[i]
      const delta = s.before.fragmentationScore - s.after.fragmentationScore
      const touchedNothing = (s.regionsOrganized?.length ?? 0) === 0
      if (delta < WEAK_DELTA_THRESHOLD || touchedNothing) {
        weakStreak++
      } else {
        break
      }
    }

    const increment = Math.min(weakStreak * WEAK_STREAK_STEP, MAX_BACKOFF_INCREMENT)
    const threshold = FRAGMENTATION_THRESHOLD + increment

    return { lastSessionAgeMs, weakStreak, threshold }
  }


  /**
   * Get the regions that need the most attention, sorted by priority.
   *
   * Priority factors:
   *   1. Neglect score (how long since last organized)
   *   2. Missing abstraction (clusters without summaries)
   *   3. Low potentiation (dormant clusters)
   *   4. High member count (large clusters benefit more from organizing)
   */
  prioritizeRegions(limit = 5): RegionHealth[] {
    const snapshot = this.snapshot()

    const scored = snapshot.regions.map(r => ({
      ...r,
      priority:
        r.neglectScore * 0.40 +
        (r.hasAbstraction ? 0 : 1) * 0.25 +
        (1 - Math.min(1, r.avgPotentiation)) * 0.20 +
        Math.min(1, r.memberCount / 50) * 0.15,
    }))

    scored.sort((a, b) => b.priority - a.priority)
    return scored.slice(0, limit)
  }


  /**
   * Compare two snapshots and compute the delta.
   */
  computeDelta(before: FieldHealthSnapshot, after: FieldHealthSnapshot): OrganizingDelta {
    const improvements = {
      fragmentationDelta: before.fragmentationScore - after.fragmentationScore,
      connectionDensityDelta: after.connectionDensity - before.connectionDensity,
      abstractionCoverageDelta: after.abstractionCoverage - before.abstractionCoverage,
      tensionDelta: before.tensionCount - after.tensionCount,
      newNuclei: after.nucleusCount - before.nucleusCount,
      newSynapses: after.synapseCount - before.synapseCount,
      newAbstractions: Math.round(
        (after.abstractionCoverage - before.abstractionCoverage) * after.nucleusCount
      ),
    }

    const parts: string[] = []
    if (improvements.fragmentationDelta > 0.01) {
      parts.push(`fragmentation reduced by ${(improvements.fragmentationDelta * 100).toFixed(1)}%`)
    }
    if (improvements.connectionDensityDelta > 0.1) {
      parts.push(`connection density increased by ${improvements.connectionDensityDelta.toFixed(2)}`)
    }
    if (improvements.newSynapses > 0) {
      parts.push(`${improvements.newSynapses} new connections`)
    }
    if (improvements.newNuclei > 0) {
      parts.push(`${improvements.newNuclei} new clusters emerged`)
    }
    if (improvements.abstractionCoverageDelta > 0) {
      parts.push(`abstraction coverage improved by ${(improvements.abstractionCoverageDelta * 100).toFixed(1)}%`)
    }
    if (improvements.tensionDelta > 0) {
      parts.push(`${improvements.tensionDelta} tensions resolved`)
    }
    if (parts.length === 0) {
      parts.push('minimal change — field was already well-organized')
    }

    return {
      before,
      after,
      improvements,
      summary: parts.join('; '),
    }
  }


  /**
   * Record that an organizing session touched specific regions.
   * Updates the region history and persists via MeditationStore.
   */
  recordOrganizingSession(
    sessionId: string,
    regionsOrganized: string[],
    before: FieldHealthSnapshot,
    after: FieldHealthSnapshot,
  ): { record: OrganizingSessionRecord; delta: OrganizingDelta } {
    const delta = this.computeDelta(before, after)
    const record: OrganizingSessionRecord = {
      sessionId,
      timestamp: Date.now(),
      regionsOrganized,
      before: {
        fragmentationScore: before.fragmentationScore,
        engramCount: before.engramCount,
        synapseCount: before.synapseCount,
        nucleusCount: before.nucleusCount,
        tensionCount: before.tensionCount,
      },
      after: {
        fragmentationScore: after.fragmentationScore,
        engramCount: after.engramCount,
        synapseCount: after.synapseCount,
        nucleusCount: after.nucleusCount,
        tensionCount: after.tensionCount,
      },
      deltaSummary: delta.summary,
    }

    // Update region history
    const history = this.loadRegionHistory()
    for (const regionId of regionsOrganized) {
      history[regionId] = Date.now()
    }
    this.saveRegionHistory(history)
    this.saveLastHealth(after)

    // Persist session record
    this.saveSessionRecord(record)

    this.logger.info('[FieldHealth] Organizing session recorded', {
      sessionId,
      regionsOrganized: regionsOrganized.length,
      fragmentationBefore: before.fragmentationScore.toFixed(3),
      fragmentationAfter: after.fragmentationScore.toFixed(3),
      summary: delta.summary,
    })

    return { record, delta }
  }


  /**
   * Get recent organizing session records for trend analysis.
   */
  getRecentSessions(limit = 10): OrganizingSessionRecord[] {
    if (!this.store) return []
    try {
      const json = this.store.getMetaText(META_KEY_SESSION_HISTORY)
      if (!json) return []
      const all = JSON.parse(json) as OrganizingSessionRecord[]
      return all.slice(-limit)
    } catch {
      return []
    }
  }


  /**
   * Format the current health state as a human-readable report.
   * Used by the organizing explorer's survey_field tool.
   */
  formatHealthReport(snapshot?: FieldHealthSnapshot): string {
    const s = snapshot ?? this.snapshot()
    const lines: string[] = [
      `Field Health Report (${new Date(s.timestamp).toISOString()})`,
      '',
      `Fragmentation Score: ${s.fragmentationScore.toFixed(3)} ${this.scoreEmoji(s.fragmentationScore)}`,
      '',
      'Metrics:',
      `  Engrams: ${s.engramCount}`,
      `  Synapses: ${s.synapseCount} (density: ${s.connectionDensity.toFixed(2)} per engram)`,
      `  Clusters: ${s.nucleusCount}`,
      `  Abstraction coverage: ${(s.abstractionCoverage * 100).toFixed(1)}%`,
      `  Orphan ratio: ${(s.orphanRatio * 100).toFixed(1)}%`,
      `  Potentiation spread: ${s.potentiationSpread.toFixed(3)}`,
      `  Unresolved tensions: ${s.tensionCount}`,
      `  Filaments: ${s.filamentCount}`,
    ]

    if (s.regions.length > 0) {
      lines.push('', 'Regions by priority:')
      const sorted = [...s.regions].sort((a, b) => b.neglectScore - a.neglectScore)
      for (const r of sorted.slice(0, 8)) {
        const abstraction = r.hasAbstraction ? 'has-summary' : 'NO-SUMMARY'
        const neglect = r.neglectScore > 0.8 ? 'NEGLECTED' : r.neglectScore > 0.4 ? 'stale' : 'recent'
        lines.push(
          `  - ${r.label} (${r.memberCount} members, pot: ${r.avgPotentiation.toFixed(3)}, ${abstraction}, ${neglect})`
        )
      }
      if (s.regions.length > 8) {
        lines.push(`  ... and ${s.regions.length - 8} more regions`)
      }
    }

    return lines.join('\n')
  }


  private scoreEmoji(score: number): string {
    if (score < 0.2) return '(excellent)'
    if (score < 0.4) return '(good)'
    if (score < 0.6) return '(moderate)'
    if (score < 0.8) return '(needs attention)'
    return '(critical)'
  }


  private loadRegionHistory(): Record<string, number> {
    if (!this.store) return {}
    try {
      const json = this.store.getMetaText(META_KEY_REGION_HISTORY)
      return json ? JSON.parse(json) : {}
    } catch {
      return {}
    }
  }

  private saveRegionHistory(history: Record<string, number>): void {
    if (!this.store) return
    try {
      this.store.setMetaText(META_KEY_REGION_HISTORY, JSON.stringify(history))
    } catch (err) {
      this.logger.warn('[FieldHealth] Failed to save region history', { error: String(err) })
    }
  }

  private loadLastHealth(): FieldHealthSnapshot | null {
    if (!this.store) return null
    try {
      const json = this.store.getMetaText(META_KEY_LAST_HEALTH)
      return json ? JSON.parse(json) : null
    } catch {
      return null
    }
  }

  private saveLastHealth(snapshot: FieldHealthSnapshot): void {
    if (!this.store) return
    try {
      // Only persist the metrics needed for shouldOrganize() growth check
      const slim = {
        timestamp: snapshot.timestamp,
        engramCount: snapshot.engramCount,
        fragmentationScore: snapshot.fragmentationScore,
      }
      this.store.setMetaText(META_KEY_LAST_HEALTH, JSON.stringify(slim))
    } catch (err) {
      this.logger.warn('[FieldHealth] Failed to save health snapshot', { error: String(err) })
    }
  }

  private saveSessionRecord(record: OrganizingSessionRecord): void {
    if (!this.store) return
    try {
      const existing = this.getRecentSessions(50)
      existing.push(record)
      // Keep last 50 sessions
      const trimmed = existing.slice(-50)
      this.store.setMetaText(META_KEY_SESSION_HISTORY, JSON.stringify(trimmed))
    } catch (err) {
      this.logger.warn('[FieldHealth] Failed to save session record', { error: String(err) })
    }
  }
}
