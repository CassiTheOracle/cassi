#!/usr/bin/env npx tsx
/**
 * CassiCore Multi-Provider API Proxy for Claude Code
 *
 * Sits between Claude Code and API providers, intercepting /v1/messages
 * requests to inject CassiCore intelligence, manage context, and dynamically
 * route to the correct provider based on the requested model.
 *
 * Architecture:
 *   Claude Code  ──ANTHROPIC_BASE_URL──>  This Proxy (port 7435)
 *                                           ├─ Resolve provider from model name
 *                                           ├─ Rewrite system prompt (inject cognitive signals)
 *                                           ├─ Manage context (collapse, summarize, budget)
 *                                           ├─ Track sessions and token usage
 *                                           └──>  Provider A (z.ai — GLM models)
 *                                             └──>  Provider B (Anthropic — Claude models)
 *                                                  └── Stream response back
 *
 * Provider routing:
 *   - Model names are matched against a routing table (glob patterns)
 *   - glm-* → z.ai, claude-* → Anthropic direct, * → z.ai (default)
 *   - Circuit breaker skips unhealthy providers
 *   - Credentials loaded from .env file or environment variables
 *
 * What this gives us over hooks alone:
 *   - Modify/remove context (hooks can only add)
 *   - Inject intelligence into the system prompt
 *   - Accurate token counting (not file-size estimates)
 *   - Full message array rewriting before it hits the model
 *   - Multi-provider routing without changing Claude Code settings
 *
 * Complementary to the hook server (port 7434):
 *   - Proxy modifies what the MODEL sees and WHERE the request goes
 *   - Hooks modify what CLAUDE CODE adds to the transcript
 *
 * Setup:
 *   1. Create .env file with provider credentials (see .env.example)
 *   2. Run: npx tsx src/proxy.ts
 *   3. The proxy auto-migrates ~/.claude/settings.json to point ANTHROPIC_BASE_URL here
 */

import fs from "node:fs";
import http from "node:http";
import https from "node:https";
import { URL } from "node:url";
import zlib from "node:zlib";
import * as bridge from "./bridge.js";
import { initFromEnv, recordSuccess, recordFailure, getHealthSummary } from "./provider-registry.js";
import { resolveRoute, resolveUpstreamUrl, getRoutingTableSummary, initRoutes, getRouteSource, type ResolvedRoute } from "./model-router.js";
import { syncSettings, extractCredentialsFromSettings } from "./settings-sync.js";
import { integrationLogger } from "./logger.js";


const logger = integrationLogger.child("proxy");

const PORT = parseInt(process.env.CASSICORE_PROXY_PORT ?? "7435", 10);

const MAX_INJECTION_CHARS = 12_000;
const INJECTION_COOLDOWN_MS = 2000;

interface ProxySessionState {
  sessionId: string;
  ccSessionId: string;
  requestCount: number;
  totalInputTokens: number;
  totalOutputTokens: number;
  lastInjectionAt: number;
  lastCognitiveContext: string;
  createdAt: number;
}

const sessions = new Map<string, ProxySessionState>();

function getProxySession(claudeSessionId: string): ProxySessionState {
  let s = sessions.get(claudeSessionId);
  if (!s) {
    const ccId = `cc:${claudeSessionId.slice(0, 12) || Date.now().toString(36)}`;
    s = {
      sessionId: claudeSessionId,
      ccSessionId: ccId,
      requestCount: 0,
      totalInputTokens: 0,
      totalOutputTokens: 0,
      lastInjectionAt: 0,
      lastCognitiveContext: "",
      createdAt: Date.now(),
    };
    sessions.set(claudeSessionId, s);
  }
  return s;
}

async function buildCognitiveInjection(state: ProxySessionState): Promise<string | null> {
  const now = Date.now();
  if (now - state.lastInjectionAt < INJECTION_COOLDOWN_MS && state.lastCognitiveContext) {
    return state.lastCognitiveContext;
  }

  const injections = await bridge.inject(state.ccSessionId);
  if (injections.length === 0) return null;

  let result = injections.join("\n\n");
  if (result.length > MAX_INJECTION_CHARS) {
    result = result.slice(0, MAX_INJECTION_CHARS - 20) + "\n[...truncated]";
  }

  state.lastInjectionAt = now;
  state.lastCognitiveContext = result;
  return result;
}

function stripSoulMd(system: string | unknown[]): string | unknown[] {
  if (typeof system === "string") {
    return system.replace(
      /# SOUL\.md — Who I Am[\s\S]*?(?=\n# [A-Z]|\n---\s*\n# |$)/,
      "",
    );
  }
  if (Array.isArray(system)) {
    return system.filter(
      (block: any) =>
        !(block.type === "text" && block.text?.includes("# SOUL.md — Who I Am")),
    );
  }
  return system;
}

function injectIntoSystemPrompt(
  body: Record<string, unknown>,
  content: string,
  tag = "cassicore-intelligence",
): void {
  const system = body.system;
  const injection = `<${tag}>\n${content}\n</${tag}>`;

  if (typeof system === "string") {
    body.system = `${system}\n\n${injection}`;
  } else if (Array.isArray(system)) {
    (system as any[]).push({
      type: "text",
      text: injection,
    });
  } else {
    body.system = injection;
  }
}

