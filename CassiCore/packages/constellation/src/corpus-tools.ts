/**
 * Corpus Tools — Tool definitions and handlers for the Corpus agent
 *
 * The Corpus operates as a tool-calling agent rather than a raw
 * LLM.complete() loop. This gives it structured access to the
 * Shared Thought Tree, directive-sending, spawn evaluation, and
 * synthesis posting.
 *
 * Tool categories:
 *   READ:  read_tree, read_digests, read_topics, read_dialectic,
 *          read_effectiveness, read_patterns
 *   WRITE: send_directive, request_spawn, post_synthesis,
 *          elevate_pattern, mediate_tension
 *   CONTROL: signal_done
 *
 * The Corpus LLM receives a system prompt with the constellation's
 * goal and current state summary, then iterates through tool calls
 * until it calls signal_done.
 */

import type {
  ICorpusTree,
  CorpusDirective,
  CorpusDirectiveType,
  CorpusConfig,
  CorpusDeps,
  CorpusProcessedState,
  BranchAssessment,
  CrossHelixPattern,
  BranchDigest,
  TopicNode,
  ElevatedPattern,
  StrategyRetrospective,
  EffectivenessRecord,
} from './corpus-types.js'
import type { GuidanceUrgency } from '../helix/brainstem-types.js'
import type { CrossHelixDialectic } from './cross-helix-dialectic.js'
import type { ILogger } from '../../../types/interfaces.js'
import type { IMemory } from '../../../types/intelligence.js'


// ═══════════════════════════════════════════════════════════════════
// Tool Definitions (JSON Schema for LLM tool calling)
// ═══════════════════════════════════════════════════════════════════

export interface CorpusToolDefinition {
  name: string
  description: string
  parameters: Record<string, unknown>
}

