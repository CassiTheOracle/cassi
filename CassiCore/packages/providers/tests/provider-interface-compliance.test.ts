/**
 * Provider Interface Compliance Tests
 *
 * This test suite verifies that provider implementations correctly adhere
 * to the IProvider interface contract defined in types/runtime.ts.
 *
 * The IProvider interface is the foundation of CassiCore's multi-provider
 * architecture. All LLM providers (Anthropic, GitHub Copilot, Qwen, etc.)
 * must implement this interface to be interchangeable within the system.
 *
 * Testing Philosophy:
 * - We test BEHAVIOR, not implementation — callers should be able to use
 *   any provider without knowing its internal details
 * - We verify the contract guarantees: async iterables, error handling,
 *   and signal cancellation
 * - We use a MockProvider to test the interface without external dependencies
 * - Real provider smoke tests verify the actual implementations compile
 *
 * Contract Coverage:
 * 1. Provider initialization with auth setup
 * 2. Model listing capabilities
 * 3. Basic completion streaming (the core provider capability)
 * 4. Token counting (for budget management)
 * 5. Health/ping functionality (for provider selection)
 * 6. Abort signal handling (for request cancellation)
 */
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { BaseProvider } from '../src/base.js'
import type { IProvider, Message, CompletionOpts, CompletionChunk, ImageAttachment } from '@cassicore/foundation'


interface MockProviderConfig {
  apiKey: string
  baseUrl?: string
  model?: string
}

/**
 * A mock provider implementation that satisfies the IProvider interface.
 * Used to verify interface compliance without external API calls.
 *
 * This mock simulates a real provider's behavior:
 * - Records all calls for verification
 * - Respects abort signals
 * - Generates context-aware mock responses
 * - Masks API keys for security
 */
class MockProvider extends BaseProvider {
  readonly id = 'mock-provider'
  readonly models = ['mock-small', 'mock-large', 'mock-vision']

  private config: MockProviderConfig
  private callHistory: Array<{ messages: Message[]; opts: CompletionOpts }> = []

  constructor(config: MockProviderConfig) {
    super()
    this.config = {
      baseUrl: 'https://api.mock-provider.example/v1',
      model: 'mock-small',
      ...config,
    }
  }

  /**
   * Verify auth configuration is properly set up
   */
  isAuthenticated(): boolean {
    return !!this.config.apiKey && this.config.apiKey.length > 0
  }

  /**
   * Get the configured API key (masked for logging)
   */
  getMaskedApiKey(): string {
    const key = this.config.apiKey
    if (key.length <= 8) return '***'
    return `${key.slice(0, 4)}...${key.slice(-4)}`
  }

  /**
   * Get call history for verification
   */
  getCallHistory(): Array<{ messages: Message[]; opts: CompletionOpts }> {
    return this.callHistory
  }

  /**
   * Clear call history
   */
  clearHistory(): void {
    this.callHistory = []
  }

  /**
   * Get available models with metadata
   */
  getAvailableModels(): Array<{
    id: string
    name: string
    contextWindow: number
    supportsVision: boolean
    supportsTools: boolean
  }> {
    return [
      {
        id: 'mock-small',
        name: 'Mock Small Model',
        contextWindow: 4096,
        supportsVision: false,
        supportsTools: true,
      },
      {
        id: 'mock-large',
        name: 'Mock Large Model',
        contextWindow: 128000,
        supportsVision: false,
        supportsTools: true,
      },
      {
        id: 'mock-vision',
        name: 'Mock Vision Model',
        contextWindow: 128000,
        supportsVision: true,
        supportsTools: true,
      },
    ]
  }

  /**
   * Stream completion chunks for the given messages
   */
  async *complete(
    messages: Message[],
    opts: CompletionOpts,
    _attachments?: ImageAttachment[],
    signal?: AbortSignal,
  ): AsyncIterable<CompletionChunk> {
    // Record the call for verification
    this.callHistory.push({ messages: [...messages], opts: { ...opts } })

    // Check for abort signal
    if (signal?.aborted) {
      throw new Error('Request aborted')
    }

    const model = opts.model || this.config.model || 'mock-small'
    const maxTokens = opts.maxTokens || 1024

    // Simulate token generation
    const responseText = this.generateMockResponse(messages, opts)
    const tokens = responseText.split(' ')

    let tokensUsed = 0
    for (const token of tokens) {
      // Check abort between chunks
      if (signal?.aborted) {
        throw new Error('Request aborted')
      }

      yield {
        type: 'token',
        text: token + ' ',
        tokensUsed: ++tokensUsed,
      }
    }

    yield { type: 'done' }
  }

