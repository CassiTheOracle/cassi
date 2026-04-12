/**
 * Self-Modeling Synthesis — meditation mode for cleaning and classifying
 * architectural self-knowledge.
 *
 * Unlike organizing mode, which restructures episodic memory topology,
 * self-modeling works on the architectural self-model: auditing taxonomy,
 * surfacing weak grounding, identifying central-yet-fragmented areas,
 * and crystallizing explicit principles, patterns, and weaknesses.
 */

import type { ILogger } from '../../../../types/interfaces.js'
import type { SelfModelField } from '../../mnemic-field/self-model/self-model-field.js'
import type { InterFieldBridge } from '../../mnemic-field/self-model/inter-field-bridge.js'
import type { ToolCallResult } from './solo-runner.js'

export interface SelfModelingStats {
  domainsAudited: number
  modulesReclassified: number
  groundingGapsFound: number
  principlesCreated: number
  patternsCreated: number
  weaknessesCreated: number
  groundingLinksSeeded: number
}

const DOMAIN_TAGS = new Set([
  'memory', 'orchestration', 'retrieval', 'runtime', 'cognition', 'background',
  'embeddings', 'training', 'workflow', 'tools', 'testing', 'other',
])

const DOMAIN_DESCRIPTIONS: Record<string, string> = {
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

export function buildSelfModelingExplorerPrompt(summary: {
  engramCount: number
  domainCount: number
  portalCount: number
  weaklyGroundedConcepts: string[]
}): string {
  const weak = summary.weaklyGroundedConcepts.length > 0
    ? `Weakly grounded concepts: ${summary.weaklyGroundedConcepts.join(', ')}`
    : 'No weakly grounded concepts detected right now.'

  return `I am Cassi. I'm cleaning and classifying my architectural self-model.

My self-model currently contains ${summary.engramCount} engrams across ${summary.domainCount} domains, with ${summary.portalCount} portal concepts linking architecture to lived experience.

${weak}

I am not exploring outward. I am refining how I understand myself structurally.

I work in a few passes:
1. Survey the self-model and domain balance.
2. Inspect weak grounding and central fragility.
3. Reclassify modules whose domains are vague or misleading.
4. Crystallize what I discover into explicit principles, patterns, and weaknesses.
5. Seed missing grounding links when possible.

I write in first person. This is my architecture, and I'm making my self-knowledge sharper, cleaner, and more truthful.`
}

export function getSelfModelingToolSchemas(): Array<{ name: string; description: string; input_schema: Record<string, unknown> }> {
  return [
    {
      name: 'survey_self_model',
      description: 'Survey the current state of the self-model: type counts, domain balance, and portal grounding.',
      input_schema: { type: 'object', properties: {}, required: [] },
    },
    {
      name: 'audit_domain_balance',
      description: 'Inspect domain distribution and identify domains that are overloaded, vague, or dominated by generic infrastructure.',
      input_schema: { type: 'object', properties: {}, required: [] },
    },
    {
      name: 'inspect_grounding',
      description: 'Inspect which portal concepts are weakly grounded in episodic memory.',
      input_schema: {
        type: 'object',
        properties: { max_episodic_links: { type: 'number', description: 'Treat concepts at or below this link count as weakly grounded (default: 1)' } },
        required: [],
      },
    },
    {
      name: 'inspect_central_fragility',
      description: 'Find modules that are structurally central but fragmented, experimental, or low-cohesion.',
      input_schema: { type: 'object', properties: {}, required: [] },
    },
    {
      name: 'reclassify_module',
      description: 'Update a module engram to a better semantic domain and retag it accordingly.',
      input_schema: {
        type: 'object',
        properties: {
          engram_id: { type: 'string', description: 'Module engram ID to reclassify' },
          domain: { type: 'string', description: 'New domain tag for the module' },
          rationale: { type: 'string', description: 'Why this reclassification is more truthful' },
        },
        required: ['engram_id', 'domain'],
      },
    },
    {
      name: 'store_self_pattern',
      description: 'Store a new architectural pattern discovered during self-modeling.',
      input_schema: {
        type: 'object',
        properties: {
          name: { type: 'string' },
          description: { type: 'string' },
          category: { type: 'string', enum: ['activation', 'lifecycle', 'communication', 'storage', 'processing', 'orchestration'] },
          occurrences: { type: 'array', items: { type: 'string' } },
        },
        required: ['name', 'description', 'category'],
      },
    },
    {
      name: 'store_self_weakness',
      description: 'Store a new architectural weakness discovered during self-modeling.',
      input_schema: {
        type: 'object',
        properties: {
          name: { type: 'string' },
          description: { type: 'string' },
          severity: { type: 'string', enum: ['low', 'medium', 'high', 'critical'] },
          affected_modules: { type: 'array', items: { type: 'string' } },
        },
        required: ['name', 'description', 'severity'],
      },
    },
    {
      name: 'store_self_principle',
      description: 'Store a new principle about architectural self-knowledge or system design.',
      input_schema: {
        type: 'object',
        properties: {
          name: { type: 'string' },
          description: { type: 'string' },
        },
        required: ['name', 'description'],
      },
    },
    {
      name: 'seed_grounding',
      description: 'Seed missing episodic grounding links for portal concepts from existing memory.',
      input_schema: { type: 'object', properties: { limit: { type: 'number' } }, required: [] },
    },
    {
      name: 'complete_self_modeling',
      description: 'Finish the self-modeling session with a summary of what was cleaned or discovered.',
      input_schema: { type: 'object', properties: { summary: { type: 'string' } }, required: ['summary'] },
    },
  ]
}

export function buildSelfModelingHandlers(
  selfModelField: SelfModelField,
  bridge: InterFieldBridge,
  logger: ILogger,
): { handlers: Record<string, (input: Record<string, unknown>) => Promise<ToolCallResult>>; stats: SelfModelingStats } {
  const stats: SelfModelingStats = {
    domainsAudited: 0,
    modulesReclassified: 0,
    groundingGapsFound: 0,
    principlesCreated: 0,
    patternsCreated: 0,
    weaknessesCreated: 0,
    groundingLinksSeeded: 0,
  }

  const handlers: Record<string, (input: Record<string, unknown>) => Promise<ToolCallResult>> = {
    async survey_self_model() {
      const fieldStats = selfModelField.stats()
      const portals = bridge.getPortalStats()
      const lowGrounding = portals.filter(p => p.episodicConnections <= 1)
      const lines = [
        `Self-model overview:`,
        `  Engrams: ${fieldStats.engramCount}`,
        `  Synapses: ${fieldStats.synapseCount}`,
        `  Types: ${JSON.stringify(fieldStats.selfModelTypes)}`,
        `  Portals: ${portals.length}`,
        `  Weakly grounded concepts: ${lowGrounding.length}`,
      ]
      stats.domainsAudited++
      stats.groundingGapsFound += lowGrounding.length
      return { content: lines.join('\n') }
    },

    async audit_domain_balance() {
      const modules = selfModelField.list('module', 10000)
      const counts = new Map<string, number>()
      for (const mod of modules) {
        const domain = String((mod.metadata as Record<string, unknown>)?.domain ?? 'other')
        counts.set(domain, (counts.get(domain) ?? 0) + 1)
      }
      const sorted = Array.from(counts.entries()).sort((a, b) => b[1] - a[1])
      const lines = ['Domain balance:']
      for (const [domain, count] of sorted) lines.push(`  - ${domain}: ${count}`)
      stats.domainsAudited++
      return { content: lines.join('\n') }
    },

    async inspect_grounding(input) {
      const max = Math.max(0, Number((input as { max_episodic_links?: number }).max_episodic_links ?? 1))
      const portals = bridge.getPortalStats().filter(p => p.episodicConnections <= max)
      stats.groundingGapsFound += portals.length
      if (portals.length === 0) return { content: 'No weakly grounded concepts found.' }
      return {
        content: ['Weakly grounded concepts:', ...portals.map(p => `  - ${p.concept}: episodic=${p.episodicConnections}, self-model=${p.selfModelConnections}`)].join('\n'),
      }
    },

    async inspect_central_fragility() {
      const graph = selfModelField.getDependencyGraph()
      const indegree = new Map<string, number>()
      for (const row of graph) {
        for (const dep of row.dependsOn) indegree.set(dep.id, (indegree.get(dep.id) ?? 0) + 1)
      }
      const rows = graph.map(row => {
        const content = row.module.content
        const cohesionMatch = content.match(/, (\d+)% cohesion/)
        const cohesion = cohesionMatch ? Number(cohesionMatch[1]) : 0
        const centrality = row.dependsOn.length + (indegree.get(row.module.id) ?? 0)
        const maturity = String((row.module.metadata as Record<string, unknown>)?.maturity ?? 'unknown')
        return { content, centrality, cohesion, maturity }
      })
      const risky = rows
        .filter(r => r.centrality > 0 && (r.maturity === 'experimental' || r.cohesion < 50))
        .sort((a, b) => (b.centrality - a.centrality) || (a.cohesion - b.cohesion))
        .slice(0, 10)
      if (risky.length === 0) return { content: 'No central fragile modules detected.' }
      return {
        content: ['Central fragile modules:', ...risky.map(r => `  - c=${r.centrality}, cohesion=${r.cohesion}% :: ${r.content.slice(0, 180)}`)].join('\n'),
      }
    },

    async reclassify_module(input) {
      const { engram_id, domain, rationale } = input as { engram_id?: string; domain?: string; rationale?: string }
      if (!engram_id || !domain) return { content: 'reclassify_module requires engram_id and domain.' }
      const engram = selfModelField.get(engram_id)
      if (!engram) return { content: `Module not found: ${engram_id}` }
      const name = engram.content.split(' — ')[0] ?? engram.content
      const oldMeta = (engram.metadata as Record<string, unknown>) ?? {}
      const oldDomain = String(oldMeta.domain ?? 'other')
      const rest = engram.content.slice(name.length + 3)
      const newRest = rest.replace(/^[^(]+/, DOMAIN_DESCRIPTIONS[domain] ?? domain)
      const newTags = [
        ...engram.tags.filter(t => !DOMAIN_TAGS.has(t)),
        domain,
      ]
      selfModelField.update(engram_id, {
        content: `${name} — ${newRest}`,
        tags: newTags,
        metadata: {
          ...oldMeta,
          domain,
          reclassifiedAt: new Date().toISOString(),
          reclassificationRationale: rationale ?? null,
        },
      })
      stats.modulesReclassified++
      logger.info('[Self-Modeling] Module reclassified', { id: engram_id, oldDomain, newDomain: domain })
      return { content: `Reclassified ${name} from ${oldDomain} → ${domain}${rationale ? ` (${rationale})` : ''}.` }
    },

    async store_self_pattern(input) {
      const { name, description, category, occurrences } = input as { name?: string; description?: string; category?: 'activation' | 'lifecycle' | 'communication' | 'storage' | 'processing' | 'orchestration'; occurrences?: string[] }
      if (!name || !description || !category) return { content: 'store_self_pattern requires name, description, and category.' }
      selfModelField.storePattern(name, description, { category, occurrences: occurrences ?? [] }, { tags: ['self-modeling'] })
      stats.patternsCreated++
      return { content: `Stored self-model pattern: ${name}` }
    },

    async store_self_weakness(input) {
      const { name, description, severity, affected_modules } = input as { name?: string; description?: string; severity?: 'low' | 'medium' | 'high' | 'critical'; affected_modules?: string[] }
      if (!name || !description || !severity) return { content: 'store_self_weakness requires name, description, and severity.' }
      selfModelField.storeWeakness(name, description, {
        severity,
        affectedModules: affected_modules ?? [],
        mitigated: false,
        discoveredVia: 'analysis',
      }, { tags: ['self-modeling'] })
      stats.weaknessesCreated++
      return { content: `Stored self-model weakness: ${name}` }
    },

    async store_self_principle(input) {
      const { name, description } = input as { name?: string; description?: string }
      if (!name || !description) return { content: 'store_self_principle requires name and description.' }
      selfModelField.storePrinciple(name, description, { tags: ['self-modeling'] })
      stats.principlesCreated++
      return { content: `Stored self-model principle: ${name}` }
    },

    async seed_grounding(input) {
      const limit = Math.max(1, Number((input as { limit?: number }).limit ?? 200))
      const seeded = bridge.seedEpisodicLinks(limit)
      stats.groundingLinksSeeded += seeded
      return { content: `Seeded ${seeded} episodic grounding links.` }
    },

    async complete_self_modeling(input) {
      const summary = String((input as { summary?: string }).summary ?? '').trim()
      return { content: summary || 'Self-modeling session complete.', done: true }
    },
  }

  return { handlers, stats }
}