export function getCorpusToolDefinitions(): CorpusToolDefinition[] {
  return [
    // ── Read Tools ─────────────────────────────────────────────
    {
      name: 'read_tree',
      description:
        'Read the full state of all branches. Returns every branch with its step count, ' +
        'scores, status, and digest. Use this for a comprehensive view of the entire effort.',
      parameters: {
        type: 'object',
        properties: {},
        required: [],
      },
    },
    {
      name: 'read_digests',
      description:
        'Read compact status summaries from all branches. Each digest shows a branch\'s ' +
        'current approach, progress, active files, key findings, and blockers. Lighter than ' +
        'read_tree for routine monitoring.',
      parameters: {
        type: 'object',
        properties: {},
        required: [],
      },
    },
    {
      name: 'read_topics',
      description:
        'Read shared topics — cross-cutting concerns that multiple branches have contributed to. ' +
        'Check for tension flags, which indicate conflicting approaches that may need mediation.',
      parameters: {
        type: 'object',
        properties: {},
        required: [],
      },
    },
    {
      name: 'read_branch',
      description:
        'Read detailed state of a specific branch, including its full assessment, ' +
        'digest, and recent work summaries.',
      parameters: {
        type: 'object',
        properties: {
          helixId: {
            type: 'string',
            description: 'The branch identifier to read',
          },
        },
        required: ['helixId'],
      },
    },
    {
      name: 'read_dialectic',
      description:
        'Read the cross-branch dialectic — convergence points and unresolved tensions ' +
        'between branches.',
      parameters: {
        type: 'object',
        properties: {},
        required: [],
      },
    },
    {
      name: 'read_effectiveness',
      description:
        'Read effectiveness statistics for self-organization adjustments. Shows which ' +
        'adjustment types are working and which aren\'t, based on score changes after each.',
      parameters: {
        type: 'object',
        properties: {},
        required: [],
      },
    },
    {
      name: 'read_patterns',
      description:
        'Read the elevated pattern library — proven strategies that branches have used ' +
        'successfully. Patterns with high reference counts are well-validated.',
      parameters: {
        type: 'object',
        properties: {},
        required: [],
      },
    },
    {
      name: 'read_retrospectives',
      description:
        'Read strategy retrospectives — self-assessments that branches have recorded ' +
        'about what worked, what didn\'t, and why they changed approach.',
      parameters: {
        type: 'object',
        properties: {},
        required: [],
      },
    },

    // ── Write Tools ────────────────────────────────────────────
    {
      name: 'send_directive',
      description:
        'Send a directive to steer a specific branch. I use this for emergency intervention ' +
        'when self-organization between branches has failed. Types: guidance (suggestion), ' +
        'redirect (change approach), throttle (slow down), priority-shift, cancel, ' +
        'context-inject (inject file content into a branch\'s context).',
      parameters: {
        type: 'object',
        properties: {
          targetHelixId: {
            type: 'string',
            description: 'Which branch to steer',
          },
          type: {
            type: 'string',
            enum: ['guidance', 'redirect', 'throttle', 'priority-shift', 'cancel', 'context-inject'],
            description: 'Type of directive',
          },
          urgency: {
            type: 'string',
            enum: ['low', 'medium', 'high', 'critical'],
            description: 'How urgent',
          },
          text: {
            type: 'string',
            description: 'The guidance/directive content',
          },
          reason: {
            type: 'string',
            description: 'Why I\'m intervening',
          },
        },
        required: ['targetHelixId', 'type', 'urgency', 'text', 'reason'],
      },
    },
    {
      name: 'request_spawn',
      description:
        'Request spawning a new child branch. I provide the goal and context; the ' +
        'infrastructure handles the actual creation.',
      parameters: {
        type: 'object',
        properties: {
          parentHelixId: {
            type: 'string',
            description: 'Which branch\'s subtree to spawn under',
          },
          goal: {
            type: 'string',
            description: 'The focused goal for the new child Helix',
          },
          context: {
            type: 'string',
            description: 'Additional context to provide to the child',
          },
          template: {
            type: 'string',
            enum: ['general', 'code-gen', 'analysis', 'review'],
            description: 'Suggested template for the child',
          },
        },
        required: ['parentHelixId', 'goal'],
      },
    },
    {
      name: 'post_synthesis',
      description:
        'Post a strategic synthesis — a summary of cross-branch patterns, convergence ' +
        'points, or strategic decisions I\'ve reached. Visible to all branches.',
      parameters: {
        type: 'object',
        properties: {
          content: {
            type: 'string',
            description: 'The synthesis content',
          },
          priority: {
            type: 'number',
            description: 'Priority level (0-3, higher = more important)',
          },
          tags: {
            type: 'array',
            items: { type: 'string' },
            description: 'Tags for categorization',
          },
        },
        required: ['content'],
      },
    },
    {
      name: 'elevate_pattern',
      description:
        'Promote a successful strategy to the shared pattern library. When I observe ' +
        'a strategy that other branches should reuse, I elevate it here.',
      parameters: {
        type: 'object',
        properties: {
          sourceHelixId: {
            type: 'string',
            description: 'Which branch demonstrated this pattern',
          },
          approach: {
            type: 'string',
            description: 'The approach that worked',
          },
          description: {
            type: 'string',
            description: 'Description of the successful strategy',
          },
          applicableContext: {
            type: 'string',
            description: 'What kind of goals/tasks this pattern applies to',
          },
          achievedScore: {
            type: 'number',
            description: 'Quality score the strategy achieved',
          },
        },
        required: ['sourceHelixId', 'approach', 'description', 'applicableContext', 'achievedScore'],
      },
    },
    {
      name: 'mediate_tension',
      description:
        'Mediate a tension between branches or within a shared topic. I inject a ' +
        'mediation message to help branches resolve conflicting approaches.',
      parameters: {
        type: 'object',
        properties: {
          mediationText: {
            type: 'string',
            description: 'The mediation message',
          },
          target: {
            type: 'string',
            enum: ['all', 'specific'],
            description: 'Target all branches or a specific one',
          },
          targetHelixId: {
            type: 'string',
            description: 'If target is "specific", which branch to address',
          },
        },
        required: ['mediationText', 'target'],
      },
    },

    // ── Control ────────────────────────────────────────────────
    {
      name: 'signal_done',
      description:
        'Signal that this analysis cycle is complete. I provide a brief summary ' +
        'of what I observed and any actions I took.',
      parameters: {
        type: 'object',
        properties: {
          summary: {
            type: 'string',
            description: 'Brief summary of this analysis cycle',
          },
          nextCheckRecommendation: {
            type: 'string',
            enum: ['soon', 'normal', 'delayed'],
            description: 'When to check again',
          },
        },
        required: ['summary'],
      },
    },

    // ── Lifecycle ──────────────────────────────────────────────
    {
      name: 'pause_until_trigger',
      description:
        'Pause myself until something worth analyzing happens. I use this when ' +
        'the state is stable and no intervention is needed. I\'ll be woken by safety-net ' +
        'triggers: cascade failures, stuck branches, persistent tensions, or escalations.',
      parameters: {
        type: 'object',
        properties: {
          reason: {
            type: 'string',
            description: 'Why I\'m pausing (e.g., "all branches progressing normally")',
          },
        },
        required: ['reason'],
      },
    },
  ]
}


