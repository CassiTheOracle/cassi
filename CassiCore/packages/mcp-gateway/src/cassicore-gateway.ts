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
  SubscribeRequestSchema,
  UnsubscribeRequestSchema,
  ListResourceTemplatesRequestSchema,
  ListPromptsRequestSchema,
  GetPromptRequestSchema,
  ProgressNotificationSchema,
  LoggingMessageNotificationSchema,
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
  // Core Tools (4: bash, read, write, edit - kept as-is)
  getCoreTools,
  executeCassiCoreTool,
  // Meta Tools (2: do, enrich - kept as-is)
  getDoTools,
  executeDoTool,
  executeEnrichTool,
  DO_TOOL_NAMES,
  ENRICH_TOOL_NAMES,
  // Consolidated Tools
  getAgentTool,
  executeAgentTool,
  getMemoryConsolidatedTool,
  executeMemoryConsolidatedTool,
  getSessionConsolidatedTool,
  executeSessionConsolidatedTool,
  getIntelligenceConsolidatedTool,
  executeIntelligenceConsolidatedTool,
  getArtifactConsolidatedTool,
  executeArtifactConsolidatedTool,
  getCodeConsolidatedTool,
  executeCodeConsolidatedTool,
  getFilesystemConsolidatedTool,
  executeFilesystemConsolidatedTool,
  getBrowserConsolidatedTool,
  executeBrowserConsolidatedTool,
  getWebConsolidatedTool,
  executeWebConsolidatedTool,
  getConfigConsolidatedTool,
  executeConfigConsolidatedTool,
  getModelConsolidatedTool,
  executeModelConsolidatedTool,
  getBlackboardConsolidatedTool,
  executeBlackboardConsolidatedTool,
  getTrainingConsolidatedTool,
  executeTrainingConsolidatedTool,
  // Tool name sets for consolidated tools
  AGENT_TOOL_NAME,
  MEMORY_CONSOLIDATED_TOOL_NAME,
  SESSION_CONSOLIDATED_TOOL_NAME,
  INTELLIGENCE_CONSOLIDATED_TOOL_NAME,
  ARTIFACT_CONSOLIDATED_TOOL_NAME,
  CODE_CONSOLIDATED_TOOL_NAME,
  FILESYSTEM_CONSOLIDATED_TOOL_NAME,
  BROWSER_CONSOLIDATED_TOOL_NAME,
  WEB_CONSOLIDATED_TOOL_NAME,
  CONFIG_CONSOLIDATED_TOOL_NAME,
  MODEL_CONSOLIDATED_TOOL_NAME,
  BLACKBOARD_CONSOLIDATED_TOOL_NAME,
  TRAINING_CONSOLIDATED_TOOL_NAME,
} from './gateway/index.js';

// Configuration
const CASSICORE_URL = process.env.CASSICORE_URL || 'http://localhost:7433';

// Logger
const logger = createLogger();

// Security Configuration

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
    const configPath = path.join(process.env.CASSICORE_HOME || process.env.HOME || process.env.USERPROFILE || '', '.cassicore', 'config.json');
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
    logger.error('HTTP gateway request rejected: CASSICORE_MCP_TOKEN is not configured');
    return false;
  }

  const authHeader = req.headers['authorization'];
  if (!authHeader || Array.isArray(authHeader)) {
    return false;
  }

  return authHeader === `Bearer ${AUTH_TOKEN}`;
}

function validateContentType(req: http.IncomingMessage, expectedType: string = 'application/json'): boolean {
  const contentType = req.headers['content-type'];
  if (!contentType) {
    return false;
  }
  
  // Allow charset specification
  return contentType.toLowerCase().startsWith(expectedType);
}

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

// Tool Registry

/**
 * @dep callers: startHttp (mcp/cassicore-gateway.ts), createServer (mcp/cassicore-gateway.ts)
 * @dep calls: getTrainingTools, getCoreTools, getSessionTools, getModelDirectiveTools, getMemoryTools [+9]
 * @dep flows: CreateHierarchyBridge → GetCoreTools (3/4), CreateHierarchyBridge → GetIntelligenceTools (3/4), CreateHierarchyBridge → GetDialecticTools (3/4) [+1]
 * @dep module: Gateway
 * @dep risk: MEDIUM | 2 callers, 4 flows, 1 module
 */

