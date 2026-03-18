/**
 * CassiCore Compatibility Layer
 * 
 * Tight integration between pi-ai and CassiCore's provider system.
 * This allows CassiCore to use pi-ai's unified provider layer directly.
 */

import type { 
  IProvider,
  Message as CassiCoreMessage,
  CompletionOpts as CassiCoreOpts,
  CompletionChunk as CassiCoreChunk,
  ImageAttachment,
  ThinkingLevel as CassiCoreThinkingLevel,
  IConfig,
  ILogger
} from './cassicore-types/index.js';

import type {
  Api,
  Model,
  Context,
  AssistantMessageEvent,
  SimpleStreamOptions,
  ThinkingLevel,
  KnownProvider
} from './types.js';

import { streamSimpleOpenAICompletions } from './providers/openai-completions.js';
import { streamSimpleAnthropic } from './providers/anthropic.js';
import { streamSimpleGoogleGeminiCli } from './providers/google-gemini-cli.js';

import { kimiModels, getKimiModel } from './providers/cassicore/kimi-coding.js';
import { qwenModels, getQwenModel, QwenLoadBalancer } from './providers/cassicore/qwen.js';
import { openrouterModels, getOpenRouterModel } from './providers/cassicore/openrouter.js';

/**
 * Stream function type alias
 */
type StreamFunction = (model: Model<Api>, context: Context, opts?: SimpleStreamOptions) =>
  AsyncIterable<AssistantMessageEvent>;

/**
 * CassiCoreProviderAdapter
 * 
 * Implements CassiCore's IProvider interface using pi-ai's native API.
 * This is the tight integration point - no external dependencies.
 */
class CassiCoreProviderAdapter implements IProvider {
  readonly id: string;
  readonly models: string[];
  private streamFn: StreamFunction;
  
  constructor(
    private model: Model<Api>,
    providerId: string,
    streamFn: StreamFunction
  ) {
    this.id = providerId;
    this.models = [model.id];
    this.streamFn = streamFn;
  }

  async *complete(
    messages: CassiCoreMessage[],
    opts: CassiCoreOpts,
    attachments?: ImageAttachment[],
    signal?: AbortSignal
  ): AsyncIterable<CassiCoreChunk> {
    // Convert CassiCore messages to pi-ai Context
    const context = toPiContext(messages, opts.systemPrompt, attachments);
    
    // Build stream options
    const streamOpts: SimpleStreamOptions = {
      maxTokens: opts.maxTokens,
      temperature: opts.temperature,
      reasoning: mapThinkingLevel(opts.thinking),
      signal
    };

    // Stream from pi-ai and convert events
    const stream = this.streamFn(this.model, context, streamOpts);
    
    for await (const event of stream) {
      yield* toCassiCoreChunks(event);
    }
  }

  async countTokens(messages: CassiCoreMessage[]): Promise<number> {
    // Estimate tokens: ~4 chars per token
    let total = 0;
    for (const msg of messages) {
      const content = typeof msg.content === 'string' 
        ? msg.content 
        : msg.content.map(c => 'text' in c ? c.text : '').join('');
      total += Math.ceil(content.length / 4);
    }
    return total;
  }

  async ping(signal?: AbortSignal): Promise<boolean> {
    try {
      // Simple ping - try to get model info
      return !!this.model;
    } catch {
      return false;
    }
  }
}

/**
 * Create providers from CassiCore config
 * 
 * This is the main entry point for CassiCore integration.
 * Reads provider configuration and creates IProvider instances.
 */
