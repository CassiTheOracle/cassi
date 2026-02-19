import type { IProvider, Message, CompletionOpts, CompletionChunk } from '../../types/runtime.js'

export abstract class BaseProvider implements IProvider {
  abstract readonly id: string
  abstract readonly models: string[]
  abstract complete(messages: Message[], opts: CompletionOpts): AsyncIterable<CompletionChunk>
  abstract countTokens(messages: Message[]): Promise<number>
  abstract ping(): Promise<boolean>

  /** Simple token estimate: ~4 chars per token */
  protected estimateTokens(messages: Message[]): number {
    return Math.ceil(messages.reduce((s, m) => s + m.content.length, 0) / 4)
  }
}
