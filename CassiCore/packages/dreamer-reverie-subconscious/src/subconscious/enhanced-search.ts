/**
 * Enhanced Subconscious Search Module
 *
 * Expands the subconscious's read-along capability to:
 * 1. Extract entities and topics from streaming conversation
 * 2. Generate semantic search queries using LLM
 * 3. Search across multiple data sources (memory, files, web)
 * 4. Cache and rank retrieved information
 * 5. Proactively inject relevant context into conversations
 * 6. Track conversation state to avoid redundant searches
 */

import type { ILogger } from '../../../types/interfaces.js';
import type { IMemory } from '../../../types/intelligence.js';
import type { IProvider } from '../../../types/runtime.js';
import type { SessionDigestStore } from '../session-digest.js';

export interface SearchContext {
  sessionId: string;
  turnId: string;
  userMessage: string;
  assistantResponse: string;
  tokens: string[];
  entities: string[];
  topics: string[];
  lastSearchAt?: number;
  retrievedContext: RetrievedItem[];
}

export interface RetrievedItem {
  id: string;
  source: 'memory' | 'file' | 'web' | 'learned' | 'cross-session';
  content: string;
  relevance: number;
  query: string;
  retrievedAt: number;
  used: boolean;
}

export interface EntityExtraction {
  entities: string[];      // Specific names: files, functions, people, projects
  topics: string[];        // General subjects: "authentication", "performance"
  intent: string;          // What the user is trying to do
  gaps: string[];          // What information seems to be missing
}

export interface SearchConfig {
  enabled: boolean;
  maxTokensToAnalyze: number;      // How many tokens to buffer before analyzing
  searchCooldownMs: number;        // Minimum time between searches
  minRelevanceToInject: number;    // Threshold for auto-injection (0-1)
  maxContextToInject: number;      // Max items to inject per turn
  maxRetrievedCache: number;       // Max items to keep per session
  enableWebSearch: boolean;
  enableFileSearch: boolean;
  enableMemorySearch: boolean;
  provider?: IProvider;            // LLM for query generation
}

export class SubconsciousSearch {
  private logger: ILogger;
  private memory?: IMemory;
  private provider?: IProvider;
  private config: SearchConfig;
  private digestStore?: SessionDigestStore;

  // Session-level search state
  private sessionContexts = new Map<string, SearchContext>();
  private lastSearchTime = new Map<string, number>();
  private pendingSearches = new Map<string, Promise<void>>();

  // Global retrieved items cache (for cross-session deduplication)
  private globalRetrievedCache = new Map<string, RetrievedItem>();

  constructor(logger: ILogger, config?: Partial<SearchConfig>) {
    this.logger = logger.child?.('subconscious-search') ?? logger;
    this.config = {
      enabled: config?.enabled ?? true,
      maxTokensToAnalyze: config?.maxTokensToAnalyze ?? 100,
      searchCooldownMs: config?.searchCooldownMs ?? 5000,
      minRelevanceToInject: config?.minRelevanceToInject ?? 0.75,
      maxContextToInject: config?.maxContextToInject ?? 3,
      maxRetrievedCache: config?.maxRetrievedCache ?? 20,
      enableWebSearch: config?.enableWebSearch ?? false, // Off by default (expensive)
      enableFileSearch: config?.enableFileSearch ?? true,
      enableMemorySearch: config?.enableMemorySearch ?? true,
      provider: config?.provider,
    };
  }

  setMemory(memory: IMemory): void {
    this.memory = memory;
  }

  setProvider(provider: IProvider): void {
    this.provider = provider;
    this.config.provider = provider;
  }

  setDigestStore(store: SessionDigestStore): void {
    this.digestStore = store;
  }

  /**
   * Initialize search context for a new turn
   */
  initTurn(sessionId: string, turnId: string, userMessage: string): void {
    if (!this.config.enabled) return;

    const existing = this.sessionContexts.get(sessionId);
    
    this.sessionContexts.set(sessionId, {
      sessionId,
      turnId,
      userMessage,
      assistantResponse: '',
      tokens: [],
      entities: existing?.entities ?? [], // Carry over entities from previous turns
      topics: existing?.topics ?? [],
      retrievedContext: existing?.retrievedContext ?? [],
    });

    this.logger.debug('Search context initialized', { sessionId, turnId });
  }