export function createProviders(
  config: IConfig,
  logger: ILogger
): Map<string, IProvider> {
  const providers = new Map<string, IProvider>();
  
  // Load providers from config
  const providerConfigs = config.get<Array<{
    id: string;
    api: Api;
    baseUrl: string;
    apiKey: string;
    models: string[];
  }>>('ai.providers', []);
  
  for (const pc of providerConfigs) {
    try {
      for (const modelId of pc.models) {
        // Build model definition
        const model: Model<Api> = {
          id: modelId,
          name: modelId,
          api: pc.api,
          provider: pc.id as KnownProvider,
          baseUrl: pc.baseUrl,
          reasoning: false,
          input: ['text'],
          cost: { input: 0, output: 0, cacheRead: 0, cacheWrite: 0 },
          contextWindow: 128000,
          maxTokens: 4096
        };
        
        const streamFn = getStreamFunction(pc.api);
        const adapter = new CassiCoreProviderAdapter(model, pc.id, streamFn);
        providers.set(`${pc.id}/${modelId}`, adapter);
      }
      
      logger.info(`[ai] Loaded provider: ${pc.id} with ${pc.models.length} models`);
    } catch (err) {
      logger.error(`[ai] Failed to load provider ${pc.id}: ${err}`);
    }
  }
  
  // Auto-register common providers from environment
  registerEnvProviders(providers, logger);
  
  return providers;
}

/**
 * Get the appropriate stream function for an API type
 */
function getStreamFunction(api: Api): StreamFunction {
  switch (api) {
    case 'openai-completions':
      return streamSimpleOpenAICompletions as StreamFunction;
    case 'anthropic-messages':
      return streamSimpleAnthropic as StreamFunction;
    case 'google-gemini-cli':
      return streamSimpleGoogleGeminiCli as StreamFunction;
    default:
      return streamSimpleOpenAICompletions as StreamFunction;
  }
}

/**
 * Convert CassiCore messages to pi-ai Context
 */
function toPiContext(
  messages: CassiCoreMessage[], 
  systemPrompt?: string,
  attachments?: ImageAttachment[]
): Context {
  const piMessages: any[] = [];
  
  for (const msg of messages) {
    if (msg.role === 'user') {
      const content: any[] = [];
      
      // Handle text content
      if (typeof msg.content === 'string') {
        content.push({ type: 'text', text: msg.content });
      } else {
        // Handle content blocks
        for (const block of msg.content) {
          if (block.type === 'text') {
            content.push({ type: 'text', text: block.text });
          }
        }
      }
      
      // Handle attachments
      if (attachments && attachments.length > 0 && piMessages.length === 0) {
        for (const att of attachments) {
          content.push({
            type: 'image',
            data: att.data,
            mimeType: att.mediaType
          });
        }
      }
      
      piMessages.push({
        role: 'user',
        content: content.length === 1 && content[0].type === 'text' 
          ? content[0].text 
          : content,
        timestamp: Date.now()
      });
      
    } else if (msg.role === 'assistant') {
      const content: any[] = [];
      
      if (typeof msg.content === 'string') {
        content.push({ type: 'text', text: msg.content });
      } else {
        for (const block of msg.content) {
          if (block.type === 'text') {
            content.push({ type: 'text', text: block.text });
          } else if (block.type === 'tool_use') {
            content.push({
              type: 'toolCall',
              id: block.id,
              name: block.name,
              arguments: block.input
            });
          }
        }
      }
      
      piMessages.push({
        role: 'assistant',
        content,
        api: 'openai-completions' as Api,
        provider: 'unknown' as KnownProvider,
        model: 'unknown',
        usage: { input: 0, output: 0, cacheRead: 0, cacheWrite: 0, totalTokens: 0, cost: { input: 0, output: 0, cacheRead: 0, cacheWrite: 0, total: 0 } },
        stopReason: 'stop' as const,
        timestamp: Date.now()
      });
    }
  }
  
  return {
    systemPrompt,
    messages: piMessages
  };
}

/**
 * Convert pi-ai AssistantMessageEvent to CassiCore CompletionChunks
 */
