/**
 * VENDORED TYPE STUB — mirrors `thalamus/index.js`. Surface: ThalamusModule + the `curate`
 * method the meditation solo-runner calls.
 */
import type { Message } from '../types/runtime.js'
import type { TopicSummary } from './types.js'

export interface ThalamusCuration {
  messages: Message[]
  meta: {
    originalCount: number
    curatedCount: number
    compressed: boolean
    dropped: number
    topicSummaries?: TopicSummary[]
  }
}

export interface ThalamusModule {
  curate(
    sessionId: string,
    messages: unknown[],
    opts?: { excludeSessionPrefixes?: string[]; [key: string]: unknown },
  ): Promise<ThalamusCuration>
  [key: string]: unknown
}
