/** JSON Schema subset for tool parameter definitions */
export interface ToolParamSchema {
  type: 'object';
  properties: Record<string, {
    type: string;
    description?: string;
    enum?: string[];
    default?: unknown;
    items?: { type: string };
  }>;
  required?: string[];
}

export interface ToolDefinition {
  name: string;
  description: string;
  parameters: ToolParamSchema;
  /** Max execution time in ms. Default 30_000. */
  timeoutMs?: number;
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
