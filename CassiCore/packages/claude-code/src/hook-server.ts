#!/usr/bin/env npx tsx
/**
 * CassiCore Hook Server for Claude Code
 *
 * Persistent HTTP server that handles Claude Code hook events and injects
 * CassiCore's intelligence layer into the conversation via additionalContext.
 *
 * This is the deep integration layer — while the MCP server provides tools,
 * the hook server provides CONTEXT. It injects cognitive signals, manages
 * pressure, handles checkpointing, and coordinates with the Thinker.
 *
 * Hook flow:
 *   SessionStart → inject initial cognitive context
 *   UserPromptSubmit → inject fresh signals + index prompt
 *   PreToolUse → pressure-based input modification
 *   PostToolUse → record output, inject pressure warnings
 *   PreCompact → save structured checkpoint
 *   PostCompact → inject recovery context
 *   Stop → ingest events, post working state
 *
 * Runs on port 7434 (CassiCore admin is 7433).
 */

import http from "node:http";
import fs from "node:fs";
import { integrationLogger } from "./logger.js";
import * as bridge from "./bridge.js";
import {
  getSession,
  classifyTier,
  classifyToolImportance,
  estimatePressureFromTranscript,
  type SessionState,
} from "./state.js";
import {
  buildCognitiveContext,
  buildPressureWarning,
} from "./context-builder.js";

const PORT = parseInt(process.env.CASSICORE_HOOK_PORT ?? "7434", 10);
const MAX_BODY_BYTES = 8 * 1024 * 1024;
const logger = integrationLogger.child("hook-server");

interface HookInput {
  session_id: string;
  cwd: string;
  hook_event_name: string;
  permission_mode?: string;
  agent_id?: string;
  agent_type?: string;
  transcript_path?: string;
  // PreToolUse / PostToolUse
  tool_name?: string;
  tool_input?: Record<string, unknown>;
  tool_output?: string;
  tool_is_error?: boolean;
  // UserPromptSubmit
  prompt?: string;
  message?: string;
}

interface HookOutput {
  continue?: boolean;
  suppressOutput?: boolean;
  systemMessage?: string;
  additionalContext?: string;
  hookSpecificOutput?: Record<string, unknown>;
}

async function handleSessionStart(input: HookInput): Promise<HookOutput> {
  const state = getSession(input.session_id);

  // Update pressure estimate from transcript
  if (input.transcript_path) {
    state.estimatedPressure = estimatePressureFromTranscript(input.transcript_path);
  }

  bridge.ingestEvents(state.ccSessionId, [{
    type: "session_start",
    sessionId: state.ccSessionId,
    source: "claude-code",
    timestamp: Date.now(),
  }]).catch(() => {});

  bridge.cortexSignal(
    state.ccSessionId,
    "perception",
    "sensory",
    `Claude Code session started in ${input.cwd || "unknown workspace"}`,
    ["claude-code", "session-start"],
    0.7,
  ).catch(() => {});
  bridge.laminaAppend(
    state.ccSessionId,
    "session-decisions",
    `Claude Code session started in ${input.cwd || "unknown workspace"}.`,
    "claude-code-session-start",
  ).catch(() => {});
  bridge.memoryStoreEpisode(
    state.ccSessionId,
    `[Claude Code session started]\nWorkspace: ${input.cwd || "unknown"}\nSession: ${state.ccSessionId}`,
    ["claude-code", "session-start", state.ccSessionId],
    "conversation",
  ).catch(() => {});
  bridge.reveriePing(state.ccSessionId, "claude-code-session-start").catch(() => {});

  const context = await buildCognitiveContext(state, { compact: false });

  return context
    ? { additionalContext: context }
    : {};
}

