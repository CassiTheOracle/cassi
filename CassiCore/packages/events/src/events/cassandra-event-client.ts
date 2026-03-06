/**
 * Cassandra Event Stream Client
 *
 * Client-side library for Cassandra to:
 * - Connect to CassiCore daemon event stream
 * - Maintain local state replica
 * - Provide reactive access to session state
 *
 * Usage:
 *   const client = new CassandraEventClient({ baseUrl: 'http://localhost:7433' });
 *   await client.connect('session-xxx');
 *
 *   // Access current state
 *   console.log(client.state.model);
 *   console.log(client.state.isStreaming);
 *
 *   // Listen for specific events
 *   client.on('tool_execution_start', (e) => {
 *     console.log(`Tool ${e.toolName} started`);
 *   });
 */

import { EventEmitter } from 'node:events';

import type {
  CassiCoreEvent,
  SessionStartEvent,
  AgentStartEvent,
  AgentEndEvent,
  TurnStartEvent,
  TurnEndEvent,
  StreamingStartEvent,
  StreamingEndEvent,
  UserMessageEvent,
  AssistantMessageEvent,
  ToolExecutionStartEvent,
  ToolExecutionEndEvent,
  ModelSelectEvent,
  ContextUsageEvent,
  CompactionStartEvent,
  CompactionEndEvent,
  ErrorEvent,
} from './event-bus.js';

// ============================================================================
// Types
// ============================================================================

export interface CassandraEventClientOptions {
  baseUrl: string;
  reconnectInterval?: number;
  maxReconnectAttempts?: number;
  debug?: boolean;
}

export interface CassandraState {
  // Session identity
  sessionId: string;
  connected: boolean;
  lastEventTimestamp: number;
  eventCount: number;

  // Conversation state
  turnIndex: number;
  isStreaming: boolean;
  currentStreamingContent: string;
  messageCount: number;

  // Configuration
  model?: string;
  thinkingLevel?: 'off' | 'minimal' | 'low' | 'medium' | 'high' | 'xhigh';
  systemPrompt?: string;
  activeTools: string[];

  // Runtime state
  activeToolCalls: Map<string, ActiveToolCall>;
  pendingToolCalls: string[];

  // Context
  contextUsage?: {
    tokens: number;
    contextWindow: number;
    percent: number;
  };

  // Metadata
  sessionStartTime?: number;
  totalTokensUsed: number;
  estimatedCost: number;
}

export interface ActiveToolCall {
  toolCallId: string;
  toolName: string;
  args: unknown;
  startTime: number;
  partialResults: unknown[];
  status: 'running' | 'completed' | 'error';
  durationMs?: number;
  result?: unknown;
  isError?: boolean;
}

export type EventType = CassiCoreEvent['type'];

export type EventHandler<T extends CassiCoreEvent> = (event: T) => void | Promise<void>;

// ============================================================================
// State Manager
// ============================================================================

class StateManager {
  state: CassandraState;
  private eventHistory: CassiCoreEvent[] = [];
  private maxHistorySize: number;

  constructor(sessionId: string, maxHistorySize = 10000) {
    this.maxHistorySize = maxHistorySize;
    this.state = {
      sessionId,
      connected: true,
      lastEventTimestamp: 0,
      eventCount: 0,
      turnIndex: 0,
      isStreaming: false,
      currentStreamingContent: '',
      messageCount: 0,
      activeTools: [],
      activeToolCalls: new Map(),
      pendingToolCalls: [],
      totalTokensUsed: 0,
      estimatedCost: 0,
    };
  }

