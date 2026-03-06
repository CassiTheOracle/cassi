/**
 * query_events Tool — Universal Event Bus Query Tool
 *
 * Query runtime events from the event history.
 * Supports both complex structured queries and simple natural language queries.
 */

import { type EventHistory } from "../../event-history.js";
import { parseSimpleQuery, getQuerySuggestions } from "../../event-query-parser.js";
import { getPreset, getAllPresets, getCategories, executePreset } from "../../event-query-presets.js";

import type {
  EventQuery,
  ComplexEventQuery,
  SimpleEventQuery,
  EventQueryResult,
} from "../../../types/event-query.js";
import type { ToolDefinition, ToolHandler, ToolExecutionContext, ToolParamSchema } from "../types.js";

// =============================================================================
// Tool Definition
// =============================================================================

export const queryEventsDefinition: ToolDefinition = {
  name: "query_events",
  description: `Query the event bus history for runtime events.

Supports three modes:
1. **complex**: Structured query with precise filters, aggregations, and sorting
2. **simple**: Natural language query that gets auto-translated (e.g., "recent subagent failures")
3. **preset**: Use a named preset query (e.g., "provider-errors", "system-health")

Examples:
- Simple: { "mode": "simple", "query": "recent subagent failures" }
- Complex: { "mode": "complex", "types": ["subagent:failed"], "since": "10m" }
- Preset: { "mode": "preset", "preset": "system-health" }`,
  parameters: {
    type: "object",
    required: ["mode"],
    properties: {
      mode: {
        type: "string",
        enum: ["complex", "simple", "preset"],
        description: "Query mode: complex (structured), simple (natural language), or preset (named)",
      },

      // Complex mode fields
      since: {
        type: "string",
        description: "Start time (ISO date or relative like '5m', '1h', '30s')",
      },
      until: {
        type: "string",
        description: "End time (ISO date or relative)",
      },
      types: {
        type: "array",
        items: { type: "string" },
        description: "Filter by specific event types",
      },
      typePattern: {
        type: "string",
        description: "Wildcard pattern for event types (e.g., 'subagent:*', 'provider:*')",
      },
      where: {
        type: "object",
        description: "Field conditions using operators: $eq, $ne, $gt, $gte, $lt, $lte, $in, $contains, $regex, $exists",
      },
      aggregate: {
        type: "object",
        description: "Aggregation specification",
      },
      limit: {
        type: "integer",
        description: "Maximum results to return",
      },
      offset: {
        type: "integer",
        description: "Pagination offset",
      },
      sort: {
        type: "object",
        description: "Sort specification",
      },
      format: {
        type: "string",
        enum: ["full", "summary", "count", "timeline", "json"],
        description: "Output format",
      },

      // Simple mode fields
      query: {
        type: "string",
        description: "Natural language query (for simple mode)",
      },

      // Preset mode fields
      preset: {
        type: "string",
        description: "Name of preset query (for preset mode)",
      },
    },
  },
  timeoutMs: 30_000,
};

// =============================================================================
// Tool Implementation
// =============================================================================

export function makeQueryEventsHandler(history: EventHistory): ToolHandler {
  return async (input: Record<string, unknown>, _ctx: ToolExecutionContext): Promise<string> => {
    try {
      const mode = input["mode"] as "complex" | "simple" | "preset";
      let result: EventQueryResult;

      switch (mode) {
        case "complex":
          result = await executeComplex(history, input);
          break;
        case "simple":
          result = await executeSimple(history, input);
          break;
        case "preset":
          result = await executePresetMode(history, input);
          break;
        default:
          return `Error: Unknown query mode: ${mode}. Use "complex", "simple", or "preset".`;
      }

      const format = input["format"] as string | undefined;
      return formatResult(result, format);
    } catch (err) {
      return `Error: Query failed: ${err instanceof Error ? err.message : String(err)}`;
    }
  };
}

