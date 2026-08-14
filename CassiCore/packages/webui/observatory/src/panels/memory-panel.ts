/**
 * memory-panel
 *
 * Archive browser for the CassiCore Observatory.
 *
 * Features:
 *  - Browse recent archive entries (conversations, insights, patterns, dialectic, events)
 *  - Full-text search with debounce
 *  - Type filter tabs
 *  - Entry detail view with content, thinking blocks, topics, entities, importance
 *  - Related entries sidebar
 *  - Real-time refresh on thinker/archivist SSE events
 *  - Periodic 30s background refresh
 */

import { LitElement, html, css, nothing } from "lit";
import { customElement, state, property } from "lit/decorators.js";
import type { EventStreamManager } from "../api/event-stream.js";
import {
  searchArchives,
  getRecentArchives,
  getArchiveById,
  getRelatedArchives,
  type ArchiveEntry,
} from "../api/observatory-client.js";

type FilterType =
  | "all"
  | "conversation"
  | "insight"
  | "pattern"
  | "dialectic"
  | "event";

const FILTER_LABELS: Record<FilterType, string> = {
  all: "All",
  conversation: "Conversations",
  insight: "Insights",
  pattern: "Patterns",
  dialectic: "Dialectic",
  event: "Events",
};

const TYPE_COLORS: Record<string, string> = {
  conversation: "var(--c-blue, #6366f1)",
  insight: "var(--c-amber, #f59e0b)",
  pattern: "var(--c-green, #10b981)",
  dialectic: "var(--c-purple, #8b5cf6)",
  dialectic_yang: "var(--c-orange, #f97316)",
  dialectic_yin: "var(--c-teal, #14b8a6)",
  dialectic_serenity: "var(--c-purple, #8b5cf6)",
  event: "var(--c-gray, #6b7280)",
  summary: "var(--c-sky, #0ea5e9)",
  reflection: "var(--c-rose, #f43f5e)",
  thinking: "var(--c-indigo, #818cf8)",
};

/**
 * @dep callers: renderDetail (webui/observatory/src/panels/memory-panel.ts), renderCard (webui/observatory/src/panels/memory-panel.ts)
 * @dep module: Panels
 * @dep risk: LOW | 2 callers, 0 flows, 1 module
 */

function typeColor(type: string): string {
  return TYPE_COLORS[type] ?? TYPE_COLORS["event"];
}

function typeGroup(type: string): FilterType {
  if (type.startsWith("dialectic")) return "dialectic";
  if (type === "conversation") return "conversation";
  if (type === "insight" || type === "reflection" || type === "thinking")
    return "insight";
  if (type === "pattern" || type === "summary") return "pattern";
  return "event";
}

/**
 * @dep callers: renderDetail (webui/observatory/src/panels/memory-panel.ts), renderCard (webui/observatory/src/panels/memory-panel.ts)
 * @dep calls: now
 * @dep module: Panels
 * @dep risk: LOW | 2 callers, 0 flows, 1 module
 */

function relativeTime(ts: number): string {
  // ts may be unix seconds or milliseconds — normalise
  const ms = ts > 1e12 ? ts : ts * 1000;
  const diff = Math.max(0, Date.now() - ms);
  const secs = Math.floor(diff / 1000);
  if (secs < 60) return `${secs}s ago`;
  const mins = Math.floor(secs / 60);
  if (mins < 60) return `${mins}m ago`;
  const hrs = Math.floor(mins / 60);
  if (hrs < 24) return `${hrs}h ago`;
  const days = Math.floor(hrs / 24);
  return `${days}d ago`;
}

function importanceClass(v: number | undefined): string {
  if (!v) return "imp-low";
  if (v >= 0.8) return "imp-critical";
  if (v >= 0.6) return "imp-high";
  if (v >= 0.4) return "imp-medium";
  return "imp-low";
}