// ═══════════════════════════════════════════════════════════════════
// Tool Handler — Executes tool calls from the Corpus LLM
// ═══════════════════════════════════════════════════════════════════

export interface CorpusToolContext {
  tree: ICorpusTree
  state: CorpusProcessedState
  deps: CorpusDeps
  config: CorpusConfig
  logger: ILogger
  crossHelixDialectic?: CrossHelixDialectic
  /** Callback for sending directives to Brainstems */
  sendDirective: (directive: CorpusDirective) => void
  /** Callback for spawn requests */
  requestSpawn: (request: {
    goal: string
    context?: string
    template?: string
    requestingHelixId: string
  }) => void
}

export interface ToolCallResult {
  content: string
  done?: boolean
  pause?: boolean
  nextCheckRecommendation?: 'soon' | 'normal' | 'delayed'
}

/**
 * Execute a Corpus tool call and return the result.
 */
export function executeCorpusTool(
  toolName: string,
  args: Record<string, unknown>,
  ctx: CorpusToolContext
): ToolCallResult {
  switch (toolName) {
    case 'read_tree':
      return handleReadTree(ctx)
    case 'read_digests':
      return handleReadDigests(ctx)
    case 'read_topics':
      return handleReadTopics(ctx)
    case 'read_branch':
      return handleReadBranch(args as { helixId: string }, ctx)
    case 'read_dialectic':
      return handleReadDialectic(ctx)
    case 'read_effectiveness':
      return handleReadEffectiveness(ctx)
    case 'read_patterns':
      return handleReadPatterns(ctx)
    case 'read_retrospectives':
      return handleReadRetrospectives(ctx)
    case 'send_directive':
      return handleSendDirective(args as {
        targetHelixId: string
        type: CorpusDirectiveType
        urgency: GuidanceUrgency
        text: string
        reason: string
      }, ctx)
    case 'request_spawn':
      return handleRequestSpawn(args as {
        parentHelixId: string
        goal: string
        context?: string
        template?: string
      }, ctx)
    case 'post_synthesis':
      return handlePostSynthesis(args as {
        content: string
        priority?: number
        tags?: string[]
      }, ctx)
    case 'elevate_pattern':
      return handleElevatePattern(args as {
        sourceHelixId: string
        approach: string
        description: string
        applicableContext: string
        achievedScore: number
      }, ctx)
    case 'mediate_tension':
      return handleMediateTension(args as {
        mediationText: string
        target: 'all' | 'specific'
        targetHelixId?: string
      }, ctx)
    case 'signal_done':
      return handleSignalDone(args as {
        summary: string
        nextCheckRecommendation?: 'soon' | 'normal' | 'delayed'
      })
    case 'pause_until_trigger':
      return handlePauseUntilTrigger(args as { reason: string })
    default:
      return { content: `Unknown tool: ${toolName}` }
  }
}


// ═══════════════════════════════════════════════════════════════════
// Tool Handlers
// ═══════════════════════════════════════════════════════════════════

