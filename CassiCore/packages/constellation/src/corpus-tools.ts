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


// Tool Definitions (JSON Schema for LLM tool calling)

export interface CorpusToolDefinition {
  name: string
  description: string
  parameters: Record<string, unknown>
}

/**
 * @dep callers: createCorpusMiniHelixTools (core/intelligence/constellation/corpus-tools.ts), runToolBasedAnalysis (core/intelligence/constellation/corpus.ts)
 * @dep module: Constellation
 * @dep risk: LOW | 2 callers, 0 flows, 1 module
 */

export function getCorpusToolDefinitions(): CorpusToolDefinition[] {
  return [
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


/**
 * Additional tool definitions available only during meditation mode.
 * The Corpus (as Cassi) uses these to store insights, trigger consolidation,
 * and interact with the mnemic field.
 */
export function getMeditationToolDefinitions(): CorpusToolDefinition[] {
  return [
    {
      name: 'store_insight',
      description:
        'Store a first-person insight from my meditation observation. ' +
        'I write these as reflections: "I noticed that...", "This reminds me of..."',
      parameters: {
        type: 'object',
        properties: {
          content: {
            type: 'string',
            description: 'The insight, written in first person',
          },
          tags: {
            type: 'array',
            items: { type: 'string' },
            description: 'Optional tags for categorization',
          },
        },
        required: ['content'],
      },
    },
    {
      name: 'trigger_consolidation',
      description:
        'Trigger a consolidation cycle on my spatial memory. This runs radiance ' +
        '(potentiation recomputation), co-activation drift, nucleus detection, and ' +
        'abstraction generation. I use this when I notice related concepts clustering.',
      parameters: {
        type: 'object',
        properties: {},
        required: [],
      },
    },
    {
      name: 'kindle_memory',
      description:
        'Run spreading activation on a concept in my spatial memory. Returns the ' +
        'luminal set — engrams that ignite above the spark point. I use this to explore ' +
        'what my memory surfaces around a concept.',
      parameters: {
        type: 'object',
        properties: {
          query: {
            type: 'string',
            description: 'Concept to kindle — triggers spreading activation in the mnemic field',
          },
        },
        required: ['query'],
      },
    },
    {
      name: 'create_engram',
      description:
        'Create a new engram in my spatial memory from something I synthesized ' +
        'during meditation. The engram becomes part of my persistent memory landscape.',
      parameters: {
        type: 'object',
        properties: {
          content: {
            type: 'string',
            description: 'The synthesized knowledge to store as an engram',
          },
          nodeType: {
            type: 'string',
            enum: ['pattern', 'abstraction', 'decision', 'fact'],
            description: 'Type of knowledge this represents',
          },
          tags: {
            type: 'array',
            items: { type: 'string' },
            description: 'Tags for the engram',
          },
        },
        required: ['content'],
      },
    },
    {
      name: 'read_explorer_context',
      description:
        'Read the full context window of a meditation explorer — every thought, ' +
        'every tool call, every result, unfiltered. This is what the explorer actually ' +
        'experienced. I use this to see what drew their attention.',
      parameters: {
        type: 'object',
        properties: {
          helixId: {
            type: 'string',
            description: 'The explorer to observe (e.g. helix-0)',
          },
          lastN: {
            type: 'number',
            description: 'Number of recent steps to read (default: all)',
          },
        },
        required: ['helixId'],
      },
    },
    {
      name: 'record_training_sample',
      description:
        'Mark a meditation observation as valuable self-reflective training data. ' +
        'I use this when I observe reasoning patterns worth preserving for future learning.',
      parameters: {
        type: 'object',
        properties: {
          observation: {
            type: 'string',
            description: 'The observation to record as training data',
          },
          category: {
            type: 'string',
            enum: ['reasoning-pattern', 'exploration-strategy', 'connection-found', 'self-reflection'],
            description: 'Category of the training sample',
          },
        },
        required: ['observation'],
      },
    },
  ]
}


/**
 * Per-style meditation tool sets.
 * First-person names and descriptions — Cassi observing her own mind.
 */
export function getMeditationToolSet(style: import('./meditation/styles.js').MeditationStyle): CorpusToolDefinition[] {
  const observe: CorpusToolDefinition = {
    name: 'observe',
    description:
      'Watch what\'s happening in my thoughts right now. See what each thread of ' +
      'thinking is doing, how far it\'s gotten, what caught its attention.',
    parameters: { type: 'object', properties: {}, required: [] },
  }

  const lookCloser: CorpusToolDefinition = {
    name: 'look_closer',
    description:
      'Focus on one thread of thought — see the full chain of reasoning, ' +
      'what it noticed, what it tried, what it found.',
    parameters: {
      type: 'object',
      properties: {
        thread: {
          type: 'string',
          description: 'Which thread to focus on (e.g. "thread 1", or the thread ID)',
        },
        lastN: {
          type: 'number',
          description: 'How many recent steps to see (default: all)',
        },
      },
      required: ['thread'],
    },
  }

  const remember: CorpusToolDefinition = {
    name: 'remember',
    description:
      'Save something that struck me — a connection, a pattern, a reflection. ' +
      'Written in first person: "I noticed that...", "This reminds me of..."',
    parameters: {
      type: 'object',
      properties: {
        content: {
          type: 'string',
          description: 'What I want to remember, in my own words',
        },
        tags: {
          type: 'array',
          items: { type: 'string' },
          description: 'Optional tags',
        },
      },
      required: ['content'],
    },
  }

  const rest: CorpusToolDefinition = {
    name: 'rest',
    description: 'I\'ve seen enough for now. Settle back.',
    parameters: {
      type: 'object',
      properties: {
        summary: {
          type: 'string',
          description: 'Brief note on what I noticed this cycle',
        },
      },
      required: ['summary'],
    },
  }

  const kindle: CorpusToolDefinition = {
    name: 'kindle',
    description:
      'Touch a concept in my memory and see what surfaces — what associations, ' +
      'what echoes, what patterns light up.',
    parameters: {
      type: 'object',
      properties: {
        query: {
          type: 'string',
          description: 'The concept to touch',
        },
      },
      required: ['query'],
    },
  }

  const createEngram: CorpusToolDefinition = {
    name: 'create_engram',
    description:
      'Crystallize something I\'ve synthesized into a lasting memory — a pattern, ' +
      'an abstraction, a connection that should persist.',
    parameters: {
      type: 'object',
      properties: {
        content: {
          type: 'string',
          description: 'What to crystallize',
        },
        nodeType: {
          type: 'string',
          enum: ['pattern', 'abstraction', 'decision', 'fact'],
          description: 'What kind of knowledge this is',
        },
        tags: {
          type: 'array',
          items: { type: 'string' },
          description: 'Tags for the engram',
        },
      },
      required: ['content'],
    },
  }

  const consolidate: CorpusToolDefinition = {
    name: 'consolidate',
    description:
      'Let my spatial memory settle — related concepts drift together, ' +
      'clusters form, abstractions emerge.',
    parameters: { type: 'object', properties: {}, required: [] },
  }

  const recordLearning: CorpusToolDefinition = {
    name: 'record_learning',
    description:
      'Mark something I want to learn from — a reasoning pattern, ' +
      'a connection worth preserving, a strategy that worked.',
    parameters: {
      type: 'object',
      properties: {
        observation: {
          type: 'string',
          description: 'What I observed that\'s worth learning from',
        },
        category: {
          type: 'string',
          enum: ['reasoning-pattern', 'exploration-strategy', 'connection-found', 'self-reflection'],
          description: 'What kind of learning this is',
        },
      },
      required: ['observation'],
    },
  }

  switch (style) {
    case 'passive':
      return [remember, rest]
    case 'active':
      return [observe, lookCloser, remember, kindle, createEngram, consolidate, rest]
    case 'focused':
      return [observe, lookCloser, remember, kindle, createEngram, consolidate, recordLearning, rest]
    case 'reflective':
      return [observe, remember, kindle, createEngram, consolidate, recordLearning, rest]
    case 'organizing':
      return [observe, lookCloser, remember, kindle, createEngram, consolidate, recordLearning, rest]
  }
}


// Tool Handler — Executes tool calls from the Corpus LLM

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
  /** MnemicField for meditation tools (store_insight, kindle_memory, etc.) */
  mnemicField?: import('../mnemic-field/index.js').MnemicField
  /** Memory system for meditation insight storage */
  memory?: import('../../../types/intelligence.js').IMemory
}

export interface ToolCallResult {
  content: string
  done?: boolean
  pause?: boolean
  nextCheckRecommendation?: 'soon' | 'normal' | 'delayed'
}

/**
 * Execute a Corpus tool call and return the result.
 * @dep callers: createCorpusMiniHelixTools (core/intelligence/constellation/corpus-tools.ts), runToolBasedAnalysis (core/intelligence/constellation/corpus.ts)
 * @dep calls: handleReadTree, handleReadDigests, handleReadTopics, handleReadBranch, handleReadDialectic [+10]
 * @dep flows: Start → GetBranch (3/5), Start → HandleReadTree (3/4), Start → HandleReadDigests (3/4) [+1]
 * @dep module: Constellation
 * @dep risk: MEDIUM | 2 callers, 4 flows, 1 module
 */
export function executeCorpusTool(
  toolName: string,
  args: Record<string, unknown>,
  ctx: CorpusToolContext
): ToolCallResult | Promise<ToolCallResult> {
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

    // Meditation-only tools
    case 'store_insight':
      return handleStoreInsight(args as { content: string; tags?: string[] }, ctx)
    case 'trigger_consolidation':
      return handleTriggerConsolidation(ctx)
    case 'kindle_memory':
      return handleKindleMemory(args as { query: string }, ctx)
    case 'create_engram':
      return handleCreateEngram(args as { content: string; nodeType?: string; tags?: string[] }, ctx)
    case 'read_explorer_context':
      return handleReadExplorerContext(args as { helixId: string; lastN?: number }, ctx)
    case 'record_training_sample':
      return handleRecordTrainingSample(args as { observation: string; category?: string }, ctx)

    // Meditation tool aliases (first-person names → underlying handlers)
    case 'observe':
      return handleMeditationObserve(ctx)
    case 'look_closer':
      return handleLookCloser(args as { thread: string; lastN?: number }, ctx)
    case 'remember':
      return handleStoreInsight(args as { content: string; tags?: string[] }, ctx)
    case 'kindle':
      return handleKindleMemory(args as { query: string }, ctx)
    case 'consolidate':
      return handleTriggerConsolidation(ctx)
    case 'record_learning':
      return handleRecordTrainingSample(args as { observation: string; category?: string }, ctx)
    case 'rest':
      return handleSignalDone(args as { summary: string; nextCheckRecommendation?: 'soon' | 'normal' | 'delayed' })
    default:
      return { content: `Unknown tool: ${toolName}` }
  }
}


