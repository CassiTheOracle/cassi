/**
 * FluxTeam — Next-generation dynamic multi-agent team architecture.
 *
 * Replaces the rigid TriadCell (Proposer→Critic→Executor) pipeline with
 * Lumen-centric execution, graph-based topologies, and learning-driven routing.
 *
 * Core components:
 *   - **FluxTeamOrchestrator**: Top-level team lifecycle management
 *   - **FluxCell**: Atomic execution unit (topology + blackboard + Lumen)
 *   - **TopologyEngine**: Graph traversal executor with conditional transitions
 *   - **Blackboard**: Enhanced shared workspace with channels and reactive subscriptions
 *   - **GenomeRegistry**: Configurable agent blueprints with Lumen posture directives
 *   - **TaskAnalyzer**: Heuristic task signature analysis
 *   - **SkillRouter**: Capability-aware genome/topology selection
 *   - **OutcomeLedger**: SQLite-backed learning store for routing optimization
 *
 * @module flux-team
 */

export {
  FluxTeamOrchestrator,
  createFluxTeamOrchestrator,
} from './flux-team-orchestrator.js'
export type { FluxTeamOrchestratorConfig } from './flux-team-orchestrator.js'

export { FluxCell, createFluxCell } from './flux-cell.js'
export type { FluxCellConfig } from './flux-cell.js'

export { TopologyEngine, createTopologyEngine } from './topology-engine.js'
export type {
  TopologyExecutionOptions,
  TopologyExecutionResult,
} from './topology-engine.js'

export {
  TOPOLOGY_TEMPLATES,
  getTopology,
  getAvailableTemplates,
  validateTopology,
} from './topology.js'

export { ConditionEvaluator, createConditionEvaluator } from './conditions.js'
export type { ConditionContext } from './conditions.js'

export { Blackboard } from './blackboard.js'
export {
  handleBlackboardToolCall,
  isBlackboardMetaTool,
  getBlackboardToolSchemas,
  getPlanToolSchemas,
  isPlanMetaTool,
  BLACKBOARD_TOOL_NAMES,
  PLAN_META_TOOL_NAMES,
  REPORT_TOOL_NAMES,
  REPORT_TOOLS,
  ALL_POSTURES_PLAN_TOOLS,
  EXECUTIVE_PLAN_TOOLS,
} from './blackboard-tools.js'

export { GENOME_TEMPLATES, createGenome } from './genome.js'
export { GenomeRegistry } from './genome-registry.js'

export { TaskAnalyzer } from './task-analyzer.js'
export { SkillRouter } from './skill-router.js'
export type { FluxRoutingResult } from './skill-router.js'

export { OutcomeLedger } from './outcome-ledger.js'
export type { OutcomeLedgerStats } from './outcome-ledger.js'

export { GlobalBlackboardRegistry } from './global-blackboard-registry.js'
export type { GlobalBlackboardEntry } from './global-blackboard-registry.js'
