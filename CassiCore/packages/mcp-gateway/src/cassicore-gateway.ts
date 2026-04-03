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

import {
  GATEWAY_VERSION,
  createLogger,
  fetchWithTimeout,
  formatError,
  formatJsonResponse,
  formatTextResponse,
  getCoreTools,
  executeCassiCoreTool,
  VYBIT_TOOL,
  SKILL_INTELLIGENCE_TOOL,
  WORKFLOW_TOOL,
  getDoTools,
  executeDoTool,
  executeEnrichTool,
  DO_TOOL_NAMES,
  ENRICH_TOOL_NAMES,
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
import { resolveToolAlias, unknownToolError } from './gateway/tool-aliases.js';

const CASSICORE_URL = process.env.CASSICORE_URL || 'http://localhost:7433';

const logger = createLogger();

// WHY: Prevent silent crashes from unhandled rejections or uncaught exceptions.
// In Node 25+ these terminate the process by default — log and continue
// (or exit gracefully) instead.

process.on('unhandledRejection', (reason) => {
  logger.error('Unhandled promise rejection in MCP gateway', { error: String(reason) });
});

process.on('uncaughtException', (err) => {
  logger.error('Uncaught exception in MCP gateway — shutting down', { error: String(err) });
  process.exit(1);
});

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
 * Validate authentication token from request.
 * WHY: HTTP mode requires token-based auth to prevent unauthorized access.
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

/**
 * Get all MCP tools.
 * @dep callers: startHttp (mcp/cassicore-gateway.ts), createServer (mcp/cassicore-gateway.ts)
 * @dep calls: getCoreTools, getDoTools, getWebConsolidatedTool, getTrainingConsolidatedTool, getSessionConsolidatedTool [+10]
 * @dep module: Mcp
 * @dep risk: LOW | 2 callers, 0 flows, 1 module
 */
function getAllTools() {
  const coreTools = getCoreTools();
  const mainCoreTools = coreTools.filter(t => ['bash', 'read', 'write', 'edit', 'todo_write'].includes(t.name));

  return [
    ...mainCoreTools,
    ...getDoTools(),
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
    VYBIT_TOOL,
    SKILL_INTELLIGENCE_TOOL,
    WORKFLOW_TOOL,
  ];
}

/**
 * Route a tool call to the appropriate domain handler
 * @dep callers: createServer (mcp/cassicore-gateway.ts), routeToolCall (mcp/cassicore-gateway.ts)
 * @dep calls: has, routeToolCall, executeTrainingTool, executeCassiCoreTool, getCoreTools [+19]
 * @dep flows: CreateHierarchyBridge → ExecuteIntelligenceTool (3/4), CreateHierarchyBridge → FormatTextResponse (3/4)
 * @dep module: Gateway
 * @dep risk: LOW | 2 callers, 2 flows, 1 module
 */
let _coreToolNameCache: Set<string> | null = null;
function isCoreToolName(name: string): boolean {
  if (!_coreToolNameCache) {
    _coreToolNameCache = new Set(getCoreTools().map(t => t.name));
  }
  return _coreToolNameCache.has(name);
}

/**
 * Route a tool call directly to the daemon's MCP tool bridge (via /tools/execute).
 * Bypasses alias resolution and consolidated tool dispatch, sending the call
 * straight to the daemon's ToolExecutor which handles external MCP servers
 * (gitnexus, serena, duckduckgo, etc.).
 *
 * WHY: Consolidated tools that internally call external MCP tools (e.g., cassi_code
 * calling gitnexus_query) need a router that does NOT go back through routeToolCall.
 * Going through routeToolCall triggers alias resolution (gitnexus_query → code)
 * which creates an infinite recursion loop.
 */
async function routeExternalToolCall(
  name: string,
  args: any,
): Promise<{ content: Array<{ type: 'text'; text: string }>; isError?: true }> {
  // WHY: The daemon's MCP tool bridge uses double-underscore as the server/tool
  // separator (e.g., gitnexus__query), but the consolidated tools use single
  // underscore (gitnexus_query). Normalize to the daemon's convention.
  const EXTERNAL_PREFIXES = ['gitnexus_', 'serena_', 'duckduckgo_'];
  let daemonToolName = name;
  for (const prefix of EXTERNAL_PREFIXES) {
    if (name.startsWith(prefix) && !name.startsWith(prefix + '_')) {
      daemonToolName = prefix + '_' + name.slice(prefix.length);
      break;
    }
  }

  logger.info('External tool call (daemon passthrough)', { tool: daemonToolName, originalName: name });
  try {
    const response = await fetchWithTimeout(`${CASSICORE_URL}/tools/execute`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ tool: daemonToolName, input: args || {} }),
      timeoutMs: 120_000,
    });
    if (!response.ok) {
      const err = await response.text().catch(() => `HTTP ${response.status}`);
      return formatError(new Error(`Daemon returned ${response.status}: ${err}`));
    }
    const result = await response.json().catch(() => null);
    if (!result) {
      return formatError(new Error('Daemon returned non-JSON response'));
    }
    // Normalize the result to MCP content format
    if (result.content && Array.isArray(result.content)) {
      return result;
    }
    return {
      content: [{ type: 'text', text: JSON.stringify(result, null, 2) }],
      isError: result.isError,
    };
  } catch (err) {
    logger.error('External tool call failed', { tool: name, error: String(err) });
    return formatError(err);
  }
}

