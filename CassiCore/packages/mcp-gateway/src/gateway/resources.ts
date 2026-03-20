#!/usr/bin/env node
/**
 * MCP Resources Module
 * 
 * Implements standardized MCP resources with caching, proper response formats,
 * and backward-compatible URI schemas.
 * 
 * Resources:
 * - cassicore://team/{teamId} - Live team state (also supports cassicore://teams/{id})
 * - cassicore://session/{sessionId}/context - Context window snapshot
 * - cassicore://config - Current configuration (safe keys only)
 * - cassicore://health - Enhanced health with provider status
 * - cassicore://intelligence/activity - Cognitive state dashboard
 */

import type { ILogger } from '../../types/interfaces.js';
import { fetchWithTimeout, GATEWAY_VERSION } from './helpers.js';

// Types

/**
 * Standard metadata for all resource responses
 */
interface ResourceMetadata {
  timestamp: string;
  ttl: number; // Time-to-live in seconds
  version: string;
}

/**
 * Standard response structure embedded in MCP text field
 */
interface ResourceResponse<T> {
  data: T;
  metadata: ResourceMetadata;
}

/**
 * Cache entry with expiration
 */
interface CacheEntry<T> {
  data: T;
  expiresAt: number; // Timestamp when entry expires
  etag: string; // SHA256 hash for conditional requests
}

/**
 * Team state response
 */
interface TeamState {
  id: string;
  goal: string;
  status: 'running' | 'paused' | 'completed' | 'failed';
  cells: Array<{
    id: string;
    role: string;
    status: string;
    goal: string;
  }>;
  budget: {
    maxTokens: number;
    usedTokens: number;
    maxIterations: number;
    usedIterations: number;
    timeoutMs: number;
    elapsedMs: number;
  };
  progress: {
    completed: number;
    total: number;
    percentage: number;
  };
  checkpoints: Array<{
    id: string;
    status: 'pending' | 'approved' | 'rejected';
    description: string;
  }>;
}

/**
 * Session context response
 */
interface SessionContext {
  sessionId: string;
  messages: Array<{
    role: string;
    content: string;
    timestamp: string;
  }>;
  tokenUsage: {
    total: number;
    remaining: number;
    limit: number;
  };
  turnCount: number;
  createdAt: string;
  lastActiveAt: string;
  metadata: {
    channel: string;
    sender: string;
    provider: string;
    model: string;
  };
}

/**
 * Config response (safe keys only)
 */
interface ConfigResponse {
  intelligence: {
    thinker: { enabled: boolean; ponderIntervalMs: number };
    dialectic: { enabled: boolean; autoInject: boolean };
    subconscious: { enabled: boolean };
  };
  providers: Record<string, { model: string; enabled: boolean }>;
  logging: { level: string };
  channels: Record<string, { enabled: boolean }>;
}

/**
 * Enhanced health response
 */
interface HealthResponse {
  status: 'healthy' | 'degraded' | 'unhealthy';
  uptime: number;
  memory: { heapMb: number; lagMs: number };
  providers: Array<{
    id: string;
    status: 'healthy' | 'degraded' | 'unhealthy';
    message?: string;
  }>;
  plugins: {
    total: number;
    healthy: number;
    crashed: string[];
  };
  checks: Array<{
    name: string;
    status: 'ok' | 'degraded' | 'down';
    message: string;
  }>;
}

/**
 * Intelligence activity response
 */
interface IntelligenceActivity {
  thinker: {
    insightsGenerated: number;
    lastInsightAt: string | null;
    pondering: boolean;
  };
  dialectic: {
    sessionsActive: number;
    totalSessions: number;
    lastSessionAt: string | null;
  };
  subconscious: {
    anomaliesDetected: number;
    lastAnomalyAt: string | null;
    patterns: string[];
  };
  recentActivity: Array<{
    type: 'insight' | 'anomaly' | 'pattern' | 'reflection';
    timestamp: string;
    summary: string;
  }>;
}

