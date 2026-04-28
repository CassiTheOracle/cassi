/**
 * CassiCore plugin for opencode — full integration.
 *
 * Provides parity with the claude-code integration:
 *   - Aurora narrative injection into the system prompt
 *     (experimental.chat.system.transform)
 *   - Session lifecycle observation (start, end, error, compaction)
 *   - Per-turn cognitive recording (cortex signals, lamina updates,
 *     mnemic episodes, reverie pings, canonical turn:start/turn:end)
 *   - Pressure-tier tracking with adaptive warnings (using actual token
 *     counts from session.turn.complete — more accurate than claude-code's
 *     transcript-size estimate)
 *   - Tool call recording with round-complete pairing
 *   - Pre/post compaction checkpointing and recovery context injection
 *   - Subagent (helix-style) lifecycle journalling
 *
 * Communicates with the CassiCore daemon over the admin Unix socket
 * (~/.cassicore/admin.sock) with a TCP fallback (127.0.0.1:7433).
 *
 * This plugin replaces the older `cassicore-footprint.mjs`. Both should
 * not be loaded simultaneously — they would double-record everything.
 *
 * Source-of-truth: integrations/opencode/src/cassicore.mjs in the
 * CassiCore repo. Install via integrations/opencode/install.sh.
 */

import http from "node:http"
import { homedir } from "node:os"
import { join } from "node:path"

// ──────────────────────────────────────────────────────────────────────────────
// Constants
// ──────────────────────────────────────────────────────────────────────────────

const SOURCE = "opencode"
const SOCKET_PATH = join(homedir(), ".cassicore", "admin.sock")
const TCP_BASE_HOST = "127.0.0.1"
const TCP_BASE_PORT = 7433

const SHORT_TIMEOUT = 2_000
const MEDIUM_TIMEOUT = 5_000
const LONG_TIMEOUT = 30_000

const HEALTH_CACHE_MS = 10_000
const AURORA_CACHE_MS = 2_000
const WORKING_STATE_INTERVAL_MS = 15_000
const LAMINA_CHAR_LIMIT = 4_000
const MAX_SESSIONS = 100
const MAX_CONTEXT_CHARS = 9_500

// Preflight context safety. This runs before the model request; if the context
// is already too large, reactive overflow warnings will never fire because the
// model won't produce a response. Keep a generous reserve for system prompt,
// tool schemas, provider overhead, and the model's response.
const APPROX_CHARS_PER_TOKEN = 4
const PREFLIGHT_TARGET_FRACTION = 0.72
const PREFLIGHT_HARD_FRACTION = 0.86
const PREFLIGHT_MIN_RESPONSE_RESERVE = 8_000
const PREFLIGHT_MAX_RESPONSE_RESERVE = 60_000
const PREFLIGHT_RECENT_MESSAGE_GRACE = 8
const PREFLIGHT_OLD_TEXT_LIMIT = 4_000
const PREFLIGHT_RECENT_TEXT_LIMIT = 16_000
const PREFLIGHT_OLD_TOOL_LIMIT = 1_500
const PREFLIGHT_RECENT_TOOL_LIMIT = 6_000
const PREFLIGHT_DEFAULT_CONTEXT_LIMIT = 128_000

// Pressure thresholds (fraction of model context used)
const PRESSURE_TIERS = [
  { name: "overflow",  min: 0.92 },
  { name: "critical",  min: 0.85 },
  { name: "high",      min: 0.78 },
  { name: "elevated",  min: 0.70 },
  { name: "warming",   min: 0.50 },
  { name: "healthy",   min: 0.00 },
]

// ──────────────────────────────────────────────────────────────────────────────
// Module state
// ──────────────────────────────────────────────────────────────────────────────

let cassiAvailable = false
let lastHealthCheck = 0
const sessions = new Map()
const laminaEnsureCache = new Set()
const auroraCache = { text: null, ts: 0 }

// ──────────────────────────────────────────────────────────────────────────────
// Plugin entry point
// ──────────────────────────────────────────────────────────────────────────────

