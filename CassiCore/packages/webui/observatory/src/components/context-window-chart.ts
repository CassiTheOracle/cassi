/**
 * context-window-chart
 *
 * ECharts horizontal stacked-bar showing a single session's context window:
 *   - Each segment = one message role (system / user / assistant / tool)
 *   - Total bar width = maxTokens; filled portion = totalTokens
 *   - Compacted messages rendered with a hatched/dimmed style via opacity
 *
 * Accepts a `snapshot` property of type ContextWindowSnapshot.
 * When `sessionId` changes the component fetches a fresh snapshot and
 * also subscribes to the SSE context_window_snapshot stream.
 */

import { LitElement, html, css, nothing } from "lit";
import { customElement, property, state } from "lit/decorators.js";
import * as echarts from "echarts/core";
import { BarChart } from "echarts/charts";
import {
  GridComponent,
  TooltipComponent,
  LegendComponent,
} from "echarts/components";
import { CanvasRenderer } from "echarts/renderers";
import type { EChartsType } from "echarts/core";
import {
  getContextWindow,
  buildContextWindowStreamUrl,
  type ContextWindowSnapshot,
} from "../api/observatory-client.js";

echarts.use([BarChart, GridComponent, TooltipComponent, LegendComponent, CanvasRenderer]);

const ROLE_COLOR: Record<string, string> = {
  system: "#6366f1",
  user: "#3b82f6",
  assistant: "#22c55e",
  tool: "#f59e0b",
  other: "#64748b",
};

@customElement("context-window-chart")
export class ContextWindowChart extends LitElement {
  static override styles = css`
    :host {
      display: flex;
      flex-direction: column;
      height: 100%;
      min-height: 160px;
    }

    .header {
      display: flex;
      align-items: center;
      gap: 0.5rem;
      padding: 0.4rem 0.5rem 0.2rem;
      flex-shrink: 0;
    }

    .chart-title {
      font-size: 0.68rem;
      font-weight: 600;
      text-transform: uppercase;
      letter-spacing: 0.08em;
      color: var(--color-text-muted, #6b6b8a);
    }

    .util-badge {
      font-size: 0.68rem;
      font-weight: 700;
      padding: 0.1rem 0.35rem;
      border-radius: 3px;
      background: var(--color-surface-3, #24243a);
      color: #e2e2f0;
    }
    .util-badge.warn { color: #eab308; }
    .util-badge.crit { color: #ef4444; }

    #chart {
      flex: 1;
      min-height: 0;
    }

    .empty {
      flex: 1;
      display: flex;
      align-items: center;
      justify-content: center;
      font-size: 0.78rem;
      color: var(--color-text-muted, #6b6b8a);
    }
  `;

  @property() sessionId: string = "";

  @state() private snapshot: ContextWindowSnapshot | null = null;
  @state() private loading = false;

  private chart: EChartsType | null = null;
  private ro: ResizeObserver | null = null;
  private es: EventSource | null = null;

  override firstUpdated(): void {
    this.initChart();
    if (this.sessionId) {
      this.fetchAndSubscribe();
    }
  }

  override willUpdate(changed: Map<string, unknown>): void {
    // Reset snapshot synchronously when sessionId changes so it's batched into
    // the same render cycle — avoids Lit's "state changed in updated()" warning.
    if (changed.has("sessionId")) {
      this.snapshot = null;
      this.loading = !!this.sessionId;
    }
  }

  override updated(changed: Map<string, unknown>): void {
    if (changed.has("sessionId")) {
      this.closeStream();
      if (this.sessionId) this.fetchAndSubscribe();
      else if (this.chart) this.chart.clear();
    }
    if (changed.has("snapshot")) {
      this.renderChart();
    }
  }

  override disconnectedCallback(): void {
    super.disconnectedCallback();
    this.closeStream();
    this.ro?.disconnect();
    this.chart?.dispose();
    this.chart = null;
  }

  private initChart(): void {
    const el = this.shadowRoot?.getElementById("chart");
    if (!el) return;

    const doInit = () => {
      this.chart = echarts.init(el, null, { renderer: "canvas" });
      // Persistent resize observer for layout changes after init
      this.ro = new ResizeObserver(() => this.chart?.resize());
      this.ro.observe(el);
      // Render any snapshot that arrived before the chart was ready
      if (this.snapshot) this.renderChart();
    };

    // If the element already has dimensions (tab is visible), init immediately.
    // Otherwise defer until it becomes visible via ResizeObserver.
    if (el.offsetWidth > 0 && el.offsetHeight > 0) {
      doInit();
    } else {
      const sentinel = new ResizeObserver((entries) => {
        const entry = entries[0];
        if (entry && entry.contentRect.width > 0 && entry.contentRect.height > 0) {
          sentinel.disconnect();
          doInit();
        }
      });
      sentinel.observe(el);
      // Keep a ref so we can clean up if the element is removed before init fires
      this.ro = sentinel;
    }
  }

