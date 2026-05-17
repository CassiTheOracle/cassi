import { BaseCognitiveModule } from '../base/cognitive-module.js'
import { createHash } from 'node:crypto'
import { MessageLuminanceScorer, extractTerms, extractFilePaths, extractMessageContent, cleanEngramContent } from './scorer.js'
import { ToolResultCompressor } from './compressor.js'
import { ToolResultDistiller } from './distiller.js'
import { TemporalRegistry } from './temporal.js'
import { createSlots } from './slots/index.js'
import { classifyMessage, isWriteTool, isReadTool, isShellTool, isSearchTool, extractFilePath, extractSearchTarget, extractCommand, isTestCommand, isBuildCommand, shortenPath, classifyTool, extractToolUses, extractToolResults, detectLanguage } from './classifier.js'
import type { ThalamusStore } from './thalamus-store.js'
import type { ILogger } from '../../../types/interfaces.js'
import type { CorticalField } from '../cortex/index.js'
import type { MnemicField } from '../mnemic-field/index.js'
import type { EngramCreate, ExpertKind, MnemicRetrievalHit } from '../mnemic-field/types.js'
import { cosineSimilarity } from '../mnemic-field/cortex.js'
import { SIGNAL_TYPE_PHRASES, EPISTEMIC_SHIFT_PHRASES, WORK_UNIT_ANNOTATION_PHRASES } from '../phrase-prototypes.js'
import type { SelfModelField } from '../mnemic-field/self-model/self-model-field.js'
import type { LocusBridge } from '../locus-bridge/index.js'
import type { FacetManager } from '../pineal/facet.js'
import type { PinealAssembler } from '../pineal/assembler.js'
import type { Aurora } from '../aurora/index.js'
import type {
  CurationConfig,
  CurationResult,
  CurationSession,
  BrainContext,
  ScoredMessage,
  CortexIndex,
  WeightedSignal,
  SelfModelHit,
  MessageSlot,
  SlotContext,
  ThalamusAnnotation,
  MessageSlotType,
  TopicCluster,
  TopicArchiveStructured,
  DropRecord,
  PinnedPattern,
  ThoughtCommand,
  ContextMapRow,
  ContextMapSnapshot,
  IntentSpan,
} from './types.js'
import { DEFAULT_CURATION_CONFIG, SIGNAL_TYPE_WEIGHTS, REGION_WEIGHTS, DEFAULT_SLOT_BUDGETS, parseThoughtCommands } from './types.js'
import { buildDropReceipt, type DropReceipt } from './drop-receipt.js'
import { hasQuestionResult, buildToolUseMapFromMessages } from '../../pipeline/turn/overflow.js'

/**
 * Deep clone a message to prevent in-place mutations from leaking
 * to the caller (critical for Anthropic thinking signatures).
 */
function deepCloneMessage(msg: any): any {
  if (!msg || typeof msg !== 'object') return msg
  const cloned: any = { ...msg }
  if (Array.isArray(msg.content)) {
    cloned.content = msg.content.map((block: any) => {
      if (!block || typeof block !== 'object') return block
      const blockClone = { ...block }
      // Deep clone nested content (for tool_result with array content)
      if (Array.isArray(block.content)) {
        blockClone.content = block.content.map((b: any) =>
          b && typeof b === 'object' ? { ...b } : b,
        )
      }
      return blockClone
    })
  }
  return cloned
}

/**
 * Validate assembled messages before returning to the caller.
 * 
 * FATAL checks (trigger fallback):
 * - Corrupted thinking signatures (our #1 bug)
 * - Duplicate tool_use IDs (API error)
 * - Truly orphan tool_use with no matching tool_result anywhere
 * 
 * WARNING checks (logged but don't trigger fallback):
 * - Consecutive same-role messages (ensureAlternation may not catch all)
 * - Orphan tool_result when tool_use exists (sanitizeToolPairs handles this)
 */
function validateMessages(messages: any[]): { valid: boolean; errors: string[]; fatal: boolean } {
  const errors: string[] = []
  let fatal = false

  // 0. First message MUST be user (Anthropic API requirement)
  if (messages.length > 0 && messages[0].role !== 'user') {
    errors.push(`First message is ${messages[0].role}, must be user`)
    fatal = true
  }

  // 1. Tool pairs — check for TRULY orphan tool_use (no matching tool_result anywhere)
  const toolUseIds = new Set<string>()
  const toolResultIds = new Set<string>()
  for (const msg of messages) {
    if (!Array.isArray(msg?.content)) continue
    for (const block of msg.content) {
      if (block?.type === 'tool_use' && block.id) toolUseIds.add(block.id)
      if (block?.type === 'tool_result' && block.tool_use_id) toolResultIds.add(block.tool_use_id)
    }
  }
  for (const id of toolUseIds) {
    if (!toolResultIds.has(id)) {
      errors.push(`Orphan tool_use: ${id}`)
      fatal = true
    }
  }

  // 2. No duplicate tool_use IDs
  const seenIds = new Set<string>()
  for (const msg of messages) {
    if (!Array.isArray(msg?.content)) continue
    for (const block of msg.content) {
      if (block?.type === 'tool_use' && block.id) {
        if (seenIds.has(block.id)) {
          errors.push(`Duplicate tool_use: ${block.id}`)
          fatal = true
        }
        seenIds.add(block.id)
      }
    }
  }

  // 3. Assistant thinking blocks are intact — THIS IS THE CRITICAL CHECK
  for (let i = 0; i < messages.length; i++) {
    const msg = messages[i]
    if (msg?.role !== 'assistant' || !Array.isArray(msg.content)) continue
    for (const block of msg.content) {
      if (block?.type === 'thinking') {
        if (!block.signature || typeof block.thinking !== 'string') {
          errors.push(`Corrupted thinking block at msg ${i}: signature=${JSON.stringify(block.signature)} thinking_type=${typeof block.thinking}`)
          fatal = true
        }
      }
    }
  }

  // 4. Strict alternation — WARNING only (don't trigger fallback)
  for (let i = 1; i < messages.length; i++) {
    if (messages[i].role === messages[i - 1].role) {
      errors.push(`Consecutive ${messages[i].role} at ${i - 1},${i}`)
    }
  }

  return { valid: errors.length === 0, errors, fatal }
}

/**
 * Sanitize tool pairs: deduplicate tool_use IDs, strip orphan tool_uses,
 * convert orphan tool_results to text, and merge consecutive same-role
 * messages (except assistant — preserves thinking signatures).
 *
 * Run this AFTER assembly but BEFORE returning to the caller.
 */
