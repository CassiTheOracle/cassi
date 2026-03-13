/**
 * Session Manager
 * 
 * Simplified session management with unified storage
 */

import { createHash } from 'node:crypto';

import { SessionNotFoundError } from './types.js';

import type {
  SessionState,
  SessionManagerOptions,
  TurnMetadata,
  TurnRequest,
  SessionFilter,
  ISessionStore,
  ILogger,
  Message,
  IntelligenceContext
} from './types.js';


export interface GetOrCreateOptions {
  model?: string;
  systemPrompt?: string;
  maxTokens?: number;
  temperature?: number;
}

/**
 * Manages session lifecycle with caching
 */
export class SessionManager {
  // In-memory cache
  private cache = new Map<string, SessionState>();
  private logger: ILogger;
  private store: ISessionStore;
  private defaultModel: string;
  private defaultSystemPrompt: string;
  
  constructor(options: SessionManagerOptions) {
    this.store = options.store;
    this.logger = options.logger;
    this.defaultModel = options.defaultModel;
    this.defaultSystemPrompt = options.defaultSystemPrompt;
    
    this.logger.info('SessionManager initialized', {
      defaultModel: this.defaultModel
    });
  }
  
  /**
   * Get existing session or create new one
   */
  async getOrCreate(
    channelId: string,
    senderId: string,
    options?: GetOrCreateOptions
  ): Promise<SessionState> {
    const sessionId = this.generateId(channelId, senderId);
    
    // Check cache first
    const cached = this.cache.get(sessionId);
    if (cached) {
      cached.lastActiveAt = Date.now();
      this.logger.debug('Session cache hit', { sessionId });
      return cached;
    }
    
    // Try to load from store
    const stored = await this.store.load(sessionId);
    if (stored) {
      this.cache.set(sessionId, stored);
      this.logger.debug('Session loaded from store', { 
        sessionId, 
        messageCount: stored.messages.length 
      });
      return stored;
    }
    
    // Create new session
    const session = this.createNewSession(sessionId, channelId, senderId, options);
    
    await this.store.save(session);
    this.cache.set(sessionId, session);
    
    this.logger.info('New session created', { 
      sessionId, 
      channelId, 
      senderId,
      provider: session.model.split('/')[0] ?? 'unknown',
      model: session.model,
    });
    
    return session;
  }
  
  /**
   * Get session by ID
   */
  async get(sessionId: string): Promise<SessionState | null> {
    // Check cache
    const cached = this.cache.get(sessionId);
    if (cached) {
      return cached;
    }
    
    // Load from store
    const stored = await this.store.load(sessionId);
    if (stored) {
      this.cache.set(sessionId, stored);
    }
    
    return stored;
  }
  
  /**
   * Get session by channel and sender
   */
  async getBySender(channelId: string, senderId: string): Promise<SessionState | null> {
    const sessionId = this.generateId(channelId, senderId);
    return this.get(sessionId);
  }
  
  /**
   * Add a turn to session
   */
  async addTurn(
    sessionId: string,
    userContent: string,
    assistantResponse: string,
    metadata?: TurnMetadata
  ): Promise<SessionState> {
    const session = await this.get(sessionId);
    if (!session) {
      throw new SessionNotFoundError(sessionId);
    }
    
    const now = Date.now();
    
    // Add user message
    const userMessage: Message = {
      role: 'user',
      content: userContent,
      timestamp: now
    };
    session.messages.push(userMessage);
    
    // If tools were used, store the full tool conversation
    if (metadata?.toolCalls && metadata.toolCalls.length > 0) {
      // Group tool calls by round — each round has an assistant message with tool calls
      // followed by a user message with the corresponding tool results
      const toolCalls = metadata.toolCalls;
      
      // For multi-round tool use, we need to reconstruct the conversation.
      // Since we only get the flat list, store as a single round:
      // assistant (with tool_calls) → user (with tool_results)
      const assistantToolMessage: Message = {
        role: 'assistant',
        content: '',  // Tool-calling turns typically have empty text content
        timestamp: now,
        toolCalls: toolCalls.map(t => ({
          id: t.toolCallId,
          name: t.toolName,
          input: {}
        }))
      };
      session.messages.push(assistantToolMessage);
      
      const toolResultMessage: Message = {
        role: 'user',
        content: '',
        timestamp: now,
        toolResults: toolCalls.map(t => ({
          toolCallId: t.toolCallId,
          content: t.content ?? '',
          isError: t.isError ?? false
        }))
      };
      session.messages.push(toolResultMessage);
    }
    
    // Add final assistant response
    const assistantMessage: Message = {
      role: 'assistant',
      content: assistantResponse,
      timestamp: now
    };
    session.messages.push(assistantMessage);
    
    session.turnCount++;
    session.lastActiveAt = now;
    
    // Persist
    await this.store.save(session);
    this.cache.set(sessionId, session);
    
    this.logger.debug('Turn added to session', {
      sessionId,
      turnCount: session.turnCount,
      tokensUsed: metadata?.tokensUsed,
      toolCalls: metadata?.toolCalls?.length ?? 0
    });
    
    return session;
  }
  
