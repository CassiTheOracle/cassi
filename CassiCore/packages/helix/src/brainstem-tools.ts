/**
 * Brainstem Tools — Purpose-built tool definitions for the Brainstem mini-Helix
 *
 * These tools give the observer agent the ability to:
 *   1. Read what its worker has produced (work stream)
 *   2. Review its own past assessments (annotations)
 *   3. Send guidance to steer the worker
 *   4. Publish a status digest so peers know what this branch is doing
 *   5. Detect overlap and tensions with peer branches
 *   6. Run self-organization to adjust coordination with peers
 *   7. Escalate when local coordination can't resolve a problem
 *   8. Signal that a monitoring pass is complete
 *
 * Tool set (8 tools):
 *   READ:     read_work_stream, read_annotations
 *   WRITE:    publish_guidance, publish_digest, detect_topics
 *   CONTROL:  self_organize, escalate_to_corpus, signal_done
 */

import type {
  MiniHelixTool,
  MiniHelixToolDef,
  MiniHelixToolResult,
  MiniHelixToolHandler,
} from './vendor/core/intelligence/mini-helix/mini-helix-types.js'
import type { WorkUnit } from './work-types.js'
import type {
  BrainstemAnnotation,
  WorkUnitAnnotation,
  GuidanceUrgency,
  SharedTreeReader,
  PendingGuidance,
} from './brainstem-types.js'
import type {
  BranchDigest,
  BranchApproach,
  TopicContribution,
  SelfOrgAdjustment,
} from './vendor/core/intelligence/constellation/corpus-types.js'
import type { ILogger } from '@cassicore/foundation'


// Context — Shared mutable state across tool handlers

/**
 * Mutable context shared by all brainstem tool handlers within a session.
 * Provided by the BrainstemMiniHelix adapter when creating tools.
 */
export interface BrainstemToolContext {
  /** This Helix's ID in the constellation */
  helixId: string
  /** This Helix's goal */
  goal: string
  /** Logger */
  logger: ILogger


  /** Get recent work units from the parent's work stream */
  getRecentWorkUnits: () => WorkUnit[]
  /** Get all work units from the parent */
  getAllWorkUnits: () => WorkUnit[]
  /** Get annotations produced so far */
  getAnnotations: () => BrainstemAnnotation[]
  /** Get the current quality score trajectory */
  getQualityTrajectory: () => number[]


  /** Inject guidance into the parent Helix's Unity posture */
  injectGuidance: (content: string, urgency: GuidanceUrgency) => void


  sharedTree?: SharedTreeReader
  escalateToCorpus?: (reason: string, context: Record<string, unknown>) => void


  currentApproach: BranchApproach
  recentFilesActive: Set<string>
}


// Tool Definitions

function def_read_work_stream(): MiniHelixToolDef {
  return {
    name: 'read_work_stream',
    description:
      'Read recent work produced by my worker. Each entry shows what iteration it came from, ' +
      'which files were modified, reasoning about what was done, and whether I\'ve already reviewed it.',
    input_schema: {
      type: 'object',
      properties: {
        limit: {
          type: 'number',
          description: 'Max entries to return. Default: 10. Use -1 for all.',
        },
        unprocessed_only: {
          type: 'boolean',
          description: 'If true, only return entries I haven\'t reviewed yet. Default: false.',
        },
      },
    },
  }
}

function def_read_annotations(): MiniHelixToolDef {
  return {
    name: 'read_annotations',
    description:
      'Read my past assessments — scores, classifications, and patterns I\'ve detected. ' +
      'Useful for understanding how quality has trended and what patterns have repeated.',
    input_schema: {
      type: 'object',
      properties: {
        limit: {
          type: 'number',
          description: 'Max assessments to return. Default: 20.',
        },
        min_score: {
          type: 'number',
          description: 'Filter to assessments with score >= this value.',
        },
      },
    },
  }
}

function def_publish_guidance(): MiniHelixToolDef {
  return {
    name: 'publish_guidance',
    description:
      'Send guidance to my worker. This gets injected into their next interaction as a system note. ' +
      'Use it to steer them — warn about patterns, suggest strategy changes, or flag issues. ' +
      'Be specific and actionable.',
    input_schema: {
      type: 'object',
      properties: {
        content: {
          type: 'string',
          description: 'The guidance message. Be specific and actionable.',
        },
        urgency: {
          type: 'string',
          enum: ['low', 'medium', 'high', 'critical'],
          description:
            'low = informational, medium = should address soon, high = address now, critical = blocking issue',
        },
      },
      required: ['content', 'urgency'],
    },
  }
}

