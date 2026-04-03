/**
 * Workflow Templates — pre-built workflow patterns for common CassiCore tasks.
 *
 * Templates are factory functions that compose existing step types (toolStep,
 * helixStep, helixBranch, constellationStep) into reusable workflows using
 * the builder API.
 *
 * Each template accepts service dependencies (executor, runner, orchestrator)
 * and options for customization. This keeps templates decoupled from the
 * daemon boot chain and allows tests to inject mocks.
 *
 * Available templates:
 *   codeReviewPipeline      — parallel multi-aspect code review with synthesis
 *   researchPipeline        — parallel investigation from multiple angles
 *   featureImplementation   — design -> implement -> test -> review pipeline
 *   scheduledCleanup        — foreach loop over cleanup tasks using tool steps
 *   eventReactorChain       — branch on event type, dispatch to handlers
 */

import type { WorkflowStep, WorkflowDefinition, StepContext } from '../../types/workflow.js'
import type {
  IHelixRunner,
  HelixResult,
  IConstellationOrchestrator,
  IToolExecutor,
} from './steps.js'
import { createWorkflow, createStep, WorkflowBuilder } from './builder.js'
import { helixBranch, helixStep, constellationStep, toolStep } from './steps.js'

export interface CodeReviewPipelineOptions {
  /** Unique workflow id (default: 'code-review-pipeline'). */
  id?: string
  /** Files or paths to review. Passed as workflow input if not set here. */
  target?: string
  /** Review aspects to run in parallel (default: correctness, security, performance). */
  aspects?: Array<{ name: string; goal: string }>
  /** Max iterations per review branch (default: 3). */
  maxIterations?: number
  /** Timeout per branch in ms (default: 5 minutes). */
  branchTimeoutMs?: number
  /** Helix runner instance. */
  runner: IHelixRunner
}

/**
 * Create a code review pipeline that runs multiple review aspects in parallel,
 * then synthesizes findings into a final report.
 *
 * Flow: analyze -> [correctness, security, performance] -> synthesize
 *
 * Input: string (target path or description of what to review)
 * Output: HelixResult (synthesis of all review findings)
 */
export function codeReviewPipeline(opts: CodeReviewPipelineOptions): WorkflowDefinition {
  const aspects = opts.aspects ?? [
    { name: 'correctness', goal: 'Review for logical correctness, edge cases, and regression risks' },
    { name: 'security', goal: 'Review for security vulnerabilities, auth issues, and input validation' },
    { name: 'performance', goal: 'Review for performance bottlenecks, unnecessary allocations, and scalability' },
  ]

  const analyzeStep = helixBranch({
    id: 'analyze-scope',
    description: 'Analyze the target scope and gather context',
    goal: (input) => {
      const target = opts.target ?? String(input)
      return `Analyze the code at "${target}" and produce a summary of: what the code does, its key dependencies, and areas of concern for reviewers.`
    },
    template: 'research',
    runner: opts.runner,
    timeoutMs: opts.branchTimeoutMs ?? 300_000,
  })

  const reviewBranches = aspects.map((aspect) =>
    helixBranch({
      id: `review-${aspect.name}`,
      description: `Review: ${aspect.name}`,
      goal: (input) => {
        const prev = input as HelixResult
        const context = prev?.conclusion ? `Context from analysis: ${prev.conclusion}` : ''
        const target = opts.target ?? 'the analyzed code'
        return `${aspect.goal} in ${target}. ${context}. List specific issues with file paths and line numbers where possible.`
      },
      template: 'review',
      runner: opts.runner,
      timeoutMs: opts.branchTimeoutMs ?? 300_000,
    }),
  )

  const synthesizeStep = helixBranch({
    id: 'synthesize-review',
    description: 'Synthesize all review findings',
    goal: 'Synthesize the parallel review findings into a prioritized report. Group by severity (critical, major, minor). Include actionable recommendations.',
    template: 'research',
    runner: opts.runner,
    timeoutMs: opts.branchTimeoutMs ?? 300_000,
  })

  return createWorkflow({ id: opts.id ?? 'code-review-pipeline', description: 'Multi-aspect parallel code review with synthesis' })
    .then(analyzeStep)
    .parallel(reviewBranches)
    .then(synthesizeStep)
    .commit()
}