/**
 * Route a tool call to the appropriate domain handler.
 * @dep callers: createServer (mcp/cassicore-gateway.ts), routeToolCall (mcp/cassicore-gateway.ts)
 * @dep calls: isCoreToolName, routeExternalToolCall, routeToolCall, executeCassiCoreTool, resolveToolAlias [+20]
 * @dep module: Gateway
 * @dep risk: LOW | 2 callers, 0 flows, 1 module
 */
async function routeToolCall(name: string, args: any, progressToken?: string | number, heartbeat?: () => void): Promise<{ content: Array<{ type: 'text'; text: string }>; isError?: true }> {
  logger.info('Tool call received', { tool: name, args });

  // HOW: resolveToolAlias handles deprecated names, prefix stripping, external MCP
  // passthrough, user shorthands, and fuzzy typo correction.
  const resolved = resolveToolAlias(name, args);
  if (resolved) {
    name = resolved.name;
    args = resolved.args as any;
  }

  try {
    // HOW: Core tools return JSON format via formatJsonResponse
    if (isCoreToolName(name)) {
      const result = await executeCassiCoreTool(CASSICORE_URL, name, args, logger);
      return formatJsonResponse(result);
    }

    // HOW: VyBit routes through ToolExecutor like core tools
    if (name === 'vybit') {
      const result = await executeCassiCoreTool(CASSICORE_URL, 'vybit', args, logger);
      return formatJsonResponse(result);
    }

    // HOW: Skill intelligence routes through ToolExecutor
    if (name === 'skill_intelligence') {
      const result = await executeCassiCoreTool(CASSICORE_URL, 'skill_intelligence', args, logger);
      return formatJsonResponse(result);
    }

    // HOW: Workflow tool routes through ToolExecutor
    if (name === 'workflow') {
      const result = await executeCassiCoreTool(CASSICORE_URL, 'workflow', args, logger);
      return formatJsonResponse(result);
    }

    // HOW: do tool is a meta-wrapper with parallel context enrichment
    if (DO_TOOL_NAMES.has(name)) {
      return await executeDoTool(
        CASSICORE_URL,
        args,
        logger,
        (toolName, toolArgs) => routeToolCall(toolName, toolArgs, progressToken, heartbeat)
      );
    }

    // HOW: enrich tool performs context-only enrichment without delegated tool calls
    if (ENRICH_TOOL_NAMES.has(name)) {
      return await executeEnrichTool(CASSICORE_URL, args, logger);
    }

    switch (name) {
      case AGENT_TOOL_NAME: {
        const agentResult = await executeAgentTool(CASSICORE_URL, args, logger, heartbeat);
        // HOW: Agent tools return mixed formats: watch/blackboard return MCP { content: [...] },
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
        // HOW: Intelligence tools return markdown
        return formatTextResponse(result);
      }

      case ARTIFACT_CONSOLIDATED_TOOL_NAME: {
        const result = await executeArtifactConsolidatedTool(CASSICORE_URL, args, logger);
        // HOW: File artifact tools return MCP format directly
        return result as { content: Array<{ type: 'text'; text: string }>; isError?: true };
      }

      case CODE_CONSOLIDATED_TOOL_NAME:
        // WHY: The code tool calls router('gitnexus_*', ...) which MUST go
        // directly to the daemon's MCP bridge. Passing routeToolCall as the
        // router creates an infinite loop: gitnexus_query → alias → code → gitnexus_query → ...
        return formatJsonResponse(await executeCodeConsolidatedTool(args, logger, (toolName, toolArgs) =>
          routeExternalToolCall(toolName, toolArgs)
        ));

      case FILESYSTEM_CONSOLIDATED_TOOL_NAME:
        return formatJsonResponse(await executeFilesystemConsolidatedTool(args, logger, (toolName, toolArgs) => routeToolCall(toolName, toolArgs, progressToken, heartbeat)));

      case BROWSER_CONSOLIDATED_TOOL_NAME:
        return formatJsonResponse(await executeBrowserConsolidatedTool(args, logger, (toolName, toolArgs) => routeToolCall(toolName, toolArgs, progressToken, heartbeat)));

      case WEB_CONSOLIDATED_TOOL_NAME:
        return formatJsonResponse(await executeWebConsolidatedTool(CASSICORE_URL, args, logger, (toolName, toolArgs) =>
          routeExternalToolCall(toolName, toolArgs)
        ));

      case CONFIG_CONSOLIDATED_TOOL_NAME:
        return formatJsonResponse(await executeConfigConsolidatedTool(CASSICORE_URL, args, logger));

      case MODEL_CONSOLIDATED_TOOL_NAME:
        return formatJsonResponse(await executeModelConsolidatedTool(CASSICORE_URL, args, logger));

      case BLACKBOARD_CONSOLIDATED_TOOL_NAME: {
        const result = await executeBlackboardConsolidatedTool(CASSICORE_URL, args, logger);
        // HOW: Blackboard tools return MCP format directly
        return result as { content: Array<{ type: 'text'; text: string }>; isError?: true };
      }

      case TRAINING_CONSOLIDATED_TOOL_NAME:
        return formatJsonResponse(await executeTrainingConsolidatedTool(CASSICORE_URL, args, logger));

      default:
        throw unknownToolError(name);
    }
  } catch (error: any) {
    logger.error('Tool execution failed', { tool: name, error: String(error) });
    return formatError(error);
  }
}

