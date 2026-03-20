import { LitElement, html, css, nothing } from "lit";
import { customElement, property, state } from "lit/decorators.js";
import cytoscape, { type Core, type NodeSingular, type ElementDefinition } from "cytoscape";
// @ts-ignore — cytoscape-dagre ships no type declarations
import dagre from "cytoscape-dagre";
import type { EventStreamManager } from "../api/event-stream.js";
import {
  listSessions,
  listSubagents,
  listProviders,
  type Session,
  type Subagent,
  type Provider,
} from "../api/observatory-client.js";

cytoscape.use(dagre);

const NODE_COLOR: Record<string, string> = {
  daemon: "#6366f1",
  session: "#3b82f6",
  subagent: "#f59e0b",
  provider: "#22c55e",
  team: "#14b8a6",
};
const STATUS_COLOR: Record<string, string> = {
  active: "#22c55e",
  running: "#22c55e",
  healthy: "#22c55e",
  completed: "#64748b",
  failed: "#ef4444",
  killed: "#ef4444",
  inactive: "#64748b",
  degraded: "#eab308",
  unavailable: "#ef4444",
  error: "#ef4444",
};

const CY_STYLE: NonNullable<cytoscape.CytoscapeOptions["style"]> = [
  {
    selector: "node",
    style: {
      "background-color": "#1a1a23",
      "border-color": "#2a2a3d",
      "border-width": 2,
      color: "#e2e2f0",
      "font-size": "10px",
      "font-family": "Inter, ui-sans-serif, system-ui, sans-serif",
      "text-valign": "bottom",
      "text-halign": "center",
      "text-margin-y": 4,
      "text-wrap": "ellipsis",
      "text-max-width": "100px",
      label: "data(label)",
      width: 36,
      height: 36,
    },
  },
  {
    selector: "node[kind='daemon']",
    style: {
      "background-color": "#6366f1",
      "border-color": "#818cf8",
      shape: "hexagon",
      width: 48,
      height: 48,
      "font-weight": "bold",
      "font-size": "11px",
    },
  },
  {
    selector: "node[kind='session']",
    style: {
      "background-color": "#1e3a5f",
      "border-color": "#3b82f6",
      shape: "round-rectangle",
      width: 52,
      height: 28,
    },
  },
  {
    selector: "node[kind='subagent']",
    style: {
      "background-color": "#2d2000",
      "border-color": "#f59e0b",
      shape: "ellipse",
      width: 30,
      height: 30,
      "font-size": "9px",
    },
  },
  {
    selector: "node[kind='provider']",
    style: {
      "background-color": "#052e16",
      "border-color": "#22c55e",
      shape: "round-rectangle",
      width: 60,
      height: 24,
      "font-size": "9px",
    },
  },
  {
    selector: "node[kind='team']",
    style: {
      "background-color": "#042f2e",
      "border-color": "#14b8a6",
      shape: "diamond",
      width: 38,
      height: 38,
    },
  },
  // Status overlays
  {
    selector: "node[status='completed']",
    style: { opacity: 0.5 },
  },
  {
    selector: "node[status='failed'], node[status='killed'], node[status='error']",
    style: { "border-color": "#ef4444", "border-width": 3 },
  },
  {
    selector: "node[status='active'], node[status='running'], node[status='healthy']",
    style: { "border-width": 2 },
  },
  // Edges
  {
    selector: "edge",
    style: {
      "line-color": "#2a2a3d",
      "target-arrow-color": "#2a2a3d",
      "target-arrow-shape": "triangle",
      "arrow-scale": 0.8,
      "curve-style": "bezier",
      width: 1.5,
      opacity: 0.7,
    },
  },
  {
    selector: "edge[kind='requests']",
    style: {
      "line-color": "#6366f1",
      "target-arrow-color": "#6366f1",
      "line-style": "dashed",
      width: 1.5,
    },
  },
  {
    selector: "edge.active-request",
    style: {
      "line-color": "#22c55e",
      "target-arrow-color": "#22c55e",
      width: 2.5,
      opacity: 1,
    },
  },
  // Selection
  {
    selector: "node:selected",
    style: {
      "border-color": "#e2e2f0",
      "border-width": 3,
    },
  },
  {
    selector: "node:active",
    style: { "overlay-opacity": 0.1 },
  },
];