  /**
   * Stream tokens into the search context
   * Triggers analysis when enough tokens accumulate
   */
  async streamToken(sessionId: string, token: string): Promise<void> {
    if (!this.config.enabled) return;

    const context = this.sessionContexts.get(sessionId);
    if (!context) return;

    context.tokens.push(token);
    context.assistantResponse += token;

    // Analyze when we have enough tokens and cooldown has passed
    const now = Date.now();
    const lastSearch = this.lastSearchTime.get(sessionId) ?? 0;
    
    if (context.tokens.length >= this.config.maxTokensToAnalyze && 
        now - lastSearch > this.config.searchCooldownMs) {
      
      // Debounce: don't start a new search if one is pending
      if (!this.pendingSearches.has(sessionId)) {
        const searchPromise = this.analyzeAndSearch(sessionId);
        this.pendingSearches.set(sessionId, searchPromise);
        
        try {
          await searchPromise;
        } finally {
          this.pendingSearches.delete(sessionId);
          this.lastSearchTime.set(sessionId, Date.now());
        }
      }
    }
  }

  /**
   * Extract entities and generate search queries from conversation
   */
  private async analyzeAndSearch(sessionId: string): Promise<void> {
    const context = this.sessionContexts.get(sessionId);
    if (!context) return;

    try {
      // 1. Extract entities using simple heuristics (fast)
      const extraction = this.extractEntitiesHeuristic(context);
      
      // Merge with existing entities/topics
      context.entities = [...new Set([...context.entities, ...extraction.entities])];
      context.topics = [...new Set([...context.topics, ...extraction.topics])];

      this.logger.debug('Entities extracted', { 
        sessionId, 
        entities: extraction.entities,
        topics: extraction.topics,
        gaps: extraction.gaps,
      });

      // 2. If we have an LLM provider, refine with semantic extraction
      if (this.provider && extraction.gaps.length > 0) {
        const refined = await this.extractEntitiesWithLLM(context);
        if (refined) {
          context.entities = [...new Set([...context.entities, ...refined.entities])];
          context.topics = [...new Set([...context.topics, ...refined.topics])];
        }
      }

      // 3. Search for each gap/missing information
      for (const gap of extraction.gaps) {
        await this.searchForGap(sessionId, gap, context);
      }

      // 4. Search for high-priority entities
      for (const entity of context.entities.slice(-5)) { // Last 5 entities
        await this.searchForEntity(sessionId, entity, context);
      }

    } catch (err) {
      this.logger.warn('Analysis and search failed', { sessionId, error: String(err) });
    }
  }

  /**
   * Fast heuristic-based entity extraction
   */
  private extractEntitiesHeuristic(context: SearchContext): EntityExtraction {
    const text = (context.userMessage + ' ' + context.assistantResponse).toLowerCase();
    const entities: string[] = [];
    const topics: string[] = [];
    const gaps: string[] = [];

    // Code/file entities
    const fileMatches = text.match(/[\w\-./]+\.(ts|js|tsx|jsx|py|rs|go|java|cpp|c|h|json|yaml|yml|md|sql)/gi);
    if (fileMatches) entities.push(...fileMatches);

    // Function/method names (patterns like "function foo()" or "foo()")
    const functionMatches = text.match(/(?:function|def|fn|method)\s+(\w+)|\b(\w+)\s*\([^)]*\)/gi);
    if (functionMatches) {
      entities.push(...functionMatches.map(m => m.replace(/\s*\(.*$/, '').replace(/^(function|def|fn|method)\s+/, '')));
    }

    // Class/component names (PascalCase)
    const classMatches = text.match(/\b[A-Z][a-zA-Z0-9]*(?:Component|Service|Controller|Manager|Handler|Model|Class)\b/g);
    if (classMatches) entities.push(...classMatches);

    // Technology topics
    const techPatterns = [
      { topic: 'database', patterns: ['database', 'db', 'sql', 'postgres', 'mysql', 'mongo', 'redis'] },
      { topic: 'api', patterns: ['api', 'endpoint', 'rest', 'graphql', 'http'] },
      { topic: 'authentication', patterns: ['auth', 'login', 'password', 'token', 'jwt', 'oauth'] },
      { topic: 'performance', patterns: ['performance', 'optimize', 'speed', 'latency', 'cache'] },
      { topic: 'testing', patterns: ['test', 'testing', 'jest', 'vitest', 'cypress'] },
      { topic: 'deployment', patterns: ['deploy', 'docker', 'kubernetes', 'k8s', 'ci/cd'] },
      { topic: 'architecture', patterns: ['architecture', 'microservices', 'monolith', 'pattern'] },
    ];

    for (const { topic, patterns } of techPatterns) {
      if (patterns.some(p => text.includes(p))) {
        topics.push(topic);
      }
    }

    // Detect information gaps
    if (text.includes('what is') || text.includes('what does') || text.includes('how does')) {
      gaps.push('definition');
    }
    if (text.includes('where') || text.includes('find') || text.includes('locate')) {
      gaps.push('location');
    }
    if (text.includes('error') || text.includes('bug') || text.includes('fix')) {
      gaps.push('error_resolution');
    }
    if (text.includes('how to') || text.includes('implement')) {
      gaps.push('implementation');
    }

    return { entities, topics, intent: '', gaps };
  }