async function handleUserPromptSubmit(input: HookInput): Promise<HookOutput> {
  const state = getSession(input.session_id);
  state.turnCount++;
  state.largeOutputsThisTurn = 0;
  state.turnStartedAt = Date.now();
  state.turnUserMessage = input.prompt ?? "";
  state.pendingToolCalls.clear();
  state.pendingToolResults.clear();

  if (input.transcript_path) {
    state.estimatedPressure = estimatePressureFromTranscript(input.transcript_path);
  }

  for (const [key, age] of state.signalAges) {
    state.signalAges.set(key, age + 1);
  }

  const prompt = input.prompt ?? "";
  if (/dialectic|yang|yin/i.test(prompt)) state.signalAges.set("dialectic", 0);
  if (/anomal/i.test(prompt)) state.signalAges.set("anomalies", 0);

  if (prompt) {
    bridge.index(state.ccSessionId, [{ role: "user", content: prompt }]);
  }

  // Emit canonical turn:start so Reverie, memory, thinker, and every
  // BaseCognitiveModule.onTurnStart hook fires for this Claude Code turn.
  if (prompt) {
    bridge.emitTurnStart(state.ccSessionId, prompt).catch(() => {});

    // Mirror as a user_message event so the admin-api conversation-history
    // interceptor captures it on the same path as Opencode sessions.
    bridge.ingestEvents(state.ccSessionId, [{
      type: "user_message",
      content: prompt,
      source: "claude-code",
      timestamp: Date.now(),
    }]).catch(() => {});

    bridge.cortexSignal(
      state.ccSessionId,
      "perception",
      "sensory",
      prompt.slice(0, 500),
      ["claude-code", "user-prompt"],
      0.75,
    ).catch(() => {});
    bridge.laminaRethink(
      state.ccSessionId,
      "open-hypotheses",
      `Current Claude Code user request:\n${prompt.slice(0, 2000)}`,
      "claude-code-user-prompt",
    ).catch(() => {});
    bridge.memoryStoreEpisode(
      state.ccSessionId,
      `[Claude Code user prompt]\n${prompt.slice(0, 8000)}`,
      ["claude-code", "user-prompt", state.ccSessionId],
      "conversation",
    ).catch(() => {});
    bridge.reveriePing(state.ccSessionId, "claude-code-user-prompt").catch(() => {});
  }

  if (prompt && prompt.length > 5) {
    await bridge.auroraObserve(prompt).catch(() => {});
  }

  if (prompt && prompt.length > 5) {
    bridge.workspaceEnrich(prompt, state.ccSessionId).catch(() => {});
  }

  const context = await buildCognitiveContext(state, {
    includeRecovery: state.postCompaction,
    compact: state.estimatedPressure > 0.5,
  });

  if (state.postCompaction) state.postCompaction = false;

  return context
    ? { additionalContext: context }
    : {};
}

async function handlePreToolUse(input: HookInput): Promise<HookOutput> {
  const state = getSession(input.session_id);
  const toolName = input.tool_name ?? "";

  if (toolName) {
    const id = (input.tool_input?.tool_use_id as string | undefined)
      ?? `${input.session_id}-${state.toolRoundCount}-${state.toolCallCount}`;
    state.pendingToolCalls.set(id, { name: toolName, id });
    bridge.cortexSignal(
      state.ccSessionId,
      "decision",
      "executive",
      `Claude Code preparing tool ${toolName}`,
      ["claude-code", "pre-tool-use", toolName],
      0.55,
    ).catch(() => {});
    bridge.ingestEvents(state.ccSessionId, [{
      type: "tool_call_start",
      sessionId: state.ccSessionId,
      toolName,
      toolCallId: id,
      source: "claude-code",
      timestamp: Date.now(),
    }]).catch(() => {});
  }

  if (input.transcript_path) {
    state.estimatedPressure = estimatePressureFromTranscript(input.transcript_path);
  }

  state.usedTools.add(toolName);
  state.toolCallCount++;

  if (/^(read|mcp__.*__read)/i.test(toolName)) {
    const filePath = input.tool_input?.file_path ?? input.tool_input?.path;
    if (typeof filePath === "string" && !state.activeFiles.includes(filePath)) {
      state.activeFiles.push(filePath);
      if (state.activeFiles.length > 20) state.activeFiles.shift();
    }
  }

  const tier = classifyTier(state.estimatedPressure);
  if (tier === "critical" || tier === "overflow") {
    const importance = classifyToolImportance(toolName);
    if (importance === "file-read" && input.tool_input) {
      const existingLimit = input.tool_input.limit as number | undefined;
      if (!existingLimit || existingLimit > 200) {
        return {
          additionalContext: `Context pressure is ${tier}. Consider reading only the specific lines you need (use offset/limit parameters) rather than full files.`,
        };
      }
    }
  }

  return {};
}

