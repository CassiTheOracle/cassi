/**
 * cognition-panel
 *
 * Real-time parallel thought stream visualization.
 * Replaces the Intelligence tab with a "rivers" model: 4 concurrent
 * cognitive streams flow side-by-side, each lane showing the live output
 * of one cognitive subsystem.
 *
 * Layout:
 *  ┌──────────────────────────────────────────────────────────────────┐
 *  │  Toolbar: Clear · turn counter                                    │
 *  │  Module strip: ● Memory  ● Thinker  ● Dialectic  ● Subconscious  │
 *  ├──────────────┬──────────────┬──────────────┬────────────────────┤
 *  │  ☯ Dialectic │  🧠 Thinker  │  💭 Subconsc │  🤝 Agents         │
 *  │  ─ Turn N ─  │  ─ Turn N ─  │  ─ Turn N ─  │  ─ Turn N ─        │
 *  │  ▶ Signal    │  ▶ Insight   │  ▶ Observed  │  ▶ Team started    │
 *  │  ▶ Synthesis │  ▶ Strategy  │  ▶ Anomaly   │  ▶ Agent spawned   │
 *  │  ─ Turn N-1 ─│  ─ Turn N-1 ─│  ─ Turn N-1 ─│  ─ Turn N-1 ─     │
 *  │  ...         │  ...         │  ...         │  ...               │
 *  └──────────────┴──────────────┴──────────────┴────────────────────┘
 *
 * Data sources:
 *  - SSE /events/stream → all cognitive events routed to lanes
 *  - GET /events/history → historical events seeded on load
 */

import { LitElement, html, css, nothing } from "lit";
import { customElement, property, state } from "lit/decorators.js";
import type { EventStreamManager } from "../api/event-stream.js";
import {
  getArchivedEntries,
  getSubconsciousLearnings,
  getSubconsciousAnomalies,
  type ArchiveEntry,
  type SubconsciousLearning,
  type SubconsciousAnomaly,
} from "../api/observatory-client.js";


type LaneId = "dialectic" | "thinker" | "subconscious" | "agents";

interface ThoughtCard {
  id: string;
  lane: LaneId;
  type: string;
  label: string;
  icon: string;
  color: string;
  preview: string;
  detail: string;
  timestamp: number;
  expanded: boolean;
  /** True for cards seeded from the archive rather than live SSE. */
  archived?: boolean;
  /** Short session identifier shown on archived cards. */
  sessionHint?: string;
}

interface TurnMarker {
  id: string;
  turnIndex: number;
  timestamp: number;
}

/** A single entry stored for session replay — all data needed to recreate a card. */
interface ReplayEntry {
  lane: LaneId;
  type: string;
  label: string;
  icon: string;
  color: string;
  preview: string;
  detail: string;
  archived: true;
  sessionHint?: string;
  timestamp: number;
}

type LaneEntry =
  | { kind: "card"; data: ThoughtCard }
  | { kind: "turn"; data: TurnMarker };


const LANE_CONFIG: Record<LaneId, { label: string; icon: string; color: string }> = {
  dialectic:    { label: "Dialectic",    icon: "☯",  color: "#f472b6" },
  thinker:      { label: "Thinker",      icon: "🧠", color: "#60a5fa" },
  subconscious: { label: "Subconscious", icon: "💭", color: "#a78bfa" },
  agents:       { label: "Agents",       icon: "🤝", color: "#2dd4bf" },
};

/** Visual metadata for each dialectic signal type. */
const SIGNAL_META: Record<string, { label: string; icon: string; color: string }> = {
  edge_case:     { label: "Edge Case",     icon: "🔍", color: "#f59e0b" },
  assumption:    { label: "Assumption",    icon: "💭", color: "#8b5cf6" },
  tension:       { label: "Tension",       icon: "⚡", color: "#f87171" },
  convergence:   { label: "Convergence",   icon: "✓",  color: "#4ade80" },
  gap:           { label: "Gap",           icon: "○",  color: "#94a3b8" },
  alternative:   { label: "Alternative",   icon: "⤷",  color: "#38bdf8" },
  connection:    { label: "Connection",    icon: "⚭",  color: "#93c5fd" },
  contradiction: { label: "Contradiction", icon: "↯",  color: "#ef4444" },
};

/** Compact status pills shown at the top of the panel. */
const MODULE_STRIP: Array<{ key: string; label: string; color: string }> = [
  { key: "memory",       label: "Memory",       color: "#6366f1" },
  { key: "thinker",      label: "Thinker",      color: "#60a5fa" },
  { key: "dialectic",    label: "Dialectic",    color: "#f472b6" },
  { key: "subconscious", label: "Subconscious", color: "#a78bfa" },
  { key: "optimizer",    label: "Optimizer",    color: "#22c55e" },
  { key: "multi-agent",  label: "Agents",       color: "#2dd4bf" },
  { key: "reflect",      label: "Reflect",      color: "#06b6d4" },
  { key: "archivist",    label: "Archivist",    color: "#64748b" },
];

const MAX_LANE_ENTRIES = 200;
const LANE_ACTIVE_MS = 1500;
const MODULE_PULSE_MS = 800;
const TURN_FLASH_MS = 700;
const COLLAPSED_LANE_PX = 36;

const LANE_IDS: LaneId[] = ["dialectic", "thinker", "subconscious", "agents"];