  /**
   * LLM-based entity extraction for better semantic understanding
   */
  private async extractEntitiesWithLLM(context: SearchContext): Promise<EntityExtraction | null> {
    if (!this.provider) return null;

    const prompt = `Analyze this conversation and extract key information:

User: ${context.userMessage}
Assistant: ${context.assistantResponse.slice(0, 500)}

Extract as JSON:
{
  "entities": ["specific names: files, functions, classes, people, projects"],
  "topics": ["general subjects like authentication, performance, etc"],
  "intent": "what the user is trying to accomplish",
  "gaps": ["what information seems missing or unclear"]
}

Be concise. Only include high-confidence items.`;

    try {
      const stream = await (this.provider as any).complete(
        [{ role: 'user', content: prompt }],
        { model: 'gpt-5-mini', stream: false, maxTokens: 200 }
      );

      let response = '';
      for await (const chunk of stream) {
        if (chunk.type === 'token') response += chunk.text;
      }

      // Extract JSON from response
      const jsonMatch = response.match(/\{[\s\S]*\}/);
      if (jsonMatch) {
        return JSON.parse(jsonMatch[0]);
      }
    } catch (err) {
      this.logger.debug('LLM entity extraction failed', { error: String(err) });
    }

    return null;
  }

  /**
   * Search for information to fill a detected gap
   */
  private async searchForGap(sessionId: string, gap: string, context: SearchContext): Promise<void> {
    const query = this.buildGapQuery(gap, context);
    await this.executeSearch(sessionId, query, 'gap', gap);
  }

  /**
   * Search for information about a specific entity
   */
  private async searchForEntity(sessionId: string, entity: string, context: SearchContext): Promise<void> {
    const queries = this.buildEntityQueries(entity, context);
    
    for (const query of queries) {
      await this.executeSearch(sessionId, query, 'entity', entity);
    }
  }

  /**
   * Build search query for a gap type
   */
  private buildGapQuery(gap: string, context: SearchContext): string {
    const entityStr = context.entities.join(' ');
    
    switch (gap) {
      case 'definition':
        return `what is ${entityStr}`;
      case 'location':
        return `where is ${entityStr} located file path`;
      case 'error_resolution':
        return `${entityStr} error fix solution`;
      case 'implementation':
        return `how to implement ${entityStr} example`;
      default:
        return `${entityStr} ${context.topics.join(' ')}`;
    }
  }

  /**
   * Build multiple search queries for an entity
   */
  private buildEntityQueries(entity: string, context: SearchContext): string[] {
    const queries: string[] = [];
    
    // Definition query
    queries.push(`what is ${entity}`);
    
    // Usage query
    queries.push(`${entity} usage example`);
    
    // Implementation query (if it looks like code)
    if (entity.includes('.') || entity.includes('_') || /[A-Z]/.test(entity)) {
      queries.push(`${entity} implementation code`);
    }
    
    // Context-specific query
    if (context.topics.length > 0) {
      queries.push(`${entity} ${context.topics[0]}`);
    }

    return queries;
  }