/**
 * Get all MCP tools - returns exactly 16 consolidated tools
 * 4 core + 2 meta + 10 consolidated
 */
/**
 * Get all MCP tools.
 */
function getAllTools() {
  const coreTools = getCoreTools();
  // Filter to only the 4 main core tools
  const mainCoreTools = coreTools.filter(t => ['bash', 'read', 'write', 'edit'].includes(t.name));

  return [
    // 4 Core tools (kept as-is)
    ...mainCoreTools,
    // 2 Meta tools (kept as-is)
    ...getDoTools(),
    // Consolidated tools
    getAgentTool(),
    getMemoryConsolidatedTool(),
    getSessionConsolidatedTool(),
    getIntelligenceConsolidatedTool(),
    getArtifactConsolidatedTool(),
    getCodeConsolidatedTool(),
    getFilesystemConsolidatedTool(),
    getBrowserConsolidatedTool(),
    getWebConsolidatedTool(),
    getConfigConsolidatedTool(),
    getModelConsolidatedTool(),
    getBlackboardConsolidatedTool(),
    getTrainingConsolidatedTool(),
  ];
}



// Tool Execution Router

/**
 * Route a tool call to the appropriate domain handler
 * @dep callers: createServer (mcp/cassicore-gateway.ts), routeToolCall (mcp/cassicore-gateway.ts)
 * @dep calls: has, routeToolCall, executeTrainingTool, executeCassiCoreTool, getCoreTools [+19]
 * @dep flows: CreateHierarchyBridge → ExecuteIntelligenceTool (3/4), CreateHierarchyBridge → FormatTextResponse (3/4)
 * @dep module: Gateway
 * @dep risk: LOW | 2 callers, 2 flows, 1 module
 */
/**
 * Backward-compat shim: maps old individual tool names to their consolidated equivalents.
 * Used by cassi_do and any cached tool references from older sessions.
 * Returns null if the name is already a current tool name.
 */