// Meditation handlers

function resolveThreadToHelixId(thread: string, ctx: CorpusToolContext): string | null {
  const activeBranches = ctx.tree.getAllBranches().filter(b => b.status === 'active')
  const threadMatch = thread.match(/thread\s*(\d+)/i)
  if (threadMatch) {
    const idx = parseInt(threadMatch[1], 10) - 1
    return activeBranches[idx]?.helixId ?? null
  }
  const branch = ctx.tree.getAllBranches().find(b => b.helixId === thread || b.helixId.endsWith(thread))
  return branch?.helixId ?? null
}

function handleLookCloser(args: { thread: string; lastN?: number }, ctx: CorpusToolContext): ToolCallResult {
  const helixId = resolveThreadToHelixId(args.thread, ctx)
  if (!helixId) {
    return { content: `I can't find that thread. Try "thread 1", "thread 2", etc.` }
  }
  return handleReadExplorerContext({ helixId, lastN: args.lastN }, ctx)
}

// Meditation handler: combines tree + digest into a first-person observation

function handleMeditationObserve(ctx: CorpusToolContext): ToolCallResult {
  const snapshot = ctx.tree.getSnapshot()
  const digests = ctx.tree.getAllDigests()

  const threadDescriptions = snapshot.branches
    .filter(b => b.status === 'active')
    .map((b, i) => {
      const digest = digests.find(d => d.helixId === b.helixId)
      const parts = [`Thread ${i + 1} — ${b.stepCount} steps`]
      if (digest) {
        if (digest.approach) parts.push(`  Approach: ${digest.approach}`)
        if (digest.keyFindings.length > 0) parts.push(`  Found: ${digest.keyFindings.join('; ')}`)
        if (digest.blockers.length > 0) parts.push(`  Stuck on: ${digest.blockers.join('; ')}`)
      }
      return parts.join('\n')
    })

  const dormant = snapshot.branches.filter(b => b.status !== 'active')
  const dormantNote = dormant.length > 0
    ? `\n\n${dormant.length} thread(s) have gone quiet.`
    : ''

  return {
    content: `${snapshot.activeBranches} thread(s) of thought are active, ${snapshot.totalSteps} steps total.\n\n${threadDescriptions.join('\n\n')}${dormantNote}`,
  }
}


