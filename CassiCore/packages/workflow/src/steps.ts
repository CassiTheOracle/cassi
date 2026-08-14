/**
 * Built-in workflow step types — factory functions for common CassiCore operations.
 *
 * Available step types:
 *   toolStep           — execute a CassiCore tool by name
 *   constellationStep  — spawn a Constellation project and wait for results
 *   helixStep          — spawn a standalone Helix session and wait for results
 *   helixBranch        — spawn a Helix branch within a Constellation workflow
 *   agentStep          — delegate to an LLM with a prompt (future)
 *
 * All step types are workflow-agnostic: they return WorkflowStep instances
 * that the builder and engine consume without special handling.
 */

import type { WorkflowStep, StepContext, RetryPolicy } from '../../types/workflow.js'

// Service interfaces (injected at runtime, not imported directly)

// WHY: Built-in steps accept service interfaces rather than importing concrete
// classes. This keeps the workflow module decoupled from core/ internals and
// allows tests to inject mocks without pulling in the full daemon boot chain.

/** Minimal interface for executing tools programmatically. */
export interface IToolExecutor {
  execute(
    call: { name: string; arguments: Record<string, unknown> },
    sessionId: string,
    opts?: { workingDir?: string },
  ): Promise<{ content: unknown; isError?: boolean }>
}

/** Minimal interface for starting Constellation projects. */
export interface IConstellationOrchestrator {
  project(opts: {
    goal: string
    context?: string
    template?: string
    sessionId: string
  }): Promise<ConstellationResult>
}

/** Result from a Constellation project. */
export interface ConstellationResult {
  sessionId: string
  status: string
  branches?: Array<{
    helixId: string
    sessionId: string
    status: string
    conclusion?: string
    filesModified?: string[]
    durationMs?: number
  }>
  synthesis?: string
  conclusion?: string
  filesModified?: string[]
  durationMs?: number
}

/** Minimal interface for creating and running Helix sessions. */
export interface IHelixRunner {
  run(config: {
    goal: string
    context?: string
    mode?: string
    sessionId?: string
    parentSessionId?: string
    maxIterations?: number
    toolAccess?: string
    timeoutMs?: number
  }): Promise<HelixResult>
}

/** Result from a Helix session. */
export interface HelixResult {
  conclusion: string
  confidence: number
  filesModified: string[]
  synthesis?: string
  durationMs: number
  findings?: Array<{ type: string; content: string }>
}

// Step: toolStep

export interface ToolStepOptions {
  /** Unique step id. */
  id: string
  /** Description for traces. */
  description?: string
  /** Tool name to execute. */
  tool: string
  /**
   * Tool arguments. Can be:
   *   - A static object
   *   - A function that builds args from the step input
   */
  args: Record<string, unknown> | ((input: unknown) => Record<string, unknown> | Promise<Record<string, unknown>>)
  /** Session id for tool execution (default: use workflow runId). */
  sessionId?: string
  /** Retry policy. */
  retry?: RetryPolicy
  /** Timeout in ms. */
  timeoutMs?: number
  /** The ToolExecutor instance. */
  executor: IToolExecutor
}

/**
 * Create a step that executes a CassiCore tool.
 *
 * Example:
 *   toolStep({
 *     id: 'search-code',
 *     tool: 'grep',
 *     args: { pattern: 'handleError', path: 'src/' },
 *     executor: toolExecutor,
 *   })
 */
export function toolStep(opts: ToolStepOptions): WorkflowStep {
  return {
    id: opts.id,
    description: opts.description ?? `Execute tool: ${opts.tool}`,
    retry: opts.retry,
    timeoutMs: opts.timeoutMs,
    execute: async (ctx: StepContext) => {
      const args = typeof opts.args === 'function'
        ? await opts.args(ctx.input)
        : opts.args

      ctx.logger.debug('Executing tool', { tool: opts.tool, args })

      const result = await opts.executor.execute(
        { name: opts.tool, arguments: args },
        opts.sessionId ?? ctx.runId,
      )

      if (result.isError) {
        throw new Error(`Tool "${opts.tool}" failed: ${JSON.stringify(result.content)}`)
      }

      return result.content
    },
  }
}