  applyEvent(event: CassiCoreEvent): void {
    this.eventHistory.push(event);
    if (this.eventHistory.length > this.maxHistorySize) {
      this.eventHistory.shift();
    }

    this.state.lastEventTimestamp = event.timestamp;
    this.state.eventCount++;

    switch (event.type) {
      case 'session_start':
        this.handleSessionStart(event as SessionStartEvent);
        break;
      case 'session_shutdown':
        this.handleSessionShutdown(event);
        break;
      case 'agent_start':
        this.handleAgentStart(event as AgentStartEvent);
        break;
      case 'agent_end':
        this.handleAgentEnd(event as AgentEndEvent);
        break;
      case 'turn_start':
        this.handleTurnStart(event as TurnStartEvent);
        break;
      case 'turn_end':
        this.handleTurnEnd(event as TurnEndEvent);
        break;
      case 'streaming_start':
        this.handleStreamingStart(event as StreamingStartEvent);
        break;
      case 'streaming_token':
        this.handleStreamingToken(event);
        break;
      case 'streaming_end':
        this.handleStreamingEnd(event as StreamingEndEvent);
        break;
      case 'user_message':
        this.handleUserMessage(event as UserMessageEvent);
        break;
      case 'assistant_message':
        this.handleAssistantMessage(event as AssistantMessageEvent);
        break;
      case 'tool_execution_start':
        this.handleToolExecutionStart(event as ToolExecutionStartEvent);
        break;
      case 'tool_execution_update':
        this.handleToolExecutionUpdate(event);
        break;
      case 'tool_execution_end':
        this.handleToolExecutionEnd(event as ToolExecutionEndEvent);
        break;
      case 'model_select':
        this.handleModelSelect(event as ModelSelectEvent);
        break;
      case 'system_prompt_update':
        this.handleSystemPromptUpdate(event);
        break;
      case 'context_usage':
        this.handleContextUsage(event as ContextUsageEvent);
        break;
      case 'compaction_start':
        this.handleCompactionStart(event as CompactionStartEvent);
        break;
      case 'compaction_end':
        this.handleCompactionEnd(event as CompactionEndEvent);
        break;
      case 'error':
        this.handleError(event as ErrorEvent);
        break;
    }
  }

  private handleSessionStart(event: SessionStartEvent): void {
    this.state.sessionStartTime = event.timestamp;
  }

  private handleSessionShutdown(event: CassiCoreEvent): void {
    this.state.connected = false;
  }

  private handleAgentStart(event: AgentStartEvent): void {
    this.state.turnIndex = event.turnIndex;
    this.state.model = event.model;
  }

  private handleAgentEnd(event: AgentEndEvent): void {
    // Clear streaming state if stuck
    if (this.state.isStreaming) {
      this.state.isStreaming = false;
      this.state.currentStreamingContent = '';
    }
  }

  private handleTurnStart(event: TurnStartEvent): void {
    this.state.turnIndex = event.turnIndex;
  }

  private handleTurnEnd(event: TurnEndEvent): void {
    // Turn completed
  }

  private handleStreamingStart(event: StreamingStartEvent): void {
    this.state.isStreaming = true;
    this.state.currentStreamingContent = '';
  }

  private handleStreamingToken(event: CassiCoreEvent): void {
    const token = (event as any).token;
    if (token) {
      this.state.currentStreamingContent += token;
    }
  }

  private handleStreamingEnd(event: StreamingEndEvent): void {
    this.state.isStreaming = false;
    this.state.currentStreamingContent = '';
  }

  private handleUserMessage(event: UserMessageEvent): void {
    this.state.messageCount++;
  }

  private handleAssistantMessage(event: AssistantMessageEvent): void {
    this.state.messageCount++;
    this.state.totalTokensUsed += event.inputTokens + event.outputTokens;
    // Simple cost estimation (could be more sophisticated)
    this.state.estimatedCost += (event.inputTokens * 0.000003) + (event.outputTokens * 0.000015);
  }

  private handleToolExecutionStart(event: ToolExecutionStartEvent): void {
    this.state.activeToolCalls.set(event.toolCallId, {
      toolCallId: event.toolCallId,
      toolName: event.toolName,
      args: event.args,
      startTime: event.timestamp,
      partialResults: [],
      status: 'running',
    });
    this.state.pendingToolCalls.push(event.toolCallId);
  }

  private handleToolExecutionUpdate(event: CassiCoreEvent): void {
    const toolCallId = (event as any).toolCallId;
    const partialResult = (event as any).partialResult;
    const toolCall = this.state.activeToolCalls.get(toolCallId);
    if (toolCall) {
      toolCall.partialResults.push(partialResult);
    }
  }

  private handleToolExecutionEnd(event: ToolExecutionEndEvent): void {
    const toolCall = this.state.activeToolCalls.get(event.toolCallId);
    if (toolCall) {
      toolCall.status = event.isError ? 'error' : 'completed';
      toolCall.durationMs = event.durationMs;
      toolCall.result = event.result;
      toolCall.isError = event.isError;
    }
    // Remove from pending
    const idx = this.state.pendingToolCalls.indexOf(event.toolCallId);
    if (idx >= 0) {
      this.state.pendingToolCalls.splice(idx, 1);
    }
  }