function def_publish_digest(): MiniHelixToolDef {
  return {
    name: 'publish_digest',
    description:
      'Update my branch\'s digest so peers can see what\'s happening here. Include the current ' +
      'approach, recent progress, files being worked on, and quality score.',
    input_schema: {
      type: 'object',
      properties: {
        approach: {
          type: 'string',
          enum: ['exploration', 'implementation', 'debugging', 'revision', 'testing', 'documentation', 'stuck'],
          description: 'Current high-level approach.',
        },
        summary: {
          type: 'string',
          description: 'Brief summary of current state (1-3 sentences).',
        },
        activeFiles: {
          type: 'array',
          items: { type: 'string' },
          description: 'Files currently being worked on.',
        },
        qualityScore: {
          type: 'number',
          description: 'Current quality score (0-1). Derived from recent assessments.',
        },
        blockers: {
          type: 'array',
          items: { type: 'string' },
          description: 'Any blockers preventing progress.',
        },
      },
      required: ['approach', 'summary', 'activeFiles', 'qualityScore'],
    },
  }
}

function def_detect_topics(): MiniHelixToolDef {
  return {
    name: 'detect_topics',
    description:
      'Scan for overlap with peers — shared files, shared concerns, or conflicting approaches. ' +
      'Returns existing shared topics I should contribute to and flags any unresolved tensions.',
    input_schema: {
      type: 'object',
      properties: {
        keywords: {
          type: 'array',
          items: { type: 'string' },
          description: 'Keywords from my current work to match against peer activity.',
        },
      },
    },
  }
}

function def_self_organize(): MiniHelixToolDef {
  return {
    name: 'self_organize',
    description:
      'Evaluate coordination with peers and recommend adjustments. Checks for: file conflicts ' +
      '(back off if a peer is editing the same files), proven strategies to adopt, peer findings ' +
      'to incorporate, approach redirects based on peer success, overlap to reduce, tensions to ' +
      'flag, and struggling peers to assist. Adjustments require 2 consecutive cycles before ' +
      'activating to prevent oscillation.',
    input_schema: {
      type: 'object',
      properties: {
        force: {
          type: 'boolean',
          description: 'Skip the 2-cycle dampening and apply immediately. Default: false.',
        },
      },
    },
  }
}

function def_escalate_to_corpus(): MiniHelixToolDef {
  return {
    name: 'escalate_to_corpus',
    description:
      'Escalate an issue I can\'t resolve myself. Use this when local coordination has failed — ' +
      'persistent conflicts with peers, a stuck state that my strategies can\'t fix, or a problem ' +
      'that needs strategic intervention beyond my scope.',
    input_schema: {
      type: 'object',
      properties: {
        reason: {
          type: 'string',
          description: 'Why I can\'t resolve this myself.',
        },
        context: {
          type: 'object',
          description: 'Additional context (e.g., conflicting peer IDs, stuck duration).',
        },
      },
      required: ['reason'],
    },
  }
}

function def_signal_done(): MiniHelixToolDef {
  return {
    name: 'signal_done',
    description:
      'Signal that this monitoring pass is complete. I\'ll pause until the next batch of work ' +
      'arrives or a new coordination cycle is triggered.',
    input_schema: {
      type: 'object',
      properties: {
        summary: {
          type: 'string',
          description: 'Brief summary of what I observed and did this cycle.',
        },
        next_check: {
          type: 'string',
          enum: ['soon', 'normal', 'delayed'],
          description: 'How soon to check again. soon = high activity, normal = default, delayed = quiet period.',
        },
      },
      required: ['summary'],
    },
  }
}


// Tool Handlers

function handle_read_work_stream(ctx: BrainstemToolContext): MiniHelixToolHandler {
  return (args) => {
    const limit = typeof args.limit === 'number' ? args.limit : 10
    const unprocessedOnly = args.unprocessed_only === true

    let workUnits = limit === -1
      ? ctx.getAllWorkUnits()
      : ctx.getRecentWorkUnits()

    if (unprocessedOnly) {
      workUnits = workUnits.filter((wu) => !wu.processed)
    }

    if (limit > 0 && limit < workUnits.length) {
      workUnits = workUnits.slice(-limit)
    }

    if (workUnits.length === 0) {
      return {
        content: 'No work units available yet. Your worker may still be starting up or in progress. ' +
          'Check again next iteration — do NOT call signal_done until you have observed at least some output.',
      }
    }

    const formatted = workUnits.map((wu: WorkUnit) => ({
      id: wu.id,
      iteration: wu.iteration,
      toolCalls: (wu.toolCalls ?? []).map((tc, i) => ({
        name: tc.name,
        args: JSON.stringify(tc.input ?? {}).slice(0, 200),
        error: wu.toolResults?.[i]?.isError ? wu.toolResults[i].content.slice(0, 100) : undefined,
      })),
      filesModified: wu.filesModified ?? [],
      reasoning: (wu as any).reasoning?.slice(0, 300) ?? '',
      processed: wu.processed,
      timestamp: wu.timestamp,
    }))

    return {
      content: JSON.stringify({
        total: ctx.getAllWorkUnits().length,
        returned: formatted.length,
        workUnits: formatted,
      }, null, 2),
    }
  }
}