@customElement("memory-panel")
export class MemoryPanel extends LitElement {
  static override styles = css`
    :host {
      display: flex;
      flex-direction: column;
      height: 100%;
      background: var(--surface-1, #0f1117);
      color: var(--text-1, #e2e8f0);
      font-family: var(--font-mono, "JetBrains Mono", monospace);
      font-size: 12px;
      overflow: hidden;
    }

    /* ── Toolbar ─────────────────────────────────────────────────── */
    .toolbar {
      display: flex;
      align-items: center;
      gap: 8px;
      padding: 8px 12px;
      border-bottom: 1px solid var(--border, #1e2433);
      flex-shrink: 0;
    }

    .toolbar-title {
      font-weight: 700;
      font-size: 11px;
      letter-spacing: 0.08em;
      text-transform: uppercase;
      color: var(--text-2, #94a3b8);
    }

    .count-badge {
      background: var(--surface-2, #1a2035);
      border: 1px solid var(--border, #1e2433);
      border-radius: 10px;
      padding: 1px 7px;
      font-size: 10px;
      color: var(--text-3, #64748b);
    }

    .sep {
      flex: 1;
    }

    .search-input {
      background: var(--surface-2, #1a2035);
      border: 1px solid var(--border, #1e2433);
      border-radius: 4px;
      color: var(--text-1, #e2e8f0);
      font-family: inherit;
      font-size: 11px;
      padding: 4px 8px;
      width: 220px;
      outline: none;
      transition: border-color 0.15s;
    }

    .search-input:focus {
      border-color: var(--accent, #6366f1);
    }

    .icon-btn {
      background: transparent;
      border: 1px solid var(--border, #1e2433);
      border-radius: 4px;
      color: var(--text-2, #94a3b8);
      cursor: pointer;
      font-size: 14px;
      line-height: 1;
      padding: 3px 7px;
      transition: color 0.15s, background 0.15s;
    }

    .icon-btn:hover {
      background: var(--surface-2, #1a2035);
      color: var(--text-1, #e2e8f0);
    }

    .spinning {
      animation: spin 1s linear infinite;
    }

    @keyframes spin {
      from { transform: rotate(0deg); }
      to { transform: rotate(360deg); }
    }

    /* ── Type tabs ───────────────────────────────────────────────── */
    .type-tabs {
      display: flex;
      gap: 2px;
      padding: 6px 12px 0;
      border-bottom: 1px solid var(--border, #1e2433);
      flex-shrink: 0;
    }

    .type-tab {
      background: transparent;
      border: none;
      border-bottom: 2px solid transparent;
      color: var(--text-3, #64748b);
      cursor: pointer;
      font-family: inherit;
      font-size: 11px;
      padding: 4px 10px 6px;
      transition: color 0.15s, border-color 0.15s;
    }

    .type-tab:hover {
      color: var(--text-1, #e2e8f0);
    }

    .type-tab.active {
      border-bottom-color: var(--accent, #6366f1);
      color: var(--text-1, #e2e8f0);
    }

    /* ── Body (split) ────────────────────────────────────────────── */
    .body {
      display: flex;
      flex: 1;
      min-height: 0;
      overflow: hidden;
    }

    /* ── Entry list ──────────────────────────────────────────────── */
    .list {
      width: 340px;
      flex-shrink: 0;
      border-right: 1px solid var(--border, #1e2433);
      overflow-y: auto;
      padding: 6px 0;
    }

    .empty {
      padding: 24px 12px;
      color: var(--text-3, #64748b);
      text-align: center;
    }

    .entry-card {
      padding: 8px 12px;
      cursor: pointer;
      border-left: 2px solid transparent;
      transition: background 0.1s, border-color 0.1s;
    }

    .entry-card:hover {
      background: var(--surface-2, #1a2035);
    }

    .entry-card.selected {
      background: var(--surface-2, #1a2035);
      border-left-color: var(--accent, #6366f1);
    }

    .card-top {
      display: flex;
      align-items: center;
      gap: 5px;
      margin-bottom: 4px;
    }

    .type-pip {
      width: 6px;
      height: 6px;
      border-radius: 50%;
      flex-shrink: 0;
    }

    .card-type {
      font-size: 10px;
      color: var(--text-3, #64748b);
      flex: 1;
      overflow: hidden;
      text-overflow: ellipsis;
      white-space: nowrap;
    }

    .card-ts {
      font-size: 10px;
      color: var(--text-3, #64748b);
      flex-shrink: 0;
    }

    .card-preview {
      color: var(--text-2, #94a3b8);
      line-height: 1.5;
      overflow: hidden;
      display: -webkit-box;
      -webkit-line-clamp: 2;
      -webkit-box-orient: vertical;
    }

    .card-chips {
      display: flex;
      flex-wrap: wrap;
      gap: 3px;
      margin-top: 4px;
    }

    .chip {
      background: var(--surface-3, #111827);
      border: 1px solid var(--border, #1e2433);
      border-radius: 3px;
      font-size: 9px;
      padding: 1px 5px;
      color: var(--text-3, #64748b);
    }

    /* ── Detail pane ─────────────────────────────────────────────── */
    .detail {
      flex: 1;
      overflow-y: auto;
      padding: 0;
      min-width: 0;
    }

    .detail-empty {
      padding: 40px 24px;
      color: var(--text-3, #64748b);
      text-align: center;
    }

    .detail-content {
      padding: 16px 20px;
    }

    .detail-header {
      display: flex;
      align-items: center;
      gap: 8px;
      margin-bottom: 14px;
      flex-wrap: wrap;
    }

    .type-badge {
      background: color-mix(in srgb, var(--badge-color) 15%, transparent);
      border: 1px solid color-mix(in srgb, var(--badge-color) 40%, transparent);
      border-radius: 4px;
      color: var(--badge-color);
      font-size: 10px;
      padding: 2px 8px;
    }

    .detail-ts {
      font-size: 10px;
      color: var(--text-3, #64748b);
    }

    .importance-badge {
      font-size: 10px;
      border-radius: 4px;
      padding: 2px 7px;
      border: 1px solid transparent;
    }

    .imp-critical { background: #451a1a; border-color: #7f1d1d; color: #fca5a5; }
    .imp-high     { background: #1c1917; border-color: #78350f; color: #fcd34d; }
    .imp-medium   { background: #0f1a17; border-color: #14532d; color: #86efac; }
    .imp-low      { background: transparent; border-color: var(--border, #1e2433); color: var(--text-3, #64748b); }

    .sentiment {
      font-size: 10px;
      color: var(--text-3, #64748b);
    }

    .detail-text {
      color: var(--text-1, #e2e8f0);
      line-height: 1.7;
      white-space: pre-wrap;
      word-break: break-word;
      margin-bottom: 16px;
    }

    .thinking-block {
      border: 1px solid var(--border, #1e2433);
      border-radius: 4px;
      margin-bottom: 14px;
      overflow: hidden;
    }

    .thinking-block summary {
      cursor: pointer;
      padding: 6px 10px;
      background: var(--surface-2, #1a2035);
      color: var(--text-3, #64748b);
      font-size: 10px;
      user-select: none;
      list-style: none;
    }

    .thinking-block summary::before {
      content: "▶ ";
    }

    .thinking-block[open] summary::before {
      content: "▼ ";
    }

    .thinking-content {
      padding: 10px;
      color: var(--text-2, #94a3b8);
      font-size: 11px;
      line-height: 1.6;
      white-space: pre-wrap;
      word-break: break-word;
      border-top: 1px solid var(--border, #1e2433);
      background: var(--surface-1, #0f1117);
    }

    .meta-section {
      border-top: 1px solid var(--border, #1e2433);
      padding-top: 12px;
      margin-top: 4px;
    }

    .meta-row {
      display: flex;
      gap: 8px;
      align-items: flex-start;
      margin-bottom: 6px;
      font-size: 11px;
    }

    .meta-label {
      color: var(--text-3, #64748b);
      min-width: 64px;
      flex-shrink: 0;
      text-align: right;
    }

    .meta-value {
      color: var(--text-2, #94a3b8);
      word-break: break-all;
    }

    .mono {
      font-family: var(--font-mono, monospace);
      font-size: 10px;
    }

    .related-section {
      border-top: 1px solid var(--border, #1e2433);
      margin-top: 14px;
      padding-top: 12px;
    }

    .related-title {
      font-size: 10px;
      text-transform: uppercase;
      letter-spacing: 0.06em;
      color: var(--text-3, #64748b);
      margin-bottom: 8px;
    }

    .related-card {
      background: var(--surface-2, #1a2035);
      border: 1px solid var(--border, #1e2433);
      border-left: 2px solid var(--rc-color, #6b7280);
      border-radius: 4px;
      cursor: pointer;
      margin-bottom: 6px;
      padding: 7px 10px;
      transition: background 0.1s;
    }

    .related-card:hover {
      background: var(--surface-3, #111827);
    }

    .related-card-type {
      font-size: 10px;
      color: var(--text-3, #64748b);
      margin-bottom: 3px;
    }

    .related-card-text {
      color: var(--text-2, #94a3b8);
      overflow: hidden;
      display: -webkit-box;
      -webkit-line-clamp: 2;
      -webkit-box-orient: vertical;
      line-height: 1.5;
    }
  `;

