/**
 * intelligence-panel
 *
 * Phase 3 Intelligence Observatory panel.
 *
 * Layout:
 *  ┌────────────────────────────────────────────────┐
 *  │  Toolbar: Refresh · last-updated timestamp      │
 *  ├──────────────────────────────┬─────────────────┤
 *  │  Module status cards (left)  │  Provider chart  │
 *  │                              │  (top-right)     │
 *  │                              ├─────────────────┤
 *  │                              │  Context window  │
 *  │                              │  chart (bottom)  │
 *  └──────────────────────────────┴─────────────────┘
 *
 * Data sources:
 *  - GET /intelligence/activity         → recent cognitive events feed
 *  - GET /intelligence/thinker/stats    → thinker module stats
 *  - GET /intelligence/subconscious/stats
 *  - GET /intelligence/archivist/stats
 *  - GET /providers/metrics             → per-provider request/latency/token metrics
 *  - SSE /events/stream                 → live intelligence:* events to pulse cards
 */

import { LitElement, html, css, nothing } from "lit";
import { customElement, property, state } from "lit/decorators.js";
import type { EventStreamManager } from "../api/event-stream.js";
import {
  getIntelligenceActivity,
  getThinkerStats,
  getSubconsciousStats,
  getArchivistStats,
  getProviderMetrics,
  type IntelligenceActivity,
  type ProviderMetrics,
} from "../api/observatory-client.js";
import "../components/provider-metrics-chart.js";
import "../components/context-window-chart.js";

// ─── Known intelligence modules ───────────────────────────────────────────────

interface ModuleInfo {
  key: string;
  label: string;
  icon: string;
  priority: number;
  color: string;
}

const MODULES: ModuleInfo[] = [
  { key: "memory",            label: "Memory",            icon: "\u{1F5C3}",  priority: 100, color: "#6366f1" },
  { key: "rule-enforcer",     label: "Rules",             icon: "\u{1F4DC}",  priority: 100, color: "#fb923c" },
  { key: "continuity",        label: "Continuity",        icon: "\u{1F517}",  priority: 90,  color: "#8b5cf6" },
  { key: "context-manager",   label: "Context Mgr",       icon: "\u{1F4CB}",  priority: 85,  color: "#0ea5e9" },
  { key: "reflect",           label: "Reflect",           icon: "\u{1FA9E}",  priority: 70,  color: "#06b6d4" },
  { key: "recover",           label: "Recover",           icon: "\u267B",  priority: 50,  color: "#f59e0b" },
  { key: "team-orchestrator", label: "Team Orchestrator",icon: "\u{1F3AF}",  priority: 45,  color: "#e879f9" },
  { key: "reflex",            label: "Reflex",            icon: "\u26A1",  priority: 45,  color: "#facc15" },
  { key: "subconscious",      label: "Subconscious",      icon: "\u{1F4AD}",  priority: 40,  color: "#a78bfa" },
  { key: "thinker",           label: "Thinker",           icon: "\u{1F9E0}",  priority: 30,  color: "#3b82f6" },
  { key: "ai-scientist",      label: "AI Scientist",      icon: "\u{1F52C}",  priority: 20,  color: "#34d399" },
  { key: "archivist",         label: "Archivist",         icon: "\u{1F4DA}",  priority: 15,  color: "#64748b" },
  { key: "optimizer",         label: "Optimizer",         icon: "\u2699",  priority: 5,   color: "#22c55e" },
  { key: "dialectic",         label: "Dialectic",         icon: "\u262F",  priority: 0,   color: "#f472b6" },
  { key: "multi-agent",       label: "Multi-Agent",       icon: "\u{1F91D}",  priority: 0,   color: "#14b8a6" },
];

interface ModuleState {
  active: boolean;
  lastActivity?: number;
  pulsing: boolean;
  stats?: Record<string, unknown>;
}

// ─── Component ────────────────────────────────────────────────────────────────

