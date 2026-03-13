/**
 * CassiCore Event API
 *
 * HTTP endpoints for:
 * - POST /events/ingest - Receive events from CLI
 * - GET /events/stream - SSE stream for event consumers
 * - GET /events/history - Query event history
 * - GET /state - Get current session state snapshot
 */

import type { CassiCoreEvent } from './event-types.js';
import type { EventBus } from '../event-bus.js';
import type { IncomingMessage, ServerResponse } from 'node:http';
import { DEFAULT_RESOURCE_LIMITS } from '../config/resource-limits.js';

// ============================================================================
// Types
// ============================================================================

export interface IngestRequest {
  sessionId: string;
  events: CassiCoreEvent[];
}

export interface IngestResponse {
  ingested: number;
  errors?: string[];
}

export interface HistoryRequest {
  sessionId: string;
  since?: number;
  limit?: number;
  eventTypes?: string[];
}

export interface HistoryResponse {
  events: any[];
  total: number;
  hasMore: boolean;
}

export interface StateSnapshotRequest {
  sessionId: string;
}

export interface StateSnapshot {
  sessionId: string;
  connected: boolean;
  lastEventTimestamp: number;
  
  // Conversation state
  turnIndex: number;
  isStreaming: boolean;
  messageCount: number;
  
  // Configuration
  model?: string;
  thinkingLevel?: 'off' | 'minimal' | 'low' | 'medium' | 'high' | 'xhigh';
  activeTools: string[];
  
  // Runtime state
  activeToolCalls: Array<{
    toolCallId: string;
    toolName: string;
    startTime: number;
  }>;
  
  // Context
  contextUsage?: {
    tokens: number;
    contextWindow: number;
    percent: number;
  };
  
  // Metadata
  sessionStartTime?: number;
  totalTokensUsed: number;
}

// ============================================================================
// SSE Connection Management with Resource Limits
// ============================================================================

interface SSEConnection {
  id: string;
  sessionId: string;
  response: ServerResponse;
  lastEventId: string | null;
  connectedAt: number;
  lastWriteAt: number;
  writePending: boolean;
}

interface SSEConnectionManagerConfig {
  maxConnectionsPerSession: number;
  maxTotalConnections: number;
  connectionTTLms: number;
  cleanupIntervalMs: number;
  backpressureTimeoutMs: number;
}

export class SSEConnectionManager {
  private connections = new Map<string, SSEConnection>();
  private connectionId = 0;
  private config: SSEConnectionManagerConfig;
  private cleanupTimer?: NodeJS.Timeout;
  private disposed = false;

  constructor(
    private eventBus: EventBus,
    config?: Partial<SSEConnectionManagerConfig>
  ) {
    this.config = {
      maxConnectionsPerSession: DEFAULT_RESOURCE_LIMITS.sse.maxConnectionsPerSession,
      maxTotalConnections: DEFAULT_RESOURCE_LIMITS.sse.maxTotalConnections,
      connectionTTLms: DEFAULT_RESOURCE_LIMITS.sse.connectionTTLms,
      cleanupIntervalMs: DEFAULT_RESOURCE_LIMITS.sse.cleanupIntervalMs,
      backpressureTimeoutMs: DEFAULT_RESOURCE_LIMITS.sse.backpressureTimeoutMs,
      ...config,
    };

    // Subscribe to all events and forward to relevant connections
    this.eventBus.onAll((event: any) => {
      if (event.sessionId) {
        this.broadcastToSession(event.sessionId, event);
      }
    });

    // Start periodic cleanup
    this.startCleanupTimer();
  }

  private startCleanupTimer(): void {
    this.cleanupTimer = setInterval(() => {
      this.cleanupStaleConnections();
    }, this.config.cleanupIntervalMs);

    // Don't prevent process exit
    if (this.cleanupTimer.unref) {
      this.cleanupTimer.unref();
    }
  }