@customElement("cognition-panel")
export class CognitionPanel extends LitElement {
  static override styles = css`
    :host {
      display: flex;
      flex-direction: column;
      height: 100%;
      overflow: hidden;
      background: var(--color-surface, #0f0f12);
      font-size: 0.8rem;
    }

    /* ── Toolbar ─────────────────────────────────── */
    .toolbar {
      display: flex;
      align-items: center;
      gap: 0.5rem;
      padding: 0.45rem 0.75rem;
      background: var(--color-surface-2, #1a1a23);
      border-bottom: 1px solid var(--color-border, #2a2a3d);
      flex-shrink: 0;
    }

    .toolbar-title {
      font-size: 0.72rem;
      font-weight: 600;
      color: var(--color-text-muted, #6b6b8a);
      text-transform: uppercase;
      letter-spacing: 0.08em;
    }

    button {
      background: var(--color-surface-3, #24243a);
      border: 1px solid var(--color-border, #2a2a3d);
      color: var(--color-text, #e2e2f0);
      font-size: 0.7rem;
      padding: 0.2rem 0.5rem;
      border-radius: 4px;
      cursor: pointer;
      transition: background 0.15s;
    }
    button:hover { background: #2e2e4a; }

    /* Turn counter — flashes on new turn */
    .turn-counter {
      margin-left: auto;
      font-size: 0.75rem;
      font-weight: 600;
      color: var(--color-text-muted, #6b6b8a);
      letter-spacing: 0.02em;
      transition: color 0.15s;
    }

    .turn-counter.flash {
      animation: turn-flash ${TURN_FLASH_MS}ms ease-out forwards;
    }

    @keyframes turn-flash {
      0%   { color: #93c5fd; text-shadow: 0 0 8px #3b82f680; }
      60%  { color: #e2e2f0; text-shadow: none; }
      100% { color: var(--color-text-muted, #6b6b8a); }
    }

    /* ── Replay bar ──────────────────────────────── */
    .replay-bar {
      display: flex;
      align-items: center;
      gap: 0.5rem;
      padding: 0.3rem 0.75rem;
      background: color-mix(in srgb, #6366f1 8%, var(--color-surface-2, #1a1a23));
      border-bottom: 1px solid color-mix(in srgb, #6366f1 30%, var(--color-border, #2a2a3d));
      flex-shrink: 0;
    }

    button.replay-active {
      border-color: color-mix(in srgb, #6366f1 55%, transparent);
      color: #818cf8;
      background: color-mix(in srgb, #6366f1 12%, var(--color-surface-3, #24243a));
    }

    .replay-play-btn {
      min-width: 26px;
      text-align: center;
    }

    .replay-time {
      font-size: 0.68rem;
      font-variant-numeric: tabular-nums;
      color: var(--color-text, #e2e2f0);
      white-space: nowrap;
    }

    .replay-time.muted {
      color: var(--color-text-muted, #6b6b8a);
    }

    .replay-scrubber {
      flex: 1;
      height: 4px;
      min-width: 80px;
      cursor: pointer;
      accent-color: #6366f1;
    }

    .replay-count {
      font-size: 0.62rem;
      color: var(--color-text-muted, #6b6b8a);
      white-space: nowrap;
      margin-left: auto;
    }

    .replay-loading {
      font-size: 0.72rem;
      color: var(--color-text-muted, #6b6b8a);
      animation: pulse-opacity 1s ease-in-out infinite alternate;
    }

    @keyframes pulse-opacity {
      from { opacity: 0.4; }
      to   { opacity: 1; }
    }

    /* ── Module status strip ─────────────────────── */
    .module-strip {
      display: flex;
      align-items: center;
      gap: 0.3rem;
      padding: 0.28rem 0.75rem;
      background: var(--color-surface-2, #1a1a23);
      border-bottom: 1px solid var(--color-border, #2a2a3d);
      flex-shrink: 0;
      overflow-x: auto;
      scrollbar-width: none;
    }
    .module-strip::-webkit-scrollbar { display: none; }

    .module-pill {
      display: flex;
      align-items: center;
      gap: 0.22rem;
      padding: 0.08rem 0.35rem 0.08rem 0.25rem;
      border-radius: 10px;
      background: var(--color-surface-3, #24243a);
      border: 1px solid var(--color-border, #2a2a3d);
      font-size: 0.62rem;
      color: var(--color-text-muted, #6b6b8a);
      white-space: nowrap;
      flex-shrink: 0;
      transition: border-color 0.2s, color 0.2s;
      user-select: none;
    }

    .module-pill.active {
      border-color: color-mix(in srgb, var(--module-color) 55%, transparent);
      color: var(--module-color);
    }

    .module-dot {
      width: 5px;
      height: 5px;
      border-radius: 50%;
      background: currentColor;
      opacity: 0.35;
      transition: opacity 0.2s;
      flex-shrink: 0;
    }

    .module-pill.active .module-dot { opacity: 1; }

    .module-pill.pulsing .module-dot {
      animation: dot-pop 0.7s ease-out;
    }

    @keyframes dot-pop {
      0%   { transform: scale(1); }
      35%  { transform: scale(2.4); opacity: 1; }
      100% { transform: scale(1); }
    }

    /* Event count badge inside module pill */
    .module-count {
      font-size: 0.58rem;
      font-weight: 600;
      opacity: 0.7;
      min-width: 1ch;
    }
    .module-pill.active .module-count { opacity: 1; }

    /* ── Lane grid — columns set inline for collapse ─ */
    .lane-grid {
      display: grid;
      /* grid-template-columns set inline via laneGridStyle */
      flex: 1;
      min-height: 0;
      overflow: hidden;
      transition: grid-template-columns 0.2s ease;
    }

    .lane {
      display: flex;
      flex-direction: column;
      border-right: 1px solid var(--color-border, #2a2a3d);
      overflow: hidden;
      min-width: 0;
      transition: opacity 0.15s;
    }
    .lane:last-child { border-right: none; }

    /* ── Lane header ─────────────────────────────── */
    .lane-header {
      display: flex;
      align-items: center;
      gap: 0.35rem;
      padding: 0.38rem 0.6rem;
      background: var(--color-surface-2, #1a1a23);
      border-bottom: 1px solid var(--color-border, #2a2a3d);
      flex-shrink: 0;
      user-select: none;
      cursor: pointer;
      transition: background 0.12s;
    }
    .lane-header:hover { background: #1e1e2e; }

    .lane-icon { font-size: 0.85rem; flex-shrink: 0; }

    .lane-label {
      font-size: 0.72rem;
      font-weight: 600;
      color: var(--lane-color);
      white-space: nowrap;
      overflow: hidden;
      text-overflow: ellipsis;
    }

    .lane-count {
      font-size: 0.58rem;
      font-weight: 600;
      color: var(--lane-color);
      opacity: 0.7;
      background: color-mix(in srgb, var(--lane-color) 12%, transparent);
      padding: 0.05rem 0.3rem;
      border-radius: 8px;
      flex-shrink: 0;
    }

    /* Collapse chevron */
    .lane-chevron {
      margin-left: auto;
      font-size: 0.55rem;
      color: var(--color-text-muted, #6b6b8a);
      opacity: 0.5;
      flex-shrink: 0;
      transition: transform 0.2s, opacity 0.15s;
    }
    .lane-header:hover .lane-chevron { opacity: 1; }
    .lane.collapsed .lane-chevron { transform: rotate(-90deg); }

    .lane-status-dot {
      width: 7px;
      height: 7px;
      border-radius: 50%;
      background: var(--color-surface-3, #24243a);
      border: 1.5px solid var(--color-border, #2a2a3d);
      transition: all 0.25s;
      flex-shrink: 0;
    }

    .lane-status-dot.active {
      background: var(--lane-color);
      border-color: var(--lane-color);
      box-shadow: 0 0 5px color-mix(in srgb, var(--lane-color) 60%, transparent);
      animation: lane-glow 1.2s ease-in-out infinite;
    }

    @keyframes lane-glow {
      0%, 100% { opacity: 1; }
      50%       { opacity: 0.35; }
    }

    /* ── Collapsed lane ──────────────────────────── */
    .lane.collapsed .lane-header {
      flex-direction: column;
      align-items: center;
      justify-content: flex-start;
      padding: 0.6rem 0;
      height: 100%;
      gap: 0.45rem;
      border-bottom: none;
      border-right: 1px solid var(--color-border, #2a2a3d);
    }

    /* When last child and collapsed, restore border */
    .lane.collapsed:last-child .lane-header { border-right: none; }

    .lane.collapsed .lane-label,
    .lane.collapsed .lane-status-dot {
      display: none;
    }

    /* Vertical count in collapsed state */
    .lane.collapsed .lane-count {
      writing-mode: vertical-rl;
      text-orientation: mixed;
      padding: 0.2rem 0;
    }

    .lane.collapsed .lane-chevron {
      margin-left: 0;
      margin-top: auto;
      transform: rotate(-90deg);
    }

    .lane.collapsed .lane-body { display: none; }

    /* ── Lane body ───────────────────────────────── */
    .lane-body {
      flex: 1;
      overflow-y: auto;
      overflow-x: hidden;
      padding: 0.45rem 0.4rem;
      display: flex;
      flex-direction: column;
      gap: 0.3rem;
      scrollbar-width: thin;
      scrollbar-color: var(--color-border, #2a2a3d) transparent;
    }

    /* ── Turn marker ─────────────────────────────── */
    .turn-marker {
      display: flex;
      align-items: center;
      gap: 0.2rem;
      padding: 0.3rem 0 0.15rem;
      flex-shrink: 0;
    }

    .turn-line {
      flex: 1;
      height: 1px;
      background: linear-gradient(
        to right,
        transparent,
        color-mix(in srgb, var(--lane-color) 30%, var(--color-border, #2a2a3d)),
        transparent
      );
    }

    .turn-label {
      font-size: 0.58rem;
      font-weight: 600;
      color: color-mix(in srgb, var(--lane-color) 50%, var(--color-text-muted, #6b6b8a));
      padding: 0 0.28rem;
      white-space: nowrap;
      letter-spacing: 0.05em;
    }

    /* ── Thought cards ───────────────────────────── */
    .thought-card {
      background: var(--color-surface-2, #1a1a23);
      border: 1px solid var(--color-border, #2a2a3d);
      border-left: 3px solid var(--card-color, #6366f1);
      border-radius: 5px;
      padding: 0.4rem 0.5rem;
      cursor: pointer;
      transition: background 0.12s, border-color 0.12s;
      animation: card-appear 0.18s ease-out;
      flex-shrink: 0;
    }

    @keyframes card-appear {
      from { opacity: 0; transform: translateY(-4px); }
      to   { opacity: 1; transform: translateY(0); }
    }

    .thought-card:hover {
      background: var(--color-surface-3, #24243a);
      border-color: color-mix(in srgb, var(--card-color) 30%, var(--color-border, #2a2a3d));
    }

    .card-header {
      display: flex;
      align-items: center;
      gap: 0.3rem;
      margin-bottom: 0.25rem;
    }

    .card-icon { font-size: 0.75rem; line-height: 1; flex-shrink: 0; }

    .card-type {
      font-size: 0.62rem;
      font-weight: 700;
      color: var(--card-color);
      text-transform: uppercase;
      letter-spacing: 0.06em;
    }

    .card-time {
      margin-left: auto;
      font-size: 0.58rem;
      color: var(--color-text-muted, #6b6b8a);
      flex-shrink: 0;
      cursor: help;
    }

    /* Preview: clamped to 3 lines, unclamped when expanded */
    .card-preview {
      font-size: 0.72rem;
      line-height: 1.5;
      color: var(--color-text, #e2e2f0);
      overflow: hidden;
      display: -webkit-box;
      -webkit-line-clamp: 3;
      -webkit-box-orient: vertical;
      word-break: break-word;
    }

    .thought-card.expanded .card-preview {
      -webkit-line-clamp: unset;
      overflow: visible;
    }

    /* Fade hint when text is clamped */
    .card-expand-hint {
      font-size: 0.58rem;
      color: var(--color-text-muted, #6b6b8a);
      margin-top: 0.15rem;
      opacity: 0.6;
    }
    .thought-card.expanded .card-expand-hint { display: none; }

    /* Archived cards — slightly muted, dotted left border */
    .thought-card.archived {
      opacity: 0.75;
      border-left-style: dashed;
    }
    .thought-card.archived:hover { opacity: 1; }

    .card-session-hint {
      font-size: 0.56rem;
      color: var(--color-text-muted, #6b6b8a);
      opacity: 0.6;
      font-family: monospace;
      flex-shrink: 0;
    }

    /* ── Empty lane state — compact ─────────────── */
    .empty-lane {
      padding: 0.6rem 0.5rem 0;
      pointer-events: none;
    }

    .empty-text {
      font-size: 0.64rem;
      font-style: italic;
      color: var(--color-text-muted, #6b6b8a);
      opacity: 0.45;
    }
  `;

