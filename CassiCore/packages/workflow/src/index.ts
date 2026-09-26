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
export { createWorkflow, createStep, WorkflowBuilder, createStateMachine, StateMachineBuilder, _resetNodeCounter } from './builder.js'
export { WorkflowStore } from './persistence.js'
export { WorkflowDefinitionStore } from './definition-store.js'
export { WorkflowRegistry } from './registry.js'
export { WorkflowScheduler } from './scheduler.js'
export type { WorkflowSchedulerConfig } from './scheduler.js'
export { WorkflowTriggerStore } from './trigger-store.js'
export {
  createHelixRunnerAdapter,
  createConstellationAdapter,
  createToolExecutorAdapter,
} from './adapters.js'
export { WorkflowEventBus } from './events.js'
export type { WorkflowEvent, EventHandler } from './events.js'
export { StateMachineExecutor } from './state-machine.js'
export type { StateMachineResult, StateMachineExecutorConfig } from './state-machine.js'
export {
  toolStep,
  constellationStep,
  helixStep,
  helixBranch,
  corpusDirectiveStep,
  corpusAssessStep,
} from './steps.js'
export {
  codeReviewPipeline,
  researchPipeline,
  featureImplementation,
  scheduledCleanup,
  eventReactorChain,
  batchEdit,
} from './templates.js'
export type {
  CodeReviewPipelineOptions,
  ResearchPipelineOptions,
  FeatureImplementationOptions,
  ScheduledCleanupOptions,
  EventReactorChainOptions,
  BatchEditOptions,
} from './templates.js'
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
  ICorpusDirectiveSender,
  CorpusDirectiveStepOptions,
  ICorpusStateReader,
  CorpusAssessStepOptions,
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
  ListenNode,
  StateMachineNode,
  StateDefinition,
  TransitionDefinition,
  TransitionGuard,
  TransitionAction,
  StoredWorkflowDefinition,
  SerializedNodeGraph,
  SerializedNode,
  IWorkflowDefinitionStore,
  IWorkflowRegistry,
  IWorkflowStore,
  WorkflowTrigger,
  IntervalTrigger,
  CronTrigger,
  EventTrigger,
  OnceTrigger,
  TriggerKind,
  TriggerState,
  IWorkflowTriggerStore,
  WorkflowListener,
  ISuspendSignal,
} from '@cassicore/foundation'
