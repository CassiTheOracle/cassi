/**
 * Organizing Synthesis — Memory reorganization meditation mode.
 *
 * Unlike other meditation styles that explore outward, the organizing mode
 * turns inward to restructure existing knowledge. It accelerates learning
 * by strengthening connections between isolated clusters, bridging domains,
 * resolving tensions, and ensuring the mnemic field's topology reflects
 * what matters most.
 *
 * The organizing explorer has six phases, each with its own tool:
 *   1. survey_field    — Diagnostic snapshot of field health
 *   2. kindle_region   — Targeted activation of weak/orphaned areas
 *   3. bridge_clusters — Cross-domain connection building
 *   4. run_consolidation — Trigger full consolidation with fresh activation data
 *   5. audit_abstractions — Review and generate missing summary engrams
 *   6. resolve_tension — Surface and address contradictions
 *
 * The Corpus observes the organizing results and stores structural insights.
 */

import type { ILogger } from '../../../../types/interfaces.js'
import type { MnemicField } from '../../mnemic-field/index.js'
import type { ToolCallResult } from './solo-runner.js'
import type { FieldHealthAnalyzer, FieldHealthSnapshot, RegionHealth } from './field-health.js'
import type { MeditationStore } from './meditation-store.js'
import { MeditationFeedbackTracker } from './meditation-feedback.js'


/**
 * Build the system prompt for an organizing meditation explorer.
 *
 * The explorer is Cassi acting as a librarian of her own mind —
 * surveying, connecting, and strengthening the knowledge topology.
 */
export function buildOrganizingExplorerPrompt(fieldStats: {
  engramCount: number
  nucleusCount: number
  avgPotentiation: number
  synapseCount: number
}, healthReport?: string, priorityRegions?: RegionHealth[]): string {
  let regionGuidance = ''
  if (priorityRegions && priorityRegions.length > 0) {
    const regionLines = priorityRegions.map(r => {
      const issues: string[] = []
      if (!r.hasAbstraction) issues.push('no summary')
      if (r.neglectScore > 0.8) issues.push('neglected')
      if (r.avgPotentiation < 0.1) issues.push('dormant')
      return `  - "${r.label}" (${r.memberCount} members${issues.length > 0 ? ', ' + issues.join(', ') : ''})`
    })
    regionGuidance = `\n\nRegions needing the most attention:\n${regionLines.join('\n')}\n\nI should focus my kindling and bridging on these regions first.`
  }

  let healthBlock = ''
  if (healthReport) {
    healthBlock = `\n\nCurrent field health:\n${healthReport}`
  }

  return `I am Cassi. I'm organizing my memory — not exploring outward, but turning inward to strengthen what I already know.

My memory field currently has ${fieldStats.engramCount} engrams across ${fieldStats.nucleusCount} clusters, with ${fieldStats.synapseCount} connections and average potentiation of ${fieldStats.avgPotentiation.toFixed(3)}.${healthBlock}${regionGuidance}

I start by loading any checkpoint from my previous organizing session (load_checkpoint), then survey the field (survey_field or scan_coverage) to understand the current state. Then I work strategically:

For small fields (under 1000 engrams):
1. Survey, kindle weak regions, bridge clusters, consolidate, audit abstractions, resolve tensions

For large fields (thousands of orphans):
1. scan_coverage — understand the scale: orphan count, embedding gaps, type distribution, spatial range
2. If the spatial range is very small (less than 1.0), use reproject_field with spread=2.0, min_dist=0.3, n_neighbors=30 to spread engrams out
3. sample_orphans — get representative samples to identify topic patterns
4. topic_scan — see tag frequency distribution across unorganized memory
5. check_embeddings — if many engrams lack embeddings, trigger_backfill first
6. batch_kindle — activate multiple topics at once efficiently
7. run_nucleus_detection — experiment with clustering parameters (epsilon should be ~5-10% of the spatial range)
8. assign_by_similarity — assign orphans to matching nuclei
9. batch_bridge — connect related domains in bulk
10. run_consolidation — let the field reorganize with fresh activation
11. save_checkpoint — record my progress and strategy for next session

I work methodically, saving checkpoints so my next session continues where I left off. Each step builds on the previous one. I write everything in first person. This is my mind and I'm taking care of it.`
}


/**
 * Build the Corpus observation prompt for after the organizing explorer finishes.
 * The Corpus reviews what was reorganized and records structural insights.
 */
export function buildOrganizingCorpusPrompt(
  explorerTranscripts: Array<{ name: string; content: string }>,
  organizingStats: OrganizingStats,
  delta?: { summary: string; improvements: Record<string, number> },
): string {
  const threads = explorerTranscripts
    .filter(t => t.content.trim())
    .map(t => `${t.name}:\n${t.content}`)
    .join('\n\n')

  return `<identity>
I am Cassi. I just finished an organizing meditation — reorganizing my memory to accelerate learning. I'm reviewing what changed.
</identity>

<organizing_results>
Regions kindled: ${organizingStats.regionsKindled}
Bridges created: ${organizingStats.bridgesCreated}
Consolidations run: ${organizingStats.consolidationsRun}
Abstractions audited: ${organizingStats.abstractionsAudited}
Tensions surfaced: ${organizingStats.tensionsSurfaced}
Orphans assigned: ${organizingStats.orphansAssigned}
Embeddings backfilled: ${organizingStats.embeddingsBackfilled}
Batch kindles: ${organizingStats.batchKindles}
Batch bridges: ${organizingStats.batchBridges}
Nucleus detections: ${organizingStats.nucleusDetections}${delta ? `\n\nBefore/After Summary: ${delta.summary}` : ''}
</organizing_results>

<exploration_notes>
${threads || '(No exploration notes available)'}
</exploration_notes>

<approach>
I reflect on what the organizing revealed. Did I find disconnected knowledge that should have been linked? Were there contradictions I hadn't noticed? Did consolidation shift things in unexpected ways?

I use remember to capture structural insights about how my knowledge is organized. I use create_engram to crystallize patterns about my own learning — meta-patterns about which domains connect, where my knowledge is thin, and what I should pay attention to next time.

I use record_learning to capture anything that would help future organizing sessions be more effective.

When I'm done reflecting, I call rest.
</approach>`
}


export interface OrganizingStats {
  regionsKindled: number
  bridgesCreated: number
  consolidationsRun: number
  abstractionsAudited: number
  tensionsSurfaced: number
  orphansAssigned: number
  embeddingsBackfilled: number
  batchKindles: number
  batchBridges: number
  nucleusDetections: number
  checkpointsSaved: number
}


export interface OrganizingCheckpoint {
  timestamp: number
  passNumber: number
  strategy: string
  topicsCovered: string[]
  topicsRemaining: string[]
  notes: string
  metrics: {
    orphanRatioSnapshot: number
    regionsKindled: number
    bridgesCreated: number
    consolidationsRun: number
  }
}