/**
 * Active resource subscriptions: URI -> Set of subscriber IDs
 */
const resourceSubscriptions = new Map<string, Set<string>>();

/**
 * Subscribe a client to a resource URI.
 * WHY: Enables real-time updates for resources like team status and session context.
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
 * Notify all subscribers of a resource update.
 */
async function notifyResourceUpdate(server: Server, uri: string): Promise<void> {
  const subscribers = resourceSubscriptions.get(uri);
  if (subscribers && subscribers.size > 0) {
    logger.info('Notifying resource update', { uri, subscriberCount: subscribers.size });
    // HOW: In stdio mode, notifications are queued and sent when possible.
    // The SDK handles the actual delivery.
  }
}

/**
 * Create MCP Server with full capabilities
 * @dep callers: webchat.ts (workers/channels/webchat.ts), bridge.js (tool-proxy/bridge.js), mock-telemetry-server.ts (mock-telemetry-server.ts), startCallbackServer (ai/src/utils/oauth/google-antigravity.ts), startCallbackServer (ai/src/utils/oauth/google-gemini-cli.ts) [+13]
 * @dep calls: now, getAllTools, routeToolCall, subscribeToResource, unsubscribeFromResource [+4]
 * @dep module: Mcp
 * @dep risk: CRITICAL | 18 callers, 0 flows, 1 module
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

  server.setRequestHandler(ListToolsRequestSchema, async () => {
    return {
      tools: getAllTools(),
    };
  });

  // WHY: Wrap all progress notifications so a broken transport never crashes
  // the request handler.
  function safeNotify(params: { progressToken: string | number; progress: number; total: number; message: string }) {
    try {
      server.notification({
        method: 'notifications/progress',
        params,
      });
    } catch (err) {
      logger.warn('Failed to send progress notification', { error: String(err) });
    }
  }

  server.setRequestHandler(CallToolRequestSchema, async (request) => {
    const { name, arguments: args, _meta } = request.params;
    const progressToken = _meta?.progressToken;
    
    // Send progress notifications for long-running operations
    if (progressToken) {
      safeNotify({ progressToken, progress: 0, total: 100, message: `Starting ${name}...` });
    }

    try {
      // HOW: Heartbeat sends MCP progress notifications to prevent client timeouts
      // during blocking operations like team_watch.
      const heartbeat = progressToken ? () => {
        safeNotify({ progressToken, progress: 50, total: 100, message: `${name} waiting for events...` });
      } : undefined

      const result = await routeToolCall(name, args, progressToken, heartbeat);
      
      if (progressToken) {
        safeNotify({ progressToken, progress: 100, total: 100, message: `${name} completed` });
      }
      
      return result;
      } catch (error: any) {
      if (progressToken) {
        safeNotify({ progressToken, progress: 100, total: 100, message: `${name} failed: ${error.message}` });
      }
      // WHY: Return a formatted error instead of re-throwing — re-throwing can break
      // the MCP connection if the error is non-serializable or the transport is
      // already in a bad state.
      logger.error('Tool call threw in handler', { tool: name, error: String(error) });
      return formatError(error);
    }
  });

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

  server.setRequestHandler(SubscribeRequestSchema, async (request) => {
    const { uri } = request.params;
    const subscriberId = `${request.params._meta?.progressToken || 'unknown'}-${Date.now()}`;
    
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

  server.setRequestHandler(UnsubscribeRequestSchema, async (request) => {
    const { uri } = request.params;
    const subscriberId = `${request.params._meta?.progressToken || 'unknown'}-${Date.now()}`;
    
    unsubscribeFromResource(uri, subscriberId);
    
    logger.info('Client unsubscribed from resource', { uri, subscriberId });
    
    return {};
  });

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

/**
 * Start with stdio transport (default for MCP).
 */
