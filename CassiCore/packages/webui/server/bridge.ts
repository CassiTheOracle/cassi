/**
 * CassiCore WebSocket Bridge Server
 *
 * Bridges CassiCore's Unix socket Admin API to WebSocket
 * Enables real-time communication with browser UI
 */

import { WebSocketServer, WebSocket } from 'ws';
import { createServer } from 'http';
import { CassiCoreAdminClient } from '../src/cassicore/admin-client.js';

interface BridgeConfig {
  port?: number;
  cassicoreSocketPath?: string;
  allowedOrigins?: string[];
}

interface ClientSession {
  ws: WebSocket;
  subscribedSessions: Set<string>;
  subscribedDialectic: string | null;
}

export class CassiCoreWebSocketBridge {
  private wss: WebSocketServer;
  private adminClient: CassiCoreAdminClient;
  private clients: Map<WebSocket, ClientSession> = new Map();
  private config: BridgeConfig;

  constructor(config: BridgeConfig = {}) {
    this.config = {
      port: 7433,
      cassicoreSocketPath: '~/.cassicore/admin.sock',
      allowedOrigins: ['http://localhost:3000', 'http://localhost:5173'],
      ...config,
    };

    this.adminClient = new CassiCoreAdminClient(this.config.cassicoreSocketPath);
  }

  async start(): Promise<void> {
    // Create HTTP server
    const server = createServer((req, res) => {
      // Handle CORS preflight
      if (req.method === 'OPTIONS') {
        this.handleCors(req, res);
        return;
      }

      // Health check endpoint
      if (req.url === '/health') {
        res.writeHead(200, { 'Content-Type': 'application/json' });
        res.end(JSON.stringify({ status: 'ok', bridge: 'active' }));
        return;
      }

      res.writeHead(404);
      res.end('Not found');
    });

    // Create WebSocket server
    this.wss = new WebSocketServer({
      server,
      verifyClient: (info, cb) => {
        const origin = info.origin;
        if (
          !this.config.allowedOrigins ||
          this.config.allowedOrigins.includes(origin)
        ) {
          cb(true);
        } else {
          cb(false, 403, 'Origin not allowed');
        }
      },
    });

    this.wss.on('connection', (ws, req) => {
      console.log('Client connected:', req.socket.remoteAddress);
      this.handleConnection(ws);
    });

    // Start polling for dialectic updates
    this.startDialecticPolling();

    return new Promise((resolve) => {
      server.listen(this.config.port, () => {
        console.log(
          `CassiCore WebSocket Bridge listening on port ${this.config.port}`
        );
        resolve();
      });
    });
  }

  private handleCors(req: any, res: any): void {
    const origin = req.headers.origin;
    if (
      !this.config.allowedOrigins ||
      this.config.allowedOrigins.includes(origin)
    ) {
      res.setHeader('Access-Control-Allow-Origin', origin);
    }
    res.setHeader('Access-Control-Allow-Methods', 'GET, POST, OPTIONS');
    res.setHeader('Access-Control-Allow-Headers', 'Content-Type');
    res.writeHead(200);
    res.end();
  }

  private handleConnection(ws: WebSocket): void {
    const session: ClientSession = {
      ws,
      subscribedSessions: new Set(),
      subscribedDialectic: null,
    };
    this.clients.set(ws, session);

    ws.on('message', async (data) => {
      try {
        const message = JSON.parse(data.toString());
        await this.handleMessage(ws, session, message);
      } catch (error) {
        console.error('Message handling error:', error);
        this.sendError(ws, 'Invalid message format');
      }
    });

    ws.on('close', () => {
      console.log('Client disconnected');
      this.clients.delete(ws);
    });

    ws.on('error', (error) => {
      console.error('WebSocket error:', error);
    });

    // Send welcome message
    this.send(ws, { type: 'connected', timestamp: Date.now() });
  }