export interface ResearchPipelineOptions {
  /** Unique workflow id (default: 'research-pipeline'). */
  id?: string
  /** Research angles to investigate in parallel. */
  angles: Array<{ name: string; goal: string }>
  /** Max iterations per angle (default: 5). */
  maxIterations?: number
  /** Timeout per angle in ms (default: 5 minutes). */
  angleTimeoutMs?: number
  /** Helix runner instance. */
  runner: IHelixRunner
}

/**
 * Create a research pipeline that investigates a question from multiple angles
 * in parallel, then synthesizes findings.
 *
 * Flow: [angle1, angle2, ...angleN] -> synthesize
 *
 * Input: string (research question or topic)
 * Output: HelixResult (synthesized findings)
 */
export function researchPipeline(opts: ResearchPipelineOptions): WorkflowDefinition {
  const angleBranches = opts.angles.map((angle) =>
    helixBranch({
      id: `research-${angle.name}`,
      description: `Investigate: ${angle.name}`,
      goal: (input) => {
        const topic = String(input)
        return `${angle.goal}. Research topic: "${topic}". Provide findings with supporting evidence and citations where available.`
      },
      template: 'research',
      runner: opts.runner,
      timeoutMs: opts.angleTimeoutMs ?? 300_000,
    }),
  )

  const synthesizeStep = helixBranch({
    id: 'synthesize-research',
    description: 'Synthesize all research findings',
    goal: 'Synthesize the parallel research findings into a comprehensive report. Identify areas of agreement, disagreement, and gaps. Provide a clear conclusion and recommended next steps.',
    template: 'research',
    runner: opts.runner,
    timeoutMs: opts.angleTimeoutMs ?? 300_000,
  })

  return createWorkflow({ id: opts.id ?? 'research-pipeline', description: 'Multi-angle parallel research with synthesis' })
    .parallel(angleBranches)
    .then(synthesizeStep)
    .commit()
}

export interface FeatureImplementationOptions {
  /** Unique workflow id (default: 'feature-implementation'). */
  id?: string
  /** Feature description. Passed as workflow input if not set here. */
  feature?: string
  /** Whether to include test step (default: true). */
  includeTests?: boolean
  /** Whether to include review step (default: true). */
  includeReview?: boolean
  /** Timeout per step in ms (default: 10 minutes). */
  stepTimeoutMs?: number
  /** Helix runner instance. */
  runner: IHelixRunner
}

/**
 * Create a feature implementation pipeline: design -> implement -> test -> review.
 *
 * Flow: design -> implement -> [test (optional)] -> [review (optional)]
 *
 * Input: string (feature description)
 * Output: HelixResult (final review or last step's result)
 */
