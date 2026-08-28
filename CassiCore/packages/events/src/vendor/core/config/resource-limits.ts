/**
 * Resource Limit Configuration
 * 
 * Centralized configuration for DoS prevention and resource management.
 * All limits are designed to be protective without affecting normal usage.
 */

export interface ResourceLimitConfig {
  // SSE Connection Limits
  sse: {
    maxConnectionsPerSession: number;  // Max SSE connections per session
    maxTotalConnections: number;        // Global max SSE connections
    connectionTTLms: number;            // Connection time-to-live
    cleanupIntervalMs: number;          // Cleanup timer interval
    backpressureTimeoutMs: number;      // Close if stuck in backpressure
  };

  // WebSocket Connection Limits
  websocket: {
    maxConnectionsPerSession: number;  // Max WS connections per session
    maxTotalConnections: number;        // Global max WS connections
    connectionTTLms: number;            // Connection time-to-live
    cleanupIntervalMs: number;          // Cleanup timer interval
    backpressureTimeoutMs: number;      // Close if stuck in backpressure
  };

  // Delegation Tracker Limits
  delegation: {
    maxTotal: number;                   // Max total tracking entries
    maxPendingPerSession: number;       // Max pending requests per session
    expiryMs: number;                   // Entry expiry time
    cleanupIntervalMs: number;          // Cleanup timer interval
  };

  // OpenCode Conversation History Limits
  conversationHistory: {
    maxMessagesPerSession: number;      // Max messages per session
    maxSessions: number;                // Max sessions to track
    cleanupIntervalMs: number;          // Cleanup timer interval
  };

  // API Rate Limiting
  rateLimit: {
    enabled: boolean;                   // Enable/disable rate limiting
    windowMs: number;                   // Rate limit window
    defaultMaxRequests: number;         // Default max requests per window
    endpointLimits: Record<string, number>; // Per-endpoint limits
    cleanupIntervalMs: number;          // Rate limit state cleanup
  };
}

/**
 * Default resource limits - protective without affecting normal usage
 */
export const DEFAULT_RESOURCE_LIMITS: ResourceLimitConfig = {
  sse: {
    maxConnectionsPerSession: 5,
    maxTotalConnections: 100,
    connectionTTLms: 30 * 60 * 1000,    // 30 minutes
    cleanupIntervalMs: 5 * 60 * 1000,   // 5 minutes
    backpressureTimeoutMs: 30 * 1000,   // 30 seconds
  },

  websocket: {
    maxConnectionsPerSession: 3,
    maxTotalConnections: 50,
    connectionTTLms: 60 * 60 * 1000,    // 60 minutes
    cleanupIntervalMs: 5 * 60 * 1000,   // 5 minutes
    backpressureTimeoutMs: 30 * 1000,   // 30 seconds
  },

  delegation: {
    maxTotal: 100,
    maxPendingPerSession: 2,
    expiryMs: 60 * 1000,                // 1 minute
    cleanupIntervalMs: 5 * 60 * 1000,   // 5 minutes
  },

  conversationHistory: {
    maxMessagesPerSession: 200,
    maxSessions: 50,
    cleanupIntervalMs: 5 * 60 * 1000,   // 5 minutes
  },

  rateLimit: {
    enabled: true,
    windowMs: 60 * 1000,                // 1 minute window
    defaultMaxRequests: 100,            // 100 requests per minute
    endpointLimits: {
      '/events/ingest': 30,             // 30/min for ingest
      '/events/stream': 20,             // 20/min for stream
      '/dialectic': 50,                 // 50/min for dialectic
      '/context': 30,                   // 30/min for context
    },
    cleanupIntervalMs: 5 * 60 * 1000,   // 5 minutes
  },
};

/**
 * Merge user config with defaults
 */
export function createResourceLimitConfig(
  userConfig?: Partial<ResourceLimitConfig>
): ResourceLimitConfig {
  if (!userConfig) return DEFAULT_RESOURCE_LIMITS;

  const merged: ResourceLimitConfig = { ...DEFAULT_RESOURCE_LIMITS };

  // Deep merge each section
  for (const key of Object.keys(userConfig) as Array<keyof ResourceLimitConfig>) {
    if (userConfig[key]) {
      merged[key] = { ...merged[key], ...userConfig[key] } as any;
    }
  }

  return merged;
}