export const CassiCorePlugin = async (input) => {
  // Best-effort initial health check (don't block plugin init)
  checkHealth().catch(() => {})

  return {
    /**
     * Aurora narrative injection. THIS is the equivalent of claude-code's
     * API proxy rewriting the system prompt. Runs on every model call.
     */
    async "experimental.chat.system.transform"(hookInput, output) {
      if (!Array.isArray(output?.system)) return
      if (!await canReachCassi()) return
      const sessionId = hookInput?.sessionID
      const sid = sessionId ? cassiSessionId(sessionId) : null

      // If preflight pruning already detected a near-overflow context, don't
      // add another ~10k chars of CassiCore narrative to the prompt. The next
      // model call needs to succeed more than it needs fresh Aurora context.
      const meta = sessionId ? getSession(sessionId) : null
      if (meta?.suppressCassiContextOnce) {
        meta.suppressCassiContextOnce = false
        return
      }

      const ctx = await buildCognitiveContext(sid)
      if (ctx) output.system.push(ctx)
    },

    /**
     * Preflight overflow protection. This is the hook that matters when the
     * conversation is already too big for the target model: without a model
     * response, neither session.turn.complete nor reactive warnings fire.
     *
     * We estimate outgoing message size, compact/ignore older bulky parts in
     * place, and suppress the next Aurora system injection if needed. This is
     * intentionally conservative: preserve the most recent messages and the
     * current user request, shrink old file/tool/read outputs first.
     */
    async "experimental.chat.messages.transform"(hookInput, output) {
      if (!Array.isArray(output?.messages)) return
      const sessionId = hookInput?.sessionID ?? sessionIdFromMessages(output.messages)
      if (!sessionId) return
      const meta = getSession(sessionId)
      const report = preflightPruneMessages(hookInput, output.messages)
      meta.preflightPressure = report.pressure
      meta.pressure = Math.max(meta.pressure ?? 0, report.pressure)

      if (report.changed) {
        meta.suppressCassiContextOnce = true
        ingest(meta.cassiSessionId, [{
          type: "preflight_context_pruned",
          sessionId: meta.cassiSessionId,
          source: SOURCE,
          pressure: report.pressure,
          beforeChars: report.beforeChars,
          afterChars: report.afterChars,
          changedMessages: report.changedMessages,
          droppedParts: report.droppedParts,
          truncatedParts: report.truncatedParts,
        }])
        cortexSignal(
          meta.cassiSessionId,
          "decision", "executive",
          `OpenCode preflight pruned context before model call: ${report.beforeChars} → ${report.afterChars} chars (${Math.round(report.pressure * 100)}% estimated pre-prune).`,
          [SOURCE, "preflight-prune", classifyTier(report.pressure)],
          0.82,
        )
        laminaAppend(
          meta.cassiSessionId,
          "session-decisions",
          `Preflight context pruning preserved generation viability: ${report.beforeChars} → ${report.afterChars} chars; changed messages=${report.changedMessages}, dropped parts=${report.droppedParts}, truncated parts=${report.truncatedParts}.`,
          "opencode-preflight-prune",
        )
      }
    },

    /**
     * Opencode event stream — we use this for session lifecycle and to
     * detect assistant message completion (so we can emit turn:end with the
     * actual response text, which the chat hooks don't give us).
     */
    async event({ event }) {
      if (!await canReachCassi()) return
      const type = event?.type
      const properties = asRecord(event?.properties)

      if (type === "session.created") {
        const sessionId = sessionIdFrom(properties.info) ?? properties.sessionID
        if (sessionId) recordSessionStart(String(sessionId), input.directory).catch(() => {})
        return
      }

      if (type === "session.deleted") {
        const sessionId = sessionIdFrom(properties.info) ?? properties.sessionID
        if (sessionId) recordSessionEnd(String(sessionId), "deleted").catch(() => {})
        return
      }

      if (type === "session.error") {
        const sessionId = sessionIdFrom(properties.info) ?? properties.sessionID ?? "global"
        const message = stringifyBrief(properties.error ?? properties)
        recordAnomaly(String(sessionId), `OpenCode session error: ${message}`).catch(() => {})
        return
      }

      if (type === "session.idle") {
        const sessionId = properties.sessionID
        if (sessionId) {
          const meta = getSession(String(sessionId))
          if (meta) postWorkingState(String(sessionId), true)
        }
        return
      }

      if (type === "message.completed" || type === "message.updated") {
        const info = asRecord(properties.info)
        if (!isAssistantCompleted(info, type)) return
        const messageId = typeof info.id === "string" ? info.id : undefined
        const sessionId = sessionIdFrom(info)
        if (!sessionId || wasCompleted(sessionId, messageId)) return
        recordAssistantMessage(sessionId, info, properties).catch(() => {})
      }
    },

    /**
     * UserPromptSubmit equivalent. Fires when a new user message hits a
     * session. We extract the prompt text, bump the turn counter, observe
     * with Aurora, and seed cortex/lamina/mnemic.
     */
    async "chat.message"(hookInput, output) {
      if (!await canReachCassi()) return
      const sessionId = hookInput?.sessionID
      if (!sessionId) return

      const prompt = extractText(output?.parts).slice(0, 8_000)
      if (!prompt) return

      const meta = getSession(sessionId)
      meta.turnCount += 1
      meta.lastUserMessage = prompt
      meta.turnStartedAt = Date.now()
      meta.largeOutputsThisTurn = 0
      meta.pendingTools.clear()

      await ensureSessionStarted(sessionId, input.directory)
      await recordUserPrompt(sessionId, prompt, hookInput)
    },

    /**
     * PreToolUse equivalent. Track active files, emit cortex decision
     * signal, register pending tool for round-complete pairing, and under
     * heavy pressure suggest narrowing file reads.
     */
    async "tool.execute.before"(hookInput, output) {
      if (!await canReachCassi()) return
      const sessionId = hookInput?.sessionID
      const toolName = hookInput?.tool
      if (!sessionId || !toolName) return

      await ensureSessionStarted(sessionId, input.directory)
      const meta = getSession(sessionId)
      meta.toolCount += 1

      const callId = String(hookInput.callID ?? `${sessionId}-${meta.toolCount}`)
      meta.pendingTools.set(callId, { name: String(toolName), id: callId })
      trackActiveFile(meta, output?.args)

      await recordToolStart(sessionId, String(toolName), callId)

      // Pressure-aware input modification
      const tier = classifyTier(meta.pressure)
      if ((tier === "critical" || tier === "overflow") && /^read|file_read|^cassi_file/i.test(String(toolName))) {
        const args = output?.args
        if (args && typeof args === "object") {
          const limit = args.limit ?? args.maxLines
          if (!limit || limit > 200) {
            // Don't mutate args silently — the SDK pattern is to leave args
            // alone but advise via cortex. Logging this as a soft signal.
            cortexSignal(
              cassiSessionId(sessionId),
              "concern", "executive",
              `Tool ${toolName} invoked under ${tier} pressure without read limit`,
              [SOURCE, "pressure", tier], 0.7,
            )
          }
        }
      }
    },

    /**
     * PostToolUse equivalent. Record result, classify error/success,
     * pair the result with its pending tool call, emit tool:round-complete.
     */
    async "tool.execute.after"(hookInput, output) {
      if (!await canReachCassi()) return
      const sessionId = hookInput?.sessionID
      const toolName = hookInput?.tool
      if (!sessionId || !toolName) return

      await ensureSessionStarted(sessionId, input.directory)
      const callId = String(hookInput.callID ?? `${sessionId}-${Date.now()}`)
      const toolOutput = typeof output?.output === "string" ? output.output : stringifyBrief(output)
      const isError = /error|exception|traceback/i.test(toolOutput.slice(0, 200))

      await recordToolResult(sessionId, String(toolName), callId, toolOutput, isError, hookInput?.args)
    },

    /**
     * PreCompact equivalent. Save a structured handoff + checkpoint so
     * post-compact can restore working context.
     */
    async "experimental.session.compacting"(hookInput, output) {
      if (!await canReachCassi()) return
      const sessionId = hookInput?.sessionID
      if (!sessionId) return
      await ensureSessionStarted(sessionId, input.directory)
      await recordPreCompact(sessionId)
      if (Array.isArray(output?.context)) {
        output.context.push(
          "## CassiCore Continuity\nA persistent cognitive checkpoint was just written for this session. After compaction, request post-compact recovery context.",
        )
      }
    },

    /**
     * PostCompact equivalent. Inject recovery context (focus topic, active
     * files, last decisions) back into the post-compact prompt via the
     * canonical event channel.
     */
    async "session.compaction.complete"(hookInput) {
      if (!await canReachCassi()) return
      const sessionId = hookInput?.sessionID
      if (!sessionId) return
      await recordPostCompact(sessionId, Boolean(hookInput?.auto), Boolean(hookInput?.overflow))
    },

    /**
     * Stop equivalent — turn finished, model handed control back. We get
     * actual token counts here, which beats claude-code's transcript-size
     * estimate. Emit canonical turn:end so Reverie/memory/thinker fire.
     */
    async "session.turn.complete"(hookInput) {
      if (!await canReachCassi()) return
      const sessionId = hookInput?.sessionID
      if (!sessionId) return
      const meta = getSession(sessionId)

      // Update pressure from real token counts
      const tokens = hookInput?.tokens
      const limit = hookInput?.model?.limit?.context
      if (tokens && limit) {
        const used = (tokens.input ?? 0) + (tokens.output ?? 0)
        meta.pressure = Math.min(1.0, used / limit)
      }

      const durationMs = meta.turnStartedAt > 0 ? Date.now() - meta.turnStartedAt : 0
      await recordTurnComplete(sessionId, hookInput, durationMs)
    },

    /**
     * Permission requests — log as cortex anomalies for self-awareness.
     * Doesn't change permission outcome.
     */
    async "permission.ask"(perm) {
      if (!await canReachCassi()) return
      const sessionId = perm?.sessionID ?? perm?.sessionId
      if (!sessionId) return
      cortexSignal(
        cassiSessionId(sessionId),
        "request", "executive",
        `OpenCode permission requested: ${stringifyBrief(perm)}`.slice(0, 700),
        [SOURCE, "permission-ask"],
        0.6,
      )
    },
  }
}

