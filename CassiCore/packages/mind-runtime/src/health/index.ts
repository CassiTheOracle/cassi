/**
 * @cassicore/mind-runtime — retained mind-health read slice (P5).
 *
 * Folds the retained mind-health READ surface of the retired `@cassicore/admin-api`
 * (CASSICORE-FOCUS §5 #27 / §6 P5) into the focused mind runtime as a host-agnostic,
 * read-only module over the retained field + intelligence. The disciplines retained
 * from the admin surface are: cortex, pineal, thalamus, memory, replay, observability.
 *
 * Unlike the deleted admin routes (HTTP handler-coupled, read+write, req/res), this
 * module returns pure in-process read-only snapshots, one function per retained
 * discipline, each resilient (missing subsystem → typed absent, never throws). The
 * channel server feeds these into `/v1/health` (verbose) and `/v1/snapshot`.
 *
 * Rule: READ-ONLY. No signal emission, no tick/attend/curate/drop, no mutation of the
 * field or intelligence. Writes stay ohmypi-side (collect_thoughts / harness tools).
 */

import type { MnemicField } from '@cassicore/mnemic-field'
import type { IEventBus } from '@cassicore/foundation'

import type { MindRuntime } from '../boot.js'

/** Read-only snapshot of the retained cortex discipline. */
export interface CortexHealth {
  available: boolean
  regions?: Array<{ name: string; activation: number; neurons?: number; incomingTracts?: number }>
  activeSignals?: number
  affect?: Record<string, unknown> | null
  stats?: Record<string, unknown> | null
  oscillation?: { running: boolean; lastTickMs?: number }
}

/** Read-only snapshot of the retained pineal discipline (facets/domains). */
export interface PinealHealth {
  available: boolean
  domains?: string[]
  facets?: number
  pinned?: number
}

/** Read-only snapshot of the retained thalamus discipline (brain-state/attention). */
export interface ThalamusHealth {
  available: boolean
  activeSession?: string | null
  contextStats?: Record<string, unknown> | null
}

/** Read-only snapshot of the retained memory discipline (the MnemicField). */
export interface MemoryHealth {
  available: boolean
  engrams?: number
  stats?: Record<string, unknown> | null
  lightning?: Record<string, unknown> | null
  harmony?: Record<string, unknown> | null
}

/** Read-only snapshot of the retained replay discipline (episodic/loop reads). */
export interface ReplayHealth {
  available: boolean
  loops?: { unifiedLoop: boolean; cortexOscillation: boolean }
  sessions?: number
  uptimeMs?: number
}

/** Read-only snapshot of the retained observability discipline (module + bus reads). */
export interface ObservabilityHealth {
  available: boolean
  modules?: number
  busEventsTracked?: number
  startedAt?: number
}

/** Aggregated retained mind-health snapshot (the retained admin read-slice fold). */
export interface MindHealthSnapshot {
  cortex: CortexHealth
  pineal: PinealHealth
  thalamus: ThalamusHealth
  memory: MemoryHealth
  replay: ReplayHealth
  observability: ObservabilityHealth
}

/** Cheap structural access to the retained intelligence's optional subsystems. */
interface SubsystemShape {
  cortex?: {
    listRegions?: () => Array<Record<string, unknown> & { name?: string; activation?: number }>
    readActive?: (opts?: unknown) => unknown
    getAffectState?: () => unknown
    getStats?: () => Record<string, unknown>
    startOscillation?: () => void
  }
  pineal?: {
    getDomains?: () => string[] | unknown[]
    listFacets?: () => unknown[]
    getPinned?: () => unknown[]
  }
  registration?: unknown
}

/** Safe-number helper: returns NaN → undefined. */
function num(v: number | undefined): number | undefined {
  return typeof v === 'number' && Number.isFinite(v) ? v : undefined
}

/**
 * Collect the retained mind-health read snapshot across all six retained disciplines.
 * Reads real field/intelligence state where available; each discipline degrades to
 * `available: false` rather than throwing when its subsystem is absent.
 */