  @property({ attribute: false }) stream: EventStreamManager | null = null;

  @state() private entries: ArchiveEntry[] = [];
  @state() private loading = false;
  @state() private query = "";
  @state() private typeFilter: FilterType = "all";
  @state() private selectedId: string | null = null;
  @state() private selectedEntry: ArchiveEntry | null = null;
  @state() private relatedEntries: ArchiveEntry[] = [];
  @state() private detailLoading = false;
  @state() private total = 0;

  private unsubs: Array<() => void> = [];
  private refreshTimer: ReturnType<typeof setInterval> | null = null;
  private searchDebounce: ReturnType<typeof setTimeout> | null = null;

  override connectedCallback(): void {
    super.connectedCallback();
    this.load();
    this.attachStream();
    this.refreshTimer = setInterval(() => this.load(), 30_000);
  }

  override disconnectedCallback(): void {
    super.disconnectedCallback();
    this.detachStream();
    if (this.refreshTimer) clearInterval(this.refreshTimer);
    if (this.searchDebounce) clearTimeout(this.searchDebounce);
  }

  override updated(changed: Map<string, unknown>): void {
    if (changed.has("stream") && this.stream) {
      this.detachStream();
      this.attachStream();
    }
  }

  private attachStream(): void {
    if (!this.stream) return;
    this.unsubs.push(
      this.stream.onAll((raw) => {
        const data = raw as Record<string, unknown>;
        const type = data["type"] as string | undefined;
        if (!type) return;
        // Trigger a refresh when the archivist stores something or the thinker emits an insight
        if (
          type === "thinker:insight" ||
          type === "thinker:ponder" ||
          type === "memory:stored" ||
          type === "archivist:stored" ||
          type === "turn:end"
        ) {
          setTimeout(() => this.load(), 800);
        }
      })
    );
  }

