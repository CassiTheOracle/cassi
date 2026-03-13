/**
 * Inference Helper — standalone LLM inference for intelligence modules.
 *
 * Can be used by modules that don't extend BaseCognitiveModule,
 * or for testing inference logic in isolation.
 */

import type { IProvider, Message, CompletionOpts } from '../../../types/runtime.js'
import type { ILogger } from '../../../types/interfaces.js'
import type { ModuleModelConfig } from './model-config.js'

export interface InferenceMetrics {
  calls: number
  errors: number
  totalMs: number
}

export interface InferenceOptions extends Partial<CompletionOpts> {
  /** Module name for observability */
  source?: string
}

/**
 * Run LLM inference using a given provider and model config.
 * Returns the raw text response.
 */
export async function infer(
  provider: IProvider,
  modelConfig: ModuleModelConfig,
  prompt: string | Message[],
  opts?: InferenceOptions,
  metrics?: InferenceMetrics,
): Promise<string> {
  const messages: Message[] = typeof prompt === 'string'
    ? [{ role: 'user', content: prompt }]
    : prompt

  const completionOpts: CompletionOpts = {
    model: modelConfig.model,
    temperature: modelConfig.temperature,
    maxTokens: modelConfig.maxTokens,
    thinking: 'none',
    allowConcurrent: true,
    dedupe: false,
    source: opts?.source,
    ...opts,
  }

  const startMs = Date.now()
  if (metrics) metrics.calls++

  try {
    let result = ''
    const stream = provider.complete(messages, completionOpts)
    for await (const chunk of stream) {
      if (chunk.type === 'token' && chunk.text) {
        result += chunk.text
      }
    }
    if (metrics) metrics.totalMs += Date.now() - startMs
    return result
  } catch (err) {
    if (metrics) {
      metrics.errors++
      metrics.totalMs += Date.now() - startMs
    }
    throw err
  }
}

/**
 * Run LLM inference and parse the response as JSON.
 * Wraps the prompt with JSON-only instructions.
 *
 * @returns Parsed JSON object, or null if parsing fails
 */
export async function inferJSON<T = unknown>(
  provider: IProvider,
  modelConfig: ModuleModelConfig,
  prompt: string | Message[],
  logger?: ILogger,
  opts?: InferenceOptions,
  metrics?: InferenceMetrics,
): Promise<T | null> {
  const messages: Message[] = typeof prompt === 'string'
    ? [
        { role: 'system', content: 'You are a JSON-only responder. Return ONLY valid JSON, no markdown, no explanation.' },
        { role: 'user', content: prompt },
      ]
    : prompt

  const raw = await infer(provider, modelConfig, messages, opts, metrics)

  try {
    const jsonMatch = raw.match(/```(?:json)?\s*([\s\S]*?)```/) || [null, raw]
    const jsonStr = (jsonMatch[1] || raw).trim()
    return JSON.parse(jsonStr) as T
  } catch (err) {
    logger?.warn('Failed to parse JSON from inference', {
      rawLength: raw.length,
      error: String(err),
    })
    return null
  }
}
