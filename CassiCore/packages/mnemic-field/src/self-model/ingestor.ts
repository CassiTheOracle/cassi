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
  modulesUpdated: number
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
  /** Update existing modules with enriched descriptions from symbols + processes */
  updateExisting?: boolean
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
    const updateExisting = options?.updateExisting ?? false

    this.logger.info('Starting Self-Model ingestion from GitNexus')

    const communities = this.queryCommunities(minSize)
    this.logger.info('Loaded communities', { count: communities.length })

    const processes = this.queryProcesses()
    this.logger.info('Loaded processes', { count: processes.length })

    const symbolsByCommunity = this.querySymbolsByCommunity()
    this.logger.info('Loaded symbols for enrichment', { communityCount: symbolsByCommunity.size })

    const processMap = this.buildProcessMap(processes)

    const { created: modulesCreated, updated: modulesUpdated } = this.ingestModules(
      communities, symbolsByCommunity, processMap, updateExisting,
    )
    const capabilitiesCreated = this.ingestCapabilities(processes)
    const dependencySynapsesCreated = this.ingestDependencies(communities)
    const weaknessesCreated = this.ingestWeaknesses(weaknessThreshold)
    const portalsCreated = this.createPortals(communities)

    const durationMs = Date.now() - start
    this.logger.info('Self-Model ingestion complete', {
      modulesCreated,
      modulesUpdated,
      capabilitiesCreated,
      weaknessesCreated,
      dependencySynapsesCreated,
      portalsCreated,
      durationMs,
    })

    return {
      modulesCreated,
      modulesUpdated,
      capabilitiesCreated,
      weaknessesCreated,
      dependencySynapsesCreated,
      portalsCreated,
      durationMs,
    }
  }

  /**
   * Ingest GitNexus communities as module engrams with rich semantic descriptions.
   *
   * Each module gets a description built from its domain, key symbol names,
   * and the execution flows that pass through it — making the FTS5 index
   * rich enough for conceptual queries like "what handles task delegation?".
   */
  private ingestModules(
    communities: CommunityRow[],
    symbolsByCommunity: Map<string, string[]>,
    processMap: Map<string, string[]>,
    updateExisting: boolean,
  ): { created: number; updated: number } {
    let created = 0
    let updated = 0

    const existingByCommId = new Map<string, { id: string }>()
    for (const mod of this.smf.list('module', 10000)) {
      const commTag = mod.tags.find(t => t.startsWith('community:'))
      if (commTag) {
        existingByCommId.set(commTag.replace('community:', ''), { id: mod.id })
      }
    }

    for (const comm of communities) {
      const domain = this.inferDomain(comm.label)
      const maturity = this.inferMaturity(comm.cohesion, comm.symbolCount)
      const symbolNames = symbolsByCommunity.get(comm.id) ?? []
      const processLabels = processMap.get(comm.id) ?? []
      const richDescription = this.buildRichDescription(comm, domain, maturity, symbolNames, processLabels)

      const existing = existingByCommId.get(comm.id)

      if (existing) {
        if (updateExisting) {
          this.smf.update(existing.id, { content: `${comm.label} — ${richDescription}` })
          updated++
        }
        continue
      }

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
        richDescription,
        metadata,
        { tags: [`community:${comm.id}`] },
      )
      created++
    }

    return { created, updated }
  }

  /**
   * Ingest GitNexus processes (execution flows) as capability engrams.
   */
  private ingestCapabilities(processes: ProcessRow[]): number {
    let created = 0

    const existingByProcId = new Set<string>()
    for (const cap of this.smf.list('capability', 10000)) {
      const procTag = cap.tags.find(t => t.startsWith('process:'))
      if (procTag) existingByProcId.add(procTag.replace('process:', ''))
    }

    for (const proc of processes) {
      if (existingByProcId.has(proc.id)) continue

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
    const modules = this.smf.list('module', 10000)
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

    const existingByPath = new Set<string>()
    for (const w of this.smf.list('weakness', 10000)) {
      const tag = w.tags.find(t => t.startsWith('hotspot:'))
      if (tag) existingByPath.add(tag.replace('hotspot:', ''))
    }

    for (const hotspot of hotspots) {
      if (hotspot.score < threshold) continue
      if (existingByPath.has(hotspot.filePath)) continue

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

      const module = this.smf.list('module', 10000).find(e =>
        e.tags.includes(`community:${comm.id}`)
      )
      if (module) {
        this.bridge.connectToPortal(concept, module.id, 'self-model')
      }

      created++
    }

    return created
  }

  /**
   * Batch-query all symbol names grouped by community.
   * Returns a map of communityId → symbol names for enriching module descriptions.
   */
  private querySymbolsByCommunity(): Map<string, string[]> {
    try {
      const raw = this.cypher(
        `MATCH (s)-[:CodeRelation {type: 'MEMBER_OF'}]->(c:Community) WHERE c.symbolCount >= 5 RETURN c.id AS commId, s.name AS name ORDER BY c.id`
      )
      const rows = this.parseRows<{ commId: string; name: string }>(raw)
      const map = new Map<string, string[]>()
      for (const row of rows) {
        if (!row.commId || !row.name) continue
        const arr = map.get(row.commId) ?? []
        arr.push(row.name)
        map.set(row.commId, arr)
      }
      this.logger.debug('Symbol enrichment data loaded', {
        communities: map.size,
        totalSymbols: rows.length,
      })
      return map
    } catch (err) {
      this.logger.warn('Failed to query symbols for enrichment', { error: String(err) })
      return new Map()
    }
  }

  /**
   * Build a reverse map from communityId → process labels.
   */
  private buildProcessMap(processes: ProcessRow[]): Map<string, string[]> {
    const map = new Map<string, string[]>()
    for (const proc of processes) {
      if (!Array.isArray(proc.communities)) continue
      for (const rawCommId of proc.communities) {
        const commId = String(rawCommId).replace(/'/g, '').trim()
        if (!commId) continue
        const arr = map.get(commId) ?? []
        arr.push(proc.label)
        map.set(commId, arr)
      }
    }
    return map
  }

  /**
   * Build a rich natural-language description of a module from its structural data.
   *
   * Instead of "Constellation — 67 symbols, cohesion 88%", produces:
   * "Multi-agent orchestration (67 symbols, 88% cohesion, stable). Key functions:
   * getHelixTemplate, evaluateSpawnRequest, detectCrossPatterns. Execution flows:
   * ProcessSingleWorkUnit → ToFloatArray, TriggerResume → TotalStepCount."
   *
   * This makes FTS5 queries like "task delegation" or "spawn decisions"
   * find the relevant modules — the self-model knows what things DO, not just
   * what they're named.
   */
  private buildRichDescription(
    comm: CommunityRow,
    domain: string,
    maturity: string,
    symbolNames: string[],
    processLabels: string[],
  ): string {
    const parts: string[] = []

    parts.push(
      `${this.describeDomain(domain)} (${comm.symbolCount} symbols, ` +
      `${(comm.cohesion * 100).toFixed(0)}% cohesion, ${maturity})`,
    )

    if (symbolNames.length > 0) {
      const topSymbols = symbolNames
        .filter(n => n.length > 3)
        .sort((a, b) => b.length - a.length)
        .slice(0, 12)
      if (topSymbols.length > 0) {
        parts.push(`Key functions: ${topSymbols.join(', ')}`)

        const splitWords = new Set<string>()
        for (const sym of topSymbols) {
          for (const word of sym.replace(/([a-z])([A-Z])/g, '$1 $2').split(/\s+/)) {
            if (word.length > 2) splitWords.add(word.toLowerCase())
          }
        }
        const wordList = Array.from(splitWords).slice(0, 25)
        if (wordList.length > 0) {
          parts.push(`Concepts: ${wordList.join(' ')}`)
        }
      }
    }

    if (processLabels.length > 0) {
      const uniqueFlows = [...new Set(processLabels)].slice(0, 5)
      parts.push(`Execution flows: ${uniqueFlows.join('; ')}`)
    }

    return parts.join('. ')
  }

  private describeDomain(domain: string): string {
    const descriptions: Record<string, string> = {
      orchestration: 'multi-agent orchestration',
      memory: 'memory and knowledge storage',
      retrieval: 'memory retrieval and activation',
      runtime: 'daemon runtime infrastructure',
      cognition: 'cognitive intelligence processing',
      background: 'background and offline processing',
      embeddings: 'embedding generation and management',
      training: 'training data pipeline',
      workflow: 'workflow execution engine',
      tools: 'tool registration and execution',
      testing: 'test infrastructure',
      other: 'supporting infrastructure',
    }
    return descriptions[domain] ?? domain
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