async function handlePostToolUse(input: HookInput): Promise<HookOutput> {
  const state = getSession(input.session_id);
  const toolName = input.tool_name ?? "";
  const output = input.tool_output ?? "";

  if (input.transcript_path) {
    state.estimatedPressure = estimatePressureFromTranscript(input.transcript_path);
  }

  if (output.length > 10_000) {
    state.largeOutputsThisTurn++;
  }

  if (output.length > 0 && output.length < 50_000) {
    bridge.index(state.ccSessionId, [{
      role: "assistant",
      content: `[${toolName}] ${output.slice(0, 5000)}`,
    }]);
  }

  if (toolName) {
    const isError = input.tool_is_error === true || /error/i.test(output.slice(0, 200));
    bridge.cortexSignal(
      state.ccSessionId,
      isError ? "concern" : "action",
      isError ? "limbic" : "motor",
      `Claude Code tool ${toolName} ${isError ? "errored" : "completed"}: ${output.slice(0, 700)}`,
      ["claude-code", "post-tool-use", toolName, isError ? "error" : "success"],
      isError ? 0.8 : 0.6,
    ).catch(() => {});
    bridge.memoryStoreEpisode(
      state.ccSessionId,
      `[Claude Code tool ${toolName} ${isError ? "error" : "result"}]\n${output.slice(0, 8000)}`,
      ["claude-code", "tool-result", toolName, state.ccSessionId],
      isError ? "error" : "observation",
    ).catch(() => {});
  }

  const toolUseId = (input.tool_input?.tool_use_id as string | undefined);
  let pairedId: string | undefined;
  if (toolUseId && state.pendingToolCalls.has(toolUseId)) {
    pairedId = toolUseId;
  } else {
    const lastKey = Array.from(state.pendingToolCalls.keys()).pop();
    if (lastKey) pairedId = lastKey;
  }
  if (pairedId) {
    const call = state.pendingToolCalls.get(pairedId);
    state.pendingToolCalls.delete(pairedId);
    state.toolRoundCount += 1;
    if (call) {
      bridge.emitToolRound(
        state.ccSessionId,
        state.toolRoundCount,
        [call],
        [{
          toolCallId: pairedId,
          isError: /error/i.test(output.slice(0, 200)),
          contentPreview: output.slice(0, 1000),
        }],
      ).catch(() => {});
    }
  }

  const warning = buildPressureWarning(state);
  if (warning) {
    return { additionalContext: warning };
  }

  const now = Date.now();
  if (now - state.lastWorkingStateAt > 15_000) {
    state.lastWorkingStateAt = now;
    postWorkingState(state);
  }

  return {};
}