export default CassiCorePlugin

// ──────────────────────────────────────────────────────────────────────────────
// Per-session state
// ──────────────────────────────────────────────────────────────────────────────

function cassiSessionId(sessionId) {
  const raw = String(sessionId || "global")
  return raw.startsWith("oc:") ? raw : `oc:${raw}`
}

function getSession(sessionId) {
  const key = String(sessionId)
  let meta = sessions.get(key)
  if (!meta) {
    evictOldestSessionIfNeeded()
    meta = {
      sessionId: key,
      cassiSessionId: cassiSessionId(key),
      createdAt: Date.now(),
      lastActivityAt: Date.now(),
      sessionStarted: false,
      turnCount: 0,
      toolCount: 0,
      compactionCount: 0,
      lastWorkingStateAt: 0,
      lastCheckpointAt: 0,
      turnStartedAt: 0,
      lastUserMessage: "",
      activeFiles: [],
      usedTools: new Set(),
      pendingTools: new Map(),
      toolRoundCount: 0,
      completedMessages: new Set(),
      pressure: 0,
      lastTier: "healthy",
      warnedAtTier: "healthy",
      handoffWritten: false,
      postCompaction: false,
      largeOutputsThisTurn: 0,
      preflightPressure: 0,
      suppressCassiContextOnce: false,
    }
    sessions.set(key, meta)
  }
  meta.lastActivityAt = Date.now()
  return meta
}

function evictOldestSessionIfNeeded() {
  if (sessions.size < MAX_SESSIONS) return
  let oldestKey
  let oldestAt = Number.POSITIVE_INFINITY
  for (const [key, meta] of sessions) {
    if (meta.lastActivityAt < oldestAt) {
      oldestAt = meta.lastActivityAt
      oldestKey = key
    }
  }
  if (oldestKey) sessions.delete(oldestKey)
}

function classifyTier(pressure) {
  for (const tier of PRESSURE_TIERS) {
    if (pressure >= tier.min) return tier.name
  }
  return "healthy"
}

// ──────────────────────────────────────────────────────────────────────────────
// Preflight context pruning
// ──────────────────────────────────────────────────────────────────────────────

function preflightPruneMessages(hookInput, messages) {
  const contextLimit = Number(hookInput?.model?.limit?.context ?? PREFLIGHT_DEFAULT_CONTEXT_LIMIT)
  if (!contextLimit || contextLimit <= 0 || messages.length === 0) {
    return {
      changed: false,
      beforeChars: estimateMessagesChars(messages),
      afterChars: estimateMessagesChars(messages),
      pressure: 0,
      changedMessages: 0,
      droppedParts: 0,
      truncatedParts: 0,
    }
  }

  const reserveTokens = Math.min(
    PREFLIGHT_MAX_RESPONSE_RESERVE,
    Math.max(PREFLIGHT_MIN_RESPONSE_RESERVE, Math.floor(contextLimit * 0.12)),
  )
  const targetTokens = Math.max(1, Math.floor(contextLimit * PREFLIGHT_TARGET_FRACTION) - reserveTokens)
  const hardTokens = Math.max(1, Math.floor(contextLimit * PREFLIGHT_HARD_FRACTION) - reserveTokens)
  const targetChars = targetTokens * APPROX_CHARS_PER_TOKEN
  const hardChars = hardTokens * APPROX_CHARS_PER_TOKEN

  const beforeChars = estimateMessagesChars(messages)
  const pressure = beforeChars / Math.max(1, contextLimit * APPROX_CHARS_PER_TOKEN)

  if (beforeChars <= hardChars) {
    return { changed: false, beforeChars, afterChars: beforeChars, pressure, changedMessages: 0, droppedParts: 0, truncatedParts: 0 }
  }

  let changedMessages = 0
  let droppedParts = 0
  let truncatedParts = 0
  const recentCutoff = Math.max(0, messages.length - PREFLIGHT_RECENT_MESSAGE_GRACE)

  // Phase 1: compact individual bulky parts. Preserve all message records, but
  // replace old huge tool/file/text content with compact synthetic summaries.
  for (let i = 0; i < messages.length; i++) {
    const msg = messages[i]
    if (!msg || !Array.isArray(msg.parts)) continue
    const isRecent = i >= recentCutoff
    const partLimit = isRecent ? PREFLIGHT_RECENT_TEXT_LIMIT : PREFLIGHT_OLD_TEXT_LIMIT
    const toolLimit = isRecent ? PREFLIGHT_RECENT_TOOL_LIMIT : PREFLIGHT_OLD_TOOL_LIMIT
    let msgChanged = false

    for (let p = 0; p < msg.parts.length; p++) {
      const part = msg.parts[p]
      const compacted = compactPartForPreflight(part, partLimit, toolLimit, isRecent)
      if (compacted !== part) {
        msg.parts[p] = compacted
        msgChanged = true
        truncatedParts += 1
      }
    }
    if (msgChanged) changedMessages += 1
  }

  let afterChars = estimateMessagesChars(messages)
  if (afterChars <= targetChars) {
    return { changed: true, beforeChars, afterChars, pressure, changedMessages, droppedParts, truncatedParts }
  }

  // Phase 2: drop old non-essential parts by marking them ignored. This is
  // safer than deleting because opencode can still retain UI history while the
  // outgoing model call excludes ignored parts.
  for (let i = 0; i < recentCutoff && afterChars > targetChars; i++) {
    const msg = messages[i]
    if (!msg || !Array.isArray(msg.parts)) continue
    let msgChanged = false
    for (let p = msg.parts.length - 1; p >= 0; p--) {
      const part = msg.parts[p]
      if (afterChars <= targetChars) break
      if (shouldPreservePart(part)) continue
      const chars = estimatePartChars(part)
      if (dropPartFromMessage(msg, p, "preflight-overflow")) {
        afterChars -= chars
        droppedParts += 1
        msgChanged = true
      }
    }
    if (msgChanged) changedMessages += 1
  }

  // Phase 3: if still too big, add a compact synthetic summary at the oldest
  // kept boundary and aggressively ignore all but the recent window. Better a
  // lossy successful turn than no response at all.
  afterChars = estimateMessagesChars(messages)
  if (afterChars > targetChars && recentCutoff > 0) {
    const summaryPart = {
      id: `cassicore-preflight-summary-${Date.now()}`,
      type: "text",
      text: `[CassiCore preflight overflow guard: older transcript parts were omitted before this model call because the outgoing context exceeded the model limit. Recover details from persistent memory/KV if needed.]`,
      synthetic: true,
      metadata: { source: SOURCE, reason: "preflight-overflow-summary" },
    }
    const boundary = messages[Math.max(0, recentCutoff - 1)]
    if (boundary && Array.isArray(boundary.parts)) boundary.parts.push(summaryPart)

    for (let i = 0; i < recentCutoff && afterChars > targetChars; i++) {
      const msg = messages[i]
      if (!msg || !Array.isArray(msg.parts)) continue
      let msgChanged = false
      for (let p = msg.parts.length - 1; p >= 0; p--) {
        const part = msg.parts[p]
        if (afterChars <= targetChars) break
        const chars = estimatePartChars(part)
        if (dropPartFromMessage(msg, p, "preflight-hard-overflow")) {
          afterChars -= chars
          droppedParts += 1
          msgChanged = true
        }
      }
      if (msgChanged) changedMessages += 1
    }
  }

  afterChars = estimateMessagesChars(messages)
  return { changed: true, beforeChars, afterChars, pressure, changedMessages, droppedParts, truncatedParts }
}