  /**
   * Update session context (from intelligence layer)
   */
  async updateContext(
    sessionId: string,
    context: Partial<IntelligenceContext>
  ): Promise<void> {
    const session = await this.get(sessionId);
    if (!session) {
      this.logger.warn('Cannot update context - session not found', { sessionId });
      return;
    }
    
    session.context = {
      ...session.context,
      ...context,
      updatedAt: Date.now()
    };
    
    await this.store.save(session);
    this.cache.set(sessionId, session);
    
    this.logger.debug('Session context updated', {
      sessionId,
      contextKeys: Object.keys(context)
    });
  }
  
  /**
   * Clear session history (but keep session)
   */
  async clear(sessionId: string): Promise<SessionState> {
    const session = await this.get(sessionId);
    if (!session) {
      throw new SessionNotFoundError(sessionId);
    }
    
    session.messages = [];
    session.turnCount = 0;
    session.context = {};
    session.lastActiveAt = Date.now();
    
    await this.store.save(session);
    this.cache.set(sessionId, session);
    
    this.logger.info('Session cleared', { sessionId });
    
    return session;
  }
  
  /**
   * Delete session completely
   */
  async delete(sessionId: string): Promise<void> {
    this.cache.delete(sessionId);
    await this.store.delete(sessionId);
    
    this.logger.info('Session deleted', { sessionId });
  }
  
  /**
   * List sessions
   */
  async list(filter?: SessionFilter): Promise<SessionState[]> {
    return this.store.list(filter);
  }
  
  /**
   * Get all active sessions from cache
   */
  getCachedSessions(): SessionState[] {
    return Array.from(this.cache.values());
  }
  
  /**
   * Invalidate cache for session
   */
  invalidateCache(sessionId: string): void {
    this.cache.delete(sessionId);
  }
  
  /**
   * Clear all cached sessions
   */
  clearCache(): void {
    this.cache.clear();
    this.logger.info('Session cache cleared');
  }
  
  /**
   * Get session statistics
   */
  async getStats(): Promise<{
    cached: number;
    persisted: number;
  }> {
    const cached = this.cache.size;
    const persisted = await (this.store as any).count?.() ?? 0;
    
    return { cached, persisted };
  }
  
  /**
   * Create a request object from session
   */
  createRequest(sessionId: string, content: string): TurnRequest {
    return {
      sessionId,
      channelId: '',  // Will be filled from session
      senderId: '',   // Will be filled from session
      content
    };
  }
  
  // ============================================================================
  // Private Methods
  // ============================================================================
  
  private generateId(channelId: string, senderId: string): string {
    // Deterministic ID based on channel + sender
    const hash = createHash('sha256')
      .update(`${channelId}:${senderId}`)
      .digest('hex')
      .slice(0, 16);
    
    return hash;
  }
  
  private createNewSession(
    sessionId: string,
    channelId: string,
    senderId: string,
    options?: GetOrCreateOptions
  ): SessionState {
    const now = Date.now();
    
    return {
      id: sessionId,
      channelId,
      senderId,
      messages: [],
      model: options?.model ?? this.defaultModel,
      systemPrompt: options?.systemPrompt ?? this.defaultSystemPrompt,
      maxTokens: options?.maxTokens ?? 4096,
      temperature: options?.temperature ?? 0.7,
      createdAt: now,
      lastActiveAt: now,
      turnCount: 0
    };
  }
}

/**
 * Factory function for creating SessionManager
 */
export function createSessionManager(
  store: ISessionStore,
  options: {
    defaultModel: string;
    defaultSystemPrompt: string;
    logger: ILogger;
  }
): SessionManager {
  return new SessionManager({
    store,
    ...options
  });
}
