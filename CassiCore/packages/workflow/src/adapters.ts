/**
 * Workflow Adapters — bridge intelligence modules to workflow step interfaces.
 *
 * The workflow system defines minimal service interfaces (IHelixRunner,
 * IToolExecutor, IConstellationOrchestrator) to stay decoupled from core/
 * internals. These adapters bridge from the actual daemon services to those
 * interfaces, enabling templates to run with real implementations.
 *
 * Each adapter factory returns a lazy object that resolves the underlying
 * service on each call, so it works even when services are wired after
 * the workflow system is initialized.
 */

import type { IHelixRunner, HelixResult, IToolExecutor, IConstellationOrchestrator, ConstellationResult } from './steps.js'
import type { HelixOrchestrator } from '../intelligence/helix/index.js'
import type { HelixResult as InternalHelixResult } from '../intelligence/helix/types.js'
import type { ConstellationOrchestrator as InternalConstellationOrchestrator } from '../intelligence/constellation/constellation-orchestrator.js'
import type { ConstellationResult as InternalConstellationResult } from '../intelligence/constellation/types.js'
import type { ToolExecutor } from '../tools/executor.js'

/**
 * Create an IHelixRunner adapter from a HelixOrchestrator.
 *
 * Maps the workflow's simplified run() interface to the full Helix project() call,
 * and extracts a simplified result.
 */
export function createHelixRunnerAdapter(
  getHelix: () => HelixOrchestrator | undefined,
): IHelixRunner {
  return {
    async run(config) {
      const helix = getHelix()
      if (!helix) throw new Error('Helix orchestrator not available')

      const result: InternalHelixResult = await helix.project({
        goal: config.goal,
        context: config.context,
        sessionId: config.sessionId,
        parentSessionId: config.parentSessionId,
        maxIterations: config.maxIterations,
        timeoutMs: config.timeoutMs,
        toolAccessOverride: config.toolAccess as 'read-only' | 'read-only+memory' | 'full' | undefined,
      })

      return mapHelixResult(result)
    },
  }
}

function mapHelixResult(r: InternalHelixResult): HelixResult {
  return {
    conclusion: r.mentorConclusion || r.unityConclusion || '(no conclusion)',
    confidence: r.mentorConfidence ?? r.qualityScore ?? 0,
    filesModified: (r.filesModified ?? []).map(f => typeof f === 'string' ? f : f.path),
    synthesis: r.mentorSynthesis ?? r.mentorConclusion,
    durationMs: r.durationMs,
    findings: [
      ...(r.mentorKeyFindings ?? []).map(f => ({ type: 'finding', content: f })),
      ...(r.mentorRemainingRisks ?? []).map(f => ({ type: 'risk', content: f })),
    ],
  }
}

/**
 * Create an IConstellationOrchestrator adapter from the real ConstellationOrchestrator.
 *
 * Maps the workflow's simplified project() interface to the full Constellation
 * call, and extracts a simplified result.
 */
export function createConstellationAdapter(
  getConstellation: () => InternalConstellationOrchestrator | undefined,
): IConstellationOrchestrator {
  return {
    async project(opts) {
      const constellation = getConstellation()
      if (!constellation) throw new Error('Constellation orchestrator not available')

      const result: InternalConstellationResult = await constellation.project({
        goal: opts.goal,
        context: opts.context,
        template: opts.template as any,
        sessionId: opts.sessionId,
      })

      return mapConstellationResult(result)
    },
  }
}

function mapConstellationResult(r: InternalConstellationResult): ConstellationResult {
  const branches = [...(r.nodes?.values() ?? [])].map(node => {
    const mentorResult = node.postureResults.get('mentor')
    const unityResult = node.postureResults.get('unity')
    const conclusion = mentorResult?.conclusion ?? unityResult?.conclusion ?? ''
    const durationMs = node.completedAt && node.startedAt
      ? node.completedAt - node.startedAt
      : 0

    return {
      helixId: node.helixId,
      sessionId: node.helixId,
      status: node.status ?? 'unknown',
      conclusion,
      filesModified: [] as string[],
      durationMs,
    }
  })

  return {
    sessionId: r.constellationId,
    status: r.recommendation ?? 'completed',
    branches,
    synthesis: r.synthesis,
    conclusion: r.synthesis ?? r.recommendation ?? '(no conclusion)',
    filesModified: branches.flatMap(b => b.filesModified ?? []),
    durationMs: r.totalDurationMs,
  }
}

/**
 * Create an IToolExecutor adapter from the daemon's ToolExecutor.
 *
 * Maps the workflow's simplified execute() call to the full ToolExecutor,
 * generating call IDs and mapping argument names.
 */
export function createToolExecutorAdapter(
  getExecutor: () => ToolExecutor | undefined,
): IToolExecutor {
  let callCounter = 0

  return {
    async execute(call, sessionId, opts?) {
      const executor = getExecutor()
      if (!executor) throw new Error('Tool executor not available')

      const result = await executor.execute(
        {
          id: `wf-tool-${++callCounter}`,
          name: call.name,
          input: call.arguments,
        },
        sessionId,
        opts,
      )

      return {
        content: result.rawContent ?? result.content,
        isError: result.isError,
      }
    },
  }
}