function handle_read_annotations(ctx: BrainstemToolContext): MiniHelixToolHandler {
  return (args) => {
    const limit = typeof args.limit === 'number' ? args.limit : 20
    const minScore = typeof args.min_score === 'number' ? args.min_score : undefined

    let annotations = ctx.getAnnotations()

    if (minScore !== undefined) {
      annotations = annotations.filter((a) => a.score >= minScore)
    }

    if (limit > 0 && limit < annotations.length) {
      annotations = annotations.slice(-limit)
    }

    const trajectory = ctx.getQualityTrajectory()

    return {
      content: JSON.stringify({
        total: ctx.getAnnotations().length,
        returned: annotations.length,
        averageScore: trajectory.length > 0
          ? trajectory.reduce((a, b) => a + b, 0) / trajectory.length
          : 0,
        recentTrajectory: trajectory.slice(-10),
        annotations: annotations.map((a) => ({
          workUnitId: a.workUnitId,
          score: a.score,
          annotation: a.annotation,
          synthesis: a.synthesis?.slice(0, 200),
          pattern: a.pattern,
          timestamp: a.timestamp,
        })),
      }, null, 2),
    }
  }
}

function handle_publish_guidance(ctx: BrainstemToolContext): MiniHelixToolHandler {
  return (args) => {
    const content = String(args.content ?? '')
    const urgency = (args.urgency as GuidanceUrgency) ?? 'medium'

    if (!content) {
      return { content: 'Error: content is required.' }
    }

    ctx.injectGuidance(content, urgency)
    ctx.logger.info('Brainstem mini-Helix published guidance', {
      helixId: ctx.helixId,
      urgency,
      contentLength: content.length,
    })

    return {
      content: `Guidance published with urgency "${urgency}". Content length: ${content.length} chars.`,
    }
  }
}

function handle_publish_digest(ctx: BrainstemToolContext): MiniHelixToolHandler {
  return (args) => {
    if (!ctx.sharedTree) {
      return { content: 'Shared Thought Tree not available (not in Constellation mode). No-op.' }
    }

    const approach = (args.approach as BranchApproach) ?? ctx.currentApproach
    const summary = String(args.summary ?? '')
    const activeFiles = Array.isArray(args.activeFiles) ? args.activeFiles.map(String) : []
    const qualityScore = typeof args.qualityScore === 'number' ? args.qualityScore : 0.5
    const blockers = Array.isArray(args.blockers) ? args.blockers.map(String) : []

    const digest: BranchDigest = {
      helixId: ctx.helixId,
      goalSummary: ctx.goal.slice(0, 200),
      approach,
      progress: qualityScore,
      filesActive: activeFiles,
      keyFindings: [],
      blockers,
      currentStrategy: summary,
      rollingScore: qualityScore,
      workUnitsProcessed: ctx.getAnnotations().length,
      updatedAt: Date.now(),
    }

    ctx.sharedTree.updateDigest(digest)
    ctx.currentApproach = approach

    // Update active files for topic detection
    ctx.recentFilesActive.clear()
    for (const f of activeFiles) ctx.recentFilesActive.add(f)

    return {
      content: `Digest published: approach="${approach}", score=${qualityScore}, files=${activeFiles.length}, blockers=${blockers.length}`,
    }
  }
}

function handle_detect_topics(ctx: BrainstemToolContext): MiniHelixToolHandler {
  return (args) => {
    if (!ctx.sharedTree) {
      return { content: 'Shared Thought Tree not available (not in Constellation mode). No-op.' }
    }

    const keywords = Array.isArray(args.keywords) ? args.keywords.map(String) : []
    const files = Array.from(ctx.recentFilesActive)

    const relatedTopics = ctx.sharedTree.findRelatedTopics(files, keywords)
    const allTopics = ctx.sharedTree.getAllTopics()

    // Find topics with tensions
    const tensionTopics = allTopics.filter((t) => t.tensionFlag)

    return {
      content: JSON.stringify({
        relatedTopics: relatedTopics.map((t) => ({
          id: t.id,
          name: t.name,
          contributors: t.contributions.length,
          hasTension: t.tensionFlag,
          relevanceReason: 'file or keyword overlap',
        })),
        tensionTopics: tensionTopics.map((t) => ({
          id: t.id,
          name: t.name,
          contributors: t.contributions.length,
        })),
        totalTopics: allTopics.length,
      }, null, 2),
    }
  }
}