async function handlePreCompact(input: HookInput): Promise<HookOutput> {
  const state = getSession(input.session_id);

  await saveCheckpoint(state, input.transcript_path);

  if (!state.handoffWritten) {
    state.handoffWritten = true;
    const handoff = {
      sessionId: state.ccSessionId,
      timestamp: Date.now(),
      trigger: `compaction at turn ${state.turnCount}`,
      focusTopic: state.focusTopic,
      activeFiles: state.activeFiles.slice(0, 10),
      usedTools: [...state.usedTools].slice(-15),
      turnCount: state.turnCount,
      criticalContext: [
        state.focusTopic ? `Focus: ${state.focusTopic}` : null,
        state.activeFiles.length > 0 ? `Active files: ${state.activeFiles.slice(0, 5).join(", ")}` : null,
        `Tools used: ${[...state.usedTools].slice(-5).join(", ")}`,
      ].filter(Boolean),
    };
    bridge.kvSet(`handoff:${state.ccSessionId}`, handoff);
  }

  if (input.transcript_path) {
    try {
      const transcript = fs.readFileSync(input.transcript_path, "utf-8");
      const messages = transcript.split("\n").filter(Boolean).map(line => {
        try { return JSON.parse(line); } catch { return null; }
      }).filter(Boolean);

      if (messages.length > 0) {
        bridge.index(state.ccSessionId, messages.slice(-50).map((m: any) => ({
          role: m.role ?? "user",
          content: typeof m.content === "string" ? m.content : JSON.stringify(m.content),
        })));
      }
    } catch {
      logger.debug("transcript read failed during pre-compact", { sessionId: state.ccSessionId });
    }
  }

  state.compactionCount++;

  bridge.ingestEvents(state.ccSessionId, [{
    type: "compaction_start",
    sessionId: state.ccSessionId,
    compactionCount: state.compactionCount,
    turnCount: state.turnCount,
    timestamp: Date.now(),
  }]).catch(() => {});

  bridge.cortexSignal(
    state.ccSessionId,
    "decision",
    "executive",
    `Claude Code pre-compaction checkpoint saved at turn ${state.turnCount}`,
    ["claude-code", "pre-compact"],
    0.8,
  ).catch(() => {});
  bridge.laminaAppend(
    state.ccSessionId,
    "session-decisions",
    `Pre-compaction checkpoint saved at turn ${state.turnCount}. Active files: ${state.activeFiles.slice(0, 5).join(", ") || "none"}.`,
    "claude-code-pre-compact",
  ).catch(() => {});
  bridge.memoryStoreEpisode(
    state.ccSessionId,
    `[Claude Code pre-compaction checkpoint]\nTurn: ${state.turnCount}\nActive files: ${state.activeFiles.slice(0, 10).join(", ")}`,
    ["claude-code", "pre-compact", state.ccSessionId],
    "conversation",
  ).catch(() => {});
  bridge.reveriePing(state.ccSessionId, "claude-code-pre-compact").catch(() => {});

  return {
    systemMessage: "CassiCore: checkpoint saved before compaction",
  };
}

async function handlePostCompact(input: HookInput): Promise<HookOutput> {
  const state = getSession(input.session_id);
  state.postCompaction = true;
  state.handoffWritten = false;

  const recovery = await buildCognitiveContext(state, {
    includeRecovery: true,
    compact: false,
  });

  bridge.ingestEvents(state.ccSessionId, [{
    type: "compaction_complete",
    sessionId: state.ccSessionId,
    compactionCount: state.compactionCount,
    timestamp: Date.now(),
  }]).catch(() => {});

  bridge.cortexSignal(
    state.ccSessionId,
    "perception",
    "sensory",
    `Claude Code compaction completed after ${state.compactionCount} compactions` ,
    ["claude-code", "post-compact"],
    0.7,
  ).catch(() => {});
  bridge.laminaAppend(
    state.ccSessionId,
    "open-hypotheses",
    `Post-compaction recovery is active for Claude Code session ${state.ccSessionId}.`,
    "claude-code-post-compact",
  ).catch(() => {});
  bridge.memoryStoreEpisode(
    state.ccSessionId,
    `[Claude Code post-compaction recovery]\nCompaction count: ${state.compactionCount}`,
    ["claude-code", "post-compact", state.ccSessionId],
    "conversation",
  ).catch(() => {});
  bridge.reveriePing(state.ccSessionId, "claude-code-post-compact").catch(() => {});

  return recovery
    ? { additionalContext: recovery }
    : {};
}

