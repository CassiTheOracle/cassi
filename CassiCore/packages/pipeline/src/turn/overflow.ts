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
