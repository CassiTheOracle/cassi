import { LitElement, html, css } from "lit";
import { customElement, property, state } from "lit/decorators.js";
import type { EventStreamManager } from "../api/event-stream.js";
import "../components/event-rate-chart.js";
import "../components/event-log.js";

@customElement("event-stream-panel")
export class EventStreamPanel extends LitElement {
  static override styles = css`
    :host {
      display: flex;
      flex-direction: column;
      height: 100%;
      overflow: hidden;
      padding: 0.75rem;
      gap: 0.75rem;
      background: var(--color-surface, #0f0f12);
    }

    .top-row {
      display: flex;
      gap: 0.75rem;
      height: 220px;
      flex-shrink: 0;
    }

    .chart-wrap {
      flex: 1;
      min-width: 0;
      background: var(--color-surface-2, #1a1a23);
      border: 1px solid var(--color-border, #2a2a3d);
      border-radius: 8px;
      overflow: hidden;
      display: flex;
      flex-direction: column;
    }

    .card-header {
      padding: 0.5rem 0.75rem;
      font-size: 0.72rem;
      font-weight: 600;
      color: var(--color-text-muted, #6b6b8a);
      text-transform: uppercase;
      letter-spacing: 0.08em;
      border-bottom: 1px solid var(--color-border, #2a2a3d);
      flex-shrink: 0;
    }

    .log-wrap {
      flex: 1;
      min-height: 0;
      background: var(--color-surface-2, #1a1a23);
      border: 1px solid var(--color-border, #2a2a3d);
      border-radius: 8px;
      overflow: hidden;
      display: flex;
      flex-direction: column;
    }

    .log-header {
      display: flex;
      align-items: center;
      justify-content: space-between;
      padding: 0.5rem 0.75rem;
      border-bottom: 1px solid var(--color-border, #2a2a3d);
      flex-shrink: 0;
    }

    .log-title {
      font-size: 0.72rem;
      font-weight: 600;
      color: var(--color-text-muted, #6b6b8a);
      text-transform: uppercase;
      letter-spacing: 0.08em;
    }

    .filter-input {
      background: var(--color-surface-3, #24243a);
      border: 1px solid var(--color-border, #2a2a3d);
      color: var(--color-text, #e2e2f0);
      font-size: 0.75rem;
      padding: 0.2rem 0.5rem;
      border-radius: 4px;
      outline: none;
      width: 180px;
    }

    .filter-input::placeholder {
      color: var(--color-text-muted, #6b6b8a);
    }

    event-log {
      flex: 1;
      min-height: 0;
    }
  `;

  @property({ attribute: false }) stream: EventStreamManager | null = null;
  @property({ type: String }) sessionId: string = "";
  @state() private filter: string = "";

  override render() {
    return html`
      <div class="top-row">
        <div class="chart-wrap">
          <div class="card-header">Event Rate (events / 5s)</div>
          <event-rate-chart .stream=${this.stream}></event-rate-chart>
        </div>
      </div>

      <div class="log-wrap">
        <div class="log-header">
          <span class="log-title">Live Event Log</span>
          <input
            class="filter-input"
            type="text"
            placeholder="Filter by type…"
            .value=${this.filter}
            @input=${(e: InputEvent) => {
              this.filter = (e.target as HTMLInputElement).value;
            }}
          />
        </div>
        <event-log .stream=${this.stream} .filter=${this.filter}></event-log>
      </div>
    `;
  }
}

declare global {
  interface HTMLElementTagNameMap {
    "event-stream-panel": EventStreamPanel;
  }
}
