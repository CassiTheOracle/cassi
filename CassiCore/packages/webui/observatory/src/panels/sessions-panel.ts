/**
 * sessions-panel
 *
 * Session management tab for the CassiCore Observatory.
 *
 * Features:
 *  - Table listing all sessions (id, channel, sender, age, messages, tokens, preview)
 *  - Checkbox select + select-all / deselect-all
 *  - "Delete selected" button
 *  - Prune toolbar: older than N days, all, by channelId, empty sessions
 *  - Live refresh via button; also refreshes after each delete/prune
 */

import { LitElement, html, css, nothing } from "lit";
import { customElement, state } from "lit/decorators.js";
import {
  listSessions,
  deleteSession,
  pruneSessions,
  type Session,
} from "../api/observatory-client.js";

type PruneMode = "olderThan" | "channelId" | "empty" | "all";

function relativeTime(iso: string): string {
  const ms = Date.now() - new Date(iso).getTime();
  const secs = Math.floor(ms / 1000);
  if (secs < 60) return `${secs}s ago`;
  const mins = Math.floor(secs / 60);
  if (mins < 60) return `${mins}m ago`;
  const hrs = Math.floor(mins / 60);
  if (hrs < 24) return `${hrs}h ago`;
  const days = Math.floor(hrs / 24);
  return `${days}d ago`;
}