  private handleModelSelect(event: ModelSelectEvent): void {
    this.state.model = event.model;
  }

  private handleSystemPromptUpdate(event: CassiCoreEvent): void {
    // Could store hash or length for tracking
  }

  private handleContextUsage(event: ContextUsageEvent): void {
    this.state.contextUsage = {
      tokens: event.tokens,
      contextWindow: event.contextWindow,
      percent: event.percent,
    };
  }

  private handleCompactionStart(event: CompactionStartEvent): void {
    // Compaction started
  }

  private handleCompactionEnd(event: CompactionEndEvent): void {
    // Compaction completed
  }

  private handleError(event: ErrorEvent): void {
    // Error occurred - this is logged via the client's error event emission
    // The console.error has been removed in favor of event-based error reporting
  }

  getEventHistory(eventTypes?: EventType[]): CassiCoreEvent[] {
    if (!eventTypes) return [...this.eventHistory];
    return this.eventHistory.filter(e => eventTypes.includes(e.type));
  }

  getRecentEvents(count: number): CassiCoreEvent[] {
    return this.eventHistory.slice(-count);
  }

  getToolCallHistory(toolName?: string): ActiveToolCall[] {
    const calls = Array.from(this.state.activeToolCalls.values());
    if (toolName) {
      return calls.filter(c => c.toolName === toolName);
    }
    return calls;
  }

  reset(): void {
    this.eventHistory = [];
    this.state.activeToolCalls.clear();
    this.state.pendingToolCalls = [];
    this.state.isStreaming = false;
    this.state.currentStreamingContent = '';
  }
}

// ============================================================================
// Event Stream Client
// ============================================================================

export class CassandraEventClient extends EventEmitter {
  private options: Required<CassandraEventClientOptions>;
  private stateManager: StateManager | null = null;
  private abortController: AbortController | null = null;
  private reconnectAttempts = 0;
  private lastEventId: string | null = null;
  private connected = false;

  constructor(options: CassandraEventClientOptions) {
    super();
    this.options = {
      baseUrl: options.baseUrl,
      reconnectInterval: options.reconnectInterval ?? 5000,
      maxReconnectAttempts: options.maxReconnectAttempts ?? 10,
      debug: options.debug ?? false,
    };
    // Prevent unhandled 'error' event from crashing the process —
    // if no external listener is attached, errors are silently absorbed.
    this.on('error', () => {});
  }

  /**
   * Connect to event stream for a session
   */
  async connect(sessionId: string): Promise<void> {
    if (this.connected) {
      throw new Error('Already connected. Disconnect first.');
    }

    this.stateManager = new StateManager(sessionId);
    this.reconnectAttempts = 0;

    await this.establishConnection(sessionId);
  }

  /**
   * Disconnect from event stream
   */
  disconnect(): void {
    this.connected = false;
    this.abortController?.abort();
    this.abortController = null;
    this.stateManager?.reset();
  }

  /**
   * Get current state
   */
  get state(): CassandraState | null {
    return this.stateManager?.state ?? null;
  }

  /**
   * Wait for a specific event type
   */
  async waitFor<T extends CassiCoreEvent>(
    eventType: T['type'],
    timeoutMs = 30000,
    predicate?: (event: T) => boolean
  ): Promise<T> {
    return new Promise((resolve, reject) => {
      const timeout = setTimeout(() => {
        this.off(eventType, handler);
        reject(new Error(`Timeout waiting for ${eventType}`));
      }, timeoutMs);

      const handler = (event: T) => {
        if (!predicate || predicate(event)) {
          clearTimeout(timeout);
          this.off(eventType, handler);
          resolve(event);
        }
      };

      this.on(eventType, handler);
    });
  }

  /**
   * Wait for streaming to complete
   */
  async waitForStreamingEnd(timeoutMs = 120000): Promise<void> {
    if (!this.state?.isStreaming) return;
    await this.waitFor('streaming_end', timeoutMs);
  }

