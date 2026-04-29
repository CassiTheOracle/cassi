export interface BroadcastDedupeDecision {
  duplicate: boolean
  reason?: string
  similarTo?: string
}


export interface BroadcastDedupeOpts {
  maxHistory?: number
  ttlMs?: number
  similarityThreshold?: number
}


interface BroadcastRecord {
  key: string
  normalized: string
  at: number
}


export class BroadcastDedupe {
  private maxHistory: number
  private ttlMs: number
  private similarityThreshold: number
  private history: BroadcastRecord[] = []

  constructor(opts: BroadcastDedupeOpts = {}) {
    this.maxHistory = opts.maxHistory ?? 32
    this.ttlMs = opts.ttlMs ?? 120_000
    this.similarityThreshold = opts.similarityThreshold ?? 0.82
  }

  check(key: string, text: string): BroadcastDedupeDecision {
    const now = Date.now()
    this.prune(now)
    const normalized = normalizeForDedupe(text)
    if (!normalized) return { duplicate: true, reason: 'empty' }

    for (const record of this.history) {
      if (record.key !== key) continue
      if (record.normalized === normalized) {
        return { duplicate: true, reason: 'exact', similarTo: record.normalized }
      }
      const sim = jaccardSimilarity(record.normalized, normalized)
      if (sim >= this.similarityThreshold) {
        return { duplicate: true, reason: `similar:${sim.toFixed(2)}`, similarTo: record.normalized }
      }
    }

    return { duplicate: false }
  }

  remember(key: string, text: string): void {
    const now = Date.now()
    this.prune(now)
    const normalized = normalizeForDedupe(text)
    if (!normalized) return
    this.history.push({ key, normalized, at: now })
    if (this.history.length > this.maxHistory) {
      this.history = this.history.slice(-this.maxHistory)
    }
  }

  private prune(now: number): void {
    this.history = this.history.filter(r => now - r.at <= this.ttlMs)
  }
}


export function normalizeForDedupe(text: string): string {
  return text
    .toLowerCase()
    .replace(/[`*_#[\](){}.,:;!?"']/g, ' ')
    .replace(/\b(h|c|thread|group|cluster|helix)[-_]?[a-z0-9]+\b/g, ' id ')
    .replace(/\s+/g, ' ')
    .trim()
}


function jaccardSimilarity(a: string, b: string): number {
  const aSet = tokenSet(a)
  const bSet = tokenSet(b)
  if (aSet.size === 0 || bSet.size === 0) return 0
  let intersection = 0
  for (const token of aSet) {
    if (bSet.has(token)) intersection++
  }
  const union = aSet.size + bSet.size - intersection
  return union === 0 ? 0 : intersection / union
}


function tokenSet(text: string): Set<string> {
  const stop = new Set(['the', 'a', 'an', 'and', 'or', 'to', 'of', 'in', 'on', 'for', 'with', 'is', 'are', 'be', 'this', 'that', 'it', 'i', 'we'])
  return new Set(text.split(/\s+/).filter(t => t.length > 2 && !stop.has(t)))
}