function renderReceiptForInjection(receipt: any): string | null {
  if (!receipt || typeof receipt !== "object") return null;
  const dropped = typeof receipt.dropped === "number" ? receipt.dropped : 0;
  const protectedSummary = receipt.protected && typeof receipt.protected === "object"
    ? receipt.protected
    : null;
  const protectedTotal = protectedSummary && typeof protectedSummary.total === "number"
    ? protectedSummary.total
    : 0;
  const distillation = receipt.distillation;
  const hasDistillationActivity = !!(distillation && typeof distillation === "object" && (
    (Array.isArray(distillation.completed) && distillation.completed.length > 0) ||
    (typeof distillation.pending === "number" && distillation.pending > 0)
  ));
  if (dropped <= 0 && protectedTotal <= 0 && !hasDistillationActivity) return null;
  const lines: string[] = [];
  if (dropped > 0 && typeof receipt.summary === "string" && receipt.summary.length > 0) {
    lines.push(receipt.summary);
  } else if (dropped <= 0) {
    lines.push("thalamus dropped 0 messages this turn");
  }

  // Include tool-chain metadata so the model knows what work was removed
  const tcs = receipt.toolChainSummary;
  if (tcs && typeof tcs === "object") {
    const parts: string[] = [];
    if (typeof tcs.toolPairCount === "number" && tcs.toolPairCount > 0) {
      parts.push(`${tcs.toolPairCount} tool call${tcs.toolPairCount > 1 ? "s" : ""}`);
    }
    if (Array.isArray(tcs.filesRead) && tcs.filesRead.length > 0) {
      parts.push(`read: ${tcs.filesRead.join(", ")}`);
    }
    if (Array.isArray(tcs.filesWritten) && tcs.filesWritten.length > 0) {
      parts.push(`wrote: ${tcs.filesWritten.join(", ")}`);
    }
    if (Array.isArray(tcs.errors) && tcs.errors.length > 0) {
      parts.push(`errors: ${tcs.errors.join("; ")}`);
    }
    if (parts.length > 0) {
      lines.push(`work dropped: ${parts.join(" · ")}`);
    }
  }

  // Topic clusters — show what subject areas were removed
  const topics = receipt.topics;
  if (Array.isArray(topics) && topics.length > 0) {
    lines.push("");
    lines.push("topics dropped:");
    for (const t of topics) lines.push(`  - ${t.topic} (${t.count} msg${t.count > 1 ? "s" : ""})`);
  }

  // Closest miss — the highest-scoring message that still got dropped
  const cm = receipt.closestMiss;
  if (cm && typeof cm === "object") {
    lines.push("");
    const lum = typeof cm.luminance === "number" ? cm.luminance.toFixed(3) : "?";
    const thr = typeof cm.threshold === "number" ? cm.threshold.toFixed(3) : "?";
    const gap = (typeof cm.luminance === "number" && typeof cm.threshold === "number")
      ? (cm.threshold - cm.luminance).toFixed(3) : "?";
    const axes = cm.axes && typeof cm.axes === "object"
      ? Object.entries(cm.axes).filter(([, v]) => typeof v === "number" && v > 0).map(([k, v]) => `${k}=${(v as number).toFixed(2)}`).join(", ")
      : "";
    lines.push(`closest miss: "${cm.snippet}" (luminance ${lum}, needed ${thr}, gap ${gap}${axes ? `, ${axes}` : ""})`);
  }

  // Budget utilization — show how tight the curation was
  const budget = receipt.budget;
  if (budget && typeof budget === "object" && typeof budget.utilization === "number") {
    lines.push(`budget: ${Math.round(budget.used / 1000)}k/${Math.round(budget.budget / 1000)}k chars (${Math.round(budget.utilization * 100)}% used)`);
  }

  // Distillation activity — closes the design gap from cassi-context-awareness
  // §"Async tool-result distillation". Pending = queued for background LLM
  // compression; completed = finished since last receipt.
  const distillation = receipt.distillation;
  if (distillation && typeof distillation === "object") {
    const pending = typeof distillation.pending === "number" ? distillation.pending : 0;
    const completed = Array.isArray(distillation.completed) ? distillation.completed : [];
    if (completed.length > 0 || pending > 0) {
      const parts: string[] = [];
      if (completed.length > 0) {
        const freed = typeof distillation.charsFreed === "number" ? distillation.charsFreed : 0;
        const fmt = (n: number) => n >= 1024 ? `${(n / 1024).toFixed(1)}KB` : `${n}ch`;
        const samples = completed.slice(0, 3).map((c: any) => `#${c.msgIndex} ${fmt(c.originalChars)}→${fmt(c.summaryChars)}`).join(", ");
        const more = completed.length > 3 ? ` +${completed.length - 3} more` : "";
        parts.push(`${completed.length} completed (-${fmt(freed)} freed): ${samples}${more}`);
      }
      if (pending > 0) parts.push(`${pending} queued`);
      lines.push(`distillation: ${parts.join(" · ")}`);
    }
  }

  if (Array.isArray(receipt.anomalies) && receipt.anomalies.length > 0) {
    lines.push("");
    lines.push("anomalies:");
    for (const a of receipt.anomalies) lines.push(`  - ${a}`);
  }
  if (protectedSummary && typeof protectedSummary.summary === "string" && protectedSummary.summary.length > 0) {
    lines.push("");
    lines.push(`protected: ${protectedSummary.summary}`);
  }
  lines.push("");
  lines.push(
    'to see full context map or inspect drops: cassi_context({action: "map"}), {action: "audit"}, {action: "recall", n: 5}',
  );
  return lines.join("\n");
}