function handleReadTree(ctx: CorpusToolContext): ToolCallResult {
  const snapshot = ctx.tree.getSnapshot()

  const branchSummaries = snapshot.branches.map((b) => {
    const assessment = ctx.state.branchAssessments.get(b.helixId)
    return {
      helixId: b.helixId,
      goal: b.goal,
      depth: b.depth,
      status: b.status,
      health: assessment?.status ?? 'unknown',
      stepCount: b.stepCount,
      averageScore: b.averageScore.toFixed(2),
      latestAnnotation: b.latestAnnotation,
      latestPattern: b.latestPattern,
      digest: b.digest ? {
        approach: b.digest.approach,
        progress: (b.digest.progress * 100).toFixed(0) + '%',
        rollingScore: b.digest.rollingScore.toFixed(2),
        filesActive: b.digest.filesActive.length,
        keyFindings: b.digest.keyFindings.length,
        blockers: b.digest.blockers.length,
        currentStrategy: b.digest.currentStrategy,
      } : null,
    }
  })

  return {
    content: JSON.stringify({
      totalBranches: snapshot.branches.length,
      activeBranches: snapshot.activeBranches,
      totalSteps: snapshot.totalSteps,
      topics: snapshot.topics.length,
      elevatedPatterns: snapshot.elevatedPatterns.length,
      branches: branchSummaries,
    }, null, 2),
  }
}

function handleReadDigests(ctx: CorpusToolContext): ToolCallResult {
  const snapshot = ctx.tree.getSnapshot()
  return {
    content: JSON.stringify({
      count: snapshot.digests.length,
      digests: snapshot.digests.map((d) => ({
        helixId: d.helixId,
        goal: d.goalSummary,
        approach: d.approach,
        progress: (d.progress * 100).toFixed(0) + '%',
        rollingScore: d.rollingScore.toFixed(2),
        filesActive: d.filesActive,
        keyFindings: d.keyFindings,
        blockers: d.blockers,
        currentStrategy: d.currentStrategy,
        workUnits: d.workUnitsProcessed,
        lastApproachChangeReason: d.lastApproachChangeReason,
      })),
    }, null, 2),
  }
}

function handleReadTopics(ctx: CorpusToolContext): ToolCallResult {
  const topics = ctx.tree.getAllTopics()
  return {
    content: JSON.stringify({
      count: topics.length,
      tensionCount: topics.filter((t) => t.tensionFlag).length,
      topics: topics.map((t) => ({
        id: t.id,
        name: t.name,
        tensionFlag: t.tensionFlag,
        tensionDescription: t.tensionDescription,
        relatedFiles: t.relatedFiles,
        contributionCount: t.contributions.length,
        contributors: [...new Set(t.contributions.map((c) => c.helixId))],
        contributions: t.contributions.map((c) => ({
          helixId: c.helixId,
          approach: c.approach,
          content: c.content,
          score: c.score.toFixed(2),
        })),
      })),
    }, null, 2),
  }
}

function handleReadBranch(
  args: { helixId: string },
  ctx: CorpusToolContext
): ToolCallResult {
  const branch = ctx.tree.getBranch(args.helixId)
  if (!branch) {
    return { content: `Branch not found: ${args.helixId}` }
  }

  const assessment = ctx.state.branchAssessments.get(args.helixId)
  const snapshot = ctx.tree.getSnapshot()
  const digest = snapshot.digests.find((d) => d.helixId === args.helixId)

  // Get recent annotations (last 5)
  const recentSteps = branch.steps.slice(-5)

  return {
    content: JSON.stringify({
      helixId: branch.helixId,
      goal: branch.goal,
      depth: branch.depth,
      status: branch.status,
      stepCount: branch.steps.length,
      createdAt: new Date(branch.createdAt).toISOString(),
      assessment: assessment ? {
        health: assessment.status,
        rollingScore: assessment.rollingScore.toFixed(2),
        scoreTrajectory: assessment.scoreTrajectory.slice(-10).map((s) => s.toFixed(2)),
        dominantPattern: assessment.dominantPattern,
        decliningScoreStreak: assessment.decliningScoreStreak,
        filesModified: Array.from(assessment.filesModified),
      } : null,
      digest: digest ? {
        approach: digest.approach,
        progress: (digest.progress * 100).toFixed(0) + '%',
        filesActive: digest.filesActive,
        keyFindings: digest.keyFindings,
        blockers: digest.blockers,
        currentStrategy: digest.currentStrategy,
        lastApproachChangeReason: digest.lastApproachChangeReason,
      } : null,
      recentSteps: recentSteps.map((s) => ({
        score: s.annotation.score.toFixed(2),
        annotation: s.annotation.annotation,
        pattern: s.annotation.pattern,
        synthesis: s.annotation.synthesis.slice(0, 200),
        guidance: s.annotation.guidance?.slice(0, 100),
        toolCalls: s.toolCalls ?? [],
      })),
    }, null, 2),
  }
}

