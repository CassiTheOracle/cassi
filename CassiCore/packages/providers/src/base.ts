import type { IProvider, Message, CompletionOpts, CompletionChunk, ImageAttachment } from '@cassicore/foundation'

export abstract class BaseProvider implements IProvider {
  abstract readonly id: string
  abstract readonly models: string[]
  // providers may accept optional attachments and an AbortSignal to allow cancellation
  abstract complete(messages: Message[], opts: CompletionOpts, attachments?: ImageAttachment[], signal?: AbortSignal): AsyncIterable<CompletionChunk>
  abstract countTokens(messages: Message[]): Promise<number>
  abstract ping(signal?: AbortSignal): Promise<boolean>

  /** Token estimate: ~4 chars per token for text, ~256 tokens per image attachment */
  protected estimateTokens(messages: Message[]): number {
    return Math.ceil(messages.reduce((s, m) => {
      const textLen = typeof m.content === 'string'
        ? m.content.length
        : m.content.reduce((cs, b) => cs + ('text' in b ? b.text.length : 50), 0)
      return s + textLen
    }, 0) / 4)
  }
}
