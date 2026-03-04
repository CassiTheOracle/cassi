/**
 * CassiCore Observatory HTTP Client
 *
 * Browser-side fetch client for the CassiCore admin API (port 7433).
 * All requests go through the Vite proxy at /api → http://127.0.0.1:7433.
 *
 * Types re-use or extend those from admin-client.ts.
 */

// ==================== Shared types (mirrored from admin-client.ts) ====================

export interface HealthStatus {
  status: "ok" | "degraded" | "error";
  timestamp: string;
  uptimeMs: number;
  memoryMb: number;
  eventLoopLagMs: number;
  version: string;
  checks: HealthCheck[];
}

export interface HealthCheck {
  name: string;
  status: "ok" | "warning" | "error";
  message: string;
  durationMs: number;
  meta?: Record<string, unknown>;
}

export interface Session {
  id: string;
  channelId: string;
  senderId: string;
  createdAt: string;
  lastActiveAt: string;
  historyLength: number;
  tokenCount: number;
  firstMessage?: string;
  lastMessage?: string;
}

export interface Message {
  role: "user" | "assistant" | "system" | "tool";
  content: string;
  id?: string;
  timestamp?: string;
}

export interface Subagent {
  id: string;
  parentSessionId?: string;
  label: string;
  status: "running" | "completed" | "failed" | "killed";
  task: string;
  result?: string;
  error?: string;
  startedAt: string;
  completedAt?: string;
}

export interface Provider {
  id: string;
  name: string;
  status: "healthy" | "degraded" | "unavailable";
  models: string[];
  defaultModel: string;
}

// ==================== Observatory-specific types ====================

export interface ProviderMetrics {
  providerId: string;
  totalRequests: number;
  successRate: number;
  avgLatencyMs: number;
  p95LatencyMs: number;
  totalTokensUsed: number;
  errors: number;
  rateLimit?: { count: number; lastHitAt: string };
}

export interface EventHistoryEntry {
  id: string;
  type: string;
  timestamp: number;
  sessionId?: string;
  data: Record<string, unknown>;
}

export interface ContextWindowSnapshot {
  type: "context_window_snapshot";
  sessionId: string;
  timestamp: number;
  eventId: string;
  turnIndex: number;
  model: string;
  // Content
  messages: Array<{
    role: "system" | "user" | "assistant" | "tool";
    content: string;
    name?: string;
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
  contentHash: string;
}

export interface IntelligenceActivity {
  module: string;
  action: string;
  sessionId?: string;
  timestamp: number;
  detail?: string;
}

export interface IntelligenceHeartbeat {
  cycleNumber: number;
  uptimeMs: number;
  moduleStatuses: Array<{ name: string; healthy: boolean; lastActivity?: number }>;
  timestamp: string;
}

export interface TeamTree {
  teamId: string;
  coordinatorAgentId?: string;
  status: string;
  agents: Array<{
    agentId: string;
    role: string;
    parentAgentId?: string;
    status: string;
  }>;
}

export interface DaemonStatus {
  status: string;
  uptime: number;
  version: string;
  sessions: number;
  plugins: { total: number; healthy: number };
  providers: string[];
}

// ==================== Client ====================

const API_BASE = "/api";

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    headers: { "Content-Type": "application/json", ...init.headers },
    ...init,
  });
  if (!res.ok) {
    const text = await res.text().catch(() => res.statusText);
    throw new Error(`API ${res.status}: ${text}`);
  }
  return res.json() as Promise<T>;
}

// ==================== Health & Status ====================

export async function getHealth(): Promise<HealthStatus> {
  return request<HealthStatus>("/health");
}

export async function getStatus(): Promise<DaemonStatus> {
  return request<DaemonStatus>("/status");
}

export async function getProviderHealth(): Promise<Record<string, unknown>> {
  return request("/health/providers");
}

// ==================== Sessions ====================

export async function listSessions(): Promise<Session[]> {
  const r = await request<{ sessions: Session[] }>("/sessions");
  return r.sessions;
}