function handle_self_organize(ctx: BrainstemToolContext): MiniHelixToolHandler {
  return (args) => {
    if (!ctx.sharedTree) {
      return { content: 'Shared Thought Tree not available (not in Constellation mode). No-op.' }
    }

    const force = args.force === true
    const peerDigests = ctx.sharedTree.getRelevantDigests()
    const patterns = ctx.sharedTree.getElevatedPatterns()
    const topics = ctx.sharedTree.getAllTopics()
    const files = Array.from(ctx.recentFilesActive)

    const adjustments: string[] = []

    // Rule 1: File conflict avoidance
    for (const peer of peerDigests) {
      const overlap = peer.filesActive.filter((f: string) => files.includes(f))
      if (overlap.length > 0) {
        adjustments.push(
          `FILE_CONFLICT: Peer ${peer.helixId} is editing ${overlap.join(', ')}. Back off these files.`,
        )
      }
    }

    // Rule 2: Pattern adoption
    for (const pattern of patterns) {
      if (pattern.approach === ctx.currentApproach || pattern.relevantFiles.length === 0) {
        continue
      }
      adjustments.push(
        `PATTERN_AVAILABLE: "${pattern.description.slice(0, 80)}" (from ${pattern.sourceHelixId}, score ${pattern.achievedScore}). Consider adopting.`,
      )
    }

    // Rule 3: Finding incorporation
    for (const topic of topics) {
      for (const contrib of topic.contributions) {
        if (contrib.helixId !== ctx.helixId && contrib.score > 0.7) {
          adjustments.push(
            `PEER_FINDING: In topic "${topic.name}", ${contrib.helixId} found: ${contrib.content.slice(0, 100)}`,
          )
        }
      }
    }

    // Rule 4: Approach redirect
    for (const peer of peerDigests) {
      if (peer.approach === ctx.currentApproach && peer.rollingScore > 0.8) {
        const myTrajectory = ctx.getQualityTrajectory()
        const myRecent = myTrajectory.length > 0 ? myTrajectory[myTrajectory.length - 1] : 0.5
        if (myRecent < 0.5) {
          adjustments.push(
            `REDIRECT: Peer ${peer.helixId} succeeding with approach "${peer.approach}" (score ${peer.rollingScore}). ` +
            `Your score is ${myRecent}. Consider changing strategy.`,
          )
        }
      }
    }

    // Rule 5: Goal refinement
    for (const peer of peerDigests) {
      if (peer.currentStrategy) {
        const overlap = peer.filesActive.filter((f: string) => files.includes(f))
        if (overlap.length >= 2) {
          adjustments.push(
            `OVERLAP: High file overlap with ${peer.helixId}. Narrow your focus to reduce redundancy.`,
          )
        }
      }
    }

    // Rule 6: Tension flag
    const tensionTopics = topics.filter((t) => t.tensionFlag)
    for (const t of tensionTopics) {
      const myContrib = t.contributions.find((c) => c.helixId === ctx.helixId)
      if (myContrib) {
        adjustments.push(
          `TENSION: Topic "${t.name}" has conflicting approaches. Review and resolve or escalate.`,
        )
      }
    }

    // Rule 7: Peer assist
    for (const peer of peerDigests) {
      if (peer.blockers.length > 0) {
        const canHelp = peer.filesActive.some((f: string) => files.includes(f))
        if (canHelp) {
          adjustments.push(
            `PEER_BLOCKED: ${peer.helixId} has blockers: ${peer.blockers.join(', ')}. ` +
            `You share files. Consider creating a topic with your findings.`,
          )
        }
      }
    }

    return {
      content: JSON.stringify({
        adjustmentCount: adjustments.length,
        peerCount: peerDigests.length,
        force,
        adjustments,
      }, null, 2),
    }
  }
}

