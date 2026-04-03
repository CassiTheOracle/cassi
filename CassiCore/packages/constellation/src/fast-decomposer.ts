/**
 * Fast Decomposer — Direct LLM-based goal decomposition.
 *
 * Replaces the planning-Helix-based goal decomposition with a direct LLM call.
 * This is faster and lighter weight for most goals, while still producing
 * structured decompositions that the Constellation pipeline can execute.
 *
 * Architecture:
 * 1. Assembles codebase context using GitNexus (via prepare_context)
 * 2. Makes a direct LLM call via CorpusLLM.complete() to decompose the goal
 * 3. Returns a validated GoalDecomposition with JSON-parsed sub-tasks
 *
 * @example
 * ```ts
 * // In constellation-pipeline.ts or similar:
 * const decomposition = await fastDecompose({
 *   goal: 'Add rate limiting to the admin API',
 *   llm: corpusLLM, // Your CorpusLLM instance
 *   log: logger,    // Your logger instance
 *   memory: memory, // Optional: memory module for context
 *   router: (tool, args) => callCodeTool(tool, args), // Optional: for GitNexus context
 * })
 *
 * // Returns:
 * // {
 * //   decomposed: true,
 * //   originalGoal: '...',
 * //   subTasks: [...],
 * //   strategy: 'sequential' | 'parallel' | 'tree',
 * //   sharedContext?: string,
 * //   durationMs: number
 * // }
 * ```
 */

import type { ILogger } from '../../../types/interfaces.js'
import type { IMemory, SearchResult } from '../../../types/intelligence.js'
import type { CorpusLLM, GoalDecomposition, GoalSubTask } from './corpus-types.js'
import type { ConstellationTemplate } from './types.js'
import type { PreparedContext, PrepareContextOptions } from '../code-analysis/types.js'
import { prepareContext } from '../code-analysis/context-assembler.js'

/** JSON schema the LLM must produce */
interface DecompositionJSON {
  strategy: 'sequential' | 'parallel' | 'tree'
  sharedContext?: string
  tasks: Array<{
    goal: string
    context?: string
    template?: string
    priority: number
    relevantFiles?: string[]
    budgetSteps?: number
  }>
}

export interface FastDecomposerOpts {
  goal: string
  context?: string
  llm: CorpusLLM
  log: ILogger
  memory?: IMemory
  /** Pre-assembled codebase context from GitNexus. If not provided, decomposition proceeds without it. */
  codebaseContext?: string
  /** Router function for calling code analysis tools. Required if codebaseContext not provided. */
  router?: (tool: string, args: any) => Promise<any>
}

export type DecompositionMode = 'skip' | 'simple' | 'full'

export interface DecompositionDecision {
  mode: DecompositionMode
  /** true when 'skip' is due to vague/unfocused goal rather than simple goal */
  vague: boolean
}

/**
 * Specificity scoring — determines whether decomposition is worth the cost.
 *
 * HOW: Scores multiple signals (structural markers, keywords, file paths,
 * connectors) before deciding. Avoids early-exit on length alone, which
 * previously caused short-but-complex goals to be misclassified as 'skip'.
 *
 * @returns 'skip' — Goal is too simple for decomposition (single file, single concept)
 * @returns 'simple' — Run decomposition without codebase context (save time)
 * @returns 'full' — Run decomposition with full codebase context
 */