  /**
   * Wait for all tool calls to complete
   */
  async waitForTools(timeoutMs = 60000): Promise<void> {
    if (!this.state || this.state.pendingToolCalls.length === 0) return;

    const pendingCount = this.state.pendingToolCalls.length;
    let completed = 0;

    return new Promise((resolve, reject) => {
      const timeout = setTimeout(() => {
        this.off('tool_execution_end', handler);
        reject(new Error(`Timeout waiting for tools (${completed}/${pendingCount})`));
      }, timeoutMs);

      const handler = () => {
        completed++;
        if (this.state && this.state.pendingToolCalls.length === 0) {
          clearTimeout(timeout);
          this.off('tool_execution_end', handler);
          resolve();
        }
      };

      this.on('tool_execution_end', handler);
    });
  }

  /**
   * Get event history
   */
  getEventHistory(eventTypes?: EventType[]): CassiCoreEvent[] {
    return this.stateManager?.getEventHistory(eventTypes) ?? [];
  }

  /**
   * Check if currently connected
   */
  get isConnected(): boolean {
    return this.connected;
  }

  /**
   * Get session ID
   */
  get sessionId(): string | null {
    return this.stateManager?.state.sessionId ?? null;
  }

  private async establishConnection(sessionId: string): Promise<void> {
    try {
      this.abortController = new AbortController();
      const url = new URL(`${this.options.baseUrl}/events/stream`);
      url.searchParams.set('sessionId', sessionId);
      if (this.lastEventId) {
        url.searchParams.set('lastEventId', this.lastEventId);
      }

      this.log('Connecting to event stream:', url.toString());

      const response = await fetch(url.toString(), {
        headers: {
          'Accept': 'text/event-stream',
        },
        signal: this.abortController.signal,
      });

      if (!response.ok) {
        throw new Error(`HTTP ${response.status}: ${response.statusText}`);
      }

      if (!response.body) {
        throw new Error('No response body');
      }

      this.connected = true;
      this.reconnectAttempts = 0;
      this.emit('connected', { sessionId });

      // Read SSE stream
      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let buffer = '';

      try {
        while (this.connected) {
          const { done, value } = await reader.read();
          if (done) break;

          buffer += decoder.decode(value, { stream: true });
          const lines = buffer.split('\n');
          buffer = lines.pop() ?? '';

          this.processLines(lines);
        }
      } catch (err) {
        if (this.connected) {
          this.log('Stream error:', err);
        }
      } finally {
        reader.releaseLock();
      }

      this.connected = false;
      this.emit('disconnected', { sessionId, willReconnect: this.reconnectAttempts < this.options.maxReconnectAttempts });

      // Attempt reconnect
      if (this.reconnectAttempts < this.options.maxReconnectAttempts) {
        this.reconnectAttempts++;
        this.log(`Reconnecting in ${this.options.reconnectInterval}ms (attempt ${this.reconnectAttempts})`);
        setTimeout(() => this.establishConnection(sessionId), this.options.reconnectInterval);
      }

    } catch (err) {
      this.log('Connection error:', err);
      this.emit('error', err);

      // Attempt reconnect
      if (this.reconnectAttempts < this.options.maxReconnectAttempts) {
        this.reconnectAttempts++;
        setTimeout(() => this.establishConnection(sessionId), this.options.reconnectInterval);
      }
    }
  }

  private processLines(lines: string[]): void {
    let currentEvent: Partial<CassiCoreEvent> = {};

    for (const line of lines) {
      if (line.startsWith('id: ')) {
        currentEvent.eventId = line.slice(4);
        this.lastEventId = currentEvent.eventId ?? null;
      } else if (line.startsWith('event: ')) {
        currentEvent.type = line.slice(7) as EventType;
      } else if (line.startsWith('data: ')) {
        try {
          const data = JSON.parse(line.slice(6));
          currentEvent = { ...currentEvent, ...data };
        } catch {
          // Ignore parse errors
        }
      } else if (line === '' && currentEvent.type) {
        // End of event
        const event = currentEvent as CassiCoreEvent;
        this.handleEvent(event);
        currentEvent = {};
      }
    }
  }

  private handleEvent(event: CassiCoreEvent): void {
    this.log('Event received:', event.type);
    this.stateManager?.applyEvent(event);
    this.emit(event.type, event);
    this.emit('*', event);
  }

  private log(...args: unknown[]): void {
    if (this.options.debug) {
      console.log('[CassandraEventClient]', ...args);
    }
  }
}

// ============================================================================
// Factory
// ============================================================================

export function createEventClient(options: CassandraEventClientOptions): CassandraEventClient {
  return new CassandraEventClient(options);
}
