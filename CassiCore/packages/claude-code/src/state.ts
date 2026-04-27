/**
 * Per-session state tracking for Claude Code integration.
 *
 * Tracks tool calls, active files, pressure estimates, and reference boosts
 * across a Claude Code session. Used by the hook server to decide what
 * context to inject and when to warn about pressure.
 */

export type ToolImportance = "strategic" | "file-read" | "code-intel" | "edit" | "transient" | "default";
export type PressureTier = "healthy" | "warming" | "elevated" | "high" | "critical" | "overflow";

export interface SessionState {
  sessionId: string;
  ccSessionId: string;
  turnCount: number;
  toolCallCount: number;
  activeFiles: string[];
  focusTopic: string;
  usedTools: Set<string>;
  /** Estimated token pressure (0-1) from transcript analysis */
  estimatedPressure: number;
  /** Last known pressure tier */
  lastTier: PressureTier;
  /** Whether a pressure warning was already injected this tier */
  warnedAtTier: PressureTier;
  /** Attention-weighted reference boosts: identity -> multiplier */
  referenceBoosts: Map<string, number>;
  /** Whether emergency handoff has been written */
  handoffWritten: boolean;
  /** Last checkpoint timestamp */
  lastCheckpointAt: number;
  /** Last working state post timestamp */
  lastWorkingStateAt: number;
  /** Turn-level large output tracking */
  largeOutputsThisTurn: number;
  /** Compaction count */
  compactionCount: number;
  /** Whether we're in post-compaction recovery */
  postCompaction: boolean;
  /** Timestamp of last activity */
  lastActivityAt: number;
  /** Progressive disclosure: signal -> turns since referenced */
  signalAges: Map<string, number>;
  createdAt: number;
  /** Wall-clock time of the current turn's start (set on UserPromptSubmit). */
  turnStartedAt: number;
  /** The user's message for the in-flight turn (used for turn:start emission). */
  turnUserMessage: string;
  /** Pending tool calls in the current round, keyed by tool_use_id. */
  pendingToolCalls: Map<string, { name: string; id: string }>;
  /** Tool results captured for the current round (paired with pendingToolCalls). */
  pendingToolResults: Map<string, { toolCallId: string; isError: boolean; contentPreview: string }>;
  /** Monotonic round counter for tool:round-complete events. */
  toolRoundCount: number;
}

const sessions = new Map<string, SessionState>();
const MAX_SESSIONS = 100;

export function getSession(sessionId: string): SessionState {
  let s = sessions.get(sessionId);
  if (!s) {
    evictOldestSessionIfNeeded();
    const ccId = sessionId.startsWith("cc:") ? sessionId : `cc:${sessionId}`;
    s = {
      sessionId,
      ccSessionId: ccId,
      turnCount: 0,
      toolCallCount: 0,
      activeFiles: [],
      focusTopic: "",
      usedTools: new Set(),
      estimatedPressure: 0,
      lastTier: "healthy",
      warnedAtTier: "healthy",
      referenceBoosts: new Map(),
      handoffWritten: false,
      lastCheckpointAt: 0,
      lastWorkingStateAt: 0,
      largeOutputsThisTurn: 0,
      compactionCount: 0,
      postCompaction: false,
      lastActivityAt: Date.now(),
      turnStartedAt: 0,
      turnUserMessage: "",
      pendingToolCalls: new Map(),
      pendingToolResults: new Map(),
      toolRoundCount: 0,
      signalAges: new Map(),
      createdAt: Date.now(),
    };
    sessions.set(sessionId, s);
  }
  s.lastActivityAt = Date.now();
  return s;
}

function evictOldestSessionIfNeeded(): void {
  if (sessions.size < MAX_SESSIONS) return;
  let oldestId: string | undefined;
  let oldestAt = Number.POSITIVE_INFINITY;
  for (const [id, state] of sessions) {
    if (state.lastActivityAt < oldestAt) {
      oldestAt = state.lastActivityAt;
      oldestId = id;
    }
  }
  if (oldestId) sessions.delete(oldestId);
}

export function classifyTier(pressure: number): PressureTier {
  if (pressure > 0.92) return "overflow";
  if (pressure > 0.85) return "critical";
  if (pressure > 0.78) return "high";
  if (pressure > 0.70) return "elevated";
  if (pressure > 0.50) return "warming";
  return "healthy";
}

export function classifyToolImportance(toolName: string): ToolImportance {
  const t = toolName.toLowerCase();
  if (/^(mcp__cassicore__|cassi_)(blackboard|memory|agent|intelligence|session)/.test(t)) return "strategic";
  if (/^(context_manifest|context_modify|context_expand|cassi_todo|todowrite|questions?)$/.test(t)) return "strategic";
  if (/^(read|mcp__.*__read)$/i.test(t)) return "file-read";
  if (/^(edit|write|mcp__.*__(edit|write|replace|insert|rename))$/i.test(t)) return "edit";
  if (/^(bash|glob|grep|webfetch|websearch|mcp__.*__(search|find|list))$/i.test(t)) return "transient";
  return "default";
}

/**
 * Estimate context pressure from transcript file size.
 * This is a rough heuristic since we can't access the actual token count.
 * Assumes ~4 chars per token and a 200K token context window.
 */
import fs from "node:fs";

export function estimatePressureFromTranscript(transcriptPath: string): number {
  try {
    const stats = fs.statSync(transcriptPath);
    const bytes = stats.size;
    // Rough: JSONL transcript bytes -> estimated tokens in context
    // Transcript includes metadata, so actual context is ~60% of transcript
    const estimatedTokens = (bytes * 0.6) / 4;
    const contextLimit = 200_000; // Claude default
    return Math.min(1.0, estimatedTokens / contextLimit);
  } catch {
    return 0;
  }
}

// Cleanup idle sessions every 30 minutes
setInterval(() => {
  const cutoff = Date.now() - 2 * 60 * 60_000;
  for (const [id, state] of sessions) {
    if (state.lastActivityAt < cutoff) sessions.delete(id);
  }
}, 30 * 60_000);
