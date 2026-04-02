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
  /** Whether this tool should be shown to agents/clients. Default: true */
  visibleToAgent?: boolean;
  /** Backend/provider that implements this tool (e.g. cassi, serena, gitnexus, scip). */
  backend?: string;
  /** Semantic capability group for routing and discovery (e.g. workspace.read, code.find_symbol). */
  capability?: string;
  /** Preferred alias names that should resolve to this tool. */
  aliases?: string[];
  /**
   * Minimum permission tier required to execute this tool.
   * Used as a fast-path in the permission oracle:
   * - 'read-only': safe for read operations (file reads, searches, web fetch)
   * - 'workspace-write': modifies workspace files (edit, write, mkdir)
   * - 'full-access': unrestricted (shell exec, system commands, network writes)
   *
   * When the active trust level meets or exceeds this tier, the full
   * consequence estimation pipeline can be skipped (performance win).
   * Default: 'full-access' (conservative — unknown tools require full assessment).
   */
  requiredPermission?: 'read-only' | 'workspace-write' | 'full-access';
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
  registry?: import('./registry.js').ToolRegistry;
  /** Shared file artifact store — injected by daemon for cassi:// URI support */
  _fileArtifactStore?: import('../file-artifact-store.js').FileArtifactStore;
  /** Global blackboard registry — injected by daemon for cross-session todo/plan sharing */
  _globalBlackboardRegistry?: import('../intelligence/flux-team/global-blackboard-registry.js').GlobalBlackboardRegistry;
  /** Auto-resolved artifact namespace for this session (e.g., 'dyad:{id}', 'team:{id}') */
  artifactNamespace?: string;
  /** Session type hint for smart defaults */
  sessionType?: 'dyad' | 'lumen' | 'flux' | 'helix' | 'standalone';
  /** Team ID for team-scoped file sharing */
  teamId?: string;
}