  private cleanupStaleConnections(): void {
    const now = Date.now();
    const toDelete: string[] = [];

    for (const [id, conn] of this.connections) {
      const age = now - conn.connectedAt;
      const sinceLastWrite = now - conn.lastWriteAt;

      // Remove if TTL exceeded
      if (age > this.config.connectionTTLms) {
        toDelete.push(id);
        continue;
      }

      // Remove if backpressure timeout exceeded
      if (conn.writePending && sinceLastWrite > this.config.backpressureTimeoutMs) {
        toDelete.push(id);
        continue;
      }

      // Check socket buffer for backpressure
      const socket = (conn.response as any).socket;
      if (socket && socket.bufferSize > 65536) { // 64KB buffer threshold
        if (sinceLastWrite > this.config.backpressureTimeoutMs) {
          toDelete.push(id);
        }
      }
    }

    for (const id of toDelete) {
      const conn = this.connections.get(id);
      if (conn) {
        try {
          conn.response.end();
        } catch {}
        this.connections.delete(id);
      }
    }

    if (toDelete.length > 0) {
      // Could add logging here if logger was available
    }
  }

  /**
   * Create a new SSE connection
   */
  createConnection(
    sessionId: string,
    response: ServerResponse,
    lastEventId: string | null = null
  ): string | null {
    // Check total connection limit
    if (this.connections.size >= this.config.maxTotalConnections) {
      return null;
    }

    // Check per-session limit
    const sessionCount = this.getConnectionCount(sessionId);
    if (sessionCount >= this.config.maxConnectionsPerSession) {
      return null;
    }

    const id = `conn_${++this.connectionId}`;
    
    // Setup SSE headers
    response.writeHead(200, {
      'Content-Type': 'text/event-stream',
      'Cache-Control': 'no-cache',
      'Connection': 'keep-alive',
      'X-Accel-Buffering': 'no',
    });

    const connection: SSEConnection = {
      id,
      sessionId,
      response,
      lastEventId,
      connectedAt: Date.now(),
      lastWriteAt: Date.now(),
      writePending: false,
    };

    this.connections.set(id, connection);

    // Send initial connection event
    this.sendEvent(connection, {
      type: 'sse_connected',
      sessionId,
      timestamp: Date.now(),
      eventId: `evt_${Date.now()}`,
    } as unknown as CassiCoreEvent);

    // Handle disconnect
    response.on('close', () => {
      this.connections.delete(id);
    });

    return id;
  }

  /**
   * Send event to a specific connection
   */
  sendEvent(connection: SSEConnection, event: CassiCoreEvent): boolean {
    const data = JSON.stringify(event);
    const message = [
      `id: ${event.eventId}`,
      `event: ${event.type}`,
      `data: ${data}`,
      '',
    ].join('\n');

    try {
      // Check for backpressure
      const socket = (connection.response as any).socket;
      if (socket && socket.bufferSize > 65536) {
        // Socket buffer is full, mark as pending
        connection.writePending = true;
        return false;
      }

      const written = connection.response.write(`${message}\n`);
      connection.lastWriteAt = Date.now();
      connection.writePending = !written;
      connection.lastEventId = event.eventId;
      return written;
    } catch (err) {
      // Connection likely closed
      this.connections.delete(connection.id);
      return false;
    }
  }

  /**
   * Broadcast event to all connections for a session
   */
  broadcastToSession(sessionId: string, event: CassiCoreEvent): void {
    for (const conn of this.connections.values()) {
      if (conn.sessionId === sessionId) {
        this.sendEvent(conn, event);
      }
    }
  }

  /**
   * Get connection count for a session
   */
  getConnectionCount(sessionId: string): number {
    let count = 0;
    for (const conn of this.connections.values()) {
      if (conn.sessionId === sessionId) count++;
    }
    return count;
  }

  /**
   * Close all connections for a session
   */
  closeSessionConnections(sessionId: string): void {
    for (const [id, conn] of this.connections) {
      if (conn.sessionId === sessionId) {
        try {
          conn.response.end();
        } catch {}
        this.connections.delete(id);
      }
    }
  }

  /**
   * Get total connection count
   */
  getTotalConnections(): number {
    return this.connections.size;
  }

