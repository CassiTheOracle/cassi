/**
 * provider-metrics-chart
 *
 * ECharts grouped-bar + line combo chart showing per-provider:
 *   - Total requests (bar)
 *   - Avg latency ms (line, secondary y-axis)
 *   - Success rate % (bar, secondary y-axis)
 *
 * Updates whenever `metrics` property is set.
 */

import { LitElement, html, css, nothing } from "lit";
import { customElement, property, state } from "lit/decorators.js";
import * as echarts from "echarts/core";
import { BarChart, LineChart } from "echarts/charts";
import {
  GridComponent,
  TooltipComponent,
  LegendComponent,
} from "echarts/components";
import { CanvasRenderer } from "echarts/renderers";
import type { EChartsType } from "echarts/core";
import type { ProviderMetrics } from "../api/observatory-client.js";

echarts.use([
  BarChart,
  LineChart,
  GridComponent,
  TooltipComponent,
  LegendComponent,
  CanvasRenderer,
]);

@customElement("provider-metrics-chart")
export class ProviderMetricsChart extends LitElement {
  static override styles = css`
    :host {
      display: flex;
      flex-direction: column;
      height: 100%;
      min-height: 200px;
      position: relative;
    }

    .chart-title {
      font-size: 0.68rem;
      font-weight: 600;
      text-transform: uppercase;
      letter-spacing: 0.08em;
      color: var(--color-text-muted, #6b6b8a);
      padding: 0.4rem 0.5rem 0.2rem;
      flex-shrink: 0;
    }

    #chart {
      flex: 1;
      min-height: 0;
    }

    .empty {
      position: absolute;
      inset: 0;
      top: 24px; /* below .chart-title */
      display: flex;
      align-items: center;
      justify-content: center;
      font-size: 0.78rem;
      color: var(--color-text-muted, #6b6b8a);
      pointer-events: none;
    }
  `;

  @property({ attribute: false }) metrics: ProviderMetrics[] = [];

  private get hasData(): boolean { return this.metrics.length > 0; }

  private chart: EChartsType | null = null;
  private ro: ResizeObserver | null = null;

  override firstUpdated(): void {
    this.initChart();
    // updateChart() is called from initChart() once dimensions are ready
  }

  override updated(changed: Map<string, unknown>): void {
    if (changed.has("metrics")) {
      this.updateChart();
    }
  }

  override disconnectedCallback(): void {
    super.disconnectedCallback();
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
      this.updateChart();
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

  private updateChart(): void {
    if (!this.chart) return;

    const data = this.metrics;

    if (!this.hasData) {
      this.chart.clear();
      return;
    }

    const providers = data.map((m) => m.providerId);
    const requests = data.map((m) => m.totalRequests);
    const errors = data.map((m) => m.errors);
    // successRate: if value is <= 1, it's a 0-1 ratio → multiply by 100 for percentage
    const successRates = data.map((m) => {
      const raw = m.successRate;
      const pct = raw <= 1 ? raw * 100 : raw;
      return Math.round(pct * 100) / 100;
    });
    const avgLatencies = data.map((m) => Math.round(m.avgLatencyMs));
    const p95Latencies = data.map((m) => Math.round(m.p95LatencyMs));

    this.chart.setOption(
      {
        backgroundColor: "transparent",
        textStyle: { color: "#e2e2f0", fontFamily: "Inter, ui-sans-serif, sans-serif", fontSize: 10 },
        tooltip: {
          trigger: "axis",
          backgroundColor: "#1a1a23",
          borderColor: "#2a2a3d",
          textStyle: { color: "#e2e2f0", fontSize: 11 },
          axisPointer: { type: "shadow" },
          formatter: (params: any[]) => {
            const name = params[0]?.name ?? "";
            const rows = params
              .map(
                (p: any) =>
                  `<div style="display:flex;justify-content:space-between;gap:12px">` +
                  `<span style="color:${p.color}">${p.seriesName}</span>` +
                  `<strong>${p.value}</strong></div>`
              )
              .join("");
            return `<div style="font-size:11px"><strong style="color:#6366f1">${name}</strong>${rows}</div>`;
          },
        },
        legend: {
          data: ["Requests", "Errors", "Avg Latency (ms)", "p95 Latency (ms)", "Success %"],
          textStyle: { color: "#6b6b8a", fontSize: 10 },
          top: 4,
          right: 8,
          itemWidth: 12,
          itemHeight: 8,
        },
        grid: { left: 48, right: 64, top: 36, bottom: 28, containLabel: false },
        xAxis: {
          type: "category",
          data: providers,
          axisLine: { lineStyle: { color: "#2a2a3d" } },
          axisLabel: { color: "#6b6b8a", fontSize: 10 },
          splitLine: { show: false },
        },
        yAxis: [
          {
            type: "value",
            name: "count",
            nameTextStyle: { color: "#6b6b8a", fontSize: 9 },
            axisLine: { lineStyle: { color: "#2a2a3d" } },
            axisLabel: { color: "#6b6b8a", fontSize: 9 },
            splitLine: { lineStyle: { color: "#1f1f2e" } },
          },
          {
            type: "value",
            name: "ms / %",
            nameTextStyle: { color: "#6b6b8a", fontSize: 9 },
            axisLine: { lineStyle: { color: "#2a2a3d" } },
            axisLabel: { color: "#6b6b8a", fontSize: 9 },
            splitLine: { show: false },
          },
        ],
        series: [
          {
            name: "Requests",
            type: "bar",
            yAxisIndex: 0,
            data: requests,
            barMaxWidth: 28,
            itemStyle: { color: "#6366f1", borderRadius: [2, 2, 0, 0] },
          },
          {
            name: "Errors",
            type: "bar",
            yAxisIndex: 0,
            data: errors,
            barMaxWidth: 28,
            itemStyle: { color: "#ef4444", borderRadius: [2, 2, 0, 0] },
          },
          {
            name: "Avg Latency (ms)",
            type: "line",
            yAxisIndex: 1,
            data: avgLatencies,
            smooth: true,
            symbol: "circle",
            symbolSize: 5,
            lineStyle: { color: "#f59e0b", width: 1.5 },
            itemStyle: { color: "#f59e0b" },
          },
          {
            name: "p95 Latency (ms)",
            type: "line",
            yAxisIndex: 1,
            data: p95Latencies,
            smooth: true,
            symbol: "circle",
            symbolSize: 4,
            lineStyle: { color: "#fb923c", width: 1.5, type: "dashed" },
            itemStyle: { color: "#fb923c" },
          },
          {
            name: "Success %",
            type: "line",
            yAxisIndex: 1,
            data: successRates,
            smooth: true,
            symbol: "diamond",
            symbolSize: 5,
            lineStyle: { color: "#22c55e", width: 1.5 },
            itemStyle: { color: "#22c55e" },
          },
        ],
      },
      true
    );
  }

  override render() {
    return html`
      <div class="chart-title">Provider Metrics</div>
      <div id="chart"></div>
      ${!this.hasData
        ? html`<div class="empty">No provider data — daemon offline or no activity yet</div>`
        : nothing}
    `;
  }
}

declare global {
  interface HTMLElementTagNameMap {
    "provider-metrics-chart": ProviderMetricsChart;
  }
}