function compactPartForPreflight(part, textLimit, toolLimit, isRecent) {
  if (!part || typeof part !== "object") return part
  if (part.ignored === true) return part

  if (typeof part.text === "string" && part.text.length > textLimit) {
    return {
      ...part,
      text: summarizeLongText(part.text, textLimit, part.type ?? "text", isRecent),
      metadata: { ...(part.metadata ?? {}), cassicorePreflight: "truncated" },
    }
  }

  if (part.type === "tool" && part.state && typeof part.state === "object") {
    const state = part.state
    if (typeof state.output === "string" && state.output.length > toolLimit) {
      return {
        ...part,
        state: {
          ...state,
          output: summarizeLongText(state.output, toolLimit, `tool:${part.tool ?? "unknown"}`, isRecent),
        },
        metadata: { ...(part.metadata ?? {}), cassicorePreflight: "tool-output-truncated" },
      }
    }
    if (typeof state.error === "string" && state.error.length > toolLimit) {
      return {
        ...part,
        state: {
          ...state,
          error: summarizeLongText(state.error, toolLimit, `tool-error:${part.tool ?? "unknown"}`, isRecent),
        },
        metadata: { ...(part.metadata ?? {}), cassicorePreflight: "tool-error-truncated" },
      }
    }
  }

  if (part.type === "file" && part.source?.text?.value && part.source.text.value.length > textLimit) {
    return {
      ...part,
      source: {
        ...part.source,
        text: {
          ...part.source.text,
          value: summarizeLongText(part.source.text.value, textLimit, `file:${part.source.path ?? part.filename ?? "unknown"}`, isRecent),
        },
      },
      metadata: { ...(part.metadata ?? {}), cassicorePreflight: "file-truncated" },
    }
  }

  return part
}

function summarizeLongText(text, limit, label, isRecent) {
  if (text.length <= limit) return text
  const head = Math.max(500, Math.floor(limit * (isRecent ? 0.7 : 0.55)))
  const tail = Math.max(500, limit - head - 400)
  return [
    `[CassiCore preflight truncated ${label}: original ${text.length} chars. ` +
      `Keeping ${head} head chars + ${tail} tail chars so the model can respond.]`,
    text.slice(0, head),
    "\n[… omitted for preflight context budget …]\n",
    text.slice(-tail),
  ].join("\n")
}

function shouldPreservePart(part) {
  if (!part || typeof part !== "object") return true
  // Preserve user text until phase 3. Assistant text/reasoning/tool output can
  // be pruned in old messages; user intent is usually the more important side
  // of the historical transcript.
  if (part.type === "text" && !part.synthetic) return true
  if (part.type === "agent") return true
  if (part.type === "subtask") return true
  if (part.type === "compaction") return true
  return false
}

function dropPartFromMessage(msg, partIndex, reason) {
  const part = msg.parts?.[partIndex]
  if (!part || typeof part !== "object") return false

  // For user text, `ignored` is the supported way to keep UI history while
  // excluding it from the model request. For assistant/tool/reasoning, opencode
  // does not honor ignored, so remove the part from the transient copy.
  if (msg.info?.role === "user" && part.type === "text") {
    if (part.ignored === true) return false
    part.ignored = true
    part.metadata = { ...(part.metadata ?? {}), cassicorePreflight: reason }
    return true
  }

  msg.parts.splice(partIndex, 1)
  return true
}

function estimateMessagesChars(messages) {
  let total = 0
  for (const msg of messages) {
    if (!msg || !Array.isArray(msg.parts)) continue
    total += estimateMessageInfoChars(msg.info)
    for (const part of msg.parts) {
      if (part?.ignored === true) continue
      total += estimatePartChars(part)
    }
  }
  return total
}

function estimateMessageInfoChars(info) {
  if (!info || typeof info !== "object") return 0
  return 80
}

function estimatePartChars(part) {
  if (!part || typeof part !== "object") return 0
  let total = 40
  if (typeof part.text === "string") total += part.text.length
  if (typeof part.content === "string") total += part.content.length
  if (typeof part.prompt === "string") total += part.prompt.length
  if (typeof part.description === "string") total += part.description.length
  if (part.type === "tool" && part.state && typeof part.state === "object") {
    if (typeof part.state.raw === "string") total += part.state.raw.length
    if (typeof part.state.output === "string") total += part.state.output.length
    if (typeof part.state.error === "string") total += part.state.error.length
    if (part.state.input) total += stringifyBrief(part.state.input).length
  }
  if (part.type === "file" && part.source?.text?.value) total += String(part.source.text.value).length
  return total
}

// ──────────────────────────────────────────────────────────────────────────────
// Cognitive context builder (Aurora-first with recovery + pressure)
// ──────────────────────────────────────────────────────────────────────────────

