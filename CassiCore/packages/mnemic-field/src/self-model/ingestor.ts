import { execSync } from 'node:child_process'
import type { ILogger } from '../../../../types/interfaces.js'
import type { SelfModelField } from './self-model-field.js'
import type { InterFieldBridge } from './inter-field-bridge.js'
import type { ModuleMetadata, WeaknessMetadata, CapabilityMetadata } from './types.js'

interface CommunityRow {
  id: string
  label: string
  symbolCount: number
  cohesion: number
}

interface ProcessRow {
  id: string
  label: string
  stepCount: number
  processType: string
  communities: string[]
}

export interface IngestResult {
  modulesCreated: number
  capabilitiesCreated: number
  weaknessesCreated: number
  dependencySynapsesCreated: number
  portalsCreated: number
  durationMs: number
}

export interface IngestOptions {
  repoRoot: string
  /** Skip LLM enrichment (faster, uses heuristic labels only) */
  skipEnrichment?: boolean
  /** Minimum symbol count for a community to be ingested as a module */
  minCommunitySize?: number
  /** Hotspot score threshold above which a module is flagged as a weakness */
  weaknessThreshold?: number
}

const INGEST_DEFAULTS = {
  minCommunitySize: 5,
  weaknessThreshold: 0.6,
} as const

/**
 * Populates the Self-Model Field from the GitNexus knowledge graph.
 *
 * Data flow:
 * 1. Communities → module engrams (the main architectural components)
 * 2. Processes → capability engrams (what the system can do)
 * 3. Cross-file CALLS/IMPORTS → depends_on synapses between modules
 * 4. Hotspot scores → weakness engrams for fragile modules
 * 5. Key concepts → portal pairs (bridge to episodic field)
 *
 * This is a batch operation intended to run on startup or periodically.
 * It's idempotent — re-running updates existing engrams rather than
 * creating duplicates (matched by community/process ID in tags).
 */
export class SelfModelIngestor {
  private smf: SelfModelField
  private bridge: InterFieldBridge | null
  private logger: ILogger
  private repoRoot: string

  constructor(
    selfModelField: SelfModelField,
    logger: ILogger,
    repoRoot: string,
    bridge?: InterFieldBridge,
  ) {
    this.smf = selfModelField
    this.bridge = bridge ?? null
    this.logger = logger.child ? logger.child('self-model-ingestor') : logger
    this.repoRoot = repoRoot
  }

  /**
   * Run a full ingestion cycle: communities → modules, processes → capabilities,
   * cross-file edges → dependency synapses, hotspots → weaknesses.
   */
  async ingest(options?: Partial<IngestOptions>): Promise<IngestResult> {
    const start = Date.now()
    const minSize = options?.minCommunitySize ?? INGEST_DEFAULTS.minCommunitySize
    const weaknessThreshold = options?.weaknessThreshold ?? INGEST_DEFAULTS.weaknessThreshold

    this.logger.info('Starting Self-Model ingestion from GitNexus')

    const communities = this.queryCommunities(minSize)
    this.logger.info('Loaded communities', { count: communities.length })

    const processes = this.queryProcesses()
    this.logger.info('Loaded processes', { count: processes.length })

    const modulesCreated = this.ingestModules(communities)
    const capabilitiesCreated = this.ingestCapabilities(processes)
    const dependencySynapsesCreated = this.ingestDependencies(communities)
    const weaknessesCreated = this.ingestWeaknesses(weaknessThreshold)
    const portalsCreated = this.createPortals(communities)

    const durationMs = Date.now() - start
    this.logger.info('Self-Model ingestion complete', {
      modulesCreated,
      capabilitiesCreated,
      weaknessesCreated,
      dependencySynapsesCreated,
      portalsCreated,
      durationMs,
    })

    return {
      modulesCreated,
      capabilitiesCreated,
      weaknessesCreated,
      dependencySynapsesCreated,
      portalsCreated,
      durationMs,
    }
  }

  /**
   * Ingest GitNexus communities as module engrams.
   */
  private ingestModules(communities: CommunityRow[]): number {
    let created = 0

    for (const comm of communities) {
      const existing = this.smf.list('module').find(e =>
        e.tags.includes(`community:${comm.id}`)
      )
      if (existing) continue

      const domain = this.inferDomain(comm.label)
      const maturity = this.inferMaturity(comm.cohesion, comm.symbolCount)

      const metadata: ModuleMetadata = {
        path: `cluster:${comm.id}`,
        domain,
        maturity,
        cluster: comm.id,
        dependentCount: 0,
        dependencyCount: 0,
        complexityScore: comm.symbolCount,
        lastSyncedAt: new Date().toISOString(),
      }

      this.smf.storeModule(
        comm.label,
        `${comm.label} — ${comm.symbolCount} symbols, cohesion ${(comm.cohesion * 100).toFixed(0)}%`,
        metadata,
        { tags: [`community:${comm.id}`] },
      )
      created++
    }

    return created
  }

