/**
 * VENDOR TYPE STUB — `core/workflow/persistence.ts` (`WorkflowStore`).
 *
 * Type-placeholder for the workflow run persistence surface referenced as an
 * inline `import(...).WorkflowStore` type in registerCoreTools deps. Aliased to
 * foundation's canonical `IWorkflowStore` so the tools' makeWorkflowHandler
 * deps typecheck. Owned by `@cassicore/workflow` (P6); re-pointed there.
 */
import type { IWorkflowStore } from '@cassicore/foundation'

/** Persists and queries workflow runs. */
export type WorkflowStore = IWorkflowStore
