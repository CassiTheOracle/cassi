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
import { fetchAndFormatContext, type ContextLimits } from './context-enrichment.js';
import type { ILogger } from '../../types/interfaces.js';

// ─── Types ───────────────────────────────────────────────────────────────────

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

// ─── Tool Definitions ─────────────────────────────────────────────────────────

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

The tool parameter accepts both the raw registered name ("bash") and the prefixed form ("cassi_bash") — one cassi_ prefix is stripped automatically.`,
    inputSchema: {
      type: 'object',
      properties: {
        tool: {
          type: 'string',
          description:
            'Registered tool name to call (e.g. "bash", "cassi_bash", "cassi_memory_search"). One leading cassi_ prefix is stripped automatically.',
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

Returns a formatted markdown block with results from three sources:
  - Memory store (stored facts, preferences, insights)
  - Archive (past conversations, tool calls, patterns, dialectic outputs)
  - Session history (indexed past session excerpts with paragraph-level granularity)

If no relevant context is found, returns a brief "no context" message.`,
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

// ─── Helpers ─────────────────────────────────────────────────────────────────

/**
 * Strip one leading "cassi_" prefix so callers can pass either the registered
 * name or the prefixed name they see in OpenCode's tool list.
 */
export function normalizeToolName(name: string): string {
  return name.startsWith('cassi_') ? name.slice('cassi_'.length) : name;
}

// ─── Enrich Executor ──────────────────────────────────────────────────────────

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

  const result = await fetchAndFormatContext(baseUrl, query, limits);

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

// ─── Do Executor ──────────────────────────────────────────────────────────────

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

  // ── Parallel execution: tool + (for non-raw modes) state card prefetch ────
  // Starting the state card fetch alongside the tool call means its latency
  // is hidden by the tool's own execution time in most cases.
  const stateCardPromise = mode !== 'raw'
    ? fetchStateCard(baseUrl, stateView).catch(() => ({ card: '', resolvedView: stateView }))
    : Promise.resolve({ card: '', resolvedView: stateView });

  const start = Date.now();
  const [toolResult, prefetchedState] = await Promise.all([
    routeTool(resolvedToolName, toolInput),
    stateCardPromise,
  ]);
  const durationMs = Date.now() - start;

  const isToolError = toolResult?.isError === true;
  const resultText  =
    toolResult?.content
      ?.map((c: { type: string; text: string }) => c.text)
      .join('\n') ?? '';

  // Augment — pass prefetched state so augmentDoResult skips a second fetch
  const augmented = await augmentDoResult({
    toolName: resolvedToolName,
    result: { text: resultText, isError: isToolError },
    durationMs,
    mode,
    stateView,
    baseUrl,
    prefetchedState: mode !== 'raw' ? prefetchedState : undefined,
  });

  return {
    content: [{ type: 'text', text: augmented.text }],
    ...(augmented.isError ? { isError: true as const } : {}),
  };
}