function extractClaudeSessionId(req: http.IncomingMessage): string {
  const header = req.headers["x-claude-code-session-id"];
  if (typeof header === "string" && header.length > 0) return header;

  const ua = req.headers["user-agent"] ?? "";
  const match = /session[_-]?id[=:]?\s*([a-zA-Z0-9_-]+)/i.exec(ua);
  if (match) return match[1];

  return "default";
}

function trackTokenUsage(state: ProxySessionState, usage: any): void {
  if (!usage) return;
  if (typeof usage.input_tokens === "number") state.totalInputTokens += usage.input_tokens;
  if (typeof usage.output_tokens === "number") state.totalOutputTokens += usage.output_tokens;
}

function postSessionMetrics(state: ProxySessionState): void {
  bridge.kvSet(`proxy-state:${state.ccSessionId}`, {
    sessionId: state.ccSessionId,
    claudeSessionId: state.sessionId,
    requestCount: state.requestCount,
    totalInputTokens: state.totalInputTokens,
    totalOutputTokens: state.totalOutputTokens,
    timestamp: Date.now(),
  });
}

function buildRequestDiagnostics(
  req: http.IncomingMessage,
  state: ProxySessionState | undefined,
  route: ResolvedRoute | null,
  requestPath: string,
  requestedModel: string,
  bodyToSend: Buffer,
): Record<string, unknown> {
  return {
    method: req.method,
    path: requestPath,
    requestedModel,
    routedProvider: route?.provider.id,
    routedBaseUrl: route?.provider.baseUrl,
    routedModel: route?.model,
    isFallbackRoute: route?.isFallback ?? false,
    claudeSessionId: state?.sessionId,
    ccSessionId: state?.ccSessionId,
    requestCount: state?.requestCount,
    totalInputTokensSoFar: state?.totalInputTokens,
    totalOutputTokensSoFar: state?.totalOutputTokens,
    bodyBytes: bodyToSend.length,
    hasClientAuthorizationHeader: typeof req.headers['authorization'] !== 'undefined',
    hasClientApiKeyHeader: typeof req.headers['x-api-key'] !== 'undefined',
  };
}

/**
 * Sanitize tool pairs: deduplicate tool_use IDs, strip orphan tool_uses,
 * convert orphan tool_results to text, and merge consecutive same-role
 * messages (except assistant — preserves thinking signatures).
 */