function resolveDeprecatedToolName(name: string, args: any): { name: string; args: any } | null {
  // Agent tools: lumen_*, dyad_*, helix_*, flux_*
  for (const prefix of ['lumen', 'dyad', 'helix'] as const) {
    if (name.startsWith(`${prefix}_`)) {
      const action = name.slice(prefix.length + 1);
      return { name: 'agent', args: { ...args, type: prefix, action } };
    }
  }
  if (name.startsWith('flux_')) {
    const suffix = name.slice(5); // flux_team, flux_run, flux_inspect, flux_watch
    if (suffix === 'team') return { name: 'agent', args: { ...args, type: 'flux', action: 'team', teamAction: args?.action } };
    if (suffix === 'run') return { name: 'agent', args: { ...args, type: 'flux', action: 'run' } };
    if (suffix === 'inspect') return { name: 'agent', args: { ...args, type: 'flux', action: 'inspect' } };
    if (suffix === 'watch') return { name: 'agent', args: { ...args, type: 'flux', action: 'watch' } };
  }

  // Memory tools
  for (const action of ['store', 'search', 'recent', 'delete', 'kv_get', 'kv_set', 'kv_del', 'stats'] as const) {
    if (name === `memory_${action}`) return { name: 'memory', args: { ...args, action } };
  }
  for (const action of ['archive_search', 'archive_get', 'archive_related', 'archive_recent'] as const) {
    if (name === action) return { name: 'memory', args: { ...args, action } };
  }
  if (name === 'browse') return { name: 'memory', args: { ...args, action: 'browse' } };
  if (name === 'universal_search') return { name: 'memory', args: { ...args, action: 'universal_search' } };

  // Session tools
  if (name === 'sessions') return { name: 'session', args: { ...args, action: 'list' } };
  for (const action of ['detail', 'prune', 'conversation', 'export'] as const) {
    if (name === `session_${action}`) return { name: 'session', args: { ...args, action } };
  }
  if (name === 'resolve_ref') return { name: 'session', args: { ...args, action: 'resolve_ref' } };
  if (name === 'index_session') return { name: 'session', args: { ...args, action: 'index' } };
  if (name === 'index_search') return { name: 'session', args: { ...args, action: 'index_search' } };
  if (name === 'index_stats') return { name: 'session', args: { ...args, action: 'index_stats' } };

  // Intelligence tools
  for (const action of ['activity', 'thinker', 'subconscious', 'consciousness', 'trace', 'effectiveness', 'budget', 'evolution', 'blindspots', 'snapshot', 'trust', 'consequences'] as const) {
    if (name === action) return { name: 'intelligence', args: { ...args, action } };
  }
  if (name === 'dialectic') return { name: 'intelligence', args: { ...args, action: 'dialectic' } };
  if (name === '_1') return { name: 'intelligence', args: { ...args, action: 'overview' } };

  // File tools
  for (const action of ['mkdir', 'delete', 'exists'] as const) {
    if (name === action) return { name: 'file', args: { ...args, action } };
  }
  if (name === 'share_file') return { name: 'file', args: { ...args, action: 'share' } };
  if (name === 'open_file') return { name: 'file', args: { ...args, action: 'open' } };
  if (name === 'file_admin') return { name: 'file', args: { ...args, action: 'admin' } };
  for (const suffix of ['write', 'read', 'list', 'delete', 'versions', 'share', 'stats', 'gc'] as const) {
    if (name === `file_artifact_${suffix}`) return { name: 'file', args: { ...args, action: suffix } };
  }

  // Web tools
  if (name === 'web_fetch') return { name: 'web', args: { ...args, action: 'fetch' } };
  if (name === 'web_search') return { name: 'web', args: { ...args, action: 'search' } };

  // Config tools
  if (name === 'config_get') return { name: 'config', args: { ...args, action: 'get' } };
  if (name === 'config_set') return { name: 'config', args: { ...args, action: 'set' } };
  if (name === 'providers') return { name: 'config', args: { ...args, action: 'providers' } };
  if (name === 'provider_metrics') return { name: 'config', args: { ...args, action: 'provider_metrics' } };
  if (name === 'provider_config') return { name: 'config', args: { ...args, action: 'provider_config' } };

  // Model tools
  if (name === 'model_directive') return { name: 'model', args: { ...args, action: args?.action } };

  // Blackboard tools
  for (const suffix of ['list', 'create', 'delete', 'post', 'read', 'search', 'watch'] as const) {
    if (name === `bb_global_${suffix}`) return { name: 'blackboard', args: { ...args, action: suffix } };
  }

  // Training tools
  for (const suffix of ['stats', 'search', 'objects', 'resolve', 'labels', 'quality', 'annotations', 'ingest', 'tag', 'export'] as const) {
    if (name === `training_${suffix}`) return { name: 'training', args: { ...args, action: suffix } };
  }

  // External MCP tools → consolidated wrappers
  const codeActionMap: Record<string, string> = {
    gitnexus_query: 'query',
    gitnexus_context: 'context',
    gitnexus_impact: 'impact',
    gitnexus_cypher: 'cypher',
    gitnexus_detect_changes: 'detect_changes',
    gitnexus_list_repos: 'list_repos',
    gitnexus_rename: 'rename_graph',
    serena_find_symbol: 'symbol',
    serena_find_referencing_symbols: 'refs',
    serena_get_symbols_overview: 'overview',
    serena_rename_symbol: 'rename_symbol',
    serena_replace_symbol_body: 'replace_symbol',
    serena_insert_after_symbol: 'insert_after',
    serena_insert_before_symbol: 'insert_before',
  };
  if (codeActionMap[name]) return { name: 'code', args: { ...args, action: codeActionMap[name] } };
  if (name === 'serena_search_for_pattern') {
    const looksCodeFocused = args?.restrict_search_to_code_files === true
      || args?.name_path_pattern !== undefined
      || args?.substring_pattern !== undefined
    return { name: looksCodeFocused ? 'code' : 'file', args: { ...args, action: looksCodeFocused ? 'search_pattern' : 'search', path: args?.path ?? args?.relative_path } };
  }

  const fileActionMap: Record<string, string> = {
    serena_read_file: 'read',
    serena_replace_content: args?.content !== undefined ? 'write' : 'edit',
    serena_list_dir: 'list',
    serena_find_file: 'find',
  };
  if (fileActionMap[name]) {
    return { name: 'file', args: { ...args, action: fileActionMap[name], path: args?.path ?? args?.relative_path } };
  }

  const browserActionMap: Record<string, string> = {
    playwright_browser_navigate: 'navigate',
    playwright_browser_snapshot: 'snapshot',
    playwright_browser_click: 'click',
    playwright_browser_type: 'type',
    playwright_browser_take_screenshot: 'screenshot',
    playwright_browser_evaluate: 'evaluate',
    playwright_browser_tabs: 'tabs',
    playwright_browser_wait_for: 'wait',
    playwright_browser_press_key: 'press_key',
    playwright_browser_fill_form: 'fill_form',
    playwright_browser_select_option: 'select',
    playwright_browser_hover: 'hover',
    playwright_browser_drag: 'drag',
    playwright_browser_close: 'close',
    playwright_browser_navigate_back: 'back',
    playwright_browser_resize: 'resize',
    playwright_browser_console_messages: 'console',
    playwright_browser_network_requests: 'network',
    playwright_browser_handle_dialog: 'handle_dialog',
    playwright_browser_file_upload: 'file_upload',
    playwright_browser_run_code: 'run_code',
    playwright_browser_install: 'install',
  };
  if (browserActionMap[name]) return { name: 'browser', args: { ...args, action: browserActionMap[name] } };

  if (name === 'duckduckgo_fetch_content') return { name: 'web', args: { ...args, action: 'fetch_content' } };

  return null; // Not a deprecated name — pass through unchanged
}

