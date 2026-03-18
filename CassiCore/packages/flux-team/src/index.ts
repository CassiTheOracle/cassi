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

// ── Orchestrator ─────────────────────────────────────────────────────────────
export {
  FluxTeamOrchestrator,
  createFluxTeamOrchestrator,
} from './flux-team-orchestrator.js'
export type { FluxTeamOrchestratorConfig } from './flux-team-orchestrator.js'

// ── FluxCell ─────────────────────────────────────────────────────────────────
export { FluxCell, createFluxCell } from './flux-cell.js'
export type { FluxCellConfig } from './flux-cell.js'

// ── Topology Engine ──────────────────────────────────────────────────────────
export { TopologyEngine, createTopologyEngine } from './topology-engine.js'
export type {
  TopologyExecutionOptions,
  TopologyExecutionResult,
} from './topology-engine.js'

// ── Topology Templates ───────────────────────────────────────────────────────
export {
  TOPOLOGY_TEMPLATES,
  getTopology,
  getAvailableTemplates,
  validateTopology,
} from './topology.js'

// ── Conditions ───────────────────────────────────────────────────────────────
export { ConditionEvaluator, createConditionEvaluator } from './conditions.js'
export type { ConditionContext } from './conditions.js'

// ── Blackboard ───────────────────────────────────────────────────────────────
export { Blackboard } from './blackboard.js'

// ── Genome System ────────────────────────────────────────────────────────────
export { GENOME_TEMPLATES, createGenome } from './genome.js'
export { GenomeRegistry } from './genome-registry.js'

// ── Task Analysis + Routing ──────────────────────────────────────────────────
export { TaskAnalyzer } from './task-analyzer.js'
export { SkillRouter } from './skill-router.js'
export type { FluxRoutingResult } from './skill-router.js'

// ── Outcome Ledger ───────────────────────────────────────────────────────────
export { OutcomeLedger } from './outcome-ledger.js'
export type { OutcomeLedgerStats } from './outcome-ledger.js'
