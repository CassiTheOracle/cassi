import { LitElement, html, css, nothing } from "lit";
import { customElement, state } from "lit/decorators.js";
import type { Session } from "./api/observatory-client.js";
import { getHealth, listSessions, buildEventStreamUrl } from "./api/observatory-client.js";
import { EventStreamManager } from "./api/event-stream.js";
import "./panels/event-stream-panel.js";
import "./panels/topology-panel.js";
import "./panels/cognition-panel.js";
import "./panels/sessions-panel.js";
import "./panels/providers-panel.js";
import "./panels/memory-panel.js";
import "./components/split-pane.js";
import "./components/event-log.js";

type Tab = "events" | "topology" | "cognition" | "providers" | "sessions" | "memory";

const TABS: Array<{ id: Tab; label: string; icon: string; key: string }> = [
  { id: "events",       label: "Event Stream", icon: "⚡", key: "1" },
  { id: "topology",     label: "Topology",     icon: "🕸", key: "2" },
  { id: "cognition",   label: "Cognition",   icon: "🌊", key: "3" },
  { id: "providers",    label: "Providers",    icon: "🔌", key: "4" },
  { id: "sessions",     label: "Sessions",     icon: "🗂", key: "5" },
  { id: "memory",       label: "Memory",       icon: "🧠", key: "6" },
];

const TAB_STORAGE_KEY = "observatory:activeTab";
const SESSION_STORAGE_KEY = "observatory:selectedSession";

@customElement("observatory-app")
export class ObservatoryApp extends LitElement {
  static override styles = css`
    :host {
      display: flex;
      flex-direction: column;
      height: 100vh;
      overflow: hidden;
      background: var(--color-surface, #0f0f12);
      color: var(--color-text, #e2e2f0);
    }

    header {
      display: flex;
      align-items: center;
      gap: 1rem;
      padding: 0 1.25rem;
      height: 48px;
      background: var(--color-surface-2, #1a1a23);
      border-bottom: 1px solid var(--color-border, #2a2a3d);
      flex-shrink: 0;
    }

    .logo {
      font-weight: 700;
      font-size: 0.9rem;
      letter-spacing: 0.05em;
      color: #6366f1;
      white-space: nowrap;
    }

    .logo span {
      color: var(--color-text-muted, #6b6b8a);
      font-weight: 400;
    }

    nav {
      display: flex;
      gap: 2px;
      margin-left: 0.5rem;
    }

    nav button {
      display: flex;
      align-items: center;
      gap: 0.35rem;
      padding: 0.3rem 0.7rem;
      border: none;
      background: transparent;
      color: var(--color-text-muted, #6b6b8a);
      font-size: 0.78rem;
      cursor: pointer;
      border-radius: 4px;
      transition: background 0.15s, color 0.15s;
    }

    nav button:hover {
      background: var(--color-surface-3, #24243a);
      color: var(--color-text, #e2e2f0);
    }

    nav button.active {
      background: var(--color-surface-3, #24243a);
      color: #6366f1;
    }

    nav button .kbd {
      font-size: 0.62rem;
      color: var(--color-text-muted, #6b6b8a);
      border: 1px solid var(--color-border, #2a2a3d);
      border-radius: 3px;
      padding: 0 3px;
      line-height: 1.4;
    }

    nav button.active .kbd {
      border-color: #6366f1;
      color: #6366f1;
    }

    .spacer {
      flex: 1;
    }

    .health-badge {
      display: flex;
      align-items: center;
      gap: 0.4rem;
      font-size: 0.72rem;
      padding: 0.2rem 0.5rem;
      border-radius: 4px;
      background: var(--color-surface-3, #24243a);
    }

    .dot {
      width: 7px;
      height: 7px;
      border-radius: 50%;
      background: var(--color-text-muted, #6b6b8a);
    }
    .dot.ok { background: var(--color-green, #22c55e); }
    .dot.degraded { background: var(--color-yellow, #eab308); }
    .dot.error { background: var(--color-red, #ef4444); }

    .session-select {
      background: var(--color-surface-3, #24243a);
      border: 1px solid var(--color-border, #2a2a3d);
      color: var(--color-text, #e2e2f0);
      font-size: 0.75rem;
      padding: 0.2rem 0.4rem;
      border-radius: 4px;
      cursor: pointer;
      max-width: 200px;
    }

    main {
      flex: 1;
      overflow: hidden;
      display: flex;
      flex-direction: column;
    }

    .panel {
      flex: 1;
      overflow: hidden;
      display: none;
    }

    .panel.active {
      display: flex;
      flex-direction: column;
    }

    .placeholder {
      display: flex;
      flex-direction: column;
      align-items: center;
      justify-content: center;
      flex: 1;
      color: var(--color-text-muted, #6b6b8a);
      gap: 0.5rem;
    }

    .placeholder .icon {
      font-size: 2.5rem;
    }

    .placeholder p {
      font-size: 0.85rem;
      margin: 0;
    }

    .stream-status {
      font-size: 0.7rem;
      color: var(--color-text-muted, #6b6b8a);
    }
    .stream-status.connected { color: var(--color-green, #22c55e); }
    .stream-status.reconnecting { color: var(--color-yellow, #eab308); }

    event-log {
      display: block;
      overflow: hidden;
      min-width: 0;
      min-height: 0;
      flex: 1;
      background: var(--color-surface, #0f0f12);
    }
  `;

