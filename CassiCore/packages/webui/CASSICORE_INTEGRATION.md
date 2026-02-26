# CassiCore WebUI Integration Design

## Overview

Forked from `pi-mono/packages/web-ui` with tight integration into CassiCore's architecture.

## Integration Strategies

### 1. Admin API Integration (Primary)

**CassiCore Endpoint:** `~/.cassicore/admin.sock`

```typescript
// New: CassiCoreAdminClient
class CassiCoreAdminClient {
  private socketPath: string;
  
  // Health & Status
  async getHealth(): Promise<HealthStatus>
  async getStatus(): Promise<SystemStatus>
  
  // Session Management
  async listSessions(): Promise<Session[]>
  async getSession(id: string): Promise<Session>
  async createSession(config: SessionConfig): Promise<Session>
  async sendMessage(sessionId: string, message: Message): Promise<void>
  
  // Dialectic (Yang/Yin/Synthesis)
  async getDialecticState(sessionId: string): Promise<DialecticState>
  async streamDialectic(sessionId: string): AsyncIterable<DialecticUpdate>
  
  // Memory
  async searchMemory(query: string, options?: SearchOptions): Promise<MemoryResult[]>
  async recallContext(sessionId: string): Promise<Context>
  
  // Subagents
  async listSubagents(parentSessionId?: string): Promise<Subagent[]>
  async spawnSubagent(task: string, config?: SubagentConfig): Promise<Subagent>
  
  // Providers
  async listProviders(): Promise<Provider[]>
  async switchProvider(sessionId: string, providerId: string): Promise<void>
}
```

### 2. WebSocket Bridge (Real-time)

**New Component:** `CassiCoreWebSocketBridge`

```typescript
// Bridges Admin API to WebSocket for browser UI
class CassiCoreWebSocketBridge {
  // Forward Admin API calls over WebSocket
  // Enable real-time streaming (dialectic, message streaming)
  // Handle reconnection logic
}
```

### 3. Direct SQLite Access (Read-only)

**Databases:** `~/.cassicore/data/*.db`

```typescript
// Read-only access for:
// - Session history
// - Memory search
// - Error patterns (reflect.db)
// - Continuity state
```

### 4. File System Integration

**Access:**
- `~/.cassicore/config.json` — Read/write configuration
- `~/.cassicore/memory/` — Markdown memories
- `~/workspaces/` — Project access via Serena

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    Browser (WebUI)                           │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────┐  │
│  │ ChatPanel   │  │ Dialectic   │  │ Memory Explorer     │  │
│  │ (messages)  │  │ Visualizer  │  │ (search/browse)     │  │
│  └──────┬──────┘  └──────┬──────┘  └──────────┬──────────┘  │
└─────────┼────────────────┼────────────────────┼─────────────┘
          │                │                    │
          └────────────────┴────────────────────┘
                           │
                    ┌──────▼──────┐
                    │  WebSocket  │
                    │   Bridge    │
                    └──────┬──────┘
                           │
┌──────────────────────────┼──────────────────────────────────┐
│                    CassiCore Daemon                         │
│  ┌───────────────────────┼──────────────────────────────┐   │
│  │                 Admin API (Unix Socket)              │   │
│  │  ┌──────────┬─────────┼──────────┬──────────────┐    │   │
│  │  │ Sessions │ Dialectic│  Memory  │  Subagents   │    │   │
│  │  └──────────┴─────────┴──────────┴──────────────┘    │   │
│  └────────────────────────────────────────────────────────┘   │
└───────────────────────────────────────────────────────────────┘
```

## New CassiCore-Specific Components

### 1. DialecticPanel

Visualizes Yang/Yin/Synthesis in real-time:

```typescript
class DialecticPanel extends LitElement {
  @property() sessionId: string;
  @property() yang: string = '';
  @property() yin: string = '';
  @property() synthesis: string = '';
  
