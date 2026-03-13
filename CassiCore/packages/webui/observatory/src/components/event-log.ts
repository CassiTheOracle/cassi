import { LitElement, html, css, nothing } from "lit";
import { customElement, property, state } from "lit/decorators.js";
import type { EventStreamManager } from "../api/event-stream.js";

const MAX_EVENTS = 500;

// Color per event category prefix
const CATEGORY_COLORS: Record<string, string> = {
  turn: "#6366f1",
  provider: "#22c55e",
  subagent: "#f59e0b",
  agent: "#ec4899",
  team: "#14b8a6",
  intelligence: "#8b5cf6",
  autonomy: "#f97316",
  tool: "#06b6d4",
  plugin: "#a3e635",
  session: "#64748b",
  daemon: "#94a3b8",
  config: "#7dd3fc",
  worker: "#c084fc",
};

function colorForType(type: string): string {
  const prefix = type.split(":")[0] ?? "";
  return CATEGORY_COLORS[prefix] ?? "#4b5563";
}

interface LogEntry {
  id: number;
  timestamp: number;
  type: string;
  sessionId?: string;
  summary: string;
  raw: unknown;
}

let _idSeq = 0;

function summarize(data: Record<string, unknown>): string {
  const skip = new Set(["type", "timestamp"]);
  const parts: string[] = [];
  for (const [k, v] of Object.entries(data)) {
    if (skip.has(k)) continue;
    const str = typeof v === "object" ? JSON.stringify(v) : String(v);
    parts.push(`${k}: ${str.length > 60 ? str.slice(0, 60) + "…" : str}`);
    if (parts.length >= 3) break;
  }
  return parts.join("  ·  ");
}

@customElement("event-log")
export class EventLog extends LitElement {
  static override styles = css`
    :host {
      display: flex;
      flex-direction: column;
      overflow: hidden;
      height: 100%;
    }

    .list {
      flex: 1;
      overflow-y: auto;
      font-family: "JetBrains Mono", "Fira Code", ui-monospace, monospace;
      font-size: 0.7rem;
      line-height: 1.5;
    }

    .row {
      display: grid;
      grid-template-columns: 72px 1fr auto;
      gap: 0.4rem;
      padding: 0.2rem 0.75rem;
      border-bottom: 1px solid var(--color-border, #2a2a3d);
      transition: background 0.1s;
      cursor: default;
      align-items: baseline;
    }

    .row:hover {
      background: var(--color-surface-3, #24243a);
    }

    .ts {
      color: var(--color-text-muted, #6b6b8a);
      font-size: 0.65rem;
      white-space: nowrap;
    }

    .type-badge {
      display: inline-flex;
      align-items: center;
      font-weight: 600;
      font-size: 0.65rem;
      padding: 0.05rem 0.3rem;
      border-radius: 3px;
      white-space: nowrap;
      color: #0f0f12;
    }

    .summary {
      color: var(--color-text-muted, #6b6b8a);
      overflow: hidden;
      text-overflow: ellipsis;
      white-space: nowrap;
    }

    .empty {
      display: flex;
      align-items: center;
      justify-content: center;
      height: 100%;
      color: var(--color-text-muted, #6b6b8a);
      font-size: 0.8rem;
    }
  `;

  @property({ attribute: false }) stream: EventStreamManager | null = null;
  @property({ type: String }) filter: string = "";

  @state() private entries: LogEntry[] = [];

  private unsubscribe: (() => void) | null = null;
  private listEl: Element | null = null;
  private autoScroll = true;

  override updated(changed: Map<string, unknown>): void {
    if (changed.has("stream")) {
      this.attachStream();
    }
  }

  override firstUpdated(): void {
    this.listEl = this.shadowRoot?.querySelector(".list") ?? null;
    this.listEl?.addEventListener("scroll", () => {
      if (!this.listEl) return;
      const { scrollTop, scrollHeight, clientHeight } = this.listEl as HTMLElement;
      this.autoScroll = scrollHeight - scrollTop - clientHeight < 40;
    });
  }

  override disconnectedCallback(): void {
    super.disconnectedCallback();
    this.unsubscribe?.();
  }

  private attachStream(): void {
    this.unsubscribe?.();
    if (!this.stream) return;

    this.unsubscribe = this.stream.onAll((data) => {
      const d = data as Record<string, unknown>;
      const type = (d["type"] as string | undefined) ?? "message";
      const entry: LogEntry = {
        id: _idSeq++,
        timestamp: Date.now(),
        type,
        sessionId: d["sessionId"] as string | undefined,
        summary: summarize(d),
        raw: d,
      };

      this.entries = this.entries.length >= MAX_EVENTS
        ? [...this.entries.slice(-MAX_EVENTS + 1), entry]
        : [...this.entries, entry];
    });
  }

  private formatTime(ts: number): string {
    const d = new Date(ts);
    return `${d.getHours().toString().padStart(2, "0")}:${d.getMinutes().toString().padStart(2, "0")}:${d.getSeconds().toString().padStart(2, "0")}`;
  }

  override render() {
    const lf = this.filter.trim().toLowerCase();
    const visible = lf
      ? this.entries.filter((e) => e.type.toLowerCase().includes(lf))
      : this.entries;

    if (visible.length === 0) {
      return html`<div class="empty">${this.stream ? "Waiting for events…" : "No stream connected"}</div>`;
    }

    // Schedule auto-scroll after render
    this.updateComplete.then(() => {
      if (this.autoScroll && this.listEl) {
        (this.listEl as HTMLElement).scrollTop = (this.listEl as HTMLElement).scrollHeight;
      }
    });

    return html`
      <div class="list">
        ${visible.map(
          (e) => html`
            <div class="row" title=${JSON.stringify(e.raw, null, 2)}>
              <span class="ts">${this.formatTime(e.timestamp)}</span>
              <span class="type-badge" style="background:${colorForType(e.type)}">${e.type}</span>
              <span class="summary">${e.summary || nothing}</span>
            </div>
          `
        )}
      </div>
    `;
  }
}

declare global {
  interface HTMLElementTagNameMap {
    "event-log": EventLog;
  }
}
