/**
 * providers-panel
 *
 * Shows live provider status (health, models) and usage metrics.
 * Polls on connect and refreshes every 30s or on manual click.
 */

import { LitElement, html, css, nothing } from "lit";
import { customElement, state } from "lit/decorators.js";
import { listProviders, getProviderMetrics } from "../api/observatory-client.js";
import type { Provider, ProviderMetrics } from "../api/observatory-client.js";
import "../components/provider-metrics-chart.js";

@customElement("providers-panel")
export class ProvidersPanel extends LitElement {
  static override styles = css`
    :host {
      display: flex;
      flex-direction: column;
      height: 100%;
      overflow: hidden;
    }

    .toolbar {
      display: flex;
      align-items: center;
      gap: 0.75rem;
      padding: 0.5rem 1rem;
      border-bottom: 1px solid var(--color-border, #2a2a3d);
      flex-shrink: 0;
    }

    .toolbar h2 {
      margin: 0;
      font-size: 0.85rem;
      font-weight: 600;
      color: var(--color-text, #e2e2f0);
    }

    .refresh-btn {
      margin-left: auto;
      background: var(--color-surface-3, #24243a);
      border: 1px solid var(--color-border, #2a2a3d);
      color: var(--color-text, #e2e2f0);
      font-size: 0.75rem;
      padding: 0.2rem 0.6rem;
      border-radius: 4px;
      cursor: pointer;
    }
    .refresh-btn:hover { background: var(--color-surface-4, #2e2e46); }

    .updated {
      font-size: 0.68rem;
      color: var(--color-text-muted, #6b6b8a);
    }

    .body {
      flex: 1;
      display: flex;
      flex-direction: column;
      overflow: hidden;
      gap: 0;
    }

    /* Provider cards */
    .provider-grid {
      display: flex;
      flex-wrap: wrap;
      gap: 0.5rem;
      padding: 0.75rem 1rem;
      border-bottom: 1px solid var(--color-border, #2a2a3d);
      flex-shrink: 0;
    }

    .provider-card {
      background: var(--color-surface-2, #1a1a23);
      border: 1px solid var(--color-border, #2a2a3d);
      border-radius: 6px;
      padding: 0.5rem 0.75rem;
      min-width: 160px;
    }

    .provider-card .name {
      font-size: 0.8rem;
      font-weight: 600;
      color: var(--color-text, #e2e2f0);
      margin-bottom: 0.2rem;
    }

    .provider-card .status {
      font-size: 0.68rem;
      display: flex;
      align-items: center;
      gap: 0.3rem;
      margin-bottom: 0.25rem;
    }

    .dot {
      width: 6px;
      height: 6px;
      border-radius: 50%;
      background: var(--color-text-muted, #6b6b8a);
      flex-shrink: 0;
    }
    .dot.healthy  { background: var(--color-green,  #22c55e); }
    .dot.degraded { background: var(--color-yellow, #eab308); }
    .dot.unavailable { background: var(--color-red, #ef4444); }

    .provider-card .models {
      font-size: 0.65rem;
      color: var(--color-text-muted, #6b6b8a);
      overflow: hidden;
      text-overflow: ellipsis;
      white-space: nowrap;
      max-width: 220px;
    }

    /* Metrics chart */
    .chart-section {
      flex: 1;
      min-height: 0;
      padding: 0.5rem 1rem;
      display: flex;
      flex-direction: column;
    }

    .section-label {
      font-size: 0.68rem;
      font-weight: 600;
      text-transform: uppercase;
      letter-spacing: 0.08em;
      color: var(--color-text-muted, #6b6b8a);
      margin-bottom: 0.25rem;
      flex-shrink: 0;
    }

    provider-metrics-chart {
      flex: 1;
      min-height: 0;
    }

    .empty {
      flex: 1;
      display: flex;
      flex-direction: column;
      align-items: center;
      justify-content: center;
      gap: 0.5rem;
      color: var(--color-text-muted, #6b6b8a);
      font-size: 0.82rem;
    }
  `;

  @state() private providers: Provider[] = [];
  @state() private metrics: ProviderMetrics[] = [];
  @state() private loading = true;
  @state() private updatedAgo = 0;

  private pollTimer: ReturnType<typeof setInterval> | null = null;
  private tickTimer: ReturnType<typeof setInterval> | null = null;
  private lastFetch = 0;

  override connectedCallback(): void {
    super.connectedCallback();
    this.fetchAll();
    this.pollTimer = setInterval(() => this.fetchAll(), 30_000);
    this.tickTimer = setInterval(() => {
      this.updatedAgo = this.lastFetch
        ? Math.round((Date.now() - this.lastFetch) / 1000)
        : 0;
    }, 1000);
  }

  override disconnectedCallback(): void {
    super.disconnectedCallback();
    if (this.pollTimer) clearInterval(this.pollTimer);
    if (this.tickTimer) clearInterval(this.tickTimer);
  }

  private async fetchAll(): Promise<void> {
    try {
      const [providers, metrics] = await Promise.all([
        listProviders(),
        getProviderMetrics(),
      ]);
      this.providers = providers;
      this.metrics = metrics;
      this.lastFetch = Date.now();
      this.updatedAgo = 0;
    } catch {
      // Daemon may be offline; keep stale data
    } finally {
      this.loading = false;
    }
  }

  override render() {
    return html`
      <div class="toolbar">
        <h2>Provider Status</h2>
        <span class="updated">
          ${this.loading
            ? "loading…"
            : this.lastFetch
              ? `updated ${this.updatedAgo}s ago`
              : ""}
        </span>
        <button class="refresh-btn" @click=${() => this.fetchAll()}>↻ Refresh</button>
      </div>

      <div class="body">
        ${this.providers.length > 0
          ? html`
              <div class="provider-grid">
                ${this.providers.map(
                  (p) => html`
                    <div class="provider-card">
                      <div class="name">${p.name}</div>
                      <div class="status">
                        <span class="dot ${p.status}"></span>
                        <span>${p.status}</span>
                      </div>
                      <div class="models" title=${(p.models ?? []).join(", ")}>
                        ${(p.models ?? []).join(", ") || p.defaultModel || ""}
                      </div>
                    </div>
                  `
                )}
              </div>
            `
          : nothing}

        <div class="chart-section">
          <div class="section-label">Usage Metrics</div>
          ${this.loading && this.providers.length === 0
            ? html`<div class="empty"><span>Loading…</span></div>`
            : html`<provider-metrics-chart .metrics=${this.metrics}></provider-metrics-chart>`}
        </div>
      </div>
    `;
  }
}

declare global {
  interface HTMLElementTagNameMap {
    "providers-panel": ProvidersPanel;
  }
}
