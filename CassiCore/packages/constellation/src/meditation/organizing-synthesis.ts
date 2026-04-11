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

I will:
1. Survey my memory field to understand its current shape — where clusters are dense, where they're sparse, where connections are missing (survey_field)
2. Kindle weak or orphaned regions to activate dormant knowledge (kindle_region)
3. Build bridges between clusters that should be connected but aren't (bridge_clusters)
4. Run consolidation to let the field reorganize based on fresh activation (run_consolidation)
5. Audit my abstractions to ensure clusters have proper summaries (audit_abstractions)
6. Surface and address any contradictions or tensions in my knowledge (resolve_tension)
7. Call complete_organizing when I'm satisfied with the reorganization

I work methodically. Each step builds on the previous one — surveying informs kindling, kindling creates activation for consolidation, and consolidation reveals where abstractions are missing. I write everything in first person. This is my mind and I'm taking care of it.`
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
Tensions surfaced: ${organizingStats.tensionsSurfaced}${delta ? `\n\nBefore/After Summary: ${delta.summary}` : ''}
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
        'Take a diagnostic snapshot of my memory field. Shows cluster distribution, ' +
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
        'Activate a weak or dormant region of memory by spreading activation through it. ' +
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
        'Search for thematic connections between two topics or domains and create ' +
        'explicit bridges. Finds engrams in both domains and looks for shared concepts.',
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
        'Trigger a full consolidation cycle: radiance recomputation, co-activation drift, ' +
        'nucleus detection, and abstraction generation. Best done after kindling to let ' +
        'the field reorganize with fresh activation data.',
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
        'Review existing abstractions (summary engrams for clusters) and identify gaps. ' +
        'Shows which clusters have summaries and which need them.',
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
        'Surface contradictions or tensions in my knowledge and record how to resolve them. ' +
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
        'Finish the organizing session with a summary of what changed.',
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
): { handlers: Record<string, (input: Record<string, unknown>) => Promise<ToolCallResult>>; stats: OrganizingStats; touchedRegions: string[] } {
  const stats: OrganizingStats = {
    regionsKindled: 0,
    bridgesCreated: 0,
    consolidationsRun: 0,
    abstractionsAudited: 0,
    tensionsSurfaced: 0,
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

        if (hits.length === 0) {
          return { content: `Nothing activated for "${query}" — this region may be empty.` }
        }

        // Spike the top hits to reinforce their activation
        let spiked = 0
        for (const hit of hits.slice(0, 8)) {
          try {
            mnemicField.spike({
              engramId: hit.id,
              magnitude,
              taskContext: `organizing:kindle:${query}`,
              outcome: 'unknown' as const,
            })
            spiked++
          } catch (err) {
            logger.debug('[Organizing] Spike failed', { engramId: hit.id, error: String(err) })
          }
        }

        const lines = hits.slice(0, 8).map(h =>
          `  - [charge: ${h.charge.toFixed(2)}, pot: ${h.potentiation.toFixed(2)}] ${h.content.slice(0, 120)}`
        )

        logger.info('[Organizing] Region kindled', { query, intensity, hits: hits.length, spiked })
        return {
          content: `Kindled "${query}" (${intensity ?? 'moderate'}): ${hits.length} engrams activated, ${spiked} spiked\n${lines.join('\n')}`,
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

        // Cross-kindle: activate domain_a's engrams with domain_b's context and vice versa
        let crossActivations = 0
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
              crossActivations += 2
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
        let synapsesCreated = 0
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
              synapsesCreated++
            } catch (err) {
              logger.debug('[Organizing] Synapse creation failed', { error: String(err) })
            }
          }
        }

        logger.info('[Organizing] Bridge created', {
          domainA: domain_a, domainB: domain_b,
          crossActivations, synapsesCreated,
        })

        return {
          content: `Bridged "${domain_a}" ↔ "${domain_b}": ${crossActivations} cross-activations, ${synapsesCreated} new synapses, 1 bridge engram created.${rationale ? `\nRationale: ${rationale}` : ''}`,
        }
      } catch (err) {
        return { content: `Bridging failed: ${String(err)}` }
      }
    },


    async run_consolidation(input) {
      const { note } = input as { note?: string }
      try {
        const result = mnemicField.consolidate()
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
          const result = mnemicField.consolidate()
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
  }

  return { handlers, stats, touchedRegions }
}