  @property({ attribute: false }) stream: EventStreamManager | null = null;
  @property() sessionId: string = "";

  @state() private lanes: Record<LaneId, LaneEntry[]> = {
    dialectic: [], thinker: [], subconscious: [], agents: [],
  };

  @state() private laneActive: Map<LaneId, boolean> = new Map();
  @state() private moduleStates: Map<string, { active: boolean; pulsing: boolean }> = new Map();
  @state() private moduleEventCounts: Map<string, number> = new Map();
  @state() private collapsedLanes: Set<LaneId> = new Set();
  @state() private turnFlash = false;

  @state() private replayMode = false;
  @state() private replayLoading = false;
  @state() private replayPlaying = false;
  /** Scrubber position — 0 to 10 000 for fine-grained range input. */
  @state() private replayProgress = 0;
  /** All entries loaded for replay, sorted oldest-first. */
  @state() private replayEntries: ReplayEntry[] = [];
  @state() private replayMinTime = 0;
  @state() private replayMaxTime = 0;
  @state() private replayCursorTime = 0;

  private unsubs: Array<() => void> = [];
  private pulseTimers: Map<string, ReturnType<typeof setTimeout>> = new Map();
  private laneTimers: Map<LaneId, ReturnType<typeof setTimeout>> = new Map();
  private turnFlashTimer: ReturnType<typeof setTimeout> | null = null;
  private playTimer: ReturnType<typeof setInterval> | null = null;
  private currentTurn = 0;
  private nextId = 0;

  override connectedCallback(): void {
    super.connectedCallback();
    this.initModuleStates();
    this.loadHistory().catch(() => { /* best effort */ });
  }

  override disconnectedCallback(): void {
    super.disconnectedCallback();
    this.detachStream();
    this.pulseTimers.forEach((t) => clearTimeout(t));
    this.laneTimers.forEach((t) => clearTimeout(t));
    if (this.turnFlashTimer) clearTimeout(this.turnFlashTimer);
    if (this.playTimer !== null) clearInterval(this.playTimer);
  }

  override updated(changed: Map<string, unknown>): void {
    if (changed.has("stream")) {
      this.detachStream();
      this.attachStream();
    }
    // Reload archive when session selection changes
    if (changed.has("sessionId")) {
      // Exit replay mode — stale data no longer applies to the new session
      if (this.replayMode) {
        this.stopPlayTimer();
        this.replayMode = false;
        this.replayEntries = [];
      }
      this.clearAll();
      this.loadHistory().catch(() => { /* best effort */ });
    }
  }