@customElement("sessions-panel")
export class SessionsPanel extends LitElement {
  static override styles = css`
    :host {
      display: flex;
      flex-direction: column;
      height: 100%;
      overflow: hidden;
      background: var(--color-surface, #0f0f12);
      color: var(--color-text, #e2e2f0);
    }

    /* ── Toolbar ── */
    .toolbar {
      display: flex;
      align-items: center;
      gap: 0.5rem;
      padding: 0.5rem 0.75rem;
      background: var(--color-surface-2, #1a1a23);
      border-bottom: 1px solid var(--color-border, #2a2a3d);
      flex-shrink: 0;
      flex-wrap: wrap;
    }

    .toolbar-title {
      font-size: 0.72rem;
      font-weight: 600;
      color: var(--color-text-muted, #6b6b8a);
      text-transform: uppercase;
      letter-spacing: 0.08em;
      margin-right: 0.25rem;
    }

    .sep {
      width: 1px;
      height: 16px;
      background: var(--color-border, #2a2a3d);
      margin: 0 0.25rem;
      flex-shrink: 0;
    }

    .count-badge {
      font-size: 0.72rem;
      color: var(--color-text-muted, #6b6b8a);
    }

    .count-badge strong {
      color: var(--color-text, #e2e2f0);
    }

    button {
      display: inline-flex;
      align-items: center;
      gap: 0.3rem;
      background: var(--color-surface-3, #24243a);
      border: 1px solid var(--color-border, #2a2a3d);
      color: var(--color-text, #e2e2f0);
      font-size: 0.72rem;
      padding: 0.2rem 0.55rem;
      border-radius: 4px;
      cursor: pointer;
      transition: background 0.15s;
      white-space: nowrap;
    }
    button:hover { background: #2e2e4a; }
    button:disabled { opacity: 0.4; cursor: default; }

    button.danger {
      border-color: #7f1d1d;
      color: #fca5a5;
    }
    button.danger:not(:disabled):hover { background: #450a0a; }

    button.primary {
      border-color: #4338ca;
      color: #a5b4fc;
    }
    button.primary:not(:disabled):hover { background: #1e1b4b; }

    /* ── Prune bar ── */
    .prune-bar {
      display: flex;
      align-items: center;
      gap: 0.5rem;
      padding: 0.45rem 0.75rem;
      background: var(--color-surface-2, #1a1a23);
      border-bottom: 1px solid var(--color-border, #2a2a3d);
      flex-shrink: 0;
      flex-wrap: wrap;
    }

    .prune-label {
      font-size: 0.7rem;
      font-weight: 600;
      color: var(--color-text-muted, #6b6b8a);
      text-transform: uppercase;
      letter-spacing: 0.07em;
    }

    .prune-mode-select,
    .prune-input {
      background: var(--color-surface-3, #24243a);
      border: 1px solid var(--color-border, #2a2a3d);
      color: var(--color-text, #e2e2f0);
      font-size: 0.75rem;
      padding: 0.2rem 0.4rem;
      border-radius: 4px;
    }

    .prune-input {
      width: 72px;
    }

    .prune-note {
      font-size: 0.68rem;
      color: var(--color-text-muted, #6b6b8a);
      font-style: italic;
    }

    /* ── Toast notification ── */
    .toast {
      position: fixed;
      bottom: 1.25rem;
      right: 1.25rem;
      background: var(--color-surface-2, #1a1a23);
      border: 1px solid var(--color-border, #2a2a3d);
      border-radius: 6px;
      padding: 0.5rem 0.9rem;
      font-size: 0.8rem;
      color: var(--color-text, #e2e2f0);
      z-index: 100;
      box-shadow: 0 4px 16px rgba(0,0,0,0.4);
      animation: slide-in 0.2s ease;
    }
    .toast.ok { border-color: #166534; color: #86efac; }
    .toast.err { border-color: #7f1d1d; color: #fca5a5; }

    @keyframes slide-in {
      from { opacity: 0; transform: translateY(8px); }
      to { opacity: 1; transform: translateY(0); }
    }

    /* ── Table ── */
    .table-wrap {
      flex: 1;
      overflow: auto;
      min-height: 0;
    }

    table {
      width: 100%;
      border-collapse: collapse;
      font-size: 0.75rem;
    }

    thead th {
      position: sticky;
      top: 0;
      background: var(--color-surface-2, #1a1a23);
      border-bottom: 1px solid var(--color-border, #2a2a3d);
      padding: 0.4rem 0.6rem;
      text-align: left;
      font-weight: 600;
      color: var(--color-text-muted, #6b6b8a);
      font-size: 0.68rem;
      text-transform: uppercase;
      letter-spacing: 0.07em;
      white-space: nowrap;
    }

    thead th:first-child {
      width: 32px;
      text-align: center;
    }

    tbody tr {
      border-bottom: 1px solid var(--color-border, #2a2a3d);
      transition: background 0.1s;
    }

    tbody tr:hover { background: var(--color-surface-2, #1a1a23); }
    tbody tr.selected { background: #1e1b4b; }

    td {
      padding: 0.35rem 0.6rem;
      vertical-align: middle;
    }

    td:first-child {
      text-align: center;
    }

    .id-cell {
      font-family: ui-monospace, monospace;
      font-size: 0.7rem;
      color: #818cf8;
      white-space: nowrap;
    }

    .channel-cell {
      white-space: nowrap;
    }

    .channel-tag {
      font-size: 0.65rem;
      padding: 0.1rem 0.35rem;
      border-radius: 3px;
      background: var(--color-surface-3, #24243a);
      color: var(--color-text-muted, #6b6b8a);
      border: 1px solid var(--color-border, #2a2a3d);
    }

    .age-cell {
      white-space: nowrap;
      color: var(--color-text-muted, #6b6b8a);
    }

    .msgs-cell {
      text-align: right;
      color: var(--color-text-muted, #6b6b8a);
    }

    .msgs-cell.has-msgs { color: var(--color-text, #e2e2f0); }

    .preview-cell {
      max-width: 320px;
      overflow: hidden;
      text-overflow: ellipsis;
      white-space: nowrap;
      color: var(--color-text-muted, #6b6b8a);
      font-size: 0.7rem;
    }

    .empty-state {
      display: flex;
      flex-direction: column;
      align-items: center;
      justify-content: center;
      flex: 1;
      gap: 0.5rem;
      color: var(--color-text-muted, #6b6b8a);
      font-size: 0.85rem;
      padding: 3rem;
    }

    .empty-state .icon { font-size: 2rem; }

    .spinner {
      display: inline-block;
      width: 10px;
      height: 10px;
      border: 2px solid #4338ca;
      border-top-color: transparent;
      border-radius: 50%;
      animation: spin 0.6s linear infinite;
    }

    @keyframes spin { to { transform: rotate(360deg); } }

    input[type="checkbox"] {
      accent-color: #6366f1;
      cursor: pointer;
      width: 13px;
      height: 13px;
    }
  `;

  @state() private sessions: Session[] = [];
  @state() private selected = new Set<string>();
  @state() private loading = false;
  @state() private busy = false;

  // Prune controls
  @state() private pruneMode: PruneMode = "olderThan";
  @state() private pruneOlderThanDays = 7;
  @state() private pruneChannelId = "";

  // Toast
  @state() private toast: { msg: string; ok: boolean } | null = null;
  private toastTimer: ReturnType<typeof setTimeout> | null = null;

  override connectedCallback(): void {
    super.connectedCallback();
    this.loadSessions();
  }

  // ── Data ──────────────────────────────────────────────────────────────────────