/**
 * Route a tool call to the appropriate domain handler.
 */
async function routeToolCall(name: string, args: any, progressToken?: string | number, heartbeat?: () => void): Promise<{ content: Array<{ type: 'text'; text: string }>; isError?: true }> {
  logger.info('Tool call received', { tool: name, args });

  // Backward-compat: map old tool names → consolidated tool + action
  const resolved = resolveDeprecatedToolName(name, args);
  if (resolved) {
    name = resolved.name;
    args = resolved.args;
  }

  try {
    // Core tools (bash, read, write, edit) - return JSON
    if (getCoreTools().some(t => t.name === name)) {
      const result = await executeCassiCoreTool(CASSICORE_URL, name, args, logger);
      return formatJsonResponse(result);
    }

    // do tool - meta-wrapper with parallel context enrichment
    if (DO_TOOL_NAMES.has(name)) {
      return await executeDoTool(
        CASSICORE_URL,
        args,
        logger,
        (toolName, toolArgs) => routeToolCall(toolName, toolArgs, progressToken, heartbeat)
      );
    }

    // enrich tool - context-only enrichment (no delegated tool call)
    if (ENRICH_TOOL_NAMES.has(name)) {
      return await executeEnrichTool(CASSICORE_URL, args, logger);
    }

    // Consolidated tools
    switch (name) {
      case AGENT_TOOL_NAME: {
        const agentResult = await executeAgentTool(CASSICORE_URL, args, logger, heartbeat);
        // Agent tools return mixed formats: watch/blackboard return MCP { content: [...] },
        // but project/status/jobs/etc return raw JSON. Wrap only when needed.
        if (agentResult?.content && Array.isArray(agentResult.content)) {
          return agentResult;
        }
        return formatJsonResponse(agentResult);
      }

      case MEMORY_CONSOLIDATED_TOOL_NAME:
        return formatJsonResponse(await executeMemoryConsolidatedTool(CASSICORE_URL, args, logger));

      case SESSION_CONSOLIDATED_TOOL_NAME:
        return formatJsonResponse(await executeSessionConsolidatedTool(CASSICORE_URL, args, logger));

      case INTELLIGENCE_CONSOLIDATED_TOOL_NAME: {
        const result = await executeIntelligenceConsolidatedTool(CASSICORE_URL, args, logger);
        // Intelligence tools return markdown
        return formatTextResponse(result);
      }

      case ARTIFACT_CONSOLIDATED_TOOL_NAME: {
        const result = await executeArtifactConsolidatedTool(CASSICORE_URL, args, logger);
        // File artifact tools return MCP format directly
        return result as { content: Array<{ type: 'text'; text: string }>; isError?: true };
      }

      case CODE_CONSOLIDATED_TOOL_NAME:
        return formatJsonResponse(await executeCodeConsolidatedTool(args, logger, (toolName, toolArgs) => routeToolCall(toolName, toolArgs, progressToken, heartbeat)));

      case FILESYSTEM_CONSOLIDATED_TOOL_NAME:
        return formatJsonResponse(await executeFilesystemConsolidatedTool(args, logger, (toolName, toolArgs) => routeToolCall(toolName, toolArgs, progressToken, heartbeat)));

      case BROWSER_CONSOLIDATED_TOOL_NAME:
        return formatJsonResponse(await executeBrowserConsolidatedTool(args, logger, (toolName, toolArgs) => routeToolCall(toolName, toolArgs, progressToken, heartbeat)));

      case WEB_CONSOLIDATED_TOOL_NAME:
        return formatJsonResponse(await executeWebConsolidatedTool(CASSICORE_URL, args, logger, (toolName, toolArgs) => routeToolCall(toolName, toolArgs, progressToken, heartbeat)));

      case CONFIG_CONSOLIDATED_TOOL_NAME:
        return formatJsonResponse(await executeConfigConsolidatedTool(CASSICORE_URL, args, logger));

      case MODEL_CONSOLIDATED_TOOL_NAME:
        return formatJsonResponse(await executeModelConsolidatedTool(CASSICORE_URL, args, logger));

      case BLACKBOARD_CONSOLIDATED_TOOL_NAME: {
        const result = await executeBlackboardConsolidatedTool(CASSICORE_URL, args, logger);
        // Blackboard tools return MCP format directly
        return result as { content: Array<{ type: 'text'; text: string }>; isError?: true };
      }

      case TRAINING_CONSOLIDATED_TOOL_NAME:
        return formatJsonResponse(await executeTrainingConsolidatedTool(CASSICORE_URL, args, logger));

      default:
        throw new Error(`Unknown tool: ${name}`);
    }
  } catch (error: any) {
    logger.error('Tool execution failed', { tool: name, error: String(error) });
    return formatError(error);
  }
}