  private initModuleStates(): void {
    for (const m of MODULE_STRIP) {
      this.moduleStates.set(m.key, { active: false, pulsing: false });
    }
    this.moduleStates = new Map(this.moduleStates);
  }


  /**
   * Fetch recent event history and seed lanes so the panel isn't empty
   * when the user first opens it. Events are processed oldest-first so
  /**
   * Seed all 4 lanes from the Archivist and Subconscious databases.
   * Runs in parallel, oldest entries first so prepend order is correct.
   * If a sessionId is selected, only entries matching that session are shown.
   */
  private async loadHistory(): Promise<void> {
    const [archiveResult, learningsResult, anomaliesResult] = await Promise.allSettled([
      getArchivedEntries({ limit: 100 }),
      getSubconsciousLearnings(),
      getSubconsciousAnomalies(),
    ]);

    // Types that map to the 4 cognitive lanes
    const ARCHIVE_LANE_TYPES = new Set([
      "dialectic_yang", "dialectic_yin", "dialectic_serenity",
      "insight", "thinking", "reflection", "pattern",
    ]);

    /** Short session tag shown on archived cards — last 6 chars of sessionId. */
    const sessionHint = (id: string | null): string | undefined =>
      id ? `#${id.slice(-6)}` : undefined;

    if (archiveResult.status === "fulfilled") {
      const entries = archiveResult.value
        .filter((e) => {
          if (!ARCHIVE_LANE_TYPES.has(e.type)) return false;
          if (this.sessionId && e.sessionId && e.sessionId !== this.sessionId) return false;
          return true;
        })
        .sort((a, b) => a.timestamp - b.timestamp); // oldest first

      for (const entry of entries) {
        const card = this.archiveEntryToCard(entry);
        if (card) this.pushCard({ ...card, archived: true, sessionHint: sessionHint(entry.sessionId) }, entry.timestamp);
      }
    }

    if (learningsResult.status === "fulfilled") {
      const sorted = [...learningsResult.value].sort((a, b) => a.timestamp - b.timestamp);
      for (const obs of sorted) {
        this.pushCard({
          lane: "subconscious",
          type: `observation:${obs.source}`,
          label: obs.source === "llm" ? "LLM Observation" : "Observation",
          icon: "👁",
          color: obs.source === "llm" ? "#a78bfa" : "#818cf8",
          preview: obs.summary,
          detail: "",
          archived: true,
        }, obs.timestamp);
      }
    }

    if (anomaliesResult.status === "fulfilled") {
      const sorted = [...anomaliesResult.value].sort((a, b) => a.timestamp - b.timestamp);
      for (const anomaly of sorted) {
        const severityColor: Record<string, string> = {
          high: "#ef4444", medium: "#f87171", low: "#fb923c",
        };
        this.pushCard({
          lane: "subconscious",
          type: "anomaly",
          label: `Anomaly — ${anomaly.severity}`,
          icon: anomaly.severity === "high" ? "🚨" : "⚠",
          color: severityColor[anomaly.severity] ?? "#fb923c",
          preview: anomaly.description,
          detail: "",
          archived: true,
        }, anomaly.timestamp);
      }
    }
  }

  /**
   * Convert a raw Archivist entry to a lane card definition.
   * Returns null for types that don't belong in any thought-stream lane.
   */
  private archiveEntryToCard(
    entry: ArchiveEntry
  ): (Omit<ThoughtCard, "id" | "expanded" | "timestamp" | "archived"> & { lane: LaneId }) | null {
    const { type, content } = entry;
    switch (type) {
      case "dialectic_yang":
        return { lane: "dialectic", type: "yang", label: "Yang — Expansion", icon: "☀", color: "#fb923c", preview: content, detail: "" };
      case "dialectic_yin":
        return { lane: "dialectic", type: "yin", label: "Yin — Critique", icon: "🌙", color: "#818cf8", preview: content, detail: "" };
      case "dialectic_serenity":
        return { lane: "dialectic", type: "serenity", label: "Serenity — Synthesis", icon: "⚖", color: "#c084fc", preview: content, detail: "" };
      case "insight":
        return { lane: "thinker", type: "insight", label: "Insight", icon: "💡", color: "#fbbf24", preview: content, detail: "" };
      case "thinking":
        return { lane: "thinker", type: "thinking", label: "Thinking", icon: "💭", color: "#93c5fd", preview: content, detail: "" };
      case "reflection":
        return { lane: "thinker", type: "reflection", label: "Reflection", icon: "🔮", color: "#a78bfa", preview: content, detail: "" };
      case "pattern":
        return { lane: "subconscious", type: "pattern", label: "Pattern", icon: "🔗", color: "#6366f1", preview: content, detail: "" };
      default:
        return null;
    }
  }


  /**
   * Load ALL archive entries for the current session (or global if none
   * selected) and store them sorted by timestamp for replay.
   */
  private async loadReplay(): Promise<void> {
    this.replayLoading = true;
    try {
      const archiveOpts = { limit: 500, ...(this.sessionId ? { sessionId: this.sessionId } : {}) };
      const [archiveResult, learningsResult, anomaliesResult] = await Promise.allSettled([
        getArchivedEntries(archiveOpts),
        getSubconsciousLearnings(),
        getSubconsciousAnomalies(),
      ]);

      const entries: ReplayEntry[] = [];

      const ARCHIVE_LANE_TYPES = new Set([
        "dialectic_yang", "dialectic_yin", "dialectic_serenity",
        "insight", "thinking", "reflection", "pattern",
      ]);
      const sessionHint = (id: string | null): string | undefined =>
        id ? `#${id.slice(-6)}` : undefined;

      if (archiveResult.status === "fulfilled") {
        for (const e of archiveResult.value) {
          if (!ARCHIVE_LANE_TYPES.has(e.type)) continue;
          if (this.sessionId && e.sessionId && e.sessionId !== this.sessionId) continue;
          const card = this.archiveEntryToCard(e);
          if (!card) continue;
          entries.push({ ...card, archived: true, sessionHint: sessionHint(e.sessionId), timestamp: e.timestamp });
        }
      }

      if (learningsResult.status === "fulfilled") {
        for (const obs of learningsResult.value) {
          entries.push({
            lane: "subconscious", type: `observation:${obs.source}`,
            label: obs.source === "llm" ? "LLM Observation" : "Observation",
            icon: "👁", color: obs.source === "llm" ? "#a78bfa" : "#818cf8",
            preview: obs.summary, detail: "", archived: true,
            timestamp: obs.timestamp,
          });
        }
      }

      if (anomaliesResult.status === "fulfilled") {
        const severityColor: Record<string, string> = { high: "#ef4444", medium: "#f87171", low: "#fb923c" };
        for (const a of anomaliesResult.value) {
          entries.push({
            lane: "subconscious", type: "anomaly",
            label: `Anomaly — ${a.severity}`,
            icon: a.severity === "high" ? "🚨" : "⚠",
            color: severityColor[a.severity] ?? "#fb923c",
            preview: a.description, detail: "", archived: true,
            timestamp: a.timestamp,
          });
        }
      }

      entries.sort((a, b) => a.timestamp - b.timestamp);
      this.replayEntries = entries;

      if (entries.length > 0) {
        this.replayMinTime = entries[0].timestamp;
        this.replayMaxTime = entries[entries.length - 1].timestamp;
        // Start at the beginning of the session
        this.replayCursorTime = this.replayMinTime;
        this.replayProgress = 0;
      }
    } finally {
      this.replayLoading = false;
    }
  }

