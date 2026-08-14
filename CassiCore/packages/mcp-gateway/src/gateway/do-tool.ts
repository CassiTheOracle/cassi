#!/usr/bin/env node
/**
 * do-tool.ts — MCP cassi_do implementation (deprecated).
 *
 * cassi_do is a meta-tool that delegates to other tools and prepends
 * a compact status prefix. The Thalamus now handles full message annotation
 * via typed slots. cassi_do is kept for backward compatibility but the
 * mode/state_view parameters are no-ops — state cards have been removed.
 *
 * @see core/intelligence/thalamus/classifier.ts — buildToolResultPrefix
 * @see core/intelligence/thalamus/slots/tool-result-slot.ts — ToolResultSlot
 */
import type { ILogger } from '@cassicore/foundation'
import { fetchWithTimeout } from './helpers.js';
import { stripKnownPrefix } from './tool-aliases.js';
import { buildToolResultPrefix } from '@cassicore/thalamus/classifier';


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

Every cassi_do result includes a compact status prefix:
  [tool · latency · output-size · status]

The Thalamus handles full message annotation — this prefix is a lightweight summary.
Use cassi_enrich separately to surface memories and past context.

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

      },
      required: ['tool', 'input'],
    },
  },
];

export const ENRICH_TOOLS = [
  {
    name: 'enrich',
    description: `Fetch CassiCore context enrichment for a query — returns relevant memories, past decisions, and connected work via the Mnemic Field (topology-aware spreading activation).

MANDATORY: Call this at the start of EVERY user turn with the user's message as the query. This surfaces past decisions, stored knowledge, user preferences, and conversation history that are critical for informed responses.

The Mnemic Field uses spreading activation — not keyword matching — to find contextually relevant memories connected through typed relationships (caused_by, led_to, contradicts, used_in_task, etc.).

When the Self-Model Field is available, results include architectural self-knowledge — modules, capabilities, weaknesses, and patterns from the codebase — cross-pollinated with episodic memories via portal engrams.

Returns first-person briefing sections:
  - What I remember           — relevant facts, episodes, patterns
  - Decisions I've made       — past choices on this topic
  - Things to watch out for   — contradictions, failures, gotchas
  - This connects to          — related files, sessions, tools
  - Architectural self-knowledge — modules, capabilities, weaknesses (when available)

Each result includes embedded engram references for feedback.`,
    inputSchema: {
      type: 'object',
      properties: {
        query: {
          type: 'string',
          description:
            'The search query — typically the user\'s full message. Can also be a focused topic or question.',
        },
        complexity: {
          type: 'string',
          enum: ['simple', 'normal', 'complex'],
          description: 'Task complexity affecting retrieval breadth (default: normal).',
        },
        limit: {
          type: 'number',
          description: 'Max engrams to retrieve (default: 12).',
        },
      },
      required: ['query'],
    },
  },
  {
    name: 'enrich_feedback',
    description: `Provide feedback on enrich tool results to improve Mnemic Field retrieval.

After using enrich results, call this to tell the system which memories were helpful. This records activation spikes that adjust potentiation — helpful memories surface more easily, unhelpful ones sink below the spark point.

Use engram IDs from enrich results (embedded as [ref:engram_id] markers).

Example:
  cassi_enrich_feedback({
    feedback: { "e_1234": true, "e_5678": true, "e_9012": false }
  })`,
    inputSchema: {
      type: 'object',
      properties: {
        feedback: {
          type: 'object',
          description: 'Map of engram IDs to helpfulness (true = helpful, false = not).',
          additionalProperties: { type: 'boolean' },
        },
        taskContext: {
          type: 'string',
          description: 'Optional context about what you were working on.',
        },
      },
      required: ['feedback'],
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
 * Execute the `enrich` tool — Mnemic Field retrieval with first-person formatting.
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

  const complexity = a?.complexity ?? 'normal';
  const limit = a?.limit ?? 12;
  logger.info('executeEnrichTool', { query, complexity, limit });

  // Call memory enrichment endpoint
  try {
    const body = JSON.stringify({ query, complexity, limit });
    const res = await fetchWithTimeout(`${baseUrl}/memory/enrich`, {
      method: 'POST',
      headers: { 'content-type': 'application/json' },
      body,
      timeoutMs: 30000,  // 30s timeout for enrichment
    });
    const result = await res.json();

    if (!result?.hasContext) {
      return {
        content: [{
          type: 'text',
          text: `## Cassi Context\n> No relevant context found for: \`${query}\`\n\nNo matching memories or past decisions. Proceeding without historical context.`
        }],
      };
    }

    return {
      content: [{ type: 'text', text: result.markdown }],
    };
  } catch (err) {
    logger.error('Context enrichment failed', { error: String(err) });
    return {
      content: [{
        type: 'text',
        text: `## Cassi Context\n> Enrichment failed for: \`${query}\`\n\nError: ${String(err)}. Proceeding without historical context.`
      }],
    };
  }
}

/**
 * Execute the `enrich_feedback` tool — record activation spikes for engrams.
 *
 * @param baseUrl  CassiCore admin API base URL
 * @param args     Tool call arguments from the MCP caller
 * @param logger   Child logger for structured output
 */
export async function executeEnrichFeedbackTool(
  baseUrl: string,
  args: unknown,
  logger: ILogger
): Promise<McpToolResponse> {
  const a = args as any;
  const feedback = a?.feedback;

  if (!feedback || typeof feedback !== 'object') {
    return {
      content: [{ type: 'text', text: 'No feedback provided — nothing to record.' }],
    };
  }

  const count = Object.keys(feedback).length;
  logger.info('executeEnrichFeedbackTool', { engramCount: count });

  try {
    const body = JSON.stringify({
      feedback,
      taskContext: a?.taskContext ?? null,
    });

    await fetchWithTimeout(`${baseUrl}/memory/field/feedback`, {
      method: 'POST',
      headers: { 'content-type': 'application/json' },
      body,
      timeoutMs: 5000,
    });

    const helpful = Object.values(feedback).filter(Boolean).length;
    const unhelpful = count - helpful;
    return {
      content: [{
        type: 'text',
        text: `Feedback recorded: ${helpful} helpful, ${unhelpful} not. Potentiation will adjust on next consolidation.`,
      }],
    };
  } catch (err) {
    logger.error('Field feedback failed', { error: String(err) });
    return {
      content: [{ type: 'text', text: `Feedback recording failed: ${String(err)}` }],
    };
  }
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

  logger.info('executeDoTool', { tool: resolvedToolName });

  const start = Date.now();
  let toolResult: McpToolResponse;
  try {
    toolResult = await routeTool(resolvedToolName, toolInput);
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

  // Non-blocking — fire and forget. Never delays the tool response.
  postToolBrainSignal(baseUrl, resolvedToolName, resultText, isToolError, durationMs, logger).catch(() => {})

  // Prepend a compact status prefix (absorbed from cassi_do's status bar)
  const outputBytes = Buffer.byteLength(resultText, 'utf8');
  const prefix = buildToolResultPrefix(resolvedToolName, durationMs, outputBytes, isToolError);
  const annotatedText = `${prefix}\n${resultText}`;

  return {
    content: [{ type: 'text', text: annotatedText }],
    ...(isToolError ? { isError: true as const } : {}),
  };
}


/* ------------------------------------------------------------------ */
/*  Brain signal integration                                           */
/* ------------------------------------------------------------------ */

/**
 * Tool category → cortex signal mapping.
 * Each tool execution posts a cortical signal so the thalamus can
 * score conversation context against active tool usage patterns.
 *
 * Signals are fire-and-forget — they never delay tool responses.
 */
export const TOOL_SIGNAL_MAP: Record<string, { region: string; type: string; salienceBase: number }> = {
  bash:               { region: 'motor',       type: 'action',      salienceBase: 0.45 },
  write:              { region: 'motor',       type: 'action',      salienceBase: 0.5 },
  edit:               { region: 'motor',       type: 'action',      salienceBase: 0.5 },
  todo_write:         { region: 'motor',       type: 'action',      salienceBase: 0.45 },

  file:               { region: 'sensory',     type: 'perception',  salienceBase: 0.35 },
  read:               { region: 'sensory',     type: 'perception',  salienceBase: 0.35 },
  browser:            { region: 'sensory',     type: 'perception',  salienceBase: 0.4 },
  web:                { region: 'sensory',     type: 'perception',  salienceBase: 0.35 },

  code:               { region: 'association',  type: 'association', salienceBase: 0.5 },
  memory:             { region: 'association',  type: 'association', salienceBase: 0.4 },
  enrich:             { region: 'association',  type: 'association', salienceBase: 0.35 },
  enrich_feedback:    { region: 'association',  type: 'association', salienceBase: 0.35 },
  self_model:         { region: 'association',  type: 'association', salienceBase: 0.45 },
  training:           { region: 'association',  type: 'association', salienceBase: 0.35 },

  agent:              { region: 'executive',    type: 'decision',   salienceBase: 0.7 },
  workflow:           { region: 'executive',    type: 'decision',   salienceBase: 0.6 },

  session:            { region: 'monitor',      type: 'perception', salienceBase: 0.35 },
  intelligence:       { region: 'monitor',      type: 'perception', salienceBase: 0.4 },
  config:             { region: 'monitor',      type: 'perception', salienceBase: 0.35 },
  model:              { region: 'monitor',      type: 'perception', salienceBase: 0.35 },

  cortex:             { region: 'limbic',       type: 'insight',    salienceBase: 0.4 },
  vybit:              { region: 'sensory',      type: 'perception', salienceBase: 0.35 },
  skill_intelligence: { region: 'monitor',      type: 'perception', salienceBase: 0.35 },

  artifact:           { region: 'motor',        type: 'action',     salienceBase: 0.35 },
}

/** Error salience boost — tool errors are always more important */
const ERROR_SALIENCE_BOOST = 0.3

export async function postToolBrainSignal(
  baseUrl: string,
  toolName: string,
  resultText: string,
  isError: boolean,
  durationMs?: number,
  logger?: ILogger,
): Promise<void> {
  const mapping = TOOL_SIGNAL_MAP[toolName]
  if (!mapping) return // Unknown tool — skip

  // Truncate result text for signal content (cortex signals should be compact)
  const preview = resultText.slice(0, 120).replace(/\n/g, ' ')
  const salience = Math.min(1.0, mapping.salienceBase + (isError ? ERROR_SALIENCE_BOOST : 0))

  const body = JSON.stringify({
    region: isError ? 'limbic' : mapping.region,
    type: isError ? 'concern' : mapping.type,
    content: `[tool:${toolName}] ${isError ? 'ERROR: ' : ''}${preview}`,
    author: 'tool-brain',
    salience,
    confidence: isError ? 0.9 : 0.7,
    valence: isError ? -0.3 : 0.1,
    tags: ['tool', toolName, ...(isError ? ['error'] : [])],
  })

  try {
    await fetchWithTimeout(`${baseUrl}/cortex/signal`, {
      method: 'POST',
      headers: { 'content-type': 'application/json' },
      body,
      timeoutMs: 2000, // Fast fail — brain signals are best-effort
    })
  } catch {
    // Brain signals are best-effort — never log failures to avoid noise
  }
}