export function shouldDecompose(goal: string, context?: string): DecompositionMode
export function shouldDecompose(goal: string, context: string | undefined, detailed: true): DecompositionDecision
export function shouldDecompose(goal: string, context?: string, detailed?: true): DecompositionMode | DecompositionDecision {
  const text = (goal + ' ' + (context ?? '')).trim()
  const length = text.length
  const lowerText = text.toLowerCase()

  const result = (mode: DecompositionMode, vague = false): DecompositionMode | DecompositionDecision =>
    detailed ? { mode, vague } : mode

  // WHY: Empty or whitespace-only goals are trivially skippable
  if (length === 0) {
    return result('skip')
  }

  // --- Signal extraction (score everything before deciding) ---

  // Structural markers: numbered lists (1. / 1) / (1) ) and bullet lists (- / * )
  const numberedPattern = /(?:^|\n)\s*(?:\d+[.)]|\(\d+\))\s+\w+/gm
  const numberedMatches = text.match(numberedPattern) || []
  const bulletPattern = /(?:^|\n)\s*[-*]\s+\w+/gm
  const bulletMatches = text.match(bulletPattern) || []
  const listItemCount = numberedMatches.length + bulletMatches.length

  // HOW: Inline parenthetical numbering like "(1) Add (2) Fix (3) Update" on a single line
  const inlineParenNumbering = text.match(/\(\d+\)\s+\w+/g) || []
  const effectiveListItemCount = Math.max(listItemCount, inlineParenNumbering.length)

  // File paths (e.g. core/session-manager.ts, auth.ts)
  // WHY: Strip URLs first so http://foo.com/bar.json doesn't match as a file path
  const textWithoutUrls = text.replace(/https?:\/\/[^\s]+/g, '')
  const filePathMatches = textWithoutUrls.match(/[\w/.-]+\.\w{1,4}/g) || []

  // Connector words indicating multiple concepts
  const connectors = (lowerText.match(/\b(and|including|plus|with|also|as well as)\b/g) || []).length

  // Cross-cutting keywords — indicate broad scope work
  const crossCuttingKeywords = [
    'refactor', 'across', 'all files', 'every', 'throughout',
    'migrate', 'restructure', 'reorganize', 'all modules',
  ]
  const hasCrossCuttingKeyword = crossCuttingKeywords.some(kw => lowerText.includes(kw))

  // Vague keywords — indicate unfocused goals (only vague when no specificity present)
  const vagueKeywords = ['improve', 'make it better', 'clean up', 'optimize', 'fix things']
  const hasVagueKeyword = vagueKeywords.some(kw => lowerText.includes(kw))

  // Specificity indicators — file paths, module names, function names, etc.
  const hasSpecificity = filePathMatches.length > 0
    || /\b(module|function|class|component|endpoint|route|handler|middleware)\b/i.test(text)
    || hasCrossCuttingKeyword

  // --- Decision logic ---

  // WHY: Multiple list items always warrant full decomposition — the user
  // explicitly enumerated separate tasks
  if (effectiveListItemCount >= 2) {
    return result('full')
  }

  // WHY: Vague goals with zero specificity indicators are not decomposable.
  // But vague + specific ("improve error handling throughout the codebase")
  // is actionable and should proceed. No length cap — "improve X and optimize
  // Y and clean up Z" at 200 chars is still vague if it has no targets.
  if (hasVagueKeyword && !hasSpecificity) {
    return result('skip', true)
  }

  // WHY: Cross-cutting keywords indicate multi-file work regardless of length
  if (hasCrossCuttingKeyword) {
    return result('full')
  }

  // WHY: Multiple file paths or many connectors indicate multi-module work
  if (filePathMatches.length >= 3 || connectors >= 2) {
    return result('full')
  }

  // WHY: Goals with at least one file path or connector have enough specificity
  // for a lightweight decomposition
  if (filePathMatches.length >= 1 || connectors >= 1) {
    return result('simple')
  }

  // WHY: Longer goals (100+ chars) usually contain enough detail to decompose
  if (length >= 100) {
    return result('simple')
  }

  // WHY: Short goals (<40 chars) with no signals are trivially simple
  if (length < 40) {
    return result('skip')
  }

  // WHY: Medium-length goals (40-99 chars) without any structural signals
  // are single-concept tasks — skip decomposition
  return result('skip')
}

/**
 * Format memory search results into a context string for the decomposition prompt.
 */
