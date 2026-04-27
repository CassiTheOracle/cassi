/**
 * Context overflow detection and recovery utilities.
 *
 * Ported from core/turn-pipeline.ts to enable shared overflow handling
 * across both pipeline systems.
 */

/* ------------------------------------------------------------------ */
/*  Overflow patterns                                                  */
/* ------------------------------------------------------------------ */

/**
 * Regex patterns to detect context overflow errors from different providers.
 * 
 * NOTE: These patterns are duplicated in ai/src/utils/overflow.ts for the AI package.
 * When adding new patterns, update BOTH files to maintain consistency.
 * 
 * Example errors:
 * - z.ai: "<400> InternalError.Algo.InvalidParameter: Range of input length should be [1, 202745]"
 */
const OVERFLOW_PATTERNS = [
  /prompt is too long/i,
  /input is too long for requested model/i,
  /exceeds the context window/i,
  /input token count.*exceeds the maximum/i,
  /maximum prompt length is \d+/i,
  /reduce the length of the messages/i,
  /maximum context length is \d+ tokens/i,
  /exceeds the limit of \d+/i,
  /exceeds the available context size/i,
  /greater than the context length/i,
  /context window exceeds limit/i,
  /exceeded model token limit/i,
  /context[_ ]length[_ ]exceeded/i,
  /too many tokens/i,
  /token limit exceeded/i,
  /InternalError\.Algo\.InvalidParameter.*input length/i, // z.ai
]

/* ------------------------------------------------------------------ */
/*  Public API                                                         */
/* ------------------------------------------------------------------ */

/** Sentinel error for context-overflow: allows targeted catch in the tool loop. */
export class ContextOverflowError extends Error {
  constructor(public readonly originalMessage: string) {
    super(`Context overflow: ${originalMessage}`)
    this.name = 'ContextOverflowError'
  }
}

/** Check if an error string matches a known context-overflow pattern. */
export function isOverflowError(errorText: string): boolean {
  if (OVERFLOW_PATTERNS.some(p => p.test(errorText))) return true
  // Cerebras/Mistral: 400/413 with no body
  if (/^4(00|13)\s*(status code)?\s*\(no body\)/i.test(errorText)) return true
  return false
}

/**
 * Reclassify a generic Error as ContextOverflowError if its message
 * matches known overflow patterns. Returns the original error if no match.
 */
export function reclassifyAsOverflow(err: Error): Error {
  if (err instanceof ContextOverflowError) return err
  if (isOverflowError(err.message)) {
    return new ContextOverflowError(err.message)
  }
  return err
}

/* ------------------------------------------------------------------ */
/*  Tool filler stripping                                              */
/* ------------------------------------------------------------------ */

/**
 * Calculate the character length of message content.
 * Handles both string content and ContentBlock arrays.
 */
export function contentLength(content: string | { type: string; text?: string }[]): number {
  if (typeof content === 'string') return content.length
  return content.reduce((sum, block) => sum + ('text' in block ? (block.text?.length ?? 50) : 50), 0)
}

/**
 * Strip filler text that models produce before tool calls.
 * Examples: "Let me check this...", "I'll run the command now."
 * These waste tokens and add no value to the conversation.
 */
