#!/usr/bin/env node
/**
 * do-tool.ts — `cassi_do` execution-layer tool + `cassi_enrich` context tool
 *
 * `cassi_do`:     Executes any registered gateway tool and wraps its result
 *                 with a status bar, optional rotating live system state card,
 *                 execution metadata, and (in guide mode) next-step suggestions.
 *
 *                 Modes: raw | observe (default) | analyze | guide
 *                 State views: auto (cycles) | health | activity | cognitive
 *
 * `cassi_enrich`: Standalone context retrieval — memories, archive, session
 *                 history. Call at the start of every turn with the user's
 *                 message. This is the ONLY tool that searches memory.
 *
 * Augmentation logic lives in do-augmentation.ts (shared with SDK bridge).
 * Memory/archive context logic lives in context-enrichment.ts (enrich only).
 */

import { augmentDoResult, fetchStateCard, type DoMode, type StateView } from './do-augmentation.js';
import { fetchAndFormatContext, type ContextLimits, fetchProactiveResults, formatProactiveResults } from './context-enrichment.js';
import { resolveSessionId } from './helpers.js';
import { stripKnownPrefix } from './tool-aliases.js';
import type { ILogger } from '../../types/interfaces.js';


/** MCP tool response shape (matches what routeToolCall returns) */
type McpToolResponse = {
  content: Array<{ type: 'text'; text: string }>;
  isError?: true;
};

/**
 * Injected routing callback — avoids circular imports and duplication of
 * the routing table. Provided by cassicore-gateway.ts when invoking executeDoTool.
 */
export type ToolRouter = (
  name: string,
  args: unknown
) => Promise<McpToolResponse>;


export const DO_TOOLS = [
  {
    name: 'do',
    description: `Call any registered tool and receive its result wrapped with live system context.

Every cassi_do result includes:
  1. Status bar  — always: tool · latency · time · output-size · status · mode
  2. State card  — observe/analyze/guide: rotating live system snapshot (health | activity | cognitive)
  3. Exec block  — analyze/guide: tool class, output size, latency breakdown
  4. Guide block — guide mode only: next-step tool suggestions when orchestration IDs are detected
  5. Tool output — the raw result of the delegated tool call

Modes (mode param, default "observe"):
  raw     — status bar + raw output only
  observe — status bar + state card + output
  analyze — observe + execution metadata
  guide   — analyze + next-step suggestions for orchestration/job/session IDs in the result

State views (state_view param, default "auto"):
  auto      — cycles through health → activity → cognitive on successive calls
  health    — provider status, active sessions, anomaly count
  activity  — intelligence module pulse, thinker ponder count, archive stats
  cognitive — thinker insight count, last insight, strategy/confidence

Use cassi_enrich separately to surface memories and past context — cassi_do does not search memory.

The tool parameter accepts both the raw registered name ("bash") and the legacy prefixed form ("cassi_bash") — one leading cassi_ prefix is stripped automatically for compatibility.`,
    inputSchema: {
      type: 'object',
      properties: {
        tool: {
          type: 'string',
          description:
            'Registered tool name to call (e.g. "bash", "read", "memory_search"). One leading cassi_ prefix is stripped automatically for compatibility.',
        },
        input: {
          type: 'object',
          description: 'Input arguments for the delegated tool.',
        },
        mode: {
          type: 'string',
          enum: ['raw', 'observe', 'analyze', 'guide'],
          description:
            'Augmentation mode (default: "observe"). raw=status bar only; observe=+state card; analyze=+exec metadata; guide=+next-step suggestions.',
        },
        state_view: {
          type: 'string',
          enum: ['auto', 'health', 'activity', 'cognitive'],
          description:
            'Which live state lens to show (default: "auto"). auto cycles through all three on successive calls.',
        },
      },
      required: ['tool', 'input'],
    },
  },
];