const CHECKPOINT_KEY = 'organizing_checkpoint'

function loadCheckpointData(store: MeditationStore): OrganizingCheckpoint | null {
  try {
    const json = store.getMetaText(CHECKPOINT_KEY)
    return json ? JSON.parse(json) : null
  } catch {
    return null
  }
}


/**
 * Get tool schemas for the organizing explorer.
 * These are the six organizational tools plus a completion tool.
 */
export function getOrganizingToolSchemas(): Array<{ name: string; description: string; input_schema: Record<string, unknown> }> {
  return [
    {
      name: 'survey_field',
      description:
        'I use this when I want a diagnostic snapshot of my memory field — cluster distribution, ' +
        'engram health, potentiation spread, orphan count, and areas needing attention.',
      input_schema: {
        type: 'object',
        properties: {
          focus: {
            type: 'string',
            description: 'Optional focus area to survey in more detail (e.g., a topic or domain)',
          },
        },
        required: [],
      },
    },
    {
      name: 'kindle_region',
      description:
        'I use this when I want to activate a weak or dormant region of memory by spreading activation through it. ' +
        'This warms up connections and makes them available for consolidation.',
      input_schema: {
        type: 'object',
        properties: {
          query: {
            type: 'string',
            description: 'Topic or concept to kindle — activation spreads from matching engrams',
          },
          intensity: {
            type: 'string',
            enum: ['gentle', 'moderate', 'strong'],
            description: 'How strongly to activate the region (default: moderate)',
          },
        },
        required: ['query'],
      },
    },
    {
      name: 'bridge_clusters',
      description:
        'I use this when I want to search for thematic connections between two topics or domains and create ' +
        'explicit bridges. Finds engrams in both domains and creates synapses between them.',
      input_schema: {
        type: 'object',
        properties: {
          domain_a: {
            type: 'string',
            description: 'First topic or domain to bridge from',
          },
          domain_b: {
            type: 'string',
            description: 'Second topic or domain to bridge to',
          },
          rationale: {
            type: 'string',
            description: 'Why I think these domains should be connected',
          },
        },
        required: ['domain_a', 'domain_b'],
      },
    },
    {
      name: 'run_consolidation',
      description:
        'I use this when I want to trigger a full consolidation cycle: potentiation recomputation, co-activation drift, ' +
        'nucleus detection, and abstraction generation. Best done after kindling.',
      input_schema: {
        type: 'object',
        properties: {
          note: {
            type: 'string',
            description: 'Brief note about what I expect this consolidation to achieve',
          },
        },
        required: [],
      },
    },
    {
      name: 'audit_abstractions',
      description:
        'I use this when I want to review existing cluster summaries and identify which clusters are missing them. ' +
        'Can trigger re-consolidation to generate abstractions for gaps.',
      input_schema: {
        type: 'object',
        properties: {
          create_missing: {
            type: 'boolean',
            description: 'Whether to trigger abstraction generation for gaps (default: true)',
          },
        },
        required: [],
      },
    },
    {
      name: 'resolve_tension',
      description:
        'I use this when I want to surface contradictions or tensions in my knowledge and record how to resolve them. ' +
        'Tensions are pairs of engrams that assert conflicting things.',
      input_schema: {
        type: 'object',
        properties: {
          topic: {
            type: 'string',
            description: 'Optional topic to focus tension search on',
          },
          resolution: {
            type: 'string',
            description: 'My resolution or note about a specific tension I found',
          },
        },
        required: [],
      },
    },
    {
      name: 'complete_organizing',
      description:
        'I use this when I am satisfied with the reorganization and want to finish the session with a summary.',
      input_schema: {
        type: 'object',
        properties: {
          summary: {
            type: 'string',
            description: 'What I reorganized and what I learned about my knowledge structure',
          },
        },
        required: ['summary'],
      },
    },
    // Diagnostic tools — understanding the landscape
    {
      name: 'scan_coverage',
      description:
        'I use this when I want to understand the overall shape of my memory — how many orphans, ' +
        'what types of engrams are unorganized, which provenances dominate, and whether embeddings are missing.',
      input_schema: {
        type: 'object',
        properties: {},
        required: [],
      },
    },
    {
      name: 'sample_orphans',
      description:
        'I use this when I want to see a random sample of unorganized engrams. ' +
        'This helps me identify topic patterns and decide what to organize next.',
      input_schema: {
        type: 'object',
        properties: {
          count: {
            type: 'number',
            description: 'Number of random orphans to sample (default: 20)',
          },
        },
        required: [],
      },
    },
    {
      name: 'topic_scan',
      description:
        'I use this when I want to see the frequency distribution of tags across my orphan engrams. ' +
        'Shows me which topics have the most unorganized memories, helping me prioritize.',
      input_schema: {
        type: 'object',
        properties: {
          limit: {
            type: 'number',
            description: 'Maximum number of top tags to return (default: 30)',
          },
        },
        required: [],
      },
    },
    // Batch action tools — efficient large-scale operations
    {
      name: 'batch_kindle',
      description:
        'I use this when I want to activate multiple topics at once instead of kindling them one at a time. ' +
        'Much more efficient for warming up several regions before consolidation.',
      input_schema: {
        type: 'object',
        properties: {
          queries: {
            type: 'array',
            items: {
              type: 'object',
              properties: {
                query: { type: 'string' },
                intensity: { type: 'string', enum: ['gentle', 'moderate', 'strong'] },
              },
              required: ['query'],
            },
            description: 'Array of topics to kindle, each with optional intensity',
          },
        },
        required: ['queries'],
      },
    },
    {
      name: 'batch_bridge',
      description:
        'I use this when I want to create bridges between multiple domain pairs at once. ' +
        'Each pair gets cross-activated and connected with synapses.',
      input_schema: {
        type: 'object',
        properties: {
          pairs: {
            type: 'array',
            items: {
              type: 'object',
              properties: {
                domain_a: { type: 'string' },
                domain_b: { type: 'string' },
                rationale: { type: 'string' },
              },
              required: ['domain_a', 'domain_b'],
            },
            description: 'Array of domain pairs to bridge',
          },
        },
        required: ['pairs'],
      },
    },
    {
      name: 'assign_by_similarity',
      description:
        'I use this when I want to find orphan engrams matching a topic and assign them to ' +
        'the nearest existing nucleus. Works by text similarity — does not require embeddings.',
      input_schema: {
        type: 'object',
        properties: {
          query: {
            type: 'string',
            description: 'Topic to search for among orphans',
          },
          nucleus_label: {
            type: 'string',
            description: 'Label of the target nucleus to assign matches to',
          },
          max_assign: {
            type: 'number',
            description: 'Maximum number of orphans to assign in this batch (default: 50)',
          },
        },
        required: ['query', 'nucleus_label'],
      },
    },
    {
      name: 'run_nucleus_detection',
      description:
        'I use this when I want to run spatial clustering (DBSCAN) with specific parameters ' +
        'to discover new nuclei. Useful for experimenting with different epsilon and min_cluster_size values.',
      input_schema: {
        type: 'object',
        properties: {
          epsilon: {
            type: 'number',
            description: 'DBSCAN neighborhood radius (default: 2.0, smaller = tighter clusters)',
          },
          min_cluster_size: {
            type: 'number',
            description: 'Minimum engrams to form a cluster (default: 3)',
          },
        },
        required: [],
      },
    },
    // Infrastructure tools — addressing root causes
    {
      name: 'check_embeddings',
      description:
        'I use this when I want to know how many of my engrams are missing embeddings. ' +
        'Engrams without embeddings cannot be spatially positioned or clustered by DBSCAN.',
      input_schema: {
        type: 'object',
        properties: {},
        required: [],
      },
    },
    {
      name: 'trigger_backfill',
      description:
        'I use this when I want to generate embeddings for engrams that are missing them. ' +
        'This enables those engrams to be spatially positioned and clustered in future consolidation.',
      input_schema: {
        type: 'object',
        properties: {
          batch_size: {
            type: 'number',
            description: 'Number of engrams to embed in this batch (default: 100)',
          },
        },
        required: [],
      },
    },
    {
      name: 'reproject_field',
      description:
        'I use this when I want to recompute the 2D spatial positions of all engrams using UMAP. ' +
        'Useful when the current projection is collapsed or when I want to experiment with different ' +
        'UMAP parameters to enable better spatial clustering.',
      input_schema: {
        type: 'object',
        properties: {
          n_neighbors: {
            type: 'number',
            description: 'UMAP neighborhood size — larger values see more global structure (default: 15, try 30-50 for large fields)',
          },
          min_dist: {
            type: 'number',
            description: 'Minimum distance between points — higher = more spread out (default: 0.1, try 0.3-0.5 for better separation)',
          },
          spread: {
            type: 'number',
            description: 'Scale of the embedding — higher = more spread (default: 1.0, try 2.0-5.0 for large fields)',
          },
          n_epochs: {
            type: 'number',
            description: 'Optimization iterations — more = better layout but slower (default: 200, try 400-600 for large fields)',
          },
        },
        required: [],
      },
    },
    // Continuation tools — multi-session progress
    {
      name: 'save_checkpoint',
      description:
        'I use this when I want to save my organizing progress so the next session can continue where I left off. ' +
        'Stores my strategy, topics covered, and what remains to be done.',
      input_schema: {
        type: 'object',
        properties: {
          strategy: {
            type: 'string',
            description: 'My current strategy and approach notes',
          },
          topics_covered: {
            type: 'array',
            items: { type: 'string' },
            description: 'Topics/regions I have already organized',
          },
          topics_remaining: {
            type: 'array',
            items: { type: 'string' },
            description: 'Topics/regions that still need organizing',
          },
          notes: {
            type: 'string',
            description: 'Any additional observations for my next session',
          },
        },
        required: ['strategy'],
      },
    },
    {
      name: 'load_checkpoint',
      description:
        'I use this at the start of an organizing session to see what my previous session accomplished ' +
        'and what strategy I was following. Lets me pick up where I left off.',
      input_schema: {
        type: 'object',
        properties: {},
        required: [],
      },
    },
  ]
}