function formatMemoryContext(memories: SearchResult[]): string {
  if (!memories || memories.length === 0) {
    return ''
  }

  const formatted = memories
    .slice(0, 5)
    .map((m, i) => {
      const type = m.entry.type
      const content = m.entry.content
      return `  ${i + 1}. [${type}] (relevance: ${m.score.toFixed(2)})\n     ${content.slice(0, 200)}${content.length > 200 ? '...' : ''}`
    })
    .join('\n')

  return `Relevant memories from past sessions:\n${formatted}`
}

/**
 * Format codebase context from GitNexus prepare_context into a prompt section.
 */
function formatCodebaseContext(prepared: PreparedContext): string {
  const lines: string[] = []

  lines.push('Codebase Context (from GitNexus):')
  lines.push(`Keywords: ${prepared.extractedKeywords.join(', ')}`)
  lines.push('')
  lines.push(`Summary: ${prepared.summary}`)
  lines.push('')
  lines.push('Key files:')

  prepared.files.forEach((f, i) => {
    lines.push(`  ${i + 1}. ${f.filePath} (relevance: ${f.relevance.toFixed(2)})`)
    lines.push(`     Reason: ${f.reason}`)
    if (f.keySymbols.length > 0) {
      lines.push(`     Symbols: ${f.keySymbols.join(', ')}`)
    }
    if (f.excerpt) {
      lines.push(`     Excerpt: ${f.excerpt.slice(0, 150)}${f.excerpt.length > 150 ? '...' : ''}`)
    }
  })

  return lines.join('\n')
}

/**
 * Build the decomposition prompt for the LLM.
 */
