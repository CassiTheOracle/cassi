/**
 * query_events Tool — Universal Event Bus Query Tool
 *
 * Query runtime events from the event history.
 * Supports both complex structured queries and simple natural language queries.
 */

import type {
  EventQuery,
  ComplexEventQuery,
  SimpleEventQuery,
  EventQueryResult,
} from "../../../types/event-query.js";
import type { Tool, ToolContext, ToolResult } from "../../../types/tools.js";
import { EventHistory } from "../../event-history.js";
import { parseSimpleQuery, getQuerySuggestions } from "../../event-query-parser.js";
import { getPreset, getAllPresets, getCategories, executePreset } from "../../event-query-presets.js";

// =============================================================================
// Tool Definition
// =============================================================================

interface QueryEventsInput {
  /** Query mode: complex (structured), simple (natural language), or preset (named query) */
  mode: "complex" | "simple" | "preset";

  // Complex query fields
  since?: string;
  until?: string;
  types?: string[];
  typePattern?: string;
  where?: Record<string, unknown>;
  aggregate?: {
    groupBy?: string;
    count?: boolean;
    sum?: string;
    avg?: string;
    min?: string;
    max?: string;
  };
  limit?: number;
  offset?: number;
  sort?: {
    field: string;
    order: "asc" | "desc";
  };
  format?: "full" | "summary" | "count" | "timeline" | "json";

  // Simple query fields
  query?: string;

  // Preset query fields
  preset?: string;
}

const name = "query_events";

const description = `Query the event bus history for runtime events.

Supports three modes:
1. **complex**: Structured query with precise filters, aggregations, and sorting
2. **simple**: Natural language query that gets auto-translated (e.g., "recent subagent failures")
3. **preset**: Use a named preset query (e.g., "provider-errors", "system-health")

Examples:
- Simple: { "mode": "simple", "query": "recent subagent failures" }
- Complex: { "mode": "complex", "types": ["subagent:failed"], "since": "10m" }
- Preset: { "mode": "preset", "preset": "system-health" }`;

const inputSchema = {
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
      properties: {
        groupBy: { type: "string", description: "Field to group by" },
        count: { type: "boolean", description: "Count per group" },
        sum: { type: "string", description: "Sum this numeric field" },
        avg: { type: "string", description: "Average this numeric field" },
        min: { type: "string", description: "Minimum of this field" },
        max: { type: "string", description: "Maximum of this field" },
      },
    },
    limit: {
      type: "integer",
      default: 100,
      minimum: 1,
      maximum: 1000,
      description: "Maximum results to return",
    },
    offset: {
      type: "integer",
      default: 0,
      minimum: 0,
      description: "Pagination offset",
    },
    sort: {
      type: "object",
      description: "Sort specification",
      properties: {
        field: { type: "string", default: "timestamp" },
        order: { type: "string", enum: ["asc", "desc"], default: "desc" },
      },
    },
    format: {
      type: "string",
      enum: ["full", "summary", "count", "timeline", "json"],
      default: "summary",
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
} as const;

// =============================================================================
// Tool Implementation
// =============================================================================

export class QueryEventsTool implements Tool {
  name = name;
  description = description;
  inputSchema = inputSchema;

  private history: EventHistory;

  constructor(history: EventHistory) {
    this.history = history;
  }

  async execute(input: QueryEventsInput, _context: ToolContext): Promise<ToolResult> {
    try {
      let result: EventQueryResult;

      switch (input.mode) {
        case "complex":
          result = await this.executeComplex(input);
          break;
        case "simple":
          result = await this.executeSimple(input);
          break;
        case "preset":
          result = await this.executePreset(input);
          break;
        default:
          return {
            success: false,
            error: `Unknown query mode: ${input.mode}. Use "complex", "simple", or "preset".`,
          };
      }

      return this.formatResult(result, input.format);
    } catch (err) {
      return {
        success: false,
        error: `Query failed: ${err instanceof Error ? err.message : String(err)}`,
      };
    }
  }

  private async executeComplex(input: QueryEventsInput): Promise<EventQueryResult> {
    const query: ComplexEventQuery = {
      mode: "complex",
      since: input.since,
      until: input.until,
      types: input.types as any,
      typePattern: input.typePattern,
      where: input.where,
      aggregate: input.aggregate,
      limit: input.limit,
      offset: input.offset,
      sort: input.sort,
      format: input.format === "json" ? "full" : input.format,
    };

    return this.history.query(query);
  }

  private async executeSimple(input: QueryEventsInput): Promise<EventQueryResult> {
    if (!input.query) {
      throw new Error("Simple mode requires a 'query' field with natural language");
    }

    const parsed = parseSimpleQuery({
      query: input.query,
      limit: input.limit,
    });

    if (!parsed.success) {
      throw new Error(parsed.error || "Failed to parse query");
    }

    const result = this.history.query(parsed.query);

    // Add translation info to result
    return {
      ...result,
      query: {
        ...result.query,
        translation: parsed.translation,
      },
    };
  }

  private async executePreset(input: QueryEventsInput): Promise<EventQueryResult> {
    if (!input.preset) {
      throw new Error("Preset mode requires a 'preset' field with preset name");
    }

    const presetQuery = executePreset(input.preset);
    if (!presetQuery) {
      const available = getAllPresets().map((p) => `"${p.name}"`).join(", ");
      throw new Error(`Unknown preset "${input.preset}". Available: ${available}`);
    }

    // Override with any user-provided options
    const query: ComplexEventQuery = {
      ...presetQuery,
      limit: input.limit ?? presetQuery.limit,
      offset: input.offset ?? presetQuery.offset,
      format: input.format === "json" ? presetQuery.format : (input.format ?? presetQuery.format),
    };

    return this.history.query(query);
  }

  private formatResult(result: EventQueryResult, format?: string): ToolResult {
    // Handle different output formats
    switch (format) {
      case "json":
        return {
          success: true,
          result: JSON.stringify(result, null, 2),
        };

      case "count":
        return {
          success: true,
          result: `Total events: ${result.metadata.totalAvailable}`,
        };

      default:
        return {
          success: true,
          result: this.formatAsText(result),
        };
    }
  }

  private formatAsText(result: EventQueryResult): string {
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
      lines.push("| Group | Count | Sum | Avg | Min | Max |");
      lines.push("|-------|-------|-----|-----|-----|-----|");

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
        const payload = event.payload as any;
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
}

// =============================================================================
// Tool Factory
// =============================================================================

export function createQueryEventsTool(history: EventHistory): Tool {
  return new QueryEventsTool(history);
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
