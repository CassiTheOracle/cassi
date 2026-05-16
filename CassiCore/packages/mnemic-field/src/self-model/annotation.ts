/**
 * Self-Model Annotation Logic
 *
 * Stateless, iterative annotation workflow for Self-Model engrams.
 * Each call finds the next unannotated engram needing an LLM summary.
 *
 * The tool enriches each engram with contextual data — metrics, relationships,
 * cluster neighborhood, connectivity hints, and annotated neighbor examples —
 * so the annotator can write accurate, informative summaries without
 * needing to cross-reference external tools.
 *
 * Relationships are discovered via neighbor queries and metadata only
 * (no external GitNexus calls during annotation).
 */

import type { SelfModelField } from './self-model-field.js'
import type { Engram, EngramType, MnemicSynapse } from '../types.js'
import type { ModuleMetadata, CapabilityMetadata } from './types.js'

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
 * Parsed metrics extracted from a self-model engram's content string.
 */
export interface EngramMetrics {
  /** Number of code symbols in this cluster */
  symbolCount: number
  /** Cohesion percentage (0-100) */
  cohesion: number
  /** Complexity score from GitNexus */
  complexityScore: number
  /** Maturity level from metadata (experimental, developing, stable) */
  maturity: string
}

/**
 * A grouped relationship view showing both directions of a synapse type.
 */
export interface RelationshipGroup {
  edgeType: string
  /** What this engram depends on / enables / references (outgoing) */
  outbound: string[]
  /** What depends on / is enabled by / references this engram (incoming) */
  inbound: string[]
}

/**
 * Candidate engram for annotation, with enriched context.
 */
export interface AnnotationCandidate {
  id: string
  nodeType: EngramType
  name: string
  currentDescription: string

  /** Full raw content string for reference (contains execution flows, etc.) */
  rawContent?: string

  /** Parsed execution flows from the content string */
  executionFlows?: string[]

  /** Parsed metrics (symbol count, cohesion, maturity, etc.) */
  metrics?: EngramMetrics

  metadata: Record<string, unknown>
  tags: string[]
  potentiation: number
  /** Provenance / timeline */
  provenance?: string
  createdAt?: string
  lastSyncedAt?: string

  /** Domain classification (from metadata — e.g. cognition, workflow, training) */
  domain?: string

  /** Modules this depends_on (outgoing depends_on) */
  dependencies?: string[]
  /** Modules that depend on this (incoming depends_on) */
  dependedBy?: string[]

  /** Modules this enables (outgoing enables) */
  enables?: string[]

  /** Capabilities referencing this module's cluster */
  relatedCapabilities?: string[]

  /** Domain siblings — other modules in the same domain */
  domainSiblings?: string[]

  /** Full relationship summary across all synapse types */
  allRelationships?: RelationshipGroup[]

  /** Weakness-specific fields */
  severity?: string
  affectedModules?: string[]

  /**
   * Quick connectivity classification:
   * - isolated: 0 deps, 0 dependents
   * - leaf: deps but no dependents (consumer, not depended on)
   * - hub: many dependents (foundational module)
   * - critical: both high deps AND high dependents
   */
  connectivityHint?: string

  /** Examples of already-annotated neighbors for annotation quality calibration */
  annotatedNeighbors?: { name: string; summary: string }[]
}

export interface AnnotationResponse {
  status: 'pending' | 'stored' | 'skipped' | 'complete' | 'error'
  instruction: string
  engram?: AnnotationCandidate
  progress?: { remaining: number; total: number }
  previousAction?: { engramId: string; action: 'annotated' | 'skipped' }
  complete?: { message: string }
  error?: string
}