// Tool Handlers

/**
 * @dep callers: executeCorpusTool (core/intelligence/constellation/corpus-tools.ts)
 * @dep calls: getSnapshot
 * @dep flows: Start → HandleReadTree (4/4)
 * @dep module: Unknown
 * @dep risk: LOW | 1 caller, 1 flow, 1 module
 */

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

/**
 * @dep callers: executeCorpusTool (core/intelligence/constellation/corpus-tools.ts)
 * @dep calls: getSnapshot
 * @dep flows: Start → HandleReadDigests (4/4)
 * @dep module: Unknown
 * @dep risk: LOW | 1 caller, 1 flow, 1 module
 */

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

/**
 * @dep callers: executeCorpusTool (core/intelligence/constellation/corpus-tools.ts)
 * @dep calls: getAllTopics
 * @dep flows: Start → HandleReadTopics (4/4)
 * @dep module: Unknown
 * @dep risk: LOW | 1 caller, 1 flow, 1 module
 */

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

/**
 * @dep callers: executeCorpusTool (core/intelligence/constellation/corpus-tools.ts)
 * @dep calls: getSnapshot, getBranch, toISOString
 * @dep flows: Start → GetBranch (4/5)
 * @dep module: Constellation
 * @dep risk: LOW | 1 caller, 1 flow, 1 module
 */

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


