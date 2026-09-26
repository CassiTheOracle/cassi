export { CrossSessionTopicIndex, DEFAULT_CROSS_SESSION_CONFIG } from './cross-session-index.js'
export type {
  CrossSessionTopicEntry,
  CrossSessionIndexConfig,
  FileConflict,
  CrossSessionQueryOpts,
} from './cross-session-index.js'

export { ThalamusAttentionSession, contextCandidateUnitId } from './attention/index.js'
export type {
  AttentionAuthority,
  AttentionKind,
  AttentionObservation,
  AttentionState,
  AttentionStatus,
  ContextCandidate,
  ContextFrame,
  ContextPlan,
  ContextPlanReceipt,
  ContextSourceStatus,
  FieldAdvisory,
  PlannedAttentionItem,
  ThalamusAttentionConfig,
  ThalamusMode,
} from './attention/index.js'
