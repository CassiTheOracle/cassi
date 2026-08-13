/** VENDORED TYPE STUB — mirrors `model-pool/types.js`. Surface: ModelHandle, ModelCompletionOpts. */
import type { Message, CompletionChunk, CompletionOpts } from '../types/runtime.js'

export interface ModelCompletionOpts extends CompletionOpts {
  modelId?: string
  [key: string]: unknown
}

export interface ModelHandle {
  id: string
  model: string
  complete(prompt: string | Message[], opts?: ModelCompletionOpts): Promise<string>
  stream(prompt: string | Message[], opts?: ModelCompletionOpts): AsyncIterable<CompletionChunk>
  release(): Promise<void> | void
  [key: string]: unknown
}
