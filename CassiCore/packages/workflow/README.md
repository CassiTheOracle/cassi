# @cassicore/workflow

Agent workflow system extracted from CassiCore's `core/workflow/`. History-preserved
import splice. Types (`WorkflowDefinition`, `WorkflowRun`, `WorkflowStep`, …) come
from `@cassicore/foundation` `types/workflow.ts`.

## Surface (barrel `index.ts`)

- `WorkflowEngine`, `SuspendSignal` (`engine.ts`)
- `createWorkflow`, `createStep`, `WorkflowBuilder`, `createStateMachine`,
  `StateMachineBuilder` (`builder.ts`)
- `WorkflowStore`, `WorkflowDefinitionStore`, `WorkflowRegistry`, `WorkflowScheduler`,
  `WorkflowTriggerStore`, `WorkflowEventBus`, `StateMachineExecutor`
- Steps: `toolStep`, `constellationStep`, `helixStep`, `helixBranch`,
  `corpusDirectiveStep`, `corpusAssessStep` (`steps.ts`)
- Templates: `featureImplementation`, `researchPipeline`, `codeReviewPipeline`,
  `scheduledCleanup`, `eventReactorChain`, `batchEdit` (`templates.ts`)
- Adapters: `createHelixRunnerAdapter`, `createConstellationAdapter`,
  `createToolExecutorAdapter` (`adapters.ts`)

Uses `better-sqlite3` for persistence/definition-store/trigger-store.