  /** Toggle replay mode on/off. */
  private async toggleReplay(): Promise<void> {
    if (this.replayMode) {
      this.stopPlayTimer();
      this.replayMode = false;
      this.replayEntries = [];
    } else {
      this.replayMode = true;
      this.replayPlaying = false;
      await this.loadReplay();
    }
  }

  /** Play or pause replay auto-advance. */
  private togglePlay(): void {
    if (this.replayPlaying) {
      this.stopPlayTimer();
    } else {
      // If already at the end, restart from the beginning
      if (this.replayCursorTime >= this.replayMaxTime) {
        this.replayCursorTime = this.replayMinTime;
        this.replayProgress = 0;
      }
      this.startPlayTimer();
    }
  }

  /**
   * Start auto-advancing the replay cursor.
   * Each 100 ms tick advances the playhead by SPEED × 100 ms of session time
   * (default 20×: 1 real second = 20 session seconds).
   */
  private startPlayTimer(): void {
    this.replayPlaying = true;
    const TICK_MS = 100;
    const SPEED = 20;
    this.playTimer = setInterval(() => {
      const step = TICK_MS * SPEED;
      this.replayCursorTime = Math.min(this.replayCursorTime + step, this.replayMaxTime);
      const range = this.replayMaxTime - this.replayMinTime;
      this.replayProgress = range > 0
        ? Math.round(((this.replayCursorTime - this.replayMinTime) / range) * 10_000)
        : 10_000;
      if (this.replayCursorTime >= this.replayMaxTime) {
        this.stopPlayTimer();
      }
    }, TICK_MS);
  }

  private stopPlayTimer(): void {
    this.replayPlaying = false;
    if (this.playTimer !== null) {
      clearInterval(this.playTimer);
      this.playTimer = null;
    }
  }

  /** Scrubber input handler — jump the playhead to the chosen position. */
  private onScrub(e: Event): void {
    const val = Number((e.target as HTMLInputElement).value);
    this.replayProgress = val;
    const range = this.replayMaxTime - this.replayMinTime;
    this.replayCursorTime = this.replayMinTime + (val / 10_000) * range;
    // Pause auto-play while the user scrubs
    if (this.replayPlaying) this.stopPlayTimer();
  }

  /**
   * In replay mode, compute virtual lanes containing only entries up to the
   * current cursor position.  In live mode, just return the real lanes.
   */
  private get activeLanes(): Record<LaneId, LaneEntry[]> {
    if (!this.replayMode) return this.lanes;
    const result: Record<LaneId, LaneEntry[]> = {
      dialectic: [], thinker: [], subconscious: [], agents: [],
    };
    let idx = 0;
    for (const entry of this.replayEntries) {
      if (entry.timestamp > this.replayCursorTime) break; // sorted, early exit
      result[entry.lane].push({
        kind: "card",
        data: {
          ...entry,
          id: `r${idx++}`,
          expanded: false,
        },
      });
    }
    return result;
  }

  /** Format a timestamp as HH:MM:SS for the replay time display. */
  private formatReplayTime(ts: number): string {
    if (!ts) return "--:--:--";
    return new Date(ts).toLocaleTimeString([], {
      hour: "2-digit", minute: "2-digit", second: "2-digit",
    });
  }

  private attachStream(): void {
    if (!this.stream) return;

    // Single catch-all handler to avoid duplicate subscriptions.
    // Route every event to the appropriate lane (or discard if unrecognized).
    this.unsubs.push(
      this.stream.onAll((raw) => {
        const data = raw as Record<string, unknown>;
        const type = data["type"] as string | undefined;
        if (!type) return;

        // Turn start → push synchronized marker into all 4 lanes
        if (type === "turn:start") {
          this.pushTurnMarker(Date.now());
          return;
        }

        const routed = this.routeEvent(type, data);
        if (routed) {
          this.pushCard(routed, Date.now());
          this.pulseLane(routed.lane);
        }

        const modKey = this.eventToModuleKey(type);
        if (modKey) this.pulseModule(modKey);
      })
    );
  }

  private detachStream(): void {
    this.unsubs.forEach((u) => u());
    this.unsubs = [];
  }


