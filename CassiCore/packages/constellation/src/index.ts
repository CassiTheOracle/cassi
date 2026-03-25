/**
 * Constellation — Self-organizing, recursively composable multi-agent system.
 *
 * Phase 1 exports: types, FlexPosture system, and templates.
 * Later phases add: pipeline, orchestrator, spawning, blackboard bridges, drone integration.
 */

// ── Types ──────────────────────────────────────────────────────────────────

export type {
  FlexPosture,
  ToolAccessLevel,
  WorkStreamMode,
  ConstellationTemplate,
  ConstellationHelixConfig,
  ConstellationNode,
  ConstellationNodeStatus,
  ConstellationPostureResult,
  SpawnRequest,
  SpawnRequestStatus,
  ConstellationResult,
  ConstellationProjectOpts,
  BlackboardBridgeConfig,
  ConstellationEventType,
} from './types.js'

export {
  constellationSessionId,
  helixSessionId,
  postureSessionId,
} from './types.js'


// ── FlexPosture System ─────────────────────────────────────────────────────

export {
  validatePosture,
  validatePostureSet,
  applyDefaults,
  composeConstellationPrompt,
  resolveSlotName,
  createPosture,
  createPostureSet,
} from './flex-posture.js'

export type { PostureValidationResult } from './flex-posture.js'


// ── Templates ──────────────────────────────────────────────────────────────

export {
  getTemplatePostures,
  listTemplates,
  describeTemplate,
  resolvePostures,
} from './templates.js'
