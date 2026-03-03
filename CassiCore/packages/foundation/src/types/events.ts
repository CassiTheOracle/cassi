/**
 * All typed events that flow through the CassieCore EventBus.
 * Every module communicates exclusively through these types.
 */

export type LogLevel = "debug" | "info" | "warn" | "error";

// Health status enum
export type HealthStatus = "healthy" | "degraded" | "unhealthy";

// CassiCore event types

export type RuntimeEvent =
  | { type: "daemon:ready"; startedAt: Date }
  | { type: "daemon:shutdown"; reason: string }
  | {
      type: "daemon:health";
      overall: HealthStatus;
      checks: Array<{ name: string; status: HealthStatus }>;
      memoryMb: number;
      uptimeMs: number;
      eventLoopLagMs: number;
      timestamp: Date;
    }
  | { type: "turn:start"; sessionId: string; message: string; timestamp: Date }
  | { type: "turn:end"; sessionId: string; response: string; durationMs: number }
  | { type: "plugin:loaded"; pluginId: string }
  | { type: "plugin:crashed"; pluginId: string; error: string; crashCount: number }
  | { type: "plugin:restarted"; pluginId: string; attempt: number }
  | { type: "plugin:stopped"; pluginId: string; reason: "max-restarts" | "manual" }
  | { type: "config:changed"; key: string; oldVal: unknown; newVal: unknown }
  | { type: "config:reloaded" }
  | { type: "config:override:set"; key: string; value: unknown; meta?: object }
  | { type: "config:override:cleared"; key: string }
  | { type: "worker:message"; pluginId: string; payload: unknown }
  // Centralized provider events
  | { type: "provider:request_start"; providerId: string; requestId: string; sessionId: string; model: string; messageCount: number }
  | { type: "provider:request_end"; providerId: string; requestId: string; sessionId: string; tokensUsed: number; durationMs: number; error?: string }
  | { type: "provider:request_error"; providerId: string; requestId: string; sessionId: string; error: string; consecutiveErrors: number }
  | { type: "provider:request_aborted"; providerId: string; requestId: string; sessionId: string }
  | { type: "provider:deduplicated"; providerId: string; sessionId: string; existingRequestId: string }
  | { type: "provider:rate_limited"; providerId: string; sessionId: string; retryAfterMs: number }
  | { type: "provider:error_reset"; providerId: string }
  | { type: "provider:request_timeout"; providerId: string; requestId: string; sessionId: string; timeoutMs: number }
  // Subagent lifecycle events
  | { type: "subagent:spawned"; parentSessionId: string; childSessionId: string; runId: string; label: string; timestamp: Date }
  | { type: "subagent:started"; runId: string; sessionId: string; timestamp: Date }
  | { type: "subagent:completed"; runId: string; sessionId: string; result: string; durationMs: number; timestamp: Date }
  | { type: "subagent:failed"; runId: string; sessionId: string; error: string; timestamp: Date }
  // Pi Bridge events
  | { type: "pi:completion:request"; requestId: string; messages: any[]; opts: any }
  | { type: "pi:completion:chunk"; requestId: string; chunk: any }
  | { type: "thinker:insight-applied"; sessionId: string; insight: string }
  // Tool registry events — emitted when tools are (re)registered into the system
  | { type: "tool:registered"; name: string; description: string; parameters?: Record<string, unknown>; server?: string }
  | { type: "tool:unregistered"; name: string; server?: string }
  // Autonomy lifecycle events
  | { type: "autonomy:started"; agentId: string; options?: Record<string, unknown> }
  | { type: "autonomy:stopped"; agentId: string; reason?: string }
  | { type: "autonomy:tool_called"; agentId: string; tool: string; summary?: string }
  // Autonomy confirmation lifecycle
  | { type: "autonomy:confirmation_requested"; id: string; agentId: string; tool: string; reason?: string }
  | { type: "autonomy:confirmation_approved"; id: string; agentId: string; tool: string; approver?: string; result?: unknown }
  | { type: "autonomy:confirmation_rejected"; id: string; agentId: string; tool: string; approver?: string; reason?: string }
  // Compaction & Context events
  | { type: "session:compacted"; sessionId: string; summary: string }
  | { type: "context-manager:sync"; sessionId: string; payload: any }
  | { type: "dialectic:signal"; sessionId: string; signalType: string; content: string; confidence: number }
  // Session Agent events
  | { type: "session_agent:created"; agentId: string; sessionId: string; agentType: string; timestamp: Date }
  | { type: "session_agent:shutdown"; agentId: string; sessionId: string; timestamp: Date }
  | { type: "session_agent:status_changed"; agentId: string; sessionId: string; status: string; timestamp: Date }
  | { type: "session_agent:observation"; agentId: string; sessionId: string; trigger: string; timestamp: Date }
  | { type: "session_agent:action"; agentId: string; sessionId: string; actionType: string; timestamp: Date }
  | { type: "session_agent:suggestion"; agentId: string; sessionId: string; suggestionType: string; timestamp: Date }
  // Skill usage tracking events
  | { type: "skill:invoked"; skillName: string; skillPath: string; sessionId: string; timestamp: Date; source?: string }
  | { type: "skill:metrics:aggregated"; period: string; topSkills: Array<{ name: string; count: number }>; totalInvocations: number; timestamp: Date }
  // Unified Intelligence Loop events
  | { type: "intelligence:heartbeat"; cycleNumber: number; uptimeMs: number; moduleStatuses: Array<{ name: string; healthy: boolean; lastActivity?: number }>; timestamp: Date }
  | { type: "intelligence:maintenance"; task: string; detail?: string; timestamp: Date }
  | { type: "intelligence:loop:started"; intervalMs: number; timestamp: Date }
  | { type: "intelligence:loop:stopped"; reason: string; cyclesCompleted: number; timestamp: Date }
  // Adaptive Behavior events (Phase 3)
  | { type: "adaptive:adaptation-applied"; adaptationId: string; adaptationType: string; target: string; confidence: number; sourceModule: string; timestamp: Date }
  | { type: "adaptive:adaptation-reverted"; adaptationId: string; adaptationType: string; target: string; reason: string; timestamp: Date }
  | { type: "adaptive:cycle-complete"; adaptationsApplied: number; adaptationsReverted: number; activeCount: number; timestamp: Date }
  // Self-Verification events (Phase 4)
  | { type: "verification:verdict-recorded"; adaptationId: string; verdict: string; effectSize: number; confidence: number; timestamp: Date }
  | { type: "verification:report-generated"; reportId: number; totalVerdicts: number; successRate: number; timestamp: Date }
  | { type: "verification:trust-updated"; sourceModule: string; oldTrust: number; newTrust: number; timestamp: Date }
  // Multi-agent lifecycle events
  | { type: "agent:spawned"; agentId: string; role: string; parentSessionId?: string }
  | { type: "agent:task-assigned"; agentId: string; task: string; sessionId: string }
  | { type: "agent:completed"; agentId: string; result: string; parentSessionId?: string; tokensUsed?: number; model?: string; durationMs?: number }
  | { type: "agent:error"; agentId: string; error: string }
  | { type: "agent:handoff"; fromAgentId: string; toAgentId: string; fromRole: string; toRole: string }
  | { type: "multi-agent:spawn-retry"; attempt: number; error: string; role: string }
  | { type: "multi-agent:spawn-failed"; error: string; role: string }
  | { type: "multi-agent:assign-retry"; attempt: number; error: string; agentId: string }
  | { type: "multi-agent:assign-failed"; error: string; agentId: string }
  // Autonomous loop events
  | { type: "autonomy:loop_started"; agentId: string; sessionId: string; opts?: Record<string, unknown> }
  | { type: "autonomy:loop_stopped"; agentId: string; reason: string; iterations: number; totalTokensUsed: number }
  | { type: "autonomy:loop_paused"; agentId: string }
  | { type: "autonomy:loop_resumed"; agentId: string }
  | { type: "autonomy:iteration"; agentId: string; iteration: number; decision: string; tokensUsed: number; totalTokensUsed: number; durationMs: number; toolCalls: number }
  | { type: "autonomy:iteration_error"; agentId: string; iteration: number; error: string }
  | { type: "autonomy:delegation_requested"; agentId: string; delegateTo: string; delegateTask: string }
  | { type: "autonomy:blocked"; agentId: string; reason: string }
  // Team orchestration events
  | { type: "team:started"; teamId: string; coordinatorAgentId?: string }
  | { type: "team:completed"; teamId: string; finalResult?: string }
  | { type: "team:failed"; teamId: string; error: string }
  | { type: "team:cancelled"; teamId: string; reason: string }
  | { type: "team:paused"; teamId: string }
  | { type: "team:resumed"; teamId: string }
  | { type: "team:budget:warning"; teamId: string; tokenPct: number; agentPct: number; timePct: number }
  | { type: "team:checkpoint"; teamId: string; checkpointId: string; trigger: string; progress: string }
  // Cross-session awareness events
  | { type: "session:created"; sessionId: string; channelId: string; senderId: string; timestamp: Date }
  | { type: "session:ended"; sessionId: string; timestamp: Date }
  | { type: "cross-session:message"; fromSessionId: string; toSessionId: string; messageId: string; content: string; timestamp: Date }
  // Reflex module events — autonomic tool execution triggered by subconscious thinking
  | { type: "reflex:triggered"; sessionId: string; intent: string; tool: string; timestamp: Date }
  | { type: "reflex:tool_executed"; sessionId: string; tool: string; durationMs: number; success: boolean; timestamp: Date }
  | { type: "reflex:result_injected"; sessionId: string; tool: string; resultSummary: string; timestamp: Date }
  | { type: "reflex:suppressed"; sessionId: string; reason: string; intent: string; timestamp: Date }
  | { type: "reflex:error"; sessionId: string; error: string; tool?: string; timestamp: Date };

export type EventType = RuntimeEvent["type"];

/** Extract the event shape for a given type literal */
export type EventOf<T extends EventType> = Extract<RuntimeEvent, { type: T }>;

/** Unsubscribe function returned by EventBus.on() */
export type Unsubscribe = () => void;