export const ENRICH_TOOLS = [
  {
    name: 'enrich',
    description: `Fetch CassiCore context enrichment for a query — returns relevant memories, archived conversations, and session history WITHOUT calling any tool.

MANDATORY: Call this at the start of EVERY user turn with the user's message as the query. This surfaces past decisions, stored knowledge, user preferences, and conversation history that are critical for informed responses.

The query is processed through a Query Intelligence pipeline before searching:
  - Entity extraction  — session refs (S0#M1), tool names, file paths, providers
  - Dynamic expansion  — related tags/entities/topics from archive metadata (cached)
  - Multi-variant search — 6–9 parallel searches using exact, entity, and expanded variants
  - Cross-source merge — results ranked by relevance × 0.7 + recency × 0.2 + diversity × 0.1
  - Empty recovery     — fallback searches + suggested related terms when nothing matches

Returns a formatted markdown block with:
  1. Top Relevant (cross-source) — best 5 results merged and ranked across all sources
  2. From Memory               — stored facts, preferences, insights
  3. From Archive              — past conversations, tool calls, patterns, dialectic outputs
  4. From Session History      — indexed past session excerpts with paragraph-level granularity

If no direct matches are found, returns broadened results + suggested search terms instead.

If no relevant context is found at all, returns a brief "no context" message.`,
    inputSchema: {
      type: 'object',
      properties: {
        query: {
          type: 'string',
          description:
            'The search query — typically the user\'s full message. Can also be a focused topic or question.',
        },
        memory_limit: {
          type: 'number',
          description: 'Max memory results (default: 5, 0 = skip).',
        },
        archive_limit: {
          type: 'number',
          description: 'Max archive results (default: 5, 0 = skip).',
        },
        index_limit: {
          type: 'number',
          description: 'Max session history results (default: 10, 0 = skip).',
        },
      },
      required: ['query'],
    },
  },
];

export const DO_TOOL_NAMES = new Set(DO_TOOLS.map(t => t.name));
export const ENRICH_TOOL_NAMES = new Set(ENRICH_TOOLS.map(t => t.name));

export function getDoTools(): Array<{
  name: string;
  description: string;
  inputSchema: Record<string, unknown>;
}> {
  return [...DO_TOOLS, ...ENRICH_TOOLS];
}


/**
 * Strip one leading known prefix ("cassi_", "serena_", "playwright_browser_", etc.)
 * so callers can pass either the registered name or the prefixed name they see in
 * OpenCode's tool list.  Delegates to stripKnownPrefix() from tool-aliases.ts so
 * the prefix list lives in one canonical place.
 */
export function normalizeToolName(name: string): string {
  return stripKnownPrefix(name) ?? name;
}


/**
 * Execute the `enrich` tool — context-only enrichment (no delegated tool call).
 *
 * @param baseUrl  CassiCore admin API base URL
 * @param args     Tool call arguments from the MCP caller
 * @param logger   Child logger for structured output
 */
export async function executeEnrichTool(
  baseUrl: string,
  args: unknown,
  logger: ILogger
): Promise<McpToolResponse> {
  const a = args as any;

  const query: string = a?.query ?? '';
  if (!query.trim()) {
    return {
      content: [{ type: 'text', text: 'No query provided — nothing to enrich.' }],
    };
  }

  const limits: ContextLimits = {
    memoryLimit: a?.memory_limit ?? 5,
    archiveLimit: a?.archive_limit ?? 5,
    indexLimit: a?.index_limit ?? 10,
  };

  logger.info('executeEnrichTool', { query, ...limits });

  let result;
  try {
    result = await fetchAndFormatContext(baseUrl, query, limits);
  } catch (err) {
    logger.error('Context enrichment failed', { error: String(err) });
    return {
      content: [
        {
          type: 'text',
          text: `## Cassi Context\n> Enrichment failed for: \`${query}\`\n\nError: ${String(err)}\n\nProceeding without historical context.`,
        },
      ],
    };
  }

  if (!result.hasContext) {
    return {
      content: [
        {
          type: 'text',
          text: `## Cassi Context\n> No relevant context found for: \`${query}\`\n\nNo matching memories, archive entries, or session history. Proceeding without historical context.`,
        },
      ],
    };
  }

  return {
    content: [{ type: 'text', text: result.markdown }],
  };
}


