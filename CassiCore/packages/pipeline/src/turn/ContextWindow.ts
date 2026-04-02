/**
 * Context Window Manager
 * 
 * Manages context window limits by trimming conversation history.
 * Uses layered compaction to produce structured summaries of older
 * messages before falling back to hard FIFO trimming.
 */

import type { Message, ILogger } from '../session/types.js'
import { CHARS_PER_TOKEN } from '../../intelligence/shared/token-estimation.js'

// WHY: Lazy-load compaction module to avoid hard dependency.
// The module may not be available in all deployment contexts,
// and we don't want the import to block ContextWindow initialization.
let compactionModule: typeof import('../../intelligence/layered-compaction.js') | null = null
let compactionLoadAttempted = false

async function getCompactionModule() {
  if (compactionLoadAttempted) return compactionModule
  compactionLoadAttempted = true
  try {
    compactionModule = await import('../../intelligence/layered-compaction.js')
  } catch {
    // Compaction not available — will use FIFO trimming only
  }
  return compactionModule
}

export interface ContextWindowOptions {
  maxTokens?: number;
  charsPerToken?: number;
  preserveSystemMessages?: boolean;
  logger?: ILogger;
  /** Optional debug callback invoked after every trim() with context stats. */
  onTrimDebug?: (stats: TrimDebugInfo) => void;
}

export interface TrimDebugInfo {
  inputMessages: number;
  outputMessages: number;
  compactionApplied: boolean;
  estimatedInputTokens: number;
  estimatedOutputTokens: number;
}

/**
 * Manages context window limits
 */
export class ContextWindow {
  private maxTokens: number;
  private charsPerToken: number;
  private preserveSystem: boolean;
  private logger?: ILogger;
  private onTrimDebug?: (stats: TrimDebugInfo) => void;
  
  constructor(options: ContextWindowOptions = {}) {
    this.maxTokens = options.maxTokens ?? 200000
    this.charsPerToken = options.charsPerToken ?? CHARS_PER_TOKEN
    this.preserveSystem = options.preserveSystemMessages ?? true
    this.logger = options.logger
    this.onTrimDebug = options.onTrimDebug
  }
  
  /**
   * Trim messages to fit within context window
   * 
   * Strategy:
   * 1. Try layered compaction first (structured summary of older messages)
   * 2. Always keep system messages
   * 3. Always keep the most recent user message
   * 4. Drop older conversation history as needed (FIFO safety net)
   */
  trim(messages: Message[]): Message[] {
    if (messages.length === 0) {
      return messages;
    }
    
    // Phase 1: Try layered compaction if available
    // This produces a structured summary of older messages while preserving
    // recent ones verbatim. Summaries merge across compaction rounds.
    const compacted = this.tryCompaction(messages);
    const workingMessages = compacted ?? messages;
    
    // Phase 2: Hard window trim as FIFO safety net
    // Single-pass partition: separate system vs conversation messages
    const systemMessages: Message[] = [];
    const conversation: Message[] = [];
    
    for (const m of workingMessages) {
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

  /**
   * Try layered compaction on the message array.
   * Returns compacted messages, or null if compaction is unavailable/unnecessary.
   */
  private tryCompaction(messages: Message[]): Message[] | null {
    if (!compactionModule) return null
    if (messages.length < 8) return null // Not enough messages to compact

    const compactionConfig = {
      preserveRecentMessages: 6,
      maxEstimatedTokens: Math.floor(this.maxTokens * 0.7),
    }

    // HOW: The layered compaction module uses the runtime Message type,
    // which is structurally compatible with the pipeline Message type
    // (both have role: 'user'|'assistant'|'system' and content: string|ContentBlock[]).
    // We cast to any to bridge the type boundary.
    const runtimeMessages = messages as any[]

    if (!compactionModule.shouldCompact(runtimeMessages, compactionConfig)) {
      return null
    }

    const result = compactionModule.compactMessages(runtimeMessages, compactionConfig)
    if (result.removedMessageCount > 0) {
      this.logger?.info('Layered compaction applied', {
        removedMessages: result.removedMessageCount,
        preservedMessages: result.compactedMessages.length,
        originalMessages: messages.length,
      })
      return result.compactedMessages as unknown as Message[]
    }

    return null
  }
}

/**
 * Create context window with safe defaults
 */
export function createSafeContextWindow(logger?: ILogger): ContextWindow {
  return new ContextWindow({
    maxTokens: 100000,
    charsPerToken: CHARS_PER_TOKEN,
    preserveSystemMessages: true,
    logger,
  })
}