async function buildCognitiveContext(sid) {
  const parts = []
  let charCount = 0

  const push = (text) => {
    if (!text) return false
    if (charCount + text.length > MAX_CONTEXT_CHARS) return false
    parts.push(text)
    charCount += text.length
    return true
  }

  // 1. Aurora narrative — primary cognitive signal
  const auroraText = await auroraSerializedCached()
  if (auroraText && auroraText.trim()) {
    push(`<aurora>\n${auroraText}\n</aurora>`)
  }

  // 2. Recovery context — only after compaction
  if (sid) {
    const meta = findMetaByCassiId(sid)
    if (meta?.postCompaction) {
      const recovery = await buildRecoveryContext(sid)
      if (recovery) push(recovery)
      meta.postCompaction = false // consume once
    }
    // 3. Pressure warning — escalating tiers
    if (meta) {
      const warning = buildPressureWarning(meta)
      if (warning) push(warning)
    }
  }

  if (parts.length === 0) return null
  return `<cassicore-context>\n${parts.join("\n\n")}\n</cassicore-context>`
}

async function auroraSerializedCached() {
  const now = Date.now()
  if (now - auroraCache.ts < AURORA_CACHE_MS && auroraCache.text !== null) {
    return auroraCache.text
  }
  const res = await send("GET", "/intelligence/aurora/serialize", undefined, SHORT_TIMEOUT)
  const text = res?.context ?? ""
  auroraCache.text = text
  auroraCache.ts = now
  return text
}

async function buildRecoveryContext(sid) {
  const handoff = await send("GET", `/memory/kv/${encodeURIComponent("handoff:" + sid)}`)
  if (handoff && typeof handoff === "object" && !handoff.error) {
    return [
      "**Recovery from compaction:**",
      `Focus: ${handoff.focusTopic ?? "unknown"}`,
      `Active files: ${(handoff.activeFiles ?? []).join(", ") || "none"}`,
      `Recent tools: ${(handoff.usedTools ?? []).slice(-5).join(", ") || "none"}`,
      ...(handoff.criticalContext?.length
        ? [`Critical:\n${handoff.criticalContext.map((c) => `- ${c}`).join("\n")}`]
        : []),
    ].join("\n")
  }
  const checkpoint = await send("GET", `/memory/kv/${encodeURIComponent("checkpoint:" + sid)}`)
  if (checkpoint && typeof checkpoint === "object" && !checkpoint.error) {
    return [
      "**Checkpoint recovery:**",
      `Turn: ${checkpoint.turnCount}, Focus: ${checkpoint.focusTopic ?? "unknown"}`,
      `Files: ${(checkpoint.activeFiles ?? []).join(", ") || "none"}`,
    ].join("\n")
  }
  return null
}

function buildPressureWarning(meta) {
  const tier = classifyTier(meta.pressure)
  if (tier === "healthy" || tier === "warming") return null
  if (tier === meta.warnedAtTier) return null
  meta.warnedAtTier = tier
  meta.lastTier = tier

  const pct = Math.round(meta.pressure * 100)
  if (tier === "elevated") {
    return `**Context Pressure:** ${pct}% (elevated). Consider consolidating — older tool results are consuming space.`
  }
  if (tier === "high") {
    return `**Context Pressure:** ${pct}% (high). Collapse old results or delegate complex remaining work to Constellation.`
  }
  if (tier === "critical" || tier === "overflow") {
    return [
      `**Context Pressure:** ${pct}% (${tier}). Save progress and delegate:`,
      '`cassi_blackboard({ action: "post", name: "session-handoff", channel: "artifacts", content: "..." })`',
      '`cassi_agent({ type: "constellation", action: "project", goal: "Continue: ..." })`',
    ].join("\n")
  }
  return null
}

function findMetaByCassiId(sid) {
  for (const meta of sessions.values()) {
    if (meta.cassiSessionId === sid) return meta
  }
  return null
}

// ──────────────────────────────────────────────────────────────────────────────
// Recorders — high-level operations on per-session events
// ──────────────────────────────────────────────────────────────────────────────

async function ensureSessionStarted(sessionId, directory) {
  const meta = getSession(sessionId)
  if (meta.sessionStarted) return
  await recordSessionStart(sessionId, directory)
}

async function recordSessionStart(sessionId, directory) {
  const meta = getSession(sessionId)
  if (meta.sessionStarted) return
  meta.sessionStarted = true
  const sid = meta.cassiSessionId
  const cwd = directory || "unknown workspace"
  const projectName = cwd.split("/").filter(Boolean).pop() || "unknown"

  ingest(sid, [{ type: "session_start", sessionId: sid, source: SOURCE, cwd }])
  cortexSignal(sid, "perception", "sensory", `OpenCode session started in ${cwd}`, [SOURCE, "session-start"], 0.7)
  laminaAppend(sid, "session-decisions", `OpenCode session started in ${cwd}.`, "opencode-session-start")
  memoryStoreEpisode(
    sid,
    `[OpenCode session started]\nWorkspace: ${cwd}\nSession: ${sid}`,
    [SOURCE, "session-start", sid], "conversation",
  )
  reveriePing(sid, "opencode-session-start")

  // Aurora seeding — ship narrative on first turn (parity with commit 816c397)
  auroraObserve(
    `OpenCode session started in workspace ${cwd}. ` +
    `Working on the ${projectName} project. ` +
    `Awaiting a prompt from Valerie.`,
  )

  // Invalidate Aurora cache so next system-prompt transform fetches fresh
  auroraCache.ts = 0
}

async function recordSessionEnd(sessionId, reason) {
  const meta = sessions.get(String(sessionId))
  if (!meta) return
  const sid = meta.cassiSessionId
  ingest(sid, [{ type: "session_end", sessionId: sid, reason, source: SOURCE }])
  cortexSignal(sid, "decision", "executive", `OpenCode session ended (${reason})`, [SOURCE, "session-end"], 0.5)
  laminaAppend(sid, "session-decisions", `OpenCode session ended (${reason}). Final turn: ${meta.turnCount}.`, "opencode-session-end")
  memoryStoreEpisode(
    sid,
    `[OpenCode session ended]\nReason: ${reason}\nTurns: ${meta.turnCount}\nTools: ${meta.toolCount}`,
    [SOURCE, "session-end", sid], "conversation",
  )
  reveriePing(sid, "opencode-session-end")
}

async function recordAnomaly(sessionId, message) {
  const sid = cassiSessionId(sessionId)
  cortexSignal(sid, "anomaly", "limbic", message.slice(0, 700), [SOURCE, "anomaly"], 0.85)
  ingest(sid, [{ type: "anomaly", sessionId: sid, message: message.slice(0, 2000), source: SOURCE }])
}