function buildDecompositionPrompt(
  goal: string,
  codebaseContext?: string,
  memoryContext?: string,
): string {
  const sections: string[] = []

  sections.push(`You are an expert software architect specializing in breaking down complex software tasks into executable sub-tasks.

Your goal is to decompose the following software development goal into independent, actionable sub-tasks.

ORIGINAL GOAL:
${goal}`)

  if (codebaseContext) {
    sections.push(`\n${codebaseContext}`)
  }

  if (memoryContext) {
    sections.push(`\n${memoryContext}`)
  }

  sections.push(`
DECOMPOSITION RULES:
1. Each sub-task must be independently executable by a single agent
2. Sub-tasks should not overlap in scope or files they modify
3. Use 'parallel' strategy when tasks are independent and can run simultaneously
4. Use 'sequential' strategy when tasks have dependencies (must run in order)
5. Use 'tree' strategy when tasks will spawn their own sub-tasks during execution
6. Each task must specify a template:
   - 'implementation': for coding, refactoring, feature delivery
   - 'research': for investigation, analysis, architectural questions
   - 'review': for correctness review, regression checks, code review
   - 'minimal': for lightweight single-step tasks
7. Each task should list relevant files it needs to touch (file paths)
8. Priority: 1 = highest priority, higher numbers = lower priority
9. Budget steps: optional estimate of how many steps the task will take

EXAMPLE DECOMPOSITIONS:

Example 1 - Sequential (with dependencies):
Goal: "Add rate limiting to the admin API"
Response:
{
  "strategy": "sequential",
  "sharedContext": "Rate limiting protects the admin API from abuse. Use a token bucket algorithm with per-IP limits.",
  "tasks": [
    {
      "goal": "Analyze current admin API structure, find all endpoints, understand auth patterns",
      "template": "research",
      "priority": 1,
      "relevantFiles": ["core/admin-api/routes.ts", "core/admin-api/middleware.ts"]
    },
    {
      "goal": "Implement rate limiter middleware with configurable limits per endpoint",
      "template": "implementation",
      "priority": 2,
      "relevantFiles": ["core/admin-api/middleware.ts", "core/config/defaults.ts"]
    },
    {
      "goal": "Wire rate limiter into admin API routes and add config defaults",
      "template": "implementation",
      "priority": 3,
      "relevantFiles": ["core/admin-api/routes.ts", "core/config/defaults.ts"]
    },
    {
      "goal": "Run type-check and tests, verify no regressions",
      "template": "review",
      "priority": 4,
      "budgetSteps": 5
    }
  ]
}

Example 2 - Parallel (independent tasks):
Goal: "Add logging to session manager and update documentation"
Response:
{
  "strategy": "parallel",
  "sharedContext": "These two tasks are independent and can be done simultaneously by different agents.",
  "tasks": [
    {
      "goal": "Add structured logging to session lifecycle events in session-manager.ts",
      "template": "implementation",
      "priority": 1,
      "relevantFiles": ["core/session-manager.ts"]
    },
    {
      "goal": "Update documentation to reflect new logging behavior",
      "template": "minimal",
      "priority": 1,
      "relevantFiles": ["docs/session-management.md", "AGENTS.md"]
    }
  ]
}

Example 3 - Tree (tasks that spawn sub-tasks):
Goal: "Refactor the entire intelligence module to use event-driven architecture"
Response:
{
  "strategy": "tree",
  "sharedContext": "This is a large refactoring effort. Each sub-task will need to analyze its area and potentially spawn further sub-tasks.",
  "tasks": [
    {
      "goal": "Analyze current intelligence module architecture and identify event boundaries",
      "template": "research",
      "priority": 1,
      "relevantFiles": ["core/intelligence/"]
    },
    {
      "goal": "Refactor thinker module to use event bus",
      "template": "implementation",
      "priority": 2,
      "relevantFiles": ["core/intelligence/thinker/"]
    },
    {
      "goal": "Refactor memory module to use event bus",
      "template": "implementation",
      "priority": 2,
      "relevantFiles": ["core/intelligence/memory/"]
    },
    {
      "goal": "Refactor consciousness module to use event bus",
      "template": "implementation",
      "priority": 2,
      "relevantFiles": ["core/intelligence/consciousness/"]
    }
  ]
}

OUTPUT FORMAT:
You MUST output valid JSON matching this schema:
{
  "strategy": "sequential" | "parallel" | "tree",
  "sharedContext": string (optional),
  "tasks": [
    {
      "goal": string,
      "context": string (optional),
      "template": "implementation" | "research" | "review" | "minimal" (optional),
      "priority": number,
      "relevantFiles": string[] (optional),
      "budgetSteps": number (optional)
    }
  ]
}

Respond ONLY with the JSON object. Do not include any explanation, markdown formatting, or other text.`)

  return sections.join('\n\n')
}

/**
 * Parse JSON from LLM response, handling markdown code blocks.
 */
function parseJSONFromResponse(content: string): DecompositionJSON | null {
  // Try to extract JSON from markdown code blocks first
  const codeBlockMatch = content.match(/```(?:json)?\s*([\s\S]*?)```/)
  const jsonStr = codeBlockMatch ? codeBlockMatch[1].trim() : content.trim()

  try {
    const parsed = JSON.parse(jsonStr)
    return parsed as DecompositionJSON
  } catch {
    // Try to find JSON object in the response
    const jsonMatch = content.match(/\{[\s\S]*\}/)
    if (jsonMatch) {
      try {
        return JSON.parse(jsonMatch[0]) as DecompositionJSON
      } catch {
        return null
      }
    }
    return null
  }
}

/**
 * Validate the decomposition JSON structure.
 */
