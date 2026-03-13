/**
 * Context Window Debugging System
 *
 * Captures and streams the actual context windows being sent to models.
 * Useful for debugging what the model actually sees vs what we think it sees.
 */

import type { EventBus } from '../event-bus.js';

export interface ContextWindowSnapshot {
  type: 'context_window_snapshot';
  sessionId: string;
  timestamp: number;
  eventId: string;
  turnIndex: number;
  model: string;
  
  // Content
  messages: Array<{
    role: 'system' | 'user' | 'assistant' | 'tool';
    content: string;
    name?: string;
    tool_calls?: any[];
  }>;
  
  // Metrics
  messageCount: number;
  totalChars: number;
  estimatedTokens: number;
  contextWindow: number;
  percentUsed: number;
  
  // Debug info
  systemPromptLength: number;
  historyMessageCount: number;
  userMessageLength: number;
  
  // Optional: content hashes for comparison
  contentHash: string;
}

export interface ContextWindowDiff {
  type: 'context_window_diff';
  sessionId: string;
  timestamp: number;
  eventId: string;
  previousHash: string;
  currentHash: string;
  additions: string[];
  removals: string[];
}

export class ContextWindowDebugger {
  private eventBus: EventBus;
  private enabled: boolean;
  private captureSystemPrompt: boolean;
  private captureFullContent: boolean;
  private maxSnapshotsPerSession: number;
  private sessionSnapshots = new Map<string, ContextWindowSnapshot[]>();
  private lastHash = new Map<string, string>();

  constructor(
    eventBus: EventBus,
    options: {
      enabled?: boolean;
      captureSystemPrompt?: boolean;
      captureFullContent?: boolean;
      maxSnapshotsPerSession?: number;
    } = {}
  ) {
    this.eventBus = eventBus;
    this.enabled = options.enabled ?? true;
    this.captureSystemPrompt = options.captureSystemPrompt ?? false; // Privacy
    this.captureFullContent = options.captureFullContent ?? true;
    this.maxSnapshotsPerSession = options.maxSnapshotsPerSession ?? 100;
  }

  /**
   * Capture a snapshot of the context window being sent to the model
   */
  captureSnapshot(
    sessionId: string,
    turnIndex: number,
    model: string,
    messages: any[],
    contextWindow: number
  ): ContextWindowSnapshot {
    if (!this.enabled) {
      return null as any;
    }

    const timestamp = Date.now();
    const eventId = `ctx_${timestamp}_${Math.random().toString(36).slice(2, 8)}`;

    // Calculate metrics
    const processedMessages = messages.map(m => this.processMessage(m));
    const totalChars = processedMessages.reduce((sum, m) => sum + (m.content?.length || 0), 0);
    const estimatedTokens = Math.ceil(totalChars / 4); // Rough estimate
    const percentUsed = (estimatedTokens / contextWindow) * 100;

    // Find system prompt
    const systemMsg = processedMessages.find(m => m.role === 'system');
    const systemPromptLength = systemMsg?.content?.length || 0;

    // Count history (non-system, non-last-user)
    const historyMessageCount = processedMessages.filter(
      m => m.role !== 'system' && m.role !== 'tool'
    ).length - 1; // Exclude current user message

    // Find user message (last user message)
    const userMessages = processedMessages.filter(m => m.role === 'user');
    const lastUserMessage = userMessages[userMessages.length - 1];
    const userMessageLength = lastUserMessage?.content?.length || 0;

    // Generate content hash
    const contentHash = this.hashContent(processedMessages);

    const snapshot: ContextWindowSnapshot = {
      type: 'context_window_snapshot',
      sessionId,
      timestamp,
      eventId,
      turnIndex,
      model,
      messages: this.captureFullContent ? processedMessages : this.summarizeMessages(processedMessages),
      messageCount: processedMessages.length,
      totalChars,
      estimatedTokens,
      contextWindow,
      percentUsed,
      systemPromptLength,
      historyMessageCount,
      userMessageLength,
      contentHash,
    };

    // Store in session history
    this.storeSnapshot(sessionId, snapshot);

    // Emit event
    this.eventBus.emit(snapshot as any);

    // Calculate and emit diff if we have a previous snapshot
    const prevHash = this.lastHash.get(sessionId);
    if (prevHash && prevHash !== contentHash) {
      const diff = this.calculateDiff(sessionId, prevHash, contentHash, processedMessages);
      if (diff) {
        this.eventBus.emit(diff as any);
      }
    }
    this.lastHash.set(sessionId, contentHash);

    return snapshot;
  }

  /**
   * Get all snapshots for a session
   */
  getSnapshots(sessionId: string): ContextWindowSnapshot[] {
    return this.sessionSnapshots.get(sessionId) || [];
  }

  /**
   * Get the most recent snapshot for a session
   */
  getLatestSnapshot(sessionId: string): ContextWindowSnapshot | undefined {
    const snapshots = this.sessionSnapshots.get(sessionId);
    return snapshots?.[snapshots.length - 1];
  }