@customElement("intelligence-panel")
export class IntelligencePanel extends LitElement {
  static override styles = css`
    :host {
      display: flex;
      flex-direction: column;
      height: 100%;
      overflow: hidden;
      background: var(--color-surface, #0f0f12);
    }

    .toolbar {
      display: flex;
      align-items: center;
      gap: 0.5rem;
      padding: 0.5rem 0.75rem;
      background: var(--color-surface-2, #1a1a23);
      border-bottom: 1px solid var(--color-border, #2a2a3d);
      flex-shrink: 0;
    }

    .toolbar-title {
      font-size: 0.72rem;
      font-weight: 600;
      color: var(--color-text-muted, #6b6b8a);
      text-transform: uppercase;
      letter-spacing: 0.08em;
    }

    button {
      background: var(--color-surface-3, #24243a);
      border: 1px solid var(--color-border, #2a2a3d);
      color: var(--color-text, #e2e2f0);
      font-size: 0.72rem;
      padding: 0.2rem 0.55rem;
      border-radius: 4px;
      cursor: pointer;
      transition: background 0.15s;
    }
    button:hover { background: #2e2e4a; }

    .ts {
      margin-left: auto;
      font-size: 0.68rem;
      color: var(--color-text-muted, #6b6b8a);
    }

    /* ── Main body ── */
    .body {
      display: flex;
      flex: 1;
      min-height: 0;
      overflow: hidden;
    }

    /* ── Left: module cards ── */
    .modules-col {
      width: 220px;
      min-width: 180px;
      flex-shrink: 0;
      overflow-y: auto;
      overflow-x: hidden;
      padding: 0.5rem;
      border-right: 1px solid var(--color-border, #2a2a3d);
      display: flex;
      flex-direction: column;
      gap: 0.35rem;
    }

    .module-card {
      display: flex;
      align-items: center;
      gap: 0.5rem;
      padding: 0.35rem 0.5rem;
      border-radius: 5px;
      background: var(--color-surface-2, #1a1a23);
      border: 1px solid var(--color-border, #2a2a3d);
      transition: border-color 0.2s;
      cursor: default;
      min-height: 36px;
    }

    .module-card.active {
      border-color: var(--module-color, #6366f1);
    }

    .module-card.pulsing {
      animation: pulse-card 0.5s ease-out;
    }

    @keyframes pulse-card {
      0%   { box-shadow: 0 0 0 0 var(--module-color, #6366f1); }
      50%  { box-shadow: 0 0 0 4px color-mix(in srgb, var(--module-color) 40%, transparent); }
      100% { box-shadow: 0 0 0 0 transparent; }
    }

    .module-icon {
      font-size: 1rem;
      line-height: 1;
      flex-shrink: 0;
    }

    .module-info {
      display: flex;
      flex-direction: column;
      min-width: 0;
    }

    .module-name {
      font-size: 0.73rem;
      font-weight: 600;
      color: var(--color-text, #e2e2f0);
      white-space: nowrap;
      overflow: hidden;
      text-overflow: ellipsis;
    }

    .module-meta {
      font-size: 0.62rem;
      color: var(--color-text-muted, #6b6b8a);
      white-space: nowrap;
      overflow: hidden;
      text-overflow: ellipsis;
    }

    .priority-badge {
      margin-left: auto;
      font-size: 0.6rem;
      color: var(--color-text-muted, #6b6b8a);
      background: var(--color-surface-3, #24243a);
      padding: 0.1rem 0.3rem;
      border-radius: 3px;
      flex-shrink: 0;
    }

    .status-dot {
      width: 6px;
      height: 6px;
      border-radius: 50%;
      background: var(--color-text-muted, #6b6b8a);
      flex-shrink: 0;
    }
    .status-dot.active { background: var(--module-color, #6366f1); }

    /* ── Right: charts ── */
    .charts-col {
      flex: 1;
      min-width: 0;
      overflow: hidden;
      display: flex;
      flex-direction: column;
    }

    .chart-pane {
      flex: 1;
      min-height: 0;
      overflow: hidden;
      display: flex;
      flex-direction: column;
    }

    .chart-pane + .chart-pane {
      border-top: 1px solid var(--color-border, #2a2a3d);
    }

    /* ── Recent activity feed ── */
    .activity-section {
      border-top: 1px solid var(--color-border, #2a2a3d);
      flex-shrink: 0;
      max-height: 130px;
      overflow-y: auto;
      background: var(--color-surface-2, #1a1a23);
    }

    .activity-header {
      font-size: 0.65rem;
      font-weight: 600;
      text-transform: uppercase;
      letter-spacing: 0.07em;
      color: var(--color-text-muted, #6b6b8a);
      padding: 0.3rem 0.75rem 0.15rem;
      position: sticky;
      top: 0;
      background: var(--color-surface-2, #1a1a23);
    }

    .activity-row {
      display: grid;
      grid-template-columns: 65px 80px 1fr;
      gap: 0.4rem;
      font-size: 0.65rem;
      padding: 0.15rem 0.75rem;
      color: var(--color-text-muted, #6b6b8a);
      border-bottom: 1px solid transparent;
    }
    .activity-row:hover {
      background: var(--color-surface-3, #24243a);
    }
    .activity-row .time { color: var(--color-text-muted, #6b6b8a); }
    .activity-row .module { color: #6366f1; font-weight: 600; }
    .activity-row .detail { color: var(--color-text, #e2e2f0); overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
  `;

