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

// ── Backend Interface ─────────────────────────────────────────────────────────

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
}

// ── Supporting Types ──────────────────────────────────────────────────────────

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

// ── Config Types ──────────────────────────────────────────────────────────────

export type ExecutionBackendType = 'cassicore' | 'opencode' | 'auto'

export interface OpenCodeBackendConfig {
  /** Base URL for OpenCode HTTP API (default: auto-discover or http://localhost:4096) */
  url?: string
  /** Path to server.json for port discovery (default: ~/.opencode/server.json) */
  serverJsonPath?: string
  /** Default agent type for team agents (default: 'build') */
  defaultAgent?: string
  /** Default model override (if not set, uses OpenCode's configured model) */
  defaultModel?: { providerID: string; modelID: string }
  /** Request timeout in ms (default: 300000 = 5 minutes) */
  requestTimeoutMs?: number
  /** Whether to forward CassiCore session hierarchy events (default: true) */
  forwardHierarchyEvents?: boolean
}
