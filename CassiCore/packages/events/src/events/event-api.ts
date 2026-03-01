/**
 * CassiCore Event API
 *
 * HTTP endpoints for:
 * - POST /events/ingest - Receive events from CLI
 * - GET /events/stream - SSE stream for event consumers
 * - GET /events/history - Query event history
 * - GET /state - Get current session state snapshot
 */

import type { IncomingMessage, ServerResponse } from 'node:http';
import type { CassiCoreEvent, CassiCoreEventBus } from './event-bus.js';

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
  events: CassiCoreEvent[];
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
// SSE Connection Management
// ============================================================================

interface SSEConnection {
  id: string;
  sessionId: string;
  response: ServerResponse;
  lastEventId: string | null;
  connectedAt: number;
}

export class SSEConnectionManager {
  private connections = new Map<string, SSEConnection>();
  private connectionId = 0;

  constructor(private eventBus: CassiCoreEventBus) {
    // Subscribe to all events and forward to relevant connections
    this.eventBus.onAll((event) => {
      this.broadcastToSession(event.sessionId, event);
    });
  }

  /**
   * Create a new SSE connection
   */
  createConnection(
    sessionId: string,
    response: ServerResponse,
    lastEventId: string | null = null
  ): string {
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
  sendEvent(connection: SSEConnection, event: CassiCoreEvent): void {
    const data = JSON.stringify(event);
    const message = [
      `id: ${event.eventId}`,
      `event: ${event.type}`,
      `data: ${data}`,
      '',
    ].join('\n');

    try {
      connection.response.write(message + '\n');
      connection.lastEventId = event.eventId;
    } catch (err) {
      // Connection likely closed
      this.connections.delete(connection.id);
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
        conn.response.end();
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
}

// ============================================================================
// HTTP Handlers
// ============================================================================

export class EventAPI {
  private sseManager: SSEConnectionManager;

  constructor(private eventBus: CassiCoreEventBus) {
    this.sseManager = new SSEConnectionManager(eventBus);
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

          this.eventBus.emit(event as CassiCoreEvent);
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
          res.write([
            `id: ${event.eventId}`,
            `event: ${event.type}`,
            `data: ${data}`,
            '',
          ].join('\n') + '\n');
        }
      }
    }

    // Create persistent connection
    this.sseManager.createConnection(sessionId, res, lastEventId);
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
  private buildStateSnapshot(sessionId: string, events: CassiCoreEvent[]): StateSnapshot {
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
          snapshot.turnIndex = event.turnIndex;
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
   * Read request body
   */
  private readBody(req: IncomingMessage): Promise<string> {
    return new Promise((resolve, reject) => {
      let body = '';
      req.on('data', chunk => body += chunk);
      req.on('end', () => resolve(body));
      req.on('error', reject);
    });
  }

  /**
   * Get SSE connection stats
   */
  getConnectionStats(): { total: number; bySession: Record<string, number> } {
    return {
      total: this.sseManager.getTotalConnections(),
      bySession: {}, // Could be implemented if needed
    };
  }
}
