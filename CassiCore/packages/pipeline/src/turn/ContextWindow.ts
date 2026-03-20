/**
 * Context Window Manager
 * 
 * Manages context window limits by trimming conversation history
 */

import type { Message, ILogger } from '../session/types.js';

export interface ContextWindowOptions {
  maxTokens?: number;
  charsPerToken?: number;
  preserveSystemMessages?: boolean;
  logger?: ILogger;
}

/**
 * Manages context window limits
 */
export class ContextWindow {
  private maxTokens: number;
  private charsPerToken: number;
  private preserveSystem: boolean;
  private logger?: ILogger;
  
  constructor(options: ContextWindowOptions = {}) {
    this.maxTokens = options.maxTokens ?? 200000;
    this.charsPerToken = options.charsPerToken ?? 4;
    this.preserveSystem = options.preserveSystemMessages ?? true;
    this.logger = options.logger;
  }
  
  /**
   * Trim messages to fit within context window
   * 
   * Strategy:
   * 1. Always keep system messages
   * 2. Always keep the most recent user message
   * 3. Drop older conversation history as needed
   */
  trim(messages: Message[]): Message[] {
    if (messages.length === 0) {
      return messages;
    }
    
    // Single-pass partition: separate system vs conversation messages
    const systemMessages: Message[] = [];
    const conversation: Message[] = [];
    
    for (const m of messages) {
      if (this.preserveSystem && m.role === 'system') {
        systemMessages.push(m);
      } else {
        conversation.push(m);
      }
    }
    
    if (conversation.length === 0) {
      return systemMessages;
    }
    
    // Always keep the last user message (not assistant)
    let lastUserIndex = conversation.length - 1;
    while (lastUserIndex >= 0 && conversation[lastUserIndex].role !== 'user') {
      lastUserIndex--;
    }
    
    // If no user message found, just use the last message
    if (lastUserIndex < 0) {
      lastUserIndex = conversation.length - 1;
    }
    
    const lastMessage = conversation[lastUserIndex];
    const history = conversation.slice(0, lastUserIndex);
    
    // Calculate budget
    const budget = this.maxTokens * this.charsPerToken;
    let used = this.estimateChars(systemMessages) + this.estimateChars([lastMessage]);
    
    // Keep adding history from most recent until we hit the limit
    // Build in reverse order with push (O(1) amortized), then reverse once (O(n))
    const kept: Message[] = [];
    
    for (let i = history.length - 1; i >= 0; i--) {
      const msg = history[i];
      const chars = this.estimateChars([msg]);
      
      if (used + chars > budget) {
        this.logger?.debug('Context window limit reached', {
          keptMessages: kept.length,
          droppedMessages: i + 1,
          estimatedTokens: Math.ceil(used / this.charsPerToken)
        });
        break;
      }
      
      kept.push(msg);
      used += chars;
    }
    
    // Reverse once instead of O(n) unshift per iteration
    kept.reverse();
    
    // Build final message list
    const result = [
      ...systemMessages,
      ...kept,
      lastMessage
    ];
    
    this.logger?.debug('Context window trimmed', {
      originalCount: messages.length,
      finalCount: result.length,
      systemCount: systemMessages.length,
      historyKept: kept.length,
      estimatedTokens: Math.ceil(used / this.charsPerToken)
    });
    
    return result;
  }
  
  /**
   * Trim to specific token count (for testing/debugging)
   */
  trimToTokens(messages: Message[], maxTokens: number): Message[] {
    const originalMax = this.maxTokens;
    this.maxTokens = maxTokens;
    
    try {
      return this.trim(messages);
    } finally {
      this.maxTokens = originalMax;
    }
  }
  
  /**
   * Check if messages fit within context window
   */
  fits(messages: Message[]): boolean {
    const estimated = this.estimateTokens(messages);
    return estimated <= this.maxTokens;
  }
  
  /**
   * Estimate token count
   */
  estimateTokens(messages: Message[]): number {
    return Math.ceil(this.estimateChars(messages) / this.charsPerToken);
  }
  
  /**
   * Get context window stats
   */
  getStats(messages: Message[]): {
    messageCount: number;
    estimatedTokens: number;
    estimatedChars: number;
    fits: boolean;
  } {
    const chars = this.estimateChars(messages);
    const tokens = Math.ceil(chars / this.charsPerToken);
    
    return {
      messageCount: messages.length,
      estimatedTokens: tokens,
      estimatedChars: chars,
      fits: tokens <= this.maxTokens
    };
  }
  
  // Private Methods
  
  private estimateChars(messages: Message[]): number {
    return messages.reduce((sum, msg) => {
      if (typeof msg.content === 'string') {
        return sum + msg.content.length;
      }
      
      // Handle ContentBlock[]
      return sum + msg.content.reduce((blockSum, block: any) => {
        if (block.type === 'text') {
          return blockSum + block.text.length;
        }
        if (block.type === 'image' && block.source?.data) {
          // Base64 image data
          return blockSum + block.source.data.length;
        }
        return blockSum + 100; // Default for other types
      }, 0);
    }, 0);
  }
}

/**
 * Create context window with safe defaults
 */
export function createSafeContextWindow(logger?: ILogger): ContextWindow {
  return new ContextWindow({
    maxTokens: 100000,  // Conservative default
    charsPerToken: 4,
    preserveSystemMessages: true,
    logger
  });
}