  private async loadSessions(): Promise<void> {
    this.loading = true;
    try {
      this.sessions = await listSessions();
      // Drop selections for IDs that no longer exist
      const ids = new Set(this.sessions.map((s) => s.id));
      for (const id of this.selected) {
        if (!ids.has(id)) this.selected.delete(id);
      }
      this.selected = new Set(this.selected);
    } catch (err) {
      this.showToast(`Load failed: ${String(err)}`, false);
    } finally {
      this.loading = false;
    }
  }

  // ── Selection ─────────────────────────────────────────────────────────────────

  private toggleSelect(id: string): void {
    const next = new Set(this.selected);
    if (next.has(id)) next.delete(id);
    else next.add(id);
    this.selected = next;
  }

  private selectAll(): void {
    this.selected = new Set(this.sessions.map((s) => s.id));
  }

  private deselectAll(): void {
    this.selected = new Set();
  }

  // ── Delete selected ───────────────────────────────────────────────────────────

  private async deleteSelected(): Promise<void> {
    if (this.selected.size === 0 || this.busy) return;
    const ids = Array.from(this.selected);
    if (!confirm(`Delete ${ids.length} session(s)? This cannot be undone.`)) return;

    this.busy = true;
    let failed = 0;
    try {
      await Promise.allSettled(
        ids.map((id) =>
          deleteSession(id).catch(() => { failed++; })
        )
      );
      const deleted = ids.length - failed;
      this.showToast(
        failed > 0
          ? `Deleted ${deleted} session(s); ${failed} failed`
          : `Deleted ${deleted} session(s)`,
        failed === 0
      );
      this.selected = new Set();
      await this.loadSessions();
    } finally {
      this.busy = false;
    }
  }

  // ── Prune ─────────────────────────────────────────────────────────────────────

  private async runPrune(): Promise<void> {
    if (this.busy) return;

    let label = "";
    let opts = {};

    switch (this.pruneMode) {
      case "olderThan":
        label = `sessions older than ${this.pruneOlderThanDays} day(s)`;
        opts = { olderThanDays: this.pruneOlderThanDays };
        break;
      case "channelId":
        if (!this.pruneChannelId.trim()) {
          this.showToast("Enter a channelId first", false);
          return;
        }
        label = `all sessions on channel "${this.pruneChannelId.trim()}"`;
        opts = { channelId: this.pruneChannelId.trim() };
        break;
      case "empty":
        label = "sessions with no messages";
        opts = { emptyOnly: true };
        break;
      case "all":
        label = "ALL sessions";
        break;
    }

    if (!confirm(`Prune ${label}? This cannot be undone.`)) return;

    this.busy = true;
    try {
      const pruneOpts = this.pruneMode === "all" ? { all: true } : opts;
      const deleted = await pruneSessions(pruneOpts);
      this.showToast(`Pruned ${deleted} session(s)`, true);
      this.selected = new Set();
      await this.loadSessions();
    } catch (err) {
      this.showToast(`Prune failed: ${String(err)}`, false);
    } finally {
      this.busy = false;
    }
  }

  // ── Toast ─────────────────────────────────────────────────────────────────────

  private showToast(msg: string, ok: boolean): void {
    if (this.toastTimer) clearTimeout(this.toastTimer);
    this.toast = { msg, ok };
    this.toastTimer = setTimeout(() => {
      this.toast = null;
      this.toastTimer = null;
    }, 3500);
  }

  // ── Render ────────────────────────────────────────────────────────────────────