/**
 * Execute the `do` meta-wrapper tool.
 *
 * @param baseUrl   CassiCore admin API base URL
 * @param args      Tool call arguments from the MCP caller
 * @param logger    Child logger for structured output
 * @param routeTool Injected routing callback from the gateway — avoids
 *                  circular imports by delegating routing back to the caller
 */
export async function executeDoTool(
  baseUrl: string,
  args: unknown,
  logger: ILogger,
  routeTool: ToolRouter
): Promise<McpToolResponse> {
  const a = args as any;

  const rawToolName: string = a?.tool ?? '';
  const toolInput: unknown  = a?.input ?? {};
  const mode: DoMode        = a?.mode       ?? 'observe';
  const stateView: StateView= a?.state_view ?? 'auto';

  // Strip one cassi_ prefix so callers can use the name as shown in OpenCode
  const resolvedToolName = normalizeToolName(rawToolName);

  // Recursion guard — check both before and after normalization
  const selfNames = new Set(['do', 'cassi_do', 'enrich', 'cassi_enrich']);
  if (!resolvedToolName || selfNames.has(rawToolName) || selfNames.has(resolvedToolName)) {
    return {
      content: [
        {
          type: 'text',
          text: JSON.stringify({
            error: 'cassi_do cannot call itself or cassi_enrich. Pass a specific tool name.',
          }),
        },
      ],
      isError: true,
    };
  }

  logger.info('executeDoTool', { tool: resolvedToolName, mode, stateView });

  // Starting the state card fetch alongside the tool call means its latency
  // is hidden by the tool's own execution time in most cases.
  const stateCardPromise: Promise<{ card: string; resolvedView: StateView }> = mode !== 'raw'
    ? fetchStateCard(baseUrl, stateView).catch((): { card: string; resolvedView: StateView } => ({ card: '', resolvedView: stateView }))
    : Promise.resolve({ card: '', resolvedView: stateView });

  const start = Date.now();
  let toolResult: McpToolResponse;
  let prefetchedState: { card: string; resolvedView: StateView } = { card: '', resolvedView: stateView };
  try {
    [toolResult, prefetchedState] = await Promise.all([
      routeTool(resolvedToolName, toolInput),
      stateCardPromise,
    ]);
  } catch (err) {
    const durationMs = Date.now() - start;
    logger.error('cassi_do delegated tool call failed', { tool: resolvedToolName, error: String(err), durationMs });
    return {
      content: [{ type: 'text', text: JSON.stringify({ error: `Tool '${resolvedToolName}' failed: ${String(err)}`, durationMs }) }],
      isError: true,
    };
  }
  const durationMs = Date.now() - start;

  const isToolError = toolResult?.isError === true;
  const resultText  =
    toolResult?.content
      ?.map((c: { type: string; text: string }) => c.text)
      .join('\n') ?? '';

  // Augment — pass prefetched state so augmentDoResult skips a second fetch.
  // WHY: If augmentation fails, return the raw tool result rather than losing
  // the work the tool already did.
  let augmented: { text: string; isError?: boolean };
  try {
    augmented = await augmentDoResult({
      toolName: resolvedToolName,
      result: { text: resultText, isError: isToolError },
      durationMs,
      mode,
      stateView,
      baseUrl,
      prefetchedState: mode !== 'raw' ? prefetchedState : undefined,
    });
  } catch (err) {
    logger.warn('cassi_do augmentation failed, returning raw result', { error: String(err) });
    augmented = { text: resultText, isError: isToolError };
  }

  return {
    content: [{ type: 'text', text: augmented.text }],
    ...(augmented.isError ? { isError: true as const } : {}),
  };
}