function sanitizeToolPairs(messages: any[]): any[] {
  if (!Array.isArray(messages) || messages.length === 0) return messages

  // Pre-scan: find all tool_use and tool_result IDs across the entire array.
  const allToolUseIds = new Set<string>()
  const allToolResultIds = new Set<string>()
  for (const msg of messages) {
    if (!Array.isArray(msg?.content)) continue
    for (const block of msg.content) {
      if (block?.type === 'tool_use' && typeof block.id === 'string') {
        allToolUseIds.add(block.id)
      }
      if (block?.type === 'tool_result' && typeof block.tool_use_id === 'string') {
        allToolResultIds.add(block.tool_use_id)
      }
    }
  }

  // Deduplicate tool_use IDs (first occurrence wins).
  const seenToolUseIds = new Set<string>()
  const deduped: any[] = []
  for (const msg of messages) {
    if (!msg || !Array.isArray(msg.content)) {
      deduped.push(msg)
      continue
    }
    let changed = false
    const kept: any[] = []
    for (const block of msg.content) {
      if (block?.type === 'tool_use' && typeof block.id === 'string') {
        if (seenToolUseIds.has(block.id)) {
          changed = true
          continue
        }
        seenToolUseIds.add(block.id)
      }
      kept.push(block)
    }
    if (!changed) {
      deduped.push(msg)
    } else if (kept.length > 0) {
      deduped.push({ ...msg, content: kept })
    }
  }
  messages = deduped

  const toolUseIds = (msg: any): string[] => {
    if (!msg || !Array.isArray(msg.content)) return []
    return msg.content
      .filter((b: any) => b?.type === 'tool_use' && typeof b.id === 'string')
      .map((b: any) => b.id)
  }
  const toolResultIds = (msg: any): Set<string> => {
    const ids = new Set<string>()
    if (!msg || !Array.isArray(msg.content)) return ids
    for (const b of msg.content) {
      if (b?.type === 'tool_result' && typeof b.tool_use_id === 'string') {
        ids.add(b.tool_use_id)
      }
    }
    return ids
  }
  const stripToolUse = (msg: any): any => {
    if (!msg || !Array.isArray(msg.content)) return msg
    const kept = msg.content.filter((b: any) => b?.type !== 'tool_use')
    if (kept.length === 0) return null
    return { ...msg, content: kept }
  }
  const stripToolResult = (msg: any): any => {
    if (!msg || !Array.isArray(msg.content)) return msg
    const kept = msg.content.filter((b: any) => b?.type !== 'tool_result')
    if (kept.length === 0) return null
    return { ...msg, content: kept }
  }
  const orphanToolResultToText = (msg: any, orphanIds: string[]): any => {
    if (!msg || !Array.isArray(msg.content)) return msg
    return {
      ...msg,
      content: msg.content.map((b: any) => {
        if (b?.type === 'tool_result' && orphanIds.includes(b.tool_use_id)) {
          const text = typeof b.content === 'string' ? b.content : JSON.stringify(b.content)
          return {
            type: 'text',
            text: `[Orphaned tool result for ${b.tool_use_id}]:\n${text}`,
          }
        }
        return b
      }),
    }
  }

  const out: any[] = []
  const strippedToolUseIds = new Set<string>()
  for (let i = 0; i < messages.length; i++) {
    let msg = messages[i]

    // Handle tool_use: if no matching tool_result ANYWHERE in the array,
    // the tool_use is truly orphaned and should be stripped.
    const uses = toolUseIds(msg)
    if (uses.length > 0) {
      const orphans = uses.filter((id) => !allToolResultIds.has(id))
      if (orphans.length === uses.length) {
        const stripped = stripToolUse(msg)
        for (const id of uses) strippedToolUseIds.add(id)
        if (!stripped) continue
        msg = stripped
      } else if (orphans.length > 0) {
        for (const id of orphans) strippedToolUseIds.add(id)
        msg = {
          ...msg,
          content: msg.content.filter(
            (b: any) => b?.type !== 'tool_use' || !orphans.includes(b.id),
          ),
        }
      }
    }

    // Handle tool_result: if no matching tool_use ANYWHERE in the array,
    // the tool_result is truly orphaned and should be converted to text.
    const results = toolResultIds(msg)
    if (results.size > 0) {
      const orphanResults = [...results].filter((id) => !allToolUseIds.has(id) || strippedToolUseIds.has(id))
      if (orphanResults.length === results.size) {
        const stripped = stripToolResult(msg)
        if (!stripped) {
          msg = orphanToolResultToText(msg, orphanResults)
        } else {
          msg = stripped
        }
      } else if (orphanResults.length > 0) {
        msg = {
          ...msg,
          content: msg.content.map((b: any) => {
            if (b?.type === 'tool_result' && orphanResults.includes(b.tool_use_id)) {
              const text = typeof b.content === 'string' ? b.content : JSON.stringify(b.content)
              return {
                type: 'text',
                text: `[Orphaned tool result for ${b.tool_use_id}]:\n${text}`,
              }
            }
            return b
          }),
        }
      }
    }

    // Never merge assistant messages — their thinking signatures are bound to
    // block structure, and concatenating content arrays invalidates signatures
    // (Anthropic 400: "Invalid signature in thinking block").
    if (out.length > 0 && out[out.length - 1].role === msg.role && msg.role !== 'assistant') {
      const prev = out[out.length - 1]
      const bothStrings = typeof prev.content === 'string' && typeof msg.content === 'string'
      if (bothStrings) {
        out[out.length - 1] = { ...prev, content: `${prev.content}\n\n${msg.content}` }
      } else {
        const prevContent = Array.isArray(prev.content) ? prev.content : [{ type: 'text', text: String(prev.content ?? '') }]
        const curContent = Array.isArray(msg.content) ? msg.content : [{ type: 'text', text: String(msg.content ?? '') }]
        out[out.length - 1] = { ...prev, content: [...prevContent, ...curContent] }
      }
      continue
    }
    out.push(msg)
  }
  return out
}

function stripThinkingBlocks(messages: any[]): void {
  for (const msg of messages) {
    if (!msg?.content || !Array.isArray(msg.content)) continue;
    msg.content = msg.content.map((block: any) => {
      if (block?.type === "thinking") {
        return { type: "text", text: block.thinking ?? "" };
      }
      if (block?.type === "redacted_thinking") {
        return { type: "text", text: "[redacted thinking]" };
      }
      return block;
    }).filter(Boolean);
  }
}

/**
 * Remove thinking blocks with empty or missing signatures, OR empty thinking text.
 * Anthropic requires:
 * - thinking blocks must have non-empty signatures
 * - thinking blocks must have non-empty thinking text
 * If either is missing/empty, convert to text block.
 */
function sanitizeThinkingSignatures(messages: any[]): void {
  for (const msg of messages) {
    if (!msg?.content || !Array.isArray(msg.content)) continue;
    msg.content = msg.content.filter((block: any) => {
      if (block?.type === "thinking") {
        const hasEmptySignature = !block.signature || block.signature === "";
        const hasEmptyThinking = !block.thinking || block.thinking === "";
        if (hasEmptySignature || hasEmptyThinking) {
          logger.warn("Dropping thinking block with empty signature or thinking text", { msgRole: msg.role, hasEmptySignature, hasEmptyThinking });
          return false;
        }
      }
      return true;
    });
  }
}

/**
 * Anthropic strictly requires that every tool_use in message N must have its
 * corresponding tool_result in message N+1. If a tool_result is missing or
 * appears later (e.g. due to curation dropping messages), strip the orphaned
 * tool_use to prevent 400 errors.
 */
