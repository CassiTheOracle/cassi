#!/usr/bin/env npx tsx
/**
 * CassiCore Anthropic API Proxy for Claude Code
 *
 * Sits between Claude Code and the Anthropic API, intercepting /v1/messages
 * requests to inject CassiCore intelligence and manage context.
 *
 * Architecture:
 *   Claude Code  ──ANTHROPIC_BASE_URL──>  This Proxy (port 7435)
 *                                           ├─ Rewrite system prompt (inject cognitive signals)
 *                                           ├─ Manage context (collapse, summarize, budget)
 *                                           ├─ Track sessions and token usage
 *                                           └──>  Real Anthropic API
 *                                                  └── Stream response back
 *
 * What this gives us over hooks alone:
 *   - Modify/remove context (hooks can only add)
 *   - Inject intelligence into the system prompt
 *   - Accurate token counting (not file-size estimates)
 *   - Full message array rewriting before it hits the model
 *
 * Complementary to the hook server (port 7434):
 *   - Proxy modifies what the MODEL sees
 *   - Hooks modify what CLAUDE CODE adds to the transcript
 *
 * Setup:
 *   export ANTHROPIC_BASE_URL=http://localhost:7435
 *   export CASSICORE_PROXY_ANTHROPIC_KEY=sk-ant-...  (or reads from Claude Code's key)
 */

import http from "node:http";
import https from "node:https";
import { URL } from "node:url";
import * as bridge from "./bridge.js";

const PORT = parseInt(process.env.CASSICORE_PROXY_PORT ?? "7435", 10);
const UPSTREAM_BASE = process.env.CASSICORE_PROXY_UPSTREAM ?? "https://api.anthropic.com";

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
  cognitiveContext: string,
): void {
  const system = body.system;
  const injection = `<cassicore-intelligence>\n${cognitiveContext}\n</cassicore-intelligence>`;

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

async function proxyRequest(
  req: http.IncomingMessage,
  res: http.ServerResponse,
  rawBody: Buffer,
): Promise<void> {
  const targetUrl = new URL(req.url ?? "/", UPSTREAM_BASE);

  const isMessages = /^\/v1\/messages/.test(targetUrl.pathname);
  const isCountTokens = targetUrl.pathname.endsWith("/count_tokens");

  let bodyToSend = rawBody;
  let state: ProxySessionState | undefined;
  let isStreaming = false;

  if (isMessages && !isCountTokens && req.method === "POST") {
    try {
      const body = JSON.parse(rawBody.toString("utf-8"));
      isStreaming = body.stream === true;
      const claudeSessionId = extractClaudeSessionId(req);
      state = getProxySession(claudeSessionId);
      state.requestCount++;

      const cognitive = await buildCognitiveInjection(state);
      if (cognitive) {
        if (body.system) {
          body.system = stripSoulMd(body.system as string | unknown[]);
        }
        injectIntoSystemPrompt(body, cognitive);
      }

      if (Array.isArray(body.messages)) {
        try {
          const curated = await bridge.curate(state.ccSessionId, body.messages);
          if (curated?.messages) {
            body.messages = curated.messages;
          }
        } catch {
          // Curation failure — proceed with original messages
        }
      }

      bodyToSend = Buffer.from(JSON.stringify(body), "utf-8");
    } catch {
      // Parse failure — forward unchanged
    }
  }

  const headers: Record<string, string | string[]> = {};
  for (const [key, value] of Object.entries(req.headers)) {
    if (key === "host" || key === "connection" || key === "content-length") continue;
    if (value !== undefined) headers[key] = value as string | string[];
  }
  headers["content-length"] = String(bodyToSend.length);
  headers["host"] = targetUrl.host;

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
      res.writeHead(proxyRes.statusCode ?? 502, proxyRes.headers);

      if (state && isStreaming) {
        let sseBuffer = "";
        proxyRes.on("data", (chunk) => {
          res.write(chunk);
          sseBuffer += (chunk as Buffer).toString("utf-8");
          // Parse SSE events for token usage from message_delta
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
        proxyRes.on("end", () => {
          postSessionMetrics(state!);
          res.end();
        });
      } else if (state && !isStreaming) {
        const chunks: Buffer[] = [];
        proxyRes.on("data", (chunk) => {
          chunks.push(chunk as Buffer);
          res.write(chunk);
        });
        proxyRes.on("end", () => {
          try {
            const data = JSON.parse(Buffer.concat(chunks).toString("utf-8"));
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
    console.error("Proxy upstream error:", String(err));
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
    res.writeHead(200, { "Content-Type": "application/json" });
    res.end(JSON.stringify({
      status: "ok",
      proxy: "cassicore-anthropic-proxy",
      cassicore: cassiUp,
      upstream: UPSTREAM_BASE,
      sessions: sessions.size,
    }));
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

server.listen(PORT, "127.0.0.1", () => {
  console.log(`CassiCore Anthropic proxy listening on http://127.0.0.1:${PORT}`);
  console.log(`Upstream: ${UPSTREAM_BASE}`);
  bridge.available().then(up => {
    console.log(`CassiCore daemon: ${up ? "connected" : "unavailable (will retry)"}`);
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