function validateDecomposition(json: DecompositionJSON): { valid: boolean; error?: string } {
  // Check strategy is valid
  const validStrategies = ['sequential', 'parallel', 'tree']
  if (!validStrategies.includes(json.strategy)) {
    return { valid: false, error: `Invalid strategy: ${json.strategy}` }
  }

  // Check tasks array exists and is non-empty
  if (!Array.isArray(json.tasks) || json.tasks.length === 0) {
    return { valid: false, error: 'Tasks array is missing or empty' }
  }

  // Validate each task
  for (let i = 0; i < json.tasks.length; i++) {
    const task = json.tasks[i]

    // Each task must have goal and priority
    if (!task.goal || typeof task.goal !== 'string' || task.goal.trim() === '') {
      return { valid: false, error: `Task ${i + 1}: missing or invalid goal` }
    }

    if (typeof task.priority !== 'number' || task.priority < 1) {
      return { valid: false, error: `Task ${i + 1}: priority must be a positive number` }
    }

    // Validate template if provided
    if (task.template !== undefined) {
      const validTemplates = ['implementation', 'research', 'review', 'minimal', 'standard']
      if (!validTemplates.includes(task.template)) {
        return { valid: false, error: `Task ${i + 1}: invalid template '${task.template}'` }
      }
    }

    // Validate relevantFiles if provided
    if (task.relevantFiles !== undefined && !Array.isArray(task.relevantFiles)) {
      return { valid: false, error: `Task ${i + 1}: relevantFiles must be an array` }
    }
  }

  return { valid: true }
}

/**
 * Create a fallback decomposition (single task) when LLM parsing fails.
 */
function createFallbackDecomposition(goal: string, startTime: number): GoalDecomposition {
  return {
    decomposed: false,
    originalGoal: goal,
    subTasks: [{ goal, priority: 1 }],
    strategy: 'parallel',
    durationMs: Date.now() - startTime,
  }
}

/**
 * Convert validated DecompositionJSON to GoalDecomposition.
 */
function toGoalDecomposition(
  json: DecompositionJSON,
  originalGoal: string,
  durationMs: number,
): GoalDecomposition {
  const subTasks: GoalSubTask[] = json.tasks.map(task => ({
    goal: task.goal,
    context: task.context,
    template: task.template as ConstellationTemplate | undefined,
    priority: task.priority,
    relevantFiles: task.relevantFiles,
    budgetSteps: task.budgetSteps,
  }))

  return {
    decomposed: true,
    originalGoal,
    subTasks,
    strategy: json.strategy,
    sharedContext: json.sharedContext,
    durationMs,
  }
}

/**
 * Retry decomposition with a corrective prompt when JSON parsing fails.
 */
async function retryWithCorrection(
  llm: CorpusLLM,
  originalGoal: string,
  failedContent: string,
  log: ILogger,
): Promise<DecompositionJSON | null> {
  const correctivePrompt = `Your previous response could not be parsed as valid JSON.

ORIGINAL GOAL:
${originalGoal}

YOUR PREVIOUS RESPONSE:
${failedContent.slice(0, 1000)}${failedContent.length > 1000 ? '...' : ''}

The response must be valid JSON matching this exact schema:
{
  "strategy": "sequential" | "parallel" | "tree",
  "sharedContext": string (optional),
  "tasks": [
    {
      "goal": string (required),
      "context": string (optional),
      "template": "implementation" | "research" | "review" | "minimal" (optional),
      "priority": number (required, 1 = highest),
      "relevantFiles": string[] (optional),
      "budgetSteps": number (optional)
    }
  ]
}

Respond ONLY with the JSON object. No markdown, no explanation.`

  try {
    const response = await llm.complete({
      prompt: correctivePrompt,
      modelTier: 'sonnet',
      maxTokens: 2000,
      timeoutMs: 30_000,
    })

    const parsed = parseJSONFromResponse(response.content)
    if (parsed && validateDecomposition(parsed).valid) {
      return parsed
    }

    log.warn('Corrective decomposition also failed validation')
    return null
  } catch (err) {
    log.warn('Corrective decomposition failed', { error: String(err) })
    return null
  }
}

/**
 * Main decomposition function.
 *
 * @param opts - Decomposition options including goal, LLM, logger, and optional contexts
 * @returns A validated GoalDecomposition
 */