// Step: constellationStep

export interface ConstellationStepOptions {
  /** Unique step id. */
  id: string
  /** Description for traces. */
  description?: string
  /**
   * Goal for the Constellation. Can be:
   *   - A static string
   *   - A function that builds the goal from the step input
   */
  goal: string | ((input: unknown) => string | Promise<string>)
  /**
   * Context for the Constellation. Can be:
   *   - A static string
   *   - A function that builds context from the step input
   */
  context?: string | ((input: unknown) => string | Promise<string>)
  /** Constellation template. */
  template?: 'standard' | 'research' | 'implementation' | 'review' | 'minimal'
  /** Retry policy. */
  retry?: RetryPolicy
  /** Timeout in ms (default: 10 minutes). */
  timeoutMs?: number
  /** The ConstellationOrchestrator instance. */
  orchestrator: IConstellationOrchestrator
}

/**
 * Create a step that spawns a Constellation project and waits for results.
 *
 * Example:
 *   constellationStep({
 *     id: 'implement-feature',
 *     goal: 'Add rate limiting to the API',
 *     template: 'implementation',
 *     orchestrator: constellationOrchestrator,
 *   })
 */
export function constellationStep(opts: ConstellationStepOptions): WorkflowStep<unknown, ConstellationResult> {
  return {
    id: opts.id,
    description: opts.description ?? `Constellation: ${typeof opts.goal === 'string' ? opts.goal.slice(0, 60) : '(dynamic)'}`,
    retry: opts.retry,
    timeoutMs: opts.timeoutMs ?? 600_000,
    execute: async (ctx: StepContext) => {
      const goal = typeof opts.goal === 'function'
        ? await opts.goal(ctx.input)
        : opts.goal

      const context = opts.context
        ? (typeof opts.context === 'function' ? await opts.context(ctx.input) : opts.context)
        : undefined

      ctx.logger.info('Starting Constellation project', { goal: goal.slice(0, 100), template: opts.template })

      const result = await opts.orchestrator.project({
        goal,
        context,
        template: opts.template ?? 'standard',
        sessionId: ctx.runId,
      })

      ctx.logger.info('Constellation completed', {
        status: result.status,
        branches: result.branches?.length ?? 0,
        filesModified: result.filesModified?.length ?? 0,
        durationMs: result.durationMs,
      })

      return result
    },
  }
}

// Step: helixStep

export interface HelixStepOptions {
  /** Unique step id. */
  id: string
  /** Description for traces. */
  description?: string
  /**
   * Goal for the Helix session. Can be:
   *   - A static string
   *   - A function that builds the goal from the step input
   */
  goal: string | ((input: unknown) => string | Promise<string>)
  /**
   * Context for the session. Can be:
   *   - A static string
   *   - A function that builds context from the step input
   */
  context?: string | ((input: unknown) => string | Promise<string>)
  /** Helix mode (default: 'adaptive'). */
  mode?: 'dialectic' | 'pipeline' | 'adaptive'
  /** Max iterations (default: 5). */
  maxIterations?: number
  /** Tool access level (default: 'read-write'). */
  toolAccess?: 'read-only' | 'read-write' | 'none'
  /** Retry policy. */
  retry?: RetryPolicy
  /** Timeout in ms (default: 5 minutes). */
  timeoutMs?: number
  /** The Helix runner instance. */
  runner: IHelixRunner
}

/**
 * Create a step that spawns a Helix session and waits for results.
 *
 * Example:
 *   helixStep({
 *     id: 'review-code',
 *     goal: 'Review the auth module for security issues',
 *     mode: 'dialectic',
 *     runner: helixRunner,
 *   })
 */