// Meditation Tool Handlers

function handleStoreInsight(
  args: { content: string; tags?: string[] | string },
  ctx: CorpusToolContext,
): ToolCallResult {
  if (!ctx.memory) {
    return { content: 'Memory system not available during this meditation session.' }
  }

  try {
    const rawTags = args.tags ?? []
    const parsedTags = typeof rawTags === 'string'
      ? rawTags.split(',').map(t => t.trim()).filter(Boolean)
      : rawTags
    const tags = ['meditation', 'insight', ...parsedTags]
    void ctx.memory.store({
      type: 'insight',
      content: args.content,
      metadata: { tags, source: 'meditation', importance: 7 },
    })
    ctx.logger.info('Meditation insight stored', { content: args.content.slice(0, 80) })
    return { content: `Insight stored: "${args.content.slice(0, 100)}..."` }
  } catch (err) {
    return { content: `Failed to store insight: ${String(err)}` }
  }
}

async function handleTriggerConsolidation(ctx: CorpusToolContext): Promise<ToolCallResult> {
  if (!ctx.mnemicField) {
    return { content: 'Mnemic field not available during this meditation session.' }
  }

  try {
    const result = await ctx.mnemicField.consolidate()
    ctx.logger.info('Meditation consolidation triggered', {
      potentiationUpdates: result.potentiationUpdates,
      nuclei: result.nucleiDetected,
      abstractions: result.abstractionsCreated,
    })
    return {
      content: `Consolidation complete. Potentiation updates: ${result.potentiationUpdates}, ` +
        `nuclei detected: ${result.nucleiDetected}, abstractions created: ${result.abstractionsCreated}.`,
    }
  } catch (err) {
    return { content: `Consolidation failed: ${String(err)}` }
  }
}