interface GraphNode extends ElementDefinition {
  data: {
    id: string;
    label: string;
    kind: "daemon" | "session" | "subagent" | "provider" | "team";
    status?: string;
    parent?: string;
  };
}

interface GraphEdge extends ElementDefinition {
  data: {
    id: string;
    source: string;
    target: string;
    kind?: "hosts" | "spawned" | "uses" | "requests";
  };
}


@customElement("topology-panel")
export class TopologyPanel extends LitElement {
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

    .legend {
      display: flex;
      align-items: center;
      gap: 0.75rem;
      margin-left: auto;
      flex-wrap: wrap;
    }

    .legend-item {
      display: flex;
      align-items: center;
      gap: 0.3rem;
      font-size: 0.68rem;
      color: var(--color-text-muted, #6b6b8a);
    }

    .legend-dot {
      width: 8px;
      height: 8px;
      border-radius: 50%;
    }

    .graph-container {
      flex: 1;
      min-height: 0;
      position: relative;
    }

    #cy {
      width: 100%;
      height: 100%;
      position: relative;
    }

    .tooltip {
      position: absolute;
      background: #1a1a23;
      border: 1px solid #2a2a3d;
      border-radius: 6px;
      padding: 0.4rem 0.6rem;
      font-size: 0.72rem;
      color: #e2e2f0;
      pointer-events: none;
      z-index: 10;
      max-width: 220px;
      display: none;
    }

    .tooltip.visible { display: block; }

    .tooltip-type {
      font-weight: 600;
      font-size: 0.65rem;
      text-transform: uppercase;
      letter-spacing: 0.06em;
      margin-bottom: 0.2rem;
    }

