/**
 * Self-Model Annotation Logic
 * 
 * Stateless, iterative annotation workflow for Self-Model engrams.
 * Each call finds the next unannotated engram needing an LLM summary.
 * 
 * The tool uses only Self-Model Field data (no external GitNexus queries).
 * Relationships are discovered via neighbor queries and metadata.
 */

import type { SelfModelField } from './self-model-field.js'
import type { Engram, EngramType } from '../types.js'
import type { ModuleMetadata, CapabilityMetadata } from './types.js'

// Type priority for annotation order
const TYPE_PRIORITY: Record<string, number> = {
  module: 1,
  capability: 2,
  weakness: 3,
  pattern: 4,
  principle: 4,
  evolution: 4,
}

const TARGET_TYPES: EngramType[] = ['module', 'capability', 'pattern', 'principle', 'weakness', 'evolution']

/**
 * Candidate engram for annotation, with enriched context.
 */
export interface AnnotationCandidate {
  id: string
  nodeType: EngramType
  name: string
  currentDescription: string
  metadata: Record<string, unknown>
  tags: string[]
  potentiation: number
  /** Modules this depends_on (for modules) */
  dependencies?: string[]
  /** Modules this enables (for capabilities/modules) */
  enables?: string[]
  /** Capabilities referencing this module */
  relatedCapabilities?: string[]
  /** Module severity (for weaknesses) */
  severity?: string
  /** Modules affected (for weaknesses) */
  affectedModules?: string[]
}

/**
 * Response from the annotation tool.
 */
export interface AnnotationResponse {
  status: 'pending' | 'stored' | 'skipped' | 'complete' | 'error'
  instruction: string
  engram?: AnnotationCandidate
  progress?: { remaining: number; total: number }
  previousAction?: { engramId: string; action: 'annotated' | 'skipped' }
  complete?: { message: string }
  error?: string
}

/**
 * Find the next unannotated engram in the Self-Model Field.
 * Returns null if all target types have been reviewed.
 */
export function findNextUnannotated(smf: SelfModelField): AnnotationCandidate | null {
  const all = smf.list(undefined, 10000)
  
  // Filter to target types without llm_summary
  const unannotated = all
    .filter(e => TARGET_TYPES.includes(e.nodeType))
    .filter(e => {
      const summary = e.metadata?.llm_summary
      return summary === undefined || summary === null || summary === ''
    })
    .sort((a, b) => {
      const pa = TYPE_PRIORITY[a.nodeType] ?? 4
      const pb = TYPE_PRIORITY[b.nodeType] ?? 4
      // Priority by type, then by potentiation (higher = more important)
      return pa !== pb ? pa - pb : b.potentiation - a.potentiation
    })
  
  const next = unannotated[0]
  return next ? buildAnnotationContext(smf, next) : null
}

/**
 * Build enriched context for an annotation candidate.
 * Gathers relationship info from Self-Model Field queries.
 */
