/**
 * Agent Workflow System — public API.
 *
 * Usage:
 *   import { createWorkflow, createStep, WorkflowEngine } from './core/workflow/index.js'
 *
 *   const step1 = createStep({ id: 'greet', execute: async (ctx) => `Hello ${ctx.input}` })
 *   const step2 = createStep({ id: 'upper', execute: async (ctx) => String(ctx.input).toUpperCase() })
 *
 *   const wf = createWorkflow({ id: 'greeting-pipeline' })
 *     .then(step1)
 *     .then(step2)
 *     .commit()
 *
 *   const engine = new WorkflowEngine({ logger, eventBus })
 *   const run = await engine.execute(wf, 'World')
 *   // run.output === 'HELLO WORLD'
 */

export { WorkflowEngine, SuspendSignal } from './engine.js'
export { createWorkflow, createStep, WorkflowBuilder, _resetNodeCounter } from './builder.js'
export { WorkflowStore } from './persistence.js'
export {
  toolStep,
  constellationStep,
  helixStep,
  helixBranch,
} from './steps.js'
export type {
  IToolExecutor,
  IConstellationOrchestrator,
  ConstellationResult,
  IHelixRunner,
  HelixResult,
  ToolStepOptions,
  ConstellationStepOptions,
  HelixStepOptions,
  HelixBranchOptions,
} from './steps.js'
export type {
  WorkflowStep,
  WorkflowDefinition,
  WorkflowNode,
  WorkflowRun,
  WorkflowState,
  WorkflowRunStatus,
  StepContext,
  StepTrace,
  RetryPolicy,
  WorkflowEngineConfig,
  WorkflowNodeKind,
  StepNode,
  ParallelNode,
  BranchNode,
  ForeachNode,
  DoUntilNode,
  DoWhileNode,
  SubworkflowNode,
  IWorkflowRegistry,
  IWorkflowStore,
  WorkflowListener,
  ISuspendSignal,
} from '../../types/workflow.js'