  @state() private activeTab: Tab = "events";
  @state() private sessions: Session[] = [];
  @state() private selectedSessionId: string = "";
  @state() private healthStatus: "ok" | "degraded" | "error" | "unknown" = "unknown";
  @state() private streamState: string = "closed";
  @state() private daemonVersion: string = "";

  private stream: EventStreamManager | null = null;
  private pollTimer: ReturnType<typeof setInterval> | null = null;
  private _onKeyDown = this._handleKeyDown.bind(this);

  override connectedCallback(): void {
    super.connectedCallback();
    // Restore persisted tab
    const savedTab = localStorage.getItem(TAB_STORAGE_KEY) as Tab | null;
    if (savedTab && TABS.some((t) => t.id === savedTab)) {
      this.activeTab = savedTab;
    }
    // NOTE: We intentionally do NOT restore selectedSessionId from localStorage here.
    // The daemon may have restarted since the last visit, making any stored session ID
    // stale. The stream always starts on the global (unfiltered) endpoint. The user
    // can pick a session from the dropdown after sessions are loaded, which will then
    // reconnect on the session-scoped endpoint and persist the new choice.

    window.addEventListener("keydown", this._onKeyDown);
    this.bootstrap();
  }

  override disconnectedCallback(): void {
    super.disconnectedCallback();
    this.stream?.close();
    if (this.pollTimer) clearInterval(this.pollTimer);
    window.removeEventListener("keydown", this._onKeyDown);
  }

  private _handleKeyDown(e: KeyboardEvent): void {
    const tag = (e.target as HTMLElement)?.tagName?.toLowerCase();
    if (tag === "input" || tag === "select" || tag === "textarea") return;
    const tab = TABS.find((t) => t.key === e.key);
    if (tab) {
      e.preventDefault();
      this.selectTab(tab.id);
    }
  }

  private async bootstrap(): Promise<void> {
    await this.refreshHealth();
    await this.refreshSessions();

    // Always start with the global (unfiltered) stream.
    // Never use a persisted session ID here — the daemon may have restarted
    // and the old ID would cause a 400 Bad Request.
    this.connectStream(undefined);

    // Poll health every 15s
    this.pollTimer = setInterval(() => this.refreshHealth(), 15_000);
  }

  private async refreshHealth(): Promise<void> {
    try {
      // Use /health directly — /status endpoint does not exist on the daemon
      const h = await getHealth();
      this.healthStatus = h.status;
      this.daemonVersion = h.version;
    } catch {
      this.healthStatus = "error";
    }
  }