export async function getSession(id: string): Promise<Session> {
  return request<Session>(`/sessions/${id}`);
}

export async function deleteSession(id: string): Promise<void> {
  await request<{ ok: boolean }>(`/sessions/${id}`, { method: "DELETE" });
}

export interface PruneOptions {
  all?: boolean;
  olderThanDays?: number;
  channelId?: string;
  emptyOnly?: boolean;
}

export async function pruneSessions(opts: PruneOptions): Promise<number> {
  const r = await request<{ ok: boolean; deleted: number }>("/sessions/prune", {
    method: "POST",
    body: JSON.stringify(opts),
  });
  return r.deleted;
}

export async function getMessages(sessionId: string, limit = 50): Promise<Message[]> {
  const r = await request<{ messages: Message[] }>(
    `/sessions/${sessionId}/messages?limit=${limit}`
  );
  return r.messages;
}

// ==================== Events ====================

export async function getEventHistory(opts: {
  sessionId?: string;
  type?: string;
  limit?: number;
  since?: number;
} = {}): Promise<EventHistoryEntry[]> {
  const params = new URLSearchParams();
  if (opts.sessionId) params.set("sessionId", opts.sessionId);
  if (opts.type) params.set("type", opts.type);
  if (opts.limit) params.set("limit", String(opts.limit));
  if (opts.since) params.set("since", String(opts.since));
  const qs = params.toString();
  const r = await request<{ events: EventHistoryEntry[] }>(
    `/events/history${qs ? `?${qs}` : ""}`
  );
  return r.events ?? [];
}

// ==================== Archive ====================

/** A single entry from the Archivist (memory.db). */
export interface ArchiveEntry {
  id: string;
  /** dialectic_yang | dialectic_yin | dialectic_serenity | insight | thinking | reflection | pattern | conversation | event | summary */
  type: string;
  content: string;
  thinking: string | null;
  metadata: Record<string, unknown>;
  sessionId: string | null;
  parentId: string | null;
  source: string;
  timestamp: number;
  analysis?: {
    summary?: string;
    keyPoints?: string[];
    sentiment?: string;
    importance?: number;
    topics?: string[];
    entities?: string[];
    relatedConcepts?: string[];
    suggestedTags?: string[];
  };
}

/** A persisted subconscious observation. */
export interface SubconsciousLearning {
  id: string;
  summary: string;
  source: "heuristic" | "llm";
  patterns?: string[];
  relatedEventTypes?: string[];
  confidence?: number;
  timestamp: number;
}

/** A persisted subconscious anomaly. */
export interface SubconsciousAnomaly {
  id: string;
  description: string;
  severity: "low" | "medium" | "high";
  eventTypes?: string[];
  suggestedAction?: string;
  acknowledged: boolean;
  timestamp: number;
}

/** Fetch recent Archivist entries (insights, dialectic, patterns, etc.). */
export async function getArchivedEntries(opts: {
  limit?: number;
  sessionId?: string;
} = {}): Promise<ArchiveEntry[]> {
  const params = new URLSearchParams();
  if (opts.limit) params.set("limit", String(opts.limit));
  if (opts.sessionId) params.set("sessionId", opts.sessionId);
  const qs = params.toString();
  const r = await request<{ entries: ArchiveEntry[] }>(
    `/intelligence/archivist/recent${qs ? `?${qs}` : ""}`
  );
  return r.entries ?? [];
}

/** Fetch persisted subconscious observations. */
export async function getSubconsciousLearnings(): Promise<SubconsciousLearning[]> {
  const r = await request<{ learnings: SubconsciousLearning[] }>(
    "/intelligence/subconscious/learnings"
  );
  return r.learnings ?? [];
}

/** Fetch persisted subconscious anomalies. */
export async function getSubconsciousAnomalies(): Promise<SubconsciousAnomaly[]> {
  const r = await request<{ anomalies: SubconsciousAnomaly[] }>(
    "/intelligence/subconscious/anomalies"
  );
  return r.anomalies ?? [];
}

