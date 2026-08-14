/**
 * IExecutionBackend — Abstraction over how autonomous agent iterations are executed.
 *
 * The AutonomousAgentLoop drives agents through repeated iterations. Each iteration
 * needs an "execution backend" that takes a prompt and returns a complete result
 * (including tool execution, LLM calls, etc.).
 *
 * Two implementations:
 *   - CassiCoreExecutionBackend: uses TurnPipeline.process() (current behavior)
 *   - OpenCodeExecutionBackend: delegates to OpenCode via HTTP session API
 */

import type { TurnResult, InboundMessage } from './runtime.js'


export interface IExecutionBackend {
  /** Human-readable backend name (for logging) */
  readonly name: string

  /**
   * Execute a single agent iteration.
   *
   * For CassiCore backend: wraps pipeline.process(inbound)
   * For OpenCode backend: sends prompt to OpenCode session via HTTP
   *
   * @param inbound - The fully-built inbound message (prompt, metadata, session context)
   * @returns The turn result with response text, token usage, tool calls, etc.
   */
  execute(inbound: InboundMessage): Promise<TurnResult>

  /**
   * Initialize a session for an agent. Called once when the autonomous loop starts.
   * OpenCode backend creates an HTTP session; CassiCore backend is a no-op.
   *
   * @param agentId - Unique agent identifier
   * @param sessionId - CassiCore session ID for this agent
   * @param opts - Agent session configuration
   */
  initAgentSession(agentId: string, sessionId: string, opts: AgentSessionOpts): Promise<void>

  /**
   * Clean up resources when the loop stops.
   * OpenCode backend may abort the session; CassiCore backend is a no-op.
   */
  destroyAgentSession(agentId: string): Promise<void>

  /**
   * Check if the backend is available and ready to accept work.
   * OpenCode backend checks HTTP connectivity; CassiCore backend checks pipeline.
   */
  isAvailable(): Promise<boolean>

  /**
   * Update the execution context for an active agent session.
   * Called by ContextManager when fresh context is assembled (memory, files, etc.).
   * OpenCode backend sends context as a system message update; CassiCore backend
   * stores it for injection on the next pipeline turn.
   *
   * @param agentId - Unique agent identifier
   * @param context - Fresh assembled context from ContextManager
   */
  updateContext?(
    agentId: string,
    context: { systemPrompt?: string; recentMemories?: string[]; files?: string[] },
  ): Promise<void>
}


export interface AgentSessionOpts {
  /** Task description for the agent */
  initialTask?: string
  /** LLM provider configuration */
  provider?: {
    providerId?: string
    model?: string
    providerModel?: string
    thinking?: string
  }
  /** Agent type for OpenCode backend (default: 'build') */
  openCodeAgent?: string
  /** Custom system prompt override */
  systemPrompt?: string
  /** Parent session ID (for hierarchy tracking) */
  parentSessionId?: string
}


export type ExecutionBackendType = 'cassicore' | 'opencode' | 'auto'

export interface OpenCodeBackendConfig {
  /** 
   * Base URL for OpenCode HTTP API.
   * If not set, auto-discovers from server.json or defaults to http://localhost:4096.
   * 
   * INTERNAL USE ONLY - NOT forwarded to OpenCode.
   */
  url?: string
  
  /** 
   * Path to server.json for port discovery.
   * Default: ~/.opencode/server.json (written by OpenCode fork U9).
   * 
   * INTERNAL USE ONLY - NOT forwarded to OpenCode.
   */
  serverJsonPath?: string
  
  /** 
   * Default agent type for team agents.
   * Default: 'build'. Used when creating sessions if opts.openCodeAgent is not set.
   * 
   * INTERNAL USE ONLY - NOT forwarded to OpenCode.
   */
  defaultAgent?: string
  
  /** 
   * Default model override for message execution.
   * Format: { providerID: string; modelID: string }
   * 
   * Used as fallback when no per-session provider override is set.
   * Per-session overrides from AgentSessionOpts.provider take precedence.
   * If not set, OpenCode uses its own configured model.
   */
  defaultModel?: { providerID: string; modelID: string }
  
  /** 
   * Request timeout in milliseconds.
   * Default: 300000 (5 minutes).
   * 
   * INTERNAL USE ONLY - NOT forwarded to OpenCode.
   */
  requestTimeoutMs?: number
  
  /** 
   * Whether to forward CassiCore session hierarchy events.
   * Default: true. Controls internal session tracking behavior.
   * 
   * INTERNAL USE ONLY - NOT forwarded to OpenCode.
   */
  forwardHierarchyEvents?: boolean
}
