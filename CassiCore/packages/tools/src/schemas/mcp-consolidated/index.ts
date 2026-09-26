/**
 * @cassicore/tools — retained consolidated mind-tool schemas (P5).
 *
 * The retained essence of the retired `@cassicore/mcp-gateway` (CASSICORE-FOCUS
 * §5 #28): the consolidated mind-tool **schemas** that helix's posture runner
 * builds code/web/browser consolidated tool definitions from
 * (`getCodeConsolidatedToolSchema`, `WEB_CONSOLIDATED_TOOL`,
 * `BROWSER_CONSOLIDATED_TOOL`, `execute{Code,Browser,Web}ConsolidatedTool`).
 *
 * Extracted here (with the helix consumer in mind) so the retained mind-tool
 * surface keeps compiling after the mcp-gateway server dies. The modules are the
 * consolidated tool schema/handler definitions + their bounded local deps
 * (tool-management, serena-onboarding, helpers); the MCP server machinery
 * (stdio/HTTP driver, daemon-child-spawn, proxy) is gone.
 */

export {
  CODE_CONSOLIDATED_TOOL,
  CODE_CONSOLIDATED_TOOL_NAME,
  executeCodeConsolidatedTool,
  getCodeConsolidatedTool,
  getCodeConsolidatedToolSchema,
} from './consolidated-code-tools.js'
export {
  WEB_CONSOLIDATED_TOOL,
  WEB_CONSOLIDATED_TOOL_NAME,
  executeWebConsolidatedTool,
  getWebConsolidatedTool,
} from './consolidated-web-tools.js'
export {
  BROWSER_CONSOLIDATED_TOOL,
  BROWSER_CONSOLIDATED_TOOL_NAME,
  executeBrowserConsolidatedTool,
  getBrowserConsolidatedTool,
} from './consolidated-browser-tools.js'
export {
  CORE_TOOLS,
  VYBIT_TOOL,
  executeCassiCoreTool,
  isCoreTool,
  getCoreTools,
} from './tool-management.js'
export type { ToolRouter } from './serena-onboarding.js'