/** Build the EventSource URL for the runtime event stream (used by EventStreamManager). */
export function buildEventStreamUrl(sessionId?: string): string {
  const params = new URLSearchParams();
  if (sessionId) params.set("sessionId", sessionId);
  const qs = params.toString();
  return `${API_BASE}/events/stream${qs ? `?${qs}` : ""}`;
}

// ==================== Subagents ====================

export async function listSubagents(parentSessionId?: string): Promise<Subagent[]> {
  const url = parentSessionId
    ? `/subagents?parent=${encodeURIComponent(parentSessionId)}`
    : "/subagents";
  const r = await request<{ subagents: Subagent[] }>(url);
  return r.subagents ?? [];
}

// ==================== Providers ====================

/**
 * List available providers.
 *
 * Server returns: { providers: string[] } (just IDs).
 * We synthesize Provider objects with minimal info since the server
 * only provides IDs at this endpoint.
 */
export async function listProviders(): Promise<Provider[]> {
  const r = await request<{ providers: string[] | Provider[] }>("/providers");
  if (!Array.isArray(r.providers)) return [];

  return r.providers.map((p) => {
    // If already a full Provider object, return as-is
    if (typeof p === "object" && p !== null) return p as Provider;
    // String ID — synthesize minimal Provider
    return {
      id: p,
      name: p,
      status: "healthy" as const,
      models: [],
      defaultModel: "",
    };
  });
}

/**
 * Fetch per-provider metrics.
 *
 * Server returns: { global, providers: [{ id, metrics }] }
 * We flatten into ProviderMetrics[] with providerId set from the wrapper.
 */
export async function getProviderMetrics(): Promise<ProviderMetrics[]> {
  const r = await request<{
    global?: unknown;
    providers?: Array<{ id: string; metrics: Record<string, unknown> | null }>;
  }>("/providers/metrics");

  if (!Array.isArray(r.providers)) return [];

  return r.providers
    .filter((p) => p.metrics != null)
    .map((p) => {
      const m = p.metrics!;
      const totalReqs = (m.totalRequests as number) ?? 0;
      const totalErrs = (m.totalErrors as number) ?? (m.errors as number) ?? (m.errorCount as number) ?? 0;
      // Compute successRate if not provided — as a 0-1 ratio
      let successRate = (m.successRate as number) ?? 0;
      if (!m.successRate && totalReqs > 0) {
        successRate = (totalReqs - totalErrs) / totalReqs;
      }
      return {
        providerId: p.id,
        totalRequests: totalReqs,
        successRate,
        avgLatencyMs: (m.avgLatencyMs as number) ?? (m.averageLatencyMs as number) ?? 0,
        p95LatencyMs: (m.p95LatencyMs as number) ?? 0,
        totalTokensUsed: (m.totalTokensUsed as number) ?? (m.totalTokens as number) ?? 0,
        errors: totalErrs,
        rateLimit: m.rateLimit as ProviderMetrics["rateLimit"],
      };
    });
}

// ==================== Debug / Context Window ====================

export async function getContextWindow(sessionId: string): Promise<ContextWindowSnapshot> {
  const r = await request<{ snapshot: ContextWindowSnapshot }>(
    `/debug/context-window?sessionId=${encodeURIComponent(sessionId)}`
  );
  return r.snapshot;
}

export function buildContextWindowStreamUrl(sessionId: string): string {
  return `${API_BASE}/debug/context-window/stream?sessionId=${encodeURIComponent(sessionId)}`;
}

// ==================== Intelligence ====================

/**
 * Fetch intelligence activity dashboard and synthesize an activity feed.
 *
 * Server returns a consolidated dashboard object:
 *   { timestamp, modules[], thinker:{stats,strategy}, memory, archive,
 *     reflect:{unresolvedPatterns}, optimizer:{sessionHealth}, dialectic, aiScientist }
 *
 * We transform this into IntelligenceActivity[] for the UI feed.
 */