  @property({ attribute: false }) stream: EventStreamManager | null = null;
  @property() sessionId: string = "";

  @state() private moduleStates = new Map<string, ModuleState>();
  @state() private activities: IntelligenceActivity[] = [];
  @state() private providerMetrics: ProviderMetrics[] = [];
  @state() private lastUpdated: Date | null = null;

  private unsubs: Array<() => void> = [];
  private pulseTimers = new Map<string, ReturnType<typeof setTimeout>>();
  private pollTimer: ReturnType<typeof setInterval> | null = null;

  override connectedCallback(): void {
    super.connectedCallback();
    this.initModuleStates();
    this.loadData();
    this.pollTimer = setInterval(() => this.loadData(), 30_000);
  }

  override disconnectedCallback(): void {
    super.disconnectedCallback();
    this.detachStream();
    if (this.pollTimer) clearInterval(this.pollTimer);
    this.pulseTimers.forEach((t) => clearTimeout(t));
  }

  override updated(changed: Map<string, unknown>): void {
    if (changed.has("stream")) {
      this.detachStream();
      this.attachStream();
    }
  }

  // ─── Init ─────────────────────────────────────────────────────────────────

  private initModuleStates(): void {
    for (const mod of MODULES) {
      this.moduleStates.set(mod.key, { active: false, pulsing: false });
    }
    this.moduleStates = new Map(this.moduleStates); // trigger reactivity
  }

  // ─── Data loading ────────────────────────────────────────────────────────

  private async loadData(): Promise<void> {
    const [activities, providerMetrics, thinkerStats, subconsciousStats, archivistStats] =
      await Promise.allSettled([
        getIntelligenceActivity(30),
        getProviderMetrics(),
        getThinkerStats(),
        getSubconsciousStats(),
        getArchivistStats(),
      ]);

    if (activities.status === "fulfilled") {
      this.activities = activities.value.slice(0, 50);
      // Mark modules active if recently seen
      const recent = Date.now() - 60_000;
      const seen = new Set<string>();
      for (const a of activities.value) {
        const key = a.module.toLowerCase().replace(/\s+/g, "-");
        if (!seen.has(key) && a.timestamp > recent) {
          seen.add(key);
          this.setModuleActive(key, a.timestamp);
        }
      }
    }

    if (providerMetrics.status === "fulfilled") {
      this.providerMetrics = providerMetrics.value;
    }

    // Attach known stats to module cards — unwrap the nested `stats` key
    // Server returns: { stats: { totalPonders: N, ... } } for each module
    if (thinkerStats.status === "fulfilled") {
      const raw = thinkerStats.value as Record<string, unknown>;
      this.setModuleStats("thinker", (raw.stats as Record<string, unknown>) ?? raw);
    }
    if (subconsciousStats.status === "fulfilled") {
      const raw = subconsciousStats.value as Record<string, unknown>;
      this.setModuleStats("subconscious", (raw.stats as Record<string, unknown>) ?? raw);
    }
    if (archivistStats.status === "fulfilled") {
      const raw = archivistStats.value as Record<string, unknown>;
      this.setModuleStats("archivist", (raw.stats as Record<string, unknown>) ?? raw);
    }

    this.lastUpdated = new Date();
  }