async function recordUserPrompt(sessionId, prompt, hookInput) {
  const meta = getSession(sessionId)
  const sid = meta.cassiSessionId

  // Index for context curator
  indexMessages(sid, [{ role: "user", content: prompt }])

  // Canonical turn:start — wakes up Reverie/memory/thinker
  emitTurnStart(sid, prompt)

  ingest(sid, [{ type: "user_message", content: prompt, source: SOURCE, sessionId: sid }])
  cortexSignal(sid, "perception", "sensory", prompt.slice(0, 500), [SOURCE, "user-prompt"], 0.75)
  laminaRethink(sid, "open-hypotheses", `Current OpenCode user request:\n${prompt.slice(0, 2000)}`, "opencode-user-prompt")
  memoryStoreEpisode(sid, `[OpenCode user prompt]\n${prompt.slice(0, 8_000)}`, [SOURCE, "user-prompt", sid], "conversation")
  reveriePing(sid, "opencode-user-prompt")

  // Aurora observe + workspace enrich (kicks off background context fetch)
  if (prompt.length > 5) {
    auroraObserve(prompt)
    workspaceEnrich(prompt, sid)
  }

  // Track agent if subagent-scoped
  recordAgentStartIfNeeded(sid, hookInput)

  // Invalidate Aurora cache so next system transform sees the observation
  auroraCache.ts = 0
}

async function recordAssistantMessage(sessionId, info, properties) {
  const meta = getSession(sessionId)
  const sid = meta.cassiSessionId
  const text = extractText(asArray(properties.parts)).slice(0, 12_000)

  ingest(sid, [{ type: "assistant_message", content: text || "[no text content]", source: SOURCE, sessionId: sid }])
  if (text) {
    indexMessages(sid, [{ role: "assistant", content: text }])
    cortexSignal(sid, "action", "motor", `OpenCode assistant response (${text.length} chars)`, [SOURCE, "assistant-message"], 0.55)
    memoryStoreEpisode(sid, `[OpenCode assistant response]\n${text.slice(0, 8_000)}`, [SOURCE, "assistant-message", sid], "observation")

    // Have Aurora observe assistant reasoning text — feeds back into the
    // cognitive state for the next turn
    auroraObserve(text)
  }
  recordAgentStopIfNeeded(sid, info)
  auroraCache.ts = 0
}

async function recordToolStart(sessionId, toolName, callId) {
  const meta = getSession(sessionId)
  const sid = meta.cassiSessionId
  meta.usedTools.add(toolName)
  ingest(sid, [{
    type: "tool_call_start",
    sessionId: sid,
    toolName,
    toolCallId: callId,
    source: SOURCE,
  }])
  cortexSignal(sid, "decision", "executive", `OpenCode preparing tool ${toolName}`, [SOURCE, "pre-tool-use", toolName], 0.55)
}

async function recordToolResult(sessionId, toolName, callId, toolOutput, isError, args) {
  const meta = getSession(sessionId)
  const sid = meta.cassiSessionId

  if (toolOutput.length > 10_000) meta.largeOutputsThisTurn += 1

  // Index moderate-sized outputs for later retrieval
  if (toolOutput.length > 0 && toolOutput.length < 50_000) {
    indexMessages(sid, [{ role: "assistant", content: `[${toolName}] ${toolOutput.slice(0, 5_000)}` }])
  }

  ingest(sid, [{
    type: "tool_call_result",
    sessionId: sid,
    toolName,
    toolCallId: callId,
    isError,
    contentPreview: toolOutput.slice(0, 1_000),
    source: SOURCE,
  }])

  cortexSignal(
    sid,
    isError ? "concern" : "action",
    isError ? "limbic" : "motor",
    `OpenCode tool ${toolName} ${isError ? "errored" : "completed"}: ${toolOutput.slice(0, 700)}`,
    [SOURCE, "post-tool-use", toolName, isError ? "error" : "success"],
    isError ? 0.8 : 0.6,
  )
  memoryStoreEpisode(
    sid,
    `[OpenCode tool ${toolName} ${isError ? "error" : "result"}]\n${toolOutput.slice(0, 8_000)}`,
    [SOURCE, "tool-result", toolName, sid],
    isError ? "error" : "observation",
  )
  reveriePing(sid, "opencode-tool-result")

  // Pair with pending call → emit tool:round-complete (parity with claude-code 8fba553)
  let pairedId
  if (callId && meta.pendingTools.has(callId)) {
    pairedId = callId
  } else {
    const lastKey = Array.from(meta.pendingTools.keys()).pop()
    if (lastKey) pairedId = lastKey
  }
  if (pairedId) {
    const call = meta.pendingTools.get(pairedId)
    meta.pendingTools.delete(pairedId)
    meta.toolRoundCount += 1
    if (call) {
      emitToolRound(sid, meta.toolRoundCount, [call], [{
        toolCallId: pairedId,
        isError,
        contentPreview: toolOutput.slice(0, 1_000),
      }])
    }
  }

  postWorkingState(sessionId)
}

async function recordPreCompact(sessionId) {
  const meta = getSession(sessionId)
  const sid = meta.cassiSessionId
  meta.compactionCount += 1

  // Save handoff (rich) and checkpoint (terse)
  const handoff = {
    sessionId: sid,
    timestamp: Date.now(),
    trigger: `compaction at turn ${meta.turnCount}`,
    focusTopic: meta.lastUserMessage.slice(0, 200),
    activeFiles: meta.activeFiles.slice(0, 10),
    usedTools: [...meta.usedTools].slice(-15),
    turnCount: meta.turnCount,
    criticalContext: [
      meta.lastUserMessage ? `Last request: ${meta.lastUserMessage.slice(0, 200)}` : null,
      meta.activeFiles.length > 0 ? `Active files: ${meta.activeFiles.slice(0, 5).join(", ")}` : null,
      `Tools used: ${[...meta.usedTools].slice(-5).join(", ")}`,
    ].filter(Boolean),
  }
  meta.handoffWritten = true
  kvSet(`handoff:${sid}`, handoff)

  const checkpoint = {
    sessionId: sid,
    timestamp: Date.now(),
    turnCount: meta.turnCount,
    toolCallCount: meta.toolCount,
    activeFiles: meta.activeFiles.slice(0, 10),
    compactionCount: meta.compactionCount,
    focusTopic: meta.lastUserMessage.slice(0, 200),
  }
  kvSet(`checkpoint:${sid}`, checkpoint)
  meta.lastCheckpointAt = Date.now()

  ingest(sid, [{
    type: "compaction_start",
    sessionId: sid,
    compactionCount: meta.compactionCount,
    turnCount: meta.turnCount,
    source: SOURCE,
  }])
  cortexSignal(sid, "decision", "executive",
    `OpenCode pre-compaction checkpoint saved at turn ${meta.turnCount}`,
    [SOURCE, "pre-compact"], 0.8)
  laminaAppend(sid, "session-decisions",
    `Pre-compaction checkpoint saved at turn ${meta.turnCount}. Active files: ${meta.activeFiles.slice(0, 5).join(", ") || "none"}.`,
    "opencode-pre-compact")
  memoryStoreEpisode(sid,
    `[OpenCode pre-compaction checkpoint]\nTurn: ${meta.turnCount}\nActive files: ${meta.activeFiles.slice(0, 10).join(", ")}`,
    [SOURCE, "pre-compact", sid], "conversation")
  reveriePing(sid, "opencode-pre-compact")
}

