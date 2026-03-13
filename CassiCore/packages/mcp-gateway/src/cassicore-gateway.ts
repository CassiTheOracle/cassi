#!/usr/bin/env node
/**
 * CassiCore MCP Gateway Server
 *
 * Exposes CassiCore's tools and capabilities via the Model Context Protocol (MCP).
 * This allows external AI systems (like Qwen-Coder) to use CassiCore's tool ecosystem.
 *
 * Supports:
 * - stdio transport (for direct IDE integration)
 * - HTTP/SSE transport (for remote connections)
 *
 * Usage:
 *   node mcp/cassicore-gateway.ts                    # stdio mode (default)
 *   node mcp/cassicore-gateway.ts --http --port 3000 # HTTP mode
 */

import { Server } from '@modelcontextprotocol/sdk/server/index.js';
import { StdioServerTransport } from '@modelcontextprotocol/sdk/server/stdio.js';
import {
  CallToolRequestSchema,
  ListToolsRequestSchema,
  ListResourcesRequestSchema,
  ReadResourceRequestSchema,
} from '@modelcontextprotocol/sdk/types.js';
import http from 'http';
import fs from 'node:fs';
import path from 'node:path';

// Import domain modules
import {
  GATEWAY_VERSION,
  createLogger,
  fetchWithTimeout,
  formatError,
  formatJsonResponse,
  formatTextResponse,
  // Tool modules
  getCoreTools,
  getIntelligenceTools,
  getDialecticTools,
  getMemoryTools,
  getConfigAdminTools,
  getSessionTools,
  getActionTools,
  getTeamTools,
  getTeamAgentTools,
  // Execution functions
  executeCassiCoreTool,
  executeIntelligenceTool,
  executeDialecticTool,
  executeMemoryTool,
  executeConfigAdminTool,
  executeSessionTool,
  executeActionTool,
  executeTeamTool,
  executeTeamAgentTool,
  // Tool name sets
  INTELLIGENCE_TOOL_NAMES,
  DIALECTIC_TOOL_NAMES,
  MEMORY_TOOL_NAMES,
  CONFIG_ADMIN_TOOL_NAMES,
  SESSION_TOOL_NAMES,
  ACTION_TOOL_NAMES,
  TEAM_TOOL_NAMES,
  TEAM_AGENT_TOOL_NAMES,
} from './gateway/index.js';

// Configuration
const CASSICORE_URL = process.env.CASSICORE_URL || 'http://localhost:7433';

// Logger
const logger = createLogger();

// ═══════════════════════════════════════════════════════════════════════════════
// Security Configuration
// ═══════════════════════════════════════════════════════════════════════════════

/**
 * Load authentication token from config file or environment
 */
function getAuthToken(): string | null {
  // Check environment variable first
  if (process.env.CASSICORE_MCP_TOKEN) {
    return process.env.CASSICORE_MCP_TOKEN;
  }

  // Check config file
  try {
    const configPath = path.join(process.env.HOME || process.env.USERPROFILE || '', '.cassicore', 'config.json');
    if (fs.existsSync(configPath)) {
      const config = JSON.parse(fs.readFileSync(configPath, 'utf8'));
      return config.mcp?.token || null;
    }
  } catch {
    // Config not found or invalid
  }

  return null;
}

const AUTH_TOKEN = getAuthToken();

/**
 * Validate authentication token from request
 */
function validateAuth(req: http.IncomingMessage): boolean {
  if (!AUTH_TOKEN) {
    // No token configured - allow all (local-only mode)
    return true;
  }

  const authHeader = req.headers['authorization'];
  if (!authHeader || Array.isArray(authHeader)) {
    return false;
  }

  return authHeader === `Bearer ${AUTH_TOKEN}`;
}

/**
 * Validate Content-Type header for POST/PUT requests
 */
function validateContentType(req: http.IncomingMessage, expectedType: string = 'application/json'): boolean {
  const contentType = req.headers['content-type'];
  if (!contentType) {
    return false;
  }
  
  // Allow charset specification
  return contentType.toLowerCase().startsWith(expectedType);
}

/**
 * Read request body with size limit
 */
function readBodyWithLimit(req: http.IncomingMessage, maxSize: number = 1024 * 1024): Promise<string> {
  return new Promise((resolve, reject) => {
    let body = '';
    let totalSize = 0;

    req.on('data', chunk => {
      totalSize += chunk.length;
      if (totalSize > maxSize) {
        req.destroy();
        reject(new Error(`Request body exceeds ${maxSize} byte limit`));
        return;
      }
      body += chunk;
    });

    req.on('end', () => resolve(body));
    req.on('error', reject);
  });
}

// ═══════════════════════════════════════════════════════════════════════════════
// Tool Registry
// ═══════════════════════════════════════════════════════════════════════════════