export async function getIntelligenceActivity(_limit = 50): Promise<IntelligenceActivity[]> {
  const r = await request<Record<string, unknown>>("/intelligence/activity");
  return synthesizeActivitiesFromDashboard(r);
}

/** Transform the /intelligence/activity dashboard response into a flat activity feed. */
function synthesizeActivitiesFromDashboard(dash: Record<string, unknown>): IntelligenceActivity[] {
  const now = (dash.timestamp as number) ?? Date.now();
  const activities: IntelligenceActivity[] = [];

  // Module list — each active module gets an entry
  const modules = dash.modules as Array<{ name: string; priority: number; status: string }> | undefined;
  if (Array.isArray(modules)) {
    for (const m of modules) {
      activities.push({
        module: m.name,
        action: "active",
        timestamp: now,
        detail: `priority ${m.priority}`,
      });
    }
  }

  // Thinker stats
  const thinker = dash.thinker as { stats?: Record<string, unknown>; strategy?: unknown } | undefined;
  if (thinker?.stats) {
    const ts = thinker.stats;
    const parts: string[] = [];
    if (ts.totalPonders !== undefined) parts.push(`${ts.totalPonders} ponders`);
    if (ts.totalInsights !== undefined) parts.push(`${ts.totalInsights} insights`);
    if (parts.length > 0) {
      activities.push({ module: "thinker", action: "stats", timestamp: now, detail: parts.join(", ") });
    }
  }

  // Memory stats
  if (dash.memory && typeof dash.memory === "object") {
    const mem = dash.memory as Record<string, unknown>;
    const parts: string[] = [];
    if (mem.totalStored !== undefined) parts.push(`${mem.totalStored} stored`);
    if (mem.totalRecalled !== undefined) parts.push(`${mem.totalRecalled} recalled`);
    if (parts.length > 0) {
      activities.push({ module: "memory", action: "stats", timestamp: now, detail: parts.join(", ") });
    }
  }

  // Archive stats
  if (dash.archive && typeof dash.archive === "object") {
    const arch = dash.archive as Record<string, unknown>;
    const parts: string[] = [];
    if (arch.totalEntries !== undefined) parts.push(`${arch.totalEntries} entries`);
    if (arch.totalArchived !== undefined) parts.push(`${arch.totalArchived} archived`);
    if (parts.length > 0) {
      activities.push({ module: "archivist", action: "stats", timestamp: now, detail: parts.join(", ") });
    }
  }

  // Reflect — unresolved patterns
  const reflect = dash.reflect as { unresolvedPatterns?: unknown[] } | undefined;
  if (reflect?.unresolvedPatterns && Array.isArray(reflect.unresolvedPatterns)) {
    activities.push({
      module: "reflect",
      action: "unresolved",
      timestamp: now,
      detail: `${reflect.unresolvedPatterns.length} unresolved patterns`,
    });
  }

  // Dialectic
  if (dash.dialectic && typeof dash.dialectic === "object") {
    const d = dash.dialectic as Record<string, unknown>;
    const parts: string[] = [];
    if (d.totalSyntheses !== undefined) parts.push(`${d.totalSyntheses} syntheses`);
    if (d.turnsProcessed !== undefined) parts.push(`${d.turnsProcessed} turns`);
    if (parts.length > 0) {
      activities.push({ module: "dialectic", action: "stats", timestamp: now, detail: parts.join(", ") });
    }
  }

  // Optimizer — session health
  const optimizer = dash.optimizer as { sessionHealth?: Record<string, unknown> } | undefined;
  if (optimizer?.sessionHealth) {
    const sessions = Object.keys(optimizer.sessionHealth);
    if (sessions.length > 0) {
      activities.push({
        module: "optimizer",
        action: "session-health",
        timestamp: now,
        detail: `${sessions.length} sessions scored`,
      });
    }
  }

  // AI Scientist
  const aiSci = dash.aiScientist as { recentStudies?: unknown[] } | undefined;
  if (aiSci?.recentStudies && Array.isArray(aiSci.recentStudies) && aiSci.recentStudies.length > 0) {
    activities.push({
      module: "ai-scientist",
      action: "studies",
      timestamp: now,
      detail: `${aiSci.recentStudies.length} recent studies`,
    });
  }

  return activities;
}

