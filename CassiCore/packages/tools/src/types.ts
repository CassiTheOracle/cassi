/** JSON Schema subset for tool parameter definitions */
export interface ToolParamSchema {
  type: 'object';
  properties: Record<string, {
    type: string;
    description?: string;
    enum?: string[];
    default?: unknown;
    items?: { type: string; enum?: string[] };
  }>;
  required?: string[];
}

/** Tool category for progressive discovery */
export type ToolCategory = 'core' | 'cognitive' | 'debug' | 'coordination' | 'extended'

export interface ToolDefinition {
  name: string;
  description: string;
  parameters: ToolParamSchema;
  /** Max execution time in ms. Default 30_000. */
  timeoutMs?: number;
  /** Tool category for progressive discovery. Default: 'core' */
  category?: ToolCategory;
  /** Fallback tool name to use when this tool's circuit breaker is open */
  fallbackTool?: string;
  /** Whether this tool is read-only (safe for parallel execution). Default: false */
  readOnly?: boolean;
}

/** A single tool call parsed from the provider stream */
export interface ToolCall {
  id: string;
  name: string;
  input: Record<string, unknown>;
}

export interface ToolResult {
  toolCallId: string;
  content: string;
  isError: boolean;
  /** Raw output before presentation formatting */
  rawContent?: string;
  /** Tool exit code (for shell tools) */
  exitCode?: number;
  /** Execution duration in ms */
  durationMs?: number;
}

export type ToolHandler = (
  input: Record<string, unknown>,
  context: ToolExecutionContext,
) => Promise<string>;

export interface ToolExecutionContext {
  sessionId: string;
  workingDir: string;
  allowedPaths: string[];      // filesystem sandbox roots (resolved)
  networkAllowlist: string[];  // allowed URL domains; ['*'] = unrestricted
  logger: import('../../types/interfaces.js').ILogger;
}