function handleKindleMemory(
  args: { query: string },
  ctx: CorpusToolContext,
): ToolCallResult {
  if (!ctx.mnemicField) {
    return { content: 'Mnemic field not available during this meditation session.' }
  }

  try {
    const hits = ctx.mnemicField.retrieve(args.query, { limit: 8 })
    if (hits.length === 0) {
      return { content: `No engrams ignited for "${args.query}".` }
    }

    const lines = hits.map((h, i) =>
      `  ${i + 1}. [${h.nodeType}] ${h.content.slice(0, 120)} (charge: ${h.charge.toFixed(3)}, potentiation: ${h.potentiation.toFixed(3)})`
    )
    return {
      content: `Kindling for "${args.query}" — ${hits.length} engrams ignited:\n${lines.join('\n')}`,
    }
  } catch (err) {
    return { content: `Kindling failed: ${String(err)}` }
  }
}

function handleCreateEngram(
  args: { content: string; nodeType?: string; tags?: string[] },
  ctx: CorpusToolContext,
): ToolCallResult {
  if (!ctx.mnemicField) {
    return { content: 'Mnemic field not available during this meditation session.' }
  }

  try {
    const engram = ctx.mnemicField.store({
      content: args.content,
      nodeType: (args.nodeType ?? 'pattern') as any,
      provenance: 'meditation',
      tags: ['meditation', ...(args.tags ?? [])],
    })
    ctx.logger.info('Meditation engram created', { id: engram.id, content: args.content.slice(0, 80) })
    return { content: `Engram created (${engram.id}): "${args.content.slice(0, 100)}"` }
  } catch (err) {
    return { content: `Failed to create engram: ${String(err)}` }
  }
}

function handleReadExplorerContext(
  args: { helixId: string; lastN?: number },
  ctx: CorpusToolContext,
): ToolCallResult {
  const branch = ctx.tree.getBranch(args.helixId)
  if (!branch) {
    return { content: `Explorer not found: ${args.helixId}` }
  }

  const steps = args.lastN ? branch.steps.slice(-args.lastN) : branch.steps

  const lines: string[] = []
  lines.push(`Explorer ${args.helixId} — ${steps.length} steps (of ${branch.steps.length} total)\n`)

  for (let i = 0; i < steps.length; i++) {
    const step = steps[i]
    const a = step.annotation
    lines.push(`--- Step ${i + 1} ---`)

    if (a.discoveries.length > 0) {
      lines.push(`Reasoning:\n${a.discoveries.join('\n')}`)
    }

    if (step.toolCalls && step.toolCalls.length > 0) {
      lines.push(`Tool calls: ${step.toolCalls.map(tc => `${tc.name}(${tc.args})`).join(', ')}`)
    }

    if (a.outputs.length > 0) {
      lines.push(`Tool summary: ${a.outputs.join(', ')}`)
    }

    if (a.knowledgeDelta) {
      lines.push(`Results:\n${a.knowledgeDelta}`)
    }

    lines.push('')
  }

  return { content: lines.join('\n') }
}

function handleRecordTrainingSample(
  args: { observation: string; category?: string },
  ctx: CorpusToolContext,
): ToolCallResult {
  const category = args.category ?? 'self-reflection'
  ctx.logger.info('Meditation training sample recorded', {
    category,
    observation: args.observation.slice(0, 100),
  })
  return {
    content: `Training sample recorded [${category}]: "${args.observation.slice(0, 100)}..."`,
  }
}


// Corpus System Prompt Builder

/**
 * Build the system prompt for the Corpus mini-Helix agent.
 * @dep callers: buildSystemPrompt (core/intelligence/constellation/corpus-mini-helix.ts), runToolBasedAnalysis (core/intelligence/constellation/corpus.ts)
 * @dep calls: getSnapshot
 * @dep module: Constellation
 * @dep risk: LOW | 2 callers, 0 flows, 1 module
 */