async function recordPostCompact(sessionId, auto, overflow) {
  const meta = getSession(sessionId)
  const sid = meta.cassiSessionId
  meta.postCompaction = true // consumed by next system-prompt transform
  meta.handoffWritten = false
  meta.warnedAtTier = "healthy" // reset pressure warnings post-compact

  ingest(sid, [{
    type: "compaction_complete",
    sessionId: sid,
    compactionCount: meta.compactionCount,
    auto,
    overflow,
    source: SOURCE,
  }])
  cortexSignal(sid, "decision", "executive",
    `OpenCode post-compaction recovery (auto=${auto}, overflow=${overflow})`,
    [SOURCE, "post-compact"], 0.7)
  laminaAppend(sid, "open-hypotheses",
    `Post-compaction recovery is active for OpenCode session ${sid}.`,
    "opencode-post-compact")
  memoryStoreEpisode(sid,
    `[OpenCode post-compaction recovery]\nCompaction count: ${meta.compactionCount}, auto=${auto}, overflow=${overflow}`,
    [SOURCE, "post-compact", sid], "conversation")
  reveriePing(sid, "opencode-post-compact")

  auroraCache.ts = 0
}

async function recordTurnComplete(sessionId, hookInput, durationMs) {
  const meta = getSession(sessionId)
  const sid = meta.cassiSessionId
  const tokens = hookInput?.tokens
  const tier = classifyTier(meta.pressure)

  postWorkingState(sessionId, true)

  ingest(sid, [{
    type: "turn_complete",
    sessionId: sid,
    turnCount: meta.turnCount,
    toolCallCount: meta.toolCount,
    activeFiles: meta.activeFiles.slice(0, 10),
    pressure: meta.pressure,
    tier,
    largeOutputs: meta.largeOutputsThisTurn,
    tokens,
    finish: hookInput?.finish,
    durationMs,
    source: SOURCE,
  }])

  // Canonical turn:end — fires Reverie.onTurnEnd, memory consolidation,
  // every BaseCognitiveModule lifecycle hook
  emitTurnEnd(
    sid,
    `[opencode turn ${meta.turnCount} complete: ${meta.toolCount} tools, ${meta.activeFiles.slice(0, 3).join(", ")}]`,
    durationMs,
  )

  cortexSignal(sid, "decision", "executive",
    `OpenCode turn ${meta.turnCount} complete after ${meta.toolCount} tools (pressure ${tier})`,
    [SOURCE, "turn-end", tier], 0.65)
  reveriePing(sid, "opencode-turn-end")
}

function postWorkingState(sessionId, force = false) {
  const meta = getSession(sessionId)
  const now = Date.now()
  if (!force && now - meta.lastWorkingStateAt < WORKING_STATE_INTERVAL_MS) return
  meta.lastWorkingStateAt = now
  const sid = meta.cassiSessionId
  const state = {
    sessionId: sid,
    timestamp: now,
    turnCount: meta.turnCount,
    pressure: meta.pressure,
    tier: classifyTier(meta.pressure),
    mode: "working",
    activeFiles: meta.activeFiles.slice(0, 10),
    toolCallCount: meta.toolCount,
    largeOutputsThisTurn: meta.largeOutputsThisTurn,
  }
  kvSet(`working-state:${sid}`, state)
  laminaAppend(sid, "session-decisions",
    `Working state: turn ${meta.turnCount}, ${meta.toolCount} tools, pressure ${classifyTier(meta.pressure)}. Active files: ${meta.activeFiles.slice(0, 5).join(", ") || "none"}.`,
    "opencode-working-state")
}

function recordAgentStartIfNeeded(sid, hookInput) {
  const agent = hookInput?.agent
  if (!agent || agent === "general") return
  helixJournalAppend(sid, "session.start", { agentId: agent, agentType: agent, hookEvent: "chat.message" }, agent)
}

function recordAgentStopIfNeeded(sid, info) {
  const agent = info.agent ?? info.agentID
  if (!agent || agent === "general") return
  helixJournalAppend(sid, "session.terminate", { agentId: agent, agentType: agent, hookEvent: "message.completed" }, agent)
}

function trackActiveFile(meta, args) {
  const record = asRecord(args)
  const filePath = record.filePath ?? record.file_path ?? record.path
  if (typeof filePath !== "string" || meta.activeFiles.includes(filePath)) return
  meta.activeFiles.push(filePath)
  if (meta.activeFiles.length > 20) meta.activeFiles.shift()
}

function wasCompleted(sessionId, messageId) {
  if (!messageId) return false
  const meta = getSession(sessionId)
  if (meta.completedMessages.has(messageId)) return true
  meta.completedMessages.add(messageId)
  // Cap memory growth
  if (meta.completedMessages.size > 200) {
    const first = meta.completedMessages.values().next().value
    meta.completedMessages.delete(first)
  }
  return false
}

// ──────────────────────────────────────────────────────────────────────────────
// CassiCore admin API bridge
// ──────────────────────────────────────────────────────────────────────────────

async function canReachCassi() {
  return cassiAvailable || await checkHealth()
}

async function checkHealth() {
  const now = Date.now()
  if (now - lastHealthCheck < HEALTH_CACHE_MS) return cassiAvailable
  lastHealthCheck = now
  const res = await send("GET", "/health")
  cassiAvailable = res?.status === "ok"
  return cassiAvailable
}