  /**
   * Map a raw event type + payload to a lane and card definition.
   * Returns null for events that don't belong in any thought-stream lane.
   */
  private routeEvent(
    type: string,
    data: Record<string, unknown>
  ): (Omit<ThoughtCard, "id" | "expanded" | "timestamp"> & { lane: LaneId }) | null {


    if (type === "dialectic:signal") {
      // { signal: { type: SignalType, content: string, confidence, sourceBranches, urgency } }
      const sig = (data.signal ?? data) as Record<string, unknown>;
      const sigType = String(sig.type ?? "signal");
      const meta = SIGNAL_META[sigType] ?? { label: sigType, icon: "◆", color: "#6366f1" };
      const desc = String(sig.content ?? sig.description ?? sig.text ?? "");
      return {
        lane: "dialectic", type: `signal:${sigType}`,
        ...meta,
        preview: desc || `${meta.label} detected`,
        detail: JSON.stringify(sig, null, 2),
      };
    }

    if (type === "dialectic:stream") {
      // Stage-based: start | yang | yin | serenity | complete
      const stage = String(data.stage ?? "");
      const d = (data.data ?? {}) as Record<string, unknown>;

      if (stage === "yang") {
        const branches = Array.isArray(d.branches) ? (d.branches as Array<Record<string, unknown>>) : [];
        const titles = branches
          .map((b) => String(b.title ?? b.content ?? b.text ?? ""))
          .filter(Boolean);
        return {
          lane: "dialectic", type: "yang",
          label: "Yang — Expansion", icon: "☀", color: "#fb923c",
          preview: titles.slice(0, 3).join(" · ") || (branches.length > 0 ? `${branches.length} branches explored` : "Expansion pass complete"),
          detail: JSON.stringify(d, null, 2),
        };
      }

      if (stage === "yin") {
        const critiques = Array.isArray(d.selfCritiques) ? (d.selfCritiques as Array<Record<string, unknown>>) : [];
        const texts = critiques
          .map((c) => String(c.critique ?? c.text ?? c.content ?? ""))
          .filter(Boolean);
        return {
          lane: "dialectic", type: "yin",
          label: "Yin — Critique", icon: "🌙", color: "#818cf8",
          preview: texts.slice(0, 3).join(" · ") || (critiques.length > 0 ? `${critiques.length} critiques` : "Critique pass complete"),
          detail: JSON.stringify(d, null, 2),
        };
      }

      if (stage === "serenity") {
        const synthesis = (d.synthesis ?? {}) as Record<string, unknown>;
        const hasSignal = Boolean(synthesis.hasSignal);
        const considered = Number(synthesis.branchesConsidered ?? 0);
        const surfaced = Number(synthesis.branchesSurfaced ?? 0);
        const quality = Number((d.meta as Record<string, unknown>)?.dialecticQuality ?? 0);
        const preview = hasSignal
          ? `Signal detected — ${surfaced}/${considered} branches surfaced`
          : quality > 0
          ? `Synthesis complete — quality ${(quality * 100).toFixed(0)}%`
          : "No signals — synthesis complete";
        return {
          lane: "dialectic", type: "serenity",
          label: "Serenity — Synthesis", icon: "⚖", color: "#c084fc",
          preview,
          detail: JSON.stringify(d, null, 2),
        };
      }

      // start / complete stages carry no meaningful content
      return null;
    }


    // thinker:insight is unwrapped from worker:message by the bridge
    if (["thinker:insight", "thinker:inject-insight", "thinker:session-injection"].includes(type)) {
      const text = String(data.insight ?? data.text ?? data.content ?? "");
      return {
        lane: "thinker", type: "insight",
        label: "Insight", icon: "💡", color: "#fbbf24",
        preview: text,
        detail: text || JSON.stringify(data, null, 2),
      };
    }

    if (type === "thinker:self-modified") {
      const text = String(data.description ?? data.change ?? data.detail ?? "");
      return {
        lane: "thinker", type: "strategy",
        label: "Strategy Updated", icon: "🔧", color: "#4ade80",
        preview: text || "Self-modification applied",
        detail: JSON.stringify(data, null, 2),
      };
    }

    if (type === "thinker:early-warning") {
      const text = String(data.warning ?? data.message ?? data.text ?? "");
      return {
        lane: "thinker", type: "warning",
        label: "Early Warning", icon: "⚠", color: "#fb923c",
        preview: text,
        detail: JSON.stringify(data, null, 2),
      };
    }

    if (type === "thinker:swarm-deployed") {
      const count = data.count != null ? `${data.count} drones` : "Swarm";
      const goal = String(data.goal ?? data.task ?? data.description ?? "");
      return {
        lane: "thinker", type: "swarm",
        label: "Swarm Deployed", icon: "🐝", color: "#fbbf24",
        preview: [count, goal].filter(Boolean).join(" — "),
        detail: JSON.stringify(data, null, 2),
      };
    }

    if (type === "thinker:subagent:spawned") {
      const role = String(data.role ?? data.type ?? data.label ?? "subagent");
      return {
        lane: "thinker", type: "subagent-spawn",
        label: "Subagent Spawned", icon: "🧬", color: "#34d399",
        preview: role,
        detail: JSON.stringify(data, null, 2),
      };
    }

    if (type === "thinker:subagent:completed" || type === "thinker:subagent:failed") {
      const ok = type === "thinker:subagent:completed";
      const result = String(data.result ?? data.summary ?? data.error ?? (ok ? "Completed" : "Failed"));
      return {
        lane: "thinker", type: ok ? "subagent-done" : "subagent-fail",
        label: ok ? "Subagent Done" : "Subagent Failed",
        icon: ok ? "✓" : "✗", color: ok ? "#4ade80" : "#f87171",
        preview: result,
        detail: JSON.stringify(data, null, 2),
      };
    }

    if (type === "thinker:ponder_start") {
      return {
        lane: "thinker", type: "ponder",
        label: "Pondering", icon: "💭", color: "#93c5fd",
        preview: "Ponder cycle started",
        detail: JSON.stringify(data, null, 2),
      };
    }

    if (type === "adaptive:adaptation-applied") {
      const desc = String(data.description ?? data.adaptation ?? data.detail ?? "");
      return {
        lane: "thinker", type: "adaptation",
        label: "Adaptation", icon: "⚙", color: "#34d399",
        preview: desc || "Adaptive behavior applied",
        detail: JSON.stringify(data, null, 2),
      };
    }


    if (type === "consciousness:observation") {
      // Observation: { id, summary, patterns, confidence, source, relatedEventTypes }
      const obs = (data.observation ?? data) as Record<string, unknown>;
      const text = String(obs.summary ?? obs.text ?? obs.message ?? obs.content ?? "");
      const src = String(obs.source ?? data.source ?? "heuristic");
      const patterns = Array.isArray(obs.patterns) ? (obs.patterns as string[]).join(", ") : "";
      return {
        lane: "subconscious", type: `observation:${src}`,
        label: src === "llm" ? "LLM Observation" : "Observation",
        icon: "👁", color: src === "llm" ? "#a78bfa" : "#818cf8",
        preview: text,
        detail: text + (patterns ? `\n\nPatterns: ${patterns}` : ""),
      };
    }

    if (type === "consciousness:anomaly") {
      // Anomaly: { id, description, severity, eventTypes, suggestedAction }
      const anomaly = (data.anomaly ?? data) as Record<string, unknown>;
      const text = String(anomaly.description ?? data.description ?? data.message ?? "");
      const severity = String(anomaly.severity ?? data.severity ?? "low");
      const severityColor: Record<string, string> = { high: "#ef4444", medium: "#f87171", low: "#fb923c" };
      return {
        lane: "subconscious", type: "anomaly",
        label: `Anomaly — ${severity}`,
        icon: severity === "high" ? "🚨" : "⚠",
        color: severityColor[severity] ?? "#fb923c",
        preview: text,
        detail: text || JSON.stringify(anomaly, null, 2),
      };
    }

    if (type === "subconscious:learning" || type === "subconscious:pattern") {
      const text = String(data.insight ?? data.pattern ?? data.text ?? data.content ?? "");
      return {
        lane: "subconscious", type: type,
        label: type === "subconscious:pattern" ? "Pattern Detected" : "Learning",
        icon: "🔗", color: "#6366f1",
        preview: text,
        detail: text || JSON.stringify(data, null, 2),
      };
    }

    if (type === "consciousness:insight") {
      const text = String(data.insight ?? data.text ?? data.content ?? "");
      return {
        lane: "subconscious", type: "cross-insight",
        label: "Cross-System Insight", icon: "✨", color: "#c084fc",
        preview: text,
        detail: text || JSON.stringify(data, null, 2),
      };
    }


    if (type === "team:started") {
      const goal = String(data.goal ?? data.description ?? data.task ?? "");
      return {
        lane: "agents", type: "team-start",
        label: "Team Started", icon: "🎯", color: "#2dd4bf",
        preview: goal,
        detail: JSON.stringify(data, null, 2),
      };
    }

    if (type === "team:completed") {
      const result = String(data.result ?? data.summary ?? "Team completed");
      return {
        lane: "agents", type: "team-complete",
        label: "Team Complete", icon: "✅", color: "#4ade80",
        preview: result,
        detail: JSON.stringify(data, null, 2),
      };
    }

    if (type === "team:failed") {
      const error = String(data.error ?? data.reason ?? "Team failed");
      return {
        lane: "agents", type: "team-failed",
        label: "Team Failed", icon: "❌", color: "#f87171",
        preview: error,
        detail: JSON.stringify(data, null, 2),
      };
    }

    if (type === "team:checkpoint") {
      const desc = String(data.description ?? data.message ?? "Checkpoint reached");
      return {
        lane: "agents", type: "checkpoint",
        label: "Checkpoint", icon: "⏸", color: "#fb923c",
        preview: desc,
        detail: JSON.stringify(data, null, 2),
      };
    }

    if (type === "agent:spawned") {
      const role = String(data.role ?? data.type ?? data.label ?? "");
      const task = String(data.task ?? data.goal ?? "");
      return {
        lane: "agents", type: "agent-spawn",
        label: "Agent Spawned", icon: "🤖", color: "#38bdf8",
        preview: [role, task].filter(Boolean).join(" — "),
        detail: JSON.stringify(data, null, 2),
      };
    }

    if (type === "agent:completed") {
      const result = String(data.result ?? data.summary ?? "Completed");
      return {
        lane: "agents", type: "agent-done",
        label: "Agent Done", icon: "✓", color: "#4ade80",
        preview: result,
        detail: JSON.stringify(data, null, 2),
      };
    }

    if (type === "agent:handoff") {
      const desc = String(data.description ?? data.message ?? data.task ?? "");
      return {
        lane: "agents", type: "handoff",
        label: "Agent Handoff", icon: "🔄", color: "#38bdf8",
        preview: desc,
        detail: JSON.stringify(data, null, 2),
      };
    }

    if (type === "drone:swarm:started") {
      const count = data.count != null ? `${data.count} drones` : "Drone swarm";
      const goal = String(data.goal ?? data.task ?? "");
      return {
        lane: "agents", type: "swarm-start",
        label: "Drone Swarm", icon: "🐝", color: "#fbbf24",
        preview: [count, goal].filter(Boolean).join(" — "),
        detail: JSON.stringify(data, null, 2),
      };
    }

    if (type === "drone:swarm:completed") {
      const summary = String(data.results ?? data.summary ?? "Swarm completed");
      return {
        lane: "agents", type: "swarm-done",
        label: "Swarm Complete", icon: "🏁", color: "#4ade80",
        preview: summary,
        detail: JSON.stringify(data, null, 2),
      };
    }

    if (type === "drone:swarm:failed") {
      const error = String(data.error ?? data.reason ?? "Swarm failed");
      return {
        lane: "agents", type: "swarm-failed",
        label: "Swarm Failed", icon: "💥", color: "#f87171",
        preview: error,
        detail: JSON.stringify(data, null, 2),
      };
    }

    return null; // event not routed to any lane
  }

