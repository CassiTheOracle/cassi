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
import { spawn } from 'child_process';

// Configuration
const CASSICORE_URL = process.env.CASSICORE_URL || 'http://localhost:7433';
const GATEWAY_VERSION = '1.0.0';

// Logger that writes to stderr (stdout reserved for MCP protocol)
function log(level: string, message: string, data?: any) {
  const timestamp = new Date().toISOString();
  const logLine = JSON.stringify({ timestamp, level, message, data });
  console.error(logLine);
}

/**
 * Tool definitions - mirror of CassiCore's tool registry
 */
const CASSICORE_TOOLS = [
  {
    name: 'bash',
    description: 'Execute bash commands with timeout and output capture. Use for file operations, running tests, git commands, etc.',
    inputSchema: {
      type: 'object',
      properties: {
        command: {
          type: 'string',
          description: 'The bash command to execute',
        },
        cwd: {
          type: 'string',
          description: 'Working directory for the command (optional, defaults to current)',
        },
        timeout: {
          type: 'number',
          description: 'Timeout in milliseconds (optional, default 30000, max 120000)',
        },
      },
      required: ['command'],
    },
  },
  {
    name: 'read',
    description: 'Read a file from the filesystem. Returns content, size, and metadata.',
    inputSchema: {
      type: 'object',
      properties: {
        path: {
          type: 'string',
          description: 'Absolute or relative path to the file',
        },
      },
      required: ['path'],
    },
  },
  {
    name: 'write',
    description: 'Write content to a file. Creates parent directories if needed.',
    inputSchema: {
      type: 'object',
      properties: {
        path: {
          type: 'string',
          description: 'Absolute or relative path to write to',
        },
        content: {
          type: 'string',
          description: 'Content to write to the file',
        },
      },
      required: ['path', 'content'],
    },
  },
  {
    name: 'edit',
    description: 'Edit a file by replacing old text with new text. Fails if old text not found.',
    inputSchema: {
      type: 'object',
      properties: {
        path: {
          type: 'string',
          description: 'Path to the file to edit',
        },
        oldText: {
          type: 'string',
          description: 'Exact text to replace (including whitespace)',
        },
        newText: {
          type: 'string',
          description: 'Replacement text',
        },
      },
      required: ['path', 'oldText', 'newText'],
    },
  },
  {
    name: 'mkdir',
    description: 'Create a directory (recursively if needed).',
    inputSchema: {
      type: 'object',
      properties: {
        path: {
          type: 'string',
          description: 'Path to the directory to create',
        },
      },
      required: ['path'],
    },
  },
  {
    name: 'delete',
    description: 'Delete a file or directory (recursively).',
    inputSchema: {
      type: 'object',
      properties: {
        path: {
          type: 'string',
          description: 'Path to delete',
        },
      },
      required: ['path'],
    },
  },
  {
    name: 'exists',
    description: 'Check if a file or directory exists. Returns existence and type.',
    inputSchema: {
      type: 'object',
      properties: {
        path: {
          type: 'string',
          description: 'Path to check',
        },
      },
      required: ['path'],
    },
  },
  {
    name: 'web_fetch',
    description: 'Fetch content from a URL. Returns text content with HTML stripped.',
    inputSchema: {
      type: 'object',
      properties: {
        url: {
          type: 'string',
          description: 'URL to fetch',
        },
        timeoutMs: {
          type: 'number',
          description: 'Timeout in milliseconds (optional, default 30000)',
        },
      },
      required: ['url'],
    },
  },
  {
    name: 'web_search',
    description: 'Search the web for information. Returns search results with titles and snippets.',
    inputSchema: {
      type: 'object',
      properties: {
        query: {
          type: 'string',
          description: 'Search query',
        },
        maxResults: {
          type: 'number',
          description: 'Maximum results to return (optional, default 5)',
        },
      },
      required: ['query'],
    },
  },
];

/**
 * Serena code intelligence tools (if available)
 */
const SERENA_TOOLS = [
  {
    name: 'serena__find_symbol',
    description: 'Find code symbols (functions, classes, variables) by name using semantic understanding.',
    inputSchema: {
      type: 'object',
      properties: {
        symbolName: {
          type: 'string',
          description: 'Name of the symbol to find',
        },
      },
      required: ['symbolName'],
    },
  },
  {
    name: 'serena__read_symbol',
    description: 'Read detailed information about a symbol including its code and documentation.',
    inputSchema: {
      type: 'object',
      properties: {
        symbolName: {
          type: 'string',
          description: 'Name of the symbol to read',
        },
      },
      required: ['symbolName'],
    },
  },
  {
    name: 'serena__find_referencing_symbols',
    description: 'Find all places where a symbol is used (references).',
    inputSchema: {
      type: 'object',
      properties: {
        symbolName: {
          type: 'string',
          description: 'Name of the symbol to find references for',
        },
      },
      required: ['symbolName'],
    },
  },
  {
    name: 'serena__list_files',
    description: 'List files in the codebase with optional filtering.',
    inputSchema: {
      type: 'object',
      properties: {
        path: {
          type: 'string',
          description: 'Directory path to list (optional)',
        },
        pattern: {
          type: 'string',
          description: 'File pattern to match (optional, e.g., "*.ts")',
        },
      },
    },
  },
  {
    name: 'serena__replace_symbol_body',
    description: 'Replace the entire body of a symbol with new code.',
    inputSchema: {
      type: 'object',
      properties: {
        symbolName: {
          type: 'string',
          description: 'Name of the symbol to replace',
        },
        newBody: {
          type: 'string',
          description: 'New code body for the symbol',
        },
      },
      required: ['symbolName', 'newBody'],
    },
  },
];