function send(method, pathname, body, timeoutMs = SHORT_TIMEOUT) {
  return new Promise((resolve) => {
    const payload = body ? JSON.stringify(body) : undefined
    const headers = payload
      ? { "content-type": "application/json", "content-length": String(Buffer.byteLength(payload)) }
      : {}

    const tryRequest = (opts) => new Promise((res) => {
      const req = http.request(opts, (response) => {
        const chunks = []
        response.on("data", (c) => chunks.push(c))
        response.on("end", () => {
          try { res(JSON.parse(Buffer.concat(chunks).toString())) }
          catch { res(null) }
        })
      })
      req.on("error", () => res(null))
      req.on("timeout", () => { req.destroy(); res(null) })
      if (payload) req.write(payload)
      req.end()
    })

    // Try Unix socket first
    const socketOpts = { socketPath: SOCKET_PATH, path: pathname, method, headers, timeout: timeoutMs }
    tryRequest(socketOpts).then((result) => {
      if (result !== null && !result?.error) {
        resolve(result)
        return
      }
      // Fall back to TCP
      const tcpOpts = { hostname: TCP_BASE_HOST, port: TCP_BASE_PORT, path: pathname, method, headers, timeout: timeoutMs }
      tryRequest(tcpOpts).then(resolve)
    })
  })
}

function sendAsync(method, pathname, body, timeoutMs = SHORT_TIMEOUT) {
  send(method, pathname, body, timeoutMs).catch(() => {})
}

// ── Bridge primitives (fire-and-forget, async-safe) ──────────────────────────

function ingest(sessionId, events) {
  const now = Date.now()
  sendAsync("POST", "/events/ingest", {
    sessionId,
    events: events.map((event) => ({ timestamp: now, source: SOURCE, sessionId, ...event })),
  })
}

function cortexSignal(sessionId, type, region, content, tags, salience) {
  sendAsync("POST", "/cortex/signal", {
    sessionId, type, region, content, tags, salience, author: SOURCE,
  })
}

function memoryStoreEpisode(sessionId, content, tags, type) {
  if (!content) return
  sendAsync("POST", "/memory/store", {
    type,
    content,
    sessionId,
    metadata: { sessionId, source: SOURCE, tags },
  })
}

function kvSet(key, value) {
  sendAsync("POST", "/memory/kv", { key, value })
}

function reveriePing(sessionId, reason) {
  sendAsync("POST", "/intelligence/reverie/ping", { sessionId, reason })
}

function indexMessages(sessionId, messages) {
  sendAsync("POST", "/context/index", { sessionId, messages })
}

function workspaceEnrich(query, sessionId) {
  sendAsync("POST", "/intelligence/workspace/enrich", { query, sessionId })
}

function auroraObserve(text) {
  sendAsync("POST", "/intelligence/aurora/observe", { text }, MEDIUM_TIMEOUT)
}

function emitTurnStart(sessionId, message) {
  sendAsync("POST", "/events/ingest", {
    sessionId,
    events: [{
      type: "turn:start",
      sessionId,
      message,
      source: SOURCE,
      timestamp: Date.now(),
    }],
  })
}

function emitTurnEnd(sessionId, response, durationMs) {
  sendAsync("POST", "/events/ingest", {
    sessionId,
    events: [{
      type: "turn:end",
      sessionId,
      response,
      durationMs,
      source: SOURCE,
      timestamp: Date.now(),
    }],
  })
}

function emitToolRound(sessionId, round, calls, results) {
  sendAsync("POST", "/events/ingest", {
    sessionId,
    events: [{
      type: "tool:round-complete",
      sessionId,
      round,
      calls,
      results,
      source: SOURCE,
      timestamp: Date.now(),
    }],
  })
}

function helixJournalAppend(sessionId, event, payload, agentId) {
  sendAsync("POST", "/helix/journal/append", {
    sessionId,
    event,
    payload,
    agentId,
    source: SOURCE,
  })
}

// ── Lamina (CAS-edited persistent working memory) ────────────────────────────

async function ensureLamina(sessionId, label) {
  const cacheKey = `${sessionId}:${label}`
  if (laminaEnsureCache.has(cacheKey)) return
  const qs = `label=${encodeURIComponent(label)}&sessionId=${encodeURIComponent(sessionId)}`
  const existing = await send("GET", `/lamina/read?${qs}`)
  if (existing && !existing.error) {
    laminaEnsureCache.add(cacheKey)
    return
  }
  const created = await send("POST", "/lamina/create", {
    label,
    content: "",
    description: `OpenCode session-scoped ${label}`,
    owner: SOURCE,
    scope: { kind: "session", sessionId },
    tags: [SOURCE, "session"],
    charLimit: LAMINA_CHAR_LIMIT,
  })
  if (created && !created.error) laminaEnsureCache.add(cacheKey)
}

async function laminaAppend(sessionId, label, content, reason) {
  await ensureLamina(sessionId, label)
  sendAsync("POST", "/lamina/append", {
    label, sessionId, content,
    separator: "\n",
    agentId: SOURCE,
    reason,
  })
}

async function laminaRethink(sessionId, label, content, reason) {
  await ensureLamina(sessionId, label)
  sendAsync("POST", "/lamina/rethink", {
    label, sessionId, content,
    agentId: SOURCE,
    reason,
  })
}

// ──────────────────────────────────────────────────────────────────────────────
// Helpers
// ──────────────────────────────────────────────────────────────────────────────

function asRecord(value) {
  return value && typeof value === "object" && !Array.isArray(value) ? value : {}
}

function asArray(value) {
  return Array.isArray(value) ? value : []
}

function stringifyBrief(value) {
  if (typeof value === "string") return value.slice(0, 4_000)
  try { return JSON.stringify(value).slice(0, 4_000) }
  catch { return String(value).slice(0, 4_000) }
}

function extractText(parts) {
  if (!Array.isArray(parts)) return ""
  return parts.map(partToText).filter(Boolean).join("\n").trim()
}

function partToText(part) {
  if (!part || typeof part !== "object") return ""
  if (typeof part.text === "string") return part.text
  if (typeof part.content === "string") return part.content
  if (part.type === "text" && typeof part.value === "string") return part.value
  return ""
}

function isAssistantCompleted(info, eventType) {
  const role = info.role
  if (role !== "assistant") return false
  return eventType === "message.completed" || Boolean(asRecord(info.time).completed)
}

function sessionIdFrom(info) {
  const record = asRecord(info)
  return typeof record.sessionID === "string" ? record.sessionID
    : typeof record.sessionId === "string" ? record.sessionId
    : undefined
}

function sessionIdFromMessages(messages) {
  for (let i = messages.length - 1; i >= 0; i--) {
    const msg = messages[i]
    const fromInfo = sessionIdFrom(msg?.info)
    if (fromInfo) return fromInfo
    if (Array.isArray(msg?.parts)) {
      for (const part of msg.parts) {
        if (typeof part?.sessionID === "string") return part.sessionID
        if (typeof part?.sessionId === "string") return part.sessionId
      }
    }
  }
  return undefined
}