export function sanitizeToolPairs(messages: any[]): any[] {
  if (!Array.isArray(messages) || messages.length === 0) return messages

  // Pre-scan: find all tool_use and tool_result IDs across the entire array.
  // After curation, tool pairs may not be adjacent, so adjacency checks alone
  // are insufficient.
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

/** A function that acquires a model handle for background LLM calls. */
type HandleFactory = (config: { tier: string; purpose: string; sessionId: string }) => Promise<{
  complete(messages: Array<{ role: string; content: string }>, opts: Record<string, unknown>): Promise<{ response: string }>
  release(): void
  model: string
}>

const SESSION_EVICT_MS = 2 * 60 * 60 * 1000
const MAX_DROP_HISTORY = 200

/** Format a duration in ms to a human-readable string for gap notes. */
function formatGapDuration(ms: number): string {
  if (ms < 1000) return `${ms}ms`
  if (ms < 60_000) return `${(ms / 1000).toFixed(0)}s`
  const minutes = Math.floor(ms / 60_000)
  const seconds = Math.floor((ms % 60_000) / 1000)
  if (seconds === 0) return `${minutes}m`
  return `${minutes}m${seconds}s`
}

/** Escape `<`, `>`, and `&` so structured archive content can't break the wrapping XML block. */
function escapeXml(s: string): string {
  return s.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
}

const INLINE_MARKER_RE = /^\[#\d+ \d{2}:\d{2}:\d{2}[^\]]*\]\n/

function formatBytes(n: number): string {
  if (n < 1000) return `${n}`
  if (n < 10000) return `${(n / 1000).toFixed(1)}k`
  return `${Math.round(n / 1000)}k`
}

function formatTimeOfDay(iso: string | undefined): string {
  if (!iso) return '?'
  const d = new Date(iso)
  if (isNaN(d.getTime())) return '?'
  return d.toISOString().slice(11, 19)
}

function shortReason(reason: string | undefined, max = 20): string {
  if (!reason) return ''
  let s = reason
  if (s.includes('/')) {
    const base = s.split('/').pop() ?? s
    if (base.length <= max) return base
    s = base
  }
  if (s.length <= max) return s
  return s.slice(0, max - 1) + '…'
}

function buildInlineMarker(msg: any, index: number): string | null {
  const ann = msg?._thalamus
  if (!ann) return null
  const t = formatTimeOfDay(ann.ts)
  const chars = formatBytes(ann.chars ?? 0)
  let tag = ''
  if (ann.protectedBy === 'pin') {
    const priorityTag = ann.pinPriority === 'critical' ? '!' : ann.pinPriority === 'high' ? '+' : ''
    tag = ` pin${priorityTag}:${shortReason(ann.protectedReason ?? ann.pinReason, 15)}`
  }
  else if (ann.protectedBy === 'recent-window') tag = ' recent'
  else if (ann.protectedBy === 'live-read') tag = ` live:${shortReason(ann.protectedReason, 20)}`
  else if (ann.protectedBy === 'system') tag = ' system'
  else if (ann.protectedBy === 'slot-budget') tag = ' slot'
  return `[#${index} ${t}${tag} ${chars}]`
}

/**
 * Prepend a compact metadata marker to each message's first text block so Cassi
 * can see protection state, timestamp, and char count in the message stream itself.
 * Format: `[#idx HH:MM:SS [tag] chars]\n` — stable across turns for cache stability.
 */
function attachInlineMarkers(messages: any[]): any[] {
  return messages.map((msg, i) => {
    // Assistant messages carry thinking signatures bound to block structure.
    // Mutating their content blocks invalidates signatures → Anthropic 400.
    if (msg?.role === 'assistant') return msg
    const ann = msg?._thalamus
    const stableIdx = (ann && typeof ann.index === 'number') ? ann.index : i
    const marker = buildInlineMarker(msg, stableIdx)
    if (!marker) return msg
    if (typeof msg.content === 'string') {
      const stripped = msg.content.replace(INLINE_MARKER_RE, '')
      return { ...msg, content: `${marker}\n${stripped}` }
    }
    if (Array.isArray(msg.content)) {
      const newContent = msg.content.slice()
      const idx = newContent.findIndex((b: any) => b?.type === 'text' && typeof b.text === 'string')
      if (idx >= 0) {
        const existing = newContent[idx].text as string
        const stripped = existing.replace(INLINE_MARKER_RE, '')
        newContent[idx] = { ...newContent[idx], text: `${marker}\n${stripped}` }
      } else {
        // Insert after any thinking/redacted_thinking blocks — Anthropic
        // requires thinking blocks to precede all other content types.
        let insertAt = 0
        for (let k = 0; k < newContent.length; k++) {
          if (newContent[k]?.type === 'thinking' || newContent[k]?.type === 'redacted_thinking') {
            insertAt = k + 1
          } else {
            break
          }
        }
        newContent.splice(insertAt, 0, { type: 'text', text: marker })
      }
      return { ...msg, content: newContent }
    }
    return msg
  })
}

/**
 * Strip _thalamus annotations from messages before they leave CassiCore.
 * The Anthropic API (and other providers) reject extra fields on message objects
 * with "Extra inputs are not permitted". _thalamus is CassiCore-internal metadata.
 */
function stripThalamusAnnotations(messages: any[]): any[] {
  return messages.map(msg => {
    if (!msg || typeof msg !== 'object') return msg
    const { _thalamus, ...rest } = msg
    return rest
  })
}

/**
 * Compute a minimal line-based diff between two strings.
 * Returns a compact, unified-diff-like string suitable for storing in
 * file_version engrams. Uses common-prefix/suffix matching — simpler
 * than full Myers diff but captures the most common case (localized edits).
 *
 * Format: `@@ -oldStart,oldCount +newStart,newCount @@` followed by
 * context lines (leading space), removed lines (`-`), and added lines (`+`).
 *
 * First version of a file stores full content; subsequent versions store
 * a diff against the first version's content so any version can be
 * reconstructed by applying one diff (no chained diffs-on-diffs).
 */
export function computeLineDiff(oldContent: string, newContent: string): string {
  if (!oldContent) return newContent
  
  const oldLines = oldContent.split('\n')
  const newLines = newContent.split('\n')
  
  // Simple common-prefix / common-suffix diff
  let prefix = 0
  while (prefix < oldLines.length && prefix < newLines.length && oldLines[prefix] === newLines[prefix]) {
    prefix++
  }
  
  let oldSuffix = oldLines.length - 1
  let newSuffix = newLines.length - 1
  while (oldSuffix >= prefix && newSuffix >= prefix && oldLines[oldSuffix] === newLines[newSuffix]) {
    oldSuffix--
    newSuffix--
  }
  
  const parts: string[] = []
  const contextStart = Math.max(0, prefix - 2)
  const contextEnd = Math.min(oldLines.length, oldSuffix + 3)
  
  // Range header
  parts.push(`@@ -${contextStart + 1},${oldSuffix - prefix + 1} +${contextStart + 1},${newSuffix - prefix + 1} @@`)
  
  // Context lines before change
  for (let i = contextStart; i < prefix; i++) {
    parts.push(` ${oldLines[i]}`)
  }
  
  // Removed lines
  for (let i = prefix; i <= oldSuffix; i++) {
    parts.push(`-${oldLines[i]}`)
  }
  
  // Added lines
  for (let i = prefix; i <= newSuffix; i++) {
    parts.push(`+${newLines[i]}`)
  }
  
  // Context lines after change
  for (let i = oldSuffix + 1; i < contextEnd; i++) {
    parts.push(` ${oldLines[i]}`)
  }
  
  return parts.join('\n')
}

/**
 * Create a synapse, silently ignoring failures.
 * Best-effort utility — never crash for synapse wiring.
 * Extracted from ThalamusModule so other modules (e.g. DMN, Locus Bridge)
 * with a MnemicField reference can wire best-effort synapses.
 */
export function safeConnect(
  mnemicField: import('../mnemic-field/index.js').MnemicField | null,
  sourceId: string,
  targetId: string,
  edgeType: string,
): void {
  if (!mnemicField || !sourceId || !targetId) return
  try {
    mnemicField.connect({ sourceId, targetId, edgeType: edgeType as any, weight: 0.8 })
  } catch { /* best-effort */ }
}

export class ThalamusModule extends BaseCognitiveModule {
  readonly name = 'thalamus'
  readonly priority = 85

  private scorer!: MessageLuminanceScorer
  private compressor!: ToolResultCompressor
  private distiller!: ToolResultDistiller
  private sessions = new Map<string, CurationSession>()
  private evictionTimer: ReturnType<typeof setInterval> | null = null

  /** GWT-style processing slots — one per message type */
  private slots!: MessageSlot[]
  /** Per-session temporal registries */
  private temporalRegistries = new Map<string, TemporalRegistry>()
  /**
   * Per-turn brain context cache — keyed by sessionId AND message count so
   * the cache misses as soon as new messages arrive. Without the messageCount
   * portion, a previous turn's cached context (e.g. from a buildDialecticContext
   * admin-API call that never invokes curate) bleeds into the next turn's
   * assembleInjections call.
   */
  private cachedBrainContext: { sessionId: string; messageCount: number; ctx: BrainContext } | null = null

  /** In-memory cache: filePath → file engram ID */
  private fileEngramCache = new Map<string, string>()
  /** Max entries before FIFO eviction */
  private fileEngramCacheMax = 5000

  private locusBridge: LocusBridge | null = null
  private cortex: CorticalField | null = null
  private mnemicField: MnemicField | null = null
  private selfModelField: SelfModelField | null = null
  private pinealFacets: FacetManager | null = null
  private aurora: Aurora | null = null
  private pinealAssembler: PinealAssembler | null = null
  private lastPinealFacetIds: string[] = []
  /** Factory for background LLM calls (topic archiving, gap summaries) */
  private handleFactory: HandleFactory | null = null
  /** Persistent store for curation audit data (drop history, pass metadata) */
  private store: ThalamusStore | null = null
  /** Sink for <note for="..."> thought-commands. Set by the daemon to route notes to Reverie. */
  private reverieNoteSink: ((sessionId: string, recipient: string, message: string) => void) | null = null

  setStore(store: ThalamusStore): void { this.store = store }
  setLocusBridge(lb: LocusBridge): void { this.locusBridge = lb }
  setCortex(c: CorticalField): void { this.cortex = c }
  setMnemicField(mf: MnemicField): void { this.mnemicField = mf }
  setSelfModelField(smf: SelfModelField): void { this.selfModelField = smf }
  setPinealFacets(fm: FacetManager): void { this.pinealFacets = fm }
  setAurora(a: Aurora): void { this.aurora = a }
  setPinealAssembler(pa: PinealAssembler): void { this.pinealAssembler = pa }
  setHandleFactory(fn: HandleFactory): void { this.handleFactory = fn }
  setReverieNoteSink(fn: (sessionId: string, recipient: string, message: string) => void): void { this.reverieNoteSink = fn }

  /** Wire a Reverie inference provider into Aurora for the reasoning slow path. */
  setReverieInferenceProvider(provider: import('../aurora/types.js').ReverieInferenceProvider): void {
this.aurora?.setReverieInferenceProvider(provider)
  }

  /** Expert cluster thresholds — messages before summary regenerates */
  private expertRegenThreshold = 10
  /** Replay buffers per session — map of sessionId → buffer of turn data */
  private replayBuffers = new Map<string, any[]>()
  /** Replay flush size — flush to MnemicField when buffer exceeds this */
  private replayFlushSize = 20
  /** Tracks engram IDs by session → messageIndex for the worthiness post-filter */
  private _engramIdByIndex = new Map<string, Map<number, string>>()

  writeMessageEngram(
    sessionId: string,
    msg: any,
    index: number,
    slotType: string,
    options?: { expertId?: string; intentSpanId?: string; thoughtCommands?: any[]; provenance?: string },
  ): void {
    if (!this.mnemicField) return

    const session = this.getSession(sessionId)
    // Use the original message timestamp when available, falling back to now
    // during back-imports where msg.timestamp may be absent.
    const msgCreatedAt = msg?.timestamp
      ? new Date(msg.timestamp).toISOString()
      : new Date().toISOString()

    // Use the caller-supplied provenance, falling back to 'thalamus'.
    const provenance = options?.provenance ?? 'thalamus'

    // Buffer tool_use blocks and store them as `tool` engrams.
    // Text content in the same message is stored as `message` engrams.
    // tool_invocation engrams are created when the tool_result arrives.
    if (slotType === 'tool_call') {
      if (Array.isArray(msg.content)) {
        for (const block of msg.content) {
          if (block?.type === 'tool_use' && block.id && block.name) {
            // Buffer for later pairing with tool_result
            session.pendingToolCalls.set(block.id, {
              toolName: block.name,
              toolClass: classifyTool(block.name),
              input: block.input ?? {},
              messageIndex: index,
              timestamp: msgCreatedAt,
            })
            session.toolUseMap.set(block.id, block.name)

            // Store as a `tool` engram
            const toolInput: EngramCreate & { sessionId: string } = {
              sessionId,
              content: JSON.stringify(block.input ?? {}),
              nodeType: 'tool' as import('../mnemic-field/types.js').EngramType,
              tags: ['tool', `session:${sessionId}`, `tool_name:${block.name}`],
              provenance,
              createdAt: msgCreatedAt,
              metadata: {
                toolName: block.name,
                toolClass: classifyTool(block.name),
                input: block.input ?? {},
                messageIndex: index,
                createdAt: msgCreatedAt,
              },
            }
            this.mnemicField.storeForSession(toolInput)
          } else if (block?.type === 'text' && block.text) {
            // Store text reasoning alongside tool calls
            const textInput: EngramCreate & { sessionId: string } = {
              sessionId,
              content: cleanEngramContent(block.text),
              nodeType: 'message' as import('../mnemic-field/types.js').EngramType,
              tags: ['assistant', `session:${sessionId}`],
              provenance,
              metadata: {
                sessionId,
                messageIndex: index,
                role: 'assistant',
                slotType: 'assistant',
                createdAt: msgCreatedAt,
              },
            }
            this.mnemicField.storeForSession(textInput)
          }
        }
      }
      return
    }

    if (slotType === 'tool_result') {
      const toolResults = extractToolResults(msg)
      for (const tr of toolResults) {
        const pending = session.pendingToolCalls.get(tr.toolUseId)
        if (!pending) continue  // orphaned result (shouldn't happen)

        const toolName = pending.toolName
        const toolClass = pending.toolClass
        const filePath = extractFilePath(pending.input) || null
        const searchTarget = extractSearchTarget(pending.input) || null

        // Determine the appropriate engram type for this tool invocation
        const nodeType = this.classifyToolResultType(toolName, toolClass, tr.isError, pending.input)

        // Build the tool_invocation engram
        const input: EngramCreate & { sessionId: string } = {
          sessionId,
          content: tr.isError ? `[ERROR] ${tr.content}` : tr.content,
          nodeType: nodeType as import('../mnemic-field/types.js').EngramType,
          tags: [nodeType, `tool:${toolName}`, `class:${toolClass}`, `session:${sessionId}`],
          provenance,
          metadata: {
            toolName,
            toolClass,
            input: pending.input,
            durationMs: 0,
            outputBytes: Buffer.byteLength(tr.content, 'utf8'),
            isError: tr.isError,
            sessionId,
            messageIndex: pending.messageIndex,
            filePath,
            searchTarget,
            createdAt: msgCreatedAt,
          } satisfies Record<string, unknown>,
        }
        this.mnemicField.storeForSession(input)

        // Track for worthiness post-filter
        let sessionMap = this._engramIdByIndex.get(sessionId)
        if (!sessionMap) {
          sessionMap = new Map()
          this._engramIdByIndex.set(sessionId, sessionMap)
        }
        sessionMap.set(pending.messageIndex, input.id ?? '')

        // Route file operations to the file-engram interceptor
        if (filePath && !tr.isError && (toolClass === 'fs' || isReadTool(toolName) || isWriteTool(toolName))) {
          const resultContent = tr.isError ? '' : tr.content
          const tiId = input.id ?? ''
          this.writeFileEngramsForTool(sessionId, toolName, toolClass, filePath, resultContent, msgCreatedAt, provenance, tiId)
        }

        session.pendingToolCalls.delete(tr.toolUseId)
      }
      return
    }

    // user, assistant, system — store as message engrams
    const content = extractMessageContent(msg)
    if (!content) return
    const input: EngramCreate & { sessionId: string } = {
      sessionId,
      content: cleanEngramContent(typeof content === 'string' ? content : JSON.stringify(content)),
      nodeType: 'message' as import('../mnemic-field/types.js').EngramType,
      tags: [slotType, `session:${sessionId}`],
      provenance,
      metadata: {
        sessionId,
        messageIndex: index,
        role: slotType,
        slotType,
        intentSpanId: options?.intentSpanId,
        expertId: options?.expertId,
        thoughtCommands: options?.thoughtCommands,
        createdAt: msgCreatedAt,
      },
    }
    const engram = this.mnemicField.storeForSession(input)

    // Track engram ID by session + messageIndex for the async worthiness post-filter
    let sessionMap2 = this._engramIdByIndex.get(sessionId)
    if (!sessionMap2) {
      sessionMap2 = new Map()
      this._engramIdByIndex.set(sessionId, sessionMap2)
    }
    sessionMap2.set(index, engram.id)
  }

  /**
   * Classify a tool_result into a specific engram type based on tool metadata
   * and result status. Priority: isError → search → shell(test/build) → write → default.
   */
  private classifyToolResultType(
    toolName: string,
    toolClass: string,
    isError: boolean,
    input: Record<string, unknown>,
  ): string {
    // 1. Errors always get error_report
    if (isError) return 'error_report'

    // 2. Search tools get search_finding
    if (toolClass === 'web' || isSearchTool(toolName)) return 'search_finding'

    // 3. Shell tools: distinguish test vs build from the command string
    if (toolClass === 'shell' || isShellTool(toolName)) {
      const command = extractCommand(input)
      if (isTestCommand(command)) return 'test_result'
      if (isBuildCommand(command)) return 'build_output'
    }

    // 4. Write/edit tools get code_change
    if (isWriteTool(toolName)) return 'code_change'

    // 5. Default: generic tool_invocation
    return 'tool_invocation'
  }

  /**
   * Create file, file_version, and file_read engrams for file-related tool invocations.
   * Called from writeMessageEngram after a tool_invocation is stored.
   */
  private writeFileEngramsForTool(
    sessionId: string,
    toolName: string,
    toolClass: string,
    filePath: string,
    content: string,
    now: string,
    provenance: string,
    toolInvocationId: string,
  ): void {
    if (!filePath) return

    try {
      const mf = this.mnemicField!  // guarded by findOrCreateFileEngram below
      const checksum = createHash('sha256').update(content, 'utf8').digest('hex')
      const language = detectLanguage(filePath)

      if (isReadTool(toolName) || toolName === 'read' || toolName === 'cassi_read') {
        // Read: create file_read engram, create/update file engram
        const fileEngram = this.findOrCreateFileEngram(sessionId, filePath, content, language, checksum, now, provenance)
        const existingMeta = (fileEngram.metadata ?? {}) as Record<string, unknown>
        const readCount = ((existingMeta.readCount as number) ?? 0) + 1
        mf.update(fileEngram.id, {
          accessedAt: now,
          metadata: {
            ...existingMeta,
            readCount,
            lastReadAt: now,
            sizeBytes: Buffer.byteLength(content, 'utf8'),
          },
        })

        // Create file_read engram
        const readEngram = mf.storeForSession({
          sessionId,
          content: '',
          nodeType: 'file_read' as import('../mnemic-field/types.js').EngramType,
          tags: ['file_read', `session:${sessionId}`, `file:${filePath}`],
          provenance,
          metadata: {
            filePath,
            sessionId,
            timestamp: now,
            readCount,
            toolInvocationId,
          } satisfies Record<string, unknown>,
        } as any)

        // Wire part_of: file_read → file
        safeConnect(mf, readEngram.id, fileEngram.id, 'part_of')
        // Wire operated_on: tool_invocation → file
        if (toolInvocationId) {
          safeConnect(mf, toolInvocationId, fileEngram.id, 'operated_on')
        }
      } else if (isWriteTool(toolName) || toolName === 'write' || toolName === 'edit' || toolName === 'cassi_write' || toolName === 'cassi_edit') {
        const fileEngram = this.findOrCreateFileEngram(sessionId, filePath, content, language, checksum, now, provenance)
        const existingMeta = (fileEngram.metadata ?? {}) as Record<string, unknown>
        const existingChecksum = existingMeta.currentChecksum as string | undefined
        const versionCount = ((existingMeta.versionCount as number) ?? 0)

        if (checksum !== existingChecksum) {
          const newVersionIndex = versionCount + 1

          // For versions beyond the first, compute a line-based diff
          // against v1's full content so every version can be reconstructed
          // by applying one diff (no chained diffs-on-diffs).
          let versionContent: string
          let diffFromBaseVersionId: string | null = null
          let supersedesId: string | null = null
          if (newVersionIndex > 1) {
            const allVersions = this.getFileVersionsByPath(filePath)
            // v1 is the first entry (oldest, sorted by t ASC), but verify
            // by checking versionIndex metadata in case of manual inserts
            // or migration artifacts that may not follow strict t-ordering.
            const firstVersion = allVersions.find(v => {
              const meta = v.metadata as Record<string, unknown> | undefined
              return meta?.versionIndex === 1 || meta?.isDiff === false
            }) ?? allVersions[0]
            if (firstVersion && firstVersion.content) {
              diffFromBaseVersionId = firstVersion.id
              versionContent = computeLineDiff(firstVersion.content, content)
            } else {
              versionContent = content
            }
            // Find the immediately previous version (vN-1) for the supersedes chain.
            // With versionIndex metadata, we look for version N-1; as a fallback
            // on unversioned records, the last array entry (most recent existing) is vN-1.
            let prevVersion: import('../mnemic-field/types.js').Engram | undefined
            for (const v of allVersions) {
              const meta = v.metadata as Record<string, unknown> | undefined
              if (meta?.versionIndex === newVersionIndex - 1) {
                prevVersion = v
                break
              }
            }
            if (!prevVersion && allVersions.length > 1) {
              prevVersion = allVersions[allVersions.length - 1]
            }
            if (prevVersion) {
              supersedesId = prevVersion.id
            } else {
              this.logger?.debug('File version chain degraded — no previous version found', {
                filePath,
                newVersionIndex,
                existingCount: allVersions.length,
              })
            }
          } else {
            versionContent = content
          }

          const versionEngram = mf.storeForSession({
            sessionId,
            content: versionContent,
            nodeType: 'file_version' as import('../mnemic-field/types.js').EngramType,
            tags: ['file_version', `file:${filePath}`, `session:${sessionId}`],
            provenance,
            metadata: {
              filePath,
              checksum,
              sizeBytes: Buffer.byteLength(content, 'utf8'),
              versionIndex: newVersionIndex,
              toolInvocationId,
              supersedesId,
              diffFromBaseVersionId,
              isDiff: newVersionIndex > 1,
            } satisfies Record<string, unknown>,
          } as any)

          safeConnect(mf, versionEngram.id, fileEngram.id, 'part_of')
          if (toolInvocationId) {
            safeConnect(mf, toolInvocationId, fileEngram.id, 'operated_on')
          }
          if (supersedesId) {
            // Wire supersedes: new version supersedes the immediate previous version
            safeConnect(mf, versionEngram.id, supersedesId, 'supersedes')
          }

          mf.update(fileEngram.id, {
            // Anchor content is truncated — full content lives in file_version
            content: content.slice(0, 500),
            accessedAt: now,
            metadata: {
              ...existingMeta,
              currentChecksum: checksum,
              sizeBytes: Buffer.byteLength(content, 'utf8'),
              versionCount: newVersionIndex,
              lastModifiedAt: now,
            },
          })
        }
      }
    } catch (err) {
      // File engram creation is best-effort — never crash message processing.
      // Log at debug level: file engram failures are expected during DB migrations
      // or when the MnemicField is temporarily unavailable.
      this.logger?.debug('File engram creation failed', {
        error: String(err),
        filePath,
        toolName,
        sessionId: sessionId.slice(-8),
      })
    }
  }

  /**
   * Find all file_version engrams for a given filePath via a single DB query.
   * Returns all versions sorted by creation order. The caller can pick
   * v1 (index 0), vN-1 (penultimate), etc. without repeated scans.
   *
   * Uses the dedicated json_extract(metadata, '$.filePath') query on the
   * MnemicField — no JS filtering over a broad list() call.
   */
  private getFileVersionsByPath(filePath: string): import('../mnemic-field/types.js').Engram[] {
    if (!this.mnemicField) return []
    return this.mnemicField.findFileVersionsByPath(filePath)
  }

  /**
   * Find or create a file engram for the given path.
   * Scans existing engrams by metadata.filePath.
   */
  private findOrCreateFileEngram(
    sessionId: string,
    filePath: string,
    content: string,
    language: string,
    checksum: string,
    now: string,
    provenance: string,
  ): import('../mnemic-field/types.js').Engram {
    if (!this.mnemicField) {
      // Best-effort — file engrams are an optimization, never a critical path.
      // The outer caller (writeFileEngramsForTool) also guards, but we guard
      // here so findOrCreateFileEngram is safe to call from any context.
      throw new Error('MnemicField not set — file engram creation skipped')
    }

    // 1. Check in-memory cache first (fast path)
    const cachedId = this.fileEngramCache.get(filePath)
    if (cachedId) {
      const engram = this.mnemicField.get(cachedId)
      if (engram) return engram
      // engram was deleted — clear cache, fall through to DB query
      this.fileEngramCache.delete(filePath)
    }

    // 2. DB query — fallback for cache misses (cross-session, cold start)
    const existing = this.mnemicField.findFileByPath(filePath)
    if (existing) {
      this.fileEngramCache.set(filePath, existing.id)
      return existing
    }

    // 3. Create new file engram
    const pathSegments = filePath.split('/').filter(Boolean)
    const engram = this.mnemicField.storeForSession({
      sessionId,
      content: content.slice(0, 500),
      nodeType: 'file' as import('../mnemic-field/types.js').EngramType,
      tags: ['file', `file:${filePath}`, language, ...pathSegments.slice(0, -1)],
      provenance,
      metadata: {
        filePath,
        language,
        currentChecksum: checksum,
        sizeBytes: Buffer.byteLength(content, 'utf8'),
        versionCount: 0,
        readCount: 0,
        lastReadAt: null,
        lastModifiedAt: null,
        createdAt: now,
      } satisfies Record<string, unknown>,
    } as any)
    // Evict oldest if at capacity.
    // Map iteration is insertion-order by spec (ES6 §23.1.3.5), so
    // keys().next().value gives the first-inserted entry → FIFO eviction.
    if (this.fileEngramCache.size >= this.fileEngramCacheMax) {
      const firstKey = this.fileEngramCache.keys().next().value
      if (firstKey) this.fileEngramCache.delete(firstKey)
    }
    this.fileEngramCache.set(filePath, engram.id)
    return engram
  }

  /**
   * MemRouter-inspired write-side classification: labels each engram with
   * semanticType, epistemicShift, and workType dimensions via prototype embeddings.
   * Runs during curate() after processAll(). Silently skips if the embedding
   * service is unavailable (engram is stored raw and classified on next pass).
   */
  private async classifyEngram(sessionId: string, annotated: any[]): Promise<void> {
    if (!this.mnemicField) return
    const sessionMap = this._engramIdByIndex.get(sessionId)
    if (!sessionMap || sessionMap.size === 0) return

    let tagged = 0
    for (const msg of annotated) {
      const msgIndex = msg._thalamus?.index
      if (typeof msgIndex !== 'number') continue

      const engramId = sessionMap.get(msgIndex)
      if (!engramId) continue  // Already filtered by Gate 1 (tool role filter)

      const content = extractMessageContent(msg)
      if (!content || content.length < 10) continue

      // Multi-dimensional label classification — inspired by MemRouter's
      // write-side content-type routing (key_facts, preference, plan, etc.).
      // Runs in parallel: one embed, four cosine-similarity lookups.
      try {
        const [sigType, epiShift, workType] = await Promise.all([
          this.mnemicField.classifyPhrase(content, SIGNAL_TYPE_PHRASES, 0.30),
          this.mnemicField.classifyPhrase(content, EPISTEMIC_SHIFT_PHRASES, 0.30),
          this.mnemicField.classifyPhrase(content, WORK_UNIT_ANNOTATION_PHRASES, 0.30),
        ])

        const labels: Record<string, unknown> = {}
        if (sigType.label) labels.semanticType = sigType.label
        if (epiShift.label) labels.epistemicShift = epiShift.label
        if (workType.label) labels.workType = workType.label
        labels.classifiedAt = new Date().toISOString()

        // Merge with existing metadata (preserves sessionId, messageIndex, slotType, etc.)
        const existing = this.mnemicField.get(engramId)
        const mergedMeta = { ...(existing?.metadata ?? {}), ...labels }
        this.mnemicField.update(engramId, { metadata: mergedMeta })
        tagged++
      } catch {
        // Embedding service unavailable — skip classification, keep engram raw
        continue
      }
    }

    if (tagged > 0) {
      this.logger.debug('Engram classification', { sessionId, tagged })
    }
  }

  assignExpertId(embedding: Float32Array | number[] | null): string | null {
    if (!this.mnemicField || !embedding || embedding.length === 0) return null
    const experts = this.mnemicField.findExpertEngrams({ limit: 50 })
    if (experts.length === 0) return null
    let bestId: string | null = null
    let bestScore = 0.3
    for (const expert of experts) {
      const centroid: number[] | undefined = (expert.metadata as any)?.expertCentroid
      if (!centroid || centroid.length === 0) continue
      const score = cosineSimilarity(embedding, centroid)
      if (score > bestScore) {
        bestScore = score
        bestId = (expert.metadata as any)?.expertId ?? expert.id
      }
    }
    return bestId
  }

  updateEngramCuration(sessionId: string, msgIndex: number, curationData: { luminance?: number; isPinned?: boolean; kept?: boolean }): void {
    if (!this.mnemicField) return
    const content = this.mnemicField.getTrace({ sessionIds: [sessionId], limit: 100 })
    const target = content.find(
      e => e.engram.metadata?.messageIndex === msgIndex && e.engram.metadata?.sessionId === sessionId,
    )
    if (!target) return
    const existingMeta = target.engram.metadata ?? {}
    this.mnemicField.update(target.engram.id, {
      metadata: {
        ...existingMeta,
        luminance: curationData.luminance ?? existingMeta.luminance,
        isPinned: curationData.isPinned ?? existingMeta.isPinned ?? false,
        kept: curationData.kept ?? existingMeta.kept ?? true,
      },
    })
  }

  async queryContext(sessionId: string, intent: string, options?: { kind?: ExpertKind }): Promise<any[]> {
    if (!this.mnemicField) return []
    const contextMessages: any[] = []

    try {
      const hits = await this.mnemicField.retrieve(intent, { limit: 5 })
      for (const hit of hits) {
        if (hit.nodeType === 'expert_summary') {
          contextMessages.push({
            role: 'system',
            content: `[Knowledge: ${hit.content.slice(0, 500)}]`,
          })
        }
      }
      if (contextMessages.length === 0) {
        for (const hit of hits.slice(0, 3)) {
          contextMessages.push({
            role: 'system',
            content: `[Related: ${hit.content.slice(0, 300)}]`,
          })
        }
      }
    } catch {
      // Best-effort
    }

    return contextMessages
  }

  captureReplaySegment(sessionId: string, turnData: any): void {
    const buffer = this.replayBuffers.get(sessionId) ?? []
    buffer.push({ ...turnData, capturedAt: new Date().toISOString() })
    this.replayBuffers.set(sessionId, buffer)
    if (buffer.length >= this.replayFlushSize) {
      this.flushReplayBuffer(sessionId)
    }
  }

  flushReplayBuffer(sessionId: string): void {
    if (!this.mnemicField) return
    const buffer = this.replayBuffers.get(sessionId)
    if (!buffer || buffer.length === 0) return
    const content = JSON.stringify(buffer)
    this.mnemicField.store({
      nodeType: 'replay_segment' as import('../mnemic-field/types.js').EngramType,
      content,
      tags: [`session:${sessionId}`],
      provenance: 'thalamus.replay',
      metadata: { sessionId, eventCount: buffer.length, flushedAt: new Date().toISOString() },
    })
    this.replayBuffers.set(sessionId, [])
  }

  writeIntentSpanEngram(sessionId: string, intentSpan: import('./types.js').IntentSpan): void {
    if (!this.mnemicField) return
    this.flushReplayBuffer(sessionId)
    this.mnemicField.store({
      nodeType: 'intent_span' as import('../mnemic-field/types.js').EngramType,
      content: `Intent span ${intentSpan.id} at message ${intentSpan.anchorIndex}`,
      tags: [`session:${sessionId}`, 'intent_span'],
      provenance: 'thalamus',
      metadata: {
        sessionId,
        intentSpanId: intentSpan.id,
        anchorIndex: intentSpan.anchorIndex,
        messageCount: intentSpan.messageIndices.length,
      },
    })
  }

  async init(): Promise<void> {
    await super.init()
    this.scorer = new MessageLuminanceScorer(this.logger)
    this.compressor = new ToolResultCompressor(this.logger)
    this.distiller = new ToolResultDistiller(this.logger)
    this.slots = createSlots()
    this.evictionTimer = setInterval(() => this.evictStaleSessions(), SESSION_EVICT_MS / 2)
  }

  async stop(): Promise<void> {
    if (this.evictionTimer) {
      clearInterval(this.evictionTimer)
      this.evictionTimer = null
    }
    this.sessions.clear()
    this.temporalRegistries.clear()
    this.cachedBrainContext = null
    for (const sid of this.replayBuffers.keys()) {
      this.flushReplayBuffer(sid)
    }
    this.replayBuffers.clear()
    await super.stop()
  }

  /**
   * Process a message in real-time as it arrives. Routes it to the
   * appropriate slot, attaches _thalamus annotation, and records
   * temporal data.
   *
   * Call this when a message enters the conversation — before it's
   * stored in the message history. Returns the augmented message.
   */
  process(
    sessionId: string,
    msg: any,
    index: number,
    toolMetrics?: Map<string, { durationMs: number; outputBytes: number }>,
    provenance?: string,
  ): any {
    const temporal = this.getTemporalRegistry(sessionId)
    const existingTs = temporal.getTimestamp(index)
    const timestamp = existingTs ?? new Date().toISOString()
    const session = this.getSession(sessionId)
    const slotType = classifyMessage(msg, session.toolUseMap)
    const isUser = slotType === 'user'

    if (!existingTs) temporal.recordMessage(index, timestamp, isUser)

    // Record tool metrics if provided (from the executor)
    if (toolMetrics) {
      for (const [id, metrics] of toolMetrics) {
        temporal.recordToolMetrics(id, metrics.durationMs, metrics.outputBytes)
      }
    }

    const ctx: SlotContext = {
      timestamp,
      sessionStart: temporal.sessionStart,
      lastUserMessageAt: temporal.lastUserMessageAt,
      toolMetrics: temporal.getToolMetricsMap(),
      toolUseMap: this.getSession(sessionId).toolUseMap,
      previousMessageTs: index > 0 ? temporal.getTimestamp(index - 1) : null,
    }

    // Route to the matching slot
    const slot = this.slots.find(s => s.matches(msg, ctx))
    let augmented: any
    if (!slot) {
      augmented = {
        ...msg,
        _thalamus: { ts: timestamp, slot: slotType, chars: extractMessageContent(msg).length },
      }
    } else {
      augmented = slot.augment(msg, ctx)
    }
    if (augmented?._thalamus) augmented._thalamus.index = index

    // Write message to Mnemic Field
    if (this.mnemicField) {
      this.writeMessageEngram(sessionId, msg, index, slotType, { provenance })
    }

    return augmented
  }

  /**
   * Process an array of messages that don't yet have _thalamus annotations.
   * Used when curate() receives un-processed messages (backward compatibility).
   */
  processAll(sessionId: string, messages: any[], provenance?: string): any[] {
    const processed = messages.map((msg, i) => {
      if (msg?._thalamus) return msg // already processed
      return this.process(sessionId, msg, i, undefined, provenance)
    })

    // Detect intent spans and pin the most recent ones.
    // Intent spans group a substantive user message + its continuations +
    // assistant context messages. Recent spans are pinned with priority so
    // active instructions survive curation.
    const spans = this.detectIntentSpans(processed)
    const session = this.getSession(sessionId)
    session.intentSpans = spans

    // Pin messages from the last 3 intent spans
    const spansToPin = spans.slice(-3)
    for (const span of spansToPin) {
      for (const idx of span.messageIndices) {
        const msg = processed[idx]
        if (!msg) continue
        if (!msg._thalamus) msg._thalamus = {}
        msg._thalamus.pinned = true

        if (idx === span.anchorIndex) {
          // Substantive user message — high priority
          msg._thalamus.pinPriority = 'high'
          msg._thalamus.pinReason = 'intent-anchor'
        } else if (msg.role === 'assistant' && idx === span.anchorIndex - 1) {
          // Assistant message directly preceding the anchor — high priority
          msg._thalamus.pinPriority = 'high'
          msg._thalamus.pinReason = 'intent-context'
        } else {
          // Continuations or other context — normal priority
          msg._thalamus.pinPriority = 'normal'
          msg._thalamus.pinReason = 'intent-context'
        }
      }
    }

    // Also pin AskUserQuestion answers (existing behavior, now with priority)
    const toolUseMap = buildToolUseMapFromMessages(processed)
    for (const msg of processed) {
      if (hasQuestionResult(msg, { toolUseMap }) && msg?._thalamus && !msg._thalamus.pinned) {
        msg._thalamus.pinned = true
        msg._thalamus.pinPriority = 'high'
        msg._thalamus.pinReason = 'AskUserQuestion answer'
      }
    }

    return processed
  }

  /**
   * Detect intent spans in the message array.
   * An intent span = substantive user message + continuations + assistant context.
   * Walks backwards to group continuations with their substantive anchor.
   */
  private detectIntentSpans(messages: any[]): IntentSpan[] {
    if (!messages || messages.length === 0) return []

    const spans: IntentSpan[] = []
    let currentSpan: { anchorIndex: number; indices: number[] } | null = null

    // Heuristic terms for identifying continuations
    const continuationWords = new Set(['continue', 'go on', 'keep going', 'ok', 'okay', 'yes', 'sure', 'proceed', 'next', 'more'])

    // Walk backwards to build spans
    for (let i = messages.length - 1; i >= 0; i--) {
      const msg = messages[i]
      if (msg?.role !== 'user') continue

      // Skip tool_result messages
      const hasToolResult = Array.isArray(msg.content) && msg.content.some((b: any) => b?.type === 'tool_result')
      if (hasToolResult) continue

      const content = extractMessageContent(msg)
      const terms = extractTerms(content)

      // Check if this is a continuation
      const isContinuation = this.isContinuationMessage(content, terms, messages, i, continuationWords)

      if (isContinuation) {
        // Add to current span if one exists
        if (currentSpan) {
          currentSpan.indices.unshift(i)
        }
      } else {
        // This is a substantive message — start a new span
        if (currentSpan) {
          spans.unshift(this.buildIntentSpan(currentSpan, messages))
        }
        currentSpan = { anchorIndex: i, indices: [i] }
      }
    }

    // Don't forget the last span
    if (currentSpan) {
      spans.unshift(this.buildIntentSpan(currentSpan, messages))
    }

    return spans
  }

  private isContinuationMessage(
    content: string,
    terms: string[],
    messages: any[],
    index: number,
    continuationWords: Set<string>,
  ): boolean {
    const lower = content.toLowerCase()

    // Short messages with ONLY continuation words → continuation
    if (content.length < 15 && content.length > 0) {
      // But not if they contain action verbs (substantive)
      const actionVerbs = /\b(fix|implement|add|create|update|refactor|debug|test|build|design|plan|review|analyze|solve|change|move|extract|merge|split|optimize|clean|document|deploy|configure|integrate|migrate|upgrade|downgrade|patch|release|launch|setup|install|uninstall|enable|disable|rename|delete|remove|replace|convert|transform|generate|compute|calculate|validate|verify|check|audit|monitor|track|search|find|locate|identify|detect|discover|explore|investigate|research|study|compare|contrast|measure|assess|evaluate|rate|score|rank|classify|categorize|organize|structure|arrange|format|parse|serialize|deserialize|encode|decode|encrypt|decrypt|compress|decompress|upload|download|import|export|sync|backup|restore|revert|reset|refresh|reload|restart|reboot|shutdown|startup|initialize|finalize|cleanup|destroy|terminate|kill|abort|cancel|retry|resume|pause|suspend|continue|proceed|advance|progress|step|stage|phase|cycle|iteration|loop|recursion|batch|job|task|workflow|pipeline|chain|sequence|series|parallel|concurrent|synchronized|asynchronous|synchronous|real-time|live|interactive|batch|offline|online|remote|local|internal|external|public|private|secure|insecure|trusted|untrusted|safe|unsafe|stable|unstable|volatile|persistent|transient|temporary|permanent|static|dynamic|active|inactive|enabled|disabled|available|unavailable|ready|not-ready|waiting|pending|runn|ing|complete|completed|done|finished|incomplete|partial|full|empty|null|undefined|zero|one|two|three|four|five|six|seven|eight|nine|ten)\b/
      if (!actionVerbs.test(lower)) return true
    }

    // Check for explicit continuation words that STAND ALONE (not embedded in substantive text)
    // e.g. "ok" or "continue" but not "confirmation" or "continuing"
    const standaloneContinuation = /\b(continue|go on|keep going|ok|okay|yes|sure|proceed|next|more)\b/
    const matches = lower.match(standaloneContinuation)
    if (matches && matches.length === 1 && content.length < 30) return true

    // Check similarity to previous user message (within 3 messages)
    let prevUserMsg: any = null
    for (let j = index - 1; j >= Math.max(0, index - 3); j--) {
      if (messages[j]?.role === 'user') {
        prevUserMsg = messages[j]
        break
      }
    }

    if (prevUserMsg) {
      const prevContent = extractMessageContent(prevUserMsg)
      const prevTerms = extractTerms(prevContent)
      const similarity = this.jaccardSimilarity(new Set(terms), new Set(prevTerms))
      // Only mark as continuation if very high similarity AND short
      if (similarity > 0.85 && content.length < 30) return true
    }

    return false
  }

  private jaccardSimilarity(a: Set<string>, b: Set<string>): number {
    if (a.size === 0 && b.size === 0) return 1.0
    const intersection = new Set([...a].filter(x => b.has(x)))
    const union = new Set([...a, ...b])
    return intersection.size / union.size
  }

  private buildIntentSpan(
    span: { anchorIndex: number; indices: number[] },
    messages: any[],
  ): IntentSpan {
    const indices = [...span.indices]
    let minIdx = span.anchorIndex
    let maxIdx = span.anchorIndex

    // Find min/max efficiently (no spread)
    for (const idx of span.indices) {
      if (idx < minIdx) minIdx = idx
      if (idx > maxIdx) maxIdx = idx
    }

    // Include assistant messages that are DIRECTLY ADJACENT to user messages
    // in the span. Don't pull in unrelated assistants from gaps.
    for (const userIdx of span.indices) {
      // Assistant before this user message
      const before = userIdx - 1
      if (before >= minIdx && messages[before]?.role === 'assistant' && !indices.includes(before)) {
        indices.push(before)
      }
      // Assistant after this user message
      const after = userIdx + 1
      if (after <= maxIdx && messages[after]?.role === 'assistant' && !indices.includes(after)) {
        indices.push(after)
      }
    }

    indices.sort((a, b) => a - b)

    return {
      id: `intent-${span.anchorIndex}`,
      messageIndices: indices,
      anchorIndex: span.anchorIndex,
      createdAt: Date.now(),
    }
  }

  /**
   * Get the slot instance for a given message type.
   * Useful for external callers that need type-specific rendering.
   */
  getSlot(type: MessageSlotType): MessageSlot | undefined {
    return this.slots.find(s => s.type === type)
  }

  /**
   * Extract and route thought-commands from assistant messages.
   * Commands: <pin>, <recall>, <note>, <flag> — parsed from message content.
   * Runs during curate(), after processAll and AQ pinning, before compression.
   */
  /**
   * Process thought-commands (<pin>, <recall>, <note>, <flag>) from assistant messages.
   * Only processes messages that haven't been processed yet (tracked via _thalamus.tcProcessed).
   * Skips content inside code blocks and inline code to prevent false matches from examples.
   */
  processThoughtCommands(sessionId: string, messages: any[]): void {
    const session = this.getSession(sessionId)
    for (let i = 0; i < messages.length; i++) {
      const msg = messages[i]
      if (msg?.role !== 'assistant') continue
      // Skip already-processed messages
      const ann: ThalamusAnnotation | undefined = msg._thalamus
      if (ann?.tcProcessed) continue

      const raw = typeof msg.content === 'string' ? msg.content
        : Array.isArray(msg.content) ? msg.content.map((b: any) => b?.text ?? '').join('')
        : ''
      if (!raw) continue

      // Strip code blocks and inline code to prevent false matches from examples
      const content = raw
        .replace(/```[\s\S]*?```/g, '')
        .replace(/`[^`]+`/g, '')

      const commands = parseThoughtCommands(content)
      // Mark as processed regardless of whether commands were found
      if (ann) ann.tcProcessed = true
      if (!commands.length) continue

      for (const cmd of commands) {
        const body = 'target' in cmd ? (cmd as any).target : 'message' in cmd ? (cmd as any).message : 'content' in cmd ? (cmd as any).content : ''
        session.thoughtCommandLog.push({ type: cmd.type, raw: `<${cmd.type}>${body}</${cmd.type}>`, timestamp: new Date().toISOString() })
        switch (cmd.type) {
          case 'pin':
            this.pin(sessionId, cmd.target, cmd.reason ?? 'thought-command')
            break
          case 'recall':
            this.recallInject(sessionId, cmd.query, 'user', `thought-recall:${cmd.query.slice(0, 40)}`)
            break
          case 'note':
            this.logger.info('Thought-command note', {
              sessionId: sessionId.slice(-8),
              recipient: cmd.recipient,
              msgLen: cmd.message.length,
            })
            this.reverieNoteSink?.(sessionId, cmd.recipient, cmd.message)
            break
          case 'flag':
            this.pin(sessionId, cmd.content, 'thought-command flag')
            break
        }
      }
    }
    // Trim log
    if (session.thoughtCommandLog.length > 100) {
      session.thoughtCommandLog = session.thoughtCommandLog.slice(-50)
    }
  }

  /**
   * Get the temporal registry for a session.
   */
  getTemporalRegistry(sessionId: string): TemporalRegistry {
    let registry = this.temporalRegistries.get(sessionId)
    if (!registry) {
      registry = new TemporalRegistry()
      this.temporalRegistries.set(sessionId, registry)
    }
    return registry
  }

  async curate(
    sessionId: string,
    messages: any[],
    configOverrides?: Partial<CurationConfig>,
  ): Promise<CurationResult> {
    const start = Date.now()

    if (!messages || messages.length === 0) {
      return this.skipResult(messages ?? [], Date.now() - start, 'empty')
    }

    const cfg = { ...DEFAULT_CURATION_CONFIG, ...this.getConfigOverrides(), ...configOverrides }

    // Exclude non-primary sessions
    if (cfg.excludeSessionPrefixes.some(p => sessionId.startsWith(p))) {
      return this.skipResult(messages, Date.now() - start, 'excluded_session')
    }

    const session = this.getSession(sessionId)
    session.totalCurations++
    session.lastCuratedAt = Date.now()

    // Ensure all messages have _thalamus annotations (backward compatibility)
    const annotated = this.processAll(sessionId, messages)

    // Multi-dimensional label classification (MemRouter-inspired write-side routing).
    // Runs after processAll so engram IDs are tracked. Stores semanticType,
    // epistemicShift, and workType labels on each engram's metadata for
    // downstream retrieval-time routing and filtering.
    await this.classifyEngram(sessionId, annotated)

    // Deep clone before any mutations to prevent signature invalidation
    // (Anthropic thinking signatures are bound to exact block structure)
    const cloned = annotated.map(m => deepCloneMessage(m))

    // Apply Cassi-issued directives (drop / collapse) keyed by stable original index.
    // Collapse mutates content immediately so scoring/budget see the shrunken size.
    // Drop is tagged here and excluded in assembleByThreshold.
    {
      const drops = session.dropDirectives
      const collapses = session.collapseDirectives
      if (drops.size > 0 || collapses.size > 0) {
        for (const msg of cloned) {
          const idx = msg?._thalamus?.index
          if (typeof idx !== 'number' || !msg._thalamus) continue
          if (drops.has(idx)) {
            msg._thalamus.directiveDropped = true
          }
          const summary = collapses.get(idx)
          if (summary) {
            const replacement = `[collapsed by cassi: ${summary}]`
            msg.content = replacement
            msg._thalamus.directiveCollapsed = true
            msg._thalamus.directiveSummary = summary
            msg._thalamus.chars = replacement.length
          }
        }
      }
    }

    // Mark AskUserQuestion answers as pinned — these encode operator intent
    // and must survive curation regardless of luminance score, even when older
    // than the recent-window. Without immunity, long sessions look like
    // assistant-drift when they were actually user-directed.
    {
      const toolUseMap = buildToolUseMapFromMessages(cloned)
      for (const msg of cloned) {
        if (hasQuestionResult(msg, { toolUseMap }) && msg?._thalamus) {
          msg._thalamus.pinned = true
          msg._thalamus.pinReason = 'AskUserQuestion answer'
        }
      }
    }

    // Process thought-commands from assistant messages (<pin>, <recall>, <note>, <flag>)
    this.processThoughtCommands(sessionId, cloned)

    const originalChars = cloned.reduce(
      (sum: number, m: any) => sum + extractMessageContent(m).length, 0
    )

    // Inject pending recall queue — synthetic messages re-injected by cassi_context recall_inject
    const pendingRecall = this.getPendingRecall(sessionId)
    if (pendingRecall.length > 0) {
      for (const r of pendingRecall) {
        cloned.push({
          role: r.role,
          content: r.content,
          _thalamus: {
            pinned: true,
            pinReason: `recall: ${r.label ?? 'user-requested'}`,
            source: r.source,
            slot: 'recalled',
          },
        })
      }
      this.clearRecall(sessionId, pendingRecall.map(r => r.id))
      this.logger.info('Injected pending recall messages', { sessionId, count: pendingRecall.length })
    }

    // Identify latest reads per file — non-latest reads are suppressed during scoring
    // so they get dropped entirely instead of being summarized.
    // Detect topic clusters before read suppression so we can scope dedup per-topic
    const topicClusters = this.detectTopicClusters(sessionId, cloned)
    const { nonLatestToolUseIds } = this.computeReadSuppression(cloned, topicClusters)

    // Phase 1: Slot-aware compression — uses _thalamus.tool.class for strategy selection.
    // Two protection mechanisms:
    //   1. Recent window — last N messages are kept verbatim (in-flight context)
    //   2. Live reads — latest read of each path with no later write to that path
    //      survives compression even when older than the recent window. Captures
    //      the "I read the file to prepare an edit" pattern: compressing those
    //      reads forces a re-read and breaks the edit chain.
    const compressionBoundary = Math.max(0, cloned.length - cfg.recentWindowSize)
    const liveReadMap = this.computeLiveReadIndices(sessionId, cloned, cfg.recentWindowSize)
    const { messages: compressed, compressed: compressedCount } =
      this.compressor.compress(cloned, compressionBoundary, { toolResultMaxChars: cfg.toolResultMaxChars }, new Set(liveReadMap.keys()))

    // Phase 2: Enrich with temporal context for scoring
    const temporal = this.getTemporalRegistry(sessionId)
    for (let i = 0; i < compressed.length; i++) {
      const msg = compressed[i]
      if (msg?._thalamus && !msg._thalamus.temporal) {
        const tc = temporal.computeTemporalContext(i)
        if (tc) {
          compressed[i] = { ...msg, _thalamus: { ...msg._thalamus, temporal: tc } }
        }
      }
    }

    // Phase 3: Score with GWT luminance and select by ignition threshold
    const brainContext = await this.getBrainContext(sessionId, compressed)

    // Adaptive protected window: expand when the recent segment is tool-dense.
    // Long tool chains (many consecutive tool_call/tool_result pairs with minimal
    // assistant text between them) need a larger window so the model retains
    // enough context to avoid re-reading files or re-running commands it already
    // executed. Without expansion, the fixed window (default 6 messages) covers
    // only ~2-3 tool rounds, causing context loss and agent loops.
    const effectiveWindowSize = this.computeAdaptiveWindow(compressed, cfg.recentWindowSize)
    const protectedStart = Math.max(0, compressed.length - effectiveWindowSize)

    const scored = this.scorer.scoreAll(compressed, brainContext, protectedStart)

    // Apply slot-specific score adjustments
    for (const sm of scored) {
      const msg = compressed[sm.messageIndex]
      const annotation: ThalamusAnnotation | undefined = msg?._thalamus
      if (annotation) {
        const slot = this.slots.find(s => s.type === annotation.slot)
        if (slot) {
          sm.luminance = slot.adjustScore(sm.luminance, annotation)
        }
      }
    }

    // Phase 3a: Boost read-class tool results that contain terms relevant to the
    // current focus. When the model reads multiple files as part of investigating
    // a problem, those reads form a cohesive context — dropping any of them breaks
    // the chain and forces the model to re-read, creating agent loops.
    {
      const focusTerms = brainContext.focusTerms
      const recentTerms = brainContext.recentMessageTerms
      const allRelevantTerms = new Set([...focusTerms, ...recentTerms])
      if (allRelevantTerms.size > 0) {
        for (const sm of scored) {
          if (sm.luminance.composite >= 0.30) continue
          const annotation: ThalamusAnnotation | undefined = compressed[sm.messageIndex]?._thalamus
          if (annotation?.slot !== 'tool_result' || annotation.tool?.class !== 'read') continue
          const content = extractMessageContent(compressed[sm.messageIndex]).toLowerCase()
          let overlap = 0
          for (const term of allRelevantTerms) {
            if (term.length >= 4 && content.includes(term)) overlap++
          }
          if (overlap >= 2) {
            sm.luminance.relevance = Math.max(sm.luminance.relevance, 0.40)
            sm.luminance.composite = Math.max(sm.luminance.composite, 0.22)
          } else if (overlap >= 1) {
            sm.luminance.composite = Math.max(sm.luminance.composite, 0.18)
          }
        }
      }
    }

    // Phase 3b: Zero out scores for redundant (non-latest) file reads.
    // Past reads are dropped entirely during assembly instead of being summarized.
    const dedupedCount = this.suppressRedundantReads(scored, compressed, nonLatestToolUseIds)

    // Phase 3c: Pin tool results related to detected loops.
    // Reverie's detectAutoLoops() posts [loop] entries to the open-hypotheses lamina
    // and cortex concern signals. When loop signals are active, pin the most recent
    // tool results to prevent them from being dropped — losing context during a loop
    // makes it worse. Pin only the last 2 tool results to be targeted and avoid
    // consuming too much of the char budget.
    const loopSignals = brainContext.cortexIndex.threats
      .filter(ws => /loop|circular|stuck|repeated.*error/i.test(ws.signal.content))
    if (loopSignals.length > 0) {
      let pinnedCount = 0
      // Walk backwards from the end, pinning up to 2 tool_result messages
      for (let i = compressed.length - 1; i >= 0 && pinnedCount < 2; i--) {
        const annotation: ThalamusAnnotation | undefined = compressed[i]?._thalamus
        if (annotation?.slot === 'tool_result' && !annotation.pinned) {
          annotation.pinned = true
          annotation.pinReason = 'loop-detection: cortex loop signal active'
          pinnedCount++
        }
      }
      if (pinnedCount > 0) {
        this.logger.info('Loop-detection: pinned recent tool results due to cortex loop signals', {
          sessionId,
          pinnedCount,
          loopSignals: loopSignals.length,
        })
      }
    }

    // Cap protected segment to half the char budget so the budget remains a real
    // ceiling. Without this, a tool-dense recent window can blow past charBudget
    // entirely (assembleByThreshold's protectedChars > charBudget early-return).
    // Live-read protection (set during compression) and Phase 3a's read boost
    // already ensure relevant older reads survive, so demoted protected reads
    // either survive via candidate selection or were not load-bearing anyway.
    // Floor: always keep the last 2 messages protected (in-flight tool pair).
    const cappedProtectedStart = this.capProtectedWindow(scored, protectedStart, compressed.length, Math.floor(cfg.charBudget * 0.5))

    const assembled = this.assembleByThreshold(compressed, scored, cappedProtectedStart, cfg, topicClusters, sessionId)

    // Phase 4b: Extractive distillation for included messages with large tool
    // results. Uses the local cross-encoder reranker to select the most
    // contextually relevant chunks, preserving semantic coherence instead of
    // naive head+tail truncation.
    let distilled = 0
    if (cfg.distillationEnabled) {
      const recentUserPrompt = this.getRecentUserPrompt(compressed)
      const recentAssistantThinking = this.getRecentAssistantThinking(compressed)
      // Protected from distillation: same set as Phase 1 heuristic protection —
      // live reads (latest read of a file with no later write) need byte-exact
      // survival because the next edit's match-string must align. Without this,
      // a distilled read forces re-reading and breaks the read-then-edit chain.
      const distillProtectedIndices = new Set(liveReadMap.keys())
      const distillResult = await this.distiller.distill(
        assembled.messages,
        assembled.includedIndices,
        session.rerankerCache,
        cfg,
        { userPrompt: recentUserPrompt, assistantThinking: recentAssistantThinking },
        distillProtectedIndices,
      )
      if (distillResult.distilled > 0) {
        assembled.messages = distillResult.messages
        distilled = distillResult.distilled
      }
    }

    const curatedChars = assembled.messages.reduce(
      (sum: number, m: any) => sum + extractMessageContent(m).length, 0
    )

    const dropped = compressed.length - assembled.messages.length

    const protectedIndices = new Set<number>()
    for (let i = cappedProtectedStart; i < compressed.length; i++) {
      protectedIndices.add(i)
    }

    for (let i = 0; i < compressed.length; i++) {
      const msg = compressed[i]
      const annotation: ThalamusAnnotation | undefined = msg?._thalamus
      if (!annotation) continue

      annotation.protectedBy = undefined
      annotation.protectedReason = undefined

      if (annotation.pinned) {
        annotation.protectedBy = 'pin'
        annotation.protectedReason = annotation.pinReason
        continue
      }
      const liveReadPath = liveReadMap.get(i)
      if (liveReadPath !== undefined) {
        annotation.protectedBy = 'live-read'
        annotation.protectedReason = liveReadPath
        continue
      }
      if (annotation.slot === 'system') {
        annotation.protectedBy = 'system'
        annotation.protectedReason = annotation.source ?? 'system'
        continue
      }
      if (i >= cappedProtectedStart) {
        annotation.protectedBy = 'recent-window'
      }
    }

    const receipt = buildDropReceipt({
      before: compressed,
      scored,
      includedIndices: assembled.includedIndices,
      protectedIndices,
      charBudget: cfg.charBudget,
      charsUsed: curatedChars,
      threshold: cfg.ignitionThreshold,
      rerankerCache: session.rerankerCache,
    })

    // Detect tool repetition — same (tool, target) appearing 3+ times
    const repetitionWarning = this.detectToolRepetition(compressed)

    // Extract topic summaries for cross-session sharing
    const topicSummaries = this.extractTopicSummaries(session, scored)

    const contextMap = this.buildContextMap(assembled.messages)

    const meta = {
      originalCount: messages.length,
      curatedCount: assembled.messages.length,
      originalChars,
      curatedChars,
      compressed: compressedCount,
      deduped: dedupedCount,
      dropped,
      gapNotes: assembled.gapNotes,
      receipt,
      repetitionWarning,
      contextMap,
      durationMs: Date.now() - start,
      topicSummaries,
      distilled,
    }

    this.logger.info('Thalamus curated', {
      sessionId,
      original: messages.length,
      curated: assembled.messages.length,
      originalChars,
      curatedChars,
      threshold: cfg.ignitionThreshold,
      phaseCoherence: brainContext.phaseCoherence?.toFixed(2) ?? "?",
      dropped,
      distilled,
      durationMs: meta.durationMs,
    })

    session.lastScored = scored
    session.lastThreshold = cfg.ignitionThreshold

    const scoredByIdx = new Map<number, typeof scored[number]>()
    for (const sm of scored) scoredByIdx.set(sm.messageIndex, sm)
    const includedSorted = [...assembled.includedIndices].sort((a, b) => a - b)
    const mapRows: ContextMapRow[] = []
    for (const idx of includedSorted) {
      const msg = compressed[idx]
      const annotation: ThalamusAnnotation | undefined = msg?._thalamus
      if (!annotation) continue
      const content = extractMessageContent(msg)
      const chars = content.length
      const originalChars =
        typeof msg?._originalChars === 'number' && msg._originalChars > 0
          ? msg._originalChars
          : chars
      const sm = scoredByIdx.get(idx)
      mapRows.push({
        msgIndex: idx,
        role: msg?.role ?? 'unknown',
        slot: annotation.slot,
        ts: annotation.ts,
        chars,
        originalChars,
        compressed: originalChars > chars * 1.05,
        tool: annotation.tool ? {
          name: annotation.tool.name,
          class: annotation.tool.class,
          isError: annotation.tool.isError,
          durationMs: annotation.tool.durationMs,
        } : undefined,
        protectedBy: annotation.protectedBy,
        protectedReason: annotation.protectedReason,
        composite: annotation.protectedBy ? undefined : sm?.luminance.composite,
        preview: content.slice(0, 80),
      })
    }
    session.lastMap = {
      pass: session.totalCurations,
      curatedAt: new Date().toISOString(),
      charBudget: cfg.charBudget,
      charsUsed: curatedChars,
      annotatedCount: cloned.length,
      visibleCount: mapRows.length,
      rows: mapRows,
    }

    // Append drop records (capped at MAX_DROP_HISTORY)
    if (receipt) {
      const includedSet = assembled.includedIndices
      for (const sm of scored) {
        const kept = includedSet.has(sm.messageIndex)
        const msg = compressed[sm.messageIndex]
        const annotation: ThalamusAnnotation | undefined = msg?._thalamus
        const content = extractMessageContent(msg)
        const isPinned = annotation?.pinned === true
        session.dropHistory.push({
          curationPass: session.totalCurations,
          msgIndex: sm.messageIndex,
          role: msg?.role ?? 'unknown',
          luminance: {
            novelty: sm.luminance.novelty,
            urgency: sm.luminance.urgency,
            relevance: sm.luminance.relevance,
            sourceCredibility: sm.luminance.sourceCredibility,
            cognitiveResonance: sm.luminance.cognitiveResonance ?? 0,
            strategicImportance: sm.luminance.strategicImportance ?? 0,
            composite: sm.luminance.composite,
          },
          kept,
          pinned: isPinned,
          preview: content.slice(0, 80),
          slot: annotation?.slot ?? 'unknown',
        })
      }
      if (session.dropHistory.length > MAX_DROP_HISTORY) {
        session.dropHistory = session.dropHistory.slice(-MAX_DROP_HISTORY)
      }

      // Persist to SQLite if store is wired
      if (this.store) {
        try {
          this.store.recordPass(
            sessionId, session.totalCurations,
            messages.length, assembled.messages.length,
            originalChars - meta.curatedChars,
            cfg.ignitionThreshold, meta.durationMs,
            session.dropHistory.filter(r => r.curationPass === session.totalCurations),
          )
          // Store full content (not preview) for recall search
          const includedSet = assembled.includedIndices
          const droppedFull = scored
            .filter(sm => !includedSet.has(sm.messageIndex))
            .map(sm => {
              const msg = compressed[sm.messageIndex]
              return {
                index: sm.messageIndex,
                role: msg?.role ?? 'unknown',
                content: extractMessageContent(msg),
                slot: msg?._thalamus?.slot ?? 'unknown',
                composite: sm.luminance.composite,
              }
            })
          this.store.storeDroppedMessages(sessionId, session.totalCurations, droppedFull)
        } catch (err) {
          this.logger.warn('ThalamusStore recordPass failed', { error: String(err) })
        }
      }
    }

    // Invalidate brain context cache after curation — each turn gets fresh context
    this.cachedBrainContext = null

    // DEBUG: Log thinking block signatures at each step
    const logThinkingSigs = (label: string, msgs: any[]) => {
      const thinkingBlocks: any[] = []
      for (let i = 0; i < msgs.length; i++) {
        const msg = msgs[i]
        if (msg?.role === 'assistant' && Array.isArray(msg.content)) {
          for (const block of msg.content) {
            if (block?.type === 'thinking') {
              thinkingBlocks.push({ msgIndex: i, sigLen: block.signature?.length ?? 0, sigType: typeof block.signature, thinkingLen: block.thinking?.length ?? 0 })
            }
          }
        }
      }
      if (thinkingBlocks.length > 0) {
        this.logger.info(`Thinking signatures ${label}`, { sessionId, count: thinkingBlocks.length, blocks: thinkingBlocks })
      }
    }
    
    logThinkingSigs('before markers', assembled.messages)
    const afterMarkers = attachInlineMarkers(assembled.messages)
    logThinkingSigs('after markers', afterMarkers)
    const afterStrip = stripThalamusAnnotations(afterMarkers)
    logThinkingSigs('after strip', afterStrip)
    let finalMessages = sanitizeToolPairs(afterStrip)
    logThinkingSigs('after sanitize', finalMessages)

    // Sanitize thinking blocks with empty/missing signatures.
    // Claude Code sometimes sends thinking blocks with empty signatures (bug).
    // Anthropic rejects these with 400, so convert them to text blocks.
    finalMessages = finalMessages.map((msg: any) => {
      if (msg?.role !== 'assistant' || !Array.isArray(msg.content)) return msg
      const newContent = msg.content.map((block: any) => {
        if (block?.type === 'thinking' && (!block.signature || block.signature === '')) {
          return { type: 'text', text: block.thinking ?? '' }
        }
        return block
      })
      return { ...msg, content: newContent }
    })

    // Validate before returning. Fatal errors trigger fallback to protected window.
    const validation = validateMessages(finalMessages)
    if (validation.fatal) {
      this.logger.error('Curation produced fatally invalid messages, falling back to protected window', {
        sessionId,
        errors: validation.errors,
        originalCount: messages.length,
      })
      const protectedWindow = this.extractProtectedWindow(cloned, cfg)
      const fallbackMeta = {
        ...meta,
        fallback: 'protected_window' as const,
        validationErrors: validation.errors,
      }
      const sanitizedFallback = sanitizeToolPairs(stripThalamusAnnotations(protectedWindow))
      return { messages: sanitizedFallback, meta: fallbackMeta }
    }
    if (!validation.valid) {
      this.logger.warn('Curation has warnings', { sessionId, errors: validation.errors })
    }

    return { messages: finalMessages, meta }
  }

  /**
   * Import historical session transcripts into the MnemicField.
   *
   * Runs the full classify → score → store pipeline (processAll) but skips
   * budget-based filtering, compression, directive application, and
   * ThalamusStore audit recording. Everything is stored; nothing is dropped.
   *
   * Callers should manage idempotency — this method stores all messages
   * unconditionally.
   */
  async importMessages(
    sessionId: string,
    messages: any[],
    metadata?: { source?: string; project?: string; model?: string },
  ): Promise<{ sessionId: string; imported: number; skippedToolMessages: number; toolChainCount: number; durationMs: number; alreadyImported?: boolean }> {
    const start = Date.now()

    if (!messages || messages.length === 0) {
      return { sessionId, imported: 0, skippedToolMessages: 0, toolChainCount: 0, durationMs: Date.now() - start }
    }

    // Run the standard classify + score + store pipeline.
    // processAll calls process() for each message, which:
    //   1. classifyMessage() → slot type
    //   2. Temporal registry timestamp recording
    //   3. Slot-based augmentation (scoring, _thalamus annotations)
    //   4. writeMessageEngram() → MnemicField storage (Gate 1 filters tool msgs)
    const provenance = metadata?.source ? `${metadata.source}-import` : 'thalamus'
    const annotated = this.processAll(sessionId, messages, provenance)

    // Track how many were tool messages (skipped by Gate 1 in writeMessageEngram)
    let skippedToolMessages = 0
    for (const msg of annotated) {
      const slot = msg?._thalamus?.slot
      if (slot === 'tool_result' || slot === 'tool_call') {
        skippedToolMessages++
      }
    }

    const imported = annotated.length - skippedToolMessages

    // Post-processing pass: attach tool chains to user engrams.
    // For each user message, collect all subsequent tool_call + tool_result
    // pairs (the assistant-with-tools messages + their tool_results) until
    // the next substantive user message. Store inline as metadata.
    let toolChainCount = 0
    if (this.mnemicField) {
      const sessionMap = this._engramIdByIndex.get(sessionId)
      for (let i = 0; i < annotated.length; i++) {
        const msg = annotated[i]
        if (msg?._thalamus?.slot !== 'user') continue

        const chain: Array<{ tool: string; class?: string; target?: string; evidence?: string }> = []
        const filePaths: string[] = []

        // Collect all tool_call/tool_result pairs until next user message
        let j = i + 1
        while (j < annotated.length) {
          const next = annotated[j]
          const nextSlot = next?._thalamus?.slot
          if (nextSlot === 'user') break

          if (nextSlot === 'tool_call') {
            const content = Array.isArray(next.content) ? next.content : []
            // Find the tool_use blocks in this tool_call message
            for (const tu of content.filter((b: any) => b?.type === 'tool_use')) {
              const toolName = tu.name ?? 'unknown'
              const toolClass = classifyTool(toolName)
              const target = extractFilePath(tu.input ?? {}) || extractSearchTarget(tu.input ?? {})
              // Look ahead for matching tool_result in the next tool_result message
              let evidence: string | undefined
              for (let k = j + 1; k < annotated.length; k++) {
                const tr = annotated[k]
                if (tr?._thalamus?.slot === 'user' || tr?._thalamus?.slot === 'tool_call') break
                if (tr?._thalamus?.slot !== 'tool_result') continue
                const trContent = Array.isArray(tr.content) ? tr.content : []
                const trBlock = trContent.find((b: any) => b?.type === 'tool_result' && b?.tool_use_id === tu.id)
                if (trBlock) {
                  evidence = (typeof trBlock.content === 'string' ? trBlock.content : JSON.stringify(trBlock.content ?? '')).slice(0, 800)
                  break
                }
              }
              chain.push({ tool: toolName, class: toolClass, target, evidence })
              if (target && !filePaths.includes(target)) filePaths.push(target)
              toolChainCount++
            }
          }
          j++
        }

        if (chain.length > 0) {
          const engramId = sessionMap?.get(i)
          if (engramId) {
            const existing = this.mnemicField.get(engramId)
            const existingMeta = existing?.metadata ?? {}
            const existingTags = existing?.tags ?? []
            this.mnemicField.update(engramId, {
              metadata: { ...existingMeta, toolChain: chain },
              tags: [...new Set([...existingTags, ...filePaths.map(p => `file:${shortenPath(p)}`)])],
            })
          }
        }
      }
    }

    // Store import marker engram for discovery
    if (this.mnemicField && imported > 0) {
      this.mnemicField.store({
        nodeType: 'fact' as any,
        content: `Imported ${imported} messages from ${metadata?.source ?? 'unknown'} session ${sessionId}`,
        tags: ['thalamus:import', `source:${metadata?.source ?? 'unknown'}`, `session:${sessionId}`],
        provenance: 'thalamus.import',
        metadata: {
          sessionId,
          imported,
          skippedToolMessages,
          source: metadata?.source,
          project: metadata?.project,
          model: metadata?.model,
          importedAt: new Date().toISOString(),
        },
      })
    }

    const durationMs = Date.now() - start
    this.logger.info('Thalamus import complete', { sessionId, imported, skippedToolMessages, toolChainCount, durationMs })

    return { sessionId, imported, skippedToolMessages, toolChainCount, durationMs }
  }

  getStats(): { sessions: number; totalCurations: number } {
    let totalCurations = 0
    for (const s of this.sessions.values()) {
      totalCurations += s.totalCurations
    }
    return { sessions: this.sessions.size, totalCurations }
  }

  /**
   * Most-recently-curated session within `windowMs` (default 5 min).
   * Used by `cassi_context` to default sessionId to the originating session.
   */
  getActiveSessionId(windowMs = 5 * 60_000): string | null {
    let best: { id: string; ts: number } | null = null
    const now = Date.now()
    for (const s of this.sessions.values()) {
      if (now - s.lastCuratedAt > windowMs) continue
      if (!best || s.lastCuratedAt > best.ts) best = { id: s.sessionId, ts: s.lastCuratedAt }
    }
    return best?.id ?? null
  }

  /**
   * Mark message indices for exclusion on the next curate pass.
   * Idempotent. Caller is responsible for clearing via `clearDirectives`.
   */
  markDrop(sessionId: string, indices: number[]): { dropped: number[] } {
    const session = this.getSession(sessionId)
    for (const i of indices) session.dropDirectives.add(i)
    return { dropped: Array.from(session.dropDirectives).sort((a, b) => a - b) }
  }

  /**
   * Replace a message's content with a short summary on the next curate pass.
   * Empty summary clears the directive for that index.
   */
  markCollapse(sessionId: string, index: number, summary: string): { collapsed: number[] } {
    const session = this.getSession(sessionId)
    if (summary && summary.trim().length > 0) {
      session.collapseDirectives.set(index, summary.trim())
    } else {
      session.collapseDirectives.delete(index)
    }
    return { collapsed: Array.from(session.collapseDirectives.keys()).sort((a, b) => a - b) }
  }

  clearDirectives(sessionId: string, opts?: { drops?: number[]; collapses?: number[] }): void {
    const session = this.getSession(sessionId)
    if (!opts) {
      session.dropDirectives.clear()
      session.collapseDirectives.clear()
      return
    }
    if (opts.drops) for (const i of opts.drops) session.dropDirectives.delete(i)
    if (opts.collapses) for (const i of opts.collapses) session.collapseDirectives.delete(i)
  }

  /**
   * Recover the original content for a tool result that was extractively
   * distilled. Returns undefined if the tool_use_id is not found in the
   * session's distillation cache.
   */
  expandToolResult(sessionId: string, toolUseId: string): { original: string; compressed: string; toolUseId: string } | undefined {
    const session = this.getSession(sessionId)
    const entry = session.rerankerCache.entries.get(toolUseId)
    if (!entry) return undefined
    return {
      toolUseId,
      original: entry.originalContent,
      compressed: entry.compressedContent,
    }
  }

  private extractToolUseId(msg: any): string | undefined {
    const ann = msg?._thalamus
    if (ann?.toolUseId) return ann.toolUseId
    if (ann?.tool?.toolUseId) return ann.tool.toolUseId
    if (typeof msg?.tool_use_id === 'string') return msg.tool_use_id
    // tool_result blocks carry tool_use_id inside the content array
    if (Array.isArray(msg?.content)) {
      for (const block of msg.content) {
        if (block?.type === 'tool_result' && typeof block.tool_use_id === 'string') {
          return block.tool_use_id
        }
      }
    }
    return undefined
  }

  private replaceToolResultContent(msg: any, newContent: string): void {
    if (Array.isArray(msg?.content)) {
      msg.content = [{ type: 'text', text: newContent }]
    } else if (typeof msg?.content === 'string') {
      msg.content = newContent
    }
  }

  audit(sessionId: string, window: number = 5): DropRecord[] {
    const session = this.sessions.get(sessionId)
    if (session && session.dropHistory.length > 0) {
      const passes = new Set<number>()
      for (let i = session.dropHistory.length - 1; i >= 0; i--) {
        passes.add(session.dropHistory[i].curationPass)
        if (passes.size > window) break
      }
      return session.dropHistory.filter(r => passes.has(r.curationPass))
    }
    // Fall back to persistent store after restart
    if (this.store) {
      try {
        return this.store.getDropRecords(sessionId, window)
      } catch (err) {
        this.logger.warn('ThalamusStore audit fallback failed', { error: String(err) })
      }
    }
    return []
  }

  pin(sessionId: string, target: string, reason: string, pinClass: string = 'episode'): string {
    const session = this.getSession(sessionId)
    const id = `pin_${Date.now().toString(36)}_${Math.random().toString(36).slice(2, 6)}`
    session.pinnedPatterns.push({
      id,
      target,
      reason,
      pinnedAt: new Date().toISOString(),
      pinClass,
    })
    return id
  }

  unpin(sessionId: string, pinId: string): boolean {
    const session = this.sessions.get(sessionId)
    if (!session) return false
    const idx = session.pinnedPatterns.findIndex(p => p.id === pinId)
    if (idx === -1) return false
    session.pinnedPatterns.splice(idx, 1)
    return true
  }

  why(sessionId: string, msgIndex: number): DropRecord | null {
    const session = this.sessions.get(sessionId)
    if (!session) return null
    for (let i = session.dropHistory.length - 1; i >= 0; i--) {
      if (session.dropHistory[i].msgIndex === msgIndex) {
        return session.dropHistory[i]
      }
    }
    if (session.lastScored.length > 0) {
      const sm = session.lastScored.find(s => s.messageIndex === msgIndex)
      if (sm) {
        return {
          curationPass: session.totalCurations,
          msgIndex: sm.messageIndex,
          role: 'unknown',
          luminance: {
            novelty: sm.luminance.novelty,
            urgency: sm.luminance.urgency,
            relevance: sm.luminance.relevance,
            sourceCredibility: sm.luminance.sourceCredibility,
            cognitiveResonance: sm.luminance.cognitiveResonance ?? 0,
            strategicImportance: sm.luminance.strategicImportance ?? 0,
            composite: sm.luminance.composite,
          },
          kept: true,
          pinned: false,
          preview: '',
          slot: 'unknown',
        }
      }
    }
    return null
  }

  getContextMap(sessionId: string, opts?: { since?: number; limit?: number }): ContextMapSnapshot | null {
    const session = this.sessions.get(sessionId)
    if (!session || !session.lastMap) return null
    const snap = session.lastMap
    let rows = snap.rows
    if (typeof opts?.since === 'number') rows = rows.filter(r => r.msgIndex >= opts.since!)
    if (typeof opts?.limit === 'number' && rows.length > opts.limit) rows = rows.slice(-opts.limit)
    if (rows === snap.rows) return snap
    return { ...snap, rows, visibleCount: rows.length }
  }

  recall(sessionId: string, query: string, limit: number = 5): Array<{
    id: number; passNumber: number; msgIndex: number
    role: string; content: string; slot: string; composite: number
  }> {
    if (!this.store) return []
    try {
      return this.store.searchDropped(sessionId, query, limit)
    } catch {
      return []
    }
  }

  recallInject(sessionId: string, content: string, role: string, label?: string): number {
    if (!this.store) return -1
    try {
      return this.store.enqueueRecall(sessionId, content, role, label)
    } catch {
      return -1
    }
  }

  getPendingRecall(sessionId: string, limit: number = 5): Array<{
    id: number; content: string; role: string; source: string; label: string | null
  }> {
    if (!this.store) return []
    try {
      return this.store.dequeueRecall(sessionId, limit)
    } catch {
      return []
    }
  }

  clearRecall(sessionId: string, ids: number[]): void {
    if (!this.store) return
    try {
      this.store.clearRecallQueue(sessionId, ids)
    } catch {}
  }

  /**
   * Get or build brain context for this session+messages.
   * Caches the result so assembleInjections and curate don't
   * duplicate the expensive buildBrainContext call in the same turn.
   */
  private async getBrainContext(sessionId: string, messages: any[]): Promise<BrainContext> {
    const messageCount = messages.length
    if (
      this.cachedBrainContext?.sessionId === sessionId &&
      this.cachedBrainContext.messageCount === messageCount
    ) {
      return this.cachedBrainContext.ctx
    }
    const ctx = await this.buildBrainContext(sessionId, messages)
    this.cachedBrainContext = { sessionId, messageCount, ctx }
    return ctx
  }

  private async buildBrainContext(sessionId: string, messages: any[]): Promise<BrainContext> {
    const foci = this.locusBridge?.getFoci() ?? []
    const focusTerms = new Set<string>()
    const focusFiles = new Set<string>()
    for (const f of foci) {
      if (!f.spark) continue
      for (const term of extractTerms(f.spark.content)) focusTerms.add(term)
      for (const file of extractFilePaths(f.spark.content)) focusFiles.add(file)
      for (const file of (f.spark.relevantFiles ?? [])) focusFiles.add(file)
    }

    const snapshot = this.globalWorkspace?.getSnapshot()
    const workspaceSignals = snapshot?.slots
      ?.filter((s: any) => s.signal !== null)
      ?.map((s: any) => s.signal!) ?? []

    for (const sig of workspaceSignals) {
      for (const term of extractTerms(sig.content)) focusTerms.add(term)
      for (const file of extractFilePaths(sig.content)) focusFiles.add(file)
    }

    const cortexSignals = this.cortex?.readActive({ limit: 30, sessionId }) ?? []
    const cortexIndex = this.buildCortexIndex(cortexSignals, sessionId)
    const affectState = this.cortex?.getAffectState?.() ?? null

    // Add high-salience cortex terms to focus
    for (const ws of cortexIndex.highSalience) {
      for (const term of ws.terms) focusTerms.add(term)
      for (const file of extractFilePaths(ws.signal.content)) focusFiles.add(file)
    }

    // Working memory terms — highest priority cognitive signals
    const workingMemoryTerms = new Set<string>()
    for (const ws of cortexIndex.workingMemory) {
      for (const term of ws.terms) workingMemoryTerms.add(term)
    }

    const mnemonicTerms = new Set<string>()
    if (this.mnemicField) {
      try {
        const topEngrams = this.mnemicField.list(15).filter(e => e.potentiation > 0.5)
        for (const e of topEngrams) {
          for (const term of extractTerms(e.content)) mnemonicTerms.add(term)
        }
      } catch {
        // Degrade gracefully
      }
    }

    const recentMessageTerms = new Set<string>()
    const recentMessageFiles = new Set<string>()
    let seen = 0
    for (let i = messages.length - 1; i >= 0 && seen < 15; i--) {
      const msg = messages[i]
      if (msg?.role !== 'user' && msg?.role !== 'assistant') continue
      seen++
      const content = extractMessageContent(msg)
      for (const term of extractTerms(content)) recentMessageTerms.add(term)
      for (const file of extractFilePaths(content)) recentMessageFiles.add(file)
    }

    const { architecturalTerms, architecturalConcepts, architecturalHits } =
      await this.buildSelfModelContext(focusTerms, recentMessageTerms)

    const { pinealTerms, pinealPriorities } = this.buildPinealContext(sessionId)

    // Phase transition detection: measure overlap between recent conversation
    // and the cortex/focus signals. Low overlap = topic shift → stale signals
    // should be down-weighted so we don't resurface completed work phases.
    const phaseCoherence = this.computePhaseCoherence(
      recentMessageTerms, focusTerms, cortexIndex,
    )

    // Strategic importance: terms appearing in multiple archived topic clusters
    const topicArchiveTerms = new Map<string, number>()
    const session = this.getSession(sessionId)
    for (const archive of session.topicArchive) {
      for (const term of archive.keyTerms ?? []) {
        topicArchiveTerms.set(term, (topicArchiveTerms.get(term) ?? 0) + 1)
      }
    }

    return {
      foci,
      workspaceSignals,
      focusTerms,
      focusFiles,
      cortexSignals,
      cortexIndex,
      affectState,
      workingMemoryTerms,
      mnemonicTerms,
      architecturalTerms,
      architecturalConcepts,
      architecturalHits,
      pinealTerms,
      pinealPriorities,
      recentMessageTerms,
      recentMessageFiles,
      phaseCoherence,
      topicArchiveTerms,
    }
  }

  /**
   * Build a compact context string for the dialectic engine from the current
   * brain state. Summarizes cortex signals, affect, memory, self-model concepts,
   * focus files, and recent conversation themes into a ~2000-char payload.
   */
  async buildDialecticContext(sessionId: string, messages: any[]): Promise<string> {
    const ctx = await this.getBrainContext(sessionId, messages)
    const parts: string[] = []

    // Cortex signals — what's active in working memory
    if (ctx.cortexIndex.highSalience.length > 0) {
      const signals = ctx.cortexIndex.highSalience.slice(0, 5)
        .map(ws => `[${ws.signal.type}] ${ws.signal.content.slice(0, 120)}`)
        .join('\n')
      parts.push(`Active cognitive signals:\n${signals}`)
    }

    // Affect state — emotional/cognitive tone
    if (ctx.affectState) {
      const a = ctx.affectState as { valence?: number; arousal?: number; dominantEmotion?: string }
      if (a.dominantEmotion) {
        parts.push(`Affect: ${a.dominantEmotion} (valence=${a.valence?.toFixed(2) ?? '?'}, arousal=${a.arousal?.toFixed(2) ?? '?'})`)
      }
    }

    // Attention focus — what files and terms are being worked on
    if (ctx.focusTerms.size > 0) {
      parts.push(`Focus terms: ${[...ctx.focusTerms].slice(0, 15).join(', ')}`)
    }
    if (ctx.focusFiles.size > 0) {
      parts.push(`Focus files: ${[...ctx.focusFiles].slice(0, 8).join(', ')}`)
    }

    // Memory terms — what's been potentiated in the Mnemic Field
    if (ctx.mnemonicTerms.size > 0) {
      parts.push(`Active memories: ${[...ctx.mnemonicTerms].slice(0, 12).join(', ')}`)
    }

    // Architectural self-knowledge — relevant codebase concepts
    if (ctx.architecturalHits.length > 0) {
      const hits = ctx.architecturalHits.slice(0, 4)
        .map(h => `${h.nodeType}: ${h.conceptName}`)
        .join(', ')
      parts.push(`Architectural context: ${hits}`)
    }

    // Identity / pineal priorities
    if (ctx.pinealTerms.size > 0) {
      parts.push(`Identity priorities: ${[...ctx.pinealTerms].slice(0, 8).join(', ')}`)
    }

    // Recent conversation themes
    if (ctx.recentMessageTerms.size > 0) {
      parts.push(`Recent conversation: ${[...ctx.recentMessageTerms].slice(0, 15).join(', ')}`)
    }

    // Working memory threats / concerns
    if (ctx.cortexIndex.threats.length > 0) {
      const threats = ctx.cortexIndex.threats.slice(0, 3)
        .map(ws => ws.signal.content.slice(0, 100))
        .join('; ')
      parts.push(`Active concerns: ${threats}`)
    }

    return parts.join('\n\n')
  }

  /**
   * Assemble context injections from Aurora (cognitive state) and Pineal (identity).
   * Replaces the InjectionAggregator — the Thalamus now owns injection assembly
   * using the same brain context it uses for message scoring.
   */
  async assembleInjections(
    sessionId: string,
    messages: any[],
  ): Promise<Array<{ content: string; source: string }>> {
    const injections: Array<{ content: string; source: string }> = []

    try {
      // Aurora: build cognitive state from current attention foci
      if (this.aurora) {
        const brainContext = await this.getBrainContext(sessionId, messages)

        // Blend focus terms with recent conversation terms, weighted by
        // phase coherence. When coherence is low (topic shift), recent
        // terms dominate so Aurora doesn't build mental state around
        // stale focus from a completed work phase.
        const pc = brainContext.phaseCoherence
        const blended: string[] = []

        // Recent terms always contribute (phase-independent ground truth)
        for (const term of brainContext.recentMessageTerms) {
          blended.push(term)
        }
        // Focus terms contribute proportionally to phase coherence
        if (pc > 0.3) {
          for (const term of brainContext.focusTerms) {
            if (!brainContext.recentMessageTerms.has(term)) {
              blended.push(term)
            }
          }
        }

        const foci = blended.slice(0, 8)

        const state = this.aurora.buildState(foci)
        const text = this.aurora.serialize(state)
        if (text) {
          injections.push({ content: `<aurora>\n${text}\n</aurora>`, source: 'aurora' })
        }
      }

      // Pineal: assemble identity facets
      if (this.pinealAssembler) {
        const { text, facetIds } = this.pinealAssembler.assemble(sessionId)
        if (text) {
          this.lastPinealFacetIds = facetIds
          injections.push({ content: `<pineal>\n${text}\n</pineal>`, source: 'pineal' })
        }
      }

      // Mnemic Field: assemble expert context
      if (this.mnemicField) {
        const lastMsg = messages[messages.length - 1]
        const intent = typeof lastMsg?.content === 'string'
          ? lastMsg.content.slice(0, 200)
          : ''
        if (intent) {
          try {
            const expertMessages = await this.queryContext(sessionId, intent)
            for (const msg of expertMessages) {
              injections.push({
                content: `<knowledge>\n${msg.content}\n</knowledge>`,
                source: 'expert',
              })
            }
          } catch {
            // Best-effort
          }
        }
      }
    } catch (err) {
      this.logger.warn('Thalamus injection assembly failed (non-fatal)', {
        sessionId: sessionId.slice(-8),
        error: String(err),
      })
    }

    if (injections.length > 0) {
      this.logger.debug('Thalamus injections assembled', {
        sessionId: sessionId.slice(-8),
        sources: injections.map(i => i.source),
        totalChars: injections.reduce((s, i) => s + i.content.length, 0),
      })
    }

    return injections
  }

  /**
   * Reinforce Pineal facets that were injected on the last turn.
   * Called on turn:end — facets earn conviction through use.
   */
  reinforcePinealFacets(): number {
    if (this.lastPinealFacetIds.length === 0 || !this.pinealFacets) return 0

    const count = this.pinealFacets.reinforceMany(this.lastPinealFacetIds)
    this.lastPinealFacetIds = []
    return count
  }

  /**
   * Forward reasoning to Aurora for cognitive state feedback.
   * Called on turn:end with the assistant's response.
   *
   * Aurora runs a fast path (regex concept extraction + graph activation)
   * and optionally a Reverie slow path (LLM semantic analysis).
   * The reasoning text is persisted as a ReasoningRecord for learning.
   */
  observeReasoning(text: string): void {
    if (!this.aurora) return
    this.aurora.observeReasoning(text)
  }

  async updateFeatureNarrative(contextText: string): Promise<void> {
    if (!this.aurora) return
    await this.aurora.updateFeatureNarrative(contextText)
  }

  /**
   * Measure coherence between recent conversation and the cortex/focus state.
   * Returns 0.0 (total topic shift) to 1.0 (same topic).
   *
   * When the conversation has moved on (e.g., from code review to running tests)
   * but cortex/focus signals still reflect the old phase, this returns a low value.
   * The scorer uses this to down-weight stale focus signals so old completed
   * work phases don't get resurfaced into context.
   */
  private computePhaseCoherence(
    recentTerms: Set<string>,
    focusTerms: Set<string>,
    cortexIndex: CortexIndex,
  ): number {
    if (recentTerms.size === 0) return 1.0 // No recent data → assume coherent

    // Gather all "background state" terms from focus + high-salience cortex
    const backgroundTerms = new Set<string>(focusTerms)
    for (const ws of cortexIndex.highSalience) {
      for (const term of ws.terms) backgroundTerms.add(term)
    }
    for (const ws of cortexIndex.workingMemory) {
      for (const term of ws.terms) backgroundTerms.add(term)
    }

    if (backgroundTerms.size === 0) return 1.0 // No background state → coherent

    // Jaccard-like overlap: what fraction of background terms appear in recent conversation?
    let overlap = 0
    for (const term of backgroundTerms) {
      if (recentTerms.has(term)) overlap++
    }

    const coherence = overlap / backgroundTerms.size
    // Clamp to [0.15, 1.0] — never fully zero (some background context is always useful)
    return Math.max(0.15, Math.min(1.0, coherence))
  }

  /**
   * Build a structured index of cortex signals, categorized by type, region,
   * salience, valence, and working memory state. This enables efficient
   * multi-axis scoring without repeated iteration.
   */
  private buildCortexIndex(signals: import('../cortex/types.js').CorticalSignal[], sessionId: string): CortexIndex {
    const index: CortexIndex = {
      byType: {},
      byRegion: {},
      workingMemory: [],
      highSalience: [],
      threats: [],
    }

    for (const sig of signals) {
      const typeW = SIGNAL_TYPE_WEIGHTS[sig.type] ?? 1.0
      const regionW = REGION_WEIGHTS[sig.region] ?? 1.0
      const weight = Math.min(2.0, sig.salience * sig.confidence * typeW * regionW)
      const terms = extractTerms(sig.content)
      const ws: WeightedSignal = { signal: sig, weight, terms }

      // Group by type
      ;(index.byType[sig.type] ??= []).push(ws)
      // Group by region
      ;(index.byRegion[sig.region] ??= []).push(ws)
      // High salience (above default)
      if (sig.salience > 0.6) index.highSalience.push(ws)
      // Negative valence = threat/concern
      if (sig.valence < -0.2) index.threats.push(ws)
    }

    // Working memory: session-focused signals
    const session = this.cortex?.getSession?.(sessionId)
    if (session) {
      try {
        const wmSignals = session.getWorkingMemory()
        for (const wmSig of wmSignals) {
          const terms = extractTerms(wmSig.content)
          index.workingMemory.push({ signal: wmSig, weight: 1.5, terms })
        }
      } catch {
        // Session may not have working memory
      }
    }

    return index
  }

  /**
   * Query the self-model using current focus terms to find architecturally
   * relevant concepts. Returns enriched terms, concept names, and raw hits.
   * ~4-5ms cost, called once per curation.
   */
  private async buildSelfModelContext(focusTerms: Set<string>, recentMessageTerms: Set<string>): Promise<{
    architecturalTerms: Set<string>
    architecturalConcepts: Set<string>
    architecturalHits: SelfModelHit[]
  }> {
    const empty = { architecturalTerms: new Set<string>(), architecturalConcepts: new Set<string>(), architecturalHits: [] as SelfModelHit[] }
    if (!this.selfModelField) return empty

    try {
      // Sample top focus terms to query the self-model for architectural context
      // Falls back to recent message terms if no focus terms exist yet (cold start)
      let sample = Array.from(focusTerms).slice(0, 6).join(' ')
      if (!sample && recentMessageTerms.size > 0) {
        sample = Array.from(recentMessageTerms).slice(0, 6).join(' ')
      }
      if (!sample) return empty

      const hits = await this.selfModelField.retrieve(sample, { limit: 10 })
      const architecturalTerms = new Set<string>()
      const architecturalConcepts = new Set<string>()
      const architecturalHits: SelfModelHit[] = []

      for (const hit of hits) {
        const conceptName = hit.content.split(' — ')[0]?.trim().toLowerCase() ?? ''
        if (conceptName) architecturalConcepts.add(conceptName)
        for (const term of extractTerms(hit.content)) architecturalTerms.add(term)
        architecturalHits.push({
          content: hit.content,
          score: hit.score,
          nodeType: (hit as any).nodeType ?? 'module',
          conceptName,
        })
      }

      return { architecturalTerms, architecturalConcepts, architecturalHits }
    } catch {
      return empty
    }
  }

  /**
   * Extract high-conviction pineal facets as identity/wisdom terms.
   * Only includes facets with conviction > 0.4 (earned through use).
   * Uses sessionId to include channel-scoped facets for the right channel.
   * ~1ms cost, called once per curation.
   */
  private buildPinealContext(sessionId: string): {
    pinealTerms: Set<string>
    pinealPriorities: Map<string, number>
  } {
    const empty = { pinealTerms: new Set<string>(), pinealPriorities: new Map<string, number>() }
    if (!this.pinealFacets) return empty

    try {
      // Detect channel from session ID prefix for scope-aware facet filtering
      const channel = this.detectChannel(sessionId)
      const facets = this.pinealFacets.list({
        active: true,
        minConviction: 0.4,
        matchScope: channel,
        limit: 30,
      })
      const pinealTerms = new Set<string>()
      const pinealPriorities = new Map<string, number>()

      for (const facet of facets) {
        for (const term of extractTerms(facet.content)) {
          pinealTerms.add(term)
          const existing = pinealPriorities.get(term) ?? 0
          pinealPriorities.set(term, Math.max(existing, facet.conviction))
        }
      }

      return { pinealTerms, pinealPriorities }
    } catch {
      return empty
    }
  }

  /**
   * Extract channel identifier from session ID prefix.
   * Maps "oc:" → "opencode", "mcp:" → "mcp", etc.
   * Returns null for internal/unknown sessions (universal facets only).
   */
  private detectChannel(sessionId: string): string | null {
    const CHANNEL_PREFIXES: Record<string, string> = {
      'oc:': 'opencode', 'mcp:': 'mcp', 'web:': 'web', 'vscode:': 'vscode',
    }
    for (const [prefix, channel] of Object.entries(CHANNEL_PREFIXES)) {
      if (sessionId.startsWith(prefix)) return channel
    }
    return null
  }

  /**
   * Threshold-based assembly: include only messages that ignite.
   * Protected messages (last N) are always included.
   * If ignited messages exceed budget, raise threshold until they fit.
   */
  private assembleByThreshold(
    messages: any[],
    scored: ScoredMessage[],
    protectedStart: number,
    config: CurationConfig,
    topicClusters?: TopicCluster[],
    sessionId?: string,
  ): {
    messages: any[]
    gapNotes: number
    includedIndices: Set<number>
    charsUsed: number
    pinnedOverrides: number
  } {
    let threshold = config.ignitionThreshold

    const isPinned = (s: ScoredMessage): boolean =>
      messages[s.messageIndex]?._thalamus?.pinned === true

    // Pinned messages are unconditionally included — they never compete
    // for budget. Reserve their chars first, then compute what's left for
    // the protected window and candidate selection.
    const allCandidates = scored
      .filter(s => s.messageIndex < protectedStart)
      .sort((a, b) => b.luminance.composite - a.luminance.composite)

    const pinnedCandidates = allCandidates.filter(isPinned)
    const pinnedChars = pinnedCandidates.reduce((sum, s) => sum + s.estimatedChars, 0)
    const pinnedSet = new Set<number>(pinnedCandidates.map(s => s.messageIndex))
    let pinnedOverrides = pinnedSet.size

    // Protected messages always included
    const protectedChars = scored
      .filter(s => s.messageIndex >= protectedStart)
      .reduce((sum, s) => sum + s.estimatedChars, 0)

    let remainingBudget = config.charBudget - pinnedChars - protectedChars

    // If budget is exhausted after reserving chars for pinned + protected,
    // set remainingBudget to 0 so no candidates are added. The protected
    // window is never shrunk — recent context is more valuable than old
    // candidates that might fit by squeezing the protected zone.
    if (remainingBudget < 0) {
      remainingBudget = 0
    }

    // Candidates: older messages that must compete for inclusion (excluding pinned, already included)
    const candidates = allCandidates.filter(s => !pinnedSet.has(s.messageIndex))

    // Ignition: select candidates above threshold, within budget
    let included = new Set<number>(pinnedSet)
    let usedChars = pinnedChars

    const selectByThreshold = (t: number): { set: Set<number>; chars: number } => {
      const set = new Set<number>(pinnedSet)
      let chars = pinnedChars
      // High-luminance candidates fill remaining budget
      for (const s of candidates) {
        if (s.luminance.composite < t) continue
        if (chars + s.estimatedChars > remainingBudget + pinnedChars) continue
        set.add(s.messageIndex)
        chars += s.estimatedChars
      }
      return { set, chars }
    }

    const result = selectByThreshold(threshold)
    included = result.set
    usedChars = result.chars

    // If still over budget (shouldn't happen with the check above, but safety), raise threshold
    if (usedChars > remainingBudget) {
      const step = 0.05
      for (let t = threshold + step; t < 1.0; t += step) {
        const retry = selectByThreshold(t)
        if (retry.chars <= remainingBudget) {
          included = retry.set
          break
        }
      }
    }

    // Build bidirectional maps for tool pair lookups (used by diversity and repair)
    const toolUseIdxById = new Map<string, number>()
    const toolResultIdxById = new Map<string, number>()
    for (let i = 0; i < messages.length; i++) {
      const msg = messages[i]
      if (!Array.isArray(msg?.content)) continue
      for (const block of msg.content) {
        if (block?.type === 'tool_use' && typeof block.id === 'string') {
          toolUseIdxById.set(block.id, i)
        }
        if (block?.type === 'tool_result' && typeof block.tool_use_id === 'string') {
          toolResultIdxById.set(block.tool_use_id, i)
        }
      }
    }

    // Diversity pass: ensure at least one representative per completed topic cluster.
    // This prevents older work phases from being completely erased when their messages
    // all score below the ignition threshold.
    // Runs BEFORE repair passes so that injected representatives can be validated and
    // paired by ensureToolPairs/ensureAlternation, avoiding orphaned tool blocks.
    const scoredByIndex = new Map(scored.map(s => [s.messageIndex, s]))
    if (topicClusters && topicClusters.length > 1) {
      // Skip the last (active) cluster — it's covered by protectedStart
      for (let ci = 0; ci < topicClusters.length - 1; ci++) {
        const cluster = topicClusters[ci]
        const clusterOldIndices = cluster.messageIndices.filter(idx => idx < protectedStart)
        if (clusterOldIndices.length === 0) continue
        const hasRepresentative = clusterOldIndices.some(idx => included.has(idx))
        if (!hasRepresentative) {
          // Pick the highest-scored message in this cluster that fits in budget
          // and does not create unpaired tool blocks.
          const candidates2 = clusterOldIndices
            .map(idx => scoredByIndex.get(idx))
            .filter((s): s is ScoredMessage => s !== undefined && s.luminance.composite > 0)
            .sort((a, b) => b.luminance.composite - a.luminance.composite)
          for (const s of candidates2) {
            if (s.estimatedChars > remainingBudget - usedChars) continue
            // Skip if injecting this message would create unpaired tool blocks
            // that cannot be resolved by adding the partner message.
            const msg = messages[s.messageIndex]
            if (Array.isArray(msg?.content)) {
              const hasToolUse = msg.content.some((c: any) => c?.type === 'tool_use')
              const hasToolResult = msg.content.some((c: any) => c?.type === 'tool_result')
              if (hasToolUse || hasToolResult) {
                const partnerResolvable = msg.content.every((c: any) => {
                  if (c?.type === 'tool_use') {
                    const resultIdx = toolResultIdxById.get(c.id)
                    if (resultIdx === undefined) return false
                    // Partner must fit in budget or already be included
                    if (!included.has(resultIdx)) {
                      const partnerChars = scoredByIndex.get(resultIdx)?.estimatedChars ?? 0
                      if (usedChars + s.estimatedChars + partnerChars > remainingBudget) return false
                    }
                  }
                  if (c?.type === 'tool_result') {
                    const useIdx = toolUseIdxById.get(c.tool_use_id)
                    if (useIdx === undefined) return false
                    if (!included.has(useIdx)) {
                      const partnerChars = scoredByIndex.get(useIdx)?.estimatedChars ?? 0
                      if (usedChars + s.estimatedChars + partnerChars > remainingBudget) return false
                    }
                  }
                  return true
                })
                if (!partnerResolvable) continue
              }
            }
            included.add(s.messageIndex)
            usedChars += s.estimatedChars
            break
          }
        }
      }
    }

    // Iterate both repair passes to fixpoint. Each pass can create work for
    // the other: ensureAlternation may bridge a gap with an assistant tool_use
    // whose tool_result isn't included (alternation fixed, pairing broken);
    // ensureToolPairs may delete an orphan pair member (pairing fixed,
    // alternation broken). Cap at 5 iterations — converges in ≤2 in practice.
    for (let pass = 0; pass < 5; pass++) {
      const before = Array.from(included).sort((a, b) => a - b).join(',')
      this.ensureToolPairs(messages, included, protectedStart)
      this.ensureAlternation(messages, included, protectedStart)
      const after = Array.from(included).sort((a, b) => a - b).join(',')
      if (before === after) break
      // Recalc usedChars after each repair pass since it adds partners
      usedChars = Array.from(included).reduce((sum, idx) => {
        return sum + (scoredByIndex.get(idx)?.estimatedChars ?? extractMessageContent(messages[idx]).length)
      }, 0)
    }

    // Phase 3c: Hard budget enforcement. After repair passes and diversity
    // injection, the actual char count can exceed charBudget because those
    // passes add messages without recalculating the budget. Trim the
    // lowest-luminance droppable messages until we're under budget.
    const calcTotalChars = (): number => {
      let total = 0
      for (let i = 0; i < messages.length; i++) {
        if (i >= protectedStart || included.has(i)) {
          total += scoredByIndex.get(i)?.estimatedChars ?? extractMessageContent(messages[i]).length
        }
      }
      return total
    }
    let totalChars = calcTotalChars()
    if (totalChars > config.charBudget) {
      const overage = totalChars - config.charBudget
      this.logger.warn('Post-assembly budget overrun, trimming', {
        sessionId,
        totalChars,
        charBudget: config.charBudget,
        overage,
      })
      // Collect droppable indices: in included, not protected.
      // Priority-aware trimming: normal first, then high (if severe), never critical.
      const droppable = Array.from(included)
        .filter(idx => {
          if (idx >= protectedStart) return false
          const priority = messages[idx]?._thalamus?.pinPriority
          if (priority === 'critical') return false
          if (priority === 'high' && overage < 5000) return false
          return true
        })
        .map(idx => {
          const s = scoredByIndex.get(idx)
          const priority = messages[idx]?._thalamus?.pinPriority ?? 'normal'
          // Sort by priority (normal first) then by score
          const priorityRank = priority === 'high' ? 1 : 0
          return { idx, score: s?.luminance.composite ?? 0, chars: s?.estimatedChars ?? 0, priorityRank }
        })
        .sort((a, b) => {
          if (a.priorityRank !== b.priorityRank) return a.priorityRank - b.priorityRank
          return a.score - b.score
        })
      let trimmed = 0
      for (const d of droppable) {
        if (totalChars <= config.charBudget) break
        included.delete(d.idx)
        totalChars -= d.chars
        trimmed++
      }
      if (trimmed > 0) {
        this.logger.info('Budget trim complete', { sessionId, trimmed, newTotalChars: totalChars })
        // Re-run repair passes: trimming may have broken alternation or pairs
        for (let pass = 0; pass < 5; pass++) {
          const before = Array.from(included).sort((a, b) => a - b).join(',')
          this.ensureToolPairs(messages, included, protectedStart)
          this.ensureAlternation(messages, included, protectedStart)
          const after = Array.from(included).sort((a, b) => a - b).join(',')
          if (before === after) break
        }
        usedChars = Array.from(included).reduce((sum, idx) => {
          return sum + (scoredByIndex.get(idx)?.estimatedChars ?? 0)
        }, 0)
      }
    }

    // Merge included older messages with protected recent messages, in order
    const allIndices = [
      ...Array.from(included).sort((a, b) => a - b),
      ...Array.from({ length: messages.length - protectedStart }, (_, i) => protectedStart + i),
    ].filter(idx => !messages[idx]?._thalamus?.directiveDropped)

    const assembled: any[] = []
    let gapNotes = 0

    for (let j = 0; j < allIndices.length; j++) {
      const idx = allIndices[j]
      const prevIdx = j > 0 ? allIndices[j - 1] : idx - 1

      if (idx - prevIdx > 2 && j > 0) {
        const gapSize = idx - prevIdx - 1
        const gapMsg = messages[idx]
        if (gapMsg && Array.isArray(gapMsg.content)) {
          // Time-aware gap note (may include topic archive summary)
          const gapDesc = this.buildGapDescription(gapSize, prevIdx, idx, messages, sessionId)
          const noted = [
            { type: 'text', text: `[${gapDesc}]` },
            ...gapMsg.content,
          ]
          assembled.push({ ...gapMsg, content: noted })
          gapNotes++
          continue
        }
      }

      assembled.push(messages[idx])
    }

    const includedIndices = new Set<number>(allIndices)
    const scoredLookup = new Map(scored.map(s => [s.messageIndex, s]))
    let finalPinnedOverrides = 0
    for (const idx of included) {
      const s = scoredLookup.get(idx)
      if (s && messages[idx]?._thalamus?.pinned && s.luminance.composite < threshold) finalPinnedOverrides++
    }
    return { messages: assembled, gapNotes, includedIndices, charsUsed: usedChars, pinnedOverrides: finalPinnedOverrides }
  }

  private ensureAlternation(
    messages: any[],
    included: Set<number>,
    protectedStart: number,
  ): void {
    const sorted = Array.from(included).sort((a, b) => a - b)

    for (let i = 0; i < sorted.length - 1; i++) {
      const curr = sorted[i]
      const next = sorted[i + 1]
      if (messages[curr]?.role === messages[next]?.role) {
        for (let bridge = curr + 1; bridge < next; bridge++) {
          if (messages[bridge]?.role !== messages[curr]?.role && bridge < protectedStart) {
            if (this.tryAddBridge(messages, included, bridge, protectedStart)) break
          }
        }
      }
    }

    if (sorted.length > 0) {
      const lastOlder = sorted[sorted.length - 1]
      const firstRecent = protectedStart
      if (firstRecent < messages.length && messages[lastOlder]?.role === messages[firstRecent]?.role) {
        for (let bridge = lastOlder + 1; bridge < firstRecent; bridge++) {
          if (messages[bridge]?.role !== messages[lastOlder]?.role) {
            if (this.tryAddBridge(messages, included, bridge, protectedStart)) break
          }
        }
      }
    }
  }

  private tryAddBridge(
    messages: any[],
    included: Set<number>,
    bridge: number,
    protectedStart: number,
  ): boolean {
    const msg = messages[bridge]
    if (!msg) return false
    const content = Array.isArray(msg.content) ? msg.content : null
    if (!content) {
      included.add(bridge)
      return true
    }

    const hasToolUse = content.some((c: any) => c?.type === 'tool_use')
    const hasToolResult = content.some((c: any) => c?.type === 'tool_result')

    if (!hasToolUse && !hasToolResult) {
      included.add(bridge)
      return true
    }

    // Build maps to find partners anywhere in the array (not just adjacent).
    // After curation drops messages, partners are often non-consecutive.
    const toolUseIdxById = new Map<string, number>()
    const toolResultIdxById = new Map<string, number>()
    for (let i = 0; i < messages.length; i++) {
      const m = messages[i]
      if (!Array.isArray(m?.content)) continue
      for (const b of m.content) {
        if (b?.type === 'tool_use' && typeof b.id === 'string') toolUseIdxById.set(b.id, i)
        if (b?.type === 'tool_result' && typeof b.tool_use_id === 'string') toolResultIdxById.set(b.tool_use_id, i)
      }
    }

    // Check if tools are orphans (no matching partner anywhere).
    // If so, convert them to text to avoid breaking tool-pair invariants.
    let needsConversion = false
    for (const block of content) {
      if (block?.type === 'tool_use') {
        const partnerIdx = toolResultIdxById.get(block.id)
        if (partnerIdx === undefined) {
          needsConversion = true
          break
        }
      }
      if (block?.type === 'tool_result') {
        const partnerIdx = toolUseIdxById.get(block.tool_use_id)
        if (partnerIdx === undefined) {
          needsConversion = true
          break
        }
      }
    }

    if (needsConversion) {
      const newContent = content.map((block: any) => {
        if (block?.type === 'tool_use') {
          return {
            type: 'text',
            text: `[tool_use: ${block.name ?? 'unknown'} (${block.id})] ${JSON.stringify(block.input ?? {})}`,
          }
        }
        if (block?.type === 'tool_result') {
          const inner = typeof block.content === 'string'
            ? block.content
            : JSON.stringify(block.content)
          return {
            type: 'text',
            text: `[tool_result: ${block.tool_use_id}]:\n${inner}`,
          }
        }
        return block
      })
      msg.content = newContent
      included.add(bridge)
      return true
    }

    // All tools have valid partners — add the bridge and its actual partners
    for (const block of content) {
      if (block?.type === 'tool_use') {
        const partnerIdx = toolResultIdxById.get(block.id)
        if (partnerIdx !== undefined && partnerIdx < protectedStart) included.add(partnerIdx)
      }
      if (block?.type === 'tool_result') {
        const partnerIdx = toolUseIdxById.get(block.tool_use_id)
        if (partnerIdx !== undefined && partnerIdx < protectedStart) included.add(partnerIdx)
      }
    }

    included.add(bridge)
    return true
  }

  private ensureToolPairs(
    messages: any[],
    included: Set<number>,
    protectedStart: number,
  ): void {
    // Build bidirectional maps by tool_use_id so we can find the *actual*
    // partner even when compaction (or summary injection) makes pairs
    // non-consecutive.
    const toolUseIdxById = new Map<string, number>()
    const toolResultIdxById = new Map<string, number>()

    for (let i = 0; i < messages.length; i++) {
      const msg = messages[i]
      if (!Array.isArray(msg?.content)) continue
      for (const block of msg.content) {
        if (block?.type === 'tool_use' && typeof block.id === 'string') {
          toolUseIdxById.set(block.id, i)
        }
        if (block?.type === 'tool_result' && typeof block.tool_use_id === 'string') {
          toolResultIdxById.set(block.tool_use_id, i)
        }
      }
    }

    const idsInMessage = (msg: any, type: 'tool_use' | 'tool_result'): string[] => {
      if (!Array.isArray(msg?.content)) return []
      return msg.content
        .filter((c: any) => c?.type === type && typeof (type === 'tool_use' ? c.id : c.tool_use_id) === 'string')
        .map((c: any) => (type === 'tool_use' ? c.id : c.tool_use_id))
    }

    // Resolve tool_use messages: every tool_use must have its matching tool_result
    for (const idx of Array.from(included)) {
      if (idx >= protectedStart) continue
      const msg = messages[idx]
      const useIds = idsInMessage(msg, 'tool_use')
      if (useIds.length === 0) continue

      let allPaired = true
      for (const id of useIds) {
        const resultIdx = toolResultIdxById.get(id)
        if (resultIdx === undefined) {
          allPaired = false
          break
        }
        if (resultIdx < protectedStart && !included.has(resultIdx)) {
          included.add(resultIdx)
        }
      }
      if (!allPaired) {
        included.delete(idx)
      }
    }

    // Resolve tool_result messages: every tool_result must have its matching tool_use
    for (const idx of Array.from(included)) {
      if (idx >= protectedStart) continue
      const msg = messages[idx]
      const resultIds = idsInMessage(msg, 'tool_result')
      if (resultIds.length === 0) continue

      let allPaired = true
      for (const id of resultIds) {
        const useIdx = toolUseIdxById.get(id)
        if (useIdx === undefined) {
          allPaired = false
          break
        }
        if (useIdx < protectedStart && !included.has(useIdx)) {
          included.add(useIdx)
        }
      }
      if (!allPaired) {
        included.delete(idx)
      }
    }

    // Protected boundary: fix pairs that cross the protected/candidate line.
    // Scan ALL protected messages, not just messages[protectedStart], because
    // a tool pair may span the boundary without touching the first protected msg.
    // Case A: tool_result in protected region, tool_use in candidate region
    if (protectedStart > 0 && protectedStart < messages.length) {
      for (let i = protectedStart; i < messages.length; i++) {
        const msg = messages[i]
        for (const id of idsInMessage(msg, 'tool_result')) {
          const useIdx = toolUseIdxById.get(id)
          if (useIdx !== undefined && useIdx < protectedStart && !included.has(useIdx)) {
            included.add(useIdx)
          }
        }
      }
    }
    // Case B: tool_use in protected region, tool_result in candidate region
    if (protectedStart > 0 && protectedStart < messages.length) {
      for (let i = protectedStart; i < messages.length; i++) {
        const msg = messages[i]
        for (const id of idsInMessage(msg, 'tool_use')) {
          const resultIdx = toolResultIdxById.get(id)
          if (resultIdx !== undefined && resultIdx < protectedStart && !included.has(resultIdx)) {
            included.add(resultIdx)
          }
        }
      }
    }
  }

  private skipResult(messages: any[], durationMs: number, reason: string): CurationResult {
    return {
      messages: stripThalamusAnnotations(messages),
      meta: {
        originalCount: messages.length,
        curatedCount: messages.length,
        originalChars: 0,
        curatedChars: 0,
        compressed: 0,
        deduped: 0,
        dropped: 0,
        gapNotes: 0,
        durationMs,
        skipped: true,
        reason,
      },
    }
  }

  /**
   * Deep clone a message to prevent in-place mutations from leaking
   * to the caller (critical for Anthropic thinking signatures).
   */
  private extractProtectedWindow(messages: any[], cfg: CurationConfig): any[] {
    const windowSize = cfg.recentWindowSize ?? 8
    let start = Math.max(0, messages.length - windowSize)
    
    // Ensure the protected window starts with a user message.
    // Anthropic API requires the first message to be from the user.
    while (start > 0 && messages[start]?.role !== 'user') {
      start--
    }
    
    // Also ensure any tool_result in the window has its matching tool_use.
    // Build a set of tool_use IDs in the window, and tool_result IDs that need them.
    const window = messages.slice(start)
    const neededToolUseIds = new Set<string>()
    const presentToolUseIds = new Set<string>()
    
    for (const msg of window) {
      if (!Array.isArray(msg?.content)) continue
      for (const block of msg.content) {
        if (block?.type === 'tool_use' && block.id) {
          presentToolUseIds.add(block.id)
        }
        if (block?.type === 'tool_result' && block.tool_use_id) {
          neededToolUseIds.add(block.tool_use_id)
        }
      }
    }
    
    // Find missing tool_use IDs and include their messages
    const missingIds = [...neededToolUseIds].filter(id => !presentToolUseIds.has(id))
    if (missingIds.length > 0) {
      // Find the messages containing the missing tool_use IDs
      const extraMessages: any[] = []
      for (let i = start - 1; i >= 0; i--) {
        const msg = messages[i]
        if (!Array.isArray(msg?.content)) continue
        for (const block of msg.content) {
          if (block?.type === 'tool_use' && missingIds.includes(block.id)) {
            extraMessages.unshift(msg)
            break
          }
        }
      }
      // Prepend the extra messages to the window
      return [...extraMessages.map(m => deepCloneMessage(m)), ...window.map(m => deepCloneMessage(m))]
    }
    
    return window.map(m => deepCloneMessage(m))
  }

  /**
   * Extract TopicSummary[] from active topic clusters and archived topics.
   * Used to feed the CrossSessionTopicIndex after each curation pass.
   * Computes per-topic importance as the average luminance composite of
   * messages belonging to each topic.
   */
  private extractTopicSummaries(
    session: CurationSession,
    scored: ScoredMessage[],
  ): import('./types.js').TopicSummary[] {
    const summaries: import('./types.js').TopicSummary[] = []

    // Archived topics — have labels and summaries from async LLM calls
    for (const archive of session.topicArchive) {
      const keyTerms = archive.keyTerms ?? [...(archive.structured?.filesTouched ?? [])]
      // Estimate importance from archived topic's message range
      const importance = this.computeTopicImportance(
        archive.originalIndices, scored,
      )
      summaries.push({
        id: archive.id,
        label: archive.label || archive.summary?.slice(0, 50) || 'Untitled topic',
        summary: archive.summary || '',
        status: 'archived',
        keyTerms,
        importanceScore: importance,
        filesTouched: archive.structured?.filesTouched,
      })
    }

    // Active topic clusters — skip any that have already been archived
    // (archived topics remain in topicClusters until the session advances
    // past them, so we dedupe by ID to avoid duplicate index entries).
    const archivedIds = new Set(session.topicArchive.map(a => a.id))
    for (const cluster of session.topicClusters) {
      if (archivedIds.has(cluster.id)) continue
      const keyTerms = [...cluster.termSet].slice(0, 12)
      const importance = this.computeTopicImportance(
        cluster.messageIndices, scored,
      )
      // Heuristic: extract path-like terms from keyTerms so ongoing work
      // surfaces in file conflict detection before the topic is archived.
      const filesTouched = this.extractFilePathsFromTerms(keyTerms)
      summaries.push({
        id: cluster.id,
        label: cluster.label || keyTerms.slice(0, 3).join(' ') || `Topic ${cluster.id}`,
        summary: cluster.summary || `Working on: ${keyTerms.slice(0, 5).join(', ')}`,
        status: 'active',
        keyTerms,
        importanceScore: importance,
        filesTouched: filesTouched.length > 0 ? filesTouched : undefined,
      })
    }

    return summaries
  }

  /**
   * Heuristic extraction of file paths from topic key terms.
   * Scans terms for path-like strings (containing '/' or ending with
   * known extensions) so ongoing work surfaces in conflict detection
   * before the topic is archived.
   */
  private extractFilePathsFromTerms(terms: string[]): string[] {
    const files: string[] = []
    const extPattern = /\.(ts|tsx|js|jsx|py|rb|go|rs|java|kt|swift|c|cpp|h|hpp|cs|fs|scala|clj|erl|ex|php|pl|lua|r|m|mm|json|yaml|yml|toml|xml|md|txt|sql|sh|bash|zsh|fish|ps1|bat|cmd|dockerfile|makefile|gradle|svelte|vue|html|css|scss|sass|less|wasm)$/i
    for (const term of terms) {
      if (term.includes('/') || term.startsWith('./') || term.startsWith('../')) {
        files.push(term)
      } else if (extPattern.test(term) && term.length > 3) {
        files.push(term)
      }
    }
    return [...new Set(files)].slice(0, 8)
  }

  /**
   * Compute average luminance composite for messages belonging to a topic.
   * Returns 0 if no scored messages overlap.
   */
  private computeTopicImportance(
    messageIndices: number[],
    scored: ScoredMessage[],
  ): number {
    if (scored.length === 0) return 0.3
    // Compute session-wide average luminance as the fallback default
    const globalAvg = scored.reduce((sum, sm) => sum + sm.luminance.composite, 0) / scored.length
    if (messageIndices.length === 0) return globalAvg
    const indexSet = new Set(messageIndices)
    let total = 0
    let count = 0
    for (const sm of scored) {
      if (indexSet.has(sm.messageIndex)) {
        total += sm.luminance.composite
        count++
      }
    }
    return count > 0 ? total / count : globalAvg
  }

  private getSession(sessionId: string): CurationSession {
    let session = this.sessions.get(sessionId)
    if (!session) {
      session = {
        sessionId,
        toolUseMap: new Map(),
        pendingToolCalls: new Map(),
        lastCuratedAt: Date.now(),
        totalCurations: 0,
        topicClusters: [],
        topicArchive: [],
        intentSpans: [],
        dropHistory: [],
        lastScored: [],
        lastThreshold: 0,
        pinnedPatterns: [],
        thoughtCommandLog: [],
        dropDirectives: new Set(),
        collapseDirectives: new Map(),
        rerankerCache: { entries: new Map() },
      }
      this.sessions.set(sessionId, session)
    }
    return session!
  }

  /**
   * Compute which file-read tool results are the latest for each file.
   * Returns:
   *   - latestResultIndices: indices of tool_result messages that are the latest
   *     read of their file (protected from compression)
   *   - nonLatestToolUseIds: tool_use_ids whose results are NOT the latest read
   *     of their file (to be suppressed during scoring)
   */
  /**
   * Detect topic clusters in the message array using a sliding-window
   * Jaccard similarity approach.  A topic boundary is inferred at user-turn
   * boundaries where the overlap between the preceding N/2 messages and the
   * following N/2 messages drops below BOUNDARY_THRESHOLD.
   *
   * Clusters are stored on the session so async archiving can proceed.
   * Returns the clusters for this curation call.
   */
  private detectTopicClusters(sessionId: string, messages: any[]): TopicCluster[] {
    const WINDOW = 6          // sliding-window size (3 look-back + 3 look-ahead)
    const HALF = WINDOW / 2
    const BOUNDARY_THRESHOLD = 0.12  // Jaccard below this at a user turn → new topic

    const session = this.getSession(sessionId)

    // Cache short-circuit: per-turn topic clustering is expensive (O(n) term
    // extraction + sliding-window walk) and most curate() calls see the same
    // history with one new message appended. If the signature is unchanged
    // from the last call, return the cached clusters but still re-fire any
    // newly-eligible archive jobs (the existence-check inside fireTopicArchive
    // ensures idempotence).
    const sig = this.buildClusterCacheSignature(messages)
    if (
      session.clusterCache &&
      session.clusterCache.messageCount === messages.length &&
      session.clusterCache.signature === sig
    ) {
      const cached = session.clusterCache.clusters
      session.topicClusters = cached
      for (let k = 0; k < cached.length - 1; k++) {
        const c = cached[k]
        const existing = session.topicArchive.find(a => a.id === c.id)
        if (!existing && !c.asyncPending) {
          this.fireTopicArchive(sessionId, c, messages)
        }
      }
      return cached
    }

    // Build term sets per message
    const termSets: Set<string>[] = messages.map(msg => {
      const content = extractMessageContent(msg)
      return new Set(extractTerms(content))
    })

    const clusters: TopicCluster[] = []
    let current: TopicCluster = {
      id: 'topic-0',
      messageIndices: [],
      termSet: new Set(),
      asyncPending: false,
    }

    for (let i = 0; i < messages.length; i++) {
      // Only consider a boundary at user turns after we have enough context
      if (i >= WINDOW && messages[i]?.role === 'user' && current.messageIndices.length >= 2) {
        const prevSet = new Set<string>()
        const nextSet = new Set<string>()
        for (let j = i - WINDOW; j < i - HALF; j++) {
          if (j >= 0) for (const t of termSets[j]) prevSet.add(t)
        }
        for (let j = i - HALF; j < i; j++) {
          if (j >= 0) for (const t of termSets[j]) nextSet.add(t)
        }
        const unionSize = new Set([...prevSet, ...nextSet]).size
        const intersectSize = [...prevSet].filter(t => nextSet.has(t)).length
        const jaccard = unionSize > 0 ? intersectSize / unionSize : 1.0

        if (jaccard < BOUNDARY_THRESHOLD) {
          clusters.push(current)
          current = {
            id: `topic-${clusters.length}`,
            messageIndices: [],
            termSet: new Set(),
            asyncPending: false,
          }
        }
      }
      current.messageIndices.push(i)
      for (const t of termSets[i]) current.termSet.add(t)
    }
    if (current.messageIndices.length > 0) clusters.push(current)

    // Persist on session; fire async archiving for completed (non-last) clusters.
    // Update the per-session cache so the next curate() with an unchanged
    // history can short-circuit at the top of this method.
    session.topicClusters = clusters
    session.clusterCache = {
      messageCount: messages.length,
      signature: sig,
      clusters,
    }
    for (let k = 0; k < clusters.length - 1; k++) {
      const c = clusters[k]
      const existing = session.topicArchive.find(a => a.id === c.id)
      if (!existing && !c.asyncPending) {
        this.fireTopicArchive(sessionId, c, messages)
      }
    }
    return clusters
  }

  /**
   * Strip reasoning/thinking artifacts some models emit despite instructions.
   * Mirrors SmartCompactionEngine.stripThinkingArtifacts.
   */
  private static stripThinkingArtifacts(text: string): string {
    return text
      .replace(/\*\*[A-Z][^*\n]{8,80}\*\*:?\s*\n*/g, '')
      .replace(/<think>[\s\S]*?<\/think>\s*/gi, '')
      .replace(/Here's a thinking process:[\s\S]*/i, '')
      .replace(/\d+\.\s*Analyze User Input:[\s\S]*/i, '')
      .replace(/\d+\.\s*Task:[\s\S]*/i, '')
      .trim()
  }

  /**
   * Build the input transcript fed to the topic-archive LLM.
   *
   * Tool calls collapse to `[Tool: name args=keys]` and tool results to
   * `[Result: name status=ok|err size=N]`. Raw tool output is suppressed —
   * its content biased the previous prompt toward summarizing returned
   * file bodies instead of conversational intent.
   */
  static shapeArchiveInput(indices: number[], messages: any[]): string {
    const lines: string[] = []
    let toolNameById = new Map<string, string>()
    for (const idx of indices.slice(0, 40)) {
      const msg = messages[idx]
      if (!msg) continue
      if (msg.role === 'assistant' && Array.isArray(msg.content)) {
        const parts: string[] = []
        for (const block of msg.content) {
          if (block?.type === 'text' && typeof block.text === 'string') {
            const t = block.text.trim()
            if (t) parts.push(t.slice(0, 400))
          } else if (block?.type === 'tool_use' && block.name) {
            toolNameById.set(block.id, block.name)
            const argKeys = block.input && typeof block.input === 'object'
              ? Object.keys(block.input).slice(0, 4).join(',')
              : ''
            parts.push(`[Tool: ${block.name}${argKeys ? ` args=${argKeys}` : ''}]`)
          }
        }
        if (parts.length > 0) lines.push(`Cassi: ${parts.join(' ')}`)
        continue
      }
      if (msg.role === 'user' && Array.isArray(msg.content)) {
        const parts: string[] = []
        for (const block of msg.content) {
          if (block?.type === 'tool_result') {
            const name = toolNameById.get(block.tool_use_id) ?? 'tool'
            const status = block.is_error ? 'err' : 'ok'
            const bodyLen = typeof block.content === 'string'
              ? block.content.length
              : Array.isArray(block.content)
                ? block.content.reduce((n: number, c: any) => n + (typeof c?.text === 'string' ? c.text.length : 0), 0)
                : 0
            parts.push(`[Result: ${name} status=${status} size=${bodyLen}]`)
          } else if (block?.type === 'text' && typeof block.text === 'string') {
            const t = block.text.trim()
            if (t) parts.push(t.slice(0, 400))
          }
        }
        if (parts.length > 0) lines.push(`User: ${parts.join(' ')}`)
        continue
      }
      const role = msg.role === 'user' ? 'User' : 'Cassi'
      const text = extractMessageContent(msg).trim().slice(0, 400)
      if (text) lines.push(`${role}: ${text}`)
    }
    return lines.join('\n')
  }

  /**
   * Parse tagged-line output from the topic-archive LLM. Tolerant of
   * partial output: any field that fails to parse is simply empty in the
   * result. Callers check hasStructuredContent() to decide whether to
   * persist the structured payload.
   */
  static parseStructuredArchive(raw: string): TopicArchiveStructured {
    const result: TopicArchiveStructured = { goal: '', decisions: [], filesTouched: [], openThreads: [] }
    if (!raw) return result

    const lines = raw.split('\n').map(l => l.replace(/\r$/, ''))
    type Field = 'goal' | 'decisions' | 'files' | 'open' | null
    let current: Field = null

    const tagMap: Record<string, Field> = {
      goal: 'goal',
      decisions: 'decisions',
      decision: 'decisions',
      files: 'files',
      'files touched': 'files',
      'files-touched': 'files',
      open: 'open',
      'open threads': 'open',
      'open-threads': 'open',
      unresolved: 'open',
    }

    for (const line of lines) {
      const tagMatch = line.match(/^([a-z][a-z _-]{0,30}):\s*(.*)$/i)
      if (tagMatch) {
        const tag = tagMatch[1].trim().toLowerCase()
        const inline = tagMatch[2].trim()
        const field = tagMap[tag]
        if (field) {
          current = field
          if (field === 'goal' && inline) result.goal = inline
          else if (inline) {
            const target = field === 'decisions' ? result.decisions
              : field === 'files' ? result.filesTouched
              : result.openThreads
            target.push(inline)
          }
          continue
        }
        current = null
        continue
      }
      const bulletMatch = line.match(/^\s*[-*•]\s+(.+)$/)
      if (bulletMatch && current && current !== 'goal') {
        const value = bulletMatch[1].trim()
        const target = current === 'decisions' ? result.decisions
          : current === 'files' ? result.filesTouched
          : result.openThreads
        if (value) target.push(value)
      }
    }

    result.goal = result.goal.trim().slice(0, 240)
    result.decisions = result.decisions.map(d => d.slice(0, 200)).slice(0, 8)
    result.filesTouched = result.filesTouched.map(f => f.slice(0, 200)).slice(0, 12)
    result.openThreads = result.openThreads.map(o => o.slice(0, 200)).slice(0, 6)
    return result
  }

  /** True when the parsed archive has at least one usable field. */
  static hasStructuredContent(s: TopicArchiveStructured): boolean {
    return Boolean(s.goal) || s.decisions.length > 0 || s.filesTouched.length > 0 || s.openThreads.length > 0
  }

  /**
   * Build a heuristic label from the cluster's messages when LLM summarization
   * fails or produces garbage.
   */
  private heuristicTopicLabel(cluster: TopicCluster, messages: any[]): string {
    const userMsgs = cluster.messageIndices
      .map(idx => messages[idx])
      .filter(m => m?.role === 'user')
      .map(m => extractMessageContent(m).trim())
    const seed = userMsgs.find(t => t.length > 10)
    if (seed) return seed.split(/[.!?\n]/)[0].slice(0, 60)
    return Array.from(cluster.termSet).slice(0, 4).join(', ').slice(0, 60)
  }

  /**
   * Cheap signature for the message array used by the topic-cluster cache.
   * Boundaries depend on content of every message but in practice only the
   * tail changes turn-to-turn (new messages append). We sample length + role
   * + a small content prefix from the last few messages — enough to detect
   * append, edit, or roll-back without rehashing the whole array.
   */
  private buildClusterCacheSignature(messages: any[]): string {
    const n = messages.length
    if (n === 0) return '0:'
    // Sample the tail (last 4) plus message count. Hash a short prefix of
    // each sampled message's content + role.
    const samples: string[] = [String(n)]
    const start = Math.max(0, n - 4)
    for (let i = start; i < n; i++) {
      const msg = messages[i]
      const role = msg?.role ?? '?'
      const content = extractMessageContent(msg)
      // 64-char prefix is enough to distinguish appends from edits while
      // staying cheap. extractMessageContent already handles complex content.
      samples.push(`${i}:${role}:${content.length}:${content.slice(0, 64)}`)
    }
    return samples.join('|')
  }

  private fireTopicArchive(sessionId: string, cluster: TopicCluster, messages: any[]): void {
    if (!this.handleFactory || cluster.asyncPending) return
    cluster.asyncPending = true

    const transcript = ThalamusModule.shapeArchiveInput(cluster.messageIndices, messages)
    const keyTerms = Array.from(cluster.termSet).slice(0, 10).join(', ')

    this.handleFactory({ tier: 'background', purpose: 'topic-archive', sessionId })
      .then(async (handle) => {
        try {
          const result = await handle.complete(
            [{
              role: 'user',
              content:
                `I need a structured archive of this conversation segment so I can carry it forward after compaction. ` +
                `Read the segment and emit four tagged fields. Focus on what I was *trying* to do and what I *decided* — ` +
                `do not summarize tool output content.\n\n` +
                `Output format (tagged lines, no markdown, no prose around it):\n` +
                `goal: <one line — what I was attempting>\n` +
                `decisions:\n- <choice that needs to survive>\n- <another>\n` +
                `files:\n- <path> (<status: created|modified|read|deleted>)\n- <another>\n` +
                `open:\n- <unresolved question or work that did not finish>\n- <another>\n\n` +
                `If a section has nothing to record, write the tag with no list items. Never invent decisions or files that aren't in the segment.\n\n` +
                `Key terms in this segment: ${keyTerms}\n\nSegment:\n${transcript}`,
            }],
            {
              model: handle.model,
              maxTokens: 400,
              temperature: 0.2,
              systemPrompt:
                'I am Cassi archiving my own conversation for future context. ' +
                'I emit only the four requested tagged fields, no other prose. ' +
                'I never include thinking, reasoning, or commentary outside the tags.',
              thinking: 'none',
              reasoning: 'none',
              source: 'thalamus-topic-archive',
              trigger: 'background',
              sessionId,
            },
          )
          const raw = result.response?.trim() ?? ''
          const cleaned = ThalamusModule.stripThinkingArtifacts(raw)
          const structured = ThalamusModule.parseStructuredArchive(cleaned)

          let summary = structured.goal
          if (!summary || summary.length > 300 || /thinking process|Analyze User Input/i.test(summary)) {
            summary = this.heuristicTopicLabel(cluster, messages)
          }

          const label = summary.split('.')[0]?.slice(0, 60) || `Topic ${cluster.id}`
          cluster.summary = summary
          cluster.label = label
          cluster.asyncPending = false

          const session = this.getSession(sessionId)
          if (!session.topicArchive.find(a => a.id === cluster.id)) {
            session.topicArchive.push({
              id: cluster.id,
              label,
              summary,
              originalIndices: cluster.messageIndices,
              archivedAt: Date.now(),
              keyTerms: Array.from(cluster.termSet).slice(0, 8),
              structured: ThalamusModule.hasStructuredContent(structured) ? structured : undefined,
            })
          }
        } catch {
          cluster.asyncPending = false
        } finally {
          handle.release()
        }
      })
      .catch(() => { cluster.asyncPending = false })
  }

    /**
   * Topic-aware read suppression.
   * Within each topic cluster, only the latest read of a given file is kept.
   * Reads of the same file in DIFFERENT topics are preserved — a new topic
   * may legitimately re-read a file that was read in an earlier phase.
   */
  private computeReadSuppression(
    messages: any[],
    topicClusters?: TopicCluster[],
  ): {
    latestResultIndices: Set<number>
    nonLatestToolUseIds: Set<string>
  } {
    const readPattern = /^(Read|cassi_read|cassi_file.*read|mcp__\w+__read)$/i
    const toolUseIdToFile = new Map<string, string>()

    // Build O(1) message-index -> topic-id lookup so the inner loops stay fast
    const idxToTopic = new Map<number, string>()
    if (topicClusters) {
      for (const c of topicClusters) {
        for (const idx of c.messageIndices) idxToTopic.set(idx, c.id)
      }
    }

    // Pass 1: map read tool_use ids to their file paths
    for (let i = 0; i < messages.length; i++) {
      const msg = messages[i]
      if (!Array.isArray(msg?.content)) continue
      for (const block of msg.content) {
        if (block?.type === 'tool_use' && block.id) {
          const toolName = block.name ?? ''
          if (readPattern.test(toolName)) {
            const fp = block.input?.filePath ?? block.input?.path ?? block.input?.file_path ?? ''
            if (fp) toolUseIdToFile.set(block.id, fp)
          }
        }
      }
    }

    // Build per-topic (or global fallback) fileRead maps
    const getTopicId = (msgIdx: number): string =>
      idxToTopic.get(msgIdx) ?? 'global'

    // Pass 2: track the latest tool_result index for each (topicId, file) pair
    const latestResultByTopicFile = new Map<string, number>()
    for (let i = 0; i < messages.length; i++) {
      const msg = messages[i]
      if (!Array.isArray(msg?.content)) continue
      for (const block of msg.content) {
        if (block?.type === 'tool_result' && block.tool_use_id) {
          const fp = toolUseIdToFile.get(block.tool_use_id)
          if (fp) {
            const key = `${getTopicId(i)}::${fp}`
            latestResultByTopicFile.set(key, i)
          }
        }
      }
    }

    // Pass 3: identify non-latest tool_use ids (within their topic)
    const nonLatestToolUseIds = new Set<string>()
    for (let i = 0; i < messages.length; i++) {
      const msg = messages[i]
      if (!Array.isArray(msg?.content)) continue
      for (const block of msg.content) {
        if (block?.type === 'tool_result' && block.tool_use_id) {
          const fp = toolUseIdToFile.get(block.tool_use_id)
          if (fp) {
            const key = `${getTopicId(i)}::${fp}`
            const latestIndex = latestResultByTopicFile.get(key)
            if (latestIndex !== undefined && latestIndex !== i) {
              nonLatestToolUseIds.add(block.tool_use_id)
            }
          }
        }
      }
    }

    return {
      latestResultIndices: new Set(latestResultByTopicFile.values()),
      nonLatestToolUseIds,
    }
  }

  /**
  /**
   * Identifies file-read messages whose results should survive compression
   * because no subsequent write has invalidated them.
   *
   * Uses MnemicField file_read and file_version engrams as the source of truth
   * instead of regex-based message scanning. For each file path read in this
   * session, checks whether a more recent write exists — if not, the read
   * result is "live" and should be preserved.
   *
   * Returned indices point at the user message containing the tool_result.
   * Pass this set to ToolResultCompressor.compress as protectedIndices so
   * those results survive even when they fall outside the recentWindow.
   *
   * Falls back gracefully to the old regex-based approach if MnemicField
   * is unavailable (best-effort).
   */
  private computeLiveReadIndices(sessionId: string, messages: any[], recentWindowSize: number): Map<number, string> {
    // Build tool_use_id → message index map from tool_result messages
    const useIdToResultIdx = new Map<string, number>()
    for (let i = 0; i < messages.length; i++) {
      const msg = messages[i]
      if (msg?.role !== 'user' || !Array.isArray(msg.content)) continue
      for (const block of msg.content) {
        if (block?.type === 'tool_result' && block.tool_use_id) {
          useIdToResultIdx.set(block.tool_use_id, i)
        }
      }
    }

    // Build tool_name → filePath map from tool_use messages
    const useIdToPath = new Map<string, string>()
    const readPattern = /^(Read|cassi_read|cassi_file.*read|mcp__\\w+__read)$/i
    for (let i = 0; i < messages.length; i++) {
      const msg = messages[i]
      if (msg?.role !== 'assistant' || !Array.isArray(msg.content)) continue
      for (const block of msg.content) {
        if (block?.type !== 'tool_use' || !block.id) continue
        const toolName = block.name ?? ''
        const fp = block.input?.filePath ?? block.input?.path ?? block.input?.file_path ?? ''
        if (!fp) continue
        if (readPattern.test(toolName)) {
          useIdToPath.set(block.id, fp)
        }
      }
    }

    // Query MnemicField for file_read engrams scoped to this session
    let livePaths = new Set<string>()
    if (this.mnemicField) {
      const sessionFileReads = this.getSessionFileReadPaths(sessionId)
      // For each read path, check if there's a newer write
      const fileVersionTimestamps = this.getLatestFileVersionTimestamps([...sessionFileReads.keys()])
      for (const [fp, readTs] of sessionFileReads) {
        const writeTs = fileVersionTimestamps.get(fp)
        if (writeTs === undefined || readTs > writeTs) {
          livePaths.add(fp)
        }
      }
    } else {
      // Fallback: use old regex-based write detection
      const writePattern = /^(write|edit|multiedit|notebookedit|cassi_write|cassi_edit|serena_replace_content|serena_replace_symbol_body|serena_insert_after_symbol|serena_insert_before_symbol|mcp__\w+__(write|edit|multiedit))$/i
      const writePaths = new Set<string>()
      for (let i = 0; i < messages.length; i++) {
        const msg = messages[i]
        if (msg?.role !== 'assistant' || !Array.isArray(msg.content)) continue
        for (const block of msg.content) {
          if (block?.type !== 'tool_use' || !block.id) continue
          const toolName = block.name ?? ''
          const fp = block.input?.filePath ?? block.input?.path ?? block.input?.file_path ?? ''
          if (!fp) continue
          if (writePattern.test(toolName)) writePaths.add(fp)
        }
      }
      // Use all read paths as live (conservative fallback)
      for (const fp of useIdToPath.values()) {
        if (!writePaths.has(fp)) livePaths.add(fp)
      }
    }

    // Map live paths back to message indices
    const live = new Map<number, string>()
    const horizon = Math.max(1, recentWindowSize * 2)
    const minIdx = Math.max(0, messages.length - horizon)
    for (const [useId, fp] of useIdToPath) {
      if (!livePaths.has(fp)) continue
      const resultIdx = useIdToResultIdx.get(useId)
      if (resultIdx !== undefined && resultIdx >= minIdx) {
        live.set(resultIdx, fp)
      }
    }

    return live
  }

  /**
   * Query the MnemicField for file_read engrams in a specific session.
   * Returns a map of filePath → timestamp (Unix ms) for each file path
   * that has been read in the given session.
   */
  private getSessionFileReadPaths(sessionId: string): Map<string, number> {
    const paths = new Map<string, number>()
    if (!this.mnemicField || !sessionId) return paths
    // List file_read engrams and filter by sessionId in metadata.
    // Caps at 500 to bound cost; a single session rarely has more than
    // a few dozen file reads.
    const reads = this.mnemicField.list(500, 'file_read')
    for (const read of reads) {
      const meta = read.metadata as Record<string, unknown> | undefined
      if (meta?.sessionId !== sessionId) continue
      const fp = meta?.filePath as string | undefined
      if (!fp) continue
      // Keep the latest timestamp per path
      const existing = paths.get(fp)
      if (existing === undefined || read.t > existing) {
        paths.set(fp, read.t)
      }
    }
    return paths
  }

  /**
   * Get the latest file_version engram timestamp for each file path.
   * Returns a map of filePath → timestamp (Unix ms).
   */
  private getLatestFileVersionTimestamps(filePaths: string[]): Map<string, number> {
    const timestamps = new Map<string, number>()
    if (!this.mnemicField || filePaths.length === 0) return timestamps
    const pathSet = new Set(filePaths)
    const versions = this.mnemicField.list(500, 'file_version')
    for (const version of versions) {
      const meta = version.metadata as Record<string, unknown> | undefined
      const fp = meta?.filePath as string | undefined
      if (!fp || !pathSet.has(fp)) continue
      const existing = timestamps.get(fp)
      if (existing === undefined || version.t > existing) {
        timestamps.set(fp, version.t)
      }
    }
    return timestamps
  }

  /**
   * Zero out luminance scores for non-latest file reads.
   * Both the tool_result and its paired tool_use are suppressed so that
   * assembly drops them entirely instead of keeping a summary.
   */
  private suppressRedundantReads(
    scored: ScoredMessage[],
    messages: any[],
    nonLatestToolUseIds: Set<string>,
  ): number {
    let suppressed = 0

    for (const sm of scored) {
      const msg = messages[sm.messageIndex]
      if (!Array.isArray(msg?.content)) continue

      const isNonLatest = msg.content.some((block: any) => {
        if (block?.type === 'tool_result' && nonLatestToolUseIds.has(block.tool_use_id)) {
          return true
        }
        if (block?.type === 'tool_use' && nonLatestToolUseIds.has(block.id)) {
          return true
        }
        return false
      })

      if (isNonLatest) {
        sm.luminance = {
          novelty: 0,
          urgency: 0,
          relevance: 0,
          sourceCredibility: 0,
          cognitiveResonance: 0,
          strategicImportance: 0,
          composite: 0,
        }
        suppressed++
      }
    }

    return suppressed
  }

  private evictStaleSessions(): void {
    const now = Date.now()
    for (const [id, session] of this.sessions) {
      if (now - session.lastCuratedAt > SESSION_EVICT_MS) {
        this.sessions.delete(id)
        this.temporalRegistries.delete(id)
        if (this.cachedBrainContext?.sessionId === id) {
          this.cachedBrainContext = null
        }
      }
    }
    // Periodic file_read pruning — prevents unbounded growth.
    // Runs on the same timer as session eviction (hourly).
    if (this.mnemicField) {
      try {
        const pruned = this.mnemicField.pruneFileReads()
        if (pruned > 0) {
          this.logger.debug('Pruned stale file_read engrams', { pruned })
        }
      } catch { /* best-effort */ }
    }
  }

  /**
   * Build a description for a run of omitted turns.
   *
   * If a topic archive covering this gap has structured fields populated by
   * the topic-archive LLM, emit a multi-line `<archived-segment>` block
   * containing goal, decisions, files, and open threads. Otherwise emit the
   * legacy one-liner — used during the LLM-pending window and as a graceful
   * degradation when parsing fails.
   */
  private buildGapDescription(
    gapSize: number,
    fromIdx: number,
    toIdx: number,
    messages: any[],
    sessionId?: string,
  ): string {
    const turnsLabel = `${gapSize} turn${gapSize > 1 ? 's' : ''}`
    let elapsedLabel = ''
    const fromTs = messages[fromIdx]?._thalamus?.ts
    const toTs = messages[toIdx]?._thalamus?.ts
    if (fromTs && toTs) {
      const elapsed = new Date(toTs).getTime() - new Date(fromTs).getTime()
      if (elapsed > 0) elapsedLabel = formatGapDuration(elapsed)
    }
    let toolCalls = 0
    for (let i = fromIdx + 1; i < toIdx; i++) {
      const slotType = messages[i]?._thalamus?.slot
      if (slotType === 'tool_call' || slotType === 'tool_result') toolCalls++
    }
    const logicalTools = Math.ceil(toolCalls / 2)

    const matchingArchive = sessionId
      ? this.getSession(sessionId).topicArchive.find(a =>
          a.originalIndices.some(idx => idx > fromIdx && idx < toIdx)
        )
      : undefined

    if (matchingArchive?.structured && ThalamusModule.hasStructuredContent(matchingArchive.structured)) {
      return ThalamusModule.renderStructuredGap(turnsLabel, elapsedLabel, logicalTools, matchingArchive.structured)
    }

    // Enriched gap: include tool-chain metadata so the model knows what was
    // accomplished in the dropped segment. This prevents re-exploration loops
    // where the agent re-reads files or re-runs commands it already executed.
    const toolMeta = this.extractGapToolMetadata(messages, fromIdx, toIdx)

    const parts = [turnsLabel]
    if (elapsedLabel) parts.push(`~${elapsedLabel}`)

    // Include tool metadata if available
    if (toolMeta.toolsUsed.length > 0) {
      parts.push(`tools: ${toolMeta.toolsUsed.join(', ')}`)
    }
    if (toolMeta.filesRead.length > 0) {
      parts.push(`read: ${toolMeta.filesRead.slice(0, 6).join(', ')}`)
    }
    if (toolMeta.filesWritten.length > 0) {
      parts.push(`wrote: ${toolMeta.filesWritten.slice(0, 4).join(', ')}`)
    }
    if (toolMeta.errors.length > 0) {
      parts.push(`errors: ${toolMeta.errors.slice(0, 3).join('; ')}`)
    }
    if (toolMeta.keyFindings.length > 0) {
      parts.push(`found: ${toolMeta.keyFindings.slice(0, 3).join('; ')}`)
    }

    if (matchingArchive) {
      const brief = matchingArchive.summary.slice(0, 100)
      parts.push(`topic: ${matchingArchive.label} — ${brief}`)
    }
    parts.push('omitted')
    return parts.join(' · ')
  }

  /**
   * Render a structured topic archive as an XML-tagged block. Empty fields
   * are skipped — partial output is still useful, so we never emit an
   * empty section that would waste tokens.
   */
  static renderStructuredGap(
    turnsLabel: string,
    elapsedLabel: string,
    logicalTools: number,
    s: TopicArchiveStructured,
  ): string {
    const attrs = [`turns="${turnsLabel.split(' ')[0]}"`]
    if (elapsedLabel) attrs.push(`elapsed="${elapsedLabel}"`)
    if (logicalTools > 0) attrs.push(`tools="${logicalTools}"`)
    const lines: string[] = [`<archived-segment ${attrs.join(' ')}>`]
    if (s.goal) lines.push(`  <goal>${escapeXml(s.goal)}</goal>`)
    if (s.decisions.length > 0) {
      lines.push(`  <decisions>`)
      for (const d of s.decisions) lines.push(`    - ${escapeXml(d)}`)
      lines.push(`  </decisions>`)
    }
    if (s.filesTouched.length > 0) {
      lines.push(`  <files-touched>`)
      for (const f of s.filesTouched) lines.push(`    - ${escapeXml(f)}`)
      lines.push(`  </files-touched>`)
    }
    if (s.openThreads.length > 0) {
      lines.push(`  <open-threads>`)
      for (const o of s.openThreads) lines.push(`    - ${escapeXml(o)}`)
      lines.push(`  </open-threads>`)
    }
    lines.push(`</archived-segment>`)
    return lines.join('\n')
  }

  /**
   * Compute an adaptive protected window size based on tool-chain density.
   *
   * When the recent segment has a high ratio of tool_call/tool_result messages
   * (i.e., the agent is in a long tool chain with minimal assistant prose),
   * the fixed `recentWindowSize` is too small — it covers only 2-3 tool rounds.
   * This causes the model to lose context about what it already did and repeat
   * tool calls (the "tool loop" problem).
   *
   * Strategy: scan the last `baseWindow * 3` messages for tool density. If >60%
   * are tool pairs, expand 1.5x; >40%, expand 1.25x. The cap is intentionally
   * conservative — live-read protection (computeLiveReadIndices) handles the
   * "I read the file 20 messages ago and still need it" case without forcing
   * a wide window over every recent tool result.
   */
  private computeAdaptiveWindow(messages: any[], baseWindow: number): number {
    if (messages.length <= baseWindow) return messages.length

    const scanRange = Math.min(baseWindow * 3, messages.length)
    const scanStart = messages.length - scanRange
    let toolCount = 0
    let total = 0

    for (let i = scanStart; i < messages.length; i++) {
      const annotation: ThalamusAnnotation | undefined = messages[i]?._thalamus
      if (!annotation) continue
      const slot = annotation.slot
      if (slot === 'tool_call' || slot === 'tool_result') {
        toolCount++
      }
      total++
    }

    if (total === 0) return baseWindow

    const toolDensity = toolCount / total

    if (toolDensity > 0.6) {
      const expanded = Math.min(Math.ceil(baseWindow * 1.5), messages.length)
      this.logger.debug('Adaptive window: tool-dense segment detected, expanding protected window', {
        baseWindow,
        expanded,
        toolDensity: toolDensity.toFixed(2),
        total,
        toolCount,
      })
      return expanded
    }

    if (toolDensity > 0.4) {
      const expanded = Math.min(Math.ceil(baseWindow * 1.25), messages.length)
      this.logger.debug('Adaptive window: moderate tool density, modestly expanding', {
        baseWindow,
        expanded,
        toolDensity: toolDensity.toFixed(2),
      })
      return expanded
    }

    return baseWindow
  }

  /**
   * Cap the protected segment so its char total does not exceed `protectedCap`.
   * Walks newest-first, accumulating estimated chars; when adding the next
   * (older) protected message would exceed the cap, stops and returns that
   * boundary as the new protectedStart.
   *
   * Floor: always keeps the last 2 messages protected, even if they alone
   * exceed the cap. This preserves the in-flight tool_use+tool_result pair
   * the model is mid-turn on.
   *
   * Demoted messages (those raised out of protection) become candidates in
   * assembleByThreshold and survive only if their composite ignites. This is
   * what makes charBudget a real ceiling rather than a lower-bound suggestion.
   */
  private capProtectedWindow(
    scored: ScoredMessage[],
    protectedStart: number,
    totalLength: number,
    protectedCap: number,
  ): number {
    if (protectedStart >= totalLength) return protectedStart

    const charsByIdx = new Map<number, number>()
    for (const s of scored) charsByIdx.set(s.messageIndex, s.estimatedChars)

    let totalProtectedChars = 0
    for (let i = protectedStart; i < totalLength; i++) {
      totalProtectedChars += charsByIdx.get(i) ?? 0
    }
    if (totalProtectedChars <= protectedCap) return protectedStart

    const minProtectedStart = Math.max(protectedStart, totalLength - 2)
    let chars = 0
    let newStart = totalLength
    for (let i = totalLength - 1; i >= protectedStart; i--) {
      const sz = charsByIdx.get(i) ?? 0
      if (i >= minProtectedStart) {
        chars += sz
        newStart = i
        continue
      }
      if (chars + sz > protectedCap) break
      chars += sz
      newStart = i
    }

    if (newStart !== protectedStart) {
      this.logger.debug('Protected window capped to budget*0.5', {
        originalStart: protectedStart,
        cappedStart: newStart,
        originalChars: totalProtectedChars,
        cappedChars: chars,
        cap: protectedCap,
      })
    }

    return newStart
  }

  /**
   * Extract tool-chain metadata from a gap segment for enriched gap descriptions.
   * Scans dropped messages for tool names, file paths, errors, and key findings.
   * This is purely heuristic — no LLM call needed.
   */
  private extractGapToolMetadata(
    messages: any[],
    fromIdx: number,
    toIdx: number,
  ): {
    toolsUsed: string[]
    filesRead: string[]
    filesWritten: string[]
    errors: string[]
    keyFindings: string[]
  } {
    const toolsUsed = new Set<string>()
    const filesRead: string[] = []
    const filesWritten: string[] = []
    const errors: string[] = []
    const keyFindings: string[] = []

    const seenFilesRead = new Set<string>()
    const seenFilesWritten = new Set<string>()

    for (let i = fromIdx + 1; i < toIdx; i++) {
      const msg = messages[i]
      if (!msg) continue
      const annotation: ThalamusAnnotation | undefined = msg._thalamus
      const slot = annotation?.slot

      // Extract from tool_use blocks (tool_call messages)
      if (slot === 'tool_call' || (Array.isArray(msg.content) && msg.content.some((c: any) => c?.type === 'tool_use'))) {
        if (Array.isArray(msg.content)) {
          for (const block of msg.content) {
            if (block?.type === 'tool_use') {
              const toolName = block.name ?? ''
              if (toolName) toolsUsed.add(toolName)

              // Extract file paths from tool inputs
              const input = block.input
              if (input && typeof input === 'object') {
                const filePath = extractFilePath(input as Record<string, unknown>)
                if (filePath) {
                  if (isWriteTool(toolName)) {
                    if (!seenFilesWritten.has(filePath)) {
                      seenFilesWritten.add(filePath)
                      filesWritten.push(shortenPath(filePath))
                    }
                  } else if (isReadTool(toolName)) {
                    if (!seenFilesRead.has(filePath)) {
                      seenFilesRead.add(filePath)
                      filesRead.push(shortenPath(filePath))
                    }
                  }
                }
                // Extract search patterns
                const pattern = extractSearchTarget(input as Record<string, unknown>)
                if (pattern && pattern.length > 2 && pattern.length < 80) {
                  keyFindings.push(`searched "${pattern}"`)
                }
                // Extract command from bash
                if (isShellTool(toolName) && (input as any).command) {
                  const cmd = String((input as any).command).split('\n')[0]?.slice(0, 60)
                  if (cmd) toolsUsed.add(`${toolName}: ${cmd}`)
                }
              }
            }
          }
        }
      }

      // Extract from tool_result blocks
      if (slot === 'tool_result' || (Array.isArray(msg.content) && msg.content.some((c: any) => c?.type === 'tool_result'))) {
        if (annotation?.tool?.isError) {
          if (Array.isArray(msg.content)) {
            for (const block of msg.content) {
              if (block?.type === 'tool_result') {
                const text = typeof block.content === 'string' ? block.content : ''
                const firstLine = text.split('\n')[0]?.slice(0, 80) ?? ''
                if (firstLine && errors.length < 3) {
                  errors.push(firstLine)
                }
              }
            }
          }
        } else {
          // Extract key findings from successful results
          if (Array.isArray(msg.content)) {
            for (const block of msg.content) {
              if (block?.type === 'tool_result') {
                const text = typeof block.content === 'string' ? block.content : ''
                // Look for line-number references (e.g., "42:" in code output)
                const lineRef = text.match(/^(\S+):(\d+)/m)
                if (lineRef) {
                  const finding = `${lineRef[1]}:${lineRef[2]}`
                  if (keyFindings.length < 5 && !keyFindings.some(f => f.includes(finding))) {
                    keyFindings.push(finding)
                  }
                }
              }
            }
          }
        }
      }
    }

    return {
      toolsUsed: Array.from(toolsUsed).slice(0, 8),
      filesRead: filesRead.slice(0, 8),
      filesWritten: filesWritten.slice(0, 4),
      errors: errors.slice(0, 3),
      keyFindings: keyFindings.slice(0, 4),
    }
  }

  /**
   * Detect tool repetition — same (tool, target) appearing 3+ times.
   * Returns a warning string suitable for injection as a system block,
   * or undefined if no repetition detected.
   *
   * This breaks agent loops where the model keeps re-reading the same file
   * or re-running the same command because it lost context about what it
   * already did.
   */
  private detectToolRepetition(messages: any[]): string | undefined {
    // Track (toolName, target) → count
    const invocations = new Map<string, { tool: string; target: string; count: number }>()

    for (const msg of messages) {
      if (!Array.isArray(msg?.content)) continue

      for (const block of msg.content) {
        if (block?.type !== 'tool_use') continue
        const toolName = block.name ?? ''
        const input = block.input
        if (!input || typeof input !== 'object') continue

        // Extract the primary target parameter based on tool class
        let target = ''
        if (isReadTool(toolName) || isWriteTool(toolName)) {
          target = extractFilePath(input as Record<string, unknown>)
        } else if (/^(grep|cassi_grep|glob|cassi_glob)$/i.test(toolName)) {
          target = extractSearchTarget(input as Record<string, unknown>)
        } else if (isShellTool(toolName)) {
          target = String(input.command ?? '')
        } else if (/^(webfetch|cassi_web)$/i.test(toolName)) {
          target = String(input.url ?? '')
        } else {
          // Generic: use first string input > 5 chars
          for (const val of Object.values(input)) {
            if (typeof val === 'string' && val.length > 5) {
              target = val.slice(0, 80)
              break
            }
          }
        }

        if (!target) continue
        // Normalize target: trim and lowercase for matching
        const normalizedTarget = String(target).trim().toLowerCase().slice(0, 100)
        if (!normalizedTarget) continue

        const key = `${toolName}::${normalizedTarget}`
        const existing = invocations.get(key)
        if (existing) {
          existing.count++
        } else {
          invocations.set(key, { tool: toolName, target: String(target).trim().slice(0, 80), count: 1 })
        }
      }
    }

    // Find repeated invocations (3+ times)
    const repeated = Array.from(invocations.values())
      .filter(inv => inv.count >= 3)
      .sort((a, b) => b.count - a.count)

    if (repeated.length === 0) return undefined

    const warnings = repeated.slice(0, 3).map(inv =>
      `${inv.tool}("${inv.target}") called ${inv.count} times`
    )

    const message = warnings.length === 1
      ? `Repeated tool call detected: ${warnings[0]}. Consider using information you already have.`
      : `Repeated tool calls detected: ${warnings.join('; ')}. Consider using information you already have.`

    this.logger.debug('Tool repetition detected', { repeated: repeated.length, worst: repeated[0] })
    return message
  }

  private buildContextMap(messages: any[]): string {
    return messages.map((msg, i) => {
      const ann = msg?._thalamus
      const idx = ann?.index ?? i
      const t = formatTimeOfDay(ann?.ts)
      const chars = formatBytes(ann?.chars ?? 0)
      const role = msg?.role ?? '?'
      const blocks = Array.isArray(msg?.content)
        ? msg.content.map((b: any) => b?.type).filter(Boolean).join('+')
        : 'text'
      let tag = ''
      if (ann?.protectedBy === 'pin') tag = ' pin'
      else if (ann?.protectedBy === 'live-read') tag = ' live'
      else if (ann?.protectedBy === 'recent-window') tag = ' recent'
      else if (ann?.protectedBy === 'system') tag = ' sys'
      return `[#${idx} ${t} ${role} ${blocks} ${chars}${tag}]`
    }).join(' ')
  }

  private getRecentUserPrompt(messages: any[]): string {
    for (let i = messages.length - 1; i >= 0; i--) {
      const msg = messages[i]
      if (msg?.role !== 'user') continue
      const content = extractMessageContent(msg)
      if (content.length > 10 && !content.includes('[#')) return content.slice(0, 300)
    }
    return ''
  }

  private getRecentAssistantThinking(messages: any[]): string {
    for (let i = messages.length - 1; i >= 0; i--) {
      const msg = messages[i]
      if (msg?.role !== 'assistant' || !Array.isArray(msg?.content)) continue
      for (const block of msg.content) {
        if (block?.type === 'thinking' && typeof block.thinking === 'string' && block.thinking.length > 20) {
          return block.thinking.slice(0, 300)
        }
      }
    }
    return ''
  }

  private getConfigOverrides(): Partial<CurationConfig> {
    if (!this.config) return {}
    const overrides: Partial<CurationConfig> = {}
    const budget = this.config.get('intelligence.thalamus.charBudget', undefined)
    if (budget) overrides.charBudget = budget
    const window = this.config.get('intelligence.thalamus.recentWindowSize', undefined)
    if (window) overrides.recentWindowSize = window
    const maxChars = this.config.get('intelligence.thalamus.toolResultMaxChars', undefined)
    if (maxChars) overrides.toolResultMaxChars = maxChars
    const threshold = this.config.get('intelligence.thalamus.ignitionThreshold', undefined)
    if (threshold) overrides.ignitionThreshold = threshold
    const prefixes = this.config.get('intelligence.thalamus.excludeSessionPrefixes', undefined)
    if (prefixes) overrides.excludeSessionPrefixes = prefixes
    return overrides
  }

  /**
   * Read-path: search MnemicField and return formatted context for
   * Hermes memory-provider injection.
   *
   * Reuses MnemicField.retrieve() (kindling) with FTS5 fallback,
   * applies nodeType/provenance/session filtering, content-fingerprint
   * dedup, and score × potentiation ranking. Returns formatted lines
   * ready for <memory-context> injection.
   */
  async injectForMemory(
    query: string,
    sessionId: string,
    limit = 5,
  ): Promise<{ context: string; hits: number }> {
    if (!this.mnemicField || !query.trim()) return { context: '', hits: 0 }

    // Term extraction: CamelCase, snake_case, ALL_CAPS, proper nouns
    const terms = this.extractKeyTerms(query)
    const kindlingQuery = terms.length > 0 ? terms.slice(0, 15).join(' ') : query.slice(0, 500)

    // Primary: kindling (embedding → ANN → spread → rerank)
    let rawHits: MnemicRetrievalHit[] = []
    try {
      rawHits = await this.mnemicField.retrieve(kindlingQuery, {
        limit: limit * 3,
        sessionId,
      })
    } catch (err) {
      this.logger.debug('injectForMemory: kindling failed, trying FTS5', { error: String(err) })
    }

    // Fallback: FTS5 text search
    if (rawHits.length === 0) {
      try {
        const ftsHits = this.mnemicField.searchText(kindlingQuery, limit * 3)
        rawHits = ftsHits.map(r => ({
          id: r.engram.id,
          content: r.engram.content,
          nodeType: r.engram.nodeType,
          score: r.score,
          charge: 0,
          potentiation: r.engram.potentiation,
          provenance: r.engram.provenance ?? '',
          tags: r.engram.tags ?? [],
          metadata: r.engram.metadata ?? {},
        }))
      } catch (err) {
        this.logger.debug('injectForMemory: FTS5 fallback failed', { error: String(err) })
      }
    }

    if (rawHits.length === 0) return { context: '', hits: 0 }

    // Filter
    const filtered = rawHits.filter(h => {
      if (ThalamusModule.INJECT_SKIP_TYPES.has(h.nodeType)) return false
      if (ThalamusModule.INJECT_SKIP_PROVENANCE.has(h.provenance)) return false
      if (h.metadata?.sessionId === sessionId) return false
      if (!h.content || h.content.length < 10) return false
      return true
    })

    // Dedup by content fingerprint (first 100 chars, cleaned)
    const seenFps = new Set<string>()
    const unique: MnemicRetrievalHit[] = []
    for (const h of filtered) {
      const fp = cleanEngramContent(h.content).slice(0, 100)
      if (!fp || seenFps.has(fp)) continue
      seenFps.add(fp)
      unique.push(h)
    }

    // Rank: score × (1 + potentiation × 0.3)
    unique.sort((a, b) =>
      (b.score * (1 + b.potentiation * 0.3)) - (a.score * (1 + a.potentiation * 0.3))
    )

    // Format
    const lines: string[] = []
    for (const h of unique.slice(0, limit)) {
      let content = cleanEngramContent(h.content)
      if (content.length > 200) content = content.slice(0, 197) + '...'
      if (!content) continue
      const prefix = h.nodeType ? `[${h.nodeType.replace(/_/g, ' ')}] ` : ''
      lines.push(`- ${prefix}${content}`)
    }

    return { context: lines.join('\n'), hits: lines.length }
  }

  /**
   * Extract CamelCase, snake_case, ALL_CAPS, and proper-noun identifiers.
   * Distinctive terms are the strongest FTS5 seed signals.
   */
  extractKeyTerms(text: string): string[] {
    const terms: string[] = []

    // CamelCase (KindlingEngine, MnemicField)
    for (const m of text.matchAll(/\b[A-Z][a-z]+(?:[A-Z][a-z]+)+\b/g)) terms.push(m[0])
    // snake_case (embedding_service, max_luminal)
    for (const m of text.matchAll(/\b[a-z]+(?:_[a-z]+){1,}\b/g)) terms.push(m[0])
    // ALL_CAPS (FTS5, ANN, GPU)
    for (const m of text.matchAll(/\b[A-Z]{2,6}\b/g)) terms.push(m[0])
    // Proper nouns (Helix, Unity, CassiCore)
    for (const m of text.matchAll(/\b[A-Z][a-z]{2,}(?:\s+[A-Z][a-z]{2,})?\b/g)) terms.push(m[0])

    // Deduplicate case-insensitively, keep longest variant
    const seen = new Set<string>()
    const unique: string[] = []
    for (const t of terms.sort((a, b) => b.length - a.length)) {
      if (seen.has(t.toLowerCase())) continue
      seen.add(t.toLowerCase())
      unique.push(t)
    }
    return unique.slice(0, 15)
  }

  private static readonly INJECT_SKIP_TYPES = new Set([
    'bridge', 'session', 'file', 'source_file', 'file_version', 'file_read',
    'changeset', 'message', 'tool_invocation', 'thought_command',
    'replay_segment', 'expert_summary',
  ])

  private static readonly INJECT_SKIP_PROVENANCE = new Set([
    'code-store', 'cortex/claude-code',
  ])
}