export function featureImplementation(opts: FeatureImplementationOptions): WorkflowDefinition {
  const builder = createWorkflow({
    id: opts.id ?? 'feature-implementation',
    description: 'Design, implement, test, and review a feature',
  })

  builder.then(helixBranch({
    id: 'design',
    description: 'Design the feature approach',
    goal: (input) => {
      const feature = opts.feature ?? String(input)
      return `Design an implementation approach for: "${feature}". Identify the files to modify, the interfaces to change, and any risks. Output a clear plan with numbered steps.`
    },
    template: 'research',
    runner: opts.runner,
    timeoutMs: opts.stepTimeoutMs ?? 600_000,
  }))

  builder.then(helixBranch({
    id: 'implement',
    description: 'Implement the feature',
    goal: (input) => {
      const prev = input as HelixResult
      const feature = opts.feature ?? 'the designed feature'
      return `Implement ${feature} following this design: ${prev?.conclusion ?? 'no design available'}. Write clean, well-tested code.`
    },
    template: 'implementation',
    runner: opts.runner,
    timeoutMs: opts.stepTimeoutMs ?? 600_000,
  }))

  if (opts.includeTests !== false) {
    builder.then(helixBranch({
      id: 'test',
      description: 'Write and run tests',
      goal: 'Write comprehensive tests for the implemented feature. Cover happy paths, edge cases, and error scenarios. Run the tests and fix any failures.',
      template: 'implementation',
      runner: opts.runner,
      timeoutMs: opts.stepTimeoutMs ?? 600_000,
    }))
  }

  if (opts.includeReview !== false) {
    builder.then(helixBranch({
      id: 'review',
      description: 'Review the implementation',
      goal: 'Review all changes made in this pipeline for correctness, code quality, and completeness. Check that the original requirements are met. List any issues found.',
      template: 'review',
      runner: opts.runner,
      timeoutMs: opts.stepTimeoutMs ?? 600_000,
    }))
  }

  return builder.commit()
}

export interface ScheduledCleanupOptions {
  /** Unique workflow id (default: 'scheduled-cleanup'). */
  id?: string
  /** Cleanup tasks to execute in sequence. */
  tasks: Array<{
    name: string
    tool: string
    args: Record<string, unknown> | ((input: unknown) => Record<string, unknown> | Promise<Record<string, unknown>>)
    description?: string
  }>
  /** Session id for tool execution. */
  sessionId: string
  /** Tool executor instance. */
  executor: IToolExecutor
}

/**
 * Create a scheduled cleanup workflow that runs a series of tool-based tasks.
 *
 * Flow: task1 -> task2 -> ... -> taskN
 *
 * Input: any (passed to first task)
 * Output: result of last task
 */
export function scheduledCleanup(opts: ScheduledCleanupOptions): WorkflowDefinition {
  const builder = createWorkflow({
    id: opts.id ?? 'scheduled-cleanup',
    description: 'Sequential cleanup tasks',
  })

  for (const task of opts.tasks) {
    builder.then(toolStep({
      id: task.name,
      description: task.description ?? `Cleanup: ${task.name}`,
      tool: task.tool,
      args: task.args,
      sessionId: opts.sessionId,
      executor: opts.executor,
    }))
  }

  return builder.commit()
}

export interface EventReactorChainOptions {
  /** Unique workflow id (default: 'event-reactor'). */
  id?: string
  /** Routes: match event data to handlers. Evaluated in order. */
  routes: Array<{
    /** Human-readable name for this route. */
    name: string
    /** Condition: returns true if this route should handle the event. */
    match: (input: unknown) => boolean | Promise<boolean>
    /** Handler step to execute when matched. */
    handler: WorkflowStep
  }>
  /** Optional fallback handler when no route matches. */
  fallback?: WorkflowStep
}

/**
 * Create an event reactor workflow that branches on event data, dispatching
 * to the matching handler.
 *
 * Flow: branch(match1 -> handler1, match2 -> handler2, ..., fallback)
 *
 * Input: event data (from trigger)
 * Output: result of matched handler
 */
export function eventReactorChain(opts: EventReactorChainOptions): WorkflowDefinition {
  const routes = opts.routes.map((route) => ({
    condition: route.match,
    nodes: [{ id: `route-${route.name}`, kind: 'step' as const, step: route.handler }],
  }))

  const fallbackNodes = opts.fallback
    ? [{ id: 'fallback', kind: 'step' as const, step: opts.fallback }]
    : undefined

  return createWorkflow({
    id: opts.id ?? 'event-reactor',
    description: 'Branch on event data and dispatch to handlers',
  })
    .branch(
      routes.map((r) => [r.condition, r.nodes[0].step] as [typeof r.condition, WorkflowStep]),
      opts.fallback,
    )
    .commit()
}