function* toCassiCoreChunks(event: AssistantMessageEvent): Generator<CassiCoreChunk> {
  switch (event.type) {
    case 'start':
      // No equivalent in CassiCore
      break;
      
    case 'text_start':
      // Start of text block
      break;
      
    case 'text_delta':
      yield { 
        type: 'token', 
        text: event.delta,
        model: event.partial.model
      };
      break;
      
    case 'text_end':
      // End of text block
      break;
      
    case 'thinking_start':
      // Start of thinking block
      break;
      
    case 'thinking_delta':
      yield { 
        type: 'thinking', 
        text: event.delta,
        model: event.partial.model
      };
      break;
      
    case 'thinking_end':
      // End of thinking block
      break;
      
    case 'toolcall_start':
      // Tool call started
      break;
      
    case 'toolcall_delta':
      // Tool call streaming (partial JSON)
      break;
      
    case 'toolcall_end':
      yield { 
        type: 'tool_use',
        toolCall: {
          id: event.toolCall.id,
          name: event.toolCall.name,
          input: event.toolCall.arguments
        },
        model: event.partial.model
      };
      break;
      
    case 'done':
      yield { 
        type: 'done',
        tokensUsed: event.message.usage.totalTokens,
        tokenBreakdown: {
          input: event.message.usage.input ?? 0,
          output: event.message.usage.output ?? 0,
          cacheRead: event.message.usage.cacheRead ?? 0,
          cacheWrite: event.message.usage.cacheWrite ?? 0,
        },
        model: event.message.model
      };
      break;
      
    case 'error':
      yield { 
        type: 'error', 
        error: event.error.errorMessage || 'Unknown error',
        model: event.error.model
      };
      break;
  }
}

/**
 * Map CassiCore thinking level to pi-ai thinking level
 */
function mapThinkingLevel(level?: CassiCoreThinkingLevel): ThinkingLevel | undefined {
  if (!level || level === 'none') return undefined;
  
  const map: Record<CassiCoreThinkingLevel, ThinkingLevel> = {
    'none': 'minimal',
    'low': 'low',
    'medium': 'medium',
    'high': 'high'
  };
  
  return map[level];
}

/**
 * Auto-register providers from environment variables
 */
function registerEnvProviders(providers: Map<string, IProvider>, logger: ILogger): void {
  // Kimi
  const kimiKey = process.env.KIMI_API_KEY;
  if (kimiKey) {
    for (const model of kimiModels) {
      const streamFn: StreamFunction = async function*(m, ctx, opts) {
        // Use kimi-specific stream with auth
        const optsWithAuth = {
          ...opts,
          headers: {
            ...opts?.headers,
            'Authorization': `Bearer ${kimiKey}`
          }
        };
        yield* streamSimpleOpenAICompletions(m as Model<'openai-completions'>, ctx, optsWithAuth);
      };
      const adapter = new CassiCoreProviderAdapter(model, 'kimi-coding', streamFn);
      providers.set(`kimi-coding/${model.id}`, adapter);
    }
    logger.info(`[ai] Auto-registered kimi-coding with ${kimiModels.length} models`);
  }
  
  // Qwen
  const qwenKey = process.env.QWEN_API_KEY || process.env.DASHSCOPE_API_KEY;
  if (qwenKey) {
    for (const model of qwenModels) {
      const streamFn: StreamFunction = async function*(m, ctx, opts) {
        const optsWithAuth = {
          ...opts,
          headers: {
            ...opts?.headers,
            'Authorization': `Bearer ${qwenKey}`
          }
        };
        yield* streamSimpleOpenAICompletions(m as Model<'openai-completions'>, ctx, optsWithAuth);
      };
      const adapter = new CassiCoreProviderAdapter(model, 'qwen', streamFn);
      providers.set(`qwen/${model.id}`, adapter);
    }
    logger.info(`[ai] Auto-registered qwen with ${qwenModels.length} models`);
  }
  
  // OpenRouter
  const openrouterKey = process.env.OPENROUTER_API_KEY;
  if (openrouterKey) {
    for (const model of openrouterModels) {
      const streamFn: StreamFunction = async function*(m, ctx, opts) {
        const optsWithAuth = {
          ...opts,
          headers: {
            ...opts?.headers,
            'Authorization': `Bearer ${openrouterKey}`,
            'HTTP-Referer': 'https://cassicore.local',
            'X-Title': 'CassiCore'
          }
        };
        yield* streamSimpleOpenAICompletions(m as Model<'openai-completions'>, ctx, optsWithAuth);
      };
      const adapter = new CassiCoreProviderAdapter(model, 'openrouter', streamFn);
      providers.set(`openrouter/${model.id}`, adapter);
    }
    logger.info(`[ai] Auto-registered openrouter with ${openrouterModels.length} models`);
  }
}

// Export the adapter class for external use
export { CassiCoreProviderAdapter };