  private async fetchAndSubscribe(): Promise<void> {
    // loading is set in willUpdate() to avoid "state changed in updated()" warning
    try {
      this.snapshot = await getContextWindow(this.sessionId);
    } catch {
      // daemon offline or no snapshot yet — stay null
    } finally {
      this.loading = false;
    }

    // Subscribe to live updates
    this.closeStream();
    const url = buildContextWindowStreamUrl(this.sessionId);
    this.es = new EventSource(url);
    this.es.addEventListener("context_window_snapshot", (e: MessageEvent) => {
      try {
        this.snapshot = JSON.parse(e.data) as ContextWindowSnapshot;
      } catch { /* ignore */ }
    });
    this.es.onerror = () => {
      // SSE errors are expected when daemon is offline — ignore silently
    };
  }

  private closeStream(): void {
    this.es?.close();
    this.es = null;
  }

  private renderChart(): void {
    if (!this.chart || !this.snapshot) return;

    const snap = this.snapshot;
    const maxTokens = snap.contextWindow || 1;

    // Aggregate by role using character count as proxy for tokens
    // (server doesn't provide per-message token counts)
    const roleTotals: Record<string, number> = {};
    const messages = snap.messages ?? [];
    for (const msg of messages) {
      const role = msg.role in ROLE_COLOR ? msg.role : "other";
      roleTotals[role] = (roleTotals[role] ?? 0) + (msg.content?.length ?? 0);
    }

    // Scale from chars to estimated tokens (proportional to estimatedTokens total)
    const totalChars = Object.values(roleTotals).reduce((a, b) => a + b, 0) || 1;
    const scale = snap.estimatedTokens / totalChars;

    // Free space
    const used = snap.estimatedTokens;
    const free = Math.max(0, maxTokens - used);

    const roles = Object.keys(ROLE_COLOR);
    const series: object[] = [];

    for (const role of roles) {
      const charCount = roleTotals[role] ?? 0;
      if (charCount > 0) {
        const estTokens = Math.round(charCount * scale);
        series.push({
          name: role,
          type: "bar",
          stack: "ctx",
          data: [estTokens],
          itemStyle: { color: ROLE_COLOR[role] },
          barMaxWidth: 28,
        });
      }
    }

    // Free space indicator
    if (free > 0) {
      series.push({
        name: "free",
        type: "bar",
        stack: "ctx",
        data: [free],
        itemStyle: { color: "#1a1a23", borderColor: "#2a2a3d", borderWidth: 1 },
        barMaxWidth: 28,
      });
    }

    this.chart.setOption(
      {
        backgroundColor: "transparent",
        textStyle: { color: "#e2e2f0", fontFamily: "Inter, ui-sans-serif, sans-serif", fontSize: 10 },
        tooltip: {
          trigger: "item",
          backgroundColor: "#1a1a23",
          borderColor: "#2a2a3d",
          textStyle: { color: "#e2e2f0", fontSize: 11 },
          formatter: (p: any) =>
            `<div style="font-size:11px"><span style="color:${p.color}">${p.seriesName}</span>: <strong>${p.value.toLocaleString()} tok</strong></div>`,
        },
        legend: {
          show: false,
        },
        grid: { left: 8, right: 8, top: 8, bottom: 8, containLabel: false },
        xAxis: {
          type: "value",
          max: maxTokens,
          show: false,
        },
        yAxis: {
          type: "category",
          data: [""],
          show: false,
        },
        series,
      },
      true
    );
  }

  private get utilizationPct(): number {
    return this.snapshot?.percentUsed ?? 0;
  }

  private get utilClass(): string {
    const p = this.utilizationPct;
    if (p >= 90) return "crit";
    if (p >= 70) return "warn";
    return "";
  }

  override render() {
    const hasData = this.snapshot !== null;
    const noSession = !this.sessionId;

    return html`
      <div class="header">
        <span class="chart-title">Context Window</span>
        ${hasData
          ? html`
              <span class="util-badge ${this.utilClass}">${this.utilizationPct.toFixed(1)}%</span>
              <span style="font-size:0.65rem;color:var(--color-text-muted,#6b6b8a)">
                ${(this.snapshot!.estimatedTokens).toLocaleString()} /
                ${(this.snapshot!.contextWindow).toLocaleString()} tok
              </span>
            `
          : nothing}
      </div>

      ${noSession
        ? html`<div class="empty">Select a session to view context window</div>`
        : !hasData && !this.loading
          ? html`<div id="chart" style="display:none"></div><div class="empty">No context data yet</div>`
          : html`<div id="chart"></div>`}
    `;
  }
}

declare global {
  interface HTMLElementTagNameMap {
    "context-window-chart": ContextWindowChart;
  }
}
