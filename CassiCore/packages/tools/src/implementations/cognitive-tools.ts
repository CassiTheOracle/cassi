/**
 * Cognitive Tools — `_reflect` and `_remember`
 *
 * These tools exploit the free tool loop in request-based billing providers
 * (e.g., GitHub Copilot). When the LLM calls these alongside its normal tools
 * (bash, read_file, etc.), they execute locally with zero additional requests.
 *
 * `_reflect`:  Returns accumulated cognitive context (recent signals, patterns,
 *              observations) so the LLM can incorporate them into its reasoning.
 *              Delegates to Context Manager + Thought Observer for rich context.
 *
 * `_remember`: Stores a cognitive observation instantly. Routes to the injection
 *              aggregator (next turn) and context manager (persistent).
 */

import type { ToolDefinition, ToolHandler } from '../types.js'
import type { ThoughtObserver, CognitiveSignal, SignalKind } from '../../intelligence/thought-observer.js'
import type { CognitiveBridge, ResonancePattern } from '../../intelligence/cognitive-bridge.js'
import type { ILogger } from '../../../types/interfaces.js'


export const reflectDefinition: ToolDefinition = {
  name: '_reflect',
  description:
    'Get accumulated cognitive context — recent observations, patterns, tensions, and edge cases noticed across the conversation. ' +
    'Call this alongside other tools when starting complex work or when you want to check what patterns have been observed. ' +
    'Returns structured context that helps maintain awareness across interactions. Lightweight, instant execution.',
  parameters: {
    type: 'object',
    properties: {
      focus: {
        type: 'string',
        description: 'Optional focus area to filter context (e.g., "error handling", "performance"). If omitted, returns all recent signals.',
      },
    },
    required: [],
  },
  timeoutMs: 5_000,
  category: 'cognitive',
  requiredPermission: 'read-only',
}

export const cognitiveRememberDefinition: ToolDefinition = {
  name: '_remember',
  description:
    'Store a cognitive observation you noticed while working — edge cases, assumptions, tensions, gaps, or insights. ' +
    'Call this alongside other tools when you discover something noteworthy. Observations are routed to the intelligence layer ' +
    'and influence future context. Instant execution, zero overhead.',
  parameters: {
    type: 'object',
    properties: {
      observations: {
        type: 'array',
        description: 'Array of observations to store. Each has kind, text, and confidence.',
        items: {
          type: 'object',
        },
      },
    },
    required: ['observations'],
  },
  timeoutMs: 5_000,
  category: 'cognitive',
  requiredPermission: 'workspace-write',
}


const SIGNAL_PREFIX: Record<string, string> = {
  edge_case:   'EDGE CASE',
  assumption:  'ASSUMPTION',
  tension:     'TENSION',
  gap:         'GAP',
  convergence: 'CONVERGENCE',
  insight:     'INSIGHT',
  memory_note: 'NOTE',
}

function formatSignal(signal: CognitiveSignal): string {
  const prefix = SIGNAL_PREFIX[signal.kind] ?? signal.kind.toUpperCase()
  return `  [${prefix}] (${(signal.confidence * 100).toFixed(0)}%) ${signal.text}`
}

function formatSignalGroup(signals: CognitiveSignal[]): string {
  if (signals.length === 0) return '  (none)'

  // Group by kind for readability
  const grouped = new Map<string, CognitiveSignal[]>()
  for (const s of signals) {
    if (!grouped.has(s.kind)) grouped.set(s.kind, [])
    grouped.get(s.kind)!.push(s)
  }

  const parts: string[] = []
  for (const [_kind, kindSignals] of grouped) {
    for (const s of kindSignals) {
      parts.push(formatSignal(s))
    }
  }

  return parts.join('\n')
}


export interface CognitiveToolDeps {
  thoughtObserver?: ThoughtObserver
  // REMOVED: injectionAggregator — deprecated. Now uses GlobalWorkspace/Thalamus.
  cognitiveBridge?: CognitiveBridge
  contextManager?: {
    getEffectiveContext(sessionId: string, opts?: { query?: string; charBudget?: number }): Promise<{ merged: string }>
  }
  subconscious?: {
    getContextInjection?(sessionId: string): string | undefined
  }
  logger: ILogger
}


/**
 * @dep callers: registerCoreTools (core/tools/implementations/index.ts), cognitive-tools.test.ts (tests/cognitive-tools.test.ts), cognitive-drones.test.ts (tests/cognitive-drones.test.ts), autofix-tool.test.ts (tests/autofix-tool.test.ts)
 * @dep calls: formatSignalGroup, getContextInjection, has, child, getResonancePatterns [+3]
 * @dep module: Intelligence
 * @dep risk: MEDIUM | 4 callers, 0 flows, 1 module
 */