// Caching Configuration

/**
 * TTL configuration per resource type (in seconds)
 */
const TTL_CONFIG: Record<string, number> = {
  'team': 2,           // Team state changes frequently
  'session': 5,        // Session context updates moderately
  'config': 30,        // Config is relatively stable
  'health': 5,         // Health needs frequent updates
  'intelligence': 10,  // Intelligence activity is moderate
};

/**
 * LRU Cache for resource responses
 */
class ResourceCache {
  private cache = new Map<string, CacheEntry<any>>();
  private maxSize: number;

  constructor(maxSize: number = 100) {
    this.maxSize = maxSize;
  }

  /**
   * Get cached entry if valid
   */
  get<T>(key: string): T | null {
    const entry = this.cache.get(key);
    if (!entry) return null;

    // Check if expired
    if (Date.now() > entry.expiresAt) {
      this.cache.delete(key);
      return null;
    }

    return entry.data;
  }

  /**
   * Set cache entry with TTL
   */
  set<T>(key: string, data: T, ttlSeconds: number): void {
    // Evict oldest if at capacity
    if (this.cache.size >= this.maxSize) {
      const firstKey = this.cache.keys().next().value;
      if (firstKey) this.cache.delete(firstKey);
    }

    const etag = this.computeEtag(JSON.stringify(data));
    this.cache.set(key, {
      data,
      expiresAt: Date.now() + (ttlSeconds * 1000),
      etag,
    });
  }

  /**
   * Invalidate cache entries matching a pattern
   */
  invalidate(pattern: RegExp): void {
    const keysToDelete: string[] = [];
    this.cache.forEach((_, key) => {
      if (pattern.test(key)) {
        keysToDelete.push(key);
      }
    });
    keysToDelete.forEach(key => this.cache.delete(key));
  }

  /**
   * Get ETag for conditional requests
   */
  getEtag(key: string): string | null {
    const entry = this.cache.get(key);
    return entry?.etag || null;
  }

  /**
   * Compute SHA256 hash for ETag
   */
  private computeEtag(content: string): string {
    // Simple hash - in production would use crypto.createHash('sha256')
    let hash = 0;
    for (let i = 0; i < content.length; i++) {
      const char = content.charCodeAt(i);
      hash = ((hash << 5) - hash) + char;
      hash = hash & hash; // Convert to 32-bit integer
    }
    return hash.toString(16);
  }
}

// Global cache instance
const resourceCache = new ResourceCache(100);

// Resource Fetchers

/**
 * Fetch team state with caching
 * @dep callers: readResource (mcp/gateway/resources.ts)
 * @dep calls: get, fetchWithTimeout, toISOString
 * @dep flows: ReadResource → Now (2/4)
 * @dep module: Gateway
 * @dep risk: LOW | 1 caller, 1 flow, 1 module
 */
async function fetchTeamState(
  cassicoreUrl: string,
  teamId: string,
  logger: ILogger
): Promise<ResourceResponse<TeamState>> {
  const cacheKey = `team:${teamId}:state`;
  const cached = resourceCache.get<ResourceResponse<TeamState>>(cacheKey);
  if (cached) {
    logger.debug('Cache hit for team state', { teamId });
    return cached;
  }

  logger.info('Fetching team state', { teamId });
  
  // Fetch team status
  const statusResponse = await fetchWithTimeout(`${cassicoreUrl}/teams/status?teamId=${teamId}`);
  const statusData = await statusResponse.json();

  // Fetch team tree for cell hierarchy
  let treeData: any = {};
  try {
    const treeResponse = await fetchWithTimeout(`${cassicoreUrl}/teams/tree?teamId=${teamId}`);
    treeData = await treeResponse.json();
  } catch (error) {
    logger.warn('Failed to fetch team tree', { teamId, error: String(error) });
  }

  const data: TeamState = {
    id: teamId,
    goal: statusData.goal || 'Unknown',
    status: statusData.status || 'running',
    cells: treeData.cells || statusData.cells || [],
    budget: {
      maxTokens: statusData.budget?.maxTokens || 0,
      usedTokens: statusData.budget?.usedTokens || 0,
      maxIterations: statusData.budget?.maxIterations || 0,
      usedIterations: statusData.budget?.usedIterations || 0,
      timeoutMs: statusData.budget?.timeoutMs || 0,
      elapsedMs: statusData.budget?.elapsedMs || 0,
    },
    progress: {
      completed: statusData.progress?.completed || 0,
      total: statusData.progress?.total || 0,
      percentage: statusData.progress?.percentage || 0,
    },
    checkpoints: statusData.checkpoints || [],
  };

  const response: ResourceResponse<TeamState> = {
    data,
    metadata: {
      timestamp: new Date().toISOString(),
      ttl: TTL_CONFIG['team'],
      version: GATEWAY_VERSION,
    },
  };

  // Cache the response
  resourceCache.set(cacheKey, response, TTL_CONFIG['team']);

  return response;
}

