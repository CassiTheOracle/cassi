import { LitElement, html, css } from "lit";
import { customElement, property } from "lit/decorators.js";
import * as echarts from "echarts";
import type { EventStreamManager } from "../api/event-stream.js";

const WINDOW_SECS = 60; // show last 60 seconds
const BUCKET_SECS = 5;  // 5-second buckets
const NUM_BUCKETS = WINDOW_SECS / BUCKET_SECS;

// Event categories for coloring
const CATEGORY_MAP: Record<string, string> = {
  "turn": "#6366f1",
  "provider": "#22c55e",
  "subagent": "#f59e0b",
  "agent": "#ec4899",
  "team": "#14b8a6",
  "intelligence": "#8b5cf6",
  "autonomy": "#f97316",
  "tool": "#06b6d4",
  "plugin": "#a3e635",
  "session": "#64748b",
  "other": "#4b5563",
};

function categorize(eventType: string): string {
  const prefix = eventType.split(":")[0];
  return CATEGORY_MAP[prefix] ?? CATEGORY_MAP["other"]!;
}

interface Bucket {
  ts: number; // epoch ms of bucket start
  counts: Record<string, number>;
}

/**
 * @dep callers: updateChart (webui/observatory/src/components/event-rate-chart.ts), attachStream (webui/observatory/src/components/event-rate-chart.ts)
 * @dep module: Components
 * @dep risk: LOW | 2 callers, 0 flows, 1 module
 */

function makeBucket(ts: number): Bucket {
  return { ts, counts: {} };
}

/**
 * @dep callers: updateChart (webui/observatory/src/components/event-rate-chart.ts), attachStream (webui/observatory/src/components/event-rate-chart.ts)
 * @dep module: Components
 * @dep risk: LOW | 2 callers, 0 flows, 1 module
 */

function bucketKey(ts: number): number {
  return Math.floor(ts / (BUCKET_SECS * 1000)) * (BUCKET_SECS * 1000);
}

@customElement("event-rate-chart")
export class EventRateChart extends LitElement {
  static override styles = css`
    :host {
      display: block;
      flex: 1;
      min-height: 0;
    }
    #chart {
      width: 100%;
      height: 100%;
    }
  `;

  @property({ attribute: false }) stream: EventStreamManager | null = null;

  private chart: echarts.ECharts | null = null;
  private buckets: Map<number, Bucket> = new Map();
  private unsubscribe: (() => void) | null = null;
  private rafTimer: number | null = null;
  private dirty = false;

  override firstUpdated(): void {
    const el = this.shadowRoot?.getElementById("chart");
    if (!el) return;

    this.chart = echarts.init(el, "dark", { renderer: "canvas" });
    this.chart.setOption(this.buildOption([]));

    new ResizeObserver(() => this.chart?.resize()).observe(el);

    this.startTicker();
  }

  override updated(changed: Map<string, unknown>): void {
    if (changed.has("stream")) {
      this.attachStream();
    }
  }

  override disconnectedCallback(): void {
    super.disconnectedCallback();
    this.unsubscribe?.();
    if (this.rafTimer !== null) cancelAnimationFrame(this.rafTimer);
    this.chart?.dispose();
  }

  private attachStream(): void {
    this.unsubscribe?.();
    if (!this.stream) return;

    this.unsubscribe = this.stream.onAll((data) => {
      const d = data as { type?: string };
      if (!d.type) return;
      const bk = bucketKey(Date.now());
      if (!this.buckets.has(bk)) this.buckets.set(bk, makeBucket(bk));
      const bucket = this.buckets.get(bk)!;
      const cat = d.type.split(":")[0] ?? "other";
      bucket.counts[cat] = (bucket.counts[cat] ?? 0) + 1;
      this.dirty = true;
    });
  }

  private startTicker(): void {
    const tick = () => {
      this.rafTimer = requestAnimationFrame(tick);
      if (this.dirty) {
        this.dirty = false;
        this.updateChart();
      }
    };
    // Also update on a 1s interval to advance time axis
    setInterval(() => { this.dirty = true; }, 1000);
    this.rafTimer = requestAnimationFrame(tick);
  }

  private updateChart(): void {
    if (!this.chart) return;
    const now = Date.now();
    const cutoff = now - WINDOW_SECS * 1000;

    // Prune old buckets
    for (const [k] of this.buckets) {
      if (k < cutoff) this.buckets.delete(k);
    }

    // Build series data
    const categories = new Set<string>();
    for (const [, b] of this.buckets) {
      Object.keys(b.counts).forEach((c) => categories.add(c));
    }

    // Fill in empty buckets for the window
    const allBuckets: Bucket[] = [];
    for (let t = bucketKey(cutoff); t <= bucketKey(now); t += BUCKET_SECS * 1000) {
      allBuckets.push(this.buckets.get(t) ?? makeBucket(t));
    }

    const xData = allBuckets.map((b) => {
      const d = new Date(b.ts);
      return `${d.getMinutes().toString().padStart(2, "0")}:${d.getSeconds().toString().padStart(2, "0")}`;
    });

    const series = Array.from(categories).map((cat) => ({
      name: cat,
      type: "line" as const,
      stack: "total",
      smooth: true,
      symbol: "none",
      lineStyle: { width: 1.5, color: CATEGORY_MAP[cat] ?? CATEGORY_MAP["other"] },
      areaStyle: { color: (CATEGORY_MAP[cat] ?? CATEGORY_MAP["other"]) + "33" },
      itemStyle: { color: CATEGORY_MAP[cat] ?? CATEGORY_MAP["other"] },
      data: allBuckets.map((b) => b.counts[cat] ?? 0),
    }));

    this.chart.setOption({ xAxis: { data: xData }, series }, { replaceMerge: ["series"] });
  }

  private buildOption(series: echarts.EChartsOption["series"]): echarts.EChartsOption {
    return {
      backgroundColor: "transparent",
      grid: { top: 10, right: 16, bottom: 24, left: 40, containLabel: false },
      xAxis: {
        type: "category",
        data: [],
        axisLine: { lineStyle: { color: "#2a2a3d" } },
        axisLabel: { color: "#6b6b8a", fontSize: 10 },
        splitLine: { show: false },
      },
      yAxis: {
        type: "value",
        minInterval: 1,
        axisLine: { show: false },
        axisLabel: { color: "#6b6b8a", fontSize: 10 },
        splitLine: { lineStyle: { color: "#2a2a3d", type: "dashed" } },
      },
      tooltip: {
        trigger: "axis",
        backgroundColor: "#1a1a23",
        borderColor: "#2a2a3d",
        textStyle: { color: "#e2e2f0", fontSize: 11 },
        axisPointer: { lineStyle: { color: "#6366f1" } },
      },
      legend: {
        show: true,
        bottom: 0,
        textStyle: { color: "#6b6b8a", fontSize: 10 },
        itemHeight: 8,
      },
      series,
    };
  }

  override render() {
    return html`<div id="chart"></div>`;
  }
}

declare global {
  interface HTMLElementTagNameMap {
    "event-rate-chart": EventRateChart;
  }
}