  /** Map an event type prefix to its module strip key. */
  private eventToModuleKey(type: string): string | null {
    const prefix = type.split(":")[0];
    const map: Record<string, string> = {
      thinker:       "thinker",
      dialectic:     "dialectic",
      consciousness: "subconscious",
      agent:         "multi-agent",
      team:          "multi-agent",
      drone:         "multi-agent",
      memory:        "memory",
      archivist:     "archivist",
      optimizer:     "optimizer",
      reflect:       "reflect",
      adaptive:      "thinker",
    };
    return map[prefix] ?? null;
  }


  /** Push a synchronized turn marker into ALL 4 lanes and flash the toolbar. */
  private pushTurnMarker(timestamp: number): void {
    this.currentTurn++;
    const entry: LaneEntry = {
      kind: "turn",
      data: { id: `turn-${this.currentTurn}`, turnIndex: this.currentTurn, timestamp },
    };
    this.lanes = {
      dialectic:    [entry, ...this.lanes.dialectic].slice(0, MAX_LANE_ENTRIES),
      thinker:      [entry, ...this.lanes.thinker].slice(0, MAX_LANE_ENTRIES),
      subconscious: [entry, ...this.lanes.subconscious].slice(0, MAX_LANE_ENTRIES),
      agents:       [entry, ...this.lanes.agents].slice(0, MAX_LANE_ENTRIES),
    };
    // Flash the toolbar turn counter
    this.turnFlash = true;
    if (this.turnFlashTimer) clearTimeout(this.turnFlashTimer);
    this.turnFlashTimer = setTimeout(() => {
      this.turnFlash = false;
      this.turnFlashTimer = null;
    }, TURN_FLASH_MS);
  }

  private pushCard(
    data: Omit<ThoughtCard, "id" | "expanded" | "timestamp"> & { lane: LaneId },
    timestamp: number
  ): void {
    const card: ThoughtCard = { archived: false, ...data, id: `c${this.nextId++}`, timestamp, expanded: false };
    const entry: LaneEntry = { kind: "card", data: card };
    this.lanes = {
      ...this.lanes,
      [card.lane]: [entry, ...this.lanes[card.lane]].slice(0, MAX_LANE_ENTRIES),
    };
  }

  private toggleCard(cardId: string, lane: LaneId): void {
    this.lanes = {
      ...this.lanes,
      [lane]: this.lanes[lane].map((e) =>
        e.kind === "card" && e.data.id === cardId
          ? { ...e, data: { ...e.data, expanded: !e.data.expanded } }
          : e
      ),
    };
  }

  /** Light up the lane status dot temporarily. */
  private pulseLane(lane: LaneId): void {
    this.laneActive = new Map(this.laneActive).set(lane, true);
    const prev = this.laneTimers.get(lane);
    if (prev) clearTimeout(prev);
    this.laneTimers.set(
      lane,
      setTimeout(() => {
        this.laneActive = new Map(this.laneActive).set(lane, false);
        this.laneTimers.delete(lane);
      }, LANE_ACTIVE_MS)
    );
  }

  /** Pulse a module pill in the status strip and increment its event count. */
  private pulseModule(key: string): void {
    const existing = this.moduleStates.get(key);
    if (!existing) return;
    this.moduleStates.set(key, { active: true, pulsing: true });
    this.moduleStates = new Map(this.moduleStates);

    // Increment event count
    this.moduleEventCounts.set(key, (this.moduleEventCounts.get(key) ?? 0) + 1);
    this.moduleEventCounts = new Map(this.moduleEventCounts);

    const prev = this.pulseTimers.get(key);
    if (prev) clearTimeout(prev);
    this.pulseTimers.set(
      key,
      setTimeout(() => {
        const s = this.moduleStates.get(key);
        if (s) {
          this.moduleStates.set(key, { ...s, pulsing: false });
          this.moduleStates = new Map(this.moduleStates);
        }
        this.pulseTimers.delete(key);
      }, MODULE_PULSE_MS)
    );
  }

