/**
 * VENDORED TYPE STUB — mirrors `mnemic-field/types.js`. Surface: EngramType,
 * SynapseType (union types derived from the ENGRAM_TYPES / SYNAPSE_TYPES
 * const arrays). Self-contained.
 */

export const ENGRAM_TYPES = [
  'fact', 'episode', 'decision', 'pattern',
  'abstraction', 'goal', 'file', 'tool', 'session', 'outcome',
  'source_file', 'changeset', 'artifact', 'concern', 'anomaly',
  'module', 'capability', 'principle', 'weakness', 'evolution', 'portal',
  'bridge',
  'synthesized_invariant',
  'intent_span',
  'thought_command',
  'replay_segment',
  'expert_summary',
  'file_version',
  'file_read',
  'tool_invocation',
  'message',
  'pineal_facet',
  'error_report',
  'search_finding',
  'code_change',
  'test_result',
  'build_output',
  'spatial_feature',
  'attractor',
  'generation',
  'visual_memory',
] as const

export type EngramType = typeof ENGRAM_TYPES[number]

export const SYNAPSE_TYPES = [
  'similar_to', 'contradicts', 'supports',
  'caused_by', 'led_to', 'used_in_task', 'part_of',
  'temporal_neighbor', 'supersedes', 'about_file', 'spawned_from',
  'imports', 'modified_by', 'co_changed', 'contains_symbol',
  'depends_on', 'implements', 'uses_pattern', 'governed_by',
  'evolved_from', 'enables', 'constrains', 'mitigates', 'portal_link',
  'responds_to',
  'triggered_by',
  'commands',
  'expert_summary',
  'injected_for',
  'contains',
  'created_in',
  'produces',
  'operated_on',
  'vindex_correlation',
  'cross_modal',
  'activated_by',
  'visual_similar',
] as const

export type SynapseType = typeof SYNAPSE_TYPES[number]