  /**
   * Execute a search across all enabled sources
   */
  private async executeSearch(
    sessionId: string, 
    query: string, 
    searchType: 'gap' | 'entity',
    target: string
  ): Promise<void> {
    const context = this.sessionContexts.get(sessionId);
    if (!context) return;

    // Check if we already searched for this recently
    const cacheKey = `${sessionId}:${query}`;
    if (this.globalRetrievedCache.has(cacheKey)) {
      this.logger.debug('Search result cached', { query });
      return;
    }

    this.logger.info('Executing search', { sessionId, query, type: searchType, target });

    // Search memory
    if (this.config.enableMemorySearch && this.memory) {
      try {
        const results = await this.memory.search(query, { limit: 3 });
        
        for (const result of results) {
          const item: RetrievedItem = {
            id: `mem_${Date.now()}_${Math.random().toString(36).slice(2, 8)}`,
            source: 'memory',
            content: result.entry.content,
            relevance: result.score,
            query,
            retrievedAt: Date.now(),
            used: false,
          };
          
          context.retrievedContext.push(item);
          this.globalRetrievedCache.set(cacheKey, item);
          
          this.logger.debug('Memory result retrieved', { 
            query, 
            relevance: result.score,
            contentPreview: item.content.slice(0, 100),
          });
        }
      } catch (err) {
        this.logger.debug('Memory search failed', { query, error: String(err) });
      }
    }

    // TODO: File search (would need file system access)
    // TODO: Web search (would need search API)

    // Cross-session search
    if (this.digestStore) {
      try {
        const siblingResults = this.digestStore.searchSiblings(sessionId, query, 3);
        for (const { digest, score } of siblingResults) {
          // Normalise score to 0-1 range (scores typically 1-10)
          const relevance = Math.min(score / 10, 1);
          const summary = [
            `[Cross-session: "${digest.topic}"]`,
            digest.currentTask ? `Current task: ${digest.currentTask}` : '',
            digest.filesActive.length > 0 ? `Files: ${digest.filesActive.slice(-3).join(', ')}` : '',
            digest.decisions.length > 0  ? `Decisions: ${digest.decisions.slice(-2).join('; ')}` : '',
            digest.learnings.length > 0  ? `Learnings: ${digest.learnings.slice(-2).join('; ')}` : '',
          ].filter(Boolean).join('\n');

          const item: RetrievedItem = {
            id:          `xs_${digest.sessionId.slice(-6)}_${Date.now()}`,
            source:      'cross-session',
            content:     summary,
            relevance,
            query,
            retrievedAt: Date.now(),
            used:        false,
          };
          context.retrievedContext.push(item);
          this.logger.debug('Cross-session result retrieved', {
            query,
            sessionId: digest.sessionId.slice(-8),
            topic: digest.topic,
            relevance,
          });
        }
      } catch (err) {
        this.logger.debug('Cross-session search failed', { query, error: String(err) });
      }
    }

    // Trim cache if needed
    if (context.retrievedContext.length > this.config.maxRetrievedCache) {
      context.retrievedContext = context.retrievedContext
        .sort((a, b) => b.relevance - a.relevance)
        .slice(0, this.config.maxRetrievedCache);
    }
  }

  /**
   * Get the most relevant context to inject into the conversation
   */
  getContextToInject(sessionId: string): RetrievedItem[] {
    const context = this.sessionContexts.get(sessionId);
    if (!context) return [];

    // Get unused items above relevance threshold
    const injectable = context.retrievedContext
      .filter(item => !item.used && item.relevance >= this.config.minRelevanceToInject)
      .sort((a, b) => b.relevance - a.relevance)
      .slice(0, this.config.maxContextToInject);

    // Mark as used
    for (const item of injectable) {
      item.used = true;
    }

    return injectable;
  }

  /**
   * Get search summary for a session
   */
  getSearchSummary(sessionId: string): {
    entities: string[];
    topics: string[];
    retrievedCount: number;
    injectedCount: number;
  } | null {
    const context = this.sessionContexts.get(sessionId);
    if (!context) return null;

    return {
      entities: context.entities,
      topics: context.topics,
      retrievedCount: context.retrievedContext.length,
      injectedCount: context.retrievedContext.filter(i => i.used).length,
    };
  }

  /**
   * Clean up session data
   */
  cleanupSession(sessionId: string): void {
    this.sessionContexts.delete(sessionId);
    this.lastSearchTime.delete(sessionId);
    this.pendingSearches.delete(sessionId);
  }

  /**
   * Get stats for monitoring
   */
  getStats(): {
    activeSessions: number;
    cachedItems: number;
    totalRetrieved: number;
    totalInjected: number;
  } {
    let totalRetrieved = 0;
    let totalInjected = 0;

    for (const context of this.sessionContexts.values()) {
      totalRetrieved += context.retrievedContext.length;
      totalInjected += context.retrievedContext.filter(i => i.used).length;
    }

    return {
      activeSessions: this.sessionContexts.size,
      cachedItems: this.globalRetrievedCache.size,
      totalRetrieved,
      totalInjected,
    };
  }
}