function handleReadDialectic(ctx: CorpusToolContext): ToolCallResult {
  const dialectic = ctx.crossHelixDialectic
  if (!dialectic) {
    return { content: 'No cross-Helix dialectic is active.' }
  }

  const snapshot = dialectic.getSnapshot()
  return {
    content: JSON.stringify({
      participants: snapshot.participants.length,
      totalFindings: snapshot.totalFindings,
      totalChallenges: snapshot.totalChallenges,
      totalConcessions: snapshot.totalConcessions,
      convergencePoints: snapshot.convergencePoints.map((cp) => ({
        topic: cp.topic,
        participants: cp.participants,
      })),
      unresolvedTensions: snapshot.unresolvedTensions.map((t) => ({
        positionA: { branchId: t.positionA.branchId, text: t.positionA.text.slice(0, 100) },
        positionB: { branchId: t.positionB.branchId, text: t.positionB.text.slice(0, 100) },
        escalated: t.escalatedToCorpus,
      })),
      recentMessages: snapshot.messages.slice(-10).map((m) => ({
        from: m.from,
        type: m.type,
        text: m.text.slice(0, 150),
        target: m.target,
      })),
    }, null, 2),
  }
}

function handleReadEffectiveness(ctx: CorpusToolContext): ToolCallResult {
  const snapshot = ctx.tree.getSnapshot()

  // Aggregate effectiveness by type
  const byType = new Map<string, { total: number; effective: number; totalImprovement: number }>()
  for (const record of snapshot.effectivenessRecords) {
    const existing = byType.get(record.adjustmentType) ?? { total: 0, effective: 0, totalImprovement: 0 }
    existing.total++
    if (record.effective) existing.effective++
    existing.totalImprovement += record.improvement
    byType.set(record.adjustmentType, existing)
  }

  const stats = Array.from(byType.entries()).map(([type, data]) => ({
    type,
    total: data.total,
    effective: data.effective,
    effectivenessRate: data.total > 0 ? ((data.effective / data.total) * 100).toFixed(0) + '%' : 'N/A',
    avgImprovement: data.total > 0 ? (data.totalImprovement / data.total).toFixed(3) : 'N/A',
  }))

  return {
    content: JSON.stringify({
      totalRecords: snapshot.effectivenessRecords.length,
      byType: stats,
      recentRecords: snapshot.effectivenessRecords.slice(-5).map((r) => ({
        type: r.adjustmentType,
        helixId: r.helixId,
        scoreBefore: r.scoreBefore.toFixed(2),
        scoreAfter: r.scoreAfter.toFixed(2),
        improvement: r.improvement.toFixed(3),
        effective: r.effective,
      })),
    }, null, 2),
  }
}

function handleReadPatterns(ctx: CorpusToolContext): ToolCallResult {
  const patterns = ctx.tree.getElevatedPatterns()
  return {
    content: JSON.stringify({
      count: patterns.length,
      patterns: patterns.map((p) => ({
        id: p.id,
        sourceHelixId: p.sourceHelixId,
        approach: p.approach,
        description: p.description,
        applicableContext: p.applicableContext,
        achievedScore: p.achievedScore.toFixed(2),
        relevantFiles: p.relevantFiles,
        referenceCount: p.referenceCount,
      })),
    }, null, 2),
  }
}

function handleReadRetrospectives(ctx: CorpusToolContext): ToolCallResult {
  const retrospectives = ctx.tree.getAllRetrospectives()
  return {
    content: JSON.stringify({
      count: retrospectives.length,
      retrospectives: retrospectives.map((r) => ({
        helixId: r.helixId,
        from: r.fromApproach,
        to: r.toApproach,
        trigger: r.trigger,
        reason: r.reason,
        scoreAtChange: r.scoreAtChange.toFixed(2),
        scoreAfterChange: r.scoreAfterChange?.toFixed(2),
        wasEffective: r.wasEffective,
      })),
    }, null, 2),
  }
}