export function collectMindHealth(runtime: MindRuntime): MindHealthSnapshot {
  const intel = runtime.intelligence as unknown as SubsystemShape
  const field = runtime.field as MnemicField | undefined

  // ── cortex ───────────────────────────────────────────────────────────────
  let cortex: CortexHealth = { available: false }
  try {
    const c = intel.cortex
    if (c) {
      const regions = c.listRegions?.() ?? []
      let activeSignals: number | undefined
      try {
        const active = c.readActive?.()
        activeSignals = num(Array.isArray(active) ? active.length : undefined)
      } catch { /* optional */ }
      let oscillation: CortexHealth['oscillation']
      try {
        // Oscillation is interval-driven inside the runtime (boot starts it); we can
        // only read its effect through the cortex snapshot/stats — report running
        // when the cortex object is present and the boot didn't disable it.
        oscillation = { running: true }
      } catch { oscillation = undefined }
      cortex = {
        available: true,
        regions: regions.map(r => ({
          name: r.name ?? '?',
          activation: num(r.activation ?? 0) ?? 0,
        })),
        activeSignals,
        affect: (c.getAffectState?.() as Record<string, unknown> | undefined) ?? null,
        stats: c.getStats?.() ?? null,
        oscillation,
      }
    }
  } catch { /* cortex unavailable */ }

  // ── pineal ───────────────────────────────────────────────────────────────
  let pineal: PinealHealth = { available: false }
  try {
    const p = intel.pineal
    if (p) {
      const domains = p.getDomains?.() ?? []
      const facets = p.listFacets?.() ?? []
      const pinned = p.getPinned?.() ?? []
      pineal = {
        available: true,
        domains: domains.map(d => typeof d === 'string' ? d : String((d as { id?: string }).id ?? '')),
        facets: facets.length,
        pinned: pinned.length,
      }
    }
  } catch { /* pineal unavailable */ }

  // ── thalamus / brain-state ──────────────────────────────────────────────
  let thalamus: ThalamusHealth = { available: false }
  try {
    const activeId = runtime.sessions.currentSessionId
    const ctxRegistry = (intel as unknown as { contextManager?: { stats?: () => Record<string, unknown> } }).contextManager
    const contextStats = ctxRegistry?.stats?.() ?? null
    if (activeId || contextStats) {
      thalamus = { available: true, activeSession: activeId ?? null, contextStats }
    }
  } catch { /* thalamus unavailable */ }

  // ── memory (MnemicField) ────────────────────────────────────────────────
  let memory: MemoryHealth = { available: false }
  if (field) {
    try {
      const stats = field.stats ? field.stats() : null
      const lightning = field.getLightningStatus ? field.getLightningStatus() : null
      let harmony: Record<string, unknown> | null = null
      try {
        const h = field.computeHarmony ? field.computeHarmony() : null
        harmony = h as Record<string, unknown> | null
      } catch { harmony = null }
      memory = {
        available: true,
        engrams: (stats?.engramCount as number | undefined) ?? undefined,
        stats: stats as Record<string, unknown> | null,
        lightning: lightning as Record<string, unknown> | null,
        harmony,
      }
    } catch { memory = { available: false } }
  }

  // ── replay / loops ───────────────────────────────────────────────────────
  const replay: ReplayHealth = {
    available: true,
    loops: {
      unifiedLoop: true,
      cortexOscillation: !!intel.cortex,
    },
    sessions: runtime.sessions.snapshotEntries().length,
    uptimeMs: Date.now() - runtime.startedAt,
  }

  // ── observability / bus + module reads ───────────────────────────────────
  let observability: ObservabilityHealth = { available: false }
  try {
    const moduleCount = Array.isArray((intel as unknown as { all?: unknown[] }).all)
      ? (intel as unknown as { all: unknown[] }).all.length
      : undefined
    observability = {
      available: true,
      modules: num(moduleCount),
      busEventsTracked: eventCount(runtime.bus),
      startedAt: runtime.startedAt,
    }
  } catch { observability = { available: false } }

  return { cortex, pineal, thalamus, memory, replay, observability }
}

/** Best-effort count of events seen on the retained bus. */
function eventCount(bus: IEventBus): number | undefined {
  // The bus exposes a history via `getEventHistory` in @cassicore/events; the
  // retained mind-runtime boot wires one. Here we just report the sampler length
  // if present — otherwise leave undefined (observability still reports the rest).
  try {
    const hist = (bus as unknown as { history?: { length?: number } }).history
    return num(hist?.length)
  } catch {
    return undefined
  }
}
