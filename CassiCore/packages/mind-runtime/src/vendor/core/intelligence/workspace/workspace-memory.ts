/**
 * WorkspaceMemory — Source credibility tracking and signal memory.
 *
 * Maintains per-module credibility scores that evolve based on feedback:
 * modules that produce signals the LLM incorporates gain credibility;
 * modules that produce noise lose it.
 *
 * Also provides content fingerprinting for novelty scoring — detecting
 * when a signal repeats what's already been surfaced recently.
 *
 * Credibility is the fourth dimension of luminance scoring. It creates
 * a feedback loop where the workspace learns which modules to trust,
 * mirroring how the brain adjusts the gain of neural pathways based on
 * whether their signals led to successful outcomes.
 */


/** Credibility update magnitudes (asymmetric — positive evidence matters more) */
const INCORPORATED_BOOST = 0.03
const NOTED_BOOST = 0.01
const IGNORED_PENALTY = -0.01

const DEFAULT_CREDIBILITY = 0.50
const MIN_CREDIBILITY = 0.10
const MAX_CREDIBILITY = 0.95

/** Max fingerprints to keep for novelty detection */
const MAX_FINGERPRINTS = 200


export type FeedbackOutcome = 'incorporated' | 'noted' | 'ignored'


export interface CredibilityRecord {
  source: string
  credibility: number
  totalSignals: number
  incorporated: number
  noted: number
  ignored: number
  lastUpdated: number
}


export class WorkspaceMemory {
  private credibility = new Map<string, CredibilityRecord>()
  private recentFingerprints = new Map<string, number>()  // fingerprint → timestamp


  /**
   * Get the credibility score for a module source.
   * Returns default (0.50) if never seen.
   */
  getCredibility(source: string): number {
    return this.credibility.get(source)?.credibility ?? DEFAULT_CREDIBILITY
  }

  /**
   * Get the full credibility record for a source.
   */
  getRecord(source: string): CredibilityRecord | undefined {
    return this.credibility.get(source)
  }

  /**
   * Get all credibility records, sorted by credibility descending.
   */
  getAllRecords(): CredibilityRecord[] {
    return Array.from(this.credibility.values())
      .sort((a, b) => b.credibility - a.credibility)
  }


  /**
   * Update credibility based on feedback.
   */
  applyFeedback(source: string, outcome: FeedbackOutcome): void {
    const record = this.ensureRecord(source)

    let delta: number
    switch (outcome) {
      case 'incorporated': delta = INCORPORATED_BOOST; record.incorporated++; break
      case 'noted': delta = NOTED_BOOST; record.noted++; break
      case 'ignored': delta = IGNORED_PENALTY; record.ignored++; break
    }

    record.credibility = Math.max(MIN_CREDIBILITY, Math.min(MAX_CREDIBILITY, record.credibility + delta))
    record.totalSignals++
    record.lastUpdated = Date.now()
  }


  /**
   * Record that a signal was submitted (for tracking total volume).
   */
  recordSubmission(source: string): void {
    this.ensureRecord(source)
  }


  /**
   * Check if content has been recently surfaced (for novelty scoring).
   * Returns true if similar content was seen within the given window.
   */
  isRecentlySurfaced(content: string, windowMs = 60_000): boolean {
    const fp = this.fingerprint(content)
    const lastSeen = this.recentFingerprints.get(fp)
    if (lastSeen && (Date.now() - lastSeen) < windowMs) return true

    this.recentFingerprints.set(fp, Date.now())
    this.pruneFingerprints()
    return false
  }


  /**
   * Simple content fingerprint — first 100 chars normalized.
   */
  private fingerprint(content: string): string {
    return content.toLowerCase().replace(/\s+/g, ' ').trim().slice(0, 100)
  }

  private pruneFingerprints(): void {
    if (this.recentFingerprints.size <= MAX_FINGERPRINTS) return
    const cutoff = Date.now() - 300_000
    for (const [fp, ts] of this.recentFingerprints) {
      if (ts < cutoff) this.recentFingerprints.delete(fp)
    }
  }

  private ensureRecord(source: string): CredibilityRecord {
    let record = this.credibility.get(source)
    if (!record) {
      record = {
        source,
        credibility: DEFAULT_CREDIBILITY,
        totalSignals: 0,
        incorporated: 0,
        noted: 0,
        ignored: 0,
        lastUpdated: Date.now(),
      }
      this.credibility.set(source, record)
    }
    return record
  }


  /**
   * Serialize for persistence (optional — credibility can be rebuilt from scratch).
   */
  serialize(): Record<string, CredibilityRecord> {
    const result: Record<string, CredibilityRecord> = {}
    for (const [key, record] of this.credibility) {
      result[key] = { ...record }
    }
    return result
  }

  /**
   * Restore from serialized state.
   */
  restore(data: Record<string, CredibilityRecord>): void {
    this.credibility.clear()
    for (const [key, record] of Object.entries(data)) {
      this.credibility.set(key, { ...record })
    }
  }
}