interface WeaknessAnnotationMetadata {
  severity?: string
  affectedModules?: string[]
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
      return summary === undefined || summary === null
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
 * Find an unannotated engram matching a name pattern.
 * Returns null if no match found or already annotated.
 */
export function findByName(smf: SelfModelField, namePattern: string): AnnotationCandidate | null {
  const all = smf.list(undefined, 10000)

  const match = all
    .filter(e => TARGET_TYPES.includes(e.nodeType))
    .filter(e => {
      const summary = e.metadata?.llm_summary
      return summary === undefined || summary === null
    })
    .find(e => e.content.toLowerCase().includes(namePattern.toLowerCase()))

  return match ? buildAnnotationContext(smf, match) : null
}

/**
 * Build enriched context for an annotation candidate.
 *
 * Gathers relationship info, metrics, cluster neighborhood, and
 * annotation examples from the Self-Model Field — giving the
 * annotator everything needed for an informed summary.
 */
export function buildAnnotationContext(smf: SelfModelField, engram: Engram): AnnotationCandidate {
  const parts = engram.content.split(' — ')
  const name = parts[0] ?? engram.content.slice(0, 50)
  const descParts = parts.slice(1).join(' — ') ?? ''

  // Split description from execution flows
  const { description, executionFlows } = parseDescriptionAndFlows(descParts)
  const metrics = parseMetrics(description)

  const neighbors = smf.getField().neighbors(engram.id)

  // Build grouped relationships from all synapse types
  const allRelationships = buildRelationshipGroups(engram, neighbors)

  // Extract specific relationship views
  const dependencies = getOutgoingNames(neighbors, engram.id, 'depends_on')
  const dependedBy = getIncomingNames(neighbors, engram.id, 'depends_on')
  const enables = getOutgoingNames(neighbors, engram.id, 'enables')


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

  // Domain siblings — other modules in the same domain (more useful than
  // cluster groups, which map 1:1 to modules in GitNexus).
  let domainSiblings: string[] | undefined
  const domain = engram.metadata?.domain as string | undefined
  if (domain && domain !== 'other' && domain !== 'unknown') {
    try {
      domainSiblings = smf.list('module', 500)
        .filter(e => {
          if (e.id === engram.id) return false
          const d = e.metadata?.domain as string | undefined
          return d === domain
        })
        .sort((a, b) => (b.metadata?.complexityScore as number ?? 0) - (a.metadata?.complexityScore as number ?? 0))
        .slice(0, 8)
        .map(e => e.content.split(' — ')[0])
      if (domainSiblings.length === 0) domainSiblings = undefined
    } catch {
      // Graceful fallback
    }
  }

  // Annotation examples from annotated neighbors
  const annotatedNeighbors = neighbors.engrams
    .filter(e => {
      const summary = e.metadata?.llm_summary
      return typeof summary === 'string' && summary.trim().length > 0
    })
    .map(e => ({
      name: e.content.split(' — ')[0],
      summary: (e.metadata!.llm_summary as string).slice(0, 200),
    }))
    .slice(0, 3)

  // Connectivity hint
  const connectivityHint = classifyConnectivity(
    dependencies.length,
    dependedBy.length,
    allRelationships.length,
  )

  // Metadata-derived values
  const lastSyncedAt = engram.metadata?.lastSyncedAt as string | undefined

  // Resolve metrics: use content-parsed values as base, but override maturity
  // with metadata as it's more authoritative (content string can be stale).
  const metaMaturity = engram.metadata?.maturity as string | undefined
  const metaComplexity = engram.metadata?.complexityScore as number | undefined

  let resolvedMetrics: EngramMetrics | undefined
  if (metrics) {
    resolvedMetrics = {
      ...metrics,
      maturity: metaMaturity ?? metrics.maturity,
    }
  } else if (metaComplexity !== undefined) {
    resolvedMetrics = {
      symbolCount: metaComplexity,
      cohesion: 0,
      complexityScore: metaComplexity,
      maturity: metaMaturity ?? 'unknown',
    }
  }

  return {
    id: engram.id,
    nodeType: engram.nodeType,
    name,
    currentDescription: description || descParts,
    rawContent: engram.content,
    executionFlows: executionFlows.length > 0 ? executionFlows : undefined,
    metrics: resolvedMetrics,
    metadata: engram.metadata,
    tags: engram.tags,
    potentiation: engram.potentiation,
    provenance: engram.provenance !== 'self-model' ? engram.provenance : undefined,
    createdAt: engram.createdAt,
    lastSyncedAt,
    domain: (engram.metadata?.domain as string) ?? undefined,
    dependencies: dependencies.length > 0 ? dependencies : undefined,
    dependedBy: dependedBy.length > 0 ? dependedBy : undefined,
    enables: enables.length > 0 ? enables : undefined,
    relatedCapabilities: relatedCapabilities && relatedCapabilities.length > 0 ? relatedCapabilities : undefined,
    domainSiblings,
    allRelationships: allRelationships.length > 0 ? allRelationships : undefined,
    severity,
    affectedModules,
    connectivityHint,
    annotatedNeighbors: annotatedNeighbors.length > 0 ? annotatedNeighbors : undefined,
  }
}


/**
 * Extract execution flows from the description portion of an engram's content.
 * Format: "... Execution flows: A → B; C → D"
 */
function extractExecutionFlows(text: string): string[] {
  const flowMatch = text.match(/Execution flows:\s*(.+)$/)
  if (!flowMatch) return []
  return flowMatch[1]
    .split(/[;,]/)
    .map(s => s.trim())
    .filter(s => s.length > 0 && s.includes('→'))
}

/**
 * Split description text into the main description and any execution flows.
 */
function parseDescriptionAndFlows(text: string): { description: string; executionFlows: string[] } {
  const flowSep = text.indexOf('Execution flows:')
  if (flowSep === -1) return { description: text.trim(), executionFlows: [] }

  const description = text.slice(0, flowSep).trim()
  const flows = extractExecutionFlows(text)
  return { description, executionFlows: flows }
}

/**
 * Parse metric annotations from a description string.
 * Format: "(N symbols, XX% cohesion, maturity)" or "(N symbols, XX% cohesion)"
 * Falls back to individual captures for resilience.
 */
function parseMetrics(text: string): EngramMetrics | null {
  // Try full format: (N symbols, XX% cohesion, maturity)
  const fullMatch = text.match(/\((\d+)\s*symbols?,\s*(\d+)%\s*cohesion,\s*(\w+)\)/)
  if (fullMatch) {
    return {
      symbolCount: parseInt(fullMatch[1], 10),
      cohesion: parseInt(fullMatch[2], 10),
      complexityScore: parseInt(fullMatch[1], 10), // symbol count as proxy
      maturity: fullMatch[3],
    }
  }
  return null
}


/**
 * Build grouped relationship lists across ALL synapse types for the engram.
 * Shows every edge type present in both incoming and outgoing directions.
 */
function buildRelationshipGroups(
  engram: Engram,
  neighbors: { engrams: Engram[]; synapses: MnemicSynapse[] },
): RelationshipGroup[] {
  const groups = new Map<string, { outbound: string[]; inbound: string[] }>()

  for (const synapse of neighbors.synapses) {
    if (!groups.has(synapse.edgeType)) {
      groups.set(synapse.edgeType, { outbound: [], inbound: [] })
    }
    const group = groups.get(synapse.edgeType)!

    const targetEngram = neighbors.engrams.find(e => e.id === synapse.targetId)
    const sourceEngram = neighbors.engrams.find(e => e.id === synapse.sourceId)

    if (synapse.sourceId === engram.id && targetEngram) {
      group.outbound.push(targetEngram.content.split(' — ')[0])
    } else if (synapse.targetId === engram.id && sourceEngram) {
      group.inbound.push(sourceEngram.content.split(' — ')[0])
    }
  }

  // Convert to sorted array, deduplicate names within each direction
  return Array.from(groups.entries())
    .map(([edgeType, g]) => ({
      edgeType,
      outbound: [...new Set(g.outbound)],
      inbound: [...new Set(g.inbound)],
    }))
    .filter(g => g.outbound.length > 0 || g.inbound.length > 0)
    .sort((a, b) => (a.outbound.length + a.inbound.length) - (b.outbound.length + b.inbound.length))
}

/** Get names of engrams this one depends on (outgoing depends_on) */
function getOutgoingNames(
  neighbors: { engrams: Engram[]; synapses: MnemicSynapse[] },
  engramId: string,
  edgeType: string,
): string[] {
  return neighbors.synapses
    .filter(s => s.edgeType === edgeType && s.sourceId === engramId)
    .map(s => {
      const target = neighbors.engrams.find(e => e.id === s.targetId)
      return target?.content.split(' — ')[0]
    })
    .filter((n): n is string => n !== undefined)
}

/** Get names of engrams that depend on this one (incoming depends_on) */
function getIncomingNames(
  neighbors: { engrams: Engram[]; synapses: MnemicSynapse[] },
  engramId: string,
  edgeType: string,
): string[] {
  return neighbors.synapses
    .filter(s => s.edgeType === edgeType && s.targetId === engramId)
    .map(s => {
      const source = neighbors.engrams.find(e => e.id === s.sourceId)
      return source?.content.split(' — ')[0]
    })
    .filter((n): n is string => n !== undefined)
}


/**
 * Classify a module's connectivity role in the dependency graph.
 */
function classifyConnectivity(
  depCount: number,       // what it depends on
  dependedCount: number,  // what depends on it
  totalRelCount: number,  // total relationship count across all types
): string {
  if (depCount === 0 && dependedCount === 0 && totalRelCount <= 1) return 'isolated'
  if (dependedCount >= 3) {
    return dependedCount >= 5
      ? `critical (${dependedCount} dependents, ${depCount} deps)`
      : `hub (${dependedCount} dependents)`
  }
  if (depCount > 0 && dependedCount > 0) return `bridge (${depCount} deps, ${dependedCount} dependents)`
  if (depCount > 0 && dependedCount === 0) return `leaf consumer (${depCount} deps, no dependents)`
  if (depCount === 0 && dependedCount > 0) return `foundation (${dependedCount} dependents, no deps)`
  return 'connected'
}


/**
 * Store an LLM-generated summary in the engram's metadata.
 */
export async function annotateEngram(smf: SelfModelField, id: string, summary: string): Promise<void> {
  const current = smf.get(id)
  if (!current) {
    throw new Error(`Engram ${id} not found`)
  }

  const updatedMetadata = { ...current.metadata, llm_summary: summary }
  await smf.update(id, { metadata: updatedMetadata })
}

/**
 * Mark an engram as reviewed without adding a summary.
 * Sets llm_summary to empty string to indicate intentional skip.
 */
export async function skipEngram(smf: SelfModelField, id: string): Promise<void> {
  const current = smf.get(id)
  if (!current) {
    throw new Error(`Engram ${id} not found`)
  }

  const updatedMetadata = { ...current.metadata, llm_summary: '' }
  await smf.update(id, { metadata: updatedMetadata })
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
 * Build a context-rich instruction for annotating an engram.
 * The instruction is tailored to the engram's type and available data,
 * guiding the annotator toward the most useful style of summary.
 */
export function buildInstruction(engram: AnnotationCandidate): string {
  const lines: string[] = []

  const guidance = getTypeGuidance(engram)
  lines.push(`## Annotate: ${engram.name}`)
  lines.push(`**Type:** ${engram.nodeType}`)
  lines.push('')
  lines.push(guidance)

  if (engram.metrics) {
    const m = engram.metrics
    lines.push('')
    lines.push('**Module profile:**')
    lines.push(`- Symbols: ${m.symbolCount} | Cohesion: ${m.cohesion}% | Maturity: ${m.maturity}`)
  }

  if (engram.connectivityHint) {
    lines.push(`- Role: ${engram.connectivityHint}`)
  }

  if (engram.executionFlows && engram.executionFlows.length > 0) {
    lines.push('')
    lines.push('**Execution flows passing through this engram:**')
    for (const flow of engram.executionFlows) {
      lines.push(`- ${flow}`)
    }
  }

  if (engram.dependencies && engram.dependencies.length > 0) {
    lines.push('')
    lines.push(`**Depends on:** ${engram.dependencies.join(', ')}`)
  }
  if (engram.dependedBy && engram.dependedBy.length > 0) {
    lines.push(`**Depended by:** ${engram.dependedBy.join(', ')}`)
  }
  if (engram.enables && engram.enables.length > 0) {
    lines.push(`**Enables:** ${engram.enables.join(', ')}`)
  }
  if (engram.relatedCapabilities && engram.relatedCapabilities.length > 0) {
    lines.push(`**Used by capabilities:** ${engram.relatedCapabilities.join(', ')}`)
  }
  if (engram.domainSiblings && engram.domainSiblings.length > 0) {
    lines.push(`**Sibling modules (${engram.domain} domain):** ${engram.domainSiblings.join(', ')}`)
  }

  if (engram.annotatedNeighbors && engram.annotatedNeighbors.length > 0) {
    lines.push('')
    lines.push('**Annotation examples from neighbors:**')
    for (const n of engram.annotatedNeighbors) {
      lines.push(`- ${n.name}: "${n.summary}"`)
    }
  }

  if (engram.nodeType === 'weakness') {
    if (engram.severity) lines.push(`**Severity:** ${engram.severity}`)
    if (engram.affectedModules && engram.affectedModules.length > 0) {
      lines.push(`**Affected modules:** ${engram.affectedModules.join(', ')}`)
    }
  }

  if (engram.createdAt) {
    const created = new Date(engram.createdAt).toISOString().slice(0, 10)
    lines.push('')
    lines.push(`**Created:** ${created}`)
  }
  if (engram.provenance) {
    lines.push(`**Source:** ${engram.provenance}`)
  }
  if (engram.lastSyncedAt) {
    const synced = new Date(engram.lastSyncedAt).toISOString().slice(0, 10)
    lines.push(`**Last synced:** ${synced}`)
  }

  if (engram.potentiation > 0.5) {
    lines.push(`**Potentiation:** ${(engram.potentiation * 100).toFixed(0)}% (highly active)`)
  } else if (engram.potentiation > 0.1) {
    lines.push(`**Potentiation:** ${(engram.potentiation * 100).toFixed(0)}%`)
  }

  lines.push('')
  lines.push('---')
  lines.push('Write a 2-4 sentence semantic summary of what this engram represents, its purpose, and its architectural role.')
  lines.push('')
  lines.push(`Call back with { engramId: "${engram.id}", summary: "..." } to store your annotation.`)
  lines.push(`Or call with { engramId: "${engram.id}", skip: true } to skip.`)
  lines.push('')
  lines.push('Your summary is stored in metadata.llm_summary for improved semantic retrieval.')

  return lines.join('\n')
}

/**
 * Get type-specific annotation guidance.
 */
function getTypeGuidance(engram: AnnotationCandidate): string {
  const name = engram.name
  const baseGuidance: Record<string, string> = {
    module:
      `Describe what the **${name}** module does architecturally — its responsibilities, ` +
      `the subsystems it touches, and why it exists as a distinct cluster. ` +
      `Focus on purpose and behavior: what concerns does it manage? What abstractions does it provide?`,
    capability:
      `Describe the **${name}** execution flow — what triggers it, what steps it coordinates, ` +
      `and what outcomes it produces. Focus on the user-visible or system-visible behavior ` +
      `rather than implementation details.`,
    weakness:
      `Describe the **${name}** architectural concern — what the weakness is, ` +
      `why it matters, what parts of the system it affects, and how it might be addressed. ` +
      `Be specific about the cost and potential mitigation strategies.`,
    pattern:
      `Explain the **${name}** design pattern — when and where it appears in the codebase, ` +
      `what problem it solves, and why it matters architecturally.`,
    principle:
      `State the **${name}** architectural principle clearly. Explain its rationale and ` +
      `its implications for how the system is built and evolved.`,
    evolution:
      `Describe the **${name}** change — what was modified, why, and what architectural ` +
      `lessons were learned from the change.`,
  }

  return baseGuidance[engram.nodeType] ?? 'Provide a semantic summary of this engram.'
}
