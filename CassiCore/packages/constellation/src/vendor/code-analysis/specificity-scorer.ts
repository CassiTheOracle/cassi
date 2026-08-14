/**
 * Specificity Scorer — Assesses task specificity for adaptive context gating.
 *
 * Scores a task description on 0–1 for how specific it is about code locations.
 * Used to decide whether injecting code context is worthwhile:
 *
 *  > 0.6  → full context (file content + symbol bodies)
 *  0.3–0.6 → file-level only (names + descriptions)
 *  < 0.3  → skip context injection entirely
 *
 * When a ContextFeedbackTracker is provided, Bayesian learning may override
 * the hardcoded thresholds based on real-world feedback data.
 */

import type { SpecificityScore, SpecificitySignal } from './types.js'
import type { ContextFeedbackTracker } from './feedback-tracker.js'


/** File path pattern: path/to/file.ext */
const FILE_PATH_RE = /[\w/.-]+\.(?:ts|js|tsx|jsx|py|go|rs|java|rb|css|html|json|yaml|yml|md)/g

/** Symbol name pattern: PascalCase or camelCase identifiers (4+ chars) */
const SYMBOL_NAME_RE = /\b(?:[A-Z][a-zA-Z0-9]{3,}|[a-z][a-zA-Z0-9]*[A-Z][a-zA-Z0-9]*)\b/g

/** Error trace patterns: "Error:", stack traces, exception names */
const ERROR_TRACE_RE = /(?:Error:|at\s+\w+|TypeError|ReferenceError|SyntaxError|throw\s+new|stack\s*trace|exception)/gi

/** Line number patterns: :123, line 45, L42 */
const LINE_NUMBER_RE = /(?::\d{1,5}\b|line\s+\d+|L\d+)/gi

/** Code reference patterns: `backtick code`, function(), class.method */
const CODE_REF_RE = /`[^`]+`|\b\w+\(\)|\b\w+\.\w+\(\)/g

/** Vague modifier patterns */
const VAGUE_MODIFIERS = [
  /\bimprove\b/i,
  /\boptimize\b/i,
  /\brefactor\s+(?:the\s+)?(?:entire|whole|all)\b/i,
  /\bclean\s*up\b/i,
  /\bmake\s+(?:it\s+)?better\b/i,
  /\boverhaul\b/i,
  /\bre(?:write|design|architect)\s+(?:the\s+)?(?:entire|whole|all)\b/i,
  /\beverything\b/i,
  /\bthe\s+codebase\b/i,
]


const WEIGHTS = {
  file_path: 0.3,
  symbol_name: 0.25,
  error_trace: 0.2,
  line_number: 0.15,
  code_reference: 0.1,
  vague_modifier: -0.15,
} as const


const FULL_CONTEXT_THRESHOLD = 0.6
const FILE_ONLY_THRESHOLD = 0.3

/**
 * Score the specificity of a task description.
 *
 * When a feedback tracker is provided and has sufficient data, the Bayesian
 * model may override the default mode selection. The original (heuristic)
 * mode is preserved in `adaptiveOverride.originalMode` for diagnostics.
 */
export function scoreSpecificity(task: string, feedbackTracker?: ContextFeedbackTracker): SpecificityScore {
  const signals: SpecificitySignal[] = []
  let score = 0

  // File paths
  const filePaths = task.match(FILE_PATH_RE) || []
  if (filePaths.length > 0) {
    const weight = Math.min(WEIGHTS.file_path * filePaths.length, 0.5) // Cap contribution
    signals.push({ type: 'file_path', weight, match: filePaths.slice(0, 3).join(', ') })
    score += weight
  }

  // Symbol names
  const symbolNames = task.match(SYMBOL_NAME_RE) || []
  if (symbolNames.length > 0) {
    const weight = Math.min(WEIGHTS.symbol_name * symbolNames.length, 0.5)
    signals.push({ type: 'symbol_name', weight, match: symbolNames.slice(0, 5).join(', ') })
    score += weight
  }

  // Error traces
  const errors = task.match(ERROR_TRACE_RE) || []
  if (errors.length > 0) {
    signals.push({ type: 'error_trace', weight: WEIGHTS.error_trace, match: errors.slice(0, 2).join(', ') })
    score += WEIGHTS.error_trace
  }

  // Line numbers
  const lineNums = task.match(LINE_NUMBER_RE) || []
  if (lineNums.length > 0) {
    signals.push({ type: 'line_number', weight: WEIGHTS.line_number, match: lineNums.slice(0, 3).join(', ') })
    score += WEIGHTS.line_number
  }

  // Code references
  const codeRefs = task.match(CODE_REF_RE) || []
  if (codeRefs.length > 0) {
    signals.push({ type: 'code_reference', weight: WEIGHTS.code_reference, match: codeRefs.slice(0, 3).join(', ') })
    score += WEIGHTS.code_reference
  }

  // Vague modifiers (negative signal)
  for (const pattern of VAGUE_MODIFIERS) {
    const match = task.match(pattern)
    if (match) {
      signals.push({ type: 'vague_modifier', weight: WEIGHTS.vague_modifier, match: match[0] })
      score += WEIGHTS.vague_modifier
    }
  }

  // Clamp to [0, 1]
  score = Math.max(0, Math.min(1, score))

  // Determine recommended mode (heuristic baseline)
  let mode: 'full' | 'file_only' | 'skip'
  if (score >= FULL_CONTEXT_THRESHOLD) {
    mode = 'full'
  } else if (score >= FILE_ONLY_THRESHOLD) {
    mode = 'file_only'
  } else {
    mode = 'skip'
  }

  // Adaptive override: if the feedback tracker has learned a better mode
  // for this specificity range, use it instead of the hardcoded thresholds.
  let adaptiveOverride: SpecificityScore['adaptiveOverride']
  if (feedbackTracker) {
    const recommendation = feedbackTracker.recommendMode(score)
    if (recommendation && recommendation.mode !== mode) {
      adaptiveOverride = {
        originalMode: mode,
        confidence: recommendation.confidence,
        reason: recommendation.reason,
      }
      mode = recommendation.mode
    }
  }

  return {
    score: Math.round(score * 1000) / 1000,
    mode,
    signals,
    adaptiveOverride,
  }
}