function enforceToolPairAdjacency(messages: any[]): void {
  logger.info("enforceToolPairAdjacency running", { messageCount: messages.length });
  for (let i = 0; i < messages.length - 1; i++) {
    const msg = messages[i];
    if (msg?.role !== 'assistant' || !Array.isArray(msg.content)) continue;

    const toolUses = msg.content.filter((b: any) => b?.type === 'tool_use' && typeof b.id === 'string');
    if (toolUses.length === 0) continue;

    const nextMsg = messages[i + 1];
    const nextHasToolResults = nextMsg?.role === 'user' && Array.isArray(nextMsg?.content);
    const nextResultIds = new Set<string>();
    if (nextHasToolResults) {
      for (const block of nextMsg.content) {
        if (block?.type === 'tool_result' && typeof block.tool_use_id === 'string') {
          nextResultIds.add(block.tool_use_id);
        }
      }
    }

    const orphanedToolUses = toolUses.filter((b: any) => !nextResultIds.has(b.id));
    if (orphanedToolUses.length > 0) {
      logger.warn("Stripping tool_use blocks without immediate tool_result", {
        sessionId: (messages as any)._sessionId,
        msgIndex: i,
        orphanedIds: orphanedToolUses.map((b: any) => b.id),
        nextMsgRole: nextMsg?.role,
        nextResultIds: [...nextResultIds],
      });
      msg.content = msg.content.filter((b: any) => b?.type !== 'tool_use' || nextResultIds.has(b.id));
    }
  }
}

/**
 * Reorder blocks to comply with Anthropic's strict block ordering:
 * - Assistant messages: thinking → tool_use → text → everything else
 * - User messages with tool_result: tool_result must come BEFORE text blocks
 *   (Anthropic requires tool_result blocks to be first in the message)
 */
function reorderAnthropicBlocks(messages: any[]): void {
  for (const msg of messages) {
    if (!Array.isArray(msg.content)) continue;
    
    if (msg.role === "assistant") {
      // Assistant: thinking → tool_use → text → other
      const groups = new Map<string, any[]>();
      for (const block of msg.content) {
        const type = block?.type ?? "other";
        let key: string;
        if (type === "thinking" || type === "redacted_thinking") key = "thinking";
        else if (type === "tool_use") key = "tool_use";
        else if (type === "text") key = "text";
        else key = "other";
        if (!groups.has(key)) groups.set(key, []);
        groups.get(key)!.push(block);
      }
      msg.content = [
        ...(groups.get("thinking") ?? []),
        ...(groups.get("tool_use") ?? []),
        ...(groups.get("text") ?? []),
        ...(groups.get("other") ?? []),
      ];
    } else if (msg.role === "user") {
      // User: if message has tool_result blocks, they must come first
      const hasToolResult = msg.content.some((b: any) => b?.type === "tool_result");
      if (hasToolResult) {
        const toolResults: any[] = [];
        const others: any[] = [];
        for (const block of msg.content) {
          if (block?.type === "tool_result") {
            toolResults.push(block);
          } else {
            others.push(block);
          }
        }
        msg.content = [...toolResults, ...others];
      }
    }
  }
}