    .tooltip-row {
      display: flex;
      gap: 0.4rem;
      color: var(--color-text-muted, #6b6b8a);
    }

    .tooltip-row span:first-child {
      color: var(--color-text-muted, #6b6b8a);
      min-width: 50px;
    }

    .tooltip-row span:last-child {
      color: #e2e2f0;
      overflow: hidden;
      text-overflow: ellipsis;
      white-space: nowrap;
    }

    .loading {
      position: absolute;
      inset: 0;
      display: flex;
      align-items: center;
      justify-content: center;
      color: var(--color-text-muted, #6b6b8a);
      font-size: 0.85rem;
      background: var(--color-surface, #0f0f12);
    }

    .stats {
      font-size: 0.68rem;
      color: var(--color-text-muted, #6b6b8a);
      padding: 0 0.25rem;
    }
  `;

  @property({ attribute: false }) stream: EventStreamManager | null = null;

  @state() private loading = true;
  @state() private nodeCount = 0;
  @state() private edgeCount = 0;
  @state() private tooltipVisible = false;
  @state() private tooltipX = 0;
  @state() private tooltipY = 0;
  @state() private tooltipData: Record<string, string> = {};
  @state() private tooltipKind = "";

  private cy: Core | null = null;
  private unsubs: Array<() => void> = [];
  private layoutTimer: ReturnType<typeof setTimeout> | null = null;
  /** Track active provider requests for edge highlighting */
  private activeRequests = new Map<string, string>(); // requestId → edgeId

  override firstUpdated(): void {
    this.initCytoscape();
    this.loadData();
    // Stream attachment handled by updated() when `stream` property is set
  }

  override updated(changed: Map<string, unknown>): void {
    if (changed.has("stream")) {
      this.detachStream();
      this.attachStream();
    }
  }

  override disconnectedCallback(): void {
    super.disconnectedCallback();
    this.detachStream();
    this.cy?.destroy();
  }


  private initCytoscape(): void {
    const el = this.shadowRoot?.getElementById("cy");
    if (!el) return;

    this.cy = cytoscape({
      container: el,
      style: CY_STYLE,
      layout: { name: "preset" },
      userZoomingEnabled: true,
      userPanningEnabled: true,
      boxSelectionEnabled: false,
      minZoom: 0.2,
      maxZoom: 4,
    });

    new ResizeObserver(() => this.cy?.resize()).observe(el);

    // Tooltip on hover
    this.cy.on("mouseover", "node", (e) => {
      const node = e.target as NodeSingular;
      const pos = e.renderedPosition;
      const d = node.data();
      this.tooltipData = {
        id: d.id,
        status: d.status ?? "—",
        ...(d.task ? { task: String(d.task).slice(0, 80) } : {}),
        ...(d.model ? { model: d.model } : {}),
        ...(d.channelId ? { channel: d.channelId } : {}),
      };
      this.tooltipKind = d.kind ?? "";
      this.tooltipX = pos.x + 12;
      this.tooltipY = pos.y - 8;
      this.tooltipVisible = true;
    });

    this.cy.on("mouseout", "node", () => {
      this.tooltipVisible = false;
    });

    // Fit on double-click background
    this.cy.on("dblclick", (e) => {
      if (e.target === this.cy) this.cy?.fit(undefined, 40);
    });
  }


  private async loadData(): Promise<void> {
    this.loading = true;
    try {
      const [sessions, providers] = await Promise.all([
        listSessions().catch(() => [] as Session[]),
        listProviders().catch(() => [] as Provider[]),
      ]);

      const subagentArrays = await Promise.all(
        sessions.map((s) =>
          listSubagents(s.id).catch(() => [] as Subagent[])
        )
      );
      const subagents = subagentArrays.flat();

      this.buildGraph(sessions, subagents, providers);
    } catch {
      // daemon offline — show empty graph with just daemon node
      this.buildGraph([], [], []);
    } finally {
      this.loading = false;
    }
  }

  private buildGraph(
    sessions: Session[],
    subagents: Subagent[],
    providers: Provider[]
  ): void {
    if (!this.cy) return;

    const elements: ElementDefinition[] = [];

    // Daemon root
    elements.push({
      data: { id: "daemon", label: "daemon", kind: "daemon", status: "active" },
    } as GraphNode);

    // Sessions
    for (const s of sessions) {
      elements.push({
        data: {
          id: `session:${s.id}`,
          label: s.id.slice(0, 8) + "…",
          kind: "session",
          status: s.historyLength > 0 ? "active" : "inactive",
          channelId: s.channelId,
        },
      } as GraphNode);
      elements.push({
        data: {
          id: `edge:daemon:${s.id}`,
          source: "daemon",
          target: `session:${s.id}`,
          kind: "hosts",
        },
      } as GraphEdge);
    }

    // Subagents
    for (const sa of subagents) {
      const saId = `subagent:${sa.id}`;
      const parentId = sa.parentSessionId
        ? `session:${sa.parentSessionId}`
        : "daemon";
      elements.push({
        data: {
          id: saId,
          label: sa.label.slice(0, 14),
          kind: "subagent",
          status: sa.status,
          task: sa.task,
        },
      } as GraphNode);
      elements.push({
        data: {
          id: `edge:${parentId}:${sa.id}`,
          source: parentId,
          target: saId,
          kind: "spawned",
        },
      } as GraphEdge);
    }

    // Providers
    for (const p of providers) {
      elements.push({
        data: {
          id: `provider:${p.id}`,
          label: p.name,
          kind: "provider",
          status: p.status,
          model: p.defaultModel,
        },
      } as GraphNode);
      elements.push({
        data: {
          id: `edge:daemon:provider:${p.id}`,
          source: "daemon",
          target: `provider:${p.id}`,
          kind: "uses",
        },
      } as GraphEdge);
    }

    this.cy.elements().remove();
    this.cy.add(elements);
    this.runLayout();
    this.updateStats();
  }


  private runLayout(animate = true): void {
    if (!this.cy) return;
    // Debounce rapid updates
    if (this.layoutTimer) clearTimeout(this.layoutTimer);
    this.layoutTimer = setTimeout(() => {
      this.layoutTimer = null;
      if (!this.cy) return;
      const layout = this.cy.layout({
        name: "dagre",
        rankDir: "TB",
        nodeSep: 70,
        edgeSep: 20,
        rankSep: 90,
        animate,
        animationDuration: animate ? 350 : 0,
        fit: true,
        padding: 40,
        // Providers are ranked to the right via edge weights
      } as any);
      layout.run();
    }, 80);
  }

  private updateStats(): void {
    if (!this.cy) return;
    this.nodeCount = this.cy.nodes().length;
    this.edgeCount = this.cy.edges().length;
  }


  private attachStream(): void {
    if (!this.stream) return;

    this.unsubs.push(
      this.stream.on("session:created", (data) => {
        const d = data as { sessionId: string; channelId: string; senderId?: string };
        this.addNode({
          data: {
            id: `session:${d.sessionId}`,
            label: d.sessionId.slice(0, 8) + "…",
            kind: "session",
            status: "active",
            channelId: d.channelId,
          },
        } as GraphNode);
        this.addEdge("daemon", `session:${d.sessionId}`, "hosts");
      }),

      this.stream.on("session:ended", (data) => {
        const d = data as { sessionId: string };
        this.updateNodeStatus(`session:${d.sessionId}`, "inactive");
      }),

      this.stream.on("subagent:spawned", (data) => {
        const d = data as {
          childSessionId: string;
          parentSessionId: string;
          label: string;
          runId: string;
        };
        const saId = `subagent:${d.childSessionId}`;
        this.addNode({
          data: {
            id: saId,
            label: (d.label ?? "subagent").slice(0, 14),
            kind: "subagent",
            status: "running",
          },
        } as GraphNode);
        const parentId = d.parentSessionId
          ? `session:${d.parentSessionId}`
          : "daemon";
        this.addEdge(parentId, saId, "spawned");
      }),

      this.stream.on("subagent:completed", (data) => {
        const d = data as { sessionId: string };
        this.updateNodeStatus(`subagent:${d.sessionId}`, "completed");
      }),

      this.stream.on("subagent:failed", (data) => {
        const d = data as { sessionId: string };
        this.updateNodeStatus(`subagent:${d.sessionId}`, "failed");
      }),

      this.stream.on("agent:spawned", (data) => {
        const d = data as { agentId: string; role: string; parentSessionId?: string };
        const agId = `subagent:${d.agentId}`;
        this.addNode({
          data: {
            id: agId,
            label: d.role.slice(0, 14),
            kind: "subagent",
            status: "running",
          },
        } as GraphNode);
        const parentId = d.parentSessionId
          ? `session:${d.parentSessionId}`
          : "daemon";
        this.addEdge(parentId, agId, "spawned");
      }),

      this.stream.on("agent:completed", (data) => {
        const d = data as { agentId: string };
        this.updateNodeStatus(`subagent:${d.agentId}`, "completed");
      }),

      this.stream.on("agent:error", (data) => {
        const d = data as { agentId: string };
        this.updateNodeStatus(`subagent:${d.agentId}`, "failed");
      }),

      this.stream.on("team:started", (data) => {
        const d = data as { teamId: string; coordinatorAgentId?: string };
        this.addNode({
          data: {
            id: `team:${d.teamId}`,
            label: d.teamId.slice(0, 10),
            kind: "team",
            status: "active",
          },
        } as GraphNode);
        this.addEdge("daemon", `team:${d.teamId}`, "hosts");
      }),

      this.stream.on("team:completed", (data) => {
        const d = data as { teamId: string };
        this.updateNodeStatus(`team:${d.teamId}`, "completed");
      }),

      this.stream.on("team:failed", (data) => {
        const d = data as { teamId: string };
        this.updateNodeStatus(`team:${d.teamId}`, "failed");
      }),

      // Highlight provider edges during active requests
      this.stream.on("provider:request_start", (data) => {
        const d = data as { providerId: string; requestId: string; sessionId: string };
        const edgeId = `edge:req:${d.requestId}`;
        this.addEdge(
          `session:${d.sessionId}`,
          `provider:${d.providerId}`,
          "requests",
          edgeId
        );
        this.cy?.getElementById(edgeId).addClass("active-request");
        this.activeRequests.set(d.requestId, edgeId);
      }),

      this.stream.on("provider:request_end", (data) => {
        const d = data as { requestId: string };
        const edgeId = this.activeRequests.get(d.requestId);
        if (edgeId) {
          // Fade then remove
          this.cy?.getElementById(edgeId).removeClass("active-request");
          setTimeout(() => this.cy?.getElementById(edgeId).remove(), 2000);
          this.activeRequests.delete(d.requestId);
          this.updateStats();
        }
      }),

      this.stream.on("provider:request_error", (data) => {
        const d = data as { requestId: string };
        const edgeId = this.activeRequests.get(d.requestId);
        if (edgeId) {
          this.cy?.getElementById(edgeId).remove();
          this.activeRequests.delete(d.requestId);
          this.updateStats();
        }
      })
    );
  }

  private detachStream(): void {
    this.unsubs.forEach((u) => u());
    this.unsubs = [];
  }


  private addNode(node: GraphNode): void {
    if (!this.cy) return;
    if (this.cy.getElementById(node.data.id).length > 0) {
      // Already exists — update status
      this.cy.getElementById(node.data.id).data(node.data);
      return;
    }
    this.cy.add(node);
    this.runLayout();
    this.updateStats();
  }

  private addEdge(
    source: string,
    target: string,
    kind: GraphEdge["data"]["kind"],
    id?: string
  ): void {
    if (!this.cy) return;
    const edgeId = id ?? `edge:${source}:${target}`;
    if (this.cy.getElementById(edgeId).length > 0) return;
    // Only add if both endpoints exist
    if (
      this.cy.getElementById(source).length === 0 ||
      this.cy.getElementById(target).length === 0
    )
      return;
    this.cy.add({ data: { id: edgeId, source, target, kind } } as GraphEdge);
    this.updateStats();
  }

  private updateNodeStatus(nodeId: string, status: string): void {
    if (!this.cy) return;
    const node = this.cy.getElementById(nodeId);
    if (node.length === 0) return;
    node.data("status", status);
  }


  private fitGraph(): void {
    this.cy?.fit(undefined, 40);
  }

  private refreshGraph(): void {
    this.loadData();
  }

  private relayout(): void {
    this.runLayout(true);
  }


  override render() {
    return html`
      <div class="toolbar">
        <span class="toolbar-title">System Topology</span>
        <button @click=${this.refreshGraph}>↻ Refresh</button>
        <button @click=${this.fitGraph}>⊡ Fit</button>
        <button @click=${this.relayout}>⊞ Layout</button>
        <span class="stats">${this.nodeCount} nodes · ${this.edgeCount} edges</span>

        <div class="legend">
          ${Object.entries(NODE_COLOR).map(
            ([kind, color]) => html`
              <div class="legend-item">
                <div class="legend-dot" style="background:${color}"></div>
                <span>${kind}</span>
              </div>
            `
          )}
        </div>
      </div>

      <div class="graph-container">
        <div id="cy"></div>

        ${this.loading
          ? html`<div class="loading">Loading topology…</div>`
          : nothing}

        <div
          class="tooltip ${this.tooltipVisible ? "visible" : ""}"
          style="left:${this.tooltipX}px;top:${this.tooltipY}px"
        >
          <div class="tooltip-type" style="color:${NODE_COLOR[this.tooltipKind] ?? "#6b6b8a"}">
            ${this.tooltipKind}
          </div>
          ${Object.entries(this.tooltipData).map(
            ([k, v]) => html`
              <div class="tooltip-row">
                <span>${k}</span>
                <span title=${v}>${v}</span>
              </div>
            `
          )}
        </div>
      </div>
    `;
  }
}

declare global {
  interface HTMLElementTagNameMap {
    "topology-panel": TopologyPanel;
  }
}