// Resource Subscription Manager

/**
 * Active resource subscriptions: URI -> Set of subscriber IDs
 */
const resourceSubscriptions = new Map<string, Set<string>>();

/**
 * Subscribe a client to a resource URI
 * @dep callers: createServer (mcp/cassicore-gateway.ts)
 * @dep calls: get, has, add
 * @dep flows: CreateHierarchyBridge → SubscribeToResource (3/3)
 * @dep module: Mcp
 * @dep risk: LOW | 1 caller, 1 flow, 1 module
 */
function subscribeToResource(uri: string, subscriberId: string): void {
  if (!resourceSubscriptions.has(uri)) {
    resourceSubscriptions.set(uri, new Set());
  }
  resourceSubscriptions.get(uri)!.add(subscriberId);
  logger.info('Resource subscription added', { uri, subscriberId, totalSubscribers: resourceSubscriptions.get(uri)!.size });
}

function unsubscribeFromResource(uri: string, subscriberId: string): void {
  const subscribers = resourceSubscriptions.get(uri);
  if (subscribers) {
    subscribers.delete(subscriberId);
    if (subscribers.size === 0) {

      resourceSubscriptions.delete(uri);
    }


    logger.info('Resource subscription removed', { uri, subscriberId, remainingSubscribers: subscribers.size });
  }
}

/**
 * Notify all subscribers of a resource update
 */
async function notifyResourceUpdate(server: Server, uri: string): Promise<void> {
  const subscribers = resourceSubscriptions.get(uri);
  if (subscribers && subscribers.size > 0) {
    logger.info('Notifying resource update', { uri, subscriberCount: subscribers.size });
    // HOW: In stdio mode, notifications are queued and sent when possible
    // The SDK handles the actual delivery
  }
}

// MCP Server

/**
 * Create MCP Server with full capabilities
 * @dep callers: webchat.ts (workers/channels/webchat.ts), bridge.js (tool-proxy/bridge.js), start (cluster/src/ccipc.js), startControllerSocket (cluster/src/controller.js), startLegacySocket (cluster/src/controller.js) [+12]
 * @dep calls: now, test, getAllTools, routeToolCall, subscribeToResource [+2]
 * @dep flows: CreateHierarchyBridge → GetCoreTools (2/4), CreateHierarchyBridge → GetIntelligenceTools (2/4), CreateHierarchyBridge → GetDialecticTools (2/4) [+4]
 * @dep module: Mcp
 * @dep risk: CRITICAL | 17 callers, 7 flows, 1 module
 */
