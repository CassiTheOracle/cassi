/**
 * CassiCore Chat Panel
 *
 * Adapted from pi-web-ui's ChatPanel to use CassiCore Admin API
 * Adds dialectic, memory, and subagent integration
 */

import { LitElement, html, css } from 'lit';
import { property, state } from 'lit/decorators.js';
import {
  CassiCoreAdminClient,
  Session,
  Message,
  DialecticState,
} from './admin-client.js';
import { DialecticPanel } from './dialectic-panel.js';
import { MemoryExplorer } from './memory-explorer.js';

export class CassiCoreChatPanel extends LitElement {
  static styles = css`
    :host {
      display: block;
      height: 100%;
      font-family: system-ui, -apple-system, sans-serif;
    }

    .chat-container {
      display: flex;
      flex-direction: column;
      height: 100%;
      background: #f8fafc;
    }

    .main-area {
      display: flex;
      flex: 1;
      overflow: hidden;
    }

    .chat-area {
      flex: 1;
      display: flex;
      flex-direction: column;
      min-width: 0;
    }

    .sidebar {
      width: 350px;
      border-left: 1px solid #e2e8f0;
      background: white;
      overflow-y: auto;
      display: flex;
      flex-direction: column;
    }

    .tabs {
      display: flex;
      border-bottom: 1px solid #e2e8f0;
    }

    .tab {
      flex: 1;
      padding: 12px;
      text-align: center;
      cursor: pointer;
      font-size: 13px;
      font-weight: 500;
      color: #64748b;
      transition: all 0.2s;
    }

    .tab:hover {
      background: #f1f5f9;
    }

    .tab.active {
      color: #6366f1;
      border-bottom: 2px solid #6366f1;
    }

    .sidebar-content {
      flex: 1;
      overflow-y: auto;
    }

    .messages {
      flex: 1;
      overflow-y: auto;
      padding: 16px;
      display: flex;
      flex-direction: column;
      gap: 12px;
    }

    .message {
      display: flex;
      gap: 12px;
      max-width: 80%;
    }

    .message.user {
      align-self: flex-end;
      flex-direction: row-reverse;
    }

    .message-avatar {
      width: 32px;
      height: 32px;
      border-radius: 50%;
      display: flex;
      align-items: center;
      justify-content: center;
      font-size: 14px;
      flex-shrink: 0;
    }

    .message.user .message-avatar {
      background: #6366f1;
    }

    .message.assistant .message-avatar {
      background: #f3f4f6;
    }

    .message-content {
      background: white;
      padding: 12px 16px;
      border-radius: 12px;
      box-shadow: 0 1px 2px rgba(0, 0, 0, 0.05);
      line-height: 1.5;
    }

    .message.user .message-content {
      background: #6366f1;
      color: white;
    }

    .input-area {
      display: flex;
      gap: 12px;
      padding: 16px;
      background: white;
      border-top: 1px solid #e2e8f0;
    }

    .message-input {
      flex: 1;
      padding: 12px 16px;
      border: 1px solid #d1d5db;
      border-radius: 8px;
      font-size: 14px;
      resize: none;
      min-height: 48px;
      max-height: 120px;
    }

    .message-input:focus {
      outline: none;
      border-color: #6366f1;
      box-shadow: 0 0 0 3px rgba(99, 102, 241, 0.1);
    }

    .send-button {
      background: #6366f1;
      color: white;
      border: none;
      padding: 12px 24px;
      border-radius: 8px;
      font-size: 14px;
      font-weight: 500;
      cursor: pointer;
      transition: background 0.2s;
    }

    .send-button:hover {
      background: #4f46e5;
    }

    .send-button:disabled {
      background: #a5b4fc;
      cursor: not-allowed;
    }

    .toolbar {
      display: flex;
      gap: 8px;
      padding: 8px 16px;
      background: white;
      border-bottom: 1px solid #e2e8f0;
    }

    .toolbar-button {
      background: #f1f5f9;
      border: none;
      padding: 6px 12px;
      border-radius: 6px;
      font-size: 12px;
      cursor: pointer;
      transition: all 0.2s;
    }

    .toolbar-button:hover {
      background: #e2e8f0;
    }

    .toolbar-button.active {
      background: #e0e7ff;
      color: #3730a3;
    }

    .empty-state {
      display: flex;
      flex-direction: column;
      align-items: center;
      justify-content: center;
      padding: 48px;
      color: #6b7280;
      text-align: center;
    }
  `;

  @property({ type: Object }) client: CassiCoreAdminClient | null = null;
  @property({ type: String }) sessionId: string | null = null;

  @state() private messages: Message[] = [];
  @state() private inputText: string = '';
  @state() private isLoading: boolean = false;
  @state() private activeTab: 'dialectic' | 'memory' | 'subagents' = 'dialectic';
  @state() private showDialectic: boolean = true;
  @state() private showMemory: boolean = false;