/**
 * Fetch session context with caching
 */
async function fetchSessionContext(
  cassicoreUrl: string,
  sessionId: string,
  logger: ILogger
): Promise<ResourceResponse<SessionContext>> {
  const cacheKey = `session:${sessionId}:context`;
  const cached = resourceCache.get<ResourceResponse<SessionContext>>(cacheKey);
  if (cached) {
    logger.debug('Cache hit for session context', { sessionId });
    return cached;
  }

  logger.info('Fetching session context', { sessionId });

  const response = await fetchWithTimeout(`${cassicoreUrl}/sessions/${sessionId}/context`);
  const data = await response.json();

  const resourceResponse: ResourceResponse<SessionContext> = {
    data: {
      sessionId,
      messages: data.messages || [],
      tokenUsage: {
        total: data.tokenUsage?.total || 0,
        remaining: data.tokenUsage?.remaining || 0,
        limit: data.tokenUsage?.limit || 10000,
      },
      turnCount: data.turnCount || 0,
      createdAt: data.createdAt || new Date().toISOString(),
      lastActiveAt: data.lastActiveAt || new Date().toISOString(),
      metadata: {
        channel: data.metadata?.channel || 'cli',
        sender: data.metadata?.sender || 'unknown',
        provider: data.metadata?.provider || 'unknown',
        model: data.metadata?.model || 'unknown',
      },
    },
    metadata: {
      timestamp: new Date().toISOString(),
      ttl: TTL_CONFIG['session'],
      version: GATEWAY_VERSION,
    },
  };

  resourceCache.set(cacheKey, resourceResponse, TTL_CONFIG['session']);

  return resourceResponse;
}

/**
 * Fetch config with caching
 */
async function fetchConfig(
  cassicoreUrl: string,
  logger: ILogger
): Promise<ResourceResponse<ConfigResponse>> {
  const cacheKey = 'config:snapshot';
  const cached = resourceCache.get<ResourceResponse<ConfigResponse>>(cacheKey);
  if (cached) {
    logger.debug('Cache hit for config');
    return cached;
  }

  logger.info('Fetching config');

  const response = await fetchWithTimeout(`${cassicoreUrl}/config`);
  const fullConfig = await response.json();

  // Filter to safe keys only
  const data: ConfigResponse = {
    intelligence: {
      thinker: {
        enabled: fullConfig.intelligence?.thinker?.enabled ?? true,
        ponderIntervalMs: fullConfig.intelligence?.thinker?.ponderIntervalMs ?? 30000,
      },
      dialectic: {
        enabled: fullConfig.intelligence?.dialectic?.enabled ?? true,
        autoInject: fullConfig.intelligence?.dialectic?.autoInject ?? true,
      },
      subconscious: {
        enabled: fullConfig.intelligence?.subconscious?.enabled ?? true,
      },
    },
    providers: {},
    logging: {
      level: fullConfig.logging?.level ?? 'info',
    },
    channels: {},
  };

  // Extract provider info
  if (fullConfig.providers) {
    for (const [id, provider] of Object.entries(fullConfig.providers)) {
      const p = provider as any;
      data.providers[id] = {
        model: p.model || 'unknown',
        enabled: p.enabled ?? true,
      };
    }
  }

  // Extract channel info
  if (fullConfig.channels) {
    for (const [id, channel] of Object.entries(fullConfig.channels)) {
      const c = channel as any;
      data.channels[id] = {
        enabled: c.enabled ?? true,
      };
    }
  }

  const resourceResponse: ResourceResponse<ConfigResponse> = {
    data,
    metadata: {
      timestamp: new Date().toISOString(),
      ttl: TTL_CONFIG['config'],
      version: GATEWAY_VERSION,
    },
  };

  resourceCache.set(cacheKey, resourceResponse, TTL_CONFIG['config']);

  return resourceResponse;
}

