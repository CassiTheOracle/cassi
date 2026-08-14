/**
 * FluxTeam Blackboard Components (Phase 2 - Pending Removal)
 *
 * REMOVED: FluxTeamOrchestrator, FluxCell, TopologyEngine, Topology,
 * GenomeRegistry, TaskAnalyzer, SkillRouter, OutcomeLedger, Conditions
 * are all deleted. All orchestration now uses Helix and Constellation.
 *
 * Remaining components (Blackboard ecosystem):
 *   - **Blackboard**: Enhanced shared workspace with channels
 *   - **GlobalBlackboardRegistry**: Named global blackboard management
 *   - **Blackboard Tools**: Plan and report tools for postures
 *
 * NOTE: Blackboard is deprecated per docs/design/constellation-enhancements-roadmap.md.
 * Migration to GlobalWorkspace + HelixSynapse is pending (Phase 2).
 *
 * @module flux-team
 */

// Blackboard core
export { Blackboard } from './blackboard.js'

// Blackboard tools (used by Helix postures)
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

// Global blackboard registry (used by multiple modules)
export { GlobalBlackboardRegistry } from './global-blackboard-registry.js'
export type { GlobalBlackboardEntry } from './global-blackboard-registry.js'

// REMOVED exports (deprecated - deleted):
// - FluxTeamOrchestrator, createFluxTeamOrchestrator, FluxTeamOrchestratorConfig
// - FluxCell, createFluxCell, FluxCellConfig
// - TopologyEngine, createTopologyEngine, TopologyExecutionOptions, TopologyExecutionResult
// - TOPOLOGY_TEMPLATES, getTopology, getAvailableTemplates, validateTopology
// - ConditionEvaluator, createConditionEvaluator, ConditionContext
// - GENOME_TEMPLATES, createGenome, GenomeRegistry
// - TaskAnalyzer, SkillRouter, FluxRoutingResult
// - OutcomeLedger, OutcomeLedgerStats