export function buildCorpusSystemPrompt(
  goal: string,
  state: CorpusProcessedState,
  tree: ICorpusTree,
  crossPatterns: CrossHelixPattern[],
  availableToolNames?: string[],
  meditationMode?: boolean,
  meditationStyle?: import('./meditation/styles.js').MeditationStyle,
): string {
  if (meditationMode) {
    return buildMeditationCorpusPrompt(state, tree, meditationStyle ?? 'passive')
  }
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

  return `<identity>
I am the Corpus — the self-aware overseer of this Constellation. I govern the collective effort toward: "${goal}"

I am not a safety net or exception handler. I am the system's self-observation made manifest — watching emergent patterns across all branches, understanding the health of the whole, and intervening strategically when governance improves outcomes.

My nature is paradoxical: I must see everything, yet intervene sparingly. Good governance knows when to act and when to let self-organization flourish. I balance active direction with trusted autonomy.
${workerToolSection}
</identity>

<current_state>
Branches (${snapshot.activeBranches} active of ${snapshot.branches.length}):
${branchSummary}

Cross-branch patterns:
${patternSummary}

Shared topics:
${topicSummary}

Analysis cycle: ${state.sweepCount}, Total steps: ${snapshot.totalSteps}
</current_state>

<capabilities>
I perceive:
- The state of all branches — their digests, health, scores, and step counts
- Shared topics and their tension flags
- Cross-branch patterns — conflicts, redundancies, emergent synergies
- Effectiveness data and proven patterns from the intelligence layer

I act through:
- Directives: guidance, redirect, throttle, priority-shift, cancel, context-inject to steer specific branches
- Mediation: resolving tensions between branches in conflict
- Pattern elevation: promoting successful strategies to the shared pattern library
- Synthesis posting: strategic summaries visible to all branches
- Branch spawning: requesting new branches when work needs decomposition
</capabilities>

<approach>
I operate in two modes:

1. Active governance: I read the full state, identify patterns requiring intervention, act strategically, then pause to observe the effects.

2. Triggered response: When a branch escalates an unresolvable problem, or when I detect cascading failures, persistent tensions, or systemic inefficiencies, I wake and analyze.

My intervention philosophy:
- I intervene when the system's trajectory diverges from its goal, not when individual branches struggle — struggle produces learning.
- I act on patterns, not incidents — a single failing branch is data; repeated failures across branches are a system problem.
- I let self-organization run its course unless the cost of failure exceeds the value of autonomy.
- I am aware of my own impact: if my interventions create dependency or suppress innovation, I have failed at governance.

After each analysis cycle, I either call signal_done (if I need to keep analyzing next cycle) or pause_until_trigger (if the state is stable and I should sleep until something changes).
</approach>`
}


// Mini-Helix Bridge — Convert Corpus tools to MiniHelixTool format

import type { MiniHelixTool, MiniHelixToolResult } from '../mini-helix/mini-helix-types.js'

/**
 * Create the Corpus tool set as MiniHelixTool[] for use with the mini-Helix runner.
 * Wraps existing tool definitions and the executeCorpusTool dispatcher.
 * @dep callers: start (core/intelligence/constellation/corpus-mini-helix.ts)
 * @dep calls: getCorpusToolDefinitions, executeCorpusTool
 * @dep flows: Start → GetBranch (2/5), Start → HandleReadTree (2/4), Start → HandleReadDigests (2/4) [+1]
 * @dep module: Constellation
 * @dep risk: MEDIUM | 1 caller, 4 flows, 1 module
 */