export async function getThinkerStrategy(sessionId: string): Promise<Record<string, unknown>> {
  return request(`/intelligence/thinker/strategy?sessionId=${encodeURIComponent(sessionId)}`);
}

export async function getThinkerStats(): Promise<Record<string, unknown>> {
  return request("/intelligence/thinker/stats");
}

export async function getSubconsciousStats(): Promise<Record<string, unknown>> {
  return request("/intelligence/subconscious/stats");
}

export async function getArchivistStats(): Promise<Record<string, unknown>> {
  return request("/intelligence/archivist/stats");
}

// ==================== Archive / Memory =============================================

export type ArchiveEntryType = 'conversation' | 'insight' | 'pattern' | 'dialectic' | 'event' | 'session' | string;
export type ArchiveSentiment = 'positive' | 'neutral' | 'negative' | string;

export interface ArchiveSearchOptions {
  filters?: {
    types?: string[];
    sessionId?: string;
    minImportance?: number;
    maxImportance?: number;
    sentiment?: string;
    topics?: string[];
    entities?: string[];
    tags?: string[];
    hasThinking?: boolean;
    startTime?: number;
    endTime?: number;
    source?: string;
  };
  limit?: number;
  sortBy?: 'relevance' | 'importance' | 'time';
}

export interface ArchiveSearchResult {
  entry: ArchiveEntry;
  score?: number;
  snippet?: string;
}

/** POST /memory/archives/search */
export async function searchArchives(
  query: string,
  opts: ArchiveSearchOptions = {}
): Promise<{ results: ArchiveSearchResult[]; total: number; query: string }> {
  const res = await fetch(`${API_BASE}/memory/archives/search`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ query, ...opts }),
  });
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return res.json();
}

/** GET /memory/archives/recent?limit=N&type=X */
export async function getRecentArchives(
  type?: string,
  limit = 50
): Promise<ArchiveEntry[]> {
  const params = new URLSearchParams({ limit: String(limit) });
  if (type) params.set('type', type);
  const data = await request<ArchiveEntry[] | { entries: ArchiveEntry[] }>(
    `/memory/archives/recent?${params}`
  );
  return Array.isArray(data) ? data : (data as any).entries ?? [];
}

/** GET /memory/archives/:id */
export async function getArchiveById(id: string): Promise<ArchiveEntry> {
  return request<ArchiveEntry>(`/memory/archives/${encodeURIComponent(id)}`);
}

/** GET /memory/archives/:id/related?limit=N */
export async function getRelatedArchives(id: string, limit = 10): Promise<ArchiveEntry[]> {
  const data = await request<ArchiveEntry[] | { entries: ArchiveEntry[] }>(
    `/memory/archives/${encodeURIComponent(id)}/related?limit=${limit}`
  );
  return Array.isArray(data) ? data : (data as any).entries ?? [];
}

/** GET /memory/archives/browse?category=tags|entities|topics&minCount=N */
export async function browseArchive(
  category: 'tags' | 'entities' | 'topics',
  minCount = 1
): Promise<{ category: string; items: { name: string; count: number }[] }> {
  return request(`/memory/archives/browse?category=${category}&minCount=${minCount}`);
}

export async function getMultiAgentMetrics(): Promise<Record<string, unknown>> {
  return request("/intelligence/multi-agent/metrics");
}

export async function getMultiAgentStats(): Promise<Record<string, unknown>> {
  return request("/intelligence/multi-agent/stats");
}
