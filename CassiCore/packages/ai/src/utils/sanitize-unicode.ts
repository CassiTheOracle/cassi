/**
 * Removes unpaired Unicode surrogate characters from a string.
 *
 * Unpaired surrogates (high surrogates 0xD800-0xDBFF without matching low surrogates 0xDC00-0xDFFF,
 * or vice versa) cause JSON serialization errors in many API providers.
 *
 * Valid emoji and other characters outside the Basic Multilingual Plane use properly paired
 * surrogates and will NOT be affected by this function.
 *
 * @param text - The text to sanitize
 * @returns The sanitized text with unpaired surrogates removed
 *
 * @example
 * // Valid emoji (properly paired surrogates) are preserved
 * sanitizeSurrogates("Hello 🙈 World") // => "Hello 🙈 World"
 *
 * // Unpaired high surrogate is removed
 * const unpaired = String.fromCharCode(0xD83D); // high surrogate without low
 * sanitizeSurrogates(`Text ${unpaired} here`) // => "Text  here"
 * @dep callers: convertResponsesMessages (ai/src/providers/openai-responses-shared.ts), convertMessages (ai/src/providers/amazon-bedrock.ts), buildSystemPrompt (ai/src/providers/amazon-bedrock.ts), convertMessages (ai/src/providers/anthropic.ts), buildParams (ai/src/providers/anthropic.ts) [+6]
 * @dep flows: StreamSimpleGoogle → SanitizeSurrogates (4/4), StreamOpenAICodexResponses → SanitizeSurrogates (4/4), StreamSimpleBedrock → SanitizeSurrogates (4/4)
 * @dep module: Providers
 * @dep risk: CRITICAL | 11 callers, 3 flows, 1 module
 */
export function sanitizeSurrogates(text: string): string {
	// Replace unpaired high surrogates (0xD800-0xDBFF not followed by low surrogate)
	// Replace unpaired low surrogates (0xDC00-0xDFFF not preceded by high surrogate)
	return text.replace(/[\uD800-\uDBFF](?![\uDC00-\uDFFF])|(?<![\uD800-\uDBFF])[\uDC00-\uDFFF]/g, "");
}