/**
 * Execute a tool via CassiCore daemon
 */
async function executeCassiCoreTool(toolName: string, args: any): Promise<any> {
  log('info', 'Executing CassiCore tool', { tool: toolName, args });

  // Map tool names to CassiCore API endpoints
  const endpointMap: Record<string, string> = {
    bash: '/tools/bash',
    read: '/tools/read',
    write: '/tools/write',
    edit: '/tools/edit',
    mkdir: '/tools/mkdir',
    delete: '/tools/delete',
    exists: '/fs/exists',
    web_fetch: '/tools/web_fetch',
    web_search: '/tools/web_search',
  };

  const endpoint = endpointMap[toolName];
  if (!endpoint) {
    throw new Error(`Unknown tool: ${toolName}`);
  }

  const url = `${CASSICORE_URL}${endpoint}`;
  
  // Determine HTTP method based on tool
  const readTools = ['read', 'exists'];
  const method = readTools.includes(toolName) ? 'GET' : 'POST';

  try {
    let response;
    
    if (method === 'GET') {
      const queryParams = new URLSearchParams(args).toString();
      response = await fetch(`${url}?${queryParams}`, {
        method: 'GET',
      });
    } else {
      response = await fetch(url, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(args),
      });
    }

    if (!response.ok) {
      const error = await response.text();
      throw new Error(`CassiCore error: ${error}`);
    }

    return await response.json();
  } catch (error: any) {
    log('error', 'Tool execution failed', { tool: toolName, error: error.message });
    throw error;
  }
}

/**
 * Execute Serena tool (if Serena MCP server is available)
 */
async function executeSerenaTool(toolName: string, args: any): Promise<any> {
  log('info', 'Executing Serena tool', { tool: toolName, args });
  
  // Serena has its own MCP server - this is a proxy
  // In practice, Qwen-Coder would connect directly to serena-server.js
  throw new Error('Serena tools should be accessed directly via serena-server.js MCP');
}

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
      tools: [...CASSICORE_TOOLS, ...SERENA_TOOLS],
    };
  });

  // Handle tool calls
  server.setRequestHandler(CallToolRequestSchema, async (request) => {
    const { name, arguments: args } = request.params;
    
    log('info', 'Tool call received', { tool: name, args });
    
    try {
      let result;
      
      if (name.startsWith('serena__')) {
        result = await executeSerenaTool(name, args);
      } else {
        result = await executeCassiCoreTool(name, args);
      }

      return {
        content: [
          {
            type: 'text',
            text: JSON.stringify(result, null, 2),
          },
        ],
      };
    } catch (error: any) {
      log('error', 'Tool execution failed', { tool: name, error: error.message });
      return {
        content: [
          {
            type: 'text',
            text: JSON.stringify({ error: error.message }, null, 2),
          },
        ],
        isError: true,
      };
    }
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
        const response = await fetch(`${CASSICORE_URL}/health`);
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

/**
 * Start with stdio transport (default for MCP)
 */
async function startStdio() {
  log('info', 'Starting CassiCore MCP Gateway (stdio mode)', { url: CASSICORE_URL });
  
  const server = createServer();
  const transport = new StdioServerTransport();
  
  await server.connect(transport);
  
  log('info', 'CassiCore MCP Gateway connected and ready');
}

/**
 * Start with HTTP/SSE transport (for remote connections)
 */
async function startHttp(port: number) {
  log('info', 'Starting CassiCore MCP Gateway (HTTP mode)', { port, url: CASSICORE_URL });
  
  const server = createServer();
  
  // Create HTTP server for SSE transport
  const httpServer = http.createServer(async (req, res) => {
    const url = new URL(req.url || '/', `http://localhost:${port}`);
    
    // Health endpoint
    if (url.pathname === '/health') {
      try {
        const cassiHealth = await fetch(`${CASSICORE_URL}/health`);
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
    
    // Tools endpoint (REST API)
    if (url.pathname === '/tools' && req.method === 'GET') {
      res.writeHead(200, { 'Content-Type': 'application/json' });
      res.end(JSON.stringify([...CASSICORE_TOOLS, ...SERENA_TOOLS]));
      return;
    }
    
    // Execute endpoint (REST API)
    if (url.pathname === '/tools/execute' && req.method === 'POST') {
      let body = '';
      req.on('data', chunk => body += chunk);
      req.on('end', async () => {
        try {
          const { tool, args } = JSON.parse(body);
          const result = await executeCassiCoreTool(tool, args);
          res.writeHead(200, { 'Content-Type': 'application/json' });
          res.end(JSON.stringify(result));
        } catch (error: any) {
          res.writeHead(500, { 'Content-Type': 'application/json' });
          res.end(JSON.stringify({ error: error.message }));
        }
      });
      return;
    }
    
    res.writeHead(404);
    res.end('Not found');
  });
  
  httpServer.listen(port, () => {
    log('info', `HTTP server listening on port ${port}`);
  });
}

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
    const healthCheck = await fetch(`${CASSICORE_URL}/health`);
    if (!healthCheck.ok) {
      throw new Error('CassiCore health check failed');
    }
    log('info', 'CassiCore daemon connection verified');
  } catch (error: any) {
    log('error', 'Failed to connect to CassiCore daemon', { 
      url: CASSICORE_URL, 
      error: error.message 
    });
    log('warn', 'Make sure CassiCore is running: cassicore daemon');
    // Continue anyway - connection might succeed later
  }
  
  if (httpMode) {
    await startHttp(port);
  } else {
    await startStdio();
  }
}

main().catch((error) => {
  log('error', 'Gateway failed to start', { error: error.message });
  process.exit(1);
});