/**
 * Get all available tools from all domains
 */
function getAllTools() {
  return [
    ...getCoreTools(),
    ...getIntelligenceTools(),
    ...getDialecticTools(),
    ...getMemoryTools(),
    ...getConfigAdminTools(),
    ...getSessionTools(),
    ...getActionTools(),
    ...getTeamTools(),
    ...getTeamAgentTools(),
  ];
}

// ═══════════════════════════════════════════════════════════════════════════════
// Tool Execution Router
// ═══════════════════════════════════════════════════════════════════════════════

/**
 * Route a tool call to the appropriate domain handler
 */
async function routeToolCall(name: string, args: any): Promise<{ content: Array<{ type: 'text'; text: string }>; isError?: true }> {
  logger.info('Tool call received', { tool: name, args });

  try {
    // Intelligence introspection tools (return markdown)
    if (INTELLIGENCE_TOOL_NAMES.has(name)) {
      const markdown = await executeIntelligenceTool(CASSICORE_URL, name, args, logger);
      return formatTextResponse(markdown);
    }

    // Dialectic tools (return markdown)
    if (DIALECTIC_TOOL_NAMES.has(name)) {
      const markdown = await executeDialecticTool(CASSICORE_URL, name, args, logger);
      return formatTextResponse(markdown);
    }

    // Core tools (return JSON)
    if (getCoreTools().some(t => t.name === name)) {
      const result = await executeCassiCoreTool(CASSICORE_URL, name, args, logger);
      return formatJsonResponse(result);
    }

    // Memory tools (return JSON)
    if (MEMORY_TOOL_NAMES.has(name)) {
      const result = await executeMemoryTool(CASSICORE_URL, name, args, logger);
      return formatJsonResponse(result);
    }

    // Config/Admin tools (return JSON)
    if (CONFIG_ADMIN_TOOL_NAMES.has(name)) {
      const result = await executeConfigAdminTool(CASSICORE_URL, name, args, logger);
      return formatJsonResponse(result);
    }

    // Session tools (return JSON)
    if (SESSION_TOOL_NAMES.has(name)) {
      const result = await executeSessionTool(CASSICORE_URL, name, args, logger);
      return formatJsonResponse(result);
    }

    // Action tools (return JSON)
    if (ACTION_TOOL_NAMES.has(name)) {
      const result = await executeActionTool(CASSICORE_URL, name, args, logger);
      return formatJsonResponse(result);
    }

    // Team tools (return JSON)
    if (TEAM_TOOL_NAMES.has(name)) {
      const result = await executeTeamTool(CASSICORE_URL, name, args, logger);
      return formatJsonResponse(result);
    }

    // Team agent tools (return JSON)
    if (TEAM_AGENT_TOOL_NAMES.has(name)) {
      const result = await executeTeamAgentTool(CASSICORE_URL, name, args, logger);
      return formatJsonResponse(result);
    }

    // Unknown tool
    throw new Error(`Unknown tool: ${name}`);
  } catch (error: any) {
    logger.error('Tool execution failed', { tool: name, error: String(error) });
    return formatError(error);
  }
}

// ═══════════════════════════════════════════════════════════════════════════════
// MCP Server
// ═══════════════════════════════════════════════════════════════════════════════

/**
 * Create MCP Server
 */
function createServer() {
  const server = new Server(
    {
      name: 'cassicore-gateway',
      version: GATEWAY_VERSION,
    },
    {
      capabilities: {
        tools: {},
        resources: {},
      },
    }
  );

  // List available tools
  server.setRequestHandler(ListToolsRequestSchema, async () => {
    return {
      tools: getAllTools(),
    };
  });

  // Handle tool calls
  server.setRequestHandler(CallToolRequestSchema, async (request) => {
    const { name, arguments: args } = request.params;
    return await routeToolCall(name, args);
  });

  // List resources (files/directories accessible)
  server.setRequestHandler(ListResourcesRequestSchema, async () => {
    return {
      resources: [
        {
          uri: 'cassicore://health',
          name: 'CassiCore Health Status',
          mimeType: 'application/json',
          description: 'Current health and status of CassiCore daemon',
        },
      ],
    };
  });

  // Read resources
  server.setRequestHandler(ReadResourceRequestSchema, async (request) => {
    const { uri } = request.params;

    if (uri === 'cassicore://health') {
      try {
        const response = await fetchWithTimeout(`${CASSICORE_URL}/health`);
        const health = await response.json();
        return {
          contents: [
            {
              uri,
              mimeType: 'application/json',
              text: JSON.stringify(health, null, 2),
            },
          ],
        };
      } catch (error: any) {
        return {
          contents: [
            {
              uri,
              mimeType: 'application/json',
              text: JSON.stringify({ status: 'error', error: error.message }),
            },
          ],
        };
      }
    }

    throw new Error(`Unknown resource: ${uri}`);
  });

  return server;
}