async function proxyRequest(
  req: http.IncomingMessage,
  res: http.ServerResponse,
  rawBody: Buffer,
): Promise<void> {
  const requestPath = req.url ?? "/";

  const isMessages = /^\/v1\/messages/.test(requestPath);
  const isCountTokens = requestPath.endsWith("/count_tokens");

  let bodyToSend = rawBody;
  let state: ProxySessionState | undefined;
  let isStreaming = false;
  let route: ResolvedRoute | null = null;
  let requestedModel = "";

  if (isMessages && req.method === "POST") {
    try {
      const body = JSON.parse(rawBody.toString("utf-8"));
      isStreaming = body.stream === true;
      requestedModel = body.model ?? "";

      route = resolveRoute(requestedModel);
      if (route) {
        logger.debug(
          `Routing model="${requestedModel}" → ${route.provider.id} (${route.provider.baseUrl})` +
          (route.isFallback ? " [fallback]" : "") +
          (route.model !== route.originalModel ? ` aliased="${route.model}"` : ""),
        );
        // Rewrite model name if aliased
        if (route.model !== route.originalModel) {
          body.model = route.model;
        }
      } else {
        logger.error(`No route for model "${requestedModel}" — forwarding to default upstream`);
      }

      const claudeSessionId = extractClaudeSessionId(req);
      state = getProxySession(claudeSessionId);
      if (!isCountTokens) {
        state.requestCount++;
      }

      // Apply the same context expansion to both /messages and /messages/count_tokens
      // so Claude Code's usage meter reflects the real payload sent upstream.
      // Count-tokens requests must NOT increment requestCount or pollute token metrics.
      const cognitive = await buildCognitiveInjection(state);
      if (cognitive) {
        if (body.system) {
          body.system = stripSoulMd(body.system as string | unknown[]);
        }
        injectIntoSystemPrompt(body, cognitive);
      }

      if (Array.isArray(body.messages)) {
        // DEBUG: Log thinking signatures from Claude Code before curation
        const originalThinkingSigs = body.messages.map((m: any, i: number) => {
          if (m.role === 'assistant' && Array.isArray(m.content)) {
            const thinkingBlocks = m.content.filter((b: any) => b.type === 'thinking');
            return { msgIndex: i, sigLens: thinkingBlocks.map((b: any) => b.signature?.length ?? 0) };
          }
          return null;
        }).filter(Boolean);
        if (originalThinkingSigs.length > 0) {
          logger.info("Original thinking signatures from Claude Code", { sessionId: state.ccSessionId, signatures: originalThinkingSigs });
        }
        
        let nextMessages = body.messages;
        try {
          const curated = await bridge.curate(state.ccSessionId, body.messages);
          if (curated?.messages) nextMessages = curated.messages;
          const receiptText = renderReceiptForInjection(curated?.meta?.receipt);
          if (receiptText) {
            injectIntoSystemPrompt(body, receiptText, "thalamus-receipt");
          }
          if (curated?.meta?.repetitionWarning) {
            injectIntoSystemPrompt(body, curated.meta.repetitionWarning, "thalamus-loop-warning");
          }
          if (curated?.meta?.contextMap) {
            injectIntoSystemPrompt(body, curated.meta.contextMap, "thalamus-map");
          }
        } catch (err) {
          logger.error("curate failed", { error: String(err) });
        }
        
        // DEBUG: Log message structure before sanitization
        const debugInfo = nextMessages.map((m: any) => ({
          role: m.role,
          blocks: Array.isArray(m.content) ? m.content.map((b: any) => b?.type || 'string') : ['string'],
          toolIds: Array.isArray(m.content) ? m.content.filter((b: any) => b?.type === 'tool_use').map((b: any) => b.id) : [],
          resultIds: Array.isArray(m.content) ? m.content.filter((b: any) => b?.type === 'tool_result').map((b: any) => b.tool_use_id) : [],
        }));
        logger.debug("proxy messages before sanitize", { sessionId: state.ccSessionId, messages: debugInfo });
        
        body.messages = sanitizeToolPairs(nextMessages);
        
        // DEBUG: Log message structure after sanitization
        const afterInfo = body.messages.map((m: any) => ({
          role: m.role,
          blocks: Array.isArray(m.content) ? m.content.map((b: any) => b?.type || 'string') : ['string'],
          toolIds: Array.isArray(m.content) ? m.content.filter((b: any) => b?.type === 'tool_use').map((b: any) => b.id) : [],
          resultIds: Array.isArray(m.content) ? m.content.filter((b: any) => b?.type === 'tool_result').map((b: any) => b.tool_use_id) : [],
        }));
        logger.debug("proxy messages after sanitize", { sessionId: state.ccSessionId, messages: afterInfo });
      }

      if (route?.provider.id === "anthropic" && Array.isArray(body.messages)) {
        // Anthropic requires valid thinking signatures. If Claude Code sends
        // empty signatures (bug), remove the thinking blocks to avoid 400 errors.
        sanitizeThinkingSignatures(body.messages);
        // Anthropic requires blocks in specific order: thinking → tool_use → text
        reorderAnthropicBlocks(body.messages);
        // Anthropic requires every tool_use to have its tool_result in the
        // immediately following message. Strip any that don't (can happen when
        // curation drops tool_result messages or parallel tool calls race).
        enforceToolPairAdjacency(body.messages);
        // Strip unsupported ttl field from cache_control — Anthropic only
        // supports { type: "ephemeral" }, and extra fields may cause the
        // validator to reject tool_result blocks (leading to "tool_use without
        // tool_result" errors).
        for (const msg of body.messages) {
          if (Array.isArray(msg.content)) {
            for (const block of msg.content) {
              if (block?.cache_control && typeof block.cache_control === 'object') {
                const { type } = block.cache_control;
                block.cache_control = { type };
              }
            }
          }
        }
      } else if (Array.isArray(body.messages)) {
        // Non-Anthropic providers don't support thinking blocks at all
        stripThinkingBlocks(body.messages);
      }

      // DEBUG: Log request headers for Anthropic
      if (route?.provider.id === "anthropic") {
        const relevantHeaders: Record<string, unknown> = {};
        for (const [key, value] of Object.entries(headers)) {
          if (key.startsWith("anthropic") || key === "x-api-key" || key === "authorization") {
            relevantHeaders[key] = value;
          }
        }
        logger.info("Anthropic request headers", { sessionId: state.ccSessionId, headers: relevantHeaders });
      }

      // DEBUG: Log exact message structure being sent to API
      const apiDebugInfo = body.messages.map((m: any, i: number) => ({
        index: i,
        role: m.role,
        blocks: Array.isArray(m.content) ? m.content.map((b: any) => ({ type: b?.type, id: b?.id, tool_use_id: b?.tool_use_id })) : [{ type: 'string' }],
      }));
      logger.info("API request messages", { sessionId: state.ccSessionId, messageCount: body.messages.length, messages: apiDebugInfo });
      
      // DEBUG: Log full JSON of first 5 messages for detailed inspection
      const firstFive = body.messages.slice(0, 5).map((m: any, i: number) => ({
        index: i,
        role: m.role,
        content: m.content,
      }));
      logger.info("API request first 5 messages FULL", { sessionId: state.ccSessionId, messages: firstFive });
      
      bodyToSend = Buffer.from(JSON.stringify(body), "utf-8");
      
      // DEBUG: Dump full request body for Anthropic to file
      if (route?.provider.id === "anthropic") {
        const dumpPath = `/tmp/anthropic-request-${state.requestCount}-${Date.now()}.json`;
        try {
          fs.writeFileSync(dumpPath, JSON.stringify(body, null, 2));
          logger.info("Dumped Anthropic request body", { dumpPath, bodyBytes: bodyToSend.length, requestCount: state.requestCount });
        } catch (e) {
          logger.error("Failed to dump request body", { error: String(e) });
        }
      }
    } catch {
      // Parse failure — forward unchanged
    }
  }

  let targetUrl: URL;
  let providerHeaders: Record<string, string> = {};

  if (route) {
    // Dynamic routing: use resolved provider
    targetUrl = new URL(resolveUpstreamUrl(route.provider, requestPath));
    // Only override auth if the provider has its own key.
    // If the provider has no key (empty string), keep whatever the client sent
    // (Claude Code sends its own OAuth token in x-api-key).
    if (route.provider.apiKey) {
      providerHeaders["x-api-key"] = route.provider.apiKey;
    }
    if (route.provider.anthropicVersion) {
      providerHeaders["anthropic-version"] = route.provider.anthropicVersion;
    }
  } else {
    // Fallback: use the original request path with the old UPSTREAM_BASE logic
    const fallbackBase = process.env.CASSICORE_PROXY_UPSTREAM ?? "https://api.anthropic.com";
    targetUrl = new URL(requestPath, fallbackBase);
  }

  const headers: Record<string, string | string[]> = {};
  for (const [key, value] of Object.entries(req.headers)) {
    if (key === "host" || key === "connection" || key === "content-length") continue;
    // Only strip incoming auth if the provider has its own key to replace it with.
    // Claude Code may send both x-api-key and Authorization bearer auth; z.ai will
    // reject the request with 401 if an expired/incorrect bearer token is forwarded
    // alongside the correct provider-managed x-api-key.
    if ((key === "x-api-key" || key === "authorization") && route?.provider.apiKey) continue;
    if (key === "anthropic-version" && route?.provider.anthropicVersion) continue;
    if (value !== undefined) headers[key] = value as string | string[];
  }
  headers["content-length"] = String(bodyToSend.length);
  headers["host"] = targetUrl.host;

  // Apply provider-specific headers (API key, version)
  Object.assign(headers, providerHeaders);

  const isHttps = targetUrl.protocol === "https:";
  const transport = isHttps ? https : http;

  const proxyReq = transport.request(
    {
      hostname: targetUrl.hostname,
      port: targetUrl.port || (isHttps ? 443 : 80),
      path: targetUrl.pathname + targetUrl.search,
      method: req.method,
      headers,
    },
    (proxyRes) => {
      const statusCode = proxyRes.statusCode ?? 502;
      const requestDiagnostics = buildRequestDiagnostics(
        req,
        state,
        route,
        requestPath,
        requestedModel,
        bodyToSend,
      );

      // Track provider health
      if (route) {
        if (statusCode >= 500 || statusCode === 429) {
          recordFailure(route.provider.id);
        } else if (statusCode < 400) {
          recordSuccess(route.provider.id);
        }
      }

      if (statusCode >= 400) {
        logger.warn("Upstream returned error status", {
          ...requestDiagnostics,
          statusCode,
          responseHeaders: proxyRes.headers,
          isStreaming,
        });
      }

      res.writeHead(statusCode, proxyRes.headers);

      if (state && isStreaming && !isCountTokens) {
        let sseBuffer = "";
        proxyRes.on("data", (chunk) => {
          res.write(chunk);
          sseBuffer += (chunk as Buffer).toString("utf-8");
          const lines = sseBuffer.split("\n");
          sseBuffer = lines.pop() ?? "";
          for (const line of lines) {
            if (!line.startsWith("data: ")) continue;
            const payload = line.slice(6).trim();
            if (payload === "[DONE]") continue;
            try {
              const evt = JSON.parse(payload);
              if (evt.type === "message_delta" && evt.usage) {
                trackTokenUsage(state!, evt.usage);
              }
              if (evt.type === "message_start" && evt.message?.usage) {
                trackTokenUsage(state!, evt.message.usage);
              }
            } catch { /* partial JSON or non-JSON line */ }
          }
        });
        // Buffer first chunks to capture error details on 400+ status
        const errorBuffer: Buffer[] = [];
        let errorBufferSize = 0;
        const MAX_ERROR_BUFFER = 4096;
        proxyRes.on("data", (chunk: Buffer) => {
          if (statusCode >= 400 && errorBufferSize < MAX_ERROR_BUFFER) {
            errorBuffer.push(chunk);
            errorBufferSize += chunk.length;
          }
        });
        proxyRes.on("end", () => {
          if (statusCode >= 400 && errorBuffer.length > 0) {
            const raw = Buffer.concat(errorBuffer);
            let errorText: string;
            try {
              const decompressed = zlib.gunzipSync(raw);
              errorText = decompressed.toString("utf-8").slice(0, MAX_ERROR_BUFFER);
            } catch {
              errorText = raw.toString("utf-8").slice(0, MAX_ERROR_BUFFER);
            }
            logger.error("Upstream streaming error payload", {
              ...requestDiagnostics,
              statusCode,
              errorPreview: errorText,
            });
          }
          postSessionMetrics(state!);
          res.end();
        });
      } else if (state && !isStreaming && !isCountTokens) {
        const chunks: Buffer[] = [];
        proxyRes.on("data", (chunk) => {
          chunks.push(chunk as Buffer);
          res.write(chunk);
        });
        proxyRes.on("end", () => {
          try {
            const raw = Buffer.concat(chunks);
            let text: string;
            try {
              const decompressed = zlib.gunzipSync(raw);
              text = decompressed.toString("utf-8");
            } catch {
              text = raw.toString("utf-8");
            }
            const data = JSON.parse(text);
            if (statusCode >= 400) {
              logger.error("Upstream error payload", {
                ...requestDiagnostics,
                statusCode,
                upstreamError: data?.error ?? data,
                usage: data?.usage,
              });
            }
            trackTokenUsage(state!, data.usage);
            postSessionMetrics(state!);
          } catch { /* non-JSON response */ }
          res.end();
        });
      } else {
        proxyRes.pipe(res);
      }
    },
  );

  proxyReq.on("error", (err) => {
    // Record failure for circuit breaker
    if (route) {
      recordFailure(route.provider.id);
    }
    logger.error(`Proxy upstream error: ${String(err)}`);
    if (!res.headersSent) {
      res.writeHead(502, { "Content-Type": "application/json" });
      res.end(JSON.stringify({ error: { type: "proxy_error", message: String(err) } }));
    }
  });

  proxyReq.write(bodyToSend);
  proxyReq.end();
}