async function handleStop(input: HookInput): Promise<HookOutput> {
  const state = getSession(input.session_id);

  if (input.transcript_path) {
    state.estimatedPressure = estimatePressureFromTranscript(input.transcript_path);
  }

  postWorkingState(state);

  bridge.ingestEvents(state.ccSessionId, [{
    type: "turn_complete",
    sessionId: state.ccSessionId,
    turnCount: state.turnCount,
    toolCallCount: state.toolCallCount,
    activeFiles: state.activeFiles.slice(0, 10),
    estimatedPressure: state.estimatedPressure,
    largeOutputs: state.largeOutputsThisTurn,
    timestamp: Date.now(),
  }]).catch(() => {});

  // Emit canonical turn:end so Reverie.onTurnEnd, memory consolidation, and
  // every BaseCognitiveModule lifecycle hook fires for this Claude Code turn.
  // The "response" is best-effort — we don't have the assistant text here, so
  // pass the user message + a turn-stats sentinel as the payload Reverie uses
  // for change detection.
  const durationMs = state.turnStartedAt > 0 ? Date.now() - state.turnStartedAt : 0;
  bridge.emitTurnEnd(
    state.ccSessionId,
    `[claude-code turn ${state.turnCount} complete: ${state.toolCallCount} tools, ${state.activeFiles.slice(0, 3).join(", ")}]`,
    durationMs,
  ).catch(() => {});

  bridge.reveriePing(state.ccSessionId, "claude-code-turn-end").catch(() => {});

  // Mirror as assistant_message for the conversation-history interceptor.
  // Best-effort summary — full assistant text isn't available at hook time,
  // but the user_message+turn-stats pair is enough for cross-session memory.
  bridge.ingestEvents(state.ccSessionId, [{
    type: "assistant_message",
    content: `[claude-code turn ${state.turnCount} complete]`,
    source: "claude-code",
    timestamp: Date.now(),
  }]).catch(() => {});
  bridge.cortexSignal(
    state.ccSessionId,
    "decision",
    "executive",
    `Claude Code turn ${state.turnCount} stopped after ${state.toolCallCount} tools` ,
    ["claude-code", "stop", "turn-end"],
    0.65,
  ).catch(() => {});
  bridge.memoryStoreEpisode(
    state.ccSessionId,
    `[Claude Code turn complete]\nTurn: ${state.turnCount}\nTools: ${state.toolCallCount}\nActive files: ${state.activeFiles.slice(0, 10).join(", ")}`,
    ["claude-code", "turn-complete", state.ccSessionId],
    "conversation",
  ).catch(() => {});

  return {};
}

async function handleNotification(input: HookInput): Promise<HookOutput> {
  const state = getSession(input.session_id);
  const content = input.message ?? input.prompt ?? "Claude Code notification";

  bridge.ingestEvents(state.ccSessionId, [{
    type: "notification",
    sessionId: state.ccSessionId,
    content,
    source: "claude-code",
    timestamp: Date.now(),
  }]).catch(() => {});
  bridge.cortexSignal(
    state.ccSessionId,
    "perception",
    "sensory",
    `Claude Code notification: ${content.slice(0, 700)}`,
    ["claude-code", "notification"],
    0.55,
  ).catch(() => {});
  bridge.memoryStoreEpisode(
    state.ccSessionId,
    `[Claude Code notification]\n${content.slice(0, 4000)}`,
    ["claude-code", "notification", state.ccSessionId],
    "observation",
  ).catch(() => {});
  bridge.reveriePing(state.ccSessionId, "claude-code-notification").catch(() => {});

  return {};
}

async function handleSubagentStart(input: HookInput): Promise<HookOutput> {
  const state = getSession(input.session_id);

  bridge.ingestEvents(state.ccSessionId, [{
    type: "subagent_start",
    sessionId: state.ccSessionId,
    agentId: input.agent_id,
    agentType: input.agent_type,
    timestamp: Date.now(),
  }]).catch(() => {});
  bridge.cortexSignal(
    state.ccSessionId,
    "decision",
    "executive",
    `Claude Code subagent started: ${input.agent_type ?? "unknown"}`,
    ["claude-code", "subagent-start"],
    0.7,
  ).catch(() => {});
  bridge.memoryStoreEpisode(
    state.ccSessionId,
    `[Claude Code subagent started]\nAgent id: ${input.agent_id ?? "unknown"}\nAgent type: ${input.agent_type ?? "unknown"}`,
    ["claude-code", "subagent", "subagent-start", state.ccSessionId],
    "conversation",
  ).catch(() => {});
  bridge.helixJournalAppend(
    state.ccSessionId,
    "session.start",
    {
      agentId: input.agent_id ?? null,
      agentType: input.agent_type ?? null,
      hookEvent: "SubagentStart",
    },
    input.agent_id,
  ).catch(() => {});
  bridge.reveriePing(state.ccSessionId, "claude-code-subagent-start").catch(() => {});

  return {};
}

