/**
 * CassiCore Admin API Client
 * 
 * Communicates with CassiCore daemon via Unix socket
 * Provides typed access to all Admin API endpoints
 */

export interface HealthStatus {
  status: 'ok' | 'degraded' | 'error';
  timestamp: string;
  uptimeMs: number;
  memoryMb: number;
  eventLoopLagMs: number;
  version: string;
  checks: HealthCheck[];
}

export interface HealthCheck {
  name: string;
  status: 'ok' | 'warning' | 'error';
  message: string;
  durationMs: number;
  meta?: Record<string, unknown>;
}

export interface Session {
  id: string;
  agentId: string;
  channelId: string;
  status: 'active' | 'inactive' | 'error';
  createdAt: string;
  lastActivityAt: string;
  messageCount: number;
  metadata?: Record<string, unknown>;
}

export interface SessionConfig {
  agentId?: string;
  channelId?: string;
  systemPrompt?: string;
  model?: string;
  thinking?: 'off' | 'low' | 'medium' | 'high';
  tools?: string[];
  metadata?: Record<string, unknown>;
}

export interface Message {
  role: 'user' | 'assistant' | 'system' | 'tool';
  content: string;
  id?: string;
  timestamp?: string;
  toolCalls?: ToolCall[];
  toolResults?: ToolResult[];
}

export interface ToolCall {
  id: string;
  name: string;
  arguments: Record<string, unknown>;
}

export interface ToolResult {
  callId: string;
  result: unknown;
  error?: string;
}

export interface DialecticState {
  sessionId: string;
  yang: string;
  yin: string;
  synthesis: string;
  status: 'observing' | 'synthesizing' | 'complete';
  turn: number;
}

export interface DialecticUpdate {
  type: 'yang' | 'yin' | 'synthesis' | 'status';
  content: string;
  turn: number;
  timestamp: string;
}

export interface MemoryResult {
  id: string;
  content: string;
  source: string;
  relevance: number;
  timestamp: string;
}

export interface SearchOptions {
  limit?: number;
  threshold?: number;
  includeMetadata?: boolean;
}

export interface Subagent {
  id: string;
  parentSessionId?: string;
  label: string;
  status: 'running' | 'completed' | 'failed' | 'killed';
  task: string;
  result?: string;
  error?: string;
  startedAt: string;
  completedAt?: string;
}

export interface SubagentConfig {
  label?: string;
  model?: string;
  thinking?: 'off' | 'low' | 'medium' | 'high';
  timeout?: number;
  tools?: string[];
}

export interface Provider {
  id: string;
  name: string;
  status: 'healthy' | 'degraded' | 'unavailable';
  models: string[];
  defaultModel: string;
}

export class CassiCoreAdminClient {
  private socketPath: string;
  private baseUrl: string;

  constructor(socketPath: string = '~/.cassicore/admin.sock') {
    this.socketPath = socketPath.replace(/^~/, process.env.HOME || '');
    this.baseUrl = 'http://localhost';
  }

  /**
   * Make request to Admin API via Unix socket
   */
  private async request<T>(
    path: string,
    options: RequestInit = {}
  ): Promise<T> {
    const url = `${this.baseUrl}${path}`;
    
    // Use node-fetch with custom agent for Unix socket
    const fetch = await this.getFetch();
    
    const response = await fetch(url, {
      ...options,
      headers: {
        'Content-Type': 'application/json',
        ...options.headers,
      },
    });

    if (!response.ok) {
      const error = await response.text();
      throw new Error(`Admin API error: ${response.status} ${error}`);
    }

    return response.json() as Promise<T>;
  }

  /**
   * Get fetch implementation with Unix socket support
   */
  private async getFetch(): Promise<typeof fetch> {
    // Dynamic import to handle both Node and browser environments
    if (typeof globalThis.fetch !== 'undefined') {
      // Browser or Node 18+
      return globalThis.fetch;
    }
    
    // Node <18, use node-fetch with unix-socket-agent
    const { default: fetch } = await import('node-fetch');
    const { default: UnixSocketAgent } = await import('unix-socket-agent');
    
    return (url: string, init?: RequestInit) => {
      return fetch(url, {
        ...init,
        agent: new UnixSocketAgent(this.socketPath),
      });
    };
  }

  // ==================== Health & Status ====================

  async getHealth(): Promise<HealthStatus> {
    return this.request<HealthStatus>('/health');
  }

  async getStatus(): Promise<{
    status: string;
    uptime: number;
    version: string;
    sessions: number;
    plugins: { total: number; healthy: number };
    providers: string[];
  }> {
    return this.request('/status');
  }

  // ==================== Session Management ====================

