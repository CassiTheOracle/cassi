/**
 * @cassicore/tools — retained mind-tool DEFINITIONS (P3 spine schema surface).
 *
 * Consolidates the individual retained mind-tool `ToolDefinition` objects so the
 * P3 spine (dev-dep on @cassicore/tools) can rebuild faithful `pi.registerTool`
 * parameter schemas from the real retained definitions (plan §4.2; DELEGATE-SURFACE
 * §1). These are the SAME definition objects `registerCoreTools` / `registerMindTools`
 * register — no behavior change, just a stable export surface for the spine.
 *
 * `list_tools` and the DELEGATE coding tools are intentionally absent (ohmypi owns
 * the coding slice).
 */

export { collectThoughtsDefinition } from './collect-thoughts.js'
export { graphDiscoverDefinition } from './graph-discover.js'
export { coordinateDefinition, checkPeersDefinition } from './peer-coordination.js'
export { listSubagentsDefinition } from './list-subagents.js'
export { getSubagentStatusDefinition } from './get-subagent-status.js'
export { getSubagentResultDefinition } from './get-subagent-result.js'
export { systemHealthDefinition } from './system-health.js'
export { debugSessionDefinition } from './debug-session.js'
export { universalSearchDefinition } from './universal-search.js'
export { cassandraQueryEventsDef } from './cassandra-event.js'
export { cassandraContextInspectDef } from './context-window-tools.js'
export { queryEventsDefinition } from './query-events.js'