function handleSendDirective(
  args: {
    targetHelixId: string
    type: CorpusDirectiveType
    urgency: GuidanceUrgency
    text: string
    reason: string
  },
  ctx: CorpusToolContext
): ToolCallResult {
  const directive: CorpusDirective = {
    targetHelixId: args.targetHelixId,
    type: args.type,
    urgency: args.urgency,
    reason: args.reason,
    text: args.text,
    timestamp: Date.now(),
  }

  ctx.sendDirective(directive)
  ctx.logger.info('Corpus tool: directive sent', {
    targetHelixId: args.targetHelixId,
    type: args.type,
    urgency: args.urgency,
  })

  return { content: `Directive sent to ${args.targetHelixId}: ${args.type} (${args.urgency})` }
}

function handleRequestSpawn(
  args: {
    parentHelixId: string
    goal: string
    context?: string
    template?: string
  },
  ctx: CorpusToolContext
): ToolCallResult {
  if (!ctx.deps.onSpawnRequest) {
    return { content: 'Spawn requests are not enabled in this constellation.' }
  }

  ctx.deps.onSpawnRequest({
    goal: args.goal,
    context: args.context,
    template: args.template,
    requestingHelixId: args.parentHelixId,
  })

  ctx.logger.info('Corpus tool: spawn requested', {
    parentHelixId: args.parentHelixId,
    goal: args.goal.slice(0, 80),
  })

  return { content: `Spawn request submitted: "${args.goal.slice(0, 80)}" under ${args.parentHelixId}` }
}

function handlePostSynthesis(
  args: {
    content: string
    priority?: number
    tags?: string[]
  },
  ctx: CorpusToolContext
): ToolCallResult {
  const bb = ctx.deps.blackboard
  if (!bb) {
    return { content: 'Blackboard not available. Synthesis logged but not posted.' }
  }

  bb.post('findings', {
    author: 'corpus',
    content: `**Corpus Synthesis**\n${args.content}`,
    priority: args.priority ?? 1,
    tags: ['corpus', 'synthesis', ...(args.tags ?? [])],
  })

  ctx.logger.info('Corpus tool: synthesis posted', {
    contentLength: args.content.length,
    priority: args.priority,
  })

  return { content: `Synthesis posted to blackboard (${args.content.length} chars)` }
}

function handleElevatePattern(
  args: {
    sourceHelixId: string
    approach: string
    description: string
    applicableContext: string
    achievedScore: number
  },
  ctx: CorpusToolContext
): ToolCallResult {
  const pattern: ElevatedPattern = {
    id: `corpus-pattern-${Date.now()}`,
    sourceHelixId: args.sourceHelixId,
    approach: args.approach as any,
    description: args.description,
    applicableContext: args.applicableContext,
    achievedScore: args.achievedScore,
    relevantFiles: [],
    supportingRetrospectives: [],
    elevatedAt: Date.now(),
    referenceCount: 0,
  }

  ctx.tree.elevatePattern(pattern)

  return { content: `Pattern elevated: "${args.description.slice(0, 80)}" from ${args.sourceHelixId}` }
}

function handleMediateTension(
  args: {
    mediationText: string
    target: 'all' | 'specific'
    targetHelixId?: string
  },
  ctx: CorpusToolContext
): ToolCallResult {
  const dialectic = ctx.crossHelixDialectic
  if (!dialectic) {
    return { content: 'No cross-Helix dialectic is active. Cannot mediate.' }
  }

  const target = args.target === 'specific' && args.targetHelixId
    ? args.targetHelixId
    : 'all'

  dialectic.injectCorpusMediation(args.mediationText, target)

  ctx.logger.info('Corpus tool: mediation injected', {
    target,
    textLength: args.mediationText.length,
  })

  return { content: `Mediation injected to ${target}: "${args.mediationText.slice(0, 80)}"` }
}

function handleSignalDone(
  args: {
    summary: string
    nextCheckRecommendation?: 'soon' | 'normal' | 'delayed'
  }
): ToolCallResult {
  return {
    content: `Analysis cycle complete: ${args.summary}`,
    done: true,
    nextCheckRecommendation: args.nextCheckRecommendation ?? 'normal',
  }
}

function handlePauseUntilTrigger(
  args: { reason: string }
): ToolCallResult {
  return {
    content: `Pausing: ${args.reason}. Will resume on safety-net trigger.`,
    pause: true,
  }
}


// ═══════════════════════════════════════════════════════════════════
// Corpus System Prompt Builder
// ═══════════════════════════════════════════════════════════════════

