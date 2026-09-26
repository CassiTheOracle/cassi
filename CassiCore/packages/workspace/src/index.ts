/**
 * @cassicore/workspace — package barrel.
 *
 * Re-exports the global-workspace (GlobalWorkspace, RadianceLoop + helpers) and
 * code-analysis (analyzeDeadCode/analyzeHotspots/ContextFeedbackTracker etc.)
 * sub-barrels. Inbound consumers (constellation, helix) re-point their vendored
 * `workspace/*` stubs here. History-preserved import splice from cassicore's
 * core/intelligence/{workspace,code-analysis}.
 */

export * from './workspace/index.js'
export * from './code-analysis/index.js'