  private setModuleActive(key: string, timestamp?: number): void {
    const existing = this.moduleStates.get(key) ?? { active: false, pulsing: false };
    this.moduleStates.set(key, { ...existing, active: true, lastActivity: timestamp });
    this.moduleStates = new Map(this.moduleStates);
  }

  private setModuleStats(key: string, stats: Record<string, unknown>): void {
    const existing = this.moduleStates.get(key) ?? { active: false, pulsing: false };
    this.moduleStates.set(key, { ...existing, stats });
    this.moduleStates = new Map(this.moduleStates);
  }

  private pulseModule(key: string): void {
    const existing = this.moduleStates.get(key) ?? { active: false, pulsing: false };
    this.moduleStates.set(key, { ...existing, active: true, pulsing: true, lastActivity: Date.now() });
    this.moduleStates = new Map(this.moduleStates);

    // Clear any existing timer
    const prev = this.pulseTimers.get(key);
    if (prev) clearTimeout(prev);

    this.pulseTimers.set(
      key,
      setTimeout(() => {
        const s = this.moduleStates.get(key);
        if (s) {
          this.moduleStates.set(key, { ...s, pulsing: false });
          this.moduleStates = new Map(this.moduleStates);
        }
        this.pulseTimers.delete(key);
      }, 800)
    );
  }

  // ─── SSE integration ──────────────────────────────────────────────────────

  private attachStream(): void {
    if (!this.stream) return;

    // Intelligence events → pulse cards
    const intelligenceEvents = [
      "thinker:ponder_start", "thinker:insight", "thinker:strategy-updated",
      "memory:stored", "memory:recalled", "memory:compacted",
      "subconscious:anomaly_detected", "subconscious:learning_updated",
      "archivist:archived", "archivist:retrieved",
      "recover:triggered", "recover:complete",
      "reflect:cycle_start", "reflect:cycle_complete",
      "dialectic:synthesis",
      "agent:spawned", "agent:completed",
    ];

    for (const evt of intelligenceEvents) {
      const key = evt.split(":")[0];
      this.unsubs.push(
        this.stream.on(evt, () => {
          this.pulseModule(key === "agent" ? "multi-agent" : key);
        })
      );
    }

    // Provider metrics refresh on request events
    this.unsubs.push(
      this.stream.on("provider:request_end", () => {
        // Debounced refresh of provider metrics
        getProviderMetrics()
          .then((m) => { this.providerMetrics = m; })
          .catch(() => { /* ignore */ });
      })
    );

    // Activity feed: prepend new intelligence activity events
    this.unsubs.push(
      this.stream.onAll((data) => {
        const ev = data as Record<string, unknown>;
        const type = ev["type"] as string | undefined;
        if (!type || !type.includes(":")) return;
        const [module] = type.split(":");
        const isIntelligence = MODULES.some((m) => m.key === module || type.startsWith(module));
        if (!isIntelligence) return;
        const entry: IntelligenceActivity = {
          module,
          action: type,
          sessionId: ev["sessionId"] as string | undefined,
          timestamp: Date.now(),
          detail: JSON.stringify(ev).slice(0, 120),
        };
        this.activities = [entry, ...this.activities].slice(0, 50);
      })
    );
  }