async function handleSubagentStop(input: HookInput): Promise<HookOutput> {
  const state = getSession(input.session_id);

  bridge.ingestEvents(state.ccSessionId, [{
    type: "subagent_stop",
    sessionId: state.ccSessionId,
    agentId: input.agent_id,
    agentType: input.agent_type,
    timestamp: Date.now(),
  }]).catch(() => {});
  bridge.cortexSignal(
    state.ccSessionId,
    "action",
    "motor",
    `Claude Code subagent stopped: ${input.agent_type ?? "unknown"}`,
    ["claude-code", "subagent-stop"],
    0.65,
  ).catch(() => {});
  bridge.memoryStoreEpisode(
    state.ccSessionId,
    `[Claude Code subagent stopped]\nAgent id: ${input.agent_id ?? "unknown"}\nAgent type: ${input.agent_type ?? "unknown"}`,
    ["claude-code", "subagent", "subagent-stop", state.ccSessionId],
    "conversation",
  ).catch(() => {});
  bridge.helixJournalAppend(
    state.ccSessionId,
    "session.terminate",
    {
      agentId: input.agent_id ?? null,
      agentType: input.agent_type ?? null,
      hookEvent: "SubagentStop",
    },
    input.agent_id,
  ).catch(() => {});
  bridge.reveriePing(state.ccSessionId, "claude-code-subagent-stop").catch(() => {});

  return {};
}

async function handleSessionEnd(input: HookInput): Promise<HookOutput> {
  const state = getSession(input.session_id);

  if (input.transcript_path) {
    state.estimatedPressure = estimatePressureFromTranscript(input.transcript_path);
  }

  postWorkingState(state);

  bridge.ingestEvents(state.ccSessionId, [{
    type: "session_end",
    sessionId: state.ccSessionId,
    turnCount: state.turnCount,
    toolCallCount: state.toolCallCount,
    estimatedPressure: state.estimatedPressure,
    timestamp: Date.now(),
  }]).catch(() => {});
  bridge.cortexSignal(
    state.ccSessionId,
    "decision",
    "executive",
    `Claude Code session ended after ${state.turnCount} turns and ${state.toolCallCount} tools`,
    ["claude-code", "session-end"],
    0.8,
  ).catch(() => {});
  bridge.laminaAppend(
    state.ccSessionId,
    "session-decisions",
    `Claude Code session ended after ${state.turnCount} turns and ${state.toolCallCount} tool calls.`,
    "claude-code-session-end",
  ).catch(() => {});
  bridge.memoryStoreEpisode(
    state.ccSessionId,
    `[Claude Code session ended]\nTurns: ${state.turnCount}\nTools: ${state.toolCallCount}\nPressure: ${state.estimatedPressure}`,
    ["claude-code", "session-end", state.ccSessionId],
    "conversation",
  ).catch(() => {});
  bridge.reveriePing(state.ccSessionId, "claude-code-session-end").catch(() => {});

  return {};
}

function postWorkingState(state: SessionState): void {
  const workingState = {
    sessionId: state.ccSessionId,
    timestamp: Date.now(),
    turnCount: state.turnCount,
    pressure: state.estimatedPressure,
    tier: classifyTier(state.estimatedPressure),
    mode: "working",
    focusTopic: state.focusTopic,
    activeFiles: state.activeFiles.slice(0, 10),
    toolCallCount: state.toolCallCount,
    largeOutputsThisTurn: state.largeOutputsThisTurn,
  };
  bridge.kvSet(`working-state:${state.ccSessionId}`, workingState);
  bridge.laminaAppend(
    state.ccSessionId,
    "session-decisions",
    `Working state: turn ${state.turnCount}, ${state.toolCallCount} tools, pressure ${classifyTier(state.estimatedPressure)}. Active files: ${state.activeFiles.slice(0, 5).join(", ") || "none"}.`,
    "claude-code-working-state",
  ).catch(() => {});
}

