/**
 * Strip reasoning/thinking artifacts some models embed in response text.
 *
 * Despite instructions like `thinking: 'none'` and `systemPrompt` guards, models
 * (especially Qwen, gpt-5-mini) sometimes emit:
 *   - Bold-header reasoning steps: **Analyzing the Request**
 *   - <think>...<think> blocks
 *   - Enumerated thinking processes: "Here's a thinking process: 1. Analyze User Input: ..."
 *
 * This is a shared utility used by SmartCompactionEngine, ThalamusModule,
 * ContextDistiller, and any other component that calls background LLMs for
 * summarization.
 */

export function stripThinkingArtifacts(text: string): string {
  if (!text) return ''
  return text
    // WHY: Models like Qwen emit reasoning as bold headers (**Verb Phrase**)
    // in response text. These are standalone bold lines 10-80 chars. We use
    // a broad match because memory entries contain these from past sessions.
    // Minimum 10 chars avoids stripping short inline emphasis like **Note:**.
    .replace(/\*\*[A-Z][^*\n]{8,80}\*\*:?\s*\n*/g, '')
    // <think> blocks used by DeepSeek, QwQ, and some Claude variants
    .replace(/<think>[\s\S]*?<\/think>\s*/gi, '')
    // "Here's a thinking process:" and everything after it
    .replace(/Here\x27s a thinking process:[\s\S]*/i, '')
    // Numbered analysis markers
    .replace(/\d+\.\s*Analyze User Input:[\s\S]*/i, '')
    .replace(/\d+\.\s*Task:[\s\S]*/i, '')
    .replace(/\d+\.\s*Identify Key Actions:[\s\S]*/i, '')
    .trim()
}
