/**
 * StateSnapshot — captures system state at a point in time for comparison.
 *
 * Supports two capture modes:
 * - **In-process**: built from direct object access (vitest harness)
 * - **Remote**: built from admin API JSON responses (live daemon)
 *
 * The diff() method compares two snapshots and reports which paths changed,
 * enabling "before/after" verification of workflows.
 */

/** Session-level state */
export interface SessionState {
  turnCount: number
  messageCount: number
  lastModel?: string
  contextTokens?: number
}

/** Intelligence module status */
export interface ModuleState {
  name: string
  status: 'running' | 'stopped' | 'error' | 'unknown'
  eventsProcessed?: number
  lastActivity?: number
}

/** Full snapshot data */
export interface SnapshotData {
  timestamp: number
  session?: SessionState
  modules: Record<string, ModuleState>
  events: {
    totalEmitted: number
    byType: Record<string, number>
  }
  trust?: Record<string, { score: number; evidence: number }>
  custom?: Record<string, unknown>
}

/** A single changed path in a diff */
export interface DiffEntry {
  path: string
  before: unknown
  after: unknown
}

/** Result of comparing two snapshots */
export interface SnapshotDiff {
  changed: DiffEntry[]
  unchanged: string[]
  added: string[]
  removed: string[]
}

export class StateSnapshot {
  readonly data: SnapshotData

  constructor(data: SnapshotData) {
    this.data = data
  }


  /** Create a snapshot from in-process data */
  static create(partial: Partial<SnapshotData>): StateSnapshot {
    return new StateSnapshot({
      timestamp: Date.now(),
      modules: {},
      events: { totalEmitted: 0, byType: {} },
      ...partial,
    })
  }

  /** Create from admin API JSON responses */
  static fromLiveData(data: {
    session?: any
    intelligence?: any
    trust?: any
    events?: any
    custom?: Record<string, unknown>
  }): StateSnapshot {
    const sessionState: SessionState | undefined = data.session ? {
      turnCount: data.session.turnCount ?? data.session.turns ?? 0,
      messageCount: data.session.messageCount ?? data.session.messages?.length ?? 0,
      lastModel: data.session.lastModel,
      contextTokens: data.session.contextTokens,
    } : undefined

    const modules: Record<string, ModuleState> = {}
    if (data.intelligence?.modules) {
      for (const [name, mod] of Object.entries(data.intelligence.modules as Record<string, any>)) {
        modules[name] = {
          name,
          status: mod.status ?? mod.healthy ? 'running' : 'unknown',
          eventsProcessed: mod.eventsProcessed,
          lastActivity: mod.lastActivity,
        }
      }
    }

    const trust: Record<string, { score: number; evidence: number }> | undefined =
      data.trust ? Object.fromEntries(
        Object.entries(data.trust as Record<string, any>).map(([domain, t]) => [
          domain,
          { score: (t as any).score ?? 0, evidence: (t as any).evidence ?? 0 },
        ])
      ) : undefined

    return new StateSnapshot({
      timestamp: Date.now(),
      session: sessionState,
      modules,
      events: data.events ?? { totalEmitted: 0, byType: {} },
      trust,
      custom: data.custom,
    })
  }


  /** Get a value by dot-path (e.g., "session.turnCount", "modules.thinker.status") */
  get(path: string): unknown {
    return getByPath(this.data, path)
  }


  /** Compare this snapshot against another and report differences */
  diff(other: StateSnapshot): SnapshotDiff {
    const beforePaths = flattenPaths(this.data)
    const afterPaths = flattenPaths(other.data)

    const allKeys = Object.keys(beforePaths).concat(Object.keys(afterPaths))
    const allPaths = Array.from(new Set(allKeys))
    const changed: DiffEntry[] = []
    const unchanged: string[] = []
    const added: string[] = []
    const removed: string[] = []

    for (const path of allPaths) {
      // Skip metadata
      if (path === 'timestamp') continue

      const inBefore = path in beforePaths
      const inAfter = path in afterPaths

      if (inBefore && inAfter) {
        if (stableStringify(beforePaths[path]) !== stableStringify(afterPaths[path])) {
          changed.push({ path, before: beforePaths[path], after: afterPaths[path] })
        } else {
          unchanged.push(path)
        }
      } else if (inAfter) {
        added.push(path)
      } else {
        removed.push(path)
      }
    }

    return { changed, unchanged, added, removed }
  }