function createServer() {
  const server = new Server(
    {
      name: 'cassicore-gateway',
      version: GATEWAY_VERSION,
    },
    {
      capabilities: {
        tools: {
          listChanged: true,
        },
        resources: {
          subscribe: true,
          listChanged: true,
        },
        prompts: {
          listChanged: true,
        },
        logging: {},
      },
    }
  );

  // List available tools
  server.setRequestHandler(ListToolsRequestSchema, async () => {
    return {
      tools: getAllTools(),
    };
  });

  // Handle tool calls with progress notification support
  server.setRequestHandler(CallToolRequestSchema, async (request) => {
    const { name, arguments: args, _meta } = request.params;
    const progressToken = _meta?.progressToken;
    
    // Send progress notifications for long-running operations
    if (progressToken) {
      server.notification({
        method: 'notifications/progress',
        params: {
          progressToken,
          progress: 0,
          total: 100,
          message: `Starting ${name}...`,
        },
      });
    }

    try {
      // Create heartbeat callback for long-running tools (sends MCP progress notifications
      // to prevent the MCP client from timing out during blocking operations like team_watch)
      const heartbeat = progressToken ? () => {
        server.notification({
          method: 'notifications/progress',
          params: {
            progressToken,
            progress: 50,
            total: 100,
            message: `${name} waiting for events...`,
          },
        })
      } : undefined

      const result = await routeToolCall(name, args, progressToken, heartbeat);
      
      // Send completion progress
      if (progressToken) {
        server.notification({
          method: 'notifications/progress',
          params: {
            progressToken,
            progress: 100,
            total: 100,
            message: `${name} completed`,
          },
        });
      }
      
      return result;
    } catch (error: any) {
      if (progressToken) {
        server.notification({
          method: 'notifications/progress',
          params: {
            progressToken,
            progress: 100,
            total: 100,
            message: `${name} failed: ${error.message}`,
          },
        });
      }
      throw error;
    }
  });

  // List static resources
  server.setRequestHandler(ListResourcesRequestSchema, async () => {
    return {
      resources: [
        {
          uri: 'cassicore://health',
          name: 'CassiCore Health Status',
          mimeType: 'application/json',
          description: 'Current health and status of CassiCore daemon',
        },
        {
          uri: 'cassicore://config',
          name: 'CassiCore Configuration',
          mimeType: 'application/json',
          description: 'Current CassiCore configuration (safe keys only)',
        },
        {
          uri: 'cassicore://intelligence/activity',
          name: 'Intelligence Activity Log',
          mimeType: 'application/json',
          description: 'Recent intelligence and analysis activity',
        },
      ],
    };
  });

  // List resource templates (dynamic URIs)
  server.setRequestHandler(ListResourceTemplatesRequestSchema, async () => {
    return {
      resourceTemplates: [
        {
          uriTemplate: 'cassicore://teams/{id}',
          name: 'Team Status',
          mimeType: 'application/json',
          description: 'Status and progress of a specific team by ID',
        },
        {
          uriTemplate: 'cassicore://sessions/{id}/context',
          name: 'Session Context Window',
          mimeType: 'application/json',
          description: 'Context window snapshot for a specific session',
        },
        {
          uriTemplate: 'cassicore://sessions/{id}/turns',
          name: 'Session Turn History',
          mimeType: 'application/json',
          description: 'Turn history for a specific session',
        },
        {
          uriTemplate: 'cassicore://memory/{query}',
          name: 'Memory Search',
          mimeType: 'application/json',
          description: 'Search CassiCore memory by query',
        },
      ],
    };
  });

  // Read resources
  server.setRequestHandler(ReadResourceRequestSchema, async (request) => {
    const { uri } = request.params;

    try {
      let content: any;
      let mimeType = 'application/json';

      if (uri === 'cassicore://health') {
        const response = await fetchWithTimeout(`${CASSICORE_URL}/health`);
        content = await response.json();
      } else if (uri === 'cassicore://config') {
        const response = await fetchWithTimeout(`${CASSICORE_URL}/config`);
        content = await response.json();
      } else if (uri === 'cassicore://intelligence/activity') {
        const response = await fetchWithTimeout(`${CASSICORE_URL}/intelligence/activity`);
        content = await response.json();
      } else if (uri.startsWith('cassicore://teams/')) {
        const teamId = uri.replace('cassicore://teams/', '');
        const response = await fetchWithTimeout(`${CASSICORE_URL}/teams/${teamId}/status`);
        content = await response.json();
      } else if (uri.startsWith('cassicore://sessions/') && uri.includes('/context')) {
        const sessionId = uri.replace('cassicore://sessions/', '').replace('/context', '');
        const response = await fetchWithTimeout(`${CASSICORE_URL}/sessions/${sessionId}/context`);
        content = await response.json();
      } else if (uri.startsWith('cassicore://sessions/') && uri.includes('/turns')) {
        const sessionId = uri.replace('cassicore://sessions/', '').replace('/turns', '');
        const response = await fetchWithTimeout(`${CASSICORE_URL}/sessions/${sessionId}/turns`);
        content = await response.json();
      } else if (uri.startsWith('cassicore://memory/')) {
        const query = decodeURIComponent(uri.replace('cassicore://memory/', ''));
        const response = await fetchWithTimeout(`${CASSICORE_URL}/memory/search?query=${encodeURIComponent(query)}`);
        content = await response.json();
      } else {
        throw new Error(`Unknown resource: ${uri}`);
      }

      return {
        contents: [
          {
            uri,
            mimeType,
            text: typeof content === 'string' ? content : JSON.stringify(content, null, 2),
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
  });

  // Handle resource subscriptions
  server.setRequestHandler(SubscribeRequestSchema, async (request) => {
    const { uri } = request.params;
    const subscriberId = `${request.params._meta?.progressToken || 'unknown'}-${Date.now()}`;
    
    // Validate URI is subscribable
    const subscribablePatterns = [
      /^cassicore:\/\/teams\/.+$/,
      /^cassicore:\/\/sessions\/.+\/context$/,
      /^cassicore:\/\/sessions\/.+\/turns$/,
      /^cassicore:\/\/health$/,
      /^cassicore:\/\/intelligence\/activity$/,
    ];
    
    const isSubscribable = subscribablePatterns.some(pattern => pattern.test(uri));
    if (!isSubscribable) {
      throw new Error(`Resource ${uri} does not support subscriptions`);
    }

    subscribeToResource(uri, subscriberId);
    
    logger.info('Client subscribed to resource', { uri, subscriberId });
    
    return {};
  });

  // Handle resource unsubscriptions
  server.setRequestHandler(UnsubscribeRequestSchema, async (request) => {
    const { uri } = request.params;
    const subscriberId = `${request.params._meta?.progressToken || 'unknown'}-${Date.now()}`;
    
    unsubscribeFromResource(uri, subscriberId);
    
    logger.info('Client unsubscribed from resource', { uri, subscriberId });
    
    return {};
  });

  // List prompts (workflow templates)
  server.setRequestHandler(ListPromptsRequestSchema, async () => {
    return {
      prompts: [
        {
          name: 'inspect-team',
          title: 'Inspect Team Status',
          description: 'Generate a comprehensive inspection report for a running team',
          arguments: [
            { name: 'teamId', description: 'The team ID to inspect', required: true },
            { name: 'includeTree', description: 'Include cell hierarchy tree', required: false },
            { name: 'includeBudget', description: 'Include budget usage', required: false },
          ],
        },
        {
          name: 'debug-session',
          title: 'Debug Session',
          description: 'Generate debugging context for a specific session',
          arguments: [
            { name: 'sessionId', description: 'The session ID to debug', required: true },
            { name: 'includeContext', description: 'Include context window', required: false },
            { name: 'includeHistory', description: 'Include event history', required: false },
          ],
        },
        {
          name: 'review-memory',
          title: 'Review Memory',
          description: 'Search and review CassiCore memory for a topic',
          arguments: [
            { name: 'query', description: 'Search query for memory', required: true },
            { name: 'limit', description: 'Maximum results to return', required: false },
            { name: 'type', description: 'Filter by memory type (conversation, fact, insight, etc.)', required: false },
          ],
        },
        {
          name: 'analyze-error',
          title: 'Analyze Error Pattern',
          description: 'Analyze recurring errors and suggest fixes',
          arguments: [
            { name: 'errorPattern', description: 'Error message or pattern to analyze', required: true },
            { name: 'includeFixes', description: 'Include suggested fixes', required: false },
          ],
        },
      ],
    };
  });

  // Get prompt template
  server.setRequestHandler(GetPromptRequestSchema, async (request) => {
    const { name, arguments: args } = request.params;

    switch (name) {
      case 'inspect-team': {
        const teamId = args?.teamId;
        const includeTree = args?.includeTree === 'true';
        const includeBudget = args?.includeBudget === 'true';

        if (!teamId) {
          throw new Error('inspect-team prompt requires teamId argument');
        }

        let messages = [{
          role: 'user' as const,
          content: {
            type: 'text' as const,
            text: `Inspect team ${teamId}. Provide a comprehensive status report including:`,
          },
        }];

        if (includeTree) {
          messages.push({
            role: 'user' as const,
            content: {
              type: 'text' as const,
              text: '- Include the full cell hierarchy tree with status of each cell',
            },
          });
        }

        if (includeBudget) {
          messages.push({
            role: 'user' as const,
            content: {
              type: 'text' as const,
              text: '- Include current budget usage and remaining allocation',
            },
          });
        }

        messages.push({
          role: 'user' as const,
          content: {
            type: 'text' as const,
            text: 'Format the response as a structured report with clear sections.',
          },
        });

        return { messages };
      }

      case 'debug-session': {
        const sessionId = args?.sessionId;
        const includeContext = args?.includeContext === 'true';
        const includeHistory = args?.includeHistory === 'true';

        if (!sessionId) {
          throw new Error('debug-session prompt requires sessionId argument');
        }

        let messages = [{
          role: 'user' as const,
          content: {
            type: 'text' as const,
            text: `Debug session ${sessionId}. Analyze the session state and identify any issues:`,
          },
        }];

        if (includeContext) {
          messages.push({
            role: 'user' as const,
            content: {
              type: 'text' as const,
              text: '- Include current context window state and token usage',
            },
          });
        }

        if (includeHistory) {
          messages.push({
            role: 'user' as const,
            content: {
              type: 'text' as const,
              text: '- Include recent event history to trace the execution flow',
            },
          });
        }

        messages.push({
          role: 'user' as const,
          content: {
            type: 'text' as const,
            text: 'Identify any errors, bottlenecks, or unexpected behavior.',
          },
        });

        return { messages };
      }

      case 'review-memory': {
        const query = args?.query;
        const limit = args?.limit || '5';
        const type = args?.type;

        if (!query) {
          throw new Error('review-memory prompt requires query argument');
        }

        let messages = [{
          role: 'user' as const,
          content: {
            type: 'text' as const,
            text: `Search CassiCore memory for: "${query}"`,
          },
        }];

        messages.push({
          role: 'user' as const,
          content: {
            type: 'text' as const,
            text: `Return up to ${limit} results`,
          },
        });

        if (type) {
          messages.push({
            role: 'user' as const,
            content: {
              type: 'text' as const,
              text: `Filter results to type: ${type}`,
            },
          });
        }

        messages.push({
          role: 'user' as const,
          content: {
            type: 'text' as const,
            text: 'Summarize the key insights and patterns found in the memory results.',
          },
        });

        return { messages };
      }

      case 'analyze-error': {
        const errorPattern = args?.errorPattern;
        const includeFixes = args?.includeFixes === 'true';

        if (!errorPattern) {
          throw new Error('analyze-error prompt requires errorPattern argument');
        }

        let messages = [{
          role: 'user' as const,
          content: {
            type: 'text' as const,
            text: `Analyze the following error pattern: "${errorPattern}"`,
          },
        }];

        messages.push({
          role: 'user' as const,
          content: {
            type: 'text' as const,
            text: '1. Identify the root cause of this error',
          },
        });

        messages.push({
          role: 'user' as const,
          content: {
            type: 'text' as const,
            text: '2. Determine if this is a recurring pattern in the codebase',
          },
        });

        if (includeFixes) {
          messages.push({
            role: 'user' as const,
            content: {
              type: 'text' as const,
              text: '3. Suggest specific code fixes or architectural changes to prevent this error',
            },
          });
        }

        return { messages };
      }

      default:
        throw new Error(`Unknown prompt: ${name}`);
    }
  });

  return server;
}

// Transports

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
  if (!AUTH_TOKEN) {
    throw new Error('CASSICORE_MCP_TOKEN is required in HTTP mode');
  }

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

// Main Entry Point

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