  private async refreshSessions(): Promise<void> {
    try {
      this.sessions = await listSessions();
      if (this.sessions.length > 0 && !this.selectedSessionId) {
        this.selectedSessionId = this.sessions[0].id;
      }
    } catch {
      // daemon not running; sessions stay empty
    }
  }

  private connectStream(sessionId?: string): void {
    this.stream?.close();
    const url = buildEventStreamUrl(sessionId || undefined); // global if no session
    this.stream = new EventStreamManager(url, {
      onStateChange: (s) => {
        this.streamState = s;
        this.requestUpdate();
      },
    });
    this.stream.connect();
    // Force child panels to pick up new stream reference
    this.requestUpdate();
  }

  private selectTab(tab: Tab): void {
    this.activeTab = tab;
    localStorage.setItem(TAB_STORAGE_KEY, tab);
  }

  private onSessionChange(e: Event): void {
    const id = (e.target as HTMLSelectElement).value;
    this.selectedSessionId = id;
    if (id) {
      localStorage.setItem(SESSION_STORAGE_KEY, id);
    } else {
      localStorage.removeItem(SESSION_STORAGE_KEY);
    }
    // Reconnect SSE filtered to the selected session (or global if none)
    this.connectStream(id || undefined);
  }

  override render() {
    return html`
      <header>
        <div class="logo">CassiCore <span>Observatory</span></div>

        <nav>
          ${TABS.map(
            (t) => html`
              <button
                class=${t.id === this.activeTab ? "active" : ""}
                @click=${() => this.selectTab(t.id)}
                title="Switch to ${t.label} (${t.key})"
              >
                <span>${t.icon}</span> ${t.label}
                <span class="kbd">${t.key}</span>
              </button>
            `
          )}
        </nav>

        <div class="spacer"></div>

        ${this.sessions.length > 0
          ? html`
              <select
                class="session-select"
                .value=${this.selectedSessionId}
                @change=${this.onSessionChange}
              >
                <option value="">All sessions</option>
                ${this.sessions.map(
                  (s) => html`<option value=${s.id}>${s.id.slice(0, 8)}… (${s.channelId})</option>`
                )}
              </select>
            `
          : nothing}

        <span class="stream-status ${this.streamState}">${this.streamState}</span>

        <div class="health-badge">
          <span class="dot ${this.healthStatus === "ok" ? "ok" : this.healthStatus === "degraded" ? "degraded" : this.healthStatus === "error" ? "error" : ""}"></span>
          ${this.healthStatus === "unknown" ? "connecting…" : this.healthStatus}
          ${this.daemonVersion ? html`<span style="color:var(--color-text-muted,#6b6b8a)">v${this.daemonVersion}</span>` : nothing}
        </div>
      </header>

      <main>
        <div class="panel ${this.activeTab === "events" ? "active" : ""}">
          <event-stream-panel
            .stream=${this.stream}
            .sessionId=${this.selectedSessionId}
          ></event-stream-panel>
        </div>

        <div class="panel ${this.activeTab === "topology" ? "active" : ""}">
          <split-pane direction="horizontal" storageKey="topology" ratio="0.65">
            <topology-panel slot="start" .stream=${this.stream}></topology-panel>
            <event-log slot="end" .stream=${this.stream} maxEvents="200"></event-log>
          </split-pane>
        </div>

        <div class="panel ${this.activeTab === "cognition" ? "active" : ""}">
          <cognition-panel
            .stream=${this.stream}
            .sessionId=${this.selectedSessionId}
          ></cognition-panel>
        </div>

        <div class="panel ${this.activeTab === "providers" ? "active" : ""}">
          <providers-panel></providers-panel>
        </div>

        <div class="panel ${this.activeTab === "sessions" ? "active" : ""}">
          <sessions-panel></sessions-panel>
        </div>

        <div class="panel ${this.activeTab === "memory" ? "active" : ""}">
          <memory-panel .stream=${this.stream}></memory-panel>
        </div>
      </main>
    `;
  }
}

declare global {
  interface HTMLElementTagNameMap {
    "observatory-app": ObservatoryApp;
  }
}