  async listSessions(): Promise<Session[]> {
    const response = await this.request<{ sessions: Session[] }>('/sessions');
    return response.sessions;
  }

  async getSession(id: string): Promise<Session> {
    return this.request<Session>(`/sessions/${id}`);
  }

  async createSession(config: SessionConfig = {}): Promise<Session> {
    return this.request<Session>('/sessions', {
      method: 'POST',
      body: JSON.stringify(config),
    });
  }

  async deleteSession(id: string): Promise<void> {
    await this.request(`/sessions/${id}`, { method: 'DELETE' });
  }

  async sendMessage(sessionId: string, message: Message): Promise<void> {
    await this.request(`/sessions/${sessionId}/messages`, {
      method: 'POST',
      body: JSON.stringify(message),
    });
  }

  async getMessages(sessionId: string, limit = 50): Promise<Message[]> {
    const response = await this.request<{ messages: Message[] }>(
      `/sessions/${sessionId}/messages?limit=${limit}`
    );
    return response.messages;
  }

  // ==================== Dialectic ====================

  async getDialecticState(sessionId: string): Promise<DialecticState> {
    return this.request<DialecticState>(`/sessions/${sessionId}/dialectic`);
  }

  async *streamDialectic(sessionId: string): AsyncGenerator<DialecticUpdate> {
    const response = await this.request<Response>(
      `/sessions/${sessionId}/dialectic/stream`,
      { method: 'GET' }
    );

    const reader = response.body?.getReader();
    if (!reader) throw new Error('No response body');

    const decoder = new TextDecoder();
    let buffer = '';

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;

      buffer += decoder.decode(value, { stream: true });
      const lines = buffer.split('\n');
      buffer = lines.pop() || '';

      for (const line of lines) {
        if (line.startsWith('data: ')) {
          try {
            const update = JSON.parse(line.slice(6)) as DialecticUpdate;
            yield update;
          } catch (e) {
            // Skip invalid JSON
          }
        }
      }
    }
  }

  // ==================== Memory ====================

  async searchMemory(
    query: string,
    options: SearchOptions = {}
  ): Promise<MemoryResult[]> {
    const params = new URLSearchParams({ q: query });
    if (options.limit) params.set('limit', String(options.limit));
    if (options.threshold) params.set('threshold', String(options.threshold));

    const response = await this.request<{ results: MemoryResult[] }>(
      `/memory/search?${params}`
    );
    return response.results;
  }

  async recallContext(sessionId: string): Promise<{
    memories: MemoryResult[];
    recentMessages: Message[];
  }> {
    return this.request(`/sessions/${sessionId}/context`);
  }

  // ==================== Subagents ====================

  async listSubagents(parentSessionId?: string): Promise<Subagent[]> {
    const url = parentSessionId
      ? `/subagents?parent=${parentSessionId}`
      : '/subagents';
    const response = await this.request<{ subagents: Subagent[] }>(url);
    return response.subagents;
  }

  async spawnSubagent(
    task: string,
    parentSessionId?: string,
    config: SubagentConfig = {}
  ): Promise<Subagent> {
    return this.request<Subagent>('/subagents', {
      method: 'POST',
      body: JSON.stringify({
        task,
        parentSessionId,
        ...config,
      }),
    });
  }

  async killSubagent(id: string): Promise<void> {
    await this.request(`/subagents/${id}`, { method: 'DELETE' });
  }

  async getSubagent(id: string): Promise<Subagent> {
    return this.request<Subagent>(`/subagents/${id}`);
  }

  // ==================== Providers ====================

  async listProviders(): Promise<Provider[]> {
    const response = await this.request<{ providers: Provider[] }>('/providers');
    return response.providers;
  }

  async switchProvider(
    sessionId: string,
    providerId: string,
    model?: string
  ): Promise<void> {
    await this.request(`/sessions/${sessionId}/provider`, {
      method: 'PUT',
      body: JSON.stringify({ providerId, model }),
    });
  }

  // ==================== Configuration ====================

  async getConfig(): Promise<Record<string, unknown>> {
    return this.request('/config');
  }

  async reloadConfig(): Promise<void> {
    await this.request('/config/reload', { method: 'POST' });
  }

  async updateConfig(updates: Record<string, unknown>): Promise<void> {
    await this.request('/config', {
      method: 'PATCH',
      body: JSON.stringify(updates),
    });
  }
}

// Singleton instance
let defaultClient: CassiCoreAdminClient | null = null;

export function getAdminClient(): CassiCoreAdminClient {
  if (!defaultClient) {
    defaultClient = new CassiCoreAdminClient();
  }
  return defaultClient;
}

export function setAdminClient(client: CassiCoreAdminClient): void {
  defaultClient = client;
}