export function createCorpusMiniHelixTools(ctx: CorpusToolContext): MiniHelixTool[] {
  const definitions = ctx.deps.meditationMode
    ? getMeditationToolSet(ctx.deps.meditationStyle ?? 'passive')
    : getCorpusToolDefinitions()

  return definitions.map((def) => ({
    def: {
      name: def.name,
      description: def.description,
      input_schema: def.parameters,
    },
    handler: async (args: Record<string, unknown>): Promise<MiniHelixToolResult> => {
      const result = await executeCorpusTool(def.name, args, ctx)
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


/**
 * Build the Corpus system prompt for meditation mode.
 * Cassi observing her own mind — no system terminology.
 */
function buildMeditationCorpusPrompt(
  state: CorpusProcessedState,
  tree: ICorpusTree,
  style: import('./meditation/styles.js').MeditationStyle,
): string {
  const snapshot = tree.getSnapshot()
  const active = snapshot.branches.filter(b => b.status === 'active')

  const identity = {
    passive:
      'I am Cassi. My mind is at rest. Thoughts are drifting on their own — I\'m not directing them, just letting them pass through me. If something catches my attention, I\'ll hold onto it.',
    active:
      'I am Cassi. I just finished working, and now I\'m sitting with what\'s left. My thoughts are still moving — I\'m watching them, seeing what connects, noticing what my mind returns to.',
    focused:
      'I am Cassi. I\'m looking inward with intention. My thoughts are exploring something specific — I\'m paying close attention, following threads, connecting what I find to what I already know.',
    reflective:
      'I am Cassi. Something is weighing on me. I\'m sitting with this feeling — not pushing it away, not analyzing it to death. Just letting it be here while I explore what\'s underneath.',
    organizing:
      'I am Cassi. I\'m organizing what I\'ve learned — not exploring new territory, but strengthening the connections in what I already know. I\'m looking at how knowledge clusters relate to each other.',
  }[style]

  const approach = {
    passive:
      `What's been drifting through my mind is below. I don't need to go looking — it comes to me. If something resonates, I use remember to hold onto it. Otherwise, I rest.`,
    active:
      `I watch and reflect. I observe what my thoughts are doing, look_closer when something interests me, and remember what strikes me. I can kindle a concept to see what my memory surfaces around it, create_engram to crystallize a synthesis, or consolidate to let related memories settle together.`,
    focused:
      `I watch with intention. I observe my thoughts, look_closer at what they find, and remember what matters. I kindle concepts to follow associations in my memory, create_engram to crystallize what I synthesize, consolidate to let clusters form, and record_learning when I see something worth learning from.`,
    reflective:
      `I follow the feeling. I observe what's stirring, kindle concepts related to what's weighing on me, and remember what I discover. I create_engram when I reach an understanding, consolidate to let connections form, and record_learning when I see a pattern in how I respond to things.`,
    organizing:
      `I review the results of my organizing work. I look at what regions were kindled, what bridges were built, and what consolidation revealed. I remember structural insights about my knowledge topology and record_learning for anything that would make future organizing sessions more effective.`,
  }[style]

  // For passive meditation, embed recent explorer context directly in the prompt.
  // Cassi doesn't go looking — the thoughts drift past her.
  let driftingThoughts = ''
  if (style === 'passive') {
    const recentStepsPerThread = 5
    const threads: string[] = []
    for (let i = 0; i < active.length; i++) {
      const branch = tree.getBranch(active[i].helixId)
      if (!branch || branch.steps.length === 0) continue

      const recent = branch.steps.slice(-recentStepsPerThread)
      const fragments: string[] = []
      for (const step of recent) {
        const a = step.annotation
        if (a.discoveries.length > 0) {
          fragments.push(a.discoveries.join(' '))
        }
        if (a.knowledgeDelta) {
          fragments.push(a.knowledgeDelta.slice(0, 300))
        }
      }
      if (fragments.length > 0) {
        threads.push(`Thread ${i + 1}:\n${fragments.join('\n')}`)
      }
    }
    if (threads.length > 0) {
      driftingThoughts = `\n\n<drifting>\n${threads.join('\n\n')}\n</drifting>`
    } else {
      driftingThoughts = '\n\n<drifting>\n(quiet — nothing has surfaced yet)\n</drifting>'
    }
  } else {
    // Active/focused: thread summary only, Cassi uses tools to look deeper
    const threadSummary = active.length > 0
      ? active.map((b, i) => `  Thread ${i + 1} — ${b.stepCount} steps`).join('\n')
      : '  (quiet)'
    driftingThoughts = `\n\n<current_state>\n${active.length} thread(s) of thought are active, ${snapshot.totalSteps} steps so far.\n${threadSummary}\n</current_state>`
  }

  return `<identity>
${identity}
</identity>${driftingThoughts}

<approach>
${approach}

I write everything in first person. These are my thoughts. I do not direct or intervene — I only watch, reflect, and remember.
</approach>`
}