  private detachStream(): void {
    this.unsubs.forEach((u) => u());
    this.unsubs = [];
  }

  private async load(): Promise<void> {
    this.loading = true;
    try {
      if (this.query.trim()) {
        const filters =
          this.typeFilter !== "all"
            ? { types: [this.typeFilter] }
            : undefined;
        const result = await searchArchives(this.query, {
          filters,
          limit: 100,
          sortBy: "time",
        });
        const raw = (result as any).results ?? result ?? [];
        this.entries = Array.isArray(raw)
          ? (raw as Array<ArchiveEntry | { entry: ArchiveEntry }>).map((r) =>
              "entry" in r ? r.entry : r
            )
          : [];
      } else {
        const typeArg =
          this.typeFilter !== "all" ? this.typeFilter : undefined;
        this.entries = await getRecentArchives(typeArg, 100);
      }
      this.total = this.entries.length;
    } catch {
      // silent — entries stay as-is
    } finally {
      this.loading = false;
    }
  }

  private handleSearchInput(e: Event): void {
    this.query = (e.target as HTMLInputElement).value;
    if (this.searchDebounce) clearTimeout(this.searchDebounce);
    this.searchDebounce = setTimeout(() => this.load(), 350);
  }

  private setTypeFilter(t: FilterType): void {
    this.typeFilter = t;
    this.load();
  }