export function helixStep(opts: HelixStepOptions): WorkflowStep<unknown, HelixResult> {
  return {
    id: opts.id,
    description: opts.description ?? `Helix: ${typeof opts.goal === 'string' ? opts.goal.slice(0, 60) : '(dynamic)'}`,
    retry: opts.retry,
    timeoutMs: opts.timeoutMs ?? 300_000,
    execute: async (ctx: StepContext) => {
      const goal = typeof opts.goal === 'function'
        ? await opts.goal(ctx.input)
        : opts.goal

      const context = opts.context
        ? (typeof opts.context === 'function' ? await opts.context(ctx.input) : opts.context)
        : undefined

      ctx.logger.info('Starting Helix session', {
        goal: goal.slice(0, 100),
        mode: opts.mode ?? 'adaptive',
      })

      const result = await opts.runner.run({
        goal,
        context,
        mode: opts.mode ?? 'adaptive',
        parentSessionId: ctx.runId,
        maxIterations: opts.maxIterations ?? 5,
        toolAccess: opts.toolAccess ?? 'read-write',
        timeoutMs: opts.timeoutMs ?? 300_000,
      })

      ctx.logger.info('Helix completed', {
        confidence: result.confidence,
        filesModified: result.filesModified.length,
        durationMs: result.durationMs,
      })

      return result
    },
  }
}

// Step: helixBranch (for intra-Constellation coordination)

export interface HelixBranchOptions {
  /** Unique step id. */
  id: string
  /** Description for traces. */
  description?: string
  /**
   * Goal for this branch. Can be:
   *   - A static string
   *   - A function that builds the goal from the previous branch's output
   */
  goal: string | ((input: unknown) => string | Promise<string>)
  /**
   * Context for this branch. Can be:
   *   - A static string
   *   - A function that builds context from the previous branch's output
   */
  context?: string | ((input: unknown) => string | Promise<string>)
  /** Branch template (default: 'standard'). */
  template?: 'standard' | 'research' | 'implementation' | 'review' | 'minimal'
  /** Retry policy. */
  retry?: RetryPolicy
  /** Timeout in ms (default: 10 minutes). */
  timeoutMs?: number
  /** The Helix runner instance. */
  runner: IHelixRunner
}

/**
 * Create a step that spawns a Helix branch within a Constellation workflow.
 *
 * Unlike helixStep, helixBranch is designed for use inside Constellation
 * workflows where branches have typed data flowing between them:
 *
 * Example:
 *   const constellationWorkflow = createWorkflow({ id: 'feature-pipeline' })
 *     .then(helixBranch({
 *       id: 'design',
 *       goal: 'Design the API surface',
 *       template: 'research',
 *       runner: helixRunner,
 *     }))
 *     .parallel([
 *       helixBranch({
 *         id: 'implement-core',
 *         goal: (prev) => `Implement based on: ${(prev as any).conclusion}`,
 *         template: 'implementation',
 *         runner: helixRunner,
 *       }),
 *       helixBranch({
 *         id: 'implement-tests',
 *         goal: 'Write test scaffolding',
 *         template: 'implementation',
 *         runner: helixRunner,
 *       }),
 *     ])
 *     .then(helixBranch({
 *       id: 'review',
 *       goal: 'Review all changes for correctness',
 *       template: 'review',
 *       runner: helixRunner,
 *     }))
 *     .commit()
 */
