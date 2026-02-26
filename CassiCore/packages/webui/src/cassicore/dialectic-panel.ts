/**
 * Dialectic Panel Component
 *
 * Visualizes Yang/Yin/Synthesis in real-time
 * Streams updates from CassiCore daemon
 */

import { LitElement, html, css } from 'lit';
import { property, state } from 'lit/decorators.js';
import {
  CassiCoreAdminClient,
  DialecticState,
  DialecticUpdate,
} from './admin-client.js';

export class DialecticPanel extends LitElement {
  static styles = css`
    :host {
      display: block;
      font-family: system-ui, -apple-system, sans-serif;
    }

    .dialectic-container {
      display: flex;
      flex-direction: column;
      gap: 12px;
      padding: 16px;
      background: #f8fafc;
      border-radius: 8px;
      border: 1px solid #e2e8f0;
    }

    .header {
      display: flex;
      justify-content: space-between;
      align-items: center;
      font-weight: 600;
      color: #1e293b;
    }

    .turn-indicator {
      font-size: 12px;
      color: #64748b;
      background: #e2e8f0;
      padding: 2px 8px;
      border-radius: 12px;
    }

    .perspectives {
      display: grid;
      grid-template-columns: 1fr 1fr;
      gap: 12px;
    }

    .perspective {
      background: white;
      border-radius: 6px;
      padding: 12px;
      border: 2px solid transparent;
      transition: all 0.2s ease;
    }

    .perspective.yang {
      border-color: #f59e0b;
    }

    .perspective.yin {
      border-color: #3b82f6;
    }

    .perspective.active {
      box-shadow: 0 0 0 3px rgba(99, 102, 241, 0.1);
    }

    .perspective-header {
      display: flex;
      align-items: center;
      gap: 8px;
      font-weight: 600;
      margin-bottom: 8px;
      font-size: 14px;
    }

    .perspective-header.yang {
      color: #b45309;
    }

    .perspective-header.yin {
      color: #1d4ed8;
    }

    .perspective-icon {
      width: 20px;
      height: 20px;
      border-radius: 50%;
      display: flex;
      align-items: center;
      justify-content: center;
      font-size: 12px;
    }

    .perspective-icon.yang {
      background: #fef3c7;
    }

    .perspective-icon.yin {
      background: #dbeafe;
    }

    .perspective-content {
      font-size: 13px;
      line-height: 1.5;
      color: #334155;
      max-height: 150px;
      overflow-y: auto;
      white-space: pre-wrap;
    }

    .perspective-content.streaming {
      animation: pulse 1.5s ease-in-out infinite;
    }

    @keyframes pulse {
      0%,
      100% {
        opacity: 1;
      }
      50% {
        opacity: 0.6;
      }
    }

    .synthesis {
      background: linear-gradient(135deg, #f3e8ff 0%, #e0e7ff 100%);
      border-radius: 6px;
      padding: 16px;
      border: 2px solid #8b5cf6;
    }

    .synthesis-header {
      display: flex;
      align-items: center;
      gap: 8px;
      font-weight: 700;
      color: #6b21a8;
      margin-bottom: 12px;
      font-size: 14px;
    }

    .synthesis-content {
      font-size: 14px;
      line-height: 1.6;
      color: #4c1d95;
      white-space: pre-wrap;
    }

    .status-bar {
      display: flex;
      align-items: center;
      gap: 8px;
      font-size: 12px;
      color: #64748b;
      margin-top: 8px;
    }

    .status-indicator {
      width: 8px;
      height: 8px;
      border-radius: 50%;
      background: #94a3b8;
      transition: background 0.3s ease;
    }

    .status-indicator.observing {
      background: #3b82f6;
      animation: blink 1s infinite;
    }

    .status-indicator.synthesizing {
      background: #8b5cf6;
      animation: blink 0.5s infinite;
    }

    .status-indicator.complete {
      background: #10b981;
    }

    @keyframes blink {
      0%,
      100% {
        opacity: 1;
      }
      50% {
        opacity: 0.3;
      }
    }

    .toggle-button {
      background: #6366f1;
      color: white;
      border: none;
      padding: 6px 12px;
      border-radius: 4px;
      font-size: 12px;
      cursor: pointer;
      transition: background 0.2s;
    }

    .toggle-button:hover {
      background: #4f46e5;
    }

    .collapsed {
      display: none;
    }
  `;

  @property({ type: String }) sessionId: string = '';
  @property({ type: Object }) client: CassiCoreAdminClient | null = null;

  @state() private yang: string = '';
  @state() private yin: string = '';
  @state() private synthesis: string = '';
  @state() private status: 'observing' | 'synthesizing' | 'complete' = 'complete';
  @state() private turn: number = 0;
  @state() private isExpanded: boolean = true;
  @state() private activePerspective: 'yang' | 'yin' | null = null;
  @state() private isStreaming: boolean = false;

