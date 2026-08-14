/**
 * Message Builder
 * 
 * Constructs message arrays from session state and requests
 */

import type { ContentBlock } from '@cassicore/foundation'
import type {
  SessionState,
  TurnRequest,
  Message,
  ILogger
} from '../session/types.js'
import { CHARS_PER_TOKEN } from '@cassicore/embeddings'

export interface MessageBuilderOptions {
  logger?: ILogger;
  includeSessionMarker?: boolean;
}

/**
 * Builds message arrays for provider requests.
 * Supports an injection queue for optimizer steering, dialectic signals,
 * cognitive feed injection, and other system-level content that should
 * be prepended to the next turn's messages.
 */
export class MessageBuilder {
  private logger?: ILogger;
  private includeSessionMarker: boolean;

  /** Queue of system content to inject on the next build() call. */
  private injectionQueue: string[] = [];
  
  constructor(options: MessageBuilderOptions = {}) {
    this.logger = options.logger;
    this.includeSessionMarker = options.includeSessionMarker ?? true;
  }

  /**
   * Queue content for injection on the next turn.
   * Used by optimizer steering, dialectic signals, cognitive feed, etc.
   * The content is injected as a system message and consumed (cleared) after use.
   */
  injectOnNextTurn(content: string): void {
    if (!content.trim()) return
    this.injectionQueue.push(content.trim())
    this.logger?.debug('Queued injection for next turn', { length: content.length })
  }

  /** Get the current injection queue length (for diagnostics). */
  get pendingInjections(): number {
    return this.injectionQueue.length
  }
  
  /**
   * Build complete message list for a turn
   */
  build(session: SessionState, request: TurnRequest): Message[] {
    const messages: Message[] = [];
    const now = Date.now();
    
    // 1. System prompt
    if (session.systemPrompt) {
      let systemContent = session.systemPrompt;
      
      // Add session marker for tracking
      if (this.includeSessionMarker) {
        systemContent += `\n\n[session:${session.id}]`;
      }
      
      messages.push({
        role: 'system',
        content: systemContent,
        timestamp: now
      });
    }

    // 1b. Consume injection queue — append to system context
    if (this.injectionQueue.length > 0) {
      const injected = this.injectionQueue.join('\n\n')
      this.injectionQueue = [] // Consume
      messages.push({
        role: 'system',
        content: injected,
        timestamp: now,
      })
      this.logger?.debug('Consumed injection queue', { length: injected.length })
    }
    
    // 2. Intelligence context (if available and fresh)
    if (session.context) {
      const contextMessages = this.buildContextMessages(session.context);
      messages.push(...contextMessages);
    }
    
    // 3. Conversation history
    messages.push(...session.messages);
    
    // 4. Current request
    const userMessage = this.buildUserMessage(request);
    messages.push(userMessage);
    
    this.logger?.debug('Messages built', {
      sessionId: session.id,
      messageCount: messages.length,
      hasAttachments: !!request.attachments?.length,
      hasContext: !!session.context
    });
    
    return messages;
  }
  
  /**
   * Build system messages from intelligence context
   */
  private buildContextMessages(context: NonNullable<SessionState['context']>): Message[] {
    const messages: Message[] = [];
    const now = Date.now();
    
    // Recent memories
    if (context.recentMemories?.length) {
      messages.push({
        role: 'system',
        content: `[Context from memory]:\n${context.recentMemories.join('\n')}`,
        timestamp: now
      });
    }
    
    // Dialectic insights
    if (context.dialecticInsights?.length) {
      messages.push({
        role: 'system',
        content: `[Dialectic analysis]:\n${context.dialecticInsights.join('\n\n')}`,
        timestamp: now
      });
    }
    
    // Thinker notes
    if (context.thinkerNotes?.length) {
      messages.push({
        role: 'system',
        content: `[Thinker insights]:\n${context.thinkerNotes.join('\n\n')}`,
        timestamp: now
      });
    }
    
    // Subconscious signals
    if (context.subconsciousSignals?.length) {
      messages.push({
        role: 'system',
        content: `[Background signals]:\n${context.subconsciousSignals.join('\n\n')}`,
        timestamp: now
      });
    }

    // InjectionAggregator injections (Corpus, SessionDigest, Optimizer, Dreamer, etc.)
    if (context.injections?.length) {
      for (const injection of context.injections) {
        messages.push({
          role: 'system',
          content: injection,
          timestamp: now
        });
      }
    }
    
    return messages;
  }
  
  /**
   * Build user message from request
   */
  private buildUserMessage(request: TurnRequest): Message {
    const now = Date.now();
    
    // Handle attachments (images)
    if (request.attachments && request.attachments.length > 0) {
      const contentBlocks: any[] = [];
      
      // Add images first
      for (const attachment of request.attachments) {
        contentBlocks.push({
          type: 'image',
          source: {
            type: 'base64',
            media_type: attachment.mediaType,
            data: attachment.data
          }
        });
      }
      
      // Add text
      contentBlocks.push({
        type: 'text',
        text: request.content || '(image)'
      });
      
      return {
        role: 'user',
        content: contentBlocks,
        timestamp: now
      };
    }
    
    // Simple text message
    return {
      role: 'user',
      content: request.content,
      timestamp: now
    };
  }
  
  /**
   * Add a system message at the beginning
   */
  prependSystemMessage(messages: Message[], content: string): Message[] {
    const now = Date.now();
    
    return [
      {
        role: 'system',
        content,
        timestamp: now
      },
      ...messages
    ];
  }
  
  /**
   * Estimate token count (rough approximation)
   */
  estimateTokens(messages: Message[]): number {
    return messages.reduce((sum, msg) => {
      const text = typeof msg.content === 'string'
        ? msg.content
        : JSON.stringify(msg.content)

      return sum + Math.ceil(text.length / CHARS_PER_TOKEN)
    }, 0)
  }
}