// ═══════════════════════════════════════════════════════════════════════════════
// Transports
// ═══════════════════════════════════════════════════════════════════════════════

/**
 * Start with stdio transport (default for MCP)
 */
async function startStdio() {
  logger.info('Starting CassiCore MCP Gateway (stdio mode)', { url: CASSICORE_URL });

  const server = createServer();
  const transport = new StdioServerTransport();

  await server.connect(transport);

  logger.info('CassiCore MCP Gateway connected and ready');
}

/**
 * Start with HTTP/SSE transport (for remote connections)
 */
async function startHttp(port: number) {
  logger.info('Starting CassiCore MCP Gateway (HTTP mode)', { port, url: CASSICORE_URL });

  const server = createServer();

  // Create HTTP server for SSE transport
  const httpServer = http.createServer(async (req, res) => {
    const url = new URL(req.url || '/', `http://localhost:${port}`);

    // Health endpoint (no auth required)
    if (url.pathname === '/health') {
      try {
        const cassiHealth = await fetchWithTimeout(`${CASSICORE_URL}/health`);
        const cassiStatus = await cassiHealth.json();
        res.writeHead(200, { 'Content-Type': 'application/json' });
        res.end(JSON.stringify({
          status: 'ok',
          gateway: 'cassicore-mcp-gateway',
          version: GATEWAY_VERSION,
          cassicore: cassiStatus,
        }));
      } catch (error: any) {
        res.writeHead(503, { 'Content-Type': 'application/json' });
        res.end(JSON.stringify({
          status: 'error',
          error: error.message,
        }));
      }
      return;
    }

    // Tools endpoint (GET - no auth required for listing)
    if (url.pathname === '/tools' && req.method === 'GET') {
      res.writeHead(200, { 'Content-Type': 'application/json' });
      res.end(JSON.stringify(getAllTools()));
      return;
    }

    // Execute endpoint (POST - REQUIRES AUTH)
    if (url.pathname === '/tools/execute' && req.method === 'POST') {
      // Validate authentication
      if (!validateAuth(req)) {
        res.writeHead(401, { 'Content-Type': 'application/json' });
        res.end(JSON.stringify({ error: 'Unauthorized - valid Bearer token required' }));
        return;
      }

      // Validate Content-Type
      if (!validateContentType(req)) {
        res.writeHead(415, { 'Content-Type': 'application/json' });
        res.end(JSON.stringify({ error: 'Unsupported Media Type - application/json required' }));
        return;
      }

      let body = '';
      try {
        body = await readBodyWithLimit(req, 1024 * 1024); // 1MB limit
        const { tool, args } = JSON.parse(body);

        // Basic input validation
        if (!tool || typeof tool !== 'string') {
          res.writeHead(400, { 'Content-Type': 'application/json' });
          res.end(JSON.stringify({ error: 'Invalid request - tool name (string) required' }));
          return;
        }

        const result = await executeCassiCoreTool(CASSICORE_URL, tool, args || {}, logger);
        res.writeHead(200, { 'Content-Type': 'application/json' });
        res.end(JSON.stringify(result));
      } catch (error: any) {
        const statusCode = error.message.includes('exceeds') ? 413 : 
                          error.message.includes('Unexpected token') ? 400 : 500;
        res.writeHead(statusCode, { 'Content-Type': 'application/json' });
        res.end(JSON.stringify({ error: error.message }));
      }
      return;
    }

    res.writeHead(404);
    res.end('Not found');
  });

  httpServer.listen(port, () => {
    logger.info(`HTTP server listening on port ${port}`);
  });
}

// ═══════════════════════════════════════════════════════════════════════════════
// Main Entry Point
// ═══════════════════════════════════════════════════════════════════════════════

/**
 * Main entry point
 */
async function main() {
  const args = process.argv.slice(2);
  const httpMode = args.includes('--http');
  const portArg = args.find(arg => arg.startsWith('--port='));
  const port = portArg ? parseInt(portArg.split('=')[1], 10) : 3000;

  // Validate CassiCore connection
  try {
    const healthCheck = await fetchWithTimeout(`${CASSICORE_URL}/health`);
    if (!healthCheck.ok) {
      throw new Error('CassiCore health check failed');
    }
    logger.info('CassiCore daemon connection verified');
  } catch (error: any) {
    logger.error('Failed to connect to CassiCore daemon', {
      url: CASSICORE_URL,
      error: String(error),
    });
    logger.warn('Make sure CassiCore is running: cassicore daemon');
    // Continue anyway - connection might succeed later
  }

  if (httpMode) {
    await startHttp(port);
  } else {
    await startStdio();
  }
}

main().catch((error) => {
  logger.error('Gateway failed to start', { error: String(error) });
  process.exit(1);
});
