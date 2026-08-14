/**
 * WorkflowRegistry — in-memory registry of live workflow definitions.
 *
 * Provides named lookup of WorkflowDefinition objects (with real function
 * references). Can be backed by a WorkflowDefinitionStore for persistence,
 * but the live definitions (with executable steps) must be registered at
 * runtime since functions can't be serialized.
 *
 * Usage:
 *   const registry = new WorkflowRegistry(logger)
 *   registry.register(myWorkflowDef)
 *   const wf = registry.get('my-workflow')
 *   engine.execute(wf, input)
 */

import type { ILogger } from '../../types/interfaces.js'
import type { WorkflowDefinition, IWorkflowRegistry } from '../../types/workflow.js'

export class WorkflowRegistry implements IWorkflowRegistry {
  private readonly definitions = new Map<string, WorkflowDefinition>()
  private readonly logger: ILogger

  constructor(logger: ILogger) {
    this.logger = logger.child('workflow-registry')
  }

  /** Register a workflow definition. Overwrites if the id already exists. */
  register(workflow: WorkflowDefinition): void {
    this.definitions.set(workflow.id, workflow)
    this.logger.debug('Registered workflow', {
      id: workflow.id,
      nodeCount: workflow.nodes.length,
    })
  }

  /** Get a workflow definition by id. */
  get(workflowId: string): WorkflowDefinition | undefined {
    return this.definitions.get(workflowId)
  }

  /** List all registered workflow definitions. */
  list(): WorkflowDefinition[] {
    return [...this.definitions.values()]
  }

  /** Remove a workflow definition by id. Returns true if it existed. */
  remove(workflowId: string): boolean {
    const existed = this.definitions.has(workflowId)
    this.definitions.delete(workflowId)
    if (existed) {
      this.logger.debug('Removed workflow', { id: workflowId })
    }
    return existed
  }

  /** Check if a workflow definition is registered. */
  has(workflowId: string): boolean {
    return this.definitions.has(workflowId)
  }

  /** Get the count of registered definitions. */
  get size(): number {
    return this.definitions.size
  }

  /** Clear all registered definitions. */
  clear(): void {
    this.definitions.clear()
    this.logger.debug('Cleared all workflow definitions')
  }
}