async function startStdio() {
  logger.info('Starting CassiCore MCP Gateway (stdio mode)', { url: CASSICORE_URL });

  const server = createServer();
  const transport = new StdioServerTransport();

  // WHY: Catch MCP-layer errors and disconnections that would otherwise
  // go unnoticed, leaving a zombie process.
  server.onerror = (error: Error) => {
    logger.error('MCP server error', { error: String(error) });
  };

  server.onclose = () => {
    logger.info('MCP server closed — exiting');
    process.exit(0);
  };

  // WHY: When the MCP client (OpenCode) disconnects, stdin emits 'end'.
  // The SDK transport only listens for 'data' and 'error', so we need
  // to detect this ourselves and trigger a clean shutdown.
  process.stdin.on('end', () => {
    logger.info('stdin ended — client disconnected, closing');
    server.close().catch(() => {});
    setTimeout(() => process.exit(0), 500);
  });

  process.stdin.on('close', () => {
    logger.info('stdin closed — exiting');
    server.close().catch(() => {});
    setTimeout(() => process.exit(0), 500);
  });

  for (const signal of ['SIGTERM', 'SIGINT', 'SIGHUP'] as const) {
    process.on(signal, () => {
      logger.info(`Received ${signal} — shutting down`);
      server.close().catch(() => {});
      setTimeout(() => process.exit(0), 500);
    });
  }

  await server.connect(transport);

  // Periodic daemon health probe: check every 60s. When the daemon goes from
  // unreachable to reachable (or vice versa), log it so connectivity gaps
  // are visible in MCP logs.
  let daemonUp = true;
  const HEALTH_INTERVAL_MS = 60_000;
  const healthProbe = setInterval(async () => {
    try {
      const resp = await fetchWithTimeout(`${CASSICORE_URL}/health`, { timeoutMs: 5_000 });
      if (!daemonUp && resp.ok) {
        logger.info('CassiCore daemon reconnected');
        daemonUp = true;
      }
    } catch {
      if (daemonUp) {
        logger.warn('CassiCore daemon unreachable — tool calls will retry');
        daemonUp = false;
      }
    }
  }, HEALTH_INTERVAL_MS);
  healthProbe.unref(); // don't keep the process alive just for the probe

  logger.info('CassiCore MCP Gateway connected and ready');
}

/**
 * Start with HTTP/SSE transport (for remote connections).
 */
async function startHttp(port: number) {
  if (!AUTH_TOKEN) {
    throw new Error('CASSICORE_MCP_TOKEN is required in HTTP mode');
  }

  logger.info('Starting CassiCore MCP Gateway (HTTP mode)', { port, url: CASSICORE_URL });

  const server = createServer();

  const httpServer = http.createServer(async (req, res) => {
    const url = new URL(req.url || '/', `http://localhost:${port}`);

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

    if (url.pathname === '/tools' && req.method === 'GET') {
      res.writeHead(200, { 'Content-Type': 'application/json' });
      res.end(JSON.stringify(getAllTools()));
      return;
    }

    if (url.pathname === '/tools/execute' && req.method === 'POST') {
      if (!validateAuth(req)) {
        res.writeHead(401, { 'Content-Type': 'application/json' });
        res.end(JSON.stringify({ error: 'Unauthorized - valid Bearer token required' }));
        return;
      }

      if (!validateContentType(req)) {
        res.writeHead(415, { 'Content-Type': 'application/json' });
        res.end(JSON.stringify({ error: 'Unsupported Media Type - application/json required' }));
        return;
      }

      let body = '';
      try {
        body = await readBodyWithLimit(req, 1024 * 1024);
        const { tool, args } = JSON.parse(body);

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

/**
 * Main entry point.
 */
async function main() {
  const args = process.argv.slice(2);
  const httpMode = args.includes('--http');
  const portArg = args.find(arg => arg.startsWith('--port='));
  const port = portArg ? parseInt(portArg.split('=')[1], 10) : 3000;

  // HOW: The startup health check uses a longer timeout to give the daemon
  // time to boot if the gateway starts before or alongside it.
  try {
    const healthCheck = await fetchWithTimeout(`${CASSICORE_URL}/health`, { timeoutMs: 10_000 });
    if (!healthCheck.ok) {
      throw new Error(`CassiCore health check returned ${healthCheck.status}`);
    }
    logger.info('CassiCore daemon connection verified');
  } catch (error: any) {
    logger.error('Failed to connect to CassiCore daemon', {
      url: CASSICORE_URL,
      error: String(error),
    });
    logger.warn('Gateway will start anyway — tool calls will retry when the daemon becomes available');
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