const server = http.createServer(async (req, res) => {
  if (req.url === "/health" && req.method === "GET") {
    const cassiUp = await bridge.available();
    const health = getHealthSummary();
    res.writeHead(200, { "Content-Type": "application/json" });
    res.end(JSON.stringify({
      status: "ok",
      proxy: "cassicore-multi-provider-proxy",
      cassicore: cassiUp,
      providers: Object.fromEntries(
        Object.entries(health).map(([id, h]) => [id, { available: h.available, circuitOpen: h.circuitOpen }]),
      ),
      sessions: sessions.size,
    }));
    return;
  }

  if (req.url === "/providers" && req.method === "GET") {
    const health = getHealthSummary();
    res.writeHead(200, { "Content-Type": "application/json" });
    res.end(JSON.stringify({ providers: health }, null, 2));
    return;
  }

  if (req.url === "/providers/routes" && req.method === "GET") {
    const routes = getRoutingTableSummary();
    res.writeHead(200, { "Content-Type": "application/json" });
    res.end(JSON.stringify({ routes }, null, 2));
    return;
  }

  if (req.url === "/stats" && req.method === "GET") {
    const stats = [...sessions.values()].map(s => ({
      sessionId: s.sessionId.slice(0, 12),
      requests: s.requestCount,
      inputTokens: s.totalInputTokens,
      outputTokens: s.totalOutputTokens,
      age: Math.round((Date.now() - s.createdAt) / 1000),
    }));
    res.writeHead(200, { "Content-Type": "application/json" });
    res.end(JSON.stringify({ sessions: stats }));
    return;
  }

  const chunks: Buffer[] = [];
  for await (const chunk of req) chunks.push(chunk as Buffer);
  const rawBody = Buffer.concat(chunks);

  await proxyRequest(req, res, rawBody);
});

