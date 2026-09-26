/**
 * Shared token estimation utilities for CassiCore.
 *
 * WHY: Using a single source of truth for chars-per-token ratio ensures
 * consistent budget enforcement across all context management systems.
 * Previously, different modules used 3.5, 4.0, or hardcoded divisions,
 * leading to budget overruns of 10-50x in production.
 */

/**
 * Standard chars-per-token ratio for context budget calculations.
 *
 * WHY: Using 3.7 as a compromise between code-heavy content (~3.5 chars/token)
 * and English text (~4.0 chars/token). All context budget code MUST use this
 * constant for consistent enforcement across the system.
 *
 * This value is derived from empirical analysis of mixed code/natural language
 * LLM inputs in the CassiCore codebase.
 */
export const CHARS_PER_TOKEN = 3.7

/**
 * Estimate tokens from character count.
 * Uses ceiling to be conservative with budget estimates.
 */
export function estimateTokens(chars: number): number {
  return Math.ceil(chars / CHARS_PER_TOKEN)
}

/**
 * Estimate characters from token count.
 * Uses floor to stay within budget limits.
 */
export function estimateChars(tokens: number): number {
  return Math.floor(tokens * CHARS_PER_TOKEN)
}