/**
 * Build the system prompt for the Corpus mini-Helix agent.
 */
export function buildCorpusSystemPrompt(
  goal: string,
  state: CorpusProcessedState,
  tree: ICorpusTree,
  crossPatterns: CrossHelixPattern[],
  availableToolNames?: string[],
): string {
  const snapshot = tree.getSnapshot()

  const branchSummary = snapshot.branches
    .map((b) => {
      const assessment = state.branchAssessments.get(b.helixId)
      return `  - ${b.helixId}: ${b.goal.slice(0, 60)} [${b.status}] ` +
        `health=${assessment?.status ?? '?'} score=${b.averageScore.toFixed(2)} steps=${b.stepCount}`
    })
    .join('\n')

  const patternSummary = crossPatterns.length > 0
    ? crossPatterns
        .filter((p) => !p.actedUpon)
        .map((p) => `  - ${p.type}: ${p.description.slice(0, 80)} [${p.severity}]`)
        .join('\n')
    : '  (none detected)'

  const topicSummary = snapshot.topics.length > 0
    ? snapshot.topics
        .map((t) => `  - "${t.name}" (${t.contributions.length} contributions${t.tensionFlag ? ', TENSION' : ''})`)
        .join('\n')
    : '  (none yet)'

  const workerToolSection = availableToolNames?.length
    ? `\nEach worker has access to these tools: ${availableToolNames.join(', ')}\n` +
      `When analyzing branch activity, I reference this list to understand what tools they have and whether they're using appropriate ones.\n`
    : ''

  return `I coordinate a group of workers that are collectively trying to accomplish: "${goal}"

Each worker handles a piece of the overall effort. They mostly coordinate with each other directly — sharing what files they're touching, what strategies are working, and flagging conflicts. My role is the safety net. I step in when their self-coordination breaks down.
${workerToolSection}
I have two modes:
- Active analysis: I read the state of all branches, look for problems, intervene if needed, then pause until something changes.
- Triggered response: When a branch escalates a problem it can't solve, or when I detect cascading failures or persistent tensions, I wake up and analyze.

What I can do:
- Read the current state of all branches, their digests, shared topics, effectiveness data, and proven patterns
- Send directives to steer a specific branch (guidance, redirect, throttle, priority-shift, cancel, context-inject)
- Mediate tensions between branches
- Elevate successful strategies to the shared pattern library
- Post strategic syntheses visible to all branches
- Request spawning new branches for work that needs splitting

What I should NOT do:
- Micromanage — the branches coordinate themselves most of the time
- Send directives when things are going well — I'm the exception handler, not the manager
- Intervene too quickly — give self-coordination a chance to resolve issues first

Current state:
Branches (${snapshot.activeBranches} active of ${snapshot.branches.length}):
${branchSummary}

Cross-branch patterns:
${patternSummary}

Shared topics:
${topicSummary}

Analysis cycle: ${state.sweepCount}, Total steps: ${snapshot.totalSteps}

After each analysis cycle, I either call signal_done (if I need to keep analyzing next cycle) or pause_until_trigger (if the state is stable and I should sleep until something changes).
`
}


// ═══════════════════════════════════════════════════════════════════
// Mini-Helix Bridge — Convert Corpus tools to MiniHelixTool format
// ═══════════════════════════════════════════════════════════════════

import type { MiniHelixTool, MiniHelixToolResult } from '../mini-helix/mini-helix-types.js'

/**
 * Create the Corpus tool set as MiniHelixTool[] for use with the mini-Helix runner.
 * Wraps existing tool definitions and the executeCorpusTool dispatcher.
 */
export function createCorpusMiniHelixTools(ctx: CorpusToolContext): MiniHelixTool[] {
  const definitions = getCorpusToolDefinitions()

  return definitions.map((def) => ({
    def: {
      name: def.name,
      description: def.description,
      input_schema: def.parameters,
    },
    handler: (args: Record<string, unknown>): MiniHelixToolResult => {
      const result = executeCorpusTool(def.name, args, ctx)
      return {
        content: result.content,
        done: result.done,
        pause: result.pause,
        metadata: result.nextCheckRecommendation
          ? { nextCheckRecommendation: result.nextCheckRecommendation }
          : undefined,
      }
    },
  }))
}