  /**
   * Get connection stats
   */
  getStats(): {
    total: number;
    bySession: Record<string, number>;
    oldestConnectionAge: number;
  } {
    const bySession: Record<string, number> = {};
    let oldestAge = 0;
    const now = Date.now();

    for (const conn of this.connections.values()) {
      bySession[conn.sessionId] = (bySession[conn.sessionId] || 0) + 1;
      const age = now - conn.connectedAt;
      if (age > oldestAge) oldestAge = age;
    }

    return {
      total: this.connections.size,
      bySession,
      oldestConnectionAge: oldestAge,
    };
  }

  /**
   * Dispose of the connection manager (cleanup timer, all connections)
   */
  dispose(): void {
    this.disposed = true;

    if (this.cleanupTimer) {
      clearInterval(this.cleanupTimer);
      this.cleanupTimer = undefined;
    }

    // Close all connections
    for (const conn of this.connections.values()) {
      try {
        conn.response.end();
      } catch {}
    }
    this.connections.clear();
  }

  /**
   * Check if manager is disposed
   */
  isDisposed(): boolean {
    return this.disposed;
  }
}

// ============================================================================
// HTTP Handlers
// ============================================================================

export class EventAPI {
  private sseManager: SSEConnectionManager;

  constructor(
    private eventBus: EventBus,
    config?: Partial<SSEConnectionManagerConfig>
  ) {
    this.sseManager = new SSEConnectionManager(eventBus, config);
  }


  /**
   * Validate event structure to prevent malicious event types
   */
  private validateEvent(event: any): { valid: boolean; error?: string } {
    // Must be an object
    if (!event || typeof event !== 'object' || Array.isArray(event)) {
      return { valid: false, error: 'Event must be an object' };
    }

    // Type is required and must be a string
    if (!event.type || typeof event.type !== 'string') {
      return { valid: false, error: 'Event type is required and must be a string' };
    }

    // Type must match allowed pattern (alphanumeric, underscore, hyphen)
    if (!/^[a-zA-Z][a-zA-Z0-9_-]*$/.test(event.type)) {
      return { valid: false, error: `Invalid event type format: ${event.type}` };
    }

    // Block dangerous event types
    const blockedTypes = ['system', 'admin', 'config', 'auth', 'permission', 'security'];
    if (blockedTypes.some(t => event.type.toLowerCase().startsWith(t))) {
      return { valid: false, error: `Event type '${event.type}' is not allowed` };
    }

    // SessionId if provided must be a string
    if (event.sessionId !== undefined && typeof event.sessionId !== 'string') {
      return { valid: false, error: 'SessionId must be a string' };
    }

    // Timestamp if provided must be a number
    if (event.timestamp !== undefined && typeof event.timestamp !== 'number') {
      return { valid: false, error: 'Timestamp must be a number' };
    }

    return { valid: true };
  }


  /**
   * POST /events/ingest
   * Receive events from CLI
   */
  async handleIngest(req: IncomingMessage, res: ServerResponse): Promise<void> {
    try {
      const body = await this.readBody(req);
      const request: IngestRequest = JSON.parse(body);

      if (!request.sessionId || !Array.isArray(request.events)) {
        res.writeHead(400, { 'Content-Type': 'application/json' });
        res.end(JSON.stringify({ error: 'Invalid request: sessionId and events array required' }));
        return;
      }

      const errors: string[] = [];
      let ingested = 0;

      for (const event of request.events) {
        try {
          // Validate event structure
          const validation = this.validateEvent(event);
          if (!validation.valid) {
            errors.push(`Invalid event structure: ${validation.error}`);
            continue;
          }

          // Ensure required fields
          if (!event.eventId) {
            event.eventId = `evt_${Date.now()}_${Math.random().toString(36).slice(2)}`;
          }
          if (!event.timestamp) {
            event.timestamp = Date.now();
          }
          if (!event.sessionId) {
            event.sessionId = request.sessionId;
          }

          this.eventBus.emit(event as any);
          ingested++;
        } catch (err) {
          errors.push(`Failed to ingest event: ${err}`);
        }
      }

      const response: IngestResponse = { ingested };
      if (errors.length > 0) {
        response.errors = errors;
      }

      res.writeHead(200, { 'Content-Type': 'application/json' });
      res.end(JSON.stringify(response));
    } catch (err) {
      res.writeHead(500, { 'Content-Type': 'application/json' });
      res.end(JSON.stringify({ error: `Ingest failed: ${err}` }));
    }
  }