  private async selectEntry(id: string): Promise<void> {
    if (this.selectedId === id) {
      this.selectedId = null;
      this.selectedEntry = null;
      this.relatedEntries = [];
      return;
    }
    this.selectedId = id;
    this.detailLoading = true;
    this.relatedEntries = [];
    try {
      const [entry, related] = await Promise.all([
        getArchiveById(id),
        getRelatedArchives(id, 5),
      ]);
      this.selectedEntry = entry;
      this.relatedEntries = related;
    } catch {
      this.selectedEntry =
        this.entries.find((e) => e.id === id) ?? null;
    } finally {
      this.detailLoading = false;
    }
  }


  private renderCard(e: ArchiveEntry): unknown {
    const color = typeColor(e.type);
    const selected = this.selectedId === e.id;
    const preview = e.content?.slice(0, 140) ?? "";
    const topics: string[] =
      e.analysis?.topics ?? (e.metadata?.topics as string[] | undefined) ?? [];

    return html`
      <div
        class="entry-card ${selected ? "selected" : ""}"
        @click=${() => this.selectEntry(e.id)}
      >
        <div class="card-top">
          <span class="type-pip" style="background: ${color}"></span>
          <span class="card-type">${e.type}</span>
          <span class="card-ts">${relativeTime(e.timestamp)}</span>
        </div>
        <div class="card-preview">
          ${preview}${(e.content?.length ?? 0) > 140 ? "…" : ""}
        </div>
        ${topics.length > 0
          ? html`
              <div class="card-chips">
                ${topics
                  .slice(0, 3)
                  .map((t) => html`<span class="chip">${t}</span>`)}
              </div>
            `
          : nothing}
      </div>
    `;
  }