  private abortController: AbortController | null = null;

  connectedCallback() {
    super.connectedCallback();
    if (this.sessionId) {
      this.startStreaming();
    }
  }

  disconnectedCallback() {
    super.disconnectedCallback();
    this.stopStreaming();
  }

  updated(changedProperties: Map<string, unknown>) {
    if (changedProperties.has('sessionId') && this.sessionId) {
      this.stopStreaming();
      this.startStreaming();
    }
  }

  private async startStreaming() {
    if (!this.client || !this.sessionId) return;

    this.abortController = new AbortController();
    this.isStreaming = true;

    try {
      // Get initial state
      const initialState = await this.client.getDialecticState(this.sessionId);
      this.updateFromState(initialState);

      // Stream updates
      for await (const update of this.client.streamDialectic(this.sessionId)) {
        if (this.abortController?.signal.aborted) break;
        this.handleUpdate(update);
      }
    } catch (error) {
      console.error('Dialectic streaming error:', error);
      this.isStreaming = false;
    }
  }

  private stopStreaming() {
    this.abortController?.abort();
    this.abortController = null;
    this.isStreaming = false;
  }

  private updateFromState(state: DialecticState) {
    this.yang = state.yang;
    this.yin = state.yin;
    this.synthesis = state.synthesis;
    this.status = state.status;
    this.turn = state.turn;
  }

  private handleUpdate(update: DialecticUpdate) {
    switch (update.type) {
      case 'yang':
        this.yang = update.content;
        this.activePerspective = 'yang';
        break;
      case 'yin':
        this.yin = update.content;
        this.activePerspective = 'yin';
        break;
      case 'synthesis':
        this.synthesis = update.content;
        this.activePerspective = null;
        break;
      case 'status':
        this.status = update.content as 'observing' | 'synthesizing' | 'complete';
        if (update.content === 'complete') {
          this.activePerspective = null;
        }
        break;
    }
    this.turn = update.turn;
  }

  private toggleExpanded() {
    this.isExpanded = !this.isExpanded;
  }

  private getStatusText(): string {
    switch (this.status) {
      case 'observing':
        return this.activePerspective === 'yang'
          ? 'Yang observing...'
          : 'Yin observing...';
      case 'synthesizing':
        return 'Synthesizing...';
      case 'complete':
        return 'Complete';
      default:
        return 'Idle';
    }
  }

  render() {
    return html`
      <div class="dialectic-container">
        <div class="header">
          <span>🧠 Dialectic Reasoning</span>
          <div>
            <span class="turn-indicator">Turn ${this.turn}</span>
            <button class="toggle-button" @click=${this.toggleExpanded}>
              ${this.isExpanded ? 'Collapse' : 'Expand'}
            </button>
          </div>
        </div>

        ${this.isExpanded
          ? html`
              <div class="perspectives">
                <div
                  class="perspective yang ${this.activePerspective === 'yang'
                    ? 'active'
                    : ''}"
                >
                  <div class="perspective-header yang">
                    <span class="perspective-icon yang">☀️</span>
                    <span>Yang (Analysis)</span>
                  </div>
                  <div
                    class="perspective-content ${this.activePerspective ===
                      'yang' && this.status === 'observing'
                      ? 'streaming'
                      : ''}"
                  >
                    ${this.yang || 'Waiting for input...'}
                  </div>
                </div>

                <div
                  class="perspective yin ${this.activePerspective === 'yin'
                    ? 'active'
                    : ''}"
                >
                  <div class="perspective-header yin">
                    <span class="perspective-icon yin">🌙</span>
                    <span>Yin (Intuition)</span>
                  </div>
                  <div
                    class="perspective-content ${this.activePerspective ===
                      'yin' && this.status === 'observing'
                      ? 'streaming'
                      : ''}"
                  >
                    ${this.yin || 'Waiting for input...'}
                  </div>
                </div>
              </div>

              ${this.synthesis
                ? html`
                    <div class="synthesis">
                      <div class="synthesis-header">
                        <span>⚡</span>
                        <span>Synthesis</span>
                      </div>
                      <div class="synthesis-content">${this.synthesis}</div>
                    </div>
                  `
                : ''}
            `
          : ''}

        <div class="status-bar">
          <div class="status-indicator ${this.status}"></div>
          <span>${this.getStatusText()}</span>
          ${this.isStreaming
            ? html`<span style="color: #3b82f6;">● Live</span>`
            : html`<span style="color: #94a3b8;">○ Disconnected</span>`}
        </div>
      </div>
    `;
  }
}

customElements.define('dialectic-panel', DialecticPanel);
