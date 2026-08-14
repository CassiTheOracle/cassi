/**
 * VENDORED — faithful runtime copy of `core/pipeline/turn/overflow.ts`.
 * Consumed by @cassicore/thalamus (classifier, compressor, distiller,
 * drop-receipt, scorer, tool-result-slot, user-slot) via
 * `hasQuestionResult` / `buildToolUseMapFromMessages`.
 *
 * Ported verbatim from D: core/pipeline/turn/overflow.ts (HEAD@d63358da).
 * Self-contained (builtins only). Re-point to `@cassicore/pipeline` when that
 * package lands (P5 repoint log).
 */
/* ------------------------------------------------------------------ */
/*  Context overflow detection and recovery utilities.                */
/* ------------------------------------------------------------------ */

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

const QUESTION_TOOL_NAMES: ReadonlySet<string> = new Set(['question', 'AskUserQuestion'])

/**
 * Check if a ContentBlock is a question tool result.
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