export function buildAnnotationContext(smf: SelfModelField, engram: Engram): AnnotationCandidate {
  // Parse "Name — Description" format (standard Self-Model content pattern)
  const parts = engram.content.split(' — ')
  const name = parts[0] ?? engram.content.slice(0, 50)
  const currentDescription = parts.slice(1).join(' — ') ?? ''
  
  // Query neighbors for relationships
  const neighbors = smf.getField().neighbors(engram.id)
  
  // Extract depends_on relationships (sourceId = this, targetId = dependency)
  const dependencies = neighbors.synapses
    .filter(s => s.edgeType === 'depends_on' && s.sourceId === engram.id)
    .map(s => {
      const target = neighbors.engrams.find(e => e.id === s.targetId)
      return target?.content.split(' — ')[0]
    })
    .filter((n): n is string => n !== undefined)
  
  // Extract enables relationships (what this module enables)
  const enables = neighbors.synapses
    .filter(s => s.edgeType === 'enables' && s.sourceId === engram.id)
    .map(s => {
      const target = neighbors.engrams.find(e => e.id === s.targetId)
      return target?.content.split(' — ')[0]
    })
    .filter((n): n is string => n !== undefined)
  
  // For modules, find capabilities that reference this cluster
  let relatedCapabilities: string[] | undefined
  if (engram.nodeType === 'module') {
    const meta = engram.metadata as unknown as ModuleMetadata | undefined
    const cluster = meta?.cluster
    if (cluster) {
      relatedCapabilities = smf.list('capability', 100)
        .filter(c => {
          const capMeta = c.metadata as unknown as CapabilityMetadata | undefined
          const implBy = capMeta?.implementedBy ?? []
          return implBy.some(i => i === cluster)
        })
        .map(c => c.content.split(' — ')[0])
    }
  }
  
  // For weaknesses, extract severity and affected modules
  let severity: string | undefined
  let affectedModules: string[] | undefined
  if (engram.nodeType === 'weakness') {
    const meta = engram.metadata as unknown as WeaknessAnnotationMetadata
    severity = meta?.severity
    affectedModules = meta?.affectedModules
  }
  
  return {
    id: engram.id,
    nodeType: engram.nodeType,
    name,
    currentDescription,
    metadata: engram.metadata,
    tags: engram.tags,
    potentiation: engram.potentiation,
    dependencies: dependencies.length > 0 ? dependencies : undefined,
    enables: enables.length > 0 ? enables : undefined,
    relatedCapabilities: relatedCapabilities && relatedCapabilities.length > 0 ? relatedCapabilities : undefined,
    severity,
    affectedModules,
  }
}

interface WeaknessAnnotationMetadata {
  severity?: string
  affectedModules?: string[]
}

/**
 * Store an LLM-generated summary in the engram's metadata.
 */
export function annotateEngram(smf: SelfModelField, id: string, summary: string): void {
  const current = smf.get(id)
  if (!current) {
    throw new Error(`Engram ${id} not found`)
  }
  
  const updatedMetadata = { ...current.metadata, llm_summary: summary }
  smf.update(id, { metadata: updatedMetadata })
}

/**
 * Mark an engram as reviewed without adding a summary.
 * Sets llm_summary to empty string to indicate intentional skip.
 */
export function skipEngram(smf: SelfModelField, id: string): void {
  const current = smf.get(id)
  if (!current) {
    throw new Error(`Engram ${id} not found`)
  }
  
  const updatedMetadata = { ...current.metadata, llm_summary: '' }
  smf.update(id, { metadata: updatedMetadata })
}

/**
 * Count unannotated and total engrams for progress reporting.
 */
export function countUnannotated(smf: SelfModelField): { remaining: number; total: number } {
  const all = smf.list(undefined, 10000)
  const target = all.filter(e => TARGET_TYPES.includes(e.nodeType))
  const unannotated = target.filter(e => {
    const summary = e.metadata?.llm_summary
    return summary === undefined || summary === null || summary === ''
  })
  
  return {
    remaining: unannotated.length,
    total: target.length,
  }
}

/**
 * Build human-readable instruction for annotating an engram.
 */
export function buildInstruction(engram: AnnotationCandidate): string {
  const typeInstructions: Record<string, string> = {
    module: 'Describe what this architectural component does, its role in the system, and key relationships. Focus on purpose and behavior rather than structure.',
    capability: 'Explain what execution flow this represents, what triggers it, and what outcomes it produces.',
    weakness: 'Describe the architectural concern, its impact on the system, and potential mitigation approaches.',
    pattern: 'Explain this recurring design pattern, when it appears in the codebase, and why it matters architecturally.',
    principle: 'State this architectural principle clearly and explain its rationale and implications.',
    evolution: 'Describe what changed, why it changed, and what architectural lessons were learned.',
  }
  
  const base = typeInstructions[engram.nodeType] ?? 'Provide a semantic summary of this engram.'
  
  return [
    `Provide a semantic summary (2-4 sentences) for this ${engram.nodeType}.`,
    base,
    '',
    `Call back with { engramId: "${engram.id}", summary: "..." } to store your annotation.`,
    `Or call with { engramId: "${engram.id}", skip: true } to skip this one.`,
    '',
    'Your summary will be stored in metadata.llm_summary for improved semantic retrieval.',
  ].join('\n')
}