  private clearAll(): void {
    this.lanes = { dialectic: [], thinker: [], subconscious: [], agents: [] };
    this.currentTurn = 0;
    this.nextId = 0;
    this.moduleEventCounts = new Map();
  }

  /** Toggle a lane between expanded and collapsed. */
  private toggleLane(id: LaneId): void {
    const next = new Set(this.collapsedLanes);
    if (next.has(id)) next.delete(id);
    else next.add(id);
    this.collapsedLanes = next;
  }

  /** CSS grid-template-columns value based on which lanes are collapsed. */
  private get laneGridColumns(): string {
    return LANE_IDS.map((id) =>
      this.collapsedLanes.has(id) ? `${COLLAPSED_LANE_PX}px` : "1fr"
    ).join(" ");
  }


  private formatTime(ts: number): string {
    const d = Math.floor((Date.now() - ts) / 1000);
    if (d < 60) return `${d}s`;
    if (d < 3600) return `${Math.floor(d / 60)}m`;
    return `${Math.floor(d / 3600)}h`;
  }

  private formatWallTime(ts: number): string {
    return new Date(ts).toLocaleTimeString([], {
      hour: "2-digit", minute: "2-digit", second: "2-digit",
    });
  }

  private cardCount(lane: LaneId): number {
    return this.activeLanes[lane].filter((e) => e.kind === "card").length;
  }


  override render() {
    const visibleCount = this.replayMode
      ? this.replayEntries.filter((e) => e.timestamp <= this.replayCursorTime).length
      : 0;

    return html`
      <div class="toolbar">
        <span class="toolbar-title">Thought Streams</span>
        <button
          class="${this.replayMode ? "replay-active" : ""}"
          @click=${this.toggleReplay}
          title="${this.replayMode ? "Exit replay mode" : "Replay archived session"}"
        >⏮ Replay</button>
        ${!this.replayMode
          ? html`<button @click=${() => this.clearAll()}>✕ Clear</button>`
          : nothing}
        ${this.currentTurn > 0 && !this.replayMode
          ? html`<span class="turn-counter ${this.turnFlash ? "flash" : ""}">Turn ${this.currentTurn}</span>`
          : nothing}
      </div>

      ${this.replayMode ? html`
        <div class="replay-bar">
          ${this.replayLoading
            ? html`<span class="replay-loading">Loading archive…</span>`
            : html`
              <button
                class="replay-play-btn"
                @click=${this.togglePlay}
                ?disabled=${this.replayEntries.length === 0}
                title="${this.replayPlaying ? "Pause" : "Play"}"
              >${this.replayPlaying ? "⏸" : "▶"}</button>
              <span class="replay-time">${this.formatReplayTime(this.replayCursorTime)}</span>
              <input
                type="range"
                class="replay-scrubber"
                min="0"
                max="10000"
                .value=${String(this.replayProgress)}
                @input=${this.onScrub}
                ?disabled=${this.replayEntries.length === 0}
              >
              <span class="replay-time muted">${this.formatReplayTime(this.replayMaxTime)}</span>
              <span class="replay-count">${visibleCount} / ${this.replayEntries.length} events</span>
            `}
        </div>
      ` : nothing}

      <div class="module-strip">
        ${MODULE_STRIP.map((m) => {
          const s = this.moduleStates.get(m.key) ?? { active: false, pulsing: false };
          const count = this.moduleEventCounts.get(m.key) ?? 0;
          return html`
            <div
              class="module-pill ${s.active ? "active" : ""} ${s.pulsing ? "pulsing" : ""}"
              style="--module-color:${m.color}"
            >
              <span class="module-dot"></span>
              ${m.label}
              ${count > 0 ? html`<span class="module-count">${count}</span>` : nothing}
            </div>
          `;
        })}
      </div>

      <div class="lane-grid" style="grid-template-columns:${this.laneGridColumns}">
        ${LANE_IDS.map((id) => this.renderLane(id))}
      </div>
    `;
  }

  private renderLane(id: LaneId) {
    const cfg = LANE_CONFIG[id];
    const entries = this.activeLanes[id];
    const isActive = this.laneActive.get(id) ?? false;
    const count = this.cardCount(id);
    const isCollapsed = this.collapsedLanes.has(id);

    return html`
      <div class="lane ${isCollapsed ? "collapsed" : ""}" style="--lane-color:${cfg.color}">
        <div class="lane-header" @click=${() => this.toggleLane(id)} title="${isCollapsed ? "Expand" : "Collapse"} ${cfg.label}">
          <span class="lane-icon">${cfg.icon}</span>
          ${!isCollapsed ? html`<span class="lane-label">${cfg.label}</span>` : nothing}
          ${count > 0 ? html`<span class="lane-count">${count}</span>` : nothing}
          ${!isCollapsed ? html`<span class="lane-status-dot ${isActive ? "active" : ""}"></span>` : nothing}
          <span class="lane-chevron">▾</span>
        </div>

        <div class="lane-body">
          ${entries.length === 0
            ? html`<div class="empty-lane"><span class="empty-text">waiting…</span></div>`
            : entries.map((e) => this.renderEntry(e))}
        </div>
      </div>
    `;
  }

  private renderEntry(entry: LaneEntry) {
    if (entry.kind === "turn") {
      const m = entry.data;
      return html`
        <div class="turn-marker">
          <span class="turn-line"></span>
          <span class="turn-label">Turn ${m.turnIndex}</span>
          <span class="turn-line"></span>
        </div>
      `;
    }

    const card = entry.data;
    const wallTime = this.formatWallTime(card.timestamp);
    // Archived cards show a real date; live cards show relative time
    const timeLabel = card.archived
      ? new Date(card.timestamp).toLocaleDateString([], { month: "short", day: "numeric" })
      : this.formatTime(card.timestamp);

    return html`
      <div
        class="thought-card ${card.expanded ? "expanded" : ""} ${card.archived ? "archived" : ""}"
        style="--card-color:${card.color}"
        @click=${() => this.toggleCard(card.id, card.lane)}
      >
        <div class="card-header">
          <span class="card-icon">${card.icon}</span>
          <span class="card-type">${card.label}</span>
          ${card.sessionHint
            ? html`<span class="card-session-hint">${card.sessionHint}</span>`
            : nothing}
          <span class="card-time" title=${wallTime}>${timeLabel}</span>
        </div>
        <div class="card-preview">
          ${card.preview
            ? card.preview
            : html`<span style="opacity:0.35;font-style:italic">no content</span>`}
        </div>
      </div>
    `;
  }
}

declare global {
  interface HTMLElementTagNameMap {
    "cognition-panel": CognitionPanel;
  }
}