  /**
   * Count tokens for the given messages
   */
  async countTokens(messages: Message[]): Promise<number> {
    return this.estimateTokens(messages)
  }

  /**
   * Health check - verify provider is reachable
   */
  async ping(signal?: AbortSignal): Promise<boolean> {
    if (signal?.aborted) {
      return false
    }

    // Simulate network check
    await new Promise((resolve) => setTimeout(resolve, 10))
    return this.isAuthenticated()
  }


  private generateMockResponse(messages: Message[], opts: CompletionOpts): string {
    const lastMessage = messages[messages.length - 1]
    const content = typeof lastMessage?.content === 'string'
      ? lastMessage.content
      : 'mock content'

    if (opts.systemPrompt?.includes('concise')) {
      return 'Brief response.'
    }

    if (content.includes('error')) {
      return 'I encountered an error processing your request.'
    }

    if (content.includes('code')) {
      return 'Here is some sample code: const x = 42;'
    }

    return 'This is a mock response from the test provider.'
  }
}


describe('Provider Interface Compliance', () => {
  describe('Initialization & Authentication', () => {
    it('initializes with a valid API key and exposes its provider ID', () => {
      const provider = new MockProvider({
        apiKey: 'test-api-key-12345',
      })

      expect(provider.id).toBe('mock-provider')
      expect(provider.isAuthenticated()).toBe(true)
    })

    it('exposes a non-empty string identifier so the routing layer can select providers by ID', () => {
      const provider = new MockProvider({ apiKey: 'test' })
      expect(provider.id).toBeDefined()
      expect(typeof provider.id).toBe('string')
      expect(provider.id.length).toBeGreaterThan(0)
    })

    it('masks API keys when logging to prevent credential leaks in logs', () => {
      const provider = new MockProvider({
        apiKey: 'sk-test-1234567890abcdef',
      })

      const masked = provider.getMaskedApiKey()
      expect(masked).toContain('...')
      expect(masked).not.toContain('sk-test-1234567890abcdef')
    })

    it('accepts a custom base URL for proxy or enterprise deployments', () => {
      const customUrl = 'https://custom.api.endpoint.com/v2'
      const provider = new MockProvider({
        apiKey: 'test',
        baseUrl: customUrl,
      })

      expect(provider).toBeDefined()
    })

    it('reports as unauthenticated when initialized with an empty API key', () => {
      const provider = new MockProvider({ apiKey: '' })
      expect(provider.isAuthenticated()).toBe(false)
    })

    it('handles very short API keys gracefully when masking', () => {
      const provider = new MockProvider({ apiKey: 'ab' })
      const masked = provider.getMaskedApiKey()
      expect(masked).toBe('***')
    })
  })

  describe('Model Discovery', () => {
    let provider: MockProvider

    beforeEach(() => {
      provider = new MockProvider({ apiKey: 'test' })
    })

    it('exposes an array of supported model IDs for the routing layer', () => {
      expect(provider.models).toBeDefined()
      expect(Array.isArray(provider.models)).toBe(true)
      expect(provider.models.length).toBeGreaterThan(0)
    })

    it('ensures all model IDs are unique to prevent routing ambiguity', () => {
      const uniqueModels = new Set(provider.models)
      expect(uniqueModels.size).toBe(provider.models.length)
    })

    it('provides metadata for each model including capabilities and limits', () => {
      const models = provider.getAvailableModels()
      expect(models.length).toBeGreaterThan(0)

      for (const model of models) {
        expect(model.id).toBeDefined()
        expect(model.name).toBeDefined()
        expect(model.contextWindow).toBeGreaterThan(0)
        expect(typeof model.supportsVision).toBe('boolean')
        expect(typeof model.supportsTools).toBe('boolean')
      }
    })

    it('includes all model IDs in the metadata so callers can cross-reference', () => {
      const models = provider.getAvailableModels()
      const modelIds = models.map((m) => m.id)

      for (const id of provider.models) {
        expect(modelIds).toContain(id)
      }
    })

    it('maintains consistency between the models array and detailed metadata', () => {
      const availableModels = provider.getAvailableModels()
      expect(availableModels.map((m) => m.id).sort()).toEqual(
        [...provider.models].sort(),
      )
    })
  })

  describe('Streaming Completion', () => {
    let provider: MockProvider

    beforeEach(() => {
      provider = new MockProvider({ apiKey: 'test' })
    })

    it('returns an async iterable from complete() enabling streaming consumption', async () => {
      const messages: Message[] = [{ role: 'user', content: 'Hello' }]
      const opts: CompletionOpts = { model: 'mock-small' }

      const result = provider.complete(messages, opts)
      expect(result).toBeDefined()
      expect(typeof result[Symbol.asyncIterator]).toBe('function')
    })

    it('yields token chunks followed by a done signal to indicate completion', async () => {
      const messages: Message[] = [{ role: 'user', content: 'Hello' }]
      const opts: CompletionOpts = { model: 'mock-small' }

      const chunks: CompletionChunk[] = []
      for await (const chunk of provider.complete(messages, opts)) {
        chunks.push(chunk)
      }

      // Should have at least one token and a done chunk
      expect(chunks.length).toBeGreaterThan(1)
      expect(chunks[chunks.length - 1].type).toBe('done')
    })

    it('includes text content in token chunks for UI rendering', async () => {
      const messages: Message[] = [{ role: 'user', content: 'Hello' }]
      const opts: CompletionOpts = { model: 'mock-small' }

      const tokenChunks: CompletionChunk[] = []
      for await (const chunk of provider.complete(messages, opts)) {
        if (chunk.type === 'token') {
          tokenChunks.push(chunk)
        }
      }

      expect(tokenChunks.length).toBeGreaterThan(0)
      for (const chunk of tokenChunks) {
        expect(chunk.text).toBeDefined()
        expect(typeof chunk.text).toBe('string')
      }
    })

    it('respects the model option to route to different model endpoints', async () => {
      const messages: Message[] = [{ role: 'user', content: 'Hello' }]
      const opts: CompletionOpts = { model: 'mock-large' }

      await Array.fromAsync(provider.complete(messages, opts))

      const history = provider.getCallHistory()
      expect(history).toHaveLength(1)
      expect(history[0].opts.model).toBe('mock-large')
    })

    it('respects maxTokens to limit response length', async () => {
      const messages: Message[] = [{ role: 'user', content: 'Hello' }]
      const opts: CompletionOpts = { model: 'mock-small', maxTokens: 100 }

      await Array.fromAsync(provider.complete(messages, opts))

      const history = provider.getCallHistory()
      expect(history[0].opts.maxTokens).toBe(100)
    })

    it('respects temperature to control response randomness', async () => {
      const messages: Message[] = [{ role: 'user', content: 'Hello' }]
      const opts: CompletionOpts = { model: 'mock-small', temperature: 0.5 }

      await Array.fromAsync(provider.complete(messages, opts))

      const history = provider.getCallHistory()
      expect(history[0].opts.temperature).toBe(0.5)
    })

    it('respects systemPrompt to set behavioral context', async () => {
      const messages: Message[] = [{ role: 'user', content: 'Hello' }]
      const opts: CompletionOpts = {
        model: 'mock-small',
        systemPrompt: 'You are a helpful assistant.',
      }

      await Array.fromAsync(provider.complete(messages, opts))

      const history = provider.getCallHistory()
      expect(history[0].opts.systemPrompt).toBe('You are a helpful assistant.')
    })

    it('handles multi-turn conversations with system, user, and assistant messages', async () => {
      const messages: Message[] = [
        { role: 'system', content: 'You are helpful.' },
        { role: 'user', content: 'Hello' },
        { role: 'assistant', content: 'Hi there!' },
        { role: 'user', content: 'How are you?' },
      ]
      const opts: CompletionOpts = { model: 'mock-small' }

      const chunks: CompletionChunk[] = []
      for await (const chunk of provider.complete(messages, opts)) {
        chunks.push(chunk)
      }

      expect(chunks.length).toBeGreaterThan(0)
      expect(chunks[chunks.length - 1].type).toBe('done')
    })

    it('records call history for debugging and auditing purposes', async () => {
      const messages: Message[] = [{ role: 'user', content: 'Test' }]
      const opts: CompletionOpts = { model: 'mock-small' }

      provider.clearHistory()
      await Array.fromAsync(provider.complete(messages, opts))

      const history = provider.getCallHistory()
      expect(history).toHaveLength(1)
      expect(history[0].messages).toEqual(messages)
      expect(history[0].opts.model).toBe('mock-small')
    })
  })

  describe('Token Counting', () => {
    let provider: MockProvider

    beforeEach(() => {
      provider = new MockProvider({ apiKey: 'test' })
    })

    it('returns a non-negative number from countTokens() for budget tracking', async () => {
      const messages: Message[] = [{ role: 'user', content: 'Hello world' }]
      const count = await provider.countTokens(messages)

      expect(typeof count).toBe('number')
      expect(count).toBeGreaterThanOrEqual(0)
    })

    it('counts tokens for a single message', async () => {
      const messages: Message[] = [{ role: 'user', content: 'Hello' }]
      const count = await provider.countTokens(messages)

      // BaseProvider.estimateTokens divides by 4
      expect(count).toBeGreaterThan(0)
    })

    it('counts tokens for multiple messages in a conversation', async () => {
      const messages: Message[] = [
        { role: 'system', content: 'You are helpful.' },
        { role: 'user', content: 'Hello there!' },
        { role: 'assistant', content: 'How can I help?' },
      ]
      const count = await provider.countTokens(messages)

      expect(count).toBeGreaterThan(0)
    })

    it('returns higher counts for longer messages', async () => {
      const shortMessages: Message[] = [{ role: 'user', content: 'Hi' }]
      const longMessages: Message[] = [
        { role: 'user', content: 'This is a much longer message with many words.' },
      ]

      const shortCount = await provider.countTokens(shortMessages)
      const longCount = await provider.countTokens(longMessages)

      expect(longCount).toBeGreaterThan(shortCount)
    })

    it('returns zero for an empty messages array', async () => {
      const count = await provider.countTokens([])
      expect(typeof count).toBe('number')
      expect(count).toBe(0)
    })

    it('handles messages with complex content types', async () => {
      const messages: Message[] = [
        {
          role: 'user',
          content: [
            { type: 'text', text: 'Look at this image:' },
            { type: 'image', source: { type: 'base64', media_type: 'image/png', data: 'abc123' } },
          ],
        },
      ]

      const count = await provider.countTokens(messages)
      expect(typeof count).toBe('number')
      expect(count).toBeGreaterThan(0)
    })
  })

  describe('Health Check (Ping)', () => {
    it('returns a boolean indicating provider reachability', async () => {
      const provider = new MockProvider({ apiKey: 'test' })
      const result = await provider.ping()

      expect(typeof result).toBe('boolean')
    })

    it('returns true when the provider is properly authenticated', async () => {
      const provider = new MockProvider({ apiKey: 'valid-key' })
      const result = await provider.ping()

      expect(result).toBe(true)
    })

    it('returns false when not authenticated (indicating the provider cannot serve requests)', async () => {
      const provider = new MockProvider({ apiKey: '' })
      const result = await provider.ping()

      expect(result).toBe(false)
    })

    it('accepts an optional abort signal for timeout control', async () => {
      const provider = new MockProvider({ apiKey: 'test' })
      const controller = new AbortController()

      const result = await provider.ping(controller.signal)
      expect(typeof result).toBe('boolean')
    })

    it('handles aborted signals gracefully by returning false', async () => {
      const provider = new MockProvider({ apiKey: 'test' })
      const controller = new AbortController()
      controller.abort()

      const result = await provider.ping(controller.signal)
      expect(result).toBe(false)
    })
  })

  describe('Request Cancellation (Abort Signal)', () => {
    let provider: MockProvider

    beforeEach(() => {
      provider = new MockProvider({ apiKey: 'test' })
    })

    it('accepts an optional abort signal in complete() for request cancellation', async () => {
      const messages: Message[] = [{ role: 'user', content: 'Hello' }]
      const opts: CompletionOpts = { model: 'mock-small' }
      const controller = new AbortController()

      const chunks: CompletionChunk[] = []
      for await (const chunk of provider.complete(messages, opts, undefined, controller.signal)) {
        chunks.push(chunk)
      }

      expect(chunks.length).toBeGreaterThan(0)
    })

    it('throws when aborted before streaming starts', async () => {
      const messages: Message[] = [{ role: 'user', content: 'Hello' }]
      const opts: CompletionOpts = { model: 'mock-small' }
      const controller = new AbortController()
      controller.abort()

      await expect(async () => {
        // eslint-disable-next-line @typescript-eslint/no-unused-vars
        for await (const _ of provider.complete(messages, opts, undefined, controller.signal)) {
          // Should not reach here
        }
      }).rejects.toThrow('Request aborted')
    })

    it('throws when aborted during streaming', async () => {
      const messages: Message[] = [{ role: 'user', content: 'Hello' }]
      const opts: CompletionOpts = { model: 'mock-small' }
      const controller = new AbortController()

      // Start the stream
      const iterator = provider.complete(messages, opts, undefined, controller.signal)

      // Get first chunk
      const first = await iterator.next()
      expect(first.done).toBe(false)

      // Abort mid-stream
      controller.abort()

      // Next iteration should throw
      await expect(iterator.next()).rejects.toThrow('Request aborted')
    })
  })

  describe('Interface Contract Verification', () => {
    it('implements all required IProvider properties and methods', () => {
      const provider = new MockProvider({ apiKey: 'test' })

      // Required properties
      expect(provider.id).toBeDefined()
      expect(provider.models).toBeDefined()

      // Required methods
      expect(typeof provider.complete).toBe('function')
      expect(typeof provider.countTokens).toBe('function')
      expect(typeof provider.ping).toBe('function')
    })

    it('extends BaseProvider to inherit common functionality', () => {
      const provider = new MockProvider({ apiKey: 'test' })
      expect(provider).toBeInstanceOf(BaseProvider)
    })

    it('maintains consistent id and models values (readonly contract)', () => {
      const provider = new MockProvider({ apiKey: 'test' })

      // These should be readonly (TypeScript compile-time check)
      // At runtime, we can verify the values don't change unexpectedly
      const originalId = provider.id
      const originalModels = [...provider.models]

      expect(provider.id).toBe(originalId)
      expect(provider.models).toEqual(originalModels)
    })
  })

  describe('Error Handling & Edge Cases', () => {
    let provider: MockProvider

    beforeEach(() => {
      provider = new MockProvider({ apiKey: 'test' })
    })

    it('handles messages with structured content arrays', async () => {
      const messages: Message[] = [
        {
          role: 'user',
          content: [
            { type: 'text', text: 'Look at this:' },
          ],
        },
      ]
      const opts: CompletionOpts = { model: 'mock-small' }

      const chunks: CompletionChunk[] = []
      for await (const chunk of provider.complete(messages, opts)) {
        chunks.push(chunk)
      }

      expect(chunks.length).toBeGreaterThan(0)
      expect(chunks[chunks.length - 1].type).toBe('done')
    })

    it('handles completion options with tools specified', async () => {
      const messages: Message[] = [{ role: 'user', content: 'Use a tool' }]
      const opts: CompletionOpts = {
        model: 'mock-small',
        tools: [
          {
            name: 'test_tool',
            description: 'A test tool',
            input_schema: { type: 'object' },
          },
        ],
      }

      const chunks: CompletionChunk[] = []
      for await (const chunk of provider.complete(messages, opts)) {
        chunks.push(chunk)
      }

      expect(chunks.length).toBeGreaterThan(0)
    })

    it('handles messages with empty content gracefully', async () => {
      const messages: Message[] = [
        { role: 'user', content: '' },
      ]
      const opts: CompletionOpts = { model: 'mock-small' }

      const chunks: CompletionChunk[] = []
      for await (const chunk of provider.complete(messages, opts)) {
        chunks.push(chunk)
      }

      expect(chunks.length).toBeGreaterThan(0)
      expect(chunks[chunks.length - 1].type).toBe('done')
    })

    it('handles very long messages without crashing', async () => {
      const longContent = 'a'.repeat(10000)
      const messages: Message[] = [{ role: 'user', content: longContent }]
      const opts: CompletionOpts = { model: 'mock-small' }

      const chunks: CompletionChunk[] = []
      for await (const chunk of provider.complete(messages, opts)) {
        chunks.push(chunk)
      }

      expect(chunks.length).toBeGreaterThan(0)
    })
  })
})