async function executeComplex(history: EventHistory, input: Record<string, unknown>): Promise<EventQueryResult> {
  const query: ComplexEventQuery = {
    mode: "complex",
    since: input["since"] as string | undefined,
    until: input["until"] as string | undefined,
    types: input["types"] as any,
    typePattern: input["typePattern"] as string | undefined,
    where: input["where"] as Record<string, unknown> | undefined,
    aggregate: input["aggregate"] as Record<string, unknown> | undefined,
    limit: input["limit"] as number | undefined,
    offset: input["offset"] as number | undefined,
    sort: input["sort"] as { field: string; order: "asc" | "desc" } | undefined,
    format: (input["format"] === "json" ? "full" : input["format"]) as "full" | "summary" | "count" | "timeline" | undefined,
  };

  return history.query(query);
}

async function executeSimple(history: EventHistory, input: Record<string, unknown>): Promise<EventQueryResult> {
  const queryText = input["query"] as string;
  if (!queryText) {
    throw new Error("Simple mode requires a 'query' field with natural language");
  }

  const parsed = parseSimpleQuery({
    query: queryText,
    limit: input["limit"] as number | undefined,
  });

  if (!parsed.success) {
    throw new Error(parsed.error || "Failed to parse query");
  }

  const result = history.query(parsed.query);

  // Add translation info to result
  return {
    ...result,
    query: {
      ...result.query,
      translation: parsed.translation,
    },
  };
}

async function executePresetMode(history: EventHistory, input: Record<string, unknown>): Promise<EventQueryResult> {
  const presetName = input["preset"] as string;
  if (!presetName) {
    throw new Error("Preset mode requires a 'preset' field with preset name");
  }

  const presetQuery = executePreset(presetName);
  if (!presetQuery) {
    const available = getAllPresets().map((p) => `"${p.name}"`).join(", ");
    throw new Error(`Unknown preset "${presetName}". Available: ${available}`);
  }

  // Override with any user-provided options
  const query: ComplexEventQuery = {
    ...presetQuery,
    limit: (input["limit"] as number | undefined) ?? presetQuery.limit,
    offset: (input["offset"] as number | undefined) ?? presetQuery.offset,
    format: input["format"] === "json" ? presetQuery.format : ((input["format"] as "full" | "summary" | "count" | "timeline" | undefined) ?? presetQuery.format),
  };

  return history.query(query);
}

function formatResult(result: EventQueryResult, format?: string): string {
  // Handle different output formats
  switch (format) {
    case "json":
      return JSON.stringify(result, null, 2);

    case "count":
      return `Total events: ${result.metadata.totalAvailable}`;

    default:
      return formatAsText(result);
  }
}