/**
 * Fetch enhanced health with caching
 * @dep callers: statusCommand (src/cli/commands/boot.ts), readResource (mcp/gateway/resources.ts)
 * @dep calls: get, fetchWithTimeout, toISOString
 * @dep module: Gateway
 * @dep risk: LOW | 2 callers, 0 flows, 1 module
 */
async function fetchHealth(
  cassicoreUrl: string,
  logger: ILogger
): Promise<ResourceResponse<HealthResponse>> {
  const cacheKey = 'health:snapshot';
  const cached = resourceCache.get<ResourceResponse<HealthResponse>>(cacheKey);
  if (cached) {
    logger.debug('Cache hit for health');
    return cached;
  }

  logger.info('Fetching health status');

  const response = await fetchWithTimeout(`${cassicoreUrl}/health`);
  const healthData = await response.json();

  // Build enhanced health response
  const data: HealthResponse = {
    status: healthData.status || 'healthy',
    uptime: healthData.uptime || 0,
    memory: {
      heapMb: healthData.memory?.heapMb || 0,
      lagMs: healthData.memory?.lagMs || 0,
    },
    providers: [],
    plugins: {
      total: healthData.plugins?.total || 0,
      healthy: healthData.plugins?.healthy || 0,
      crashed: healthData.plugins?.crashed || [],
    },
    checks: healthData.checks || [],
  };

  // Add provider status from health data
  // WHY: HealthMonitor only checks provider presence, not latency
  if (healthData.providers) {
    const providersMeta = healthData.checks?.find((c: any) => c.name === 'providers')?.meta;
    if (providersMeta) {
      const providerIds = providersMeta.providers || [];
      const missingIds = providersMeta.missing || [];
      
      for (const id of providerIds) {
        data.providers.push({
          id,
          status: missingIds.includes(id) ? 'degraded' : 'healthy',
          message: missingIds.includes(id) ? 'Provider missing required API' : undefined,
        });
      }
    }
  }

  const resourceResponse: ResourceResponse<HealthResponse> = {
    data,
    metadata: {
      timestamp: new Date().toISOString(),
      ttl: TTL_CONFIG['health'],
      version: GATEWAY_VERSION,
    },
  };

  resourceCache.set(cacheKey, resourceResponse, TTL_CONFIG['health']);

  return resourceResponse;
}

/**
 * Fetch intelligence activity with caching
 */