  /**
   * Get snapshots since a timestamp
   */
  getSnapshotsSince(sessionId: string, since: number): ContextWindowSnapshot[] {
    const snapshots = this.sessionSnapshots.get(sessionId) || [];
    return snapshots.filter(s => s.timestamp >= since);
  }

  /**
   * Clear snapshots for a session
   */
  clearSession(sessionId: string): void {
    this.sessionSnapshots.delete(sessionId);
    this.lastHash.delete(sessionId);
  }

  /**
   * Enable/disable debugging
   */
  setEnabled(enabled: boolean): void {
    this.enabled = enabled;
  }

  /**
   * Get statistics for a session
   */
  getStats(sessionId: string): {
    snapshotCount: number;
    totalMessages: number;
    avgContextSize: number;
    maxContextSize: number;
    lastSnapshot: number;
  } {
    const snapshots = this.sessionSnapshots.get(sessionId) || [];
    if (snapshots.length === 0) {
      return {
        snapshotCount: 0,
        totalMessages: 0,
        avgContextSize: 0,
        maxContextSize: 0,
        lastSnapshot: 0,
      };
    }

    const sizes = snapshots.map(s => s.estimatedTokens);
    return {
      snapshotCount: snapshots.length,
      totalMessages: snapshots.reduce((sum, s) => sum + s.messageCount, 0),
      avgContextSize: Math.round(sizes.reduce((a, b) => a + b, 0) / sizes.length),
      maxContextSize: Math.max(...sizes),
      lastSnapshot: snapshots[snapshots.length - 1]?.timestamp || 0,
    };
  }

  private processMessage(msg: any): any {
    const processed: any = {
      role: msg.role,
    };

    // Handle content
    if (typeof msg.content === 'string') {
      processed.content = msg.content;
    } else if (Array.isArray(msg.content)) {
      // Content blocks (images, etc)
      processed.content = msg.content.map((block: any) => {
        if (block.type === 'text') return block.text;
        if (block.type === 'image') return '[IMAGE]';
        return '[CONTENT]';
      }).join('');
    } else {
      processed.content = String(msg.content || '');
    }

    // Truncate very long content for privacy/performance
    if (processed.content.length > 10000) {
      processed.content = `${processed.content.slice(0, 10000)  }\n... [truncated]`;
      processed.wasTruncated = true;
    }

    // Handle tool calls
    if (msg.tool_calls) {
      processed.tool_calls = msg.tool_calls.map((tc: any) => ({
        id: tc.id,
        type: tc.type,
        function: {
          name: tc.function?.name,
          arguments: tc.function?.arguments?.slice(0, 500), // Truncate args
        },
      }));
    }

    // Handle tool results
    if (msg.role === 'tool') {
      processed.name = msg.name;
      processed.tool_call_id = msg.tool_call_id;
    }

    return processed;
  }

  private summarizeMessages(messages: any[]): any[] {
    // Return truncated version without full content
    return messages.map(m => ({
      role: m.role,
      contentLength: m.content?.length || 0,
      preview: m.content?.slice(0, 200) + (m.content?.length > 200 ? '...' : ''),
      hasToolCalls: !!m.tool_calls,
    }));
  }

  private hashContent(messages: any[]): string {
    // Simple hash of message roles and content lengths
    const hashStr = messages
      .map(m => `${m.role}:${m.content?.length || 0}`)
      .join('|');
    return Buffer.from(hashStr).toString('base64').slice(0, 16);
  }

  private storeSnapshot(sessionId: string, snapshot: ContextWindowSnapshot): void {
    let snapshots = this.sessionSnapshots.get(sessionId);
    if (!snapshots) {
      snapshots = [];
      this.sessionSnapshots.set(sessionId, snapshots);
    }

    snapshots.push(snapshot);

    // Limit storage
    if (snapshots.length > this.maxSnapshotsPerSession) {
      snapshots.shift();
    }
  }

  private calculateDiff(
    sessionId: string,
    previousHash: string,
    currentHash: string,
    currentMessages: any[]
  ): ContextWindowDiff | null {
    // Simple diff: find new messages since last snapshot
    // In a real implementation, we'd compare message-by-message
    const lastSnapshot = this.getLatestSnapshot(sessionId);
    if (!lastSnapshot) return null;

    const previousCount = lastSnapshot.messageCount;
    const currentCount = currentMessages.length;

    if (currentCount <= previousCount) return null;

    const newMessages = currentMessages.slice(previousCount);

    return {
      type: 'context_window_diff',
      sessionId,
      timestamp: Date.now(),
      eventId: `diff_${Date.now()}`,
      previousHash,
      currentHash,
      additions: newMessages.map(m => `[${m.role}]: ${m.content?.slice(0, 100)}...`),
      removals: [],
    };
  }
}

// Singleton instance
let globalDebugger: ContextWindowDebugger | null = null;

export function initContextWindowDebugger(eventBus: EventBus): ContextWindowDebugger {
  if (!globalDebugger) {
    globalDebugger = new ContextWindowDebugger(eventBus);
  }
  return globalDebugger;
}

export function getContextWindowDebugger(): ContextWindowDebugger | null {
  return globalDebugger;
}

export function resetContextWindowDebugger(): void {
  globalDebugger = null;
}