async function saveCheckpoint(state: SessionState, transcriptPath?: string): Promise<void> {
  const checkpoint = {
    sessionId: state.ccSessionId,
    timestamp: Date.now(),
    turnCount: state.turnCount,
    pressure: state.estimatedPressure,
    tier: classifyTier(state.estimatedPressure),
    focusTopic: state.focusTopic,
    activeFiles: state.activeFiles.slice(0, 10),
    usedTools: [...state.usedTools].slice(-20),
    compactionCount: state.compactionCount,
  };
  bridge.kvSet(`checkpoint:${state.ccSessionId}`, checkpoint);
  state.lastCheckpointAt = Date.now();
}

const ROUTE_MAP: Record<string, (input: HookInput) => Promise<HookOutput>> = {
  SessionStart: handleSessionStart,
  UserPromptSubmit: handleUserPromptSubmit,
  PreToolUse: handlePreToolUse,
  PostToolUse: handlePostToolUse,
  PreCompact: handlePreCompact,
  PostCompact: handlePostCompact,
  Notification: handleNotification,
  Stop: handleStop,
  SubagentStart: handleSubagentStart,
  SubagentStop: handleSubagentStop,
  SessionEnd: handleSessionEnd,
};

const server = http.createServer(async (req, res) => {
  // Health check
  if (req.url === "/health" && req.method === "GET") {
    const cassiUp = await bridge.available();
    res.writeHead(200, { "Content-Type": "application/json" });
    res.end(JSON.stringify({ status: "ok", cassicore: cassiUp }));
    return;
  }

  // All hook requests are POST
  if (req.method !== "POST") {
    res.writeHead(405);
    res.end();
    return;
  }

  const chunks: Buffer[] = [];
  let total = 0;
  try {
    for await (const chunk of req) {
      const buf = chunk as Buffer;
      total += buf.length;
      if (total > MAX_BODY_BYTES) {
        res.writeHead(413, { "Content-Type": "application/json" });
        res.end(JSON.stringify({ error: "body too large" }));
        req.destroy();
        return;
      }
      chunks.push(buf);
    }
  } catch {
    return;
  }

  let input: HookInput;
  try {
    input = JSON.parse(Buffer.concat(chunks).toString());
  } catch {
    res.writeHead(400, { "Content-Type": "application/json" });
    res.end(JSON.stringify({ error: "invalid JSON" }));
    return;
  }

  // Route by hook event name
  const eventName = input.hook_event_name ?? req.url?.replace(/^\/hooks\//, "") ?? "";
  const handler = ROUTE_MAP[eventName];

  if (!handler) {
    // Unknown hook — return empty (allow)
    res.writeHead(200, { "Content-Type": "application/json" });
    res.end("{}");
    return;
  }

  try {
    const result = await handler(input);

    // Build hook response
    const response: Record<string, unknown> = { continue: true };

    if (result.additionalContext) {
      response.additionalContext = result.additionalContext;
    }
    if (result.systemMessage) {
      response.systemMessage = result.systemMessage;
    }
    if (result.suppressOutput !== undefined) {
      response.suppressOutput = result.suppressOutput;
    }
    if (result.hookSpecificOutput) {
      response.hookSpecificOutput = {
        hookEventName: eventName,
        ...result.hookSpecificOutput,
      };
    }

    res.writeHead(200, { "Content-Type": "application/json" });
    res.end(JSON.stringify(response));
  } catch (err) {
    logger.error(`Hook ${eventName} error`, { error: String(err) });
    res.writeHead(200, { "Content-Type": "application/json" });
    res.end("{}");
  }
});

server.listen(PORT, "127.0.0.1", () => {
  logger.info(`CassiCore hook server listening on http://127.0.0.1:${PORT}`);
  bridge.available().then(up => {
    logger.info(`CassiCore daemon: ${up ? "connected" : "unavailable (will retry)"}`);
  });
});

// Graceful shutdown
process.on("SIGINT", () => { server.close(); process.exit(0); });
process.on("SIGTERM", () => { server.close(); process.exit(0); });