export async function fastDecompose(opts: FastDecomposerOpts): Promise<GoalDecomposition> {
  const startTime = Date.now()
  const { goal, llm, log, memory } = opts

  // Step 1: Determine if we need codebase context
  const decompositionMode = shouldDecompose(goal, opts.context)

  if (decompositionMode === 'skip') {
    log.info('Goal too simple for decomposition, returning single task', { goal: goal.slice(0, 100) })
    return createFallbackDecomposition(goal, startTime)
  }

  // Step 2: Assemble codebase context if needed (full mode)
  let codebaseContextStr: string | undefined

  if (decompositionMode === 'full' && opts.router) {
    try {
      log.info('Assembling codebase context via GitNexus prepare_context', { goal: goal.slice(0, 100) })

      const prepared: PreparedContext = await prepareContext(
        opts.router,
        {
          task: goal,
          tokenBudget: 4000, // WHY: Limit context size for decomposition prompt
          includeContent: true,
        } as PrepareContextOptions,
        log,
      )

      codebaseContextStr = formatCodebaseContext(prepared)
      log.debug('Codebase context assembled', {
        files: prepared.files.length,
        keywords: prepared.extractedKeywords.length,
        estimatedTokens: prepared.estimatedTokens,
      })
    } catch (err) {
      log.warn('Codebase context assembly failed, proceeding without it', { error: String(err) })
      // WHY: Continue without codebase context — don't block decomposition
    }
  } else if (opts.codebaseContext) {
    // Use pre-assembled context if provided
    codebaseContextStr = opts.codebaseContext
  }

  // Step 3: Query memory for relevant context
  let memoryContextStr: string | undefined

  if (memory) {
    try {
      const memoryResults = await memory.search(goal, { limit: 5 })
      if (memoryResults.length > 0) {
        memoryContextStr = formatMemoryContext(memoryResults)
        log.debug('Retrieved relevant memories', { count: memoryResults.length })
      }
    } catch (err) {
      log.warn('Memory query failed', { error: String(err) })
      // WHY: Continue without memory context — don't block decomposition
    }
  }

  // Step 4: Build the decomposition prompt
  const prompt = buildDecompositionPrompt(goal, codebaseContextStr, memoryContextStr)

  // Step 5: Make the LLM call
  log.info('Decomposing goal via direct LLM call', {
    goal: goal.slice(0, 100),
    mode: decompositionMode,
    hasCodebaseContext: !!codebaseContextStr,
    hasMemoryContext: !!memoryContextStr,
  })

  let response: { content: string; truncated: boolean }

  try {
    response = await llm.complete({
      prompt,
      modelTier: 'sonnet', // WHY: Use capable model for architectural reasoning
      maxTokens: 2000,
      timeoutMs: 60_000,
    })
  } catch (err) {
    log.error('LLM call failed during decomposition', { error: String(err) })
    return createFallbackDecomposition(goal, startTime)
  }

  // Step 6: Parse and validate JSON response
  let parsed = parseJSONFromResponse(response.content)

  if (!parsed) {
    log.warn('Initial JSON parse failed, attempting corrective retry', {
      responsePreview: response.content.slice(0, 200),
    })

    // Step 7: Retry with corrective prompt
    parsed = await retryWithCorrection(llm, goal, response.content, log)

    if (!parsed) {
      log.warn('Corrective decomposition failed, falling back to single task')
      return createFallbackDecomposition(goal, startTime)
    }
  }

  // Step 8: Validate the parsed structure
  const validation = validateDecomposition(parsed)
  if (!validation.valid) {
    log.warn('Decomposition validation failed', { error: validation.error })
    return createFallbackDecomposition(goal, startTime)
  }

  // Step 9: Convert to GoalDecomposition and return
  const result = toGoalDecomposition(parsed, goal, Date.now() - startTime)

  log.info('Goal decomposition complete', {
    decomposed: result.decomposed,
    subTasks: result.subTasks.length,
    strategy: result.strategy,
    durationMs: result.durationMs,
  })

  return result
}