export function helixBranch(opts: HelixBranchOptions): WorkflowStep<unknown, HelixResult> {
  return {
    id: opts.id,
    description: opts.description ?? `Branch: ${typeof opts.goal === 'string' ? opts.goal.slice(0, 60) : '(dynamic)'}`,
    retry: opts.retry,
    timeoutMs: opts.timeoutMs ?? 600_000,
    execute: async (ctx: StepContext) => {
      const goal = typeof opts.goal === 'function'
        ? await opts.goal(ctx.input)
        : opts.goal

      // HOW: Build branch context from the previous step's output plus any
      // explicit context. This enables typed data flow between branches.
      let context = ''
      if (opts.context) {
        context = typeof opts.context === 'function'
          ? await opts.context(ctx.input)
          : opts.context
      }

      // Append previous branch output as context if available
      if (ctx.input && typeof ctx.input === 'object') {
        const prev = ctx.input as Record<string, unknown>
        if (prev.conclusion || prev.synthesis || prev.findings) {
          const parts: string[] = []
          if (prev.conclusion) parts.push(`Previous conclusion: ${prev.conclusion}`)
          if (prev.synthesis) parts.push(`Previous synthesis: ${prev.synthesis}`)
          if (prev.filesModified) parts.push(`Files modified: ${JSON.stringify(prev.filesModified)}`)
          context = context ? `${context}\n\n${parts.join('\n')}` : parts.join('\n')
        }
      }

      ctx.logger.info('Starting Helix branch', {
        branchId: opts.id,
        goal: goal.slice(0, 100),
        template: opts.template ?? 'standard',
      })

      const result = await opts.runner.run({
        goal,
        context: context || undefined,
        mode: opts.template === 'research' ? 'dialectic' : 'pipeline',
        parentSessionId: ctx.runId,
        maxIterations: 5,
        toolAccess: opts.template === 'review' ? 'read-only' : 'read-write',
        timeoutMs: opts.timeoutMs ?? 600_000,
      })

      // Accumulate modified files in workflow state for later reference
      if (result.filesModified.length > 0) {
        const existing = (ctx.state.allFilesModified as string[]) ?? []
        ctx.setState({
          allFilesModified: [...new Set([...existing, ...result.filesModified])],
        })
      }

      ctx.logger.info('Helix branch completed', {
        branchId: opts.id,
        confidence: result.confidence,
        filesModified: result.filesModified.length,
        durationMs: result.durationMs,
      })

      return result
    },
  }
}


// Step: corpusDirectiveStep — Send a directive to a Helix branch through the Corpus

/**
 * Minimal interface for the Corpus directive sender.
 *
 * WHY: Same decoupling pattern as IHelixRunner and IToolExecutor —
 * strategy workflows accept service interfaces rather than importing
 * the Corpus class, keeping workflows testable with mocks.
 */
export interface ICorpusDirectiveSender {
  sendDirective(directive: {
    targetHelixId: string
    type: string
    urgency: string
    reason: string
    text: string
    fromPattern?: string
    maxIterationsRemaining?: number
    requiredAction?: string
  }): Promise<void>
}

export interface CorpusDirectiveStepOptions {
  /** Unique step id. */
  id: string
  /** Description for traces. */
  description?: string
  /** Target Helix id — static or derived from input. */
  targetHelixId: string | ((input: unknown) => string)
  /** Directive type (e.g., 'redirect', 'throttle', 'context-inject'). */
  directiveType: string
  /** Urgency level. */
  urgency: string
  /** Directive text — static or derived from input. */
  text: string | ((input: unknown) => string)
  /** Reason for the directive. */
  reason?: string | ((input: unknown) => string)
  /** Source pattern type (for audit). */
  fromPattern?: string
  /** Max iterations to allow (for throttle directives). */
  maxIterationsRemaining?: number
  /** Required action (for enforcement directives). */
  requiredAction?: 'narrow_scope' | 'switch_strategy' | 'conclude' | 'produce_output'
  /** Retry policy. */
  retry?: RetryPolicy
  /** Timeout in ms (default: 30s). */
  timeoutMs?: number
  /** The directive sender instance. */
  sender: ICorpusDirectiveSender
}

/**
 * Create a step that sends a directive from the Corpus to a Helix branch.
 *
 * WHY: Conflict resolution and other strategies need to steer branches.
 * This step wraps the directive-sending mechanism so it can be composed
 * into strategy workflows alongside helix/tool steps.
 */