  /**
   * Ingest GitNexus processes (execution flows) as capability engrams.
   */
  private ingestCapabilities(processes: ProcessRow[]): number {
    let created = 0

    for (const proc of processes) {
      const existing = this.smf.list('capability').find(e =>
        e.tags.includes(`process:${proc.id}`)
      )
      if (existing) continue

      const metadata: CapabilityMetadata = {
        implementedBy: proc.communities.map(c => c.replace(/'/g, '')),
        active: true,
      }

      this.smf.storeCapability(
        proc.label,
        `Execution flow: ${proc.label} (${proc.stepCount} steps, ${proc.processType})`,
        metadata,
        { tags: [`process:${proc.id}`] },
      )
      created++
    }

    return created
  }

  /**
   * Create depends_on synapses between module engrams based on
   * cross-community CALLS relationships in the GitNexus graph.
   */
  private ingestDependencies(communities: CommunityRow[]): number {
    const crossEdges = this.queryCrossCommunityCalls()
    if (crossEdges.length === 0) return 0

    const moduleByCommId = new Map<string, string>()
    const modules = this.smf.list('module')
    for (const mod of modules) {
      const commTag = mod.tags.find(t => t.startsWith('community:'))
      if (commTag) {
        moduleByCommId.set(commTag.replace('community:', ''), mod.id)
      }
    }

    let created = 0
    const seen = new Set<string>()

    for (const edge of crossEdges) {
      const sourceModId = moduleByCommId.get(edge.sourceCommunity)
      const targetModId = moduleByCommId.get(edge.targetCommunity)
      if (!sourceModId || !targetModId || sourceModId === targetModId) continue

      const key = `${sourceModId}→${targetModId}`
      if (seen.has(key)) continue
      seen.add(key)

      try {
        this.smf.connect(sourceModId, targetModId, 'depends_on', Math.min(1.0, 0.3 + edge.count * 0.05))
        created++
      } catch {
        // synapse may already exist
      }
    }

    return created
  }

  /**
   * Detect and ingest weaknesses from hotspot analysis.
   * Modules with high hotspot scores are fragile and complex.
   */
  private ingestWeaknesses(threshold: number): number {
    const hotspots = this.queryHotspots()
    let created = 0

    for (const hotspot of hotspots) {
      if (hotspot.score < threshold) continue

      const existing = this.smf.list('weakness').find(e =>
        e.tags.includes(`hotspot:${hotspot.filePath}`)
      )
      if (existing) continue

      const severity = hotspot.score >= 0.8 ? 'critical' as const
        : hotspot.score >= 0.7 ? 'high' as const
        : 'medium' as const

      const metadata: WeaknessMetadata = {
        severity,
        affectedModules: [hotspot.filePath],
        mitigated: false,
        discoveredVia: 'analysis',
      }

      this.smf.storeWeakness(
        hotspot.filePath.split('/').pop() ?? hotspot.filePath,
        `High complexity hotspot: ${hotspot.filePath} (score: ${hotspot.score.toFixed(2)}, ${hotspot.lines} lines, ${hotspot.symbols} symbols, ${hotspot.edges} edges)`,
        metadata,
        { tags: [`hotspot:${hotspot.filePath}`] },
      )
      created++
    }

    return created
  }

  /**
   * Create portal pairs for key architectural concepts, bridging
   * the self-model to the episodic field.
   */
  private createPortals(communities: CommunityRow[]): number {
    if (!this.bridge) return 0

    let created = 0
    const topCommunities = communities.slice(0, 15)

    for (const comm of topCommunities) {
      const concept = comm.label.toLowerCase().replace(/[^a-z0-9-]/g, '-')
      const result = this.bridge.createPortalPair(concept)
      if (!result) continue

      const module = this.smf.list('module').find(e =>
        e.tags.includes(`community:${comm.id}`)
      )
      if (module) {
        this.bridge.connectToPortal(concept, module.id, 'self-model')
      }

      created++
    }

    return created
  }

  private queryCommunities(minSize: number): CommunityRow[] {
    try {
      const raw = this.cypher(
        `MATCH (c:Community) WHERE c.symbolCount >= ${minSize} RETURN c.id AS id, c.label AS label, c.symbolCount AS symbolCount, c.cohesion AS cohesion ORDER BY c.symbolCount DESC`
      )
      return this.parseRows<CommunityRow>(raw)
    } catch (err) {
      this.logger.warn('Failed to query communities', { error: String(err) })
      return []
    }
  }

  private queryProcesses(): ProcessRow[] {
    try {
      const raw = this.cypher(
        `MATCH (p:Process) WHERE p.stepCount >= 3 RETURN p.id AS id, p.label AS label, p.stepCount AS stepCount, p.processType AS processType, p.communities AS communities ORDER BY p.stepCount DESC LIMIT 50`
      )
      return this.parseRows<ProcessRow>(raw)
    } catch (err) {
      this.logger.warn('Failed to query processes', { error: String(err) })
      return []
    }
  }

  private queryCrossCommunityCalls(): Array<{ sourceCommunity: string; targetCommunity: string; count: number }> {
    try {
      const raw = this.cypher(
        `MATCH (a)-[r:CodeRelation {type: 'CALLS'}]->(b), (a)-[:CodeRelation {type: 'MEMBER_OF'}]->(ca:Community), (b)-[:CodeRelation {type: 'MEMBER_OF'}]->(cb:Community) WHERE ca.id <> cb.id RETURN ca.id AS src, cb.id AS tgt, count(*) AS cnt ORDER BY cnt DESC LIMIT 200`
      )
      const rows = this.parseRows<{ src: string; tgt: string; cnt: number }>(raw)
      return rows.map(r => ({ sourceCommunity: r.src, targetCommunity: r.tgt, count: r.cnt }))
    } catch (err) {
      this.logger.warn('Failed to query cross-community calls', { error: String(err) })
      return []
    }
  }

  private queryHotspots(): Array<{ filePath: string; score: number; lines: number; symbols: number; edges: number }> {
    try {
      // Identify communities with low cohesion and high symbol count as complexity hotspots
      const raw = this.cypher(
        `MATCH (c:Community) WHERE c.symbolCount >= 20 AND c.cohesion < 0.5 RETURN c.id AS id, c.label AS label, c.symbolCount AS symbols, c.cohesion AS cohesion ORDER BY c.symbolCount DESC LIMIT 30`
      )
      const rows = this.parseRows<{ id: string; label: string; symbols: number; cohesion: number }>(raw)
      return rows.map(r => ({
        filePath: `cluster:${r.id} (${r.label})`,
        score: Math.min(1.0, (r.symbols / 60) * (1 - r.cohesion)),
        lines: 0,
        symbols: r.symbols,
        edges: 0,
      }))
    } catch (err) {
      this.logger.warn('Failed to query hotspots', { error: String(err) })
      return []
    }
  }

  /**
   * Execute a Cypher query against the GitNexus graph via CLI.
   */
  private cypher(query: string): string {
    return execSync(
      `npx gitnexus cypher ${JSON.stringify(query)}`,
      { cwd: this.repoRoot, encoding: 'utf8', timeout: 30_000, stdio: ['ignore', 'pipe', 'pipe'] },
    )
  }

  /**
   * Parse GitNexus JSON output into typed rows.
   * Handles both array and markdown-table formats.
   */
  private parseRows<T>(raw: string): T[] {
    try {
      const parsed = JSON.parse(raw)

      if (Array.isArray(parsed)) return parsed as T[]

      if (parsed.markdown && typeof parsed.markdown === 'string') {
        return this.parseMarkdownTable<T>(parsed.markdown)
      }

      if (parsed.rows && Array.isArray(parsed.rows)) return parsed.rows as T[]

      return []
    } catch {
      return []
    }
  }

  /**
   * Parse a markdown table into objects.
   */
  private parseMarkdownTable<T>(md: string): T[] {
    const lines = md.split('\n').filter(l => l.trim().startsWith('|'))
    if (lines.length < 3) return []

    const headers = lines[0].split('|').map(s => s.trim()).filter(Boolean)
    const rows: T[] = []

    for (let i = 2; i < lines.length; i++) {
      const cells = lines[i].split('|').map(s => s.trim()).filter(Boolean)
      if (cells.length !== headers.length) continue

      const obj: Record<string, unknown> = {}
      for (let j = 0; j < headers.length; j++) {
        const val = cells[j]
        const num = Number(val)
        if (!isNaN(num) && val !== '') {
          obj[headers[j]] = num
        } else if (val.startsWith('[') || val.startsWith('{')) {
          try { obj[headers[j]] = JSON.parse(val) } catch { obj[headers[j]] = val }
        } else {
          obj[headers[j]] = val
        }
      }
      rows.push(obj as T)
    }

    return rows
  }

  private inferDomain(label: string): string {
    const lower = label.toLowerCase()
    if (lower.includes('memory') || lower.includes('mnemic')) return 'memory'
    if (lower.includes('constellation') || lower.includes('helix') || lower.includes('flux') || lower.includes('triad')) return 'orchestration'
    if (lower.includes('cortex') || lower.includes('kindling')) return 'retrieval'
    if (lower.includes('runtime') || lower.includes('daemon')) return 'runtime'
    if (lower.includes('intelligence') || lower.includes('thinker') || lower.includes('synapse')) return 'cognition'
    if (lower.includes('subconscious') || lower.includes('meditation') || lower.includes('pineal')) return 'background'
    if (lower.includes('embedding')) return 'embeddings'
    if (lower.includes('training')) return 'training'
    if (lower.includes('workflow')) return 'workflow'
    if (lower.includes('command') || lower.includes('tool')) return 'tools'
    if (lower.includes('test')) return 'testing'
    return 'other'
  }

  private inferMaturity(cohesion: number, symbolCount: number): ModuleMetadata['maturity'] {
    if (cohesion > 0.9 && symbolCount > 20) return 'foundational'
    if (cohesion > 0.7 && symbolCount > 10) return 'stable'
    if (cohesion > 0.5) return 'developing'
    return 'experimental'
  }
}