function formatAsText(result: EventQueryResult): string {
  const lines: string[] = [];

  // Header
  lines.push(`# Event Query Results`);
  lines.push("");

  // Query info
  lines.push(`**Mode:** ${result.query.mode}`);
  if (result.query.translation) {
    lines.push(`**Translation:** ${result.query.translation}`);
  }
  lines.push("");

  // Metadata
  lines.push(`## Metadata`);
  lines.push(`- Total available: ${result.metadata.totalAvailable}`);
  lines.push(`- Returned: ${result.metadata.returned}`);
  lines.push(`- Execution time: ${result.metadata.executionTimeMs.toFixed(2)}ms`);
  lines.push(`- Time range: ${result.metadata.timeRange.from.toISOString()} to ${result.metadata.timeRange.to.toISOString()}`);
  if (result.metadata.truncated) {
    lines.push(`- ⚠️ Results were truncated`);
  }
  lines.push("");

  // Results
  if ("groups" in result.results) {
    // Aggregation result
    lines.push(`## Aggregation Results`);
    lines.push("");
    lines.push(`| Group | Count | Sum | Avg | Min | Max |`);
    lines.push(`|-------|-------|-----|-----|-----|-----|`);

    for (const group of result.results.groups) {
      const cells = [
        group.key,
        group.count.toString(),
        group.sum?.toFixed(2) ?? "-",
        group.avg?.toFixed(2) ?? "-",
        group.min?.toFixed(2) ?? "-",
        group.max?.toFixed(2) ?? "-",
      ];
      lines.push(`| ${cells.join(" | ")} |`);
    }

    if (result.results.totals) {
      lines.push("");
      lines.push(`**Totals:** Count=${result.results.totals.count}${
        result.results.totals.sum !== undefined ? `, Sum=${result.results.totals.sum.toFixed(2)}` : ""
      }${
        result.results.totals.avg !== undefined ? `, Avg=${result.results.totals.avg.toFixed(2)}` : ""
      }`);
    }
  } else {
    // Event list result
    lines.push(`## Events (${result.results.length})`);
    lines.push("");

    for (const event of result.results) {
      lines.push(`### ${event.type}`);
      lines.push(`- **ID:** ${event.id}`);
      lines.push(`- **Time:** ${event.timestamp.toISOString()}`);
      if (event.metadata.sessionId) {
        lines.push(`- **Session:** ${event.metadata.sessionId}`);
      }
      if (event.metadata.agentId) {
        lines.push(`- **Agent:** ${event.metadata.agentId}`);
      }
      if (event.metadata.source) {
        lines.push(`- **Source:** ${event.metadata.source}`);
      }

      // Payload summary
      const payload = event.payload as Record<string, unknown>;
      if (payload && typeof payload === "object") {
        const relevantFields = Object.entries(payload)
          .filter(([key]) => key !== "type")
          .slice(0, 5); // Show first 5 fields

        if (relevantFields.length > 0) {
          lines.push(`- **Payload:**`);
          for (const [key, value] of relevantFields) {
            const valueStr = typeof value === "object" ? JSON.stringify(value) : String(value);
            lines.push(`  - ${key}: ${valueStr.substring(0, 100)}${valueStr.length > 100 ? "..." : ""}`);
          }
        }
      }
      lines.push("");
    }
  }

  return lines.join("\n");
}

// =============================================================================
// Helper: List Presets
// =============================================================================

export function listPresetsForTool(): string {
  const categories = getCategories();
  const lines: string[] = ["Available query presets:", ""];

  for (const category of categories) {
    lines.push(`## ${category.charAt(0).toUpperCase() + category.slice(1)}`);
    const presets = getAllPresets().filter((p) => p.category === category);
    for (const preset of presets) {
      lines.push(`- **${preset.name}**: ${preset.description}`);
    }
    lines.push("");
  }

  return lines.join("\n");
}

// =============================================================================
// Backwards-compatible factory
// =============================================================================

export interface QueryEventsTool {
  name: string;
  description: string;
  inputSchema: ToolParamSchema;
  execute(input: Record<string, unknown>, context: ToolExecutionContext): Promise<{ success: boolean; result?: string; error?: string }>;
}

export function createQueryEventsTool(history: EventHistory): QueryEventsTool {
  const handler = makeQueryEventsHandler(history);
  return {
    name: queryEventsDefinition.name,
    description: queryEventsDefinition.description,
    inputSchema: queryEventsDefinition.parameters,
    async execute(input: Record<string, unknown>, context: ToolExecutionContext): Promise<{ success: boolean; result?: string; error?: string }> {
      try {
        const result = await handler(input, context);
        return { success: true, result };
      } catch (err) {
        return { success: false, error: err instanceof Error ? err.message : String(err) };
      }
    }
  };
}

// =============================================================================
// Helper: Get Suggestions
// =============================================================================

export function getSuggestionsForTool(context?: { sessionId?: string; agentId?: string }): string {
  const suggestions = getQuerySuggestions(context);
  const lines: string[] = ["Suggested queries:", ""];

  for (const s of suggestions) {
    lines.push(`## ${s.description}`);
    lines.push(`Query: "${s.query}"`);
    lines.push(`Result: ${s.example}`);
    lines.push("");
  }

  return lines.join("\n");
}
