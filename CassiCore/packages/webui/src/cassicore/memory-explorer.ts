/**
 * Memory Explorer Component
 *
 * Browse and search CassiCore's memory system
 * Visualizes memory/ directory and enables semantic search
 */

import { LitElement, html, css } from 'lit';
import { property, state } from 'lit/decorators.js';
import { CassiCoreAdminClient, MemoryResult, SearchOptions } from './admin-client.js';

interface MemoryFile {
  path: string;
  name: string;
  lastModified: Date;
  size: number;
  content?: string;
}

interface MemoryTreeNode {
  name: string;
  path: string;
  type: 'file' | 'directory';
  children?: MemoryTreeNode[];
  lastModified?: Date;
}

export class MemoryExplorer extends LitElement {
  static styles = css`
    :host {
      display: block;
      font-family: system-ui, -apple-system, sans-serif;
      height: 100%;
    }

    .explorer-container {
      display: flex;
      flex-direction: column;
      height: 100%;
      background: #f8fafc;
      border-radius: 8px;
      border: 1px solid #e2e8f0;
      overflow: hidden;
    }

    .header {
      display: flex;
      justify-content: space-between;
      align-items: center;
      padding: 12px 16px;
      background: white;
      border-bottom: 1px solid #e2e8f0;
    }

    .header-title {
      font-weight: 600;
      color: #1e293b;
      display: flex;
      align-items: center;
      gap: 8px;
    }

    .search-box {
      display: flex;
      gap: 8px;
      padding: 12px 16px;
      background: white;
      border-bottom: 1px solid #e2e8f0;
    }

    .search-input {
      flex: 1;
      padding: 8px 12px;
      border: 1px solid #d1d5db;
      border-radius: 6px;
      font-size: 14px;
    }

    .search-input:focus {
      outline: none;
      border-color: #6366f1;
      box-shadow: 0 0 0 3px rgba(99, 102, 241, 0.1);
    }

    .search-button {
      background: #6366f1;
      color: white;
      border: none;
      padding: 8px 16px;
      border-radius: 6px;
      font-size: 14px;
      cursor: pointer;
      transition: background 0.2s;
    }

    .search-button:hover {
      background: #4f46e5;
    }

    .search-button:disabled {
      background: #a5b4fc;
      cursor: not-allowed;
    }

    .main-content {
      display: flex;
      flex: 1;
      overflow: hidden;
    }

    .tree-panel {
      width: 250px;
      border-right: 1px solid #e2e8f0;
      overflow-y: auto;
      padding: 12px;
      background: white;
    }

    .tree-node {
      display: flex;
      align-items: center;
      gap: 6px;
      padding: 4px 8px;
      border-radius: 4px;
      cursor: pointer;
      font-size: 13px;
      color: #374151;
    }

    .tree-node:hover {
      background: #f3f4f6;
    }

    .tree-node.selected {
      background: #e0e7ff;
      color: #3730a3;
    }

    .tree-node .icon {
      width: 16px;
      text-align: center;
    }

    .tree-children {
      margin-left: 16px;
      border-left: 1px solid #e5e7eb;
      padding-left: 4px;
    }

    .content-panel {
      flex: 1;
      overflow-y: auto;
      padding: 16px;
    }

    .search-results {
      display: flex;
      flex-direction: column;
      gap: 12px;
    }

    .search-result {
      background: white;
      border-radius: 6px;
      padding: 12px;
      border: 1px solid #e5e7eb;
      cursor: pointer;
      transition: all 0.2s;
    }

    .search-result:hover {
      border-color: #6366f1;
      box-shadow: 0 2px 4px rgba(0, 0, 0, 0.05);
    }

    .result-header {
      display: flex;
      justify-content: space-between;
      align-items: center;
      margin-bottom: 8px;
    }

    .result-path {
      font-size: 12px;
      color: #6366f1;
      font-weight: 500;
    }

    .result-score {
      font-size: 11px;
      color: #10b981;
      background: #d1fae5;
      padding: 2px 8px;
      border-radius: 12px;
    }

    .result-content {
      font-size: 13px;
      color: #4b5563;
      line-height: 1.5;
      display: -webkit-box;
      -webkit-line-clamp: 3;
      -webkit-box-orient: vertical;
      overflow: hidden;
    }

    .file-viewer {
      background: white;
      border-radius: 6px;
      border: 1px solid #e5e7eb;
      overflow: hidden;
    }

    .file-header {
      display: flex;
      justify-content: space-between;
      align-items: center;
      padding: 12px 16px;
      background: #f9fafb;
      border-bottom: 1px solid #e5e7eb;
    }

    .file-path {
      font-family: monospace;
      font-size: 13px;
      color: #374151;
    }

    .file-meta {
      font-size: 12px;
      color: #6b7280;
    }

    .file-content {
      padding: 16px;
      font-family: monospace;
      font-size: 13px;
      line-height: 1.6;
      white-space: pre-wrap;
      color: #1f2937;
      max-height: 500px;
      overflow-y: auto;
    }

    .empty-state {
      display: flex;
      flex-direction: column;
      align-items: center;
      justify-content: center;
      padding: 48px 24px;
      color: #6b7280;
      text-align: center;
    }

    .empty-state-icon {
      font-size: 48px;
      margin-bottom: 16px;
    }

    .loading {
      display: flex;
      align-items: center;
      justify-content: center;
      padding: 48px;
      color: #6b7280;
    }

    .spinner {
      width: 20px;
      height: 20px;
      border: 2px solid #e5e7eb;
      border-top-color: #6366f1;
      border-radius: 50%;
      animation: spin 1s linear infinite;
      margin-right: 8px;
    }

    @keyframes spin {
      to {
        transform: rotate(360deg);
      }
    }
  `;