  override render() {
    const allSelected =
      this.sessions.length > 0 && this.selected.size === this.sessions.length;
    const someSelected = this.selected.size > 0;

    // Unique channelIds for prune input hint
    const channels = [...new Set(this.sessions.map((s) => s.channelId))].sort();

    return html`
      <!-- ── Toolbar ── -->
      <div class="toolbar">
        <span class="toolbar-title">Sessions</span>

        <span class="count-badge">
          <strong>${this.sessions.length}</strong> total
          ${someSelected ? html`· <strong>${this.selected.size}</strong> selected` : nothing}
        </span>

        <div class="sep"></div>

        <button @click=${this.selectAll} ?disabled=${this.busy || this.sessions.length === 0}>
          Select all
        </button>
        <button @click=${this.deselectAll} ?disabled=${this.busy || !someSelected}>
          Deselect
        </button>

        <button
          class="danger"
          ?disabled=${this.busy || !someSelected}
          @click=${this.deleteSelected}
        >
          ${this.busy ? html`<span class="spinner"></span>` : nothing}
          Delete selected (${this.selected.size})
        </button>

        <div class="sep"></div>

        <button
          class="primary"
          ?disabled=${this.loading || this.busy}
          @click=${this.loadSessions}
        >
          ${this.loading ? html`<span class="spinner"></span>` : "↻"}
          Refresh
        </button>
      </div>

      <!-- ── Prune bar ── -->
      <div class="prune-bar">
        <span class="prune-label">Prune</span>

        <select
          class="prune-mode-select"
          .value=${this.pruneMode}
          @change=${(e: Event) => {
            this.pruneMode = (e.target as HTMLSelectElement).value as PruneMode;
          }}
          ?disabled=${this.busy}
        >
          <option value="olderThan">Older than N days</option>
          <option value="channelId">By channelId</option>
          <option value="empty">Empty sessions</option>
          <option value="all">All sessions</option>
        </select>

        ${this.pruneMode === "olderThan"
          ? html`
              <input
                class="prune-input"
                type="number"
                min="0"
                .value=${String(this.pruneOlderThanDays)}
                @input=${(e: Event) => {
                  this.pruneOlderThanDays = Number((e.target as HTMLInputElement).value);
                }}
                ?disabled=${this.busy}
              />
              <span class="prune-note">days</span>
            `
          : nothing}

        ${this.pruneMode === "channelId"
          ? html`
              <input
                class="prune-input"
                style="width:160px"
                type="text"
                placeholder="e.g. channel:cli"
                list="channel-list"
                .value=${this.pruneChannelId}
                @input=${(e: Event) => {
                  this.pruneChannelId = (e.target as HTMLInputElement).value;
                }}
                ?disabled=${this.busy}
              />
              <datalist id="channel-list">
                ${channels.map((c) => html`<option value=${c}></option>`)}
              </datalist>
            `
          : nothing}

        ${this.pruneMode === "empty"
          ? html`<span class="prune-note">sessions with 0 messages</span>`
          : nothing}

        ${this.pruneMode === "all"
          ? html`<span class="prune-note" style="color:#fca5a5">⚠ deletes everything</span>`
          : nothing}

        <button
          class="danger"
          ?disabled=${this.busy}
          @click=${this.runPrune}
        >
          ${this.busy ? html`<span class="spinner"></span>` : nothing}
          Run prune
        </button>
      </div>

      <!-- ── Table ── -->
      ${this.sessions.length === 0 && !this.loading
        ? html`
            <div class="empty-state">
              <span class="icon">🗂</span>
              <span>No sessions found</span>
            </div>
          `
        : html`
            <div class="table-wrap">
              <table>
                <thead>
                  <tr>
                    <th>
                      <input
                        type="checkbox"
                        .checked=${allSelected}
                        @change=${allSelected ? this.deselectAll : this.selectAll}
                        title="Select / deselect all"
                      />
                    </th>
                    <th>ID</th>
                    <th>Channel</th>
                    <th>Sender</th>
                    <th>Last active</th>
                    <th>Msgs</th>
                    <th>Tokens</th>
                    <th>Preview</th>
                  </tr>
                </thead>
                <tbody>
                  ${this.sessions.map((s) => {
                    const sel = this.selected.has(s.id);
                    return html`
                      <tr
                        class=${sel ? "selected" : ""}
                        @click=${() => this.toggleSelect(s.id)}
                      >
                        <td>
                          <input
                            type="checkbox"
                            .checked=${sel}
                            @click=${(e: Event) => e.stopPropagation()}
                            @change=${() => this.toggleSelect(s.id)}
                          />
                        </td>
                        <td class="id-cell" title=${s.id}>${s.id.slice(0, 8)}…</td>
                        <td class="channel-cell">
                          <span class="channel-tag">${s.channelId}</span>
                        </td>
                        <td>${s.senderId}</td>
                        <td class="age-cell" title=${s.lastActiveAt}>
                          ${relativeTime(s.lastActiveAt)}
                        </td>
                        <td class="msgs-cell ${s.historyLength > 0 ? "has-msgs" : ""}">
                          ${s.historyLength}
                        </td>
                        <td class="msgs-cell">
                          ${s.tokenCount > 0 ? s.tokenCount.toLocaleString() : "—"}
                        </td>
                        <td class="preview-cell" title=${s.lastMessage ?? s.firstMessage ?? ""}>
                          ${s.lastMessage ?? s.firstMessage ?? html`<em>empty</em>`}
                        </td>
                      </tr>
                    `;
                  })}
                </tbody>
              </table>
            </div>
          `}

      <!-- ── Toast ── -->
      ${this.toast
        ? html`
            <div class="toast ${this.toast.ok ? "ok" : "err"}">
              ${this.toast.msg}
            </div>
          `
        : nothing}
    `;
  }
}

declare global {
  interface HTMLElementTagNameMap {
    "sessions-panel": SessionsPanel;
  }
}