  /**
   * GET /events/stream?sessionId=xxx&lastEventId=xxx
   * SSE endpoint for streaming events
   */
  handleStream(req: IncomingMessage, res: ServerResponse, query: URLSearchParams): void {
    const sessionId = query.get('sessionId');
    if (!sessionId) {
      res.writeHead(400, { 'Content-Type': 'application/json' });
      res.end(JSON.stringify({ error: 'sessionId query parameter required' }));
      return;
    }

    // Check connection limits before proceeding
    const sessionCount = this.sseManager.getConnectionCount(sessionId);
    if (sessionCount >= DEFAULT_RESOURCE_LIMITS.sse.maxConnectionsPerSession) {
      res.writeHead(503, { 
        'Content-Type': 'application/json',
        'Retry-After': '60'
      });
      res.end(JSON.stringify({ 
        error: 'Too many SSE connections for this session',
        maxConnections: DEFAULT_RESOURCE_LIMITS.sse.maxConnectionsPerSession,
        retryAfter: 60
      }));
      return;
    }

    const totalConnections = this.sseManager.getTotalConnections();
    if (totalConnections >= DEFAULT_RESOURCE_LIMITS.sse.maxTotalConnections) {
      res.writeHead(503, { 
        'Content-Type': 'application/json',
        'Retry-After': '60'
      });
      res.end(JSON.stringify({ 
        error: 'Too many total SSE connections',
        maxConnections: DEFAULT_RESOURCE_LIMITS.sse.maxTotalConnections,
        retryAfter: 60
      }));
      return;
    }

    const lastEventId = query.get('lastEventId');
    
    // Send any missed events first if lastEventId provided
    if (lastEventId) {
      // Parse timestamp from eventId format: evt_{timestamp}_{random}
      const match = lastEventId.match(/evt_(\d+)_/);
      if (match) {
        const since = parseInt(match[1], 10);
        const missedEvents = this.eventBus.getEventsSince(sessionId, since);
        
        // Setup headers first
        res.writeHead(200, {
          'Content-Type': 'text/event-stream',
          'Cache-Control': 'no-cache',
          'Connection': 'keep-alive',
          'X-Accel-Buffering': 'no',
        });

        // Send missed events
        for (const event of missedEvents) {
          const data = JSON.stringify(event);
          res.write(`${[
            `id: ${(event as any).eventId}`,
            `event: ${event.type}`,
            `data: ${data}`,
            '',
          ].join('\n')}\n`);
        }
      }
    }

    // Create persistent connection
    const connectionId = this.sseManager.createConnection(sessionId, res, lastEventId);
    if (!connectionId) {
      res.writeHead(503, { 
        'Content-Type': 'application/json',
        'Retry-After': '60'
      });
      res.end(JSON.stringify({ 
        error: 'Connection limit exceeded',
        retryAfter: 60
      }));
      return;
    }
  }

  /**
   * GET /events/history?sessionId=xxx&since=xxx&limit=xxx
   * Query event history
   */
  handleHistory(req: IncomingMessage, res: ServerResponse, query: URLSearchParams): void {
    const sessionId = query.get('sessionId');
    if (!sessionId) {
      res.writeHead(400, { 'Content-Type': 'application/json' });
      res.end(JSON.stringify({ error: 'sessionId query parameter required' }));
      return;
    }

    const since = query.get('since') ? parseInt(query.get('since')!, 10) : 0;
    const limit = query.get('limit') ? parseInt(query.get('limit')!, 10) : 100;
    const eventTypes = query.get('eventTypes')?.split(',') || [];

    let events = this.eventBus.getEventsSince(sessionId, since);
    
    // Filter by event types if specified
    if (eventTypes.length > 0) {
      events = events.filter(e => eventTypes.includes(e.type));
    }

    // Apply limit
    const total = events.length;
    const hasMore = total > limit;
    events = events.slice(0, limit);

    const response: HistoryResponse = {
      events,
      total,
      hasMore,
    };

    res.writeHead(200, { 'Content-Type': 'application/json' });
    res.end(JSON.stringify(response));
  }