async function fetchIntelligenceActivity(
  cassicoreUrl: string,
  logger: ILogger
): Promise<ResourceResponse<IntelligenceActivity>> {
  const cacheKey = 'intelligence:activity';
  const cached = resourceCache.get<ResourceResponse<IntelligenceActivity>>(cacheKey);
  if (cached) {
    logger.debug('Cache hit for intelligence activity');
    return cached;
  }

  logger.info('Fetching intelligence activity');

  const response = await fetchWithTimeout(`${cassicoreUrl}/intelligence/activity`);
  const activityData = await response.json();

  const data: IntelligenceActivity = {
    thinker: {
      insightsGenerated: activityData.thinker?.insightsGenerated || 0,
      lastInsightAt: activityData.thinker?.lastInsightAt || null,
      pondering: activityData.thinker?.pondering ?? false,
    },
    dialectic: {
      sessionsActive: activityData.dialectic?.sessionsActive || 0,
      totalSessions: activityData.dialectic?.totalSessions || 0,
      lastSessionAt: activityData.dialectic?.lastSessionAt || null,
    },
    subconscious: {
      anomaliesDetected: activityData.subconscious?.anomaliesDetected || 0,
      lastAnomalyAt: activityData.subconscious?.lastAnomalyAt || null,
      patterns: activityData.subconscious?.patterns || [],
    },
    recentActivity: activityData.recentActivity || [],
  };

  const resourceResponse: ResourceResponse<IntelligenceActivity> = {
    data,
    metadata: {
      timestamp: new Date().toISOString(),
      ttl: TTL_CONFIG['intelligence'],
      version: GATEWAY_VERSION,
    },
  };

  resourceCache.set(cacheKey, resourceResponse, TTL_CONFIG['intelligence']);

  return resourceResponse;
}

// Main Resource Handler

/**
 * Parse resource URI and extract type and parameters
 */
export function parseResourceUri(uri: string): {
  type: string;
  params: Record<string, string>;
} | null {
  // Team resources (both singular and plural for backward compatibility)
  const teamMatch = uri.match(/^cassicore:\/\/teams?\/([^/]+)$/);
  if (teamMatch) {
    return { type: 'team', params: { teamId: teamMatch[1] } };
  }

  // Session context
  const sessionContextMatch = uri.match(/^cassicore:\/\/sessions?\/([^/]+)\/context$/);
  if (sessionContextMatch) {
    return { type: 'session', params: { sessionId: sessionContextMatch[1] } };
  }

  // Session turns (not in scope but supported)
  const sessionTurnsMatch = uri.match(/^cassicore:\/\/sessions?\/([^/]+)\/turns$/);
  if (sessionTurnsMatch) {
    return { type: 'turns', params: { sessionId: sessionTurnsMatch[1] } };
  }

  // Static resources
  if (uri === 'cassicore://config') {
    return { type: 'config', params: {} };
  }
  if (uri === 'cassicore://health') {
    return { type: 'health', params: {} };
  }
  if (uri === 'cassicore://intelligence/activity') {
    return { type: 'intelligence', params: {} };
  }

  // Memory search
  const memoryMatch = uri.match(/^cassicore:\/\/memory\/(.+)$/);
  if (memoryMatch) {
    return { type: 'memory', params: { query: memoryMatch[1] } };
  }

  return null;
}

/**
 * Read a resource and return MCP-compliant response
 * @dep calls: fetchTeamState, fetchSessionContext, fetchConfig, fetchHealth, fetchIntelligenceActivity [+3]
 * @dep flows: ReadResource → Now (1/4)
 * @dep module: Gateway
 * @dep risk: LOW | 0 callers, 1 flow, 1 module
 */
