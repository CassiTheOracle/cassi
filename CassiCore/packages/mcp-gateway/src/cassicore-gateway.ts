/**
 * MCP Gateway Server
 *
 * Adds SSE Streaming Integration with Debugging.
 */
import { Server } from '@modelcontextprotocol/sdk/server/index.js';
import { StdioServerTransport } from '@modelcontextprotocol/sdk/server/stdio.js';
import http from 'http';
import { EventBus } from './event-bus.js'; // Importing EventBus for streaming
import { SSEConnectionManager } from './sse-connection-manager.js'; // SSE Connection Utilities

const CASSICORE_URL = process.env.CASSICORE_URL || 'http://localhost:7433';
const logger = console; // Simplified logging for demonstration

/**
 * HTTP Server with SSE Protocol support.
 */
async function startHttpServer() {
  const eventBus = new EventBus(); // SSE Bus Initialization
  const sseManager = new SSEConnectionManager(eventBus); // Connection Manager Setup

  const server = http.createServer(async (req, res) => {
    if (req.url === '/sse/stream' && req.method === 'GET') {
      logger.info('Establishing SSE connection...');
      sseManager.establishConnection(req, res); // Delegate to SSE Manager

      // Emit a test event to verify the system
      setTimeout(() => {
        eventBus.emit('test-stream', { data: 'Test message' });
        logger.info('Test event emitted to SSE connection');
      }, 1000);
      return;
    }

    res.statusCode = 404;
    res.end('Not Found');
  });

  // Start Listening on Port 3000
  const port = 3000;
  server.listen(port, () => {
    console.log(`HTTP/SSE Server is running at http://localhost:${port}`);
  });

  logger.info('SSE Server Initialized');
}

// Start Gateway in HTTP/SSE Mode
if (process.argv.includes('--http')) {
  startHttpServer();
} else {
  // Default stdio Mode
  const stdioTransport = new StdioServerTransport({ logger });
  const server = new Server(stdioTransport, { logger });
  server.loadToolDefinitions(getAllTools()); // Loaded tools from registry
  server.start();
}