  @property({ type: Object }) client: CassiCoreAdminClient | null = null;
  @property({ type: String }) rootPath: string = '~/.cassicore/memory';

  @state() private tree: MemoryTreeNode | null = null;
  @state() private selectedNode: MemoryTreeNode | null = null;
  @state() private selectedFile: MemoryFile | null = null;
  @state() private searchQuery: string = '';
  @state() private searchResults: MemoryResult[] = [];
  @state() private isSearching: boolean = false;
  @state() private viewMode: 'tree' | 'search' = 'tree';

  connectedCallback() {
    super.connectedCallback();
    this.loadTree();
  }

  private async loadTree() {
    // In a real implementation, this would fetch from the server
    // For now, creating a mock structure
    this.tree = {
      name: 'memory',
      path: this.rootPath,
      type: 'directory',
      children: [
        {
          name: 'daily',
          path: `${this.rootPath}/daily`,
          type: 'directory',
          children: [],
        },
        {
          name: 'projects',
          path: `${this.rootPath}/projects`,
          type: 'directory',
          children: [],
        },
        {
          name: 'people',
          path: `${this.rootPath}/people`,
          type: 'directory',
          children: [],
        },
        {
          name: 'active-context.md',
          path: `${this.rootPath}/active-context.md`,
          type: 'file',
          lastModified: new Date(),
        },
      ],
    };
  }

  private async handleSearch() {
    if (!this.client || !this.searchQuery.trim()) return;

    this.isSearching = true;
    this.viewMode = 'search';

    try {
      const results = await this.client.searchMemory(this.searchQuery, {
        limit: 20,
        threshold: 0.7,
      });
      this.searchResults = results;
    } catch (error) {
      console.error('Search error:', error);
    } finally {
      this.isSearching = false;
    }
  }

  private handleNodeClick(node: MemoryTreeNode) {
    this.selectedNode = node;
    if (node.type === 'file') {
      this.loadFile(node.path);
    }
  }

  private async loadFile(path: string) {
    // In real implementation, fetch from server
    this.selectedFile = {
      path,
      name: path.split('/').pop() || '',
      lastModified: new Date(),
      size: 0,
      content: `# ${path}

This is a sample memory file content.
In the real implementation, this would be fetched from the server.`,
    };
  }

  private renderTree(node: MemoryTreeNode, depth = 0): unknown {
    const isSelected = this.selectedNode?.path === node.path;

    return html`
      <div>
        <div
          class="tree-node ${isSelected ? 'selected' : ''}"
          style="padding-left: ${depth * 12 + 8}px"
          @click=${() => this.handleNodeClick(node)}
        >
          <span class="icon">${node.type === 'directory' ? '📁' : '📄'}</span>
          <span>${node.name}</span>
        </div>
        ${node.children && node.children.length > 0
          ? html`
              <div class="tree-children">
                ${node.children.map((child) => this.renderTree(child, depth + 1))}
              </div>
            `
          : ''}
      </div>
    `;
  }

  private renderSearchResults() {
    if (this.isSearching) {
      return html`
        <div class="loading">
          <div class="spinner"></div>
          Searching...
        </div>
      `;
    }

    if (this.searchResults.length === 0) {
      return html`
        <div class="empty-state">
          <div class="empty-state-icon">🔍</div>
          <p>No results found</p>
          <p style="font-size: 13px;">Try a different search query</p>
        </div>
      `;
    }

    return html`
      <div class="search-results">
        ${this.searchResults.map(
          (result) => html`
            <div class="search-result" @click=${() => this.loadFile(result.source)}>
              <div class="result-header">
                <span class="result-path">${result.source}</span>
                <span class="result-score">${(result.relevance * 100).toFixed(0)}%</span>
              </div>
              <div class="result-content">${result.content}</div>
            </div>
          `
        )}
      </div>
    `;
  }

  private renderFileViewer() {
    if (!this.selectedFile) {
      return html`
        <div class="empty-state">
          <div class="empty-state-icon">📝</div>
          <p>Select a file to view</p>
        </div>
      `;
    }

    return html`
      <div class="file-viewer">
        <div class="file-header">
          <span class="file-path">${this.selectedFile.path}</span>
          <span class="file-meta">
            ${this.selectedFile.lastModified?.toLocaleString()}
          </span>
        </div>
        <div class="file-content">${this.selectedFile.content}</div>
      </div>
    `;
  }

  render() {
    return html`
      <div class="explorer-container">
        <div class="header">
          <div class="header-title">
            <span>🧠</span>
            <span>Memory Explorer</span>
          </div>
        </div>

        <div class="search-box">
          <input
            class="search-input"
            type="text"
            placeholder="Search memories..."
            .value=${this.searchQuery}
            @input=${(e: Event) => (this.searchQuery = (e.target as HTMLInputElement).value)}
            @keydown=${(e: KeyboardEvent) => e.key === 'Enter' && this.handleSearch()}
          />
          <button class="search-button" @click=${this.handleSearch} ?disabled=${this.isSearching}>
            ${this.isSearching ? 'Searching...' : 'Search'}
          </button>
        </div>

        <div class="main-content">
          <div class="tree-panel">
            ${this.tree ? this.renderTree(this.tree) : html`<div class="loading">Loading...</div>`}
          </div>

          <div class="content-panel">
            ${this.viewMode === 'search' ? this.renderSearchResults() : this.renderFileViewer()}
          </div>
        </div>
      </div>
    `;
  }
}

customElements.define('memory-explorer', MemoryExplorer);