  /** Assert a path changed between this snapshot and another */
  assertChanged(other: StateSnapshot, path: string): void {
    const d = this.diff(other)
    const isChanged = d.changed.some(c => c.path === path) || d.added.includes(path) || d.removed.includes(path)
    if (!isChanged) {
      throw new SnapshotAssertionError(`Expected "${path}" to change but it did not`, this.data, other.data)
    }
  }

  /** Assert a path did NOT change between this snapshot and another */
  assertUnchanged(other: StateSnapshot, path: string): void {
    const d = this.diff(other)
    const isChanged = d.changed.some(c => c.path === path) || d.added.includes(path) || d.removed.includes(path)
    if (isChanged) {
      const entry = d.changed.find(c => c.path === path)
      throw new SnapshotAssertionError(
        `Expected "${path}" unchanged but it changed` +
        (entry ? ` from ${JSON.stringify(entry.before)} to ${JSON.stringify(entry.after)}` : ''),
        this.data,
        other.data,
      )
    }
  }

  /** Assert a specific value at a path */
  assertValue(path: string, expected: unknown): void {
    const actual = this.get(path)
    if (stableStringify(actual) !== stableStringify(expected)) {
      throw new SnapshotAssertionError(
        `Expected "${path}" to be ${JSON.stringify(expected)} but got ${JSON.stringify(actual)}`,
        this.data,
        {},
      )
    }
  }

  /** Assert a numeric value is greater than a threshold */
  assertGreaterThan(path: string, threshold: number): void {
    const actual = this.get(path)
    if (typeof actual !== 'number' || actual <= threshold) {
      throw new SnapshotAssertionError(
        `Expected "${path}" > ${threshold} but got ${JSON.stringify(actual)}`,
        this.data,
        {},
      )
    }
  }
}


export class SnapshotAssertionError extends Error {
  constructor(
    message: string,
    public readonly snapshotA: unknown,
    public readonly snapshotB: unknown,
  ) {
    super(message)
    this.name = 'SnapshotAssertionError'
  }
}


/** Resolve a dot-path like "session.turnCount" against an object */
function getByPath(obj: unknown, path: string): unknown {
  const parts = path.split('.')
  let current: unknown = obj
  for (const part of parts) {
    if (current === null || current === undefined || typeof current !== 'object') return undefined
    current = (current as Record<string, unknown>)[part]
  }
  return current
}

/** Flatten a nested object into { "a.b.c": value } pairs (leaf values only) */
/**
 * @dep callers: diff (src/testing/verification/state-snapshot.ts), flattenPaths (src/testing/verification/state-snapshot.ts)
 * @dep calls: flattenPaths
 * @dep module: Verification
 * @dep risk: LOW | 2 callers, 0 flows, 1 module
 */

function flattenPaths(obj: unknown, prefix = ''): Record<string, unknown> {
  const result: Record<string, unknown> = {}
  if (obj === null || obj === undefined || typeof obj !== 'object') {
    if (prefix) result[prefix] = obj
    return result
  }
  for (const [key, value] of Object.entries(obj)) {
    const fullPath = prefix ? `${prefix}.${key}` : key
    if (value !== null && typeof value === 'object' && !Array.isArray(value)) {
      Object.assign(result, flattenPaths(value, fullPath))
    } else {
      result[fullPath] = value
    }
  }
  return result
}

/** Stable JSON stringify for comparison (sorts object keys) */
/**
 * @dep callers: assertValue (src/testing/verification/state-snapshot.ts), diff (src/testing/verification/state-snapshot.ts)
 * @dep module: Verification
 * @dep risk: LOW | 2 callers, 0 flows, 1 module
 */

function stableStringify(value: unknown): string {
  if (value === undefined) return 'undefined'
  return JSON.stringify(value, (_, v) => {
    if (v && typeof v === 'object' && !Array.isArray(v)) {
      return Object.fromEntries(Object.entries(v).sort(([a], [b]) => a.localeCompare(b)))
    }
    return v
  })
}
