/**
 * P8-DEFERRED type stub — @cassicore/ai provider SDK surface.
 *
 * The whole `ai/` tree stays in `D:`, migrating at P8 as `@cassicore/ai`. These
 * symbols are consumed by the providers package (`index.ts` re-export + the
 * `qwen-loadbalancer`), so this module declares a faithful consumer-facing type
 * surface for them and throws at runtime (the "not connected" pattern).
 *
 * Re-point to `@cassicore/ai` and delete this vendor at P8 (§3.b of the P7 table).
 */
import type {
  Message,
  CompletionOpts,
  CompletionChunk,
  ImageAttachment,
} from '@cassicore/foundation'

function notMigrated(name: string): never {
  throw new Error(
    `${name}: @cassicore/ai (ai/) is not migrated — P8-deferred. Re-point packages/providers/src/vendor/ai/... to @cassicore/ai and delete this stub at P8.`
  )
}

/** Minimal shared base for the AI provider SDK surface (type-faithful subset). */
export abstract class OpenAICompatibleBase {
  abstract readonly id: string
  abstract readonly models: string[]
  abstract complete(
    messages: Message[],
    opts: CompletionOpts,
    attachments?: ImageAttachment[],
    signal?: AbortSignal
  ): AsyncIterable<CompletionChunk>
  abstract countTokens(messages: Message[]): Promise<number>
}

/** OAuth credentials for a Qwen account. */
export interface QwenOAuthCredentials {
  refresh: string
  access: string
  expires: number
  enterpriseUrl?: string
}

export class AlibabaCodingProvider extends OpenAICompatibleBase {
  readonly id = "alibaba-coding"
  readonly models: string[] = []
  constructor(apiKey?: string) { super(); notMigrated('AlibabaCodingProvider') }
  getApiKey(): string { return notMigrated('AlibabaCodingProvider') }
  complete(): AsyncIterable<CompletionChunk> { return notMigrated('AlibabaCodingProvider') }
  countTokens(): Promise<number> { return notMigrated('AlibabaCodingProvider') }
}

export class DeepSeekProvider extends OpenAICompatibleBase {
  readonly id = "deepseek"
  readonly models: string[] = []
  constructor(apiKey?: string) { super(); notMigrated('DeepSeekProvider') }
  complete(): AsyncIterable<CompletionChunk> { return notMigrated('DeepSeekProvider') }
  countTokens(): Promise<number> { return notMigrated('DeepSeekProvider') }
}

export class KimiCodingProvider extends OpenAICompatibleBase {
  readonly id = "kimi-coding"
  readonly models: string[] = []
  constructor(apiKey?: string) { super(); notMigrated('KimiCodingProvider') }
  complete(): AsyncIterable<CompletionChunk> { return notMigrated('KimiCodingProvider') }
  countTokens(): Promise<number> { return notMigrated('KimiCodingProvider') }
}

export class OpenRouterProvider extends OpenAICompatibleBase {
  readonly id = "openrouter"
  readonly models: string[] = []
  constructor(apiKey?: string, baseUrlOrRouting?: string | unknown) { super(); notMigrated('OpenRouterProvider') }
  complete(): AsyncIterable<CompletionChunk> { return notMigrated('OpenRouterProvider') }
  countTokens(): Promise<number> { return notMigrated('OpenRouterProvider') }
}

export class ZaiProvider extends OpenAICompatibleBase {
  readonly id = "z-ai"
  readonly models: string[] = []
  constructor(apiKey?: string) { super(); notMigrated('ZaiProvider') }
  complete(): AsyncIterable<CompletionChunk> { return notMigrated('ZaiProvider') }
  countTokens(): Promise<number> { return notMigrated('ZaiProvider') }
}

export class QwenProvider extends OpenAICompatibleBase {
  readonly id = "qwen"
  readonly models: string[] = []
  private apiKey: string
  private baseUrl?: string
  private credentials?: QwenOAuthCredentials
  constructor(apiKey: string, baseUrl?: string, credentials?: QwenOAuthCredentials) {
    super()
    this.apiKey = apiKey
    this.baseUrl = baseUrl
    this.credentials = credentials
    notMigrated('QwenProvider')
  }
  complete(): AsyncIterable<CompletionChunk> { return notMigrated('QwenProvider') }
  countTokens(): Promise<number> { return notMigrated('QwenProvider') }
  /** OAuth: refresh the access token. */
  static refreshToken(credentials: QwenOAuthCredentials): Promise<QwenOAuthCredentials> {
    return notMigrated('QwenProvider.refreshToken')
  }
}
