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

// ── Hook Input Types ────────────────────────────────────────────────────────

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
}

interface HookOutput {
  continue?: boolean;
  suppressOutput?: boolean;
  systemMessage?: string;
  additionalContext?: string;
  hookSpecificOutput?: Record<string, unknown>;
}

// ── Hook Handlers ───────────────────────────────────────────────────────────

async function handleSessionStart(input: HookInput): Promise<HookOutput> {
  const state = getSession(input.session_id);

  // Update pressure estimate from transcript
  if (input.transcript_path) {
    state.estimatedPressure = estimatePressureFromTranscript(input.transcript_path);
  }

  // Notify CassiCore of new session
  bridge.ingestEvents(state.ccSessionId, [{
    type: "session_start",
    sessionId: state.ccSessionId,
    source: "claude-code",
    timestamp: Date.now(),
  }]).catch(() => {});

  // Build initial cognitive context
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

  // Update pressure from transcript
  if (input.transcript_path) {
    state.estimatedPressure = estimatePressureFromTranscript(input.transcript_path);
  }

  // Age all signal expansions (for progressive disclosure)
  for (const [key, age] of state.signalAges) {
    state.signalAges.set(key, age + 1);
  }

  // Check if the user prompt references any signals (reset progressive disclosure)
  const prompt = input.prompt ?? "";
  if (/dialectic|yang|yin/i.test(prompt)) state.signalAges.set("dialectic", 0);
  if (/anomal/i.test(prompt)) state.signalAges.set("anomalies", 0);

  // Index the prompt in CassiCore
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

    // Mirror perception into the Cortex working memory region so spreading
    // activation can pick it up on the next retrieval pass.
    bridge.cortexSignal(
      state.ccSessionId,
      "perception",
      "sensory",
      prompt.slice(0, 500),
      ["claude-code", "user-prompt"],
    ).catch(() => {});
  }

  // Feed prompt to Aurora for concept tracking and shift detection
  if (prompt && prompt.length > 5) {
    await bridge.auroraObserve(prompt).catch(() => {});
  }

  // Enrich workspace with memory signals (GWT fallback path)
  if (prompt && prompt.length > 5) {
    bridge.workspaceEnrich(prompt, state.ccSessionId).catch(() => {});
  }

  // Build cognitive context (Aurora-first with GWT fallback)
  const context = await buildCognitiveContext(state, {
    includeRecovery: state.postCompaction,
    compact: state.estimatedPressure > 0.5,
  });

  // Clear post-compaction flag after first injection
  if (state.postCompaction) state.postCompaction = false;

  return context
    ? { additionalContext: context }
    : {};
}