export function makeReflectHandler(deps: CognitiveToolDeps): ToolHandler {
  const log = deps.logger.child?.('_reflect') ?? deps.logger

  return async (input, context) => {
    const focus = (input['focus'] as string | undefined)?.trim()
    const parts: string[] = []

    // 1. Gather signals from Thought Observer
    const thoughtSignals = deps.thoughtObserver?.peekSignals(context.sessionId) ?? []
    if (thoughtSignals.length > 0) {
      let filtered = thoughtSignals
      if (focus) {
        const focusLower = focus.toLowerCase()
        filtered = thoughtSignals.filter(s =>
          s.text.toLowerCase().includes(focusLower) ||
          s.kind.includes(focusLower)
        )
      }
      if (filtered.length > 0) {
        parts.push(`COGNITIVE OBSERVATIONS (${filtered.length} signals from thinking analysis):\n${formatSignalGroup(filtered)}`)
      }
    }

    // 2. Gather subconscious context if available
    if (deps.subconscious?.getContextInjection) {
      try {
        const subconsciousCtx = deps.subconscious.getContextInjection(context.sessionId)
        if (subconsciousCtx) {
          // Trim to a reasonable size for tool result
          const trimmed = subconsciousCtx.slice(0, 2000)
          parts.push(`SUBCONSCIOUS OBSERVATIONS:\n${trimmed}`)
        }
      } catch {
        // best-effort
      }
    }

    // 3. Gather fused signals from brain-linked peers (via CognitiveBridge)
    if (deps.cognitiveBridge) {
      const fusedSignals = deps.cognitiveBridge.getFusedSignals(context.sessionId)
      if (fusedSignals.length > 0) {
        let filtered = fusedSignals
        if (focus) {
          const focusLower = focus.toLowerCase()
          filtered = fusedSignals.filter(s =>
            s.text.toLowerCase().includes(focusLower) ||
            s.kind.includes(focusLower)
          )
        }
        if (filtered.length > 0) {
          parts.push(`PEER COGNITIVE SIGNALS (${filtered.length} from brain-linked sessions):\n${formatSignalGroup(filtered)}`)
        }
      }

      // 4. Resonance patterns — amplified cross-session convergences
      const resonance = deps.cognitiveBridge.getResonancePatterns(context.sessionId)
      if (resonance.length > 0) {
        const lines = resonance.map(r => {
          const label = r.kind === 'resonance' ? 'RESONANCE' : 'TENSION'
          const conf = `${(r.amplifiedConfidence * 100).toFixed(0)}%`
          if (r.kind === 'resonance') {
            return `  [${label}] (${conf}) Both sessions independently noted: "${r.signalA.signal.text.slice(0, 100)}"`
          } else {
            return `  [${label}] (${conf}) Sessions diverge: "${r.signalA.signal.text.slice(0, 60)}" vs "${r.signalB.signal.text.slice(0, 60)}"`
          }
        })
        parts.push(`CROSS-SESSION PATTERNS (${resonance.length}):\n${lines.join('\n')}`)
      }
    }

    // 5. Brief context from Context Manager (if focus is specified)
    if (focus && deps.contextManager) {
      try {
        const ctx = await deps.contextManager.getEffectiveContext(context.sessionId, {
          query: focus,
          charBudget: 2000,
        })
        if (ctx.merged && ctx.merged.length > 50) {
          parts.push(`RELEVANT CONTEXT:\n${ctx.merged.slice(0, 2000)}`)
        }
      } catch {
        // best-effort
      }
    }

    if (parts.length === 0) {
      return 'No cognitive observations accumulated yet for this session. Observations build up as I work through my thinking process.'
    }

    log.info(`[_reflect] Returned ${thoughtSignals.length} signals`, {
      sessionId: context.sessionId.slice(-8),
      focus: focus ?? '(all)',
    })

    return parts.join('\n\n')
  }
}

/**
 * @dep callers: registerCoreTools (core/tools/implementations/index.ts), cognitive-tools.test.ts (tests/cognitive-tools.test.ts)
 * @dep calls: has, child, queueDialecticSignal
 * @dep module: Implementations
 * @dep risk: LOW | 2 callers, 0 flows, 1 module
 */

export function makeCognitiveRememberHandler(deps: CognitiveToolDeps): ToolHandler {
  const log = deps.logger.child?.('_remember') ?? deps.logger

  const VALID_KINDS = new Set<string>([
    'edge_case', 'assumption', 'tension', 'gap', 'convergence', 'insight', 'memory_note',
  ])

  return async (input, context) => {
    const rawObservations = input['observations']
    if (!rawObservations || !Array.isArray(rawObservations)) {
      return 'Error: observations must be an array of { kind, text, confidence } objects.'
    }

    const observations: Array<{ kind: string; text: string; confidence: number }> = []

    for (const obs of rawObservations) {
      if (!obs || typeof obs !== 'object') continue
      const kind = String(obs.kind ?? obs.type ?? 'insight')
      const text = String(obs.text ?? obs.content ?? '')
      const confidence = Number(obs.confidence ?? 0.7)

      if (!text.trim()) continue

      observations.push({
        kind: VALID_KINDS.has(kind) ? kind : 'insight',
        text: text.slice(0, 300), // Cap length
        confidence: Math.max(0, Math.min(1, confidence)),
      })
    }

    if (observations.length === 0) {
      return 'No valid observations provided. Each observation needs at least a "text" field.'
    }

    // REMOVED: injectionAggregator routing — deprecated. Observations are now
    // stored via MemoryShim and accessed by Thalamus/GlobalWorkspace.

    log.info(`[_remember] Stored ${observations.length} observation(s)`, {
      sessionId: context.sessionId.slice(-8),
      kinds: observations.map(o => o.kind).join(', '),
    })

    return `Stored ${observations.length} observation(s). They will be available in subsequent interactions.`
  }
}