export async function readResource(
  uri: string,
  cassicoreUrl: string,
  logger: ILogger
): Promise<{
  contents: Array<{
    uri: string;
    mimeType: string;
    text: string;
  }>;
}> {
  const parsed = parseResourceUri(uri);
  if (!parsed) {
    throw new Error(`Unknown resource: ${uri}`);
  }

  let response: ResourceResponse<any>;

  try {
    switch (parsed.type) {
      case 'team':
        response = await fetchTeamState(cassicoreUrl, parsed.params.teamId, logger);
        break;
      case 'session':
        response = await fetchSessionContext(cassicoreUrl, parsed.params.sessionId, logger);
        break;
      case 'config':
        response = await fetchConfig(cassicoreUrl, logger);
        break;
      case 'health':
        response = await fetchHealth(cassicoreUrl, logger);
        break;
      case 'intelligence':
        response = await fetchIntelligenceActivity(cassicoreUrl, logger);
        break;
      case 'turns':
        // Fetch session turns (simpler, no standardization needed)
        const turnsResponse = await fetchWithTimeout(
          `${cassicoreUrl}/sessions/${parsed.params.sessionId}/turns`
        );
        const turnsData = await turnsResponse.json();
        response = {
          data: turnsData,
          metadata: {
            timestamp: new Date().toISOString(),
            ttl: TTL_CONFIG['session'],
            version: GATEWAY_VERSION,
          },
        };
        break;
      case 'memory':
        // Memory search
        const memoryResponse = await fetchWithTimeout(
          `${cassicoreUrl}/memory/search?query=${encodeURIComponent(parsed.params.query)}`
        );
        const memoryData = await memoryResponse.json();
        response = {
          data: memoryData,
          metadata: {
            timestamp: new Date().toISOString(),
            ttl: 60, // Memory results are stable
            version: GATEWAY_VERSION,
          },
        };
        break;
      default:
        throw new Error(`Unsupported resource type: ${parsed.type}`);
    }

    return {
      contents: [
        {
          uri,
          mimeType: 'application/json',
          text: JSON.stringify(response, null, 2),
        },
      ],
    };
  } catch (error: any) {
    logger.error('Resource fetch failed', { uri, error: String(error) });
    
    // Return error response in standard format
    const errorResponse: ResourceResponse<any> = {
      data: { error: error.message },
      metadata: {
        timestamp: new Date().toISOString(),
        ttl: 0,
        version: GATEWAY_VERSION,
      },
    };

    return {
      contents: [
        {
          uri,
          mimeType: 'application/json',
          text: JSON.stringify(errorResponse, null, 2),
        },
      ],
    };
  }
}

/**
 * Get resource definitions for ListResourcesRequestSchema
 */
export function getStaticResources() {
  return [
    {
      uri: 'cassicore://health',
      name: 'CassiCore Health Status',
      mimeType: 'application/json',
      description: 'Current health and status of CassiCore daemon with provider status',
    },
    {
      uri: 'cassicore://config',
      name: 'CassiCore Configuration',
      mimeType: 'application/json',
      description: 'Current CassiCore configuration (safe keys only)',
    },
    {
      uri: 'cassicore://intelligence/activity',
      name: 'Intelligence Activity Log',
      mimeType: 'application/json',
      description: 'Recent intelligence and analysis activity dashboard',
    },
  ];
}

/**
 * Get resource templates for ListResourceTemplatesRequestSchema
 */
export function getResourceTemplates() {
  return [
    {
      uriTemplate: 'cassicore://team/{teamId}',
      name: 'Team State',
      mimeType: 'application/json',
      description: 'Live team state including cell hierarchy, budget, and progress (also supports cassicore://teams/{id})',
    },
    {
      uriTemplate: 'cassicore://session/{sessionId}/context',
      name: 'Session Context Window',
      mimeType: 'application/json',
      description: 'Context window snapshot for a specific session',
    },
    {
      uriTemplate: 'cassicore://session/{sessionId}/turns',
      name: 'Session Turn History',
      mimeType: 'application/json',
      description: 'Turn history for a specific session',
    },
    {
      uriTemplate: 'cassicore://memory/{query}',
      name: 'Memory Search',
      mimeType: 'application/json',
      description: 'Search CassiCore memory by query',
    },
  ];
}

/**
 * Invalidate cache entries for a specific resource type
 */
export function invalidateResourceCache(type: string, id?: string): void {
  let pattern: RegExp;
  
  switch (type) {
    case 'team':
      pattern = id ? new RegExp(`^team:${id}:`) : /^team:/;
      break;
    case 'session':
      pattern = id ? new RegExp(`^session:${id}:`) : /^session:/;
      break;
    case 'config':
      pattern = /^config:/;
      break;
    case 'health':
      pattern = /^health:/;
      break;
    case 'intelligence':
      pattern = /^intelligence:/;
      break;
    default:
      pattern = /.*/;
  }
  
  resourceCache.invalidate(pattern);
}
