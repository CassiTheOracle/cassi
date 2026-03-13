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
  | { type: "daemon:restarting"; reason: string; expectedDowntimeMs?: number }
  | { type: "daemon:resumed"; startedAt: Date; previousShutdownReason?: string; restoredTeams?: number; restoredLoops?: number; downtimeMs?: number }
  | {
      type: "daemon:health";
      overall: HealthStatus;
      checks: Array<{ name: string; status: HealthStatus }>;
      memoryMb: number;
      uptimeMs: number;
      eventLoopLagMs: number;
      timestamp: Date;
    }
  | { type: "turn:start"; sessionId: string; turnId?: string; message: string; timestamp: Date }
  | { type: "turn:end"; sessionId: string; response: string; durationMs: number; traceId?: string }
  | { type: "plugin:loaded"; pluginId: string }
  | { type: "plugin:crashed"; pluginId: string; error: string; crashCount: number }
  | { type: "plugin:restarted"; pluginId: string; attempt: number }
  | { type: "plugin:stopped"; pluginId: string; reason: "max-restarts" | "manual" | "circuit-breaker" }
  | { type: "plugin:circuit-open"; pluginId: string; crashCount: number; windowMs: number }
  | { type: "plugin:circuit-closed"; pluginId: string }
  | { type: "plugin:health-timeout"; pluginId: string; sincePongMs: number }
  | { type: "daemon:degraded"; pluginId: string; reason: string }
  | { type: "config:changed"; key: string; oldVal: unknown; newVal: unknown }
  | { type: "config:reloaded" }
  | { type: "config:override:set"; key: string; value: unknown; meta?: object }
  | { type: "config:override:cleared"; key: string }
  | { type: "worker:message"; pluginId: string; payload: unknown }
  // Centralized provider events
   | { type: "provider:request_start"; providerId: string; requestId: string; sessionId: string; source: string; trigger?: string; model: string; messageCount: number; timestamp: Date }
   | { type: "provider:request_prompt"; providerId: string; requestId: string; sessionId: string; source: string; messages: Array<{ role: string; content: string }>; systemPrompt?: string; timestamp: Date }
   | { type: "provider:request_end"; providerId: string; requestId: string; sessionId: string; source: string; trigger?: string; model: string; tokensUsed: { input: number; output: number; thinking: number }; durationMs: number; error?: string; timestamp: Date }
   | { type: "provider:request_error"; providerId: string; requestId: string; sessionId: string; source: string; trigger?: string; model: string; error: string; durationMs: number; timestamp: Date }
   | { type: "provider:request_aborted"; providerId: string; requestId: string; sessionId: string }
   | { type: "provider:deduplicated"; providerId: string; sessionId: string; existingRequestId: string }
   | { type: "provider:rate_limited"; providerId: string; sessionId: string; retryAfterMs: number }
   | { type: "provider:error_reset"; providerId: string }
   | { type: "provider:request_timeout"; providerId: string; requestId: string; sessionId: string; timeoutMs: number }
   | { type: "provider:request_chunk"; providerId: string; requestId: string; sessionId: string; source: string; trigger?: string; model: string; chunkType: "token" | "thinking" | "tool_use"; text?: string; toolCall?: { id: string; name: string; input: Record<string, unknown> }; timestamp: Date }
   // Budget events
   | { type: "budget:warning"; providerId: string; tier: "cautious" | "frugal" | "critical"; percentUsed: number; remaining: number; monthlyLimit: number }
   | { type: "budget:tier_changed"; providerId: string; previousTier: "normal" | "cautious" | "frugal" | "critical"; newTier: "normal" | "cautious" | "frugal" | "critical"; percentUsed: number; remaining: number }
   // Subagent lifecycle events
  | { type: "subagent:spawned"; parentSessionId: string; childSessionId: string; runId: string; label: string; timestamp: Date }
  | { type: "subagent:started"; runId: string; sessionId: string; timestamp: Date }
  | { type: "subagent:completed"; runId: string; sessionId: string; result: string; durationMs: number; timestamp: Date }
  | { type: "subagent:failed"; runId: string; sessionId: string; error: string; timestamp: Date }
  // Pi Bridge events
  | { type: "pi:completion:request"; requestId: string; messages: any[]; opts: any }
  | { type: "pi:completion:chunk"; requestId: string; chunk: any }
  | { type: "thinker:insight-applied"; sessionId: string; insight: string; requestId?: string }
  | { type: "injection:timeout"; sessionId: string; source: string; timeoutMs: number; timestamp: Date }
  | { type: "injection:aggregated"; sessionId: string; sources: string[]; totalChars: number; partCount: number; timestamp: Date }
   // Tool registry events — emitted when tools are (re)registered into the system
  | { type: "tool:registered"; name: string; description: string; parameters?: Record<string, unknown>; server?: string }
  | { type: "tool:unregistered"; name: string; server?: string }
  // Tool execution events — emitted after every tool call completes
  | { type: "tool:executed"; sessionId: string; toolName: string; durationMs: number; isError: boolean; source?: string; timestamp: Date }
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
  | { type: "dialectic:signal"; sessionId: string; signalType: string; content: string; confidence: number; requestId?: string }
  | { type: "dialectic:started"; dialecticId: string }
  | { type: "dialectic:stopped"; dialecticId: string; reason: string }
  | { type: "dialectic:iteration"; dialecticId: string; iteration: number; summary: { yang?: number; yin?: number; hasSignal?: boolean } }
  | { type: "dialectic:error"; dialecticId: string; error: string }
  // Session Agent events

  // Skill usage tracking events
  | { type: "skill:invoked"; skillName: string; skillPath: string; sessionId: string; timestamp: Date; source?: string }
  | { type: "skill:metrics:aggregated"; period: string; topSkills: Array<{ name: string; count: number }>; totalInvocations: number; timestamp: Date }
  // Unified Intelligence Loop events
   | { type: "intelligence:heartbeat"; cycleNumber: number; uptimeMs: number; moduleStatuses: Array<{ name: string; healthy: boolean; lastActivity?: number }>; activeRequests?: number; activeSessions?: number; timestamp: Date }
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
  | { type: "multi-agent:metrics"; metrics: Record<string, number> }
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

  // Drone swarm events — lightweight parallel agent execution
  | { type: "drone:spawned"; droneId: string; swarmId: string; role: string; parentSessionId: string; timestamp: Date }
  | { type: "drone:completed"; droneId: string; swarmId: string; role: string; tokensUsed: number; durationMs: number; requestId?: string; timestamp: Date }
  | { type: "drone:failed"; droneId: string; swarmId: string; role: string; error: string; retryCount: number; timestamp: Date }
  | { type: "drone:cancelled"; droneId: string; swarmId: string; reason: string; timestamp: Date }
  | { type: "drone:timed_out"; droneId: string; swarmId: string; timeoutMs: number; timestamp: Date }
  | { type: "drone:swarm:started"; swarmId: string; mission: string; droneCount: number; parentSessionId: string; timestamp: Date }
  | { type: "drone:swarm:completed"; swarmId: string; mission: string; successCount: number; failCount: number; totalTokensUsed: number; durationMs: number; timestamp: Date }
  | { type: "drone:swarm:failed"; swarmId: string; mission: string; error: string; timestamp: Date }
  | { type: "drone:prediction"; swarmId: string; branchCount: number; topBranch: string; topProbability: number; tokensUsed: number; timestamp: Date }
  | { type: "drone:speculative:matched"; swarmId: string; droneId: string; branchId: string; probability: number; timestamp: Date }
  | { type: "drone:speculative:discarded"; swarmId: string; droneIds: string[]; reason: string; timestamp: Date }
  | { type: "drone:swarm:cognitive-summary"; swarmId: string; parentSessionId: string; totalSignals: number; signalsByKind: Record<string, number>; resonanceCount: number; timestamp: Date }
  | { type: "drone:autonomous-probe:triggered"; source: "thinker" | "subconscious" | "dialectic"; reason: string; priority: "low" | "medium" | "high"; probeCount: number; timestamp: Date }
  | { type: "drone:autonomous-probe:completed"; source: "thinker" | "subconscious" | "dialectic"; success: boolean; signalCount: number; tokensUsed: number; durationMs: number; timestamp: Date }
  | { type: "drone:cache-hit"; droneId: string; swarmId: string; cacheKey: string; timestamp: Date }
  // Consciousness events — emitted by the Subconscious conscious observer
  | {
      type: "consciousness:observation";
      sessionId?: string;
      requestId?: string;
      observation: {
        id: string;
        summary: string;
        patterns: string[];
        confidence: number;
        source: "heuristic" | "llm";
        relatedEventTypes: string[];
      };
      timestamp: Date;
    }
  | {
      type: "consciousness:anomaly";
      sessionId?: string;
      requestId?: string;
      anomaly: {
        id: string;
        description: string;
        severity: "low" | "medium" | "high";
        eventTypes: string[];
        suggestedAction?: string;
      };
      timestamp: Date;
    }
   | {
      type: "consciousness:insight";
      requestId?: string;
      insight: string;
      relatedEvents: string[];
      confidence: number;
      timestamp: Date;
    }
   | {
      type: "consciousness:state";
      model: {
        activeSessions: number;
        systemHealth: "healthy" | "degraded" | "critical";
        providerStatus: Record<string, string>;
        pluginStatus: Record<string, string>;
        budgetTiers: Record<string, string>;
        activeDrones: number;
        activeTeams: number;
        recentPatterns: string[];
        observationCount: number;
      };
      timestamp: Date;
    }
  // ── SelfHealingAgent events ─────────────────────────────────────────────
  | { type: "intelligence:processor-error"; processorName: string; error: string; timestamp: number }
  | { type: "self-healer:error-detected";   id: string; processorName: string; error: string; attempt: number }
  | { type: "self-healer:repair-proposed";  id: string; filePath: string; patch: string }
  | { type: "self-healer:repair-applied";   id: string; filePath: string }
  | { type: "self-healer:repair-validated"; id: string; filePath: string }
  | { type: "self-healer:repair-failed";    id: string; error: string }
  | { type: "self-healer:skipped";          id: string; reason: string }
  | { type: "self-healer:gave-up";          id: string; processorName: string; error: string; attempts: number }
  | { type: "self-healer:not-applicable";   id: string; reason: string }
  | { type: "self-healer:processor-suppressed"; processorName: string; failureCount: number }
  | { type: "self-healer:rebuild-started";  id: string }
  | { type: "self-healer:rebuild-succeeded"; id: string }
  | { type: "self-healer:rebuild-failed";   id: string; error: string }
  | { type: "self-healer:restart-requested"; id: string; reason: string }
  | { type: "self-healer:shutdown-requested"; id: string; reason: string }
  // ── ErrorLearner events (merged Reflect + Recover) ──────────────────────────
  | { type: "error-learner:pattern_stored"; pattern: string; category: string; occurrences: number; timestamp: Date }
  | { type: "error-learner:recovery_attempted"; pattern: string; strategy: string; attempt: number; maxAttempts: number; timestamp: Date }
  | { type: "error-learner:recovery_exhausted"; pattern: string; context?: string; timestamp: Date }
  // ── AI Scientist events ─────────────────────────────────────────────────────
  | { type: "ai-scientist:study-complete"; studyId: string; track: string; summary: string }
  | { type: "ai-scientist:breakthrough"; track: string; title: string; metric: string; deltaPercent: number; effectSize: number; pValue: number }
  // ── Thinker quality signals ─────────────────────────────────────────────────
   | { type: "thinker:feedback"; sessionId: string; helpful: boolean; insightContent?: string }
   | { type: "thinker:ponder-skipped"; sessionId: string; reason: string }
   | { type: "thinker:strategy-updated"; strategy: Record<string, unknown> }
   | { type: "thinker:repair-request"; id: string; prompt: string }
   | { type: "thinker:repair-response"; id: string; text: string; error?: string }
   | { type: "thinker:inject-insight"; sessionId: string; insight: string; level: string; requestId?: string }
   | { type: "thinker:early-warning"; sessionId: string; warning: string; requestId?: string }
   | { type: "thinker:self-modified"; module: string; change: Record<string, unknown> }
   | { type: "thinker:swarm-deployed"; sessionId: string; swarmId: string; mission: string }
  // ── Thought Observer events ────────────────────────────────────────────────
    | {
        type: "thinking:signal-extracted";
        sessionId: string;
        signals: Array<{ kind: string; text: string; confidence: number }>;
        source: "realtime" | "post-turn" | "manual";
        thinkingCharsProcessed: number;
        timestamp: Date;
      }
  // ── Dialectic extra signals ─────────────────────────────────────────────────
  | { type: "dialectic:no-signal"; sessionId: string; reason: string; requestId?: string }
  | { type: "dialectic:convergence"; sessionId: string; converged: boolean; requestId?: string }
  // ── Subconscious anomaly (short-form) ───────────────────────────────────────
  | { type: "subconscious:anomaly"; anomalyId: string; description: string; severity: "low" | "medium" | "high" }
  // ── AI Engineer lifecycle events ────────────────────────────────────────────
  | { type: "ai-engineer:upgrade-proposed"; trialId: string; targetId: string; moduleId: string; rationale: string; validationScore: number }
  | { type: "ai-engineer:upgrade-applied";  trialId: string; targetId: string; moduleId: string; deltaPercent: Record<string, number>; reason: string }
  | { type: "ai-engineer:upgrade-reverted"; trialId: string; targetId: string; moduleId: string; outcome: string; deltaPercent: Record<string, number>; reason: string }
  | { type: "ai-engineer:upgrade-skipped";  targetId?: string; reason: string }
  | { type: "ai-engineer:prompt-updated";   targetId: string; moduleId: string }
  // ── Consequence Estimator events ──────────────────────────────────────────
  | {
      type: "consequence:estimated";
      sessionId: string;
      toolName: string;
      riskLevel: "negligible" | "low" | "moderate" | "high" | "critical";
      riskScore: number;
      reversibility: "fully" | "partially" | "irreversible";
      dimensions: { dataLoss: number; systemStability: number; externalImpact: number; resourceCost: number; privacyRisk: number };
      estimatorType: "heuristic" | "llm" | "combined";
      timestamp: Date;
    }
  | { type: "consequence:estimation-failed"; sessionId: string; toolName: string; error: string; timestamp: Date }
  // ── Trust Ledger events ───────────────────────────────────────────────────
  | {
      type: "trust:score-updated";
      domain: string;
      oldScore: number;
      newScore: number;
      delta: number;
      reason: string;
      evidence: string;
      timestamp: Date;
    }
  | { type: "trust:domain-created"; domain: string; initialScore: number; timestamp: Date }
  | { type: "trust:decay-applied"; domain: string; oldScore: number; newScore: number; decayFactor: number; timestamp: Date }
  | {
      type: "trust:outcome-recorded";
      domain: string;
      action: string;
      success: boolean;
      consequenceAccuracy: number;
      timestamp: Date;
    }
  // ── Permission Oracle events ──────────────────────────────────────────────
  | {
      type: "permission:decision";
      sessionId: string;
      toolName: string;
      decision: "allow" | "deny" | "escalate";
      riskScore: number;
      trustScore: number;
      threshold: number;
      reason: string;
      timestamp: Date;
    }
  | { type: "permission:escalated"; sessionId: string; toolName: string; reason: string; riskLevel: string; timestamp: Date }
  | { type: "permission:human-response"; sessionId: string; toolName: string; approved: boolean; responder?: string; responseTimeMs: number; timestamp: Date }
  | {
      type: "permission:override";
      sessionId: string;
      toolName: string;
      originalDecision: "allow" | "deny" | "escalate";
      overriddenTo: "allow" | "deny";
      reason: string;
      timestamp: Date;
    }
  // ── Autonomy Governance events (graduated autonomy lifecycle) ─────────────
  | {
      type: "autonomy:trust-gate";
      sessionId: string;
      action: string;
      gateResult: "passed" | "blocked" | "escalated";
      trustScore: number;
      requiredThreshold: number;
      riskScore: number;
      timestamp: Date;
    }
  | {
      type: "autonomy:level-changed";
      previousLevel: "supervised" | "guided" | "autonomous" | "trusted";
      newLevel: "supervised" | "guided" | "autonomous" | "trusted";
      reason: string;
      overallTrust: number;
      timestamp: Date;
    }
  // ── Scout events (pre-turn search agent) ──────────────────────────────────
  | { type: "scout:started"; sessionId: string; message: string; timestamp: Date }
  | { type: "scout:tool_call"; sessionId: string; tool: string; input: Record<string, unknown>; timestamp: Date }
  | { type: "scout:tool_result"; sessionId: string; tool: string; resultLength: number; isError: boolean; durationMs: number; timestamp: Date }
  | { type: "scout:completed"; sessionId: string; contextLength: number; toolCalls: number; durationMs: number; roundsUsed: number; status: string; timestamp: Date }
  | { type: "scout:skipped"; sessionId: string; reason: string; timestamp: Date }
  | { type: "scout:error"; sessionId: string; error: string; timestamp: Date }
  // ── Self-improvement loop events ──────────────────────────────────────────
  | { type: "improvement:proposal-queued"; proposalId: string; trigger: string; source: string; confidence: number; timestamp: Date }
  | { type: "improvement:gate-started"; proposalId: string; mode: string; timestamp: Date }
  | { type: "improvement:gate-passed"; proposalId: string; improvements: string[]; timestamp: Date }
  | { type: "improvement:gate-failed"; proposalId: string; regressions: string[]; timestamp: Date }
  | { type: "improvement:applying"; proposalId: string; adaptation: string; config: Record<string, unknown>; timestamp: Date }
  | { type: "improvement:reverting"; proposalId: string; adaptation: string; timestamp: Date }
  | { type: "improvement:reverted"; proposalId: string; reason: string; timestamp: Date }
  | { type: "improvement:confirmed"; proposalId: string; improvements: string[]; timestamp: Date }
  | { type: "improvement:thrashing-detected"; adaptationType: string; revertRate: number; total: number; timestamp: Date }
   | { type: "improvement:meta-learning"; adjustments: string[]; timestamp: Date }
    // ── Macro-Dialectic events (Triad: Yang + Yin + Unity) ───────────────────
    | { type: "macro-dialectic:triad-ready"; workspaceId: string; yang: { providerId: string; model: string }; yin: { providerId: string; model: string }; unity: { providerId: string; model: string }; timestamp: Date }
    | { type: "macro-dialectic:triad-degraded"; workspaceId: string; degradedRole: "yang" | "yin" | "unity"; reason: string; timestamp: Date }
    | { type: "macro-dialectic:triad-stopped"; workspaceId: string; reason: string; turnsProcessed: number; timestamp: Date }
    | { type: "macro-dialectic:turn-start"; workspaceId: string; sessionId: string; messageId: string; source: string; timestamp: Date }
    | { type: "macro-dialectic:turn-end"; workspaceId: string; sessionId: string; durationMs: number; yangChunks: number; yinChunks: number; toolRequestsProcessed: number; timestamp: Date }
    | { type: "macro-dialectic:reasoning-chunk"; workspaceId: string; chunkId: string; source: "yang" | "yin"; sequenceIndex: number; isFinal: boolean; timestamp: Date }
    | { type: "macro-dialectic:tool-request"; requestId: string; requester: "yang" | "yin"; tool: string; priority: "immediate" | "normal" | "background"; tier: "read" | "write" | "destructive"; timestamp: Date }
    | { type: "macro-dialectic:tool-request-amended"; requestId: string; amender: "yang" | "yin"; reject: boolean; timestamp: Date }
    | { type: "macro-dialectic:tool-executed"; workspaceId: string; requestId: string; tool: string; isError: boolean; durationMs: number; timestamp: Date }
    | { type: "macro-dialectic:tool-request-rejected"; requestId: string; tool: string; requester: "yang" | "yin"; timestamp: Date }
    | { type: "macro-dialectic:lock-acquired"; lockId: string; resource: string; tier: "read" | "write" | "destructive"; requestId: string; timestamp: Date }
    | { type: "macro-dialectic:lock-released"; lockId: string; resource: string; timestamp: Date }
    | { type: "macro-dialectic:convergence"; workspaceId: string; sessionId: string; yangPosition: string; yinPosition: string; confidence: number; timestamp: Date }
    | { type: "macro-dialectic:divergence"; workspaceId: string; sessionId: string; yangPosition: string; yinPosition: string; tensionLevel: number; timestamp: Date }
    | { type: "macro-dialectic:unity-stream-chunk"; workspaceId: string; sessionId: string; chunkIndex: number; text: string; timestamp: Date }
    | { type: "macro-dialectic:unity-complete"; workspaceId: string; sessionId: string; toolsExecuted: number; durationMs: number; timestamp: Date }
   // Triad Team events — hierarchical dialectic team system
   | { type: "triad-team:created"; teamId: string; entityId: string; message: string; timestamp: Date }
   | { type: "triad-team:started"; teamId: string; entityId: string; message: string; timestamp: Date }
   | { type: "triad-team:planning"; teamId: string; entityId: string; message: string; timestamp: Date }
   | { type: "triad-team:plan-complete"; teamId: string; entityId: string; message: string; timestamp: Date }
   | { type: "triad-team:cell-spawned"; teamId: string; entityId: string; message: string; timestamp: Date }
   | { type: "triad-team:cell-phase"; teamId: string; entityId: string; message: string; phase: string; timestamp: Date }
   | { type: "triad-team:cell-completed"; teamId: string; entityId: string; message: string; timestamp: Date }
   | { type: "triad-team:cell-failed"; teamId: string; entityId: string; message: string; timestamp: Date }
   | { type: "triad-team:cell-degraded"; teamId: string; entityId: string; message: string; timestamp: Date }
   | { type: "triad-team:synthesis"; teamId: string; entityId: string; message: string; timestamp: Date }
   | { type: "triad-team:completed"; teamId: string; entityId: string; message: string; timestamp: Date }
   | { type: "triad-team:failed"; teamId: string; entityId: string; message: string; timestamp: Date }
   | { type: "triad-team:cancelled"; teamId: string; entityId: string; message: string; timestamp: Date }
   | { type: "triad-team:paused"; teamId: string; entityId: string; message: string; timestamp: Date }
   | { type: "triad-team:resumed"; teamId: string; entityId: string; message: string; timestamp: Date }
   | { type: "triad-team:checkpoint"; teamId: string; entityId: string; message: string; timestamp: Date }
   | { type: "triad-team:checkpoint:approved"; teamId: string; entityId: string; message: string; timestamp: Date }
   | { type: "triad-team:checkpoint:rejected"; teamId: string; entityId: string; message: string; timestamp: Date }
   | { type: "triad-team:budget-warning"; teamId: string; entityId: string; message: string; timestamp: Date }
  // ── Tool Loop Mid-Round events ────────────────────────────────────────
  | {
      type: "tool:round-complete";
      sessionId: string;
      round: number;
      toolCalls: Array<{ name: string; id: string }>;
      results: Array<{ toolCallId: string; isError: boolean; contentPreview: string }>;
      timestamp: Date;
    }
  | {
      type: "intelligence:mid-loop-injection";
      sessionId: string;
      source: string;
      charCount: number;
      round: number;
      method: "text-block" | "content-append";
      timestamp: Date;
    }
  | {
      type: "user:mid-turn-message";
      sessionId: string;
      content: string;
      source: string;
      timestamp: Date;
    }
  // ── Background Job events ──────────────────────────────────────────
  | { type: "job:started"; jobId: string; label: string; command: string; sessionId?: string }
  | { type: "job:completed"; jobId: string; label: string; exitCode?: number; duration: number; summary: string; sessionId?: string }
  | { type: "job:failed"; jobId: string; label: string; exitCode?: number; duration: number; summary: string; sessionId?: string }
  | { type: "job:cancelled"; jobId: string; label: string; exitCode?: number; duration: number; summary: string; sessionId?: string }
  | { type: "job:timeout"; jobId: string; label: string; duration: number; summary: string; sessionId?: string }
  // ── Triad Team Context Management events ───────────────────────────
  | {
      type: "triad-team:context-validated";
      cellId: string;
      tokens: number;
      budget: number;
      utilization: number;
      source: "tiktoken" | "provider" | "char-estimate";
      modelId: string;
      timestamp: Date;
    }
  | {
      type: "triad-team:context-pruned";
      cellId: string;
      originalTokens: number;
      prunedTokens: number;
      budget: number;
      sectionsDropped: string[];
      timestamp: Date;
    }
  | {
      type: "triad-team:context-trimmed";
      cellId: string;
      direction: "parent-down" | "child-up";
      originalChars: number;
      trimmedChars: number;
      depth: number;
      timestamp: Date;
    }
  | {
      type: "triad-team:budget-warning";
      cellId: string;
      tokens: number;
      budget: number;
      utilization: number;
      phase: string;
      timestamp: Date;
    }
  // ── OpenCode Channel events ────────────────────────────────────────
  | { type: "opencode:mode-change"; mode: "sse" | "sqlite" | "hybrid"; reason: string; timestamp: Date };

export type EventType = RuntimeEvent["type"];

/** Extract the event shape for a given type literal */
export type EventOf<T extends EventType> = Extract<RuntimeEvent, { type: T }>;

/** Unsubscribe function returned by EventBus.on() */
export type Unsubscribe = () => void;