// Entry-point guard — import as a module (for tests) without starting the server.
const isMain = (() => {
  const arg = process.argv[1];
  if (!arg) return false;
  const url = new URL(import.meta.url);
  return url.pathname === arg || url.pathname.endsWith("/" + arg.split("/").pop());
})();

async function boot(): Promise<void> {
  // Load provider credentials from .env file if present
  try {
    const dotenv = await import("dotenv");
    dotenv.config({ path: new URL("../.env", import.meta.url).pathname });
  } catch {
    // dotenv not installed — rely on environment variables directly
  }

  // Seed credentials from existing settings.json on first run
  const creds = extractCredentialsFromSettings();
  if (creds.zAiApiKey && !process.env.Z_AI_API_KEY && !process.env.ANTHROPIC_AUTH_TOKEN) {
    process.env.ANTHROPIC_AUTH_TOKEN = creds.zAiApiKey;
  }
  if (creds.zAiBaseUrl && !process.env.Z_AI_BASE_URL) {
    process.env.Z_AI_BASE_URL = creds.zAiBaseUrl;
  }

  // Initialize provider registry from environment
  initFromEnv();

  // Initialize routing table (daemon → config file → defaults)
  await initRoutes();

  // Auto-migrate ~/.claude/settings.json
  syncSettings();

  server.listen(PORT, "127.0.0.1", () => {
    const routes = getRoutingTableSummary();
    const providers = getHealthSummary();
    logger.info(`CassiCore multi-provider proxy listening on http://127.0.0.1:${PORT}`);
    logger.info(`Routing table:`);
    for (const r of routes) {
      logger.info(`  ${r.pattern.padEnd(20)} → ${r.providerId}${r.modelAlias ? ` (alias: ${r.modelAlias})` : ""} [${r.providerAvailable ? "up" : "down"}]`);
    }
    logger.info(`Provider auth:`);
    for (const [id, p] of Object.entries(providers)) {
      logger.info(`  ${id.padEnd(20)} key=${p.hasApiKey ? p.apiKeyPreview : 'MISSING'} via ${p.apiKeyHeader}`);
    }
    bridge.available().then(up => {
      logger.info(`CassiCore daemon: ${up ? "connected" : "unavailable (will retry)"}`);
    });
  });

  setInterval(() => {
    const cutoff = Date.now() - 4 * 60 * 60_000;
    for (const [id, state] of sessions) {
      if (state.createdAt < cutoff && state.requestCount === 0) sessions.delete(id);
    }
  }, 30 * 60_000);

  process.on("SIGINT", () => { server.close(); process.exit(0); });
  process.on("SIGTERM", () => { server.close(); process.exit(0); });
}

if (isMain) {
  boot().catch(err => {
    logger.error("Proxy boot failed", { error: String(err) });
    process.exit(1);
  });
}