  /**
   * GET /state?sessionId=xxx
   * Get current session state snapshot
   */
  handleState(req: IncomingMessage, res: ServerResponse, query: URLSearchParams): void {
    const sessionId = query.get('sessionId');
    if (!sessionId) {
      res.writeHead(400, { 'Content-Type': 'application/json' });
      res.end(JSON.stringify({ error: 'sessionId query parameter required' }));
      return;
    }

    // Build state snapshot from event history
    const events = this.eventBus.getAllEvents(sessionId);
    const snapshot = this.buildStateSnapshot(sessionId, events);

    res.writeHead(200, { 'Content-Type': 'application/json' });
    res.end(JSON.stringify(snapshot));
  }

  /**
   * Build state snapshot from event history
   */
  private buildStateSnapshot(sessionId: string, events: any[]): StateSnapshot {
    const snapshot: StateSnapshot = {
      sessionId,
      connected: true,
      lastEventTimestamp: 0,
      turnIndex: 0,
      isStreaming: false,
      messageCount: 0,
      activeTools: [],
      activeToolCalls: [],
      totalTokensUsed: 0,
    };

    const activeToolCalls = new Map<string, { toolCallId: string; toolName: string; startTime: number }>();

    for (const event of events) {
      snapshot.lastEventTimestamp = Math.max(snapshot.lastEventTimestamp, event.timestamp);

      switch (event.type) {
        case 'session_start':
          snapshot.sessionStartTime = event.timestamp;
          break;
        case 'agent_start':
          snapshot.turnIndex = event.turnIndex || 0;
          snapshot.model = event.model;
          break;
        case 'streaming_start':
          snapshot.isStreaming = true;
          break;
        case 'streaming_end':
          snapshot.isStreaming = false;
          break;
        case 'user_message':
        case 'assistant_message':
          snapshot.messageCount++;
          break;
        case 'assistant_message':
          snapshot.totalTokensUsed += (event as any).inputTokens + (event as any).outputTokens;
          break;
        case 'tool_execution_start':
          activeToolCalls.set(event.toolCallId, {
            toolCallId: event.toolCallId,
            toolName: event.toolName,
            startTime: event.timestamp,
          });
          break;
        case 'tool_execution_end':
          activeToolCalls.delete(event.toolCallId);
          break;
        case 'model_select':
          snapshot.model = (event as any).model;
          break;
        case 'context_usage':
          snapshot.contextUsage = {
            tokens: (event as any).tokens,
            contextWindow: (event as any).contextWindow,
            percent: (event as any).percent,
          };
          break;
      }
    }

    snapshot.activeToolCalls = Array.from(activeToolCalls.values());

    return snapshot;
  }

  /**
  /**
   * Read request body with size limit and Content-Type validation
   */
  private readBody(req: IncomingMessage, maxSize: number = 1024 * 1024): Promise<string> {
    return new Promise((resolve, reject) => {
      // Validate Content-Type for POST requests
      const contentType = req.headers['content-type'];
      if (contentType && !contentType.toLowerCase().startsWith('application/json')) {
        reject(new Error('Unsupported Media Type - application/json required'));
        return;
      }

      let body = '';
      let totalSize = 0;

      req.on('data', chunk => {
        totalSize += chunk.length;
        if (totalSize > maxSize) {
          req.destroy();
          reject(new Error(`Request body exceeds ${maxSize} byte limit`));
          return;
        }
        body += chunk;
      });
      req.on('end', () => resolve(body));
      req.on('error', reject);
    });
  }

  /**
   * Get SSE connection stats
   */
  getConnectionStats(): { total: number; bySession: Record<string, number>; oldestConnectionAge: number } {
    return this.sseManager.getStats();
  }

  /**
   * Dispose of the EventAPI (cleanup resources)
   */
  dispose(): void {
    this.sseManager.dispose();
  }
}