  // Streaming updates via WebSocket
  // Collapsible panels for each perspective
  // Diff highlighting between perspectives
}
```

### 2. MemoryExplorer

Browse and search CassiCore's memory:

```typescript
class MemoryExplorer extends LitElement {
  // Tree view: memory/ directory structure
  // Semantic search across memories
  // Timeline view of memory updates
  // Direct editing with auto-save
}
```

### 3. SubagentMonitor

Real-time subagent tracking:

```typescript
class SubagentMonitor extends LitElement {
  // List active subagents
  // View subagent logs/output
  // Kill/restart subagents
  // Spawn new subagents
}
```

### 4. ProviderSwitcher

Dynamic provider management:

```typescript
class ProviderSwitcher extends LitElement {
  // List available providers
  // Switch mid-conversation
  // Show provider health/status
  // Fallback chain visualization
}
```

### 5. SystemHealthDashboard

Monitor CassiCore health:

```typescript
class SystemHealthDashboard extends LitElement {
  // CPU/Memory usage
  // Event loop lag
  // Plugin health
  // Error rate trends
}
```

## Modified Components (from pi-web-ui)

### ChatPanel → CassiCoreChatPanel

**Changes:**
- Use `CassiCoreAdminClient` instead of `Agent`
- Add dialectic toggle
- Add memory search sidebar
- Add subagent spawn button
- Stream from Admin API instead of direct LLM

### Storage → CassiCoreStorage

**Changes:**
- Use `~/.cassicore/config.json` for settings
- Use SQLite for sessions (not IndexedDB)
- Sync with CassiCore's native storage

## Integration Points

| Feature | pi-web-ui | CassiCore WebUI |
|---------|-----------|-----------------|
| Backend | pi-agent-core | CassiCore Admin API |
| Storage | IndexedDB | SQLite + config.json |
| LLM | Direct API calls | Via CassiCore daemon |
| Sessions | In-memory | Persistent (sessions.db) |
| Memory | None | Full memory system |
| Dialectic | None | Yang/Yin/Synthesis |
| Subagents | None | Spawn/monitor UI |
| Providers | Static config | Dynamic switching |

## Implementation Phases

### Phase 1: Admin API Client (Day 1)
- Create `CassiCoreAdminClient` class
- Implement session management
- Test against running daemon

### Phase 2: WebSocket Bridge (Day 2)
- Create bridge server
- Implement real-time streaming
- Reconnection handling

### Phase 3: Core UI Components (Day 3-4)
- Port ChatPanel to use AdminClient
- Add DialecticPanel
- Basic MemoryExplorer

### Phase 4: Advanced Features (Day 5-7)
- SubagentMonitor
- ProviderSwitcher
- SystemHealthDashboard
- Full integration testing

## File Structure

```
webui/
├── src/
│   ├── cassicore/           # NEW: CassiCore-specific
│   │   ├── admin-client.ts  # Admin API client
│   │   ├── websocket-bridge.ts
│   │   ├── dialectic-panel.ts
│   │   ├── memory-explorer.ts
│   │   ├── subagent-monitor.ts
│   │   ├── provider-switcher.ts
│   │   └── health-dashboard.ts
│   ├── components/          # Modified from pi-web-ui
│   │   └── cassicore-chat-panel.ts
│   ├── core/                # EXISTING: from pi-web-ui
│   │   ├── chat-panel.ts
│   │   ├── storage/
│   │   └── ...
│   └── index.ts             # Re-exports
├── server/                  # NEW: WebSocket bridge server
│   ├── index.ts
│   └── bridge.ts
├── example/                 # MODIFIED: CassiCore example
│   └── cassicore-app/
└── package.json             # MODIFIED: CassiCore deps
```

## Dependencies

**Add:**
- `ws` — WebSocket server
- `better-sqlite3` — SQLite access (optional)
- `@cassicore/types` — Shared types

**Remove (replaced):**
- `@mariozechner/pi-agent-core` → Use Admin API
- `@mariozechner/pi-ai` → Via CassiCore