export function corpusDirectiveStep(opts: CorpusDirectiveStepOptions): WorkflowStep<unknown, void> {
  return {
    id: opts.id,
    description: opts.description ?? `Directive: ${opts.directiveType} → ${typeof opts.targetHelixId === 'string' ? opts.targetHelixId : '(dynamic)'}`,
    retry: opts.retry,
    timeoutMs: opts.timeoutMs ?? 30_000,
    execute: async (ctx: StepContext) => {
      const targetHelixId = typeof opts.targetHelixId === 'function'
        ? opts.targetHelixId(ctx.input)
        : opts.targetHelixId

      const text = typeof opts.text === 'function'
        ? opts.text(ctx.input)
        : opts.text

      const reason = opts.reason
        ? (typeof opts.reason === 'function' ? opts.reason(ctx.input) : opts.reason)
        : `Strategy step: ${opts.id}`

      ctx.logger.info('Sending Corpus directive', {
        targetHelixId,
        type: opts.directiveType,
        urgency: opts.urgency,
      })

      await opts.sender.sendDirective({
        targetHelixId,
        type: opts.directiveType,
        urgency: opts.urgency,
        reason,
        text,
        fromPattern: opts.fromPattern,
        maxIterationsRemaining: opts.maxIterationsRemaining,
        requiredAction: opts.requiredAction,
      })

      ctx.logger.info('Directive sent', { targetHelixId, type: opts.directiveType })
    },
  }
}


// Step: corpusAssessStep — Read Corpus tree state and produce an assessment

/**
 * Minimal interface for reading Corpus state.
 *
 * WHY: Strategy workflows need to inspect the Corpus tree and processed
 * state without importing the full Corpus class. This thin read interface
 * enables mocking in tests.
 */
export interface ICorpusStateReader {
  getProcessedState(): {
    branchAssessments: Map<string, { status: string; rollingScore: number; filesModified: Set<string> }>
    crossPatterns: Array<{ type: string; helixIds: string[]; severity: string; description: string }>
    budgets: Map<string, { consumedSteps: number; maxSteps: number }>
  }
  getTree(): {
    getBranch(helixId: string): { helixId: string; goal: string; steps: unknown[]; status: string } | undefined
    getAllBranches(): Array<{ helixId: string; goal: string; status: string }>
  }
}

export interface CorpusAssessStepOptions<T = unknown> {
  /** Unique step id. */
  id: string
  /** Description for traces. */
  description?: string
  /**
   * Assessment function — reads state and produces a typed result.
   * The result is passed as input to the next step in the workflow.
   */
  assess: (reader: ICorpusStateReader, input: unknown) => Promise<T> | T
  /** Retry policy. */
  retry?: RetryPolicy
  /** Timeout in ms (default: 10s). */
  timeoutMs?: number
  /** The state reader instance. */
  reader: ICorpusStateReader
}

/**
 * Create a step that reads Corpus state and produces an assessment.
 *
 * WHY: Strategies need to inspect the current Corpus state (branch health,
 * patterns, budgets) before deciding on interventions. This step provides
 * a clean read-only access point that produces typed results for downstream
 * steps.
 */
export function corpusAssessStep<T = unknown>(opts: CorpusAssessStepOptions<T>): WorkflowStep<unknown, T> {
  return {
    id: opts.id,
    description: opts.description ?? `Assess: ${opts.id}`,
    retry: opts.retry,
    timeoutMs: opts.timeoutMs ?? 10_000,
    execute: async (ctx: StepContext) => {
      ctx.logger.info('Running Corpus assessment', { stepId: opts.id })

      const result = await opts.assess(opts.reader, ctx.input)

      ctx.logger.info('Assessment complete', { stepId: opts.id })

      return result
    },
  }
}