  private detachStream(): void {
    this.unsubs.forEach((u) => u());
    this.unsubs = [];
  }

  // ─── Helpers ─────────────────────────────────────────────────────────────

  private formatTime(ts?: number): string {
    if (!ts) return "—";
    const delta = Math.floor((Date.now() - ts) / 1000);
    if (delta < 60) return `${delta}s ago`;
    if (delta < 3600) return `${Math.floor(delta / 60)}m ago`;
    return `${Math.floor(delta / 3600)}h ago`;
  }

  private formatAction(action: string): string {
    // Make raw action strings more readable
    return action.replace(/[-_]/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());
  }

  private moduleMetaLine(mod: ModuleInfo, state: ModuleState): string {
    if (state.stats) {
      const s = state.stats;
      // Thinker-specific
      if (mod.key === "thinker" && s.totalPonders !== undefined) {
        return `${s.totalPonders} ponders`;
      }
      // Archivist-specific
      if (mod.key === "archivist" && s.totalEntries !== undefined) {
        return `${s.totalEntries} entries`;
      }
      // Subconscious-specific — server sends totalLearnings, totalAnomalies
      if (mod.key === "subconscious" && (s.totalLearnings !== undefined || s.learningCount !== undefined)) {
        const count = s.totalLearnings ?? s.learningCount;
        return `${count} learnings`;
      }
    }
    if (state.lastActivity) {
      return this.formatTime(state.lastActivity);
    }
    return "no recent activity";
  }

  // ─── Render ──────────────────────────────────────────────────────────────

  override render() {
    return html`
      <div class="toolbar">
        <span class="toolbar-title">Intelligence Observatory</span>
        <button @click=${() => this.loadData()}>↻ Refresh</button>
        ${this.lastUpdated
          ? html`<span class="ts">updated ${this.formatTime(this.lastUpdated.getTime())}</span>`
          : nothing}
      </div>

      <div class="body">
        <!-- Module status cards -->
        <div class="modules-col">
          ${MODULES.map((mod) => {
            const state = this.moduleStates.get(mod.key) ?? { active: false, pulsing: false };
            return html`
              <div
                class="module-card ${state.active ? "active" : ""} ${state.pulsing ? "pulsing" : ""}"
                style="--module-color:${mod.color}"
              >
                <span class="status-dot ${state.active ? "active" : ""}"></span>
                <span class="module-icon">${mod.icon}</span>
                <div class="module-info">
                  <span class="module-name">${mod.label}</span>
                  <span class="module-meta">${this.moduleMetaLine(mod, state)}</span>
                </div>
                <span class="priority-badge">${mod.priority}</span>
              </div>
            `;
          })}
        </div>

        <!-- Charts column -->
        <div class="charts-col">
          <div class="chart-pane">
            <provider-metrics-chart
              .metrics=${this.providerMetrics}
            ></provider-metrics-chart>
          </div>
          <div class="chart-pane">
            <context-window-chart
              .sessionId=${this.sessionId}
            ></context-window-chart>
          </div>
        </div>
      </div>

      <!-- Recent activity feed -->
      <div class="activity-section">
        <div class="activity-header">Recent Cognitive Activity</div>
        ${this.activities.length === 0
          ? html`<div style="padding:0.4rem 0.75rem;font-size:0.7rem;color:var(--color-text-muted,#6b6b8a)">No activity yet</div>`
          : this.activities.map(
              (a) => html`
                <div class="activity-row">
                  <span class="time">${this.formatTime(a.timestamp)}</span>
                  <span class="module">${a.module}</span>
                  <span class="detail" title=${a.detail ?? ""}>${this.formatAction(a.action)}${a.detail ? ` — ${a.detail}` : ""}</span>
                </div>
              `
            )}
      </div>
    `;
  }
}

declare global {
  interface HTMLElementTagNameMap {
    "intelligence-panel": IntelligencePanel;
  }
}
