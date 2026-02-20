import type { IProvider, Message, CompletionOpts, CompletionChunk } from '../../types/runtime.js'

export abstract class BaseProvider implements IProvider {
  abstract readonly id: string
  abstract readonly models: string[]
  abstract complete(messages: Message[], opts: CompletionOpts): AsyncIterable<CompletionChunk>
  abstract countTokens(messages: Message[]): Promise<number>
  abstract ping(): Promise<boolean>

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
