/**
 * SplitPane — resizable two-slot container
 *
 * Usage:
 *   <split-pane direction="horizontal" storageKey="topo-split">
 *     <div slot="start">...</div>
 *     <div slot="end">...</div>
 *   </split-pane>
 *
 * direction: "horizontal" (side-by-side, default) | "vertical" (top-bottom)
 * storageKey: optional localStorage key to persist split ratio
 * ratio: initial split ratio 0–1 (default 0.5)
 */

import { LitElement, html, css } from "lit";
import { customElement, property, state } from "lit/decorators.js";

@customElement("split-pane")
export class SplitPane extends LitElement {
  static override styles = css`
    :host {
      display: flex;
      flex: 1;
      overflow: hidden;
      min-height: 0;
      min-width: 0;
    }

    :host([direction="vertical"]) {
      flex-direction: column;
    }

    .pane {
      overflow: hidden;
      min-width: 0;
      min-height: 0;
      display: flex;
      flex-direction: column;
    }

    ::slotted(*) {
      flex: 1;
      overflow: hidden;
      min-width: 0;
      min-height: 0;
    }

    .divider {
      flex-shrink: 0;
      background: var(--color-border, #2a2a3d);
      transition: background 0.15s;
      position: relative;
      z-index: 10;
      cursor: col-resize;
    }

    :host([direction="vertical"]) .divider {
      cursor: row-resize;
    }

    .divider:hover,
    .divider.dragging {
      background: #6366f1;
    }

    /* Horizontal: vertical divider bar */
    :host(:not([direction="vertical"])) .divider {
      width: 4px;
    }

    /* Vertical: horizontal divider bar */
    :host([direction="vertical"]) .divider {
      height: 4px;
    }

    /* Hit-area expansion without visual change */
    .divider::before {
      content: "";
      position: absolute;
      inset: -4px;
    }
  `;

  @property({ reflect: true }) direction: "horizontal" | "vertical" = "horizontal";
  @property({ type: String }) storageKey = "";
  @property({ type: Number }) ratio = 0.5;

  @state() private _ratio = 0.5;
  @state() private _dragging = false;

  private _dragStart = 0;
  private _ratioAtDragStart = 0;
  private _containerSize = 0;

  override connectedCallback(): void {
    super.connectedCallback();
    // Load persisted ratio
    if (this.storageKey) {
      const stored = localStorage.getItem(`split-pane:${this.storageKey}`);
      if (stored !== null) {
        const parsed = parseFloat(stored);
        if (!isNaN(parsed) && parsed > 0.05 && parsed < 0.95) {
          this._ratio = parsed;
          return;
        }
      }
    }
    this._ratio = this.ratio;
  }

  private _onDividerMouseDown = (e: MouseEvent): void => {
    e.preventDefault();
    this._dragging = true;
    this._dragStart = this.direction === "horizontal" ? e.clientX : e.clientY;
    this._ratioAtDragStart = this._ratio;

    const host = this.shadowRoot!.host as HTMLElement;
    const rect = host.getBoundingClientRect();
    this._containerSize = this.direction === "horizontal" ? rect.width : rect.height;

    window.addEventListener("mousemove", this._onMouseMove);
    window.addEventListener("mouseup", this._onMouseUp);
  };

  private _onMouseMove = (e: MouseEvent): void => {
    if (!this._dragging) return;
    const pos = this.direction === "horizontal" ? e.clientX : e.clientY;
    const delta = pos - this._dragStart;
    const deltaRatio = delta / this._containerSize;
    this._ratio = Math.min(0.9, Math.max(0.1, this._ratioAtDragStart + deltaRatio));
  };

  private _onMouseUp = (): void => {
    this._dragging = false;
    window.removeEventListener("mousemove", this._onMouseMove);
    window.removeEventListener("mouseup", this._onMouseUp);
    if (this.storageKey) {
      localStorage.setItem(`split-pane:${this.storageKey}`, String(this._ratio));
    }
  };

  override render() {
    const startSize = `${this._ratio * 100}%`;
    const endSize = `${(1 - this._ratio) * 100}%`;

    const isH = this.direction !== "vertical";
    const startStyle = isH
      ? `width: ${startSize}; flex-shrink: 0;`
      : `height: ${startSize}; flex-shrink: 0;`;
    const endStyle = isH
      ? `width: ${endSize}; flex-shrink: 0;`
      : `height: ${endSize}; flex-shrink: 0;`;

    return html`
      <div class="pane" style=${startStyle}>
        <slot name="start"></slot>
      </div>
      <div
        class="divider ${this._dragging ? "dragging" : ""}"
        @mousedown=${this._onDividerMouseDown}
      ></div>
      <div class="pane" style=${endStyle}>
        <slot name="end"></slot>
      </div>
    `;
  }
}

declare global {
  interface HTMLElementTagNameMap {
    "split-pane": SplitPane;
  }
}