  private async handleMessage(
    ws: WebSocket,
    session: ClientSession,
    message: any
  ): Promise<void> {
    const { type, payload, id } = message;

    switch (type) {
      case 'health': {
        const health = await this.adminClient.getHealth();
        this.send(ws, { type: 'health', payload: health, id });
        break;
      }

      case 'sessions.list': {
        const sessions = await this.adminClient.listSessions();
        this.send(ws, { type: 'sessions.list', payload: sessions, id });
        break;
      }

      case 'sessions.get': {
        const sessionData = await this.adminClient.getSession(payload.sessionId);
        this.send(ws, { type: 'sessions.get', payload: sessionData, id });
        break;
      }

      case 'sessions.create': {
        const newSession = await this.adminClient.createSession(payload.config);
        this.send(ws, { type: 'sessions.create', payload: newSession, id });
        break;
      }

      case 'sessions.sendMessage': {
        await this.adminClient.sendMessage(payload.sessionId, payload.message);
        this.send(ws, { type: 'sessions.sendMessage', payload: { success: true }, id });
        break;
      }

      case 'sessions.subscribe': {
        session.subscribedSessions.add(payload.sessionId);
        this.send(ws, {
          type: 'sessions.subscribe',
          payload: { sessionId: payload.sessionId },
          id,
        });
        break;
      }

      case 'sessions.unsubscribe': {
        session.subscribedSessions.delete(payload.sessionId);
        this.send(ws, {
          type: 'sessions.unsubscribe',
          payload: { sessionId: payload.sessionId },
          id,
        });
        break;
      }

      case 'dialectic.get': {
        const state = await this.adminClient.getDialecticState(payload.sessionId);
        this.send(ws, { type: 'dialectic.get', payload: state, id });
        break;
      }

      case 'dialectic.subscribe': {
        session.subscribedDialectic = payload.sessionId;
        this.send(ws, {
          type: 'dialectic.subscribe',
          payload: { sessionId: payload.sessionId },
          id,
        });
        break;
      }

      case 'dialectic.unsubscribe': {
        session.subscribedDialectic = null;
        this.send(ws, { type: 'dialectic.unsubscribe', payload: {}, id });
        break;
      }

      case 'memory.search': {
        const results = await this.adminClient.searchMemory(payload.query, payload.options);
        this.send(ws, { type: 'memory.search', payload: results, id });
        break;
      }

      case 'subagents.list': {
        const subagents = await this.adminClient.listSubagents(payload.parentSessionId);
        this.send(ws, { type: 'subagents.list', payload: subagents, id });
        break;
      }

      case 'subagents.spawn': {
        const subagent = await this.adminClient.spawnSubagent(
          payload.task,
          payload.parentSessionId,
          payload.config
        );
        this.send(ws, { type: 'subagents.spawn', payload: subagent, id });
        break;
      }

      case 'providers.list': {
        const providers = await this.adminClient.listProviders();
        this.send(ws, { type: 'providers.list', payload: providers, id });
        break;
      }

      case 'providers.switch': {
        await this.adminClient.switchProvider(
          payload.sessionId,
          payload.providerId,
          payload.model
        );
        this.send(ws, { type: 'providers.switch', payload: { success: true }, id });
        break;
      }

      default:
        this.sendError(ws, `Unknown message type: ${type}`, id);
    }
  }

  private send(ws: WebSocket, data: any): void {
    if (ws.readyState === WebSocket.OPEN) {
      ws.send(JSON.stringify(data));
    }
  }

  private sendError(ws: WebSocket, error: string, id?: string): void {
    this.send(ws, { type: 'error', payload: { error }, id });
  }

  private broadcast(data: any, filter?: (session: ClientSession) => boolean): void {
    for (const [ws, session] of this.clients) {
      if (!filter || filter(session)) {
        this.send(ws, data);
      }
    }
  }

  private startDialecticPolling(): void {
    // Poll every 500ms for dialectic updates
    setInterval(async () => {
      const subscribedSessions = new Set<string>();

      // Collect all subscribed dialectic sessions
      for (const session of this.clients.values()) {
        if (session.subscribedDialectic) {
          subscribedSessions.add(session.subscribedDialectic);
        }
      }

      // Fetch updates for each subscribed session
      for (const sessionId of subscribedSessions) {
        try {
          const state = await this.adminClient.getDialecticState(sessionId);
          this.broadcast(
            {
              type: 'dialectic.update',
              payload: state,
              sessionId,
            },
            (s) => s.subscribedDialectic === sessionId
          );
        } catch (error) {
          console.error(`Failed to fetch dialectic state for ${sessionId}:`, error);
        }
      }
    }, 500);
  }

  stop(): void {
    this.wss?.close();
  }
}

// CLI entry point
if (import.meta.main) {
  const port = parseInt(process.env.CASSICORE_BRIDGE_PORT || '7433');
  const bridge = new CassiCoreWebSocketBridge({ port });

  bridge.start().catch((error) => {
    console.error('Failed to start bridge:', error);
    process.exit(1);
  });

  process.on('SIGINT', () => {
    console.log('Shutting down bridge...');
    bridge.stop();
    process.exit(0);
  });
}