export function stripToolFiller(text: string): string {
  if (!text) return text

  const fillerPatterns = [
    // Checking/verifying
    /^\s*(let me|let's|i'll|i will)\s+(check|verify|see|look up|find out|confirm)\s*(this|that|it|now|real quick|quickly)?\s*\.?\s*$/i,
    /^\s*(checking|verifying|looking up)\s*(this|that|it|now)?\s*\.?\s*$/i,

    // Running/executing
    /^\s*(let me|let's|i'll|i will)\s+(run|execute|call|use)\s+(the\s+)?(\w+\s+)?(tool|command)\s*\.?\s*$/i,
    /^\s*(running|executing|calling)\s+(the\s+)?(\w+\s+)?(tool|command)\s*\.?\s*$/i,

    // Generic action announcements
    /^\s*(let me|let's|i'll|i will)\s+(do|handle|take care of|get)\s+(this|that|it|for you)\s*\.?\s*$/i,
    /^\s*(i'm going to|i am going to|i'll)\s+(use|try|attempt)\s+to\s+\w+\s*\.?\s*$/i,

    // File operations
    /^\s*(let me|let's|i'll)\s+(read|list|show|display|open)\s+(the\s+)?(file|directory|folder|contents)\s*\.?\s*$/i,

    // Multi-sentence fillers (remove everything before a tool call marker)
    /^\s*[\w\s,]+?(i'll|let me|i'm going to)\s+[\w\s,]+?\.?\s*$/i,
  ]

  const trimmed = text.trim()

  for (const pattern of fillerPatterns) {
    if (pattern.test(trimmed)) {
      return '' // Strip the filler entirely
    }
  }

  // If text ends with colon and has tool-call-like structure, keep it (minimal context)
  // e.g., "Checking the workspace:" is okay
  if (trimmed.endsWith(':') && trimmed.split(' ').length <= 6) {
    return trimmed
  }

  return trimmed
}

/* ------------------------------------------------------------------ */
/*  Question tool detection                                            */
/* ------------------------------------------------------------------ */

/**
 * Tool names that produce semantically-user-input results.
 *
 * `question` is CassiCore's native AskUserQuestion-equivalent; `AskUserQuestion`
 * is the Claude Code harness tool. Both wrap user intent in a tool_result block
 * and must survive PCPM scoring as user messages, not be flushed as tool noise.
 */
const QUESTION_TOOL_NAMES: ReadonlySet<string> = new Set(['question', 'AskUserQuestion'])

/**
 * Check if a ContentBlock is a question tool result.
 *
 * Anthropic tool_result blocks carry only `tool_use_id`, not `tool_name` —
 * pass `toolUseMap` (built once via {@link buildToolUseMapFromMessages}) to
 * resolve the originating tool name. Internal blocks that include `tool_name`
 * directly are matched without needing the map.
 */
export function isQuestionBlock(
  block: { type: string; tool_name?: string; tool_use_id?: string },
  toolUseMap?: Map<string, string>,
): boolean {
  if (block.type !== 'tool_result') return false
  if (block.tool_name && QUESTION_TOOL_NAMES.has(block.tool_name)) return true
  if (toolUseMap && block.tool_use_id) {
    const name = toolUseMap.get(block.tool_use_id)
    if (name && QUESTION_TOOL_NAMES.has(name)) return true
  }
  return false
}

/**
 * Check if a Message contains a question tool result.
 * Works with both ContentBlock[] (runtime messages) and ToolResult[] (internal messages).
 */
export function hasQuestionResult(
  msg: {
    role: string
    content?: unknown
    toolResults?: Array<{ toolName?: string }>
  },
  opts?: { toolUseMap?: Map<string, string> },
): boolean {
  if (msg.role !== 'user') return false
  const toolUseMap = opts?.toolUseMap

  // ContentBlock[] path (runtime Message format)
  if (Array.isArray(msg.content)) {
    return (msg.content as Array<{ type: string; tool_name?: string; tool_use_id?: string }>)
      .some(b => isQuestionBlock(b, toolUseMap))
  }

  // ToolResult[] path (internal Message format used by ToolLoop)
  if (Array.isArray(msg.toolResults)) {
    return msg.toolResults.some(tr => !!tr.toolName && QUESTION_TOOL_NAMES.has(tr.toolName))
  }

  return false
}

/**
 * Build a `tool_use_id → tool_name` map from prior assistant tool_use blocks.
 *
 * Used by {@link hasQuestionResult} callers that have the full message array
 * but no precomputed map. Build once per scoring/curation pass and reuse —
 * the map is O(messages) to build but O(1) per lookup.
 */
export function buildToolUseMapFromMessages(messages: any[]): Map<string, string> {
  const map = new Map<string, string>()
  for (const msg of messages) {
    if (msg?.role !== 'assistant' || !Array.isArray(msg.content)) continue
    for (const block of msg.content) {
      if (block?.type === 'tool_use' && typeof block.id === 'string' && typeof block.name === 'string') {
        map.set(block.id, block.name)
      }
    }
  }
  return map
}