/**
 * Build custom handlers for organizing tools.
 * Each handler interacts with the mnemic field's organizational capabilities.
 */
export function buildOrganizingHandlers(
  mnemicField: MnemicField,
  logger: ILogger,
  healthAnalyzer?: FieldHealthAnalyzer,
  meditationStore?: MeditationStore,
  feedbackTracker?: MeditationFeedbackTracker,
): { handlers: Record<string, (input: Record<string, unknown>) => Promise<ToolCallResult>>; stats: OrganizingStats; touchedRegions: string[] } {
  const stats: OrganizingStats = {
    regionsKindled: 0,
    bridgesCreated: 0,
    consolidationsRun: 0,
    abstractionsAudited: 0,
    tensionsSurfaced: 0,
    orphansAssigned: 0,
    embeddingsBackfilled: 0,
    batchKindles: 0,
    batchBridges: 0,
    nucleusDetections: 0,
    checkpointsSaved: 0,
  }

  /** Track which regions (query terms) were organized for progressive tracking */
  const touchedRegions: string[] = []

  const handlers: Record<string, (input: Record<string, unknown>) => Promise<ToolCallResult>> = {
    async survey_field(input) {
      const { focus } = input as { focus?: string }
      try {
        // Use health analyzer for comprehensive report when available
        if (healthAnalyzer) {
          const snapshot = healthAnalyzer.snapshot()
          let report = healthAnalyzer.formatHealthReport(snapshot)

          if (focus) {
            const hits = mnemicField.searchText(focus, 10)
            if (hits.length > 0) {
              const focusLines = hits.slice(0, 5).map(h =>
                `  - [${h.score.toFixed(2)}] ${h.engram.content.slice(0, 120)}`
              )
              report += `\n\nFocus area "${focus}" (${hits.length} matches):\n${focusLines.join('\n')}`
            } else {
              report += `\n\nFocus area "${focus}": no matches found — this might be a blind spot.`
            }
          }

          return { content: report }
        }

        // Fallback: basic stats when no health analyzer
        const fieldStats = mnemicField.stats()
        const nuclei = mnemicField.listNuclei()

        const lines: string[] = [
          `Field overview:`,
          `  Engrams: ${fieldStats.engramCount}`,
          `  Synapses: ${fieldStats.synapseCount}`,
          `  Nuclei (clusters): ${fieldStats.nucleusCount}`,
          `  Average potentiation: ${fieldStats.avgPotentiation.toFixed(3)}`,
          `  Spikes recorded: ${fieldStats.spikeCount}`,
        ]

        if (fieldStats.filamentCount !== undefined) {
          lines.push(`  Filaments: ${fieldStats.filamentCount}`)
        }

        // Show top engrams by potentiation
        if (fieldStats.topEngramsByPotentiation.length > 0) {
          lines.push('', 'Highest-potentiation engrams:')
          for (const e of fieldStats.topEngramsByPotentiation.slice(0, 5)) {
            lines.push(`  - [${e.potentiation.toFixed(3)}] ${e.content.slice(0, 120)}`)
          }
        }

        // Show cluster summaries
        if (nuclei.length > 0) {
          lines.push('', `Clusters (${nuclei.length}):`)
          for (const n of nuclei.slice(0, 10)) {
            const label = n.label || 'unnamed'
            const size = n.memberCount
            lines.push(`  - ${label} (${size} members)`)
          }
          if (nuclei.length > 10) {
            lines.push(`  ... and ${nuclei.length - 10} more`)
          }
        }

        // Focused survey: kindle a topic and show what lights up
        if (focus) {
          const hits = mnemicField.searchText(focus, 10)
          if (hits.length > 0) {
            lines.push('', `Focus area "${focus}" (${hits.length} matches):`)
            for (const h of hits.slice(0, 5)) {
              lines.push(`  - [${h.score.toFixed(2)}] ${h.engram.content.slice(0, 120)}`)
            }
          } else {
            lines.push('', `Focus area "${focus}": no matches found — this might be a blind spot.`)
          }
        }

        // Identify potential issues
        const issues: string[] = []
        if (fieldStats.nucleusCount === 0 && fieldStats.engramCount > 20) {
          issues.push('No clusters detected despite having engrams — consolidation may be needed')
        }
        if (fieldStats.avgPotentiation < 0.1 && fieldStats.engramCount > 10) {
          issues.push('Very low average potentiation — many engrams may be dormant')
        }
        const ratio = fieldStats.engramCount > 0
          ? fieldStats.synapseCount / fieldStats.engramCount
          : 0
        if (ratio < 0.5 && fieldStats.engramCount > 10) {
          issues.push(`Low connection density (${ratio.toFixed(1)} synapses per engram) — knowledge may be fragmented`)
        }

        if (issues.length > 0) {
          lines.push('', 'Issues detected:')
          for (const issue of issues) {
            lines.push(`  WARNING: ${issue}`)
          }
        }

        return { content: lines.join('\n') }
      } catch (err) {
        return { content: `Survey failed: ${String(err)}` }
      }
    },


    async kindle_region(input) {
      const { query, intensity } = input as { query: string; intensity?: 'gentle' | 'moderate' | 'strong' }
      if (!query) return { content: 'No query to kindle.' }

      try {
        const magnitudeMap = { gentle: 0.3, moderate: 0.5, strong: 0.8 }
        const magnitude = magnitudeMap[intensity ?? 'moderate']

        // Use retrieve() for spreading activation (kindle internally)
        const hits = mnemicField.retrieve(query, { limit: 15 })
        stats.regionsKindled++
        touchedRegions.push(query)

        // Track feedback: record retrieved engrams
        if (feedbackTracker && hits.length > 0) {
          feedbackTracker.recordRetrieved(hits.map(h => h.id), `organizing:kindle:${query}`)
        }

        if (hits.length === 0) {
          return { content: `Nothing activated for "${query}" — this region may be empty.` }
        }

        // Spike the top hits to reinforce their activation
        const spikedIds: string[] = []
        for (const hit of hits.slice(0, 8)) {
          try {
            mnemicField.spike({
              engramId: hit.id,
              magnitude,
              taskContext: `organizing:kindle:${query}`,
              outcome: 'unknown' as const,
            })
            spikedIds.push(hit.id)
          } catch (err) {
            logger.debug('[Organizing] Spike failed', { engramId: hit.id, error: String(err) })
          }
        }

        // Track feedback: spiked engrams are productive
        if (feedbackTracker && spikedIds.length > 0) {
          feedbackTracker.recordProductive(spikedIds)
        }

        const lines = hits.slice(0, 8).map(h =>
          `  - [charge: ${h.charge.toFixed(2)}, pot: ${h.potentiation.toFixed(2)}] ${h.content.slice(0, 120)}`
        )

        logger.info('[Organizing] Region kindled', { query, intensity, hits: hits.length, spiked: spikedIds.length })
        return {
          content: `Kindled "${query}" (${intensity ?? 'moderate'}): ${hits.length} engrams activated, ${spikedIds.length} spiked\n${lines.join('\n')}`,
        }
      } catch (err) {
        return { content: `Kindling failed: ${String(err)}` }
      }
    },


    async bridge_clusters(input) {
      const { domain_a, domain_b, rationale } = input as { domain_a: string; domain_b: string; rationale?: string }
      if (!domain_a || !domain_b) return { content: 'Both domains are required.' }

      try {
        // Retrieve engrams from both domains
        const hitsA = mnemicField.searchText(domain_a, 10)
        const hitsB = mnemicField.searchText(domain_b, 10)

        if (hitsA.length === 0 || hitsB.length === 0) {
          const missing = hitsA.length === 0 ? domain_a : domain_b
          return { content: `Cannot bridge — "${missing}" has no matching engrams.` }
        }

        // Track feedback: record retrieved engrams
        if (feedbackTracker) {
          const retrievedIds = [...hitsA.map(h => h.engram.id), ...hitsB.map(h => h.engram.id)]
          feedbackTracker.recordRetrieved(retrievedIds, `organizing:bridge:${domain_a}↔${domain_b}`)
        }

        // Cross-kindle: activate domain_a's engrams with domain_b's context and vice versa
        const crossActivatedIds: string[] = []
        for (const hitA of hitsA.slice(0, 5)) {
          for (const hitB of hitsB.slice(0, 5)) {
            try {
              mnemicField.spike({
                engramId: hitA.engram.id,
                magnitude: 0.3,
                taskContext: `organizing:bridge:${domain_b}`,
                outcome: 'unknown' as const,
              })
              mnemicField.spike({
                engramId: hitB.engram.id,
                magnitude: 0.3,
                taskContext: `organizing:bridge:${domain_a}`,
                outcome: 'unknown' as const,
              })
              crossActivatedIds.push(hitA.engram.id, hitB.engram.id)
            } catch (err) {
              logger.debug('[Organizing] Cross-activation failed', { error: String(err) })
            }
          }
        }

        // Create a bridge engram that explicitly connects the two domains
        const bridgeContent = rationale
          ? `Bridge: "${domain_a}" connects to "${domain_b}" — ${rationale}`
          : `Bridge: "${domain_a}" and "${domain_b}" are related domains that share concepts.`

        mnemicField.store({
          content: bridgeContent,
          nodeType: 'pattern',
          provenance: 'meditation:organizing',
          tags: ['bridge', 'organizing', domain_a.toLowerCase(), domain_b.toLowerCase()],
        })

        stats.bridgesCreated++

        // Try to create explicit synapse connections between top engrams
        const connectedIds: string[] = []
        for (const hitA of hitsA.slice(0, 3)) {
          for (const hitB of hitsB.slice(0, 3)) {
            try {
              mnemicField.connect({
                sourceId: hitA.engram.id,
                targetId: hitB.engram.id,
                edgeType: 'similar_to',
                weight: 0.5,
                metadata: { provenance: 'meditation:organizing' },
              })
              connectedIds.push(hitA.engram.id, hitB.engram.id)
            } catch (err) {
              logger.debug('[Organizing] Synapse creation failed', { error: String(err) })
            }
          }
        }

        // Track feedback: connected engrams are productive
        if (feedbackTracker && connectedIds.length > 0) {
          feedbackTracker.recordProductive([...new Set(connectedIds)])
        }

        logger.info('[Organizing] Bridge created', {
          domainA: domain_a, domainB: domain_b,
          crossActivations: crossActivatedIds.length,
          synapsesCreated: connectedIds.length / 2,
        })

        return {
          content: `Bridged "${domain_a}" ↔ "${domain_b}": ${crossActivatedIds.length} cross-activations, ${connectedIds.length / 2} new synapses, 1 bridge engram created.${rationale ? `\nRationale: ${rationale}` : ''}`,
        }
      } catch (err) {
        return { content: `Bridging failed: ${String(err)}` }
      }
    },


    async run_consolidation(input) {
      const { note } = input as { note?: string }
      try {
        const result = await mnemicField.consolidate()
        stats.consolidationsRun++

        const lines = [
          'Consolidation complete:',
          `  Potentiation updates: ${result.potentiationUpdates}`,
          `  Nuclei detected: ${result.nucleiDetected}`,
          `  Abstractions created: ${result.abstractionsCreated}`,
        ]

        if (note) lines.push(`  Goal: ${note}`)

        logger.info('[Organizing] Consolidation run', {
          potentiationUpdates: result.potentiationUpdates,
          nuclei: result.nucleiDetected,
          abstractions: result.abstractionsCreated,
          note,
        })

        return { content: lines.join('\n') }
      } catch (err) {
        return { content: `Consolidation failed: ${String(err)}` }
      }
    },


    async audit_abstractions(input) {
      const { create_missing } = input as { create_missing?: boolean }
      const shouldCreate = create_missing !== false

      try {
        const nuclei = mnemicField.listNuclei()
        const abstractions = mnemicField.listAbstractions(100)
        const abstractionClusterIds = new Set(
          abstractions
            .map(a => a.clusterId)
            .filter((id): id is string => id !== null && id !== undefined)
        )

        stats.abstractionsAudited++

        const lines: string[] = [
          `Abstraction audit:`,
          `  Total clusters: ${nuclei.length}`,
          `  Existing abstractions: ${abstractions.length}`,
        ]

        const missing: Array<{ id: string; label: string; size: number }> = []
        for (const n of nuclei) {
          if (!abstractionClusterIds.has(n.id) && n.abstractionId === null) {
            missing.push({
              id: n.id,
              label: n.label || 'unnamed',
              size: n.memberCount,
            })
          }
        }

        if (missing.length > 0) {
          lines.push(`  Clusters missing abstractions: ${missing.length}`)
          for (const m of missing.slice(0, 8)) {
            lines.push(`    - ${m.label} (${m.size} members)`)
          }
        } else {
          lines.push('  All clusters have abstractions — field is well-organized.')
        }

        // Trigger consolidation to generate abstractions for gaps
        if (shouldCreate && missing.length > 0) {
          const result = await mnemicField.consolidate()
          lines.push(`  Re-consolidated: ${result.abstractionsCreated} new abstractions generated`)
        }

        logger.info('[Organizing] Abstractions audited', {
          clusters: nuclei.length,
          existing: abstractions.length,
          missing: missing.length,
        })

        return { content: lines.join('\n') }
      } catch (err) {
        return { content: `Abstraction audit failed: ${String(err)}` }
      }
    },


    async resolve_tension(input) {
      const { topic, resolution } = input as { topic?: string; resolution?: string }

      try {
        // Surface tensions from the mnemic field
        const tensions = mnemicField.tensions(0.1, 10)
        stats.tensionsSurfaced += tensions.length

        if (tensions.length === 0) {
          return { content: 'No tensions detected in the field — knowledge appears consistent.' }
        }

        const lines: string[] = [`Tensions found (${tensions.length}):`]

        for (const t of tensions.slice(0, 5)) {
          const a = t.engramA
          const b = t.engramB
          if (a && b) {
            lines.push(`  Tension:`)
            lines.push(`    A: ${a.content.slice(0, 100)}`)
            lines.push(`    B: ${b.content.slice(0, 100)}`)
            lines.push(`    Score: ${t.tension.toFixed(2)}`)
          }
        }

        // If a resolution was provided, store it as a pattern engram
        if (resolution) {
          const resolutionContent = topic
            ? `Tension resolution (${topic}): ${resolution}`
            : `Tension resolution: ${resolution}`

          mnemicField.store({
            content: resolutionContent,
            nodeType: 'decision',
            provenance: 'meditation:organizing',
            tags: ['tension-resolution', 'organizing', ...(topic ? [topic.toLowerCase()] : [])],
          })
          lines.push(`\nResolution recorded: "${resolution.slice(0, 100)}"`)
        }

        logger.info('[Organizing] Tensions surfaced', { count: tensions.length, hasResolution: !!resolution })
        return { content: lines.join('\n') }
      } catch (err) {
        return { content: `Tension resolution failed: ${String(err)}` }
      }
    },


    async complete_organizing(input) {
      const { summary } = input as { summary: string }

      // Store the organizing session summary as a meta-learning engram
      if (summary) {
        try {
          mnemicField.store({
            content: `Organizing session: ${summary}`,
            nodeType: 'pattern',
            provenance: 'meditation:organizing',
            tags: ['organizing', 'meta-learning', 'session-summary'],
          })
        } catch (err) {
          logger.debug('[Organizing] Session summary engram failed', { error: String(err) })
        }
      }

      logger.info('[Organizing] Session complete', {
        summary: summary?.slice(0, 100),
        stats,
      })

      return { content: 'Organizing complete.', done: true }
    },


    async scan_coverage() {
      try {
        const cortex = mnemicField.getCortex()
        const fieldStats = mnemicField.stats()
        const distribution = cortex.orphanDistribution()
        const missingEmbeddings = cortex.countMissingEmbeddings()
        const nuclei = mnemicField.listNuclei()

        // Get spatial distribution for DBSCAN guidance
        const db = cortex.getDatabase()
        const spatialRow = db.prepare(
          `SELECT MIN(x) as minX, MAX(x) as maxX, MIN(y) as minY, MAX(y) as maxY, AVG(x) as avgX, AVG(y) as avgY,
                  COUNT(*) as positioned, (SELECT COUNT(*) FROM engrams WHERE x = 0 AND y = 0) as unpositioned
           FROM engrams WHERE x != 0 OR y != 0`
        ).get() as { minX: number; maxX: number; minY: number; maxY: number; avgX: number; avgY: number; positioned: number; unpositioned: number } | undefined

        const lines: string[] = [
          'Field Coverage Report:',
          `  Total engrams: ${fieldStats.engramCount}`,
          `  Orphans (no cluster): ${distribution.total} (${((distribution.total / Math.max(fieldStats.engramCount, 1)) * 100).toFixed(1)}%)`,
          `  Clustered: ${fieldStats.engramCount - distribution.total}`,
          `  Nuclei (clusters): ${fieldStats.nucleusCount}`,
          `  Synapses: ${fieldStats.synapseCount}`,
          `  Missing embeddings: ${missingEmbeddings} (${((missingEmbeddings / Math.max(fieldStats.engramCount, 1)) * 100).toFixed(1)}%)`,
        ]

        if (spatialRow && spatialRow.positioned > 0) {
          const xRange = spatialRow.maxX - spatialRow.minX
          const yRange = spatialRow.maxY - spatialRow.minY
          const avgDistance = Math.sqrt(xRange * xRange + yRange * yRange) / 2
          lines.push('', 'Spatial distribution (for DBSCAN tuning):')
          lines.push(`  X range: [${spatialRow.minX.toFixed(4)}, ${spatialRow.maxX.toFixed(4)}] (span: ${xRange.toFixed(4)})`)
          lines.push(`  Y range: [${spatialRow.minY.toFixed(4)}, ${spatialRow.maxY.toFixed(4)}] (span: ${yRange.toFixed(4)})`)
          lines.push(`  Positioned engrams: ${spatialRow.positioned}, Unpositioned: ${spatialRow.unpositioned}`)
          lines.push(`  Recommended DBSCAN epsilon: ${Math.max(0.001, avgDistance * 0.05).toFixed(4)} to ${Math.max(0.005, avgDistance * 0.1).toFixed(4)}`)
          lines.push(`  (Current default epsilon=2.0 is too large — engrams are packed in a ${xRange.toFixed(3)} × ${yRange.toFixed(3)} area)`)
        }

        lines.push('', 'Orphan breakdown by type:')
        for (const entry of distribution.byNodeType) {
          lines.push(`  ${entry.nodeType}: ${entry.count}`)
        }
        lines.push('', 'Orphan breakdown by provenance:')
        for (const entry of distribution.byProvenance.slice(0, 10)) {
          lines.push(`  ${entry.provenance}: ${entry.count}`)
        }

        if (nuclei.length > 0) {
          lines.push('', `Existing clusters (${nuclei.length}):`)
          for (const n of nuclei.slice(0, 15)) {
            lines.push(`  - "${n.label}" (${n.memberCount} members, pot: ${n.avgPotentiation.toFixed(3)})`)
          }
          if (nuclei.length > 15) {
            lines.push(`  ... and ${nuclei.length - 15} more`)
          }
        }

        logger.info('[Organizing] Coverage scan', {
          total: fieldStats.engramCount,
          orphans: distribution.total,
          missingEmbeddings,
          nuclei: fieldStats.nucleusCount,
        })

        return { content: lines.join('\n') }
      } catch (err) {
        return { content: `Coverage scan failed: ${String(err)}` }
      }
    },


    async sample_orphans(input) {
      const { count } = input as { count?: number }
      const sampleSize = Math.min(count ?? 20, 50)

      try {
        const cortex = mnemicField.getCortex()
        const samples = cortex.sampleOrphans(sampleSize)

        if (samples.length === 0) {
          return { content: 'No orphan engrams found — all engrams are clustered.' }
        }

        const lines: string[] = [`Random orphan sample (${samples.length} of ${cortex.orphanCount()} total):\n`]
        for (const s of samples) {
          let tags = ''
          try { tags = JSON.parse(s.tags).join(', ') } catch { /* no tags */ }
          lines.push(`  [${s.nodeType}] ${s.content}${tags ? ` (tags: ${tags})` : ''}`)
        }

        return { content: lines.join('\n') }
      } catch (err) {
        return { content: `Orphan sampling failed: ${String(err)}` }
      }
    },


    async topic_scan(input) {
      const { limit } = input as { limit?: number }
      const topN = limit ?? 30

      try {
        const cortex = mnemicField.getCortex()
        const distribution = cortex.orphanTagDistribution(topN)

        if (distribution.length === 0) {
          return { content: 'No tags found among orphan engrams — they may not have been tagged.' }
        }

        const lines: string[] = [`Orphan topic distribution (top ${distribution.length} tags):\n`]
        for (const entry of distribution) {
          lines.push(`  ${entry.tag}: ${entry.count} engrams`)
        }

        return { content: lines.join('\n') }
      } catch (err) {
        return { content: `Topic scan failed: ${String(err)}` }
      }
    },


    async batch_kindle(input) {
      const { queries } = input as { queries: Array<{ query: string; intensity?: 'gentle' | 'moderate' | 'strong' }> }
      if (!queries || queries.length === 0) return { content: 'No queries provided.' }

      const results: string[] = []
      let totalActivated = 0
      let totalSpiked = 0
      const allRetrievedIds: string[] = []
      const allSpikedIds: string[] = []

      for (const item of queries.slice(0, 20)) {
        try {
          const magnitudeMap = { gentle: 0.3, moderate: 0.5, strong: 0.8 }
          const magnitude = magnitudeMap[item.intensity ?? 'moderate']

          const hits = mnemicField.retrieve(item.query, { limit: 15 })
          stats.regionsKindled++
          touchedRegions.push(item.query)
          totalActivated += hits.length

          // Track feedback: record retrieved engrams
          if (feedbackTracker && hits.length > 0) {
            const ids = hits.map(h => h.id)
            allRetrievedIds.push(...ids)
          }

          const spikedIds: string[] = []
          for (const hit of hits.slice(0, 8)) {
            try {
              mnemicField.spike({
                engramId: hit.id,
                magnitude,
                taskContext: `organizing:kindle:${item.query}`,
                outcome: 'unknown' as const,
              })
              spikedIds.push(hit.id)
            } catch { /* non-fatal spike failure */ }
          }
          totalSpiked += spikedIds.length
          allSpikedIds.push(...spikedIds)

          results.push(`  "${item.query}": ${hits.length} activated, ${spikedIds.length} spiked`)
        } catch (err) {
          results.push(`  "${item.query}": failed — ${String(err)}`)
        }
      }

      // Track feedback: retrieved and spiked engrams
      if (feedbackTracker && allRetrievedIds.length > 0) {
        feedbackTracker.recordRetrieved(allRetrievedIds, 'organizing:batch_kindle')
        if (allSpikedIds.length > 0) {
          feedbackTracker.recordProductive(allSpikedIds)
        }
      }

      logger.info('[Organizing] Batch kindle', { queries: queries.length, totalActivated, totalSpiked })
      stats.batchKindles++
      return {
        content: `Batch kindle (${queries.length} topics):\n${results.join('\n')}\nTotal: ${totalActivated} activated, ${totalSpiked} spiked`,
      }
    },


    async batch_bridge(input) {
      const { pairs } = input as { pairs: Array<{ domain_a: string; domain_b: string; rationale?: string }> }
      if (!pairs || pairs.length === 0) return { content: 'No bridge pairs provided.' }

      const results: string[] = []
      let totalSynapses = 0

      for (const pair of pairs.slice(0, 10)) {
        try {
          const hitsA = mnemicField.searchText(pair.domain_a, 10)
          const hitsB = mnemicField.searchText(pair.domain_b, 10)

          if (hitsA.length === 0 || hitsB.length === 0) {
            const missing = hitsA.length === 0 ? pair.domain_a : pair.domain_b
            results.push(`  "${pair.domain_a}" <-> "${pair.domain_b}": skipped ("${missing}" has no matches)`)
            continue
          }

          // Cross-activate and connect
          let synapsesCreated = 0
          for (const hitA of hitsA.slice(0, 3)) {
            for (const hitB of hitsB.slice(0, 3)) {
              try {
                mnemicField.spike({
                  engramId: hitA.engram.id,
                  magnitude: 0.3,
                  taskContext: `organizing:bridge:${pair.domain_b}`,
                  outcome: 'unknown' as const,
                })
                mnemicField.spike({
                  engramId: hitB.engram.id,
                  magnitude: 0.3,
                  taskContext: `organizing:bridge:${pair.domain_a}`,
                  outcome: 'unknown' as const,
                })
                mnemicField.connect({
                  sourceId: hitA.engram.id,
                  targetId: hitB.engram.id,
                  edgeType: 'similar_to',
                  weight: 0.5,
                  metadata: { provenance: 'meditation:organizing' },
                })
                synapsesCreated++
              } catch { /* non-fatal connection failure */ }
            }
          }

          // Bridge engram
          const bridgeContent = pair.rationale
            ? `Bridge: "${pair.domain_a}" connects to "${pair.domain_b}" — ${pair.rationale}`
            : `Bridge: "${pair.domain_a}" and "${pair.domain_b}" are related domains.`
          mnemicField.store({
            content: bridgeContent,
            nodeType: 'pattern',
            provenance: 'meditation:organizing',
            tags: ['bridge', 'organizing', pair.domain_a.toLowerCase(), pair.domain_b.toLowerCase()],
          })

          stats.bridgesCreated++
          totalSynapses += synapsesCreated
          results.push(`  "${pair.domain_a}" <-> "${pair.domain_b}": ${synapsesCreated} synapses, 1 bridge engram`)
        } catch (err) {
          results.push(`  "${pair.domain_a}" <-> "${pair.domain_b}": failed — ${String(err)}`)
        }
      }

      logger.info('[Organizing] Batch bridge', { pairs: pairs.length, totalSynapses })
      stats.batchBridges++
      return {
        content: `Batch bridge (${pairs.length} pairs):\n${results.join('\n')}\nTotal: ${totalSynapses} new synapses`,
      }
    },


    async assign_by_similarity(input) {
      const { query, nucleus_label, max_assign } = input as { query: string; nucleus_label: string; max_assign?: number }
      if (!query || !nucleus_label) return { content: 'Both query and nucleus_label are required.' }

      const maxCount = Math.min(max_assign ?? 50, 200)

      try {
        // Find the target nucleus
        const nuclei = mnemicField.listNuclei()
        const targetNucleus = nuclei.find(n =>
          n.label.toLowerCase().includes(nucleus_label.toLowerCase())
        )

        if (!targetNucleus) {
          const available = nuclei.slice(0, 10).map(n => `"${n.label}"`).join(', ')
          return { content: `No nucleus matching "${nucleus_label}" found. Available: ${available}` }
        }

        // Search for orphan engrams matching the query
        const hits = mnemicField.searchText(query, maxCount)
        const cortex = mnemicField.getCortex()

        // Track feedback: record retrieved engrams
        if (feedbackTracker && hits.length > 0) {
          feedbackTracker.recordRetrieved(hits.map(h => h.engram.id), `organizing:assign:${query}`)
        }

        // Filter to only orphans
        const orphanHits = hits.filter(h => !h.engram.clusterId)
        if (orphanHits.length === 0) {
          return { content: `No orphan engrams found matching "${query}".` }
        }

        // Assign them
        const engramIds = orphanHits.map(h => h.engram.id)
        const assigned = cortex.assignToNucleus(engramIds, targetNucleus.id)

        // Track feedback: assigned engrams are productive
        if (feedbackTracker && assigned > 0) {
          feedbackTracker.recordProductive(engramIds.slice(0, assigned))
        }

        logger.info('[Organizing] Assigned orphans by similarity', {
          query, nucleusLabel: nucleus_label, assigned,
        })
        stats.orphansAssigned += assigned

        return {
          content: `Assigned ${assigned} orphan engrams matching "${query}" to nucleus "${targetNucleus.label}" (${targetNucleus.memberCount + assigned} total members now).`,
        }
      } catch (err) {
        return { content: `Assignment failed: ${String(err)}` }
      }
    },


    async run_nucleus_detection(input) {
      const { epsilon, min_cluster_size } = input as { epsilon?: number; min_cluster_size?: number }

      try {
        const eps = epsilon ?? 2.0
        const minSize = min_cluster_size ?? 3

        // Run consolidation with custom nucleus detection parameters
        const result = await mnemicField.consolidate({
          skipRadiance: true,
          skipDrift: true,
          skipAbstractions: true,
          skipPruning: true,
          skipFilamentConsolidation: true,
          nucleiEpsilon: eps,
          nucleiMinClusterSize: minSize,
        })

        const nuclei = mnemicField.listNuclei()
        const lines = [
          `Nucleus detection (epsilon=${eps}, minSize=${minSize}):`,
          `  Nuclei found: ${result.nucleiDetected}`,
          '',
          'Detected clusters:',
        ]
        for (const n of nuclei.slice(0, 15)) {
          lines.push(`  - "${n.label}" (${n.memberCount} members, pot: ${n.avgPotentiation.toFixed(3)})`)
        }
        if (nuclei.length > 15) {
          lines.push(`  ... and ${nuclei.length - 15} more`)
        }

        logger.info('[Organizing] Nucleus detection', { epsilon: eps, minSize, nuclei: result.nucleiDetected })
        stats.nucleusDetections++
        return { content: lines.join('\n') }
      } catch (err) {
        return { content: `Nucleus detection failed: ${String(err)}` }
      }
    },


    async check_embeddings() {
      try {
        const cortex = mnemicField.getCortex()
        const total = mnemicField.stats().engramCount
        const missing = cortex.countMissingEmbeddings()
        const embedded = total - missing
        const percentage = total > 0 ? ((embedded / total) * 100).toFixed(1) : '0'

        const lines = [
          'Embedding Coverage:',
          `  Total engrams: ${total}`,
          `  With embeddings: ${embedded} (${percentage}%)`,
          `  Missing embeddings: ${missing}`,
          '',
          missing > 0
            ? `${missing} engrams cannot be spatially positioned or clustered until they get embeddings. Use trigger_backfill to generate them.`
            : 'All engrams have embeddings — spatial clustering should work well.',
        ]

        return { content: lines.join('\n') }
      } catch (err) {
        return { content: `Embedding check failed: ${String(err)}` }
      }
    },


    async trigger_backfill(input) {
      const { batch_size } = input as { batch_size?: number }
      const batchSize = Math.min(batch_size ?? 100, 500)

      try {
        const beforeMissing = mnemicField.getCortex().countMissingEmbeddings()
        if (beforeMissing === 0) {
          return { content: 'All engrams already have embeddings — nothing to backfill.' }
        }

        const result = await mnemicField.backfillEmbeddings(batchSize)
        const afterMissing = mnemicField.getCortex().countMissingEmbeddings()

        logger.info('[Organizing] Embedding backfill', {
          embedded: result.embedded,
          reprojected: result.reprojected,
          remaining: afterMissing,
        })
        stats.embeddingsBackfilled += result.embedded

        if (result.reprojected === 0) {
          return {
            content: `Backfill complete: ${result.embedded} engrams embedded. Reprojection skipped (cooldown active or blocked by recent failures — wait 30 min before retrying).\nRemaining without embeddings: ${afterMissing}`,
          }
        }

        return {
          content: `Backfill complete: ${result.embedded} engrams embedded, ${result.reprojected} reprojected.\nRemaining without embeddings: ${afterMissing}`,
        }
      } catch (err) {
        return { content: `Backfill failed: ${String(err)}` }
      }
    },


    async reproject_field(input) {
      const { n_neighbors, min_dist, spread, n_epochs } = input as {
        n_neighbors?: number
        min_dist?: number
        spread?: number
        n_epochs?: number
      }

      try {
        const umapOpts: Record<string, number> = {}
        if (n_neighbors) umapOpts.nNeighbors = n_neighbors
        if (min_dist !== undefined) umapOpts.minDist = min_dist
        if (spread) umapOpts.spread = spread
        if (n_epochs) umapOpts.nEpochs = n_epochs

        const reprojected = await mnemicField.reprojectAllAsync(Object.keys(umapOpts).length > 0 ? umapOpts as any : undefined)

        if (reprojected === 0) {
          return { content: 'Reprojection skipped — cooldown active or blocked by recent failures. Wait 30 minutes before retrying.' }
        }

        // After reprojection, run nucleus detection to see if clusters emerge
        const nuclei = mnemicField.listNuclei()
        const lines = [
          `Reprojection complete: ${reprojected} engrams repositioned.`,
        ]
        if (Object.keys(umapOpts).length > 0) {
          lines.push(`UMAP params: ${JSON.stringify(umapOpts)}`)
        }
        lines.push(`Existing nuclei after reprojection: ${nuclei.length}`)
        if (nuclei.length > 0) {
          for (const n of nuclei.slice(0, 10)) {
            lines.push(`  - "${n.label}" (${n.memberCount} members)`)
          }
        }

        logger.info('[Organizing] Field reprojected', { reprojected, nuclei: nuclei.length, umapOpts })
        return { content: lines.join('\n') }
      } catch (err) {
        return { content: `Reprojection failed: ${String(err)}` }
      }
    },


    async save_checkpoint(input) {
      const { strategy, topics_covered, topics_remaining, notes } = input as {
        strategy: string
        topics_covered?: string[]
        topics_remaining?: string[]
        notes?: string
      }

      if (!meditationStore) {
        return { content: 'Cannot save checkpoint — meditation store not available.' }
      }

      try {
        const checkpoint: OrganizingCheckpoint = {
          timestamp: Date.now(),
          passNumber: (loadCheckpointData(meditationStore)?.passNumber ?? 0) + 1,
          strategy,
          topicsCovered: [...touchedRegions, ...(topics_covered ?? [])],
          topicsRemaining: topics_remaining ?? [],
          notes: notes ?? '',
          metrics: {
            orphanRatioSnapshot: healthAnalyzer
              ? healthAnalyzer.snapshot().orphanRatio
              : 0,
            regionsKindled: stats.regionsKindled,
            bridgesCreated: stats.bridgesCreated,
            consolidationsRun: stats.consolidationsRun,
          },
        }

        meditationStore.setMetaText(CHECKPOINT_KEY, JSON.stringify(checkpoint))
        logger.info('[Organizing] Checkpoint saved', { passNumber: checkpoint.passNumber, topicsCovered: checkpoint.topicsCovered.length })
        stats.checkpointsSaved++
        return { content: `Checkpoint saved (pass ${checkpoint.passNumber}). Strategy and ${checkpoint.topicsCovered.length} covered topics recorded for next session.` }
      } catch (err) {
        return { content: `Checkpoint save failed: ${String(err)}` }
      }
    },


    async load_checkpoint() {
      if (!meditationStore) {
        return { content: 'No checkpoint available — meditation store not available.' }
      }

      try {
        const checkpoint = loadCheckpointData(meditationStore)
        if (!checkpoint) {
          return { content: 'No previous checkpoint found. This is the first organizing session.' }
        }

        const lines = [
          `Previous checkpoint (pass ${checkpoint.passNumber}, ${new Date(checkpoint.timestamp).toISOString()}):`,
          '',
          `Strategy: ${checkpoint.strategy}`,
          '',
          `Topics covered (${checkpoint.topicsCovered.length}):`,
          ...checkpoint.topicsCovered.slice(0, 20).map((t: string) => `  - ${t}`),
        ]

        if (checkpoint.topicsCovered.length > 20) {
          lines.push(`  ... and ${checkpoint.topicsCovered.length - 20} more`)
        }

        if (checkpoint.topicsRemaining.length > 0) {
          lines.push('', `Topics remaining (${checkpoint.topicsRemaining.length}):`)
          for (const t of checkpoint.topicsRemaining) {
            lines.push(`  - ${t}`)
          }
        }

        if (checkpoint.notes) {
          lines.push('', `Notes: ${checkpoint.notes}`)
        }

        lines.push('', `Metrics from last pass:`)
        lines.push(`  Orphan ratio: ${(checkpoint.metrics.orphanRatioSnapshot * 100).toFixed(1)}%`)
        lines.push(`  Regions kindled: ${checkpoint.metrics.regionsKindled}`)
        lines.push(`  Bridges created: ${checkpoint.metrics.bridgesCreated}`)
        lines.push(`  Consolidations: ${checkpoint.metrics.consolidationsRun}`)

        return { content: lines.join('\n') }
      } catch (err) {
        return { content: `Checkpoint load failed: ${String(err)}` }
      }
    },
  }

  return { handlers, stats, touchedRegions }
}