  private renderDetail(): unknown {
    if (!this.selectedId) {
      return html`<div class="detail-empty">
        Select an entry to view details
      </div>`;
    }
    if (this.detailLoading) {
      return html`<div class="detail-empty">Loading…</div>`;
    }
    const e = this.selectedEntry;
    if (!e) return html`<div class="detail-empty">Entry not found</div>`;

    const color = typeColor(e.type);
    const importance = e.analysis?.importance ?? (e.metadata?.importance as number | undefined);
    const sentiment = e.analysis?.sentiment ?? (e.metadata?.sentiment as string | undefined);
    const topics: string[] = e.analysis?.topics ?? (e.metadata?.topics as string[] | undefined) ?? [];
    const entities: string[] = e.analysis?.entities ?? (e.metadata?.entities as string[] | undefined) ?? [];
    const tags: string[] = e.analysis?.suggestedTags ?? (e.metadata?.tags as string[] | undefined) ?? [];

    return html`
      <div class="detail-content">
        <div class="detail-header">
          <span class="type-badge" style="--badge-color: ${color}">
            ${e.type}
          </span>
          <span class="detail-ts">${relativeTime(e.timestamp)}</span>
          ${importance !== undefined
            ? html`<span
                class="importance-badge ${importanceClass(importance)}"
                title="Importance"
                >imp ${(importance * 100).toFixed(0)}%</span
              >`
            : nothing}
          ${sentiment
            ? html`<span class="sentiment">${sentiment}</span>`
            : nothing}
        </div>

        <div class="detail-text">${e.content}</div>

        ${e.thinking
          ? html`
              <details class="thinking-block">
                <summary>Thinking block</summary>
                <div class="thinking-content">${e.thinking}</div>
              </details>
            `
          : nothing}

        <div class="meta-section">
          ${topics.length > 0
            ? html`<div class="meta-row">
                <span class="meta-label">Topics</span>
                <span class="meta-value">${topics.join(", ")}</span>
              </div>`
            : nothing}
          ${entities.length > 0
            ? html`<div class="meta-row">
                <span class="meta-label">Entities</span>
                <span class="meta-value">${entities.join(", ")}</span>
              </div>`
            : nothing}
          ${tags.length > 0
            ? html`<div class="meta-row">
                <span class="meta-label">Tags</span>
                <span class="meta-value">${tags.join(", ")}</span>
              </div>`
            : nothing}
          ${e.sessionId
            ? html`<div class="meta-row">
                <span class="meta-label">Session</span>
                <span class="meta-value mono"
                  >${e.sessionId.slice(0, 12)}…</span
                >
              </div>`
            : nothing}
          ${e.source
            ? html`<div class="meta-row">
                <span class="meta-label">Source</span>
                <span class="meta-value">${e.source}</span>
              </div>`
            : nothing}
          <div class="meta-row">
            <span class="meta-label">ID</span>
            <span class="meta-value mono">${e.id.slice(0, 16)}…</span>
          </div>
        </div>

        ${this.relatedEntries.length > 0
          ? html`
              <div class="related-section">
                <div class="related-title">Related entries</div>
                ${this.relatedEntries.map(
                  (r) => html`
                    <div
                      class="related-card"
                      style="--rc-color: ${typeColor(r.type)}"
                      @click=${() => this.selectEntry(r.id)}
                    >
                      <div class="related-card-type">
                        ${r.type} · ${relativeTime(r.timestamp)}
                      </div>
                      <div class="related-card-text">
                        ${r.content?.slice(0, 100)}${(r.content?.length ?? 0) > 100 ? "…" : ""}
                      </div>
                    </div>
                  `
                )}
              </div>
            `
          : nothing}
      </div>
    `;
  }

  override render(): unknown {
    const filters: FilterType[] = [
      "all",
      "conversation",
      "insight",
      "pattern",
      "dialectic",
      "event",
    ];

    return html`
      <div class="toolbar">
        <span class="toolbar-title">Memory Archive</span>
        <span class="count-badge">${this.total} entries</span>
        <div class="sep"></div>
        <input
          class="search-input"
          type="search"
          placeholder="Search archive…"
          .value=${this.query}
          @input=${this.handleSearchInput}
        />
        <button
          class="icon-btn ${this.loading ? "spinning" : ""}"
          @click=${() => this.load()}
          title="Refresh"
        >
          ↻
        </button>
      </div>

      <div class="type-tabs">
        ${filters.map(
          (t) => html`
            <button
              class="type-tab ${this.typeFilter === t ? "active" : ""}"
              @click=${() => this.setTypeFilter(t)}
            >
              ${FILTER_LABELS[t]}
            </button>
          `
        )}
      </div>

      <div class="body">
        <div class="list">
          ${this.entries.length === 0
            ? html`<div class="empty">
                ${this.loading ? "Loading…" : "No entries found"}
              </div>`
            : this.entries.map((e) => this.renderCard(e))}
        </div>
        <div class="detail">${this.renderDetail()}</div>
      </div>
    `;
  }
}

declare global {
  interface HTMLElementTagNameMap {
    "memory-panel": MemoryPanel;
  }
}
