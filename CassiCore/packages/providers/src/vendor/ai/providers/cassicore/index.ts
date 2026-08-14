/**
 * P8-DEFERRED type stub — @cassicore/ai provider SDK surface.
 *
 * The whole `ai/` tree stays in `D:`, migrating at P8 as `@cassicore/ai`. These
 * symbols are consumed by the providers package (`index.ts` provider-factory +
 * the `qwen-loadbalancer`), so this module declares a faithful consumer-facing
 * surface (IProvider-compatible) and throws at runtime (the "not connected"
 * pattern).
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

/**
 * Minimal shared base for the AI provider SDK surface (type-faithful subset of
 * `ai/providers/cassicore/openai-compatible-base.ts` — implements the
 * IProvider-compatible members providers/index.ts and qwen-loadbalancer use).
 */
export abstract class OpenAICompatibleBase {
  abstract readonly id: string
  abstract readonly models: string[]
  constructor() {
    notMigrated('OpenAICompatibleBase')
  }
  complete(
    messages: Message[],
    opts: CompletionOpts,
    attachments?: ImageAttachment[],
    signal?: AbortSignal
  ): AsyncIterable<CompletionChunk> {
    return notMigrated('OpenAICompatibleBase')
  }
  ping(signal?: AbortSignal): Promise<boolean> {
    return notMigrated('OpenAICompatibleBase')
  }
  countTokens(messages: Message[]): Promise<number> {
    return notMigrated('OpenAICompatibleBase')
  }
}

/** OAuth credentials for a Qwen account. */
export interface QwenOAuthCredentials {
  refresh: string
  access: string
  expires: number
  enterpriseUrl?: string
}

export class OpenCodeGoProvider extends OpenAICompatibleBase {
  readonly id = "opencode-go"
  readonly models: string[] = []
  constructor(apiKey?: string) { super(); notMigrated('OpenCodeGoProvider') }
}

export class AlibabaCodingProvider extends OpenAICompatibleBase {
  readonly id = "alibaba-coding"
  readonly models: string[] = []
  constructor(apiKey?: string) { super(); notMigrated('AlibabaCodingProvider') }
  getApiKey(): string { return notMigrated('AlibabaCodingProvider') }
}

export class DeepSeekProvider extends OpenAICompatibleBase {
  readonly id = "deepseek"
  readonly models: string[] = []
  constructor(apiKey?: string) { super(); notMigrated('DeepSeekProvider') }
}

export class KimiCodingProvider extends OpenAICompatibleBase {
  readonly id = "kimi-coding"
  readonly models: string[] = []
  constructor(apiKey?: string) { super(); notMigrated('KimiCodingProvider') }
}

export class OpenRouterProvider extends OpenAICompatibleBase {
  readonly id = "openrouter"
  readonly models: string[] = []
  constructor(apiKey?: string, baseUrlOrRouting?: string | unknown) { super(); notMigrated('OpenRouterProvider') }
}

export class ZaiProvider extends OpenAICompatibleBase {
  readonly id = "z-ai"
  readonly models: string[] = []
  constructor(apiKey?: string) { super(); notMigrated('ZaiProvider') }
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
  /** OAuth: refresh the access token. */
  static refreshToken(credentials: QwenOAuthCredentials): Promise<QwenOAuthCredentials> {
    return notMigrated('QwenProvider.refreshToken')
  }
}