async function handlePreToolUse(input: HookInput): Promise<HookOutput> {
  const state = getSession(input.session_id);
  const toolName = input.tool_name ?? "";

  // Capture the in-flight tool call so the matching PostToolUse can pair it
  // into a tool:round-complete event for Reverie's tool-log + loop detection.
  if (toolName) {
    const id = (input.tool_input?.tool_use_id as string | undefined)
      ?? `${input.session_id}-${state.toolRoundCount}-${state.toolCallCount}`;
    state.pendingToolCalls.set(id, { name: toolName, id });
  }

  // Update pressure
  if (input.transcript_path) {
    state.estimatedPressure = estimatePressureFromTranscript(input.transcript_path);
  }

  state.usedTools.add(toolName);
  state.toolCallCount++;

  // Track active files from Read tools
  if (/^(read|mcp__.*__read)/i.test(toolName)) {
    const filePath = input.tool_input?.file_path ?? input.tool_input?.path;
    if (typeof filePath === "string" && !state.activeFiles.includes(filePath)) {
      state.activeFiles.push(filePath);
      if (state.activeFiles.length > 20) state.activeFiles.shift();
    }
  }

  // At critical pressure, suggest using compressed tool calls
  const tier = classifyTier(state.estimatedPressure);
  if (tier === "critical" || tier === "overflow") {
    const importance = classifyToolImportance(toolName);
    if (importance === "file-read" && input.tool_input) {
      // Suggest limiting read size at high pressure
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

  // Update pressure
  if (input.transcript_path) {
    state.estimatedPressure = estimatePressureFromTranscript(input.transcript_path);
  }

  // Track large outputs
  if (output.length > 10_000) {
    state.largeOutputsThisTurn++;
  }

  // Index tool result in CassiCore (fire-and-forget)
  if (output.length > 0 && output.length < 50_000) {
    bridge.index(state.ccSessionId, [{
      role: "assistant",
      content: `[${toolName}] ${output.slice(0, 5000)}`,
    }]);
  }

  // Emit canonical tool:round-complete so Reverie's sliding tool-log,
  // loop detection, Reflex, and Aurora's tool-affect tracking all fire.
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

  // Check for pressure warning
  const warning = buildPressureWarning(state);
  if (warning) {
    return { additionalContext: warning };
  }

  // Post working state periodically
  const now = Date.now();
  if (now - state.lastWorkingStateAt > 15_000) {
    state.lastWorkingStateAt = now;
    postWorkingState(state);
  }

  return {};
}

async function handlePreCompact(input: HookInput): Promise<HookOutput> {
  const state = getSession(input.session_id);

  // Save structured checkpoint before compaction
  await saveCheckpoint(state, input.transcript_path);

  // Write emergency handoff
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

  // Archive to CassiCore
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
    } catch { /* transcript read is best-effort */ }
  }

  state.compactionCount++;

  // Notify CassiCore
  bridge.ingestEvents(state.ccSessionId, [{
    type: "compaction_start",
    sessionId: state.ccSessionId,
    compactionCount: state.compactionCount,
    turnCount: state.turnCount,
    timestamp: Date.now(),
  }]).catch(() => {});

  return {
    systemMessage: "CassiCore: checkpoint saved before compaction",
  };
}

async function handlePostCompact(input: HookInput): Promise<HookOutput> {
  const state = getSession(input.session_id);
  state.postCompaction = true;
  state.handoffWritten = false;

  // Build recovery context
  const recovery = await buildCognitiveContext(state, {
    includeRecovery: true,
    compact: false,
  });

  // Notify CassiCore
  bridge.ingestEvents(state.ccSessionId, [{
    type: "compaction_complete",
    sessionId: state.ccSessionId,
    compactionCount: state.compactionCount,
    timestamp: Date.now(),
  }]).catch(() => {});

  return recovery
    ? { additionalContext: recovery }
    : {};
}

async function handleStop(input: HookInput): Promise<HookOutput> {
  const state = getSession(input.session_id);

  // Update pressure final
  if (input.transcript_path) {
    state.estimatedPressure = estimatePressureFromTranscript(input.transcript_path);
  }

  // Post working state
  postWorkingState(state);

  // Ingest turn complete
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

  // Direct Reverie ping as a belt-and-suspenders backup — guarantees an
  // ambient curation pass even if the bus event is lost or filtered.
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

  return {};
}

async function handleSessionEnd(input: HookInput): Promise<HookOutput> {
  const state = getSession(input.session_id);

  // Final archive
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

  return {};
}

// ── Helpers ─────────────────────────────────────────────────────────────────

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

// ── HTTP Server ─────────────────────────────────────────────────────────────

const ROUTE_MAP: Record<string, (input: HookInput) => Promise<HookOutput>> = {
  SessionStart: handleSessionStart,
  UserPromptSubmit: handleUserPromptSubmit,
  PreToolUse: handlePreToolUse,
  PostToolUse: handlePostToolUse,
  PreCompact: handlePreCompact,
  PostCompact: handlePostCompact,
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
    console.error(`Hook ${eventName} error:`, err);
    // Return empty on error — don't block Claude
    res.writeHead(200, { "Content-Type": "application/json" });
    res.end("{}");
  }
});

server.listen(PORT, "127.0.0.1", () => {
  console.log(`CassiCore hook server listening on http://127.0.0.1:${PORT}`);
  bridge.available().then(up => {
    console.log(`CassiCore daemon: ${up ? "connected" : "unavailable (will retry)"}`);
  });
});

// Graceful shutdown
process.on("SIGINT", () => { server.close(); process.exit(0); });
process.on("SIGTERM", () => { server.close(); process.exit(0); });