  private messageStream: ReadableStreamDefaultReader | null = null;

  connectedCallback() {
    super.connectedCallback();
    if (this.sessionId) {
      this.loadMessages();
    }
  }

  private async loadMessages() {
    if (!this.client || !this.sessionId) return;
    try {
      this.messages = await this.client.getMessages(this.sessionId, 50);
    } catch (error) {
      console.error('Failed to load messages:', error);
    }
  }

  private async sendMessage() {
    if (!this.inputText.trim() || !this.client || !this.sessionId) return;

    const message: Message = {
      role: 'user',
      content: this.inputText,
      timestamp: new Date().toISOString(),
    };

    this.messages = [...this.messages, message];
    this.inputText = '';
    this.isLoading = true;

    try {
      await this.client.sendMessage(this.sessionId, message);
      // Poll for response
      await this.pollForResponse();
    } catch (error) {
      console.error('Failed to send message:', error);
    } finally {
      this.isLoading = false;
    }
  }

  private async pollForResponse() {
    if (!this.client || !this.sessionId) return;

    // Poll for new messages
    const initialCount = this.messages.length;
    let attempts = 0;
    const maxAttempts = 60; // 30 seconds with 500ms delay

    while (attempts < maxAttempts) {
      await new Promise((resolve) => setTimeout(resolve, 500));
      const messages = await this.client.getMessages(this.sessionId, 50);

      if (messages.length > initialCount) {
        this.messages = messages;
        break;
      }

      attempts++;
    }
  }

  private handleInputKeydown(e: KeyboardEvent) {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      this.sendMessage();
    }
  }

  private toggleDialectic() {
    this.showDialectic = !this.showDialectic;
  }

  private toggleMemory() {
    this.showMemory = !this.showMemory;
  }

  private renderSidebar() {
    return html`
      <div class="sidebar">
        <div class="tabs">
          <div
            class="tab ${this.activeTab === 'dialectic' ? 'active' : ''}"
            @click=${() => (this.activeTab = 'dialectic')}
          >
            🧠 Dialectic
          </div>
          <div
            class="tab ${this.activeTab === 'memory' ? 'active' : ''}"
            @click=${() => (this.activeTab = 'memory')}
          >
            📝 Memory
          </div>
          <div
            class="tab ${this.activeTab === 'subagents' ? 'active' : ''}"
            @click=${() => (this.activeTab = 'subagents')}
          >
            🤖 Subagents
          </div>
        </div>
        <div class="sidebar-content">
          ${this.activeTab === 'dialectic' && this.sessionId
            ? html`
                <dialectic-panel
                  .sessionId=${this.sessionId}
                  .client=${this.client}
                ></dialectic-panel>
              `
            : ''}
          ${this.activeTab === 'memory'
            ? html` <memory-explorer .client=${this.client}></memory-explorer> `
            : ''}
          ${this.activeTab === 'subagents'
            ? html`
                <div style="padding: 16px;">
                  <p>Subagent monitor coming soon...</p>
                </div>
              `
            : ''}
        </div>
      </div>
    `;
  }

  render() {
    return html`
      <div class="chat-container">
        <div class="toolbar">
          <button
            class="toolbar-button ${this.showDialectic ? 'active' : ''}"
            @click=${this.toggleDialectic}
          >
            🧠 Dialectic
          </button>
          <button
            class="toolbar-button ${this.showMemory ? 'active' : ''}"
            @click=${this.toggleMemory}
          >
            📝 Memory
          </button>
        </div>

        <div class="main-area">
          <div class="chat-area">
            <div class="messages">
              ${this.messages.length === 0
                ? html`
                    <div class="empty-state">
                      <p>No messages yet</p>
                      <p style="font-size: 13px;">
                        Start a conversation with CassiCore
                      </p>
                    </div>
                  `
                : this.messages.map(
                    (msg) => html`
                      <div class="message ${msg.role}">
                        <div class="message-avatar">
                          ${msg.role === 'user' ? '👤' : '🤖'}
                        </div>
                        <div class="message-content">${msg.content}</div>
                      </div>
                    `
                  )}
            </div>

            <div class="input-area">
              <textarea
                class="message-input"
                placeholder="Type your message..."
                .value=${this.inputText}
                @input=${(e: Event) =>
                  (this.inputText = (e.target as HTMLTextAreaElement).value)
                }
                @keydown=${this.handleInputKeydown}
              ></textarea>
              <button
                class="send-button"
                @click=${this.sendMessage}
                ?disabled=${this.isLoading || !this.inputText.trim()}
              >
                ${this.isLoading ? 'Sending...' : 'Send'}
              </button>
            </div>
          </div>

          ${this.showDialectic ? this.renderSidebar() : ''}
        </div>
      </div>
    `;
  }
}

customElements.define('cassicore-chat-panel', CassiCoreChatPanel);