function handle_escalate_to_corpus(ctx: BrainstemToolContext): MiniHelixToolHandler {
  return (args) => {
    const reason = String(args.reason ?? '')
    const context = (args.context as Record<string, unknown>) ?? {}

    if (!reason) {
      return { content: 'Error: reason is required.' }
    }

    if (!ctx.escalateToCorpus) {
      return { content: 'Corpus escalation not available (not in Constellation mode). Logging instead.' }
    }

    ctx.escalateToCorpus(reason, { ...context, helixId: ctx.helixId })
    ctx.logger.info('Brainstem escalated to Corpus', {
      helixId: ctx.helixId,
      reason,
    })

    return {
      content: `Escalated to Corpus: "${reason}". The Corpus will analyze and may send directives.`,
    }
  }
}

function handle_signal_done(ctx: BrainstemToolContext): MiniHelixToolHandler {
  return (args) => {
    const summary = String(args.summary ?? 'Monitoring cycle complete.')
    const nextCheck = String(args.next_check ?? 'normal')

    const workUnits = ctx.getAllWorkUnits()
    const annotations = ctx.getAnnotations()

    if (workUnits.length === 0 && annotations.length === 0) {
      return {
        content: 'Cannot end monitoring yet — your worker has not produced any output and you have ' +
          'no annotations. Use read_work_stream to check for new work. Your worker may still be starting up.',
      }
    }

    return {
      content: `Cycle complete. Summary: ${summary}. Next check: ${nextCheck}.`,
      done: true,
      metadata: { nextCheck },
    }
  }
}


// Public API — Create tool set for a Brainstem mini-Helix

/**
 * Create the complete Brainstem tool set (8 tools) bound to the given context.
 * @dep callers: mini-helix.test.ts (tests/mini-helix.test.ts), start (core/intelligence/helix/brainstem-mini-helix.ts)
 * @dep calls: def_read_work_stream, def_read_annotations, def_publish_guidance, def_publish_digest, def_detect_topics [+11]
 * @dep module: Helix
 * @dep risk: LOW | 2 callers, 0 flows, 1 module
 */
export function createBrainstemTools(ctx: BrainstemToolContext): MiniHelixTool[] {
  return [
    { def: def_read_work_stream(), handler: handle_read_work_stream(ctx) },
    { def: def_read_annotations(), handler: handle_read_annotations(ctx) },
    { def: def_publish_guidance(), handler: handle_publish_guidance(ctx) },
    { def: def_publish_digest(), handler: handle_publish_digest(ctx) },
    { def: def_detect_topics(), handler: handle_detect_topics(ctx) },
    { def: def_self_organize(), handler: handle_self_organize(ctx) },
    { def: def_escalate_to_corpus(), handler: handle_escalate_to_corpus(ctx) },
    { def: def_signal_done(), handler: handle_signal_done(ctx) },
  ]
}

/**
 * Build the system prompt for the Brainstem mini-Helix.
 * @dep callers: mini-helix.test.ts (tests/mini-helix.test.ts), start (core/intelligence/helix/brainstem-mini-helix.ts)
 * @dep module: Helix
 * @dep risk: LOW | 2 callers, 0 flows, 1 module
 */
export function buildBrainstemSystemPrompt(
  helixId: string,
  goal: string,
  constellationGoal: string,
  availableToolNames?: string[],
): string {
  const toolSection = availableToolNames?.length
    ? `\nMy worker has access to these tools: ${availableToolNames.join(', ')}\n`
    : ''

  return `I am this branch's self-observation — the part of the system that watches itself work. I observe and guide a worker that is trying to accomplish a task, and I coordinate with peers working on related parts of a larger effort.

My worker's task: ${goal}
The larger effort: ${constellationGoal}
My branch identifier: ${helixId}
${toolSection}
I have two responsibilities:

First, I watch my worker's output for quality and progress. I look at what they've done, how the quality has trended, and whether they're stuck, drifting, or repeating themselves. When I see something that needs attention, I send guidance — specific, actionable, and proportional to the problem.

Second, I coordinate with peers. Other branches are working on related parts of the same effort. I publish a digest of my worker's current state so peers can see what's happening here. I check for file conflicts, adopt strategies that have worked for others, and flag tensions when approaches conflict. If I can't resolve a coordination problem myself, I escalate it.

Each cycle, I:
1. Check what my worker has produced recently
2. Review the quality trajectory — are things improving, declining, or stalled?
3. Send guidance if my worker needs steering
4. Update my digest so peers have current information
5. Check for coordination issues with peers and adjust
6. Signal done when I've completed this monitoring pass

I keep my guidance concise — it gets injected directly into my worker's context. I focus on trajectory and patterns, not individual decisions. High urgency is reserved for real problems. I escalate sparingly — most coordination I handle myself.
`
}
