/**
 * Cognitive Tools — `_reflect`, `_remember`, and `_probe`
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
 *
 * `_probe`:   Dispatches a targeted drone swarm to investigate a cognitive signal.
 *              Maps signal kinds to investigation strategies, spawns scout drones,
 *              and returns aggregated findings + resonance patterns. This lets the
 *              LLM "think wider" using parallel free drones instead of sequential
 *              reasoning. All within the free tool loop.
 */

import type { ToolDefinition, ToolHandler } from '../types.js'
import type { ThoughtObserver, CognitiveSignal, SignalKind } from '../../intelligence/thought-observer.js'
import type { InjectionAggregator } from '../../intelligence/injection-aggregator.js'
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

    // Suggest probing for high-confidence signals that would benefit from investigation
    // Use filtered signals if a focus was specified, otherwise use all thought signals
    const PROBEABLE_KINDS = new Set(['edge_case', 'assumption', 'tension', 'gap', 'insight'])
    const signalsForProbing = focus
      ? thoughtSignals.filter(s => {
          const focusLower = focus.toLowerCase()
          return s.text.toLowerCase().includes(focusLower) || s.kind.includes(focusLower)
        })
      : thoughtSignals
    const probeableSignals = signalsForProbing.filter(s => PROBEABLE_KINDS.has(s.kind) && s.confidence >= 0.7)
    if (probeableSignals.length > 0) {
      const top = probeableSignals.sort((a, b) => b.confidence - a.confidence).slice(0, 3)
      const suggestions = top.map(s =>
        `  → _probe(signal_kind="${s.kind}", signal_text="${s.text.slice(0, 80)}")`
      )
      parts.push(`PROBE SUGGESTIONS — investigate these signals with free drone swarms:\n${suggestions.join('\n')}`)

      // For high-confidence actionable signals, also suggest _autofix
      const FIXABLE_KINDS = new Set(['edge_case', 'gap'])
      const fixableSignals = top.filter(s => FIXABLE_KINDS.has(s.kind) && s.confidence >= 0.80)
      if (fixableSignals.length > 0) {
        const fixSuggestions = fixableSignals.map(s =>
          `  → _autofix(signal_kind="${s.kind}", signal_text="${s.text.slice(0, 80)}")`
        )
        parts.push(`AUTOFIX SUGGESTIONS — these high-confidence bugs can be fixed autonomously:\n${fixSuggestions.join('\n')}`)
      }
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

// _probe — Dispatch targeted drone swarms to investigate cognitive signals

export const probeDefinition: ToolDefinition = {
  name: '_probe',
  description:
    'Dispatch a targeted drone swarm to investigate a cognitive signal in depth. ' +
    'Maps the signal kind (edge_case, assumption, gap, tension, insight) to investigation strategies, ' +
    'spawns scout drones in parallel, and returns aggregated findings including any resonance patterns. ' +
    'This lets you "think wider" using parallel free drones instead of collecting thoughts step-by-step. ' +
    'Call this when _reflect surfaces a signal that deserves deeper investigation. ' +
    'Executes within the free tool loop — all drones use gpt-5-mini on request-based billing.',
  parameters: {
    type: 'object',
    properties: {
      signal_kind: {
        type: 'string',
        description: 'Kind of cognitive signal to investigate',
        enum: ['edge_case', 'assumption', 'tension', 'gap', 'insight'],
      },
      signal_text: {
        type: 'string',
        description: 'The signal text to investigate (from _reflect output)',
      },
      depth: {
        type: 'string',
        description: 'Investigation depth: "shallow" = 3 drones, "deep" = 7 drones. Default "shallow".',
        enum: ['shallow', 'deep'],
      },
      context: {
        type: 'string',
        description: 'Additional context to help the drones (e.g., relevant file paths, function names)',
      },
    },
    required: ['signal_kind', 'signal_text'],
  },
  timeoutMs: 60_000,  // Drone swarm can take a while
  category: 'cognitive',
  requiredPermission: 'read-only',
}

/**
 * Maps a signal kind to investigation strategies (prompts for scout drones).
 * Each strategy gives a different investigative angle on the same signal.
 * @dep callers: generateDeepProbeStrategies (core/tools/implementations/cognitive-tools.ts), makeProbeHandler (core/tools/implementations/cognitive-tools.ts)
 * @dep module: Implementations
 * @dep risk: LOW | 2 callers, 0 flows, 1 module
 */
function generateProbeStrategies(
  signalKind: string,
  signalText: string,
  context?: string,
): string[] {
  const ctx = context ? `\n\nAdditional context: ${context}` : ''

  const STRATEGIES: Record<string, string[]> = {
    edge_case: [
      `Find tests or code paths that cover this edge case: "${signalText}". Look for existing test coverage, guard clauses, or error handling that addresses this specific scenario.${ctx}`,
      `Find callers and usages that do NOT guard against this edge case: "${signalText}". Identify vulnerable code paths where this could cause failures.${ctx}`,
      `Find similar patterns in the codebase where this same edge case type has been handled elsewhere. Look for analogous solutions: "${signalText}"${ctx}`,
    ],
    assumption: [
      `Verify whether this assumption holds true across the codebase: "${signalText}". Find evidence supporting or contradicting it.${ctx}`,
      `Find counterexamples where this assumption is violated: "${signalText}". Look for code paths, configurations, or runtime conditions that break this assumption.${ctx}`,
      `Check documentation, comments, and commit messages for context about this assumption: "${signalText}". Was it intentional? Is it documented?${ctx}`,
    ],
    tension: [
      `Analyze the first side of this tension: "${signalText}". What are the implications and downstream effects if we favor this approach?${ctx}`,
      `Analyze the opposing side of this tension: "${signalText}". What are the implications and downstream effects of the alternative?${ctx}`,
      `Find resolution patterns — how have similar tensions been resolved elsewhere in this codebase? Look for compromises, abstractions, or design patterns: "${signalText}"${ctx}`,
    ],
    gap: [
      `Find where in the codebase this gap should be addressed: "${signalText}". Identify the most natural location for implementation.${ctx}`,
      `Check if there are TODOs, FIXMEs, or open issues related to this gap: "${signalText}". Look in comments, issue trackers, and commit messages.${ctx}`,
      `Find how similar functionality is handled elsewhere in the codebase. Look for patterns that could be reused to fill this gap: "${signalText}"${ctx}`,
    ],
    insight: [
      `Find supporting evidence for this insight: "${signalText}". Look for code patterns, performance metrics, or design decisions that confirm it.${ctx}`,
      `Find contradicting evidence or limitations of this insight: "${signalText}". Look for edge cases or contexts where it doesn't apply.${ctx}`,
      `Map the blast radius — what code paths and components are affected by this insight: "${signalText}"? Identify all impacted areas.${ctx}`,
    ],
  }

  const strategies = STRATEGIES[signalKind] ?? STRATEGIES.insight
  return strategies
}

/**
 * Extended strategies for "deep" probes (7 drones instead of 3).
 * Adds broader and more speculative investigation angles.
 */
function generateDeepProbeStrategies(
  signalKind: string,
  signalText: string,
  context?: string,
): string[] {
  const base = generateProbeStrategies(signalKind, signalText, context)
  const ctx = context ? `\n\nAdditional context: ${context}` : ''

  const deep = [
    `Trace the execution flow involving this concern: "${signalText}". Follow the call chain from entry point to completion, noting every decision point.${ctx}`,
    `Assess the risk and severity if this concern materializes: "${signalText}". What's the worst-case impact? What's the probability?${ctx}`,
    `Identify the minimal change needed to address this concern: "${signalText}". What's the smallest, safest fix?${ctx}`,
    `Look for related concerns in adjacent modules: "${signalText}". Is this part of a broader pattern that spans multiple components?${ctx}`,
  ]

  return [...base, ...deep]
}

export interface ProbeDeps extends CognitiveToolDeps {
  droneSwarm?: {
    scout(
      tasks: Array<{ query: string; context?: string }>,
      parentSessionId: string,
    ): Promise<any>
  }
}

/**
 * @dep callers: registerCoreTools (core/tools/implementations/index.ts), cognitive-drones.test.ts (tests/cognitive-drones.test.ts)
 * @dep calls: generateDeepProbeStrategies, generateProbeStrategies, scout, child
 * @dep module: Implementations
 * @dep risk: LOW | 2 callers, 0 flows, 1 module
 */

export function makeProbeHandler(deps: ProbeDeps): ToolHandler {
  const log = deps.logger.child?.('_probe') ?? deps.logger

  return async (input, context) => {
    const signalKind = String(input['signal_kind'] ?? 'insight')
    const signalText = String(input['signal_text'] ?? '')
    const depth = String(input['depth'] ?? 'shallow')
    const probeContext = (input['context'] as string | undefined)?.trim()

    if (!signalText.trim()) {
      return 'Error: signal_text is required. Pass the signal text from _reflect output.'
    }

    if (!deps.droneSwarm) {
      return 'Error: Drone swarm is not available. _probe requires the drone swarm to be active.'
    }

    // Generate investigation strategies based on signal kind and depth
    const strategies = depth === 'deep'
      ? generateDeepProbeStrategies(signalKind, signalText, probeContext)
      : generateProbeStrategies(signalKind, signalText, probeContext)

    log.info(`[_probe] Dispatching ${strategies.length} drones for ${signalKind} signal`, {
      sessionId: context.sessionId.slice(-8),
      depth,
      signalText: signalText.slice(0, 80),
    })

    try {
      // Build ScoutTask[] from investigation strategies
      const scoutTasks = strategies.map(strategy => ({
        query: strategy,
        context: probeContext,
      }))

      // Dispatch scout swarm — these drones are free on request-based billing
      const result = await deps.droneSwarm.scout(scoutTasks, context.sessionId)

      // Format the results
      const parts: string[] = []
      parts.push(`PROBE RESULTS — ${signalKind.toUpperCase()} investigation (${strategies.length} drones)`)
      parts.push(`Signal: "${signalText.slice(0, 150)}"`)
      parts.push('─'.repeat(60))

      // Aggregated output from the swarm
      if (result?.output) {
        parts.push(result.output.slice(0, 4000))
      } else if (result?.droneResults) {
        const droneResults = Object.entries(result.droneResults) as Array<[string, any]>
        for (const [droneId, dr] of droneResults) {
          if (dr.success && dr.output) {
            parts.push(`\n[Drone ${droneId.slice(-6)}]`)
            parts.push(dr.output.slice(0, 1500))
          }
        }
      }

      // Include cognitive signals extracted from drone outputs
      if (result?.cognitiveSignals && result.cognitiveSignals.length > 0) {
        parts.push('\n' + '─'.repeat(60))
        parts.push(`EXTRACTED SIGNALS (${result.cognitiveSignals.length}):`)
        for (const sig of result.cognitiveSignals.slice(0, 10)) {
          const prefix = SIGNAL_PREFIX[sig.kind] ?? sig.kind.toUpperCase()
          parts.push(`  [${prefix}] (${(sig.confidence * 100).toFixed(0)}%) ${sig.text}`)
        }
      }

      // Include resonance patterns (from Phase 3 — swarm resonance detection)
      if (result?.resonancePatterns && result.resonancePatterns.length > 0) {
        parts.push('\n' + '─'.repeat(60))
        parts.push(`SWARM RESONANCE PATTERNS (${result.resonancePatterns.length}):`)
        for (const pat of result.resonancePatterns) {
          const label = pat.kind === 'swarm_resonance' ? 'CONVERGENCE' : 'TENSION'
          parts.push(`  [${label}] ${pat.droneCount} drones independently flagged (${(pat.amplifiedConfidence * 100).toFixed(0)}%): "${pat.representativeText?.slice(0, 120) ?? ''}"`)
        }
      }

      log.info(`[_probe] Complete`, {
        sessionId: context.sessionId.slice(-8),
        droneCount: strategies.length,
        signalsExtracted: result?.cognitiveSignals?.length ?? 0,
        resonancePatterns: result?.resonancePatterns?.length ?? 0,
      })

      return parts.join('\n')
    } catch (err) {
      log.error('[_probe] Drone swarm failed', { error: String(err) })
      return `Error: Probe failed — ${String(err)}`
    }
  }
}
