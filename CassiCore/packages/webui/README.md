# CassiCore WebUI

Tightly integrated web interface for the CassiCore daemon.

## Overview

Forked from `pi-mono/packages/web-ui` with deep integration into CassiCore's architecture. This is not a generic chat UI—it's purpose-built for CassiCore's unique features.

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    Browser (WebUI)                           │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────┐  │
│  │ ChatPanel   │  │ Dialectic   │  │ Memory Explorer     │  │
│  │ (messages)  │  │ Panel       │  │ (search/browse)     │  │
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
└──────────────────────────────────────────────────────────────┘
```

## Key Features

### 1. Dialectic Visualization
- Real-time Yang/Yin/Synthesis display
- Streaming updates as CassiCore reasons
- Collapsible panels with status indicators

### 2. Memory Explorer
- Browse `~/.cassicore/memory/` directory
- Semantic search across memories
- Direct file viewing and editing

### 3. Subagent Monitor
- Spawn and monitor subagents
- View subagent logs and output
- Real-time status updates

### 4. Provider Management
- Dynamic provider switching
- Health monitoring
- Fallback chain visualization

## Integration Points

| Feature | CassiCore Integration |
|---------|----------------------|
| Backend | Admin API via Unix socket |
| Real-time | WebSocket bridge (port 7433) |
| Storage | SQLite (sessions.db, memory.db) |
| Config | `~/.cassicore/config.json` |
| Dialectic | Native dialectic stream |
| Memory | Direct memory access |

## Quick Start

### 1. Install Dependencies
```bash
cd /home/valerie/workspaces/cassicore/webui
npm install
```

### 2. Start WebSocket Bridge
```bash
npm run bridge
# or
npx tsx server/bridge.ts
```

### 3. Start Development Server
```bash
npm run dev
```

### 4. Open Example App
```bash
open example/cassicore-app/index.html
# or serve with any static server
npx serve example/cassicore-app
```

## Components

### `cassicore-chat-panel`
Main chat interface with integrated sidebar for dialectic/memory/subagents.

```html
<cassicore-chat-panel
  .client="${adminClient}"
  .sessionId="${sessionId}"
>
</cassicore-chat-panel>
```

### `dialectic-panel`
Visualizes Yang/Yin/Synthesis reasoning in real-time.

```html
<dialectic-panel
  .sessionId="${sessionId}"
  .client="${adminClient}"
>
</dialectic-panel>
```

### `memory-explorer`
Browse and search CassiCore's memory system.

```html
<memory-explorer
  .client="${adminClient}"
  rootPath="~/.cassicore/memory"
>
</memory-explorer>
```

### `CassiCoreAdminClient`
TypeScript client for Admin API.

```typescript
import { CassiCoreAdminClient } from '@cassicore/webui/cassicore';

const client = new CassiCoreAdminClient('~/.cassicore/admin.sock');

// Health check
const health = await client.getHealth();

// Sessions
const sessions = await client.listSessions();
const session = await client.createSession({
  agentId: 'valerie',
  thinking: 'medium'
});

// Send message
await client.sendMessage(session.id, {
  role: 'user',
  content: 'Hello CassiCore!'
});

// Stream dialectic
for await (const update of client.streamDialectic(session.id)) {
  console.log(update.type, update.content);
}

// Search memory
const results = await client.searchMemory('semantic query', {
  limit: 10,
  threshold: 0.7
});

// Spawn subagent
const subagent = await client.spawnSubagent(
  'Research quantum computing',
  session.id,
  { thinking: 'high' }
);
```

## File Structure

```
webui/
├── src/
│   ├── cassicore/              # CassiCore-specific code
│   │   ├── admin-client.ts     # Admin API client
│   │   ├── dialectic-panel.ts  # Dialectic visualization
│   │   ├── memory-explorer.ts  # Memory browser/search
│   │   ├── cassicore-chat-panel.ts  # Main chat UI
│   │   └── index.ts            # Exports
│   └── core/                   # (from pi-web-ui)
├── server/
│   └── bridge.ts               # WebSocket bridge server
├── example/
│   └── cassicore-app/          # Example application
│       └── index.html
├── package.json
└── README.md
```

## Comparison: pi-web-ui vs CassiCore WebUI

| Aspect | pi-web-ui | CassiCore WebUI |
|--------|-----------|-----------------|
| Purpose | Generic AI chat | CassiCore-specific |
| Backend | pi-agent-core | CassiCore daemon |
| Dialectic | ❌ None | ✅ Native support |
| Memory | ❌ None | ✅ Full integration |
| Subagents | ❌ None | ✅ Spawn/monitor |
| Providers | Static config | Dynamic switching |
| Storage | IndexedDB | SQLite |
| Real-time | Polling | WebSocket |

## Roadmap

### Phase 1: Core (Complete)
- ✅ Admin API client
- ✅ WebSocket bridge
- ✅ Dialectic panel
- ✅ Memory explorer
- ✅ Basic chat UI

### Phase 2: Advanced Features
- 🔄 Subagent monitor
- 🔄 Provider switcher
- 🔄 System health dashboard
- 🔄 File attachments
- 🔄 Artifacts (HTML, SVG)

### Phase 3: Polish
- ⏳ Mobile responsiveness
- ⏳ Dark mode
- ⏳ Keyboard shortcuts
- ⏳ Customizable layouts

## License

MIT
