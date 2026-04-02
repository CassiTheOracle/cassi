#!/usr/bin/env node
/**
 * Consolidated Browser Tools Module
 *
 * Wraps Playwright MCP browser tools behind a single cassi_browser tool.
 * All actions are Unity-only (browser interactions have side effects).
 *
 * CRITICAL: Playwright uses `ref` (element references from accessibility snapshots),
 * NOT CSS selectors. The `ref` param is a string like "s1e2" returned from a snapshot.
 */

import type { ToolRouter } from './serena-onboarding.js'
import type { ILogger } from '../../types/interfaces.js'

/**
 * Consolidated browser tool definition
 */
export const BROWSER_CONSOLIDATED_TOOL = {
  name: 'browser',
  description: `Browser automation — navigate, interact, and extract data from web pages using Playwright.

IMPORTANT: Most actions require a 'ref' parameter — an element reference string (like "s1e2") obtained from a snapshot. Always call snapshot first to get refs, then use them for click/type/etc.

Workflow: navigate → snapshot → click/type using refs → screenshot/evaluate as needed.`,
  inputSchema: {
    type: 'object',
    properties: {
      action: {
        type: 'string',
        enum: [
          'navigate', 'snapshot', 'click', 'type', 'screenshot', 'evaluate',
          'tabs', 'wait', 'press_key', 'fill_form', 'select', 'hover', 'drag',
          'close', 'back', 'resize', 'console', 'network', 'handle_dialog',
          'file_upload', 'run_code', 'install',
        ],
        description: 'Browser action to perform',
      },
      // navigate params
      url: {
        type: 'string',
        description: 'URL to navigate to (for navigate action)',
      },
      // Element interaction params (click, type, screenshot, evaluate, select, hover)
      ref: {
        type: 'string',
        description: 'Element reference from snapshot (e.g. "s1e2"). Required for click, type, select, hover, drag.',
      },
      element: {
        type: 'string',
        description: 'Human-readable element description (for permission context)',
      },
      // type params
      text: {
        type: 'string',
        description: 'Text to type (for type action) or text to wait for (for wait action)',
      },
      slowly: {
        type: 'boolean',
        description: 'Type one character at a time (for type action)',
      },
      submit: {
        type: 'boolean',
        description: 'Press Enter after typing (for type action)',
      },
      // click params
      button: {
        type: 'string',
        enum: ['left', 'right', 'middle'],
        description: 'Mouse button (for click action, default: left)',
      },
      doubleClick: {
        type: 'boolean',
        description: 'Double click instead of single (for click action)',
      },
      modifiers: {
        type: 'array',
        items: { type: 'string' },
        description: 'Modifier keys: Alt, Control, ControlOrMeta, Meta, Shift (for click action)',
      },
      // screenshot params
      screenshotType: {
        type: 'string',
        enum: ['png', 'jpeg'],
        description: 'Image format (for screenshot action, default: png)',
      },
      fullPage: {
        type: 'boolean',
        description: 'Capture full scrollable page (for screenshot action)',
      },
      // evaluate params
      function: {
        type: 'string',
        description: 'JavaScript function to evaluate: () => { ... } or (element) => { ... }',
      },
      // tabs params
      tabAction: {
        type: 'string',
        enum: ['list', 'new', 'close', 'select'],
        description: 'Tab operation (for tabs action)',
      },
      index: {
        type: 'number',
        description: 'Tab index (for tabs close/select)',
      },
      // wait params
      textGone: {
        type: 'string',
        description: 'Text to wait for to disappear (for wait action)',
      },
      time: {
        type: 'number',
        description: 'Time to wait in seconds (for wait action)',
      },
      // press_key params
      key: {
        type: 'string',
        description: 'Key name (e.g. "ArrowLeft", "Enter") or character (for press_key action)',
      },
      // fill_form params
      fields: {
        type: 'array',
        items: {
          type: 'object',
          properties: {
            name: { type: 'string' },
            type: { type: 'string', enum: ['textbox', 'checkbox', 'radio', 'combobox', 'slider'] },
            ref: { type: 'string' },
            value: { type: 'string' },
          },
          required: ['name', 'type', 'ref', 'value'],
        },
        description: 'Form fields to fill (for fill_form action)',
      },
      // select params
      values: {
        type: 'array',
        items: { type: 'string' },
        description: 'Values to select in dropdown (for select action)',
      },
      // drag params
      startRef: {
        type: 'string',
        description: 'Source element reference (for drag action)',
      },
      startElement: {
        type: 'string',
        description: 'Source element description (for drag action)',
      },
      endRef: {
        type: 'string',
        description: 'Target element reference (for drag action)',
      },
      endElement: {
        type: 'string',
        description: 'Target element description (for drag action)',
      },
      // resize params
      width: {
        type: 'number',
        description: 'Browser window width (for resize action)',
      },
      height: {
        type: 'number',
        description: 'Browser window height (for resize action)',
      },
      // console params
      level: {
        type: 'string',
        enum: ['error', 'warning', 'info', 'debug'],
        description: 'Console message level filter (for console action)',
      },
      // network params
      includeStatic: {
        type: 'boolean',
        description: 'Include static resources like images/fonts/scripts (for network action)',
      },
      // handle_dialog params
      accept: {
        type: 'boolean',
        description: 'Whether to accept the dialog (for handle_dialog action)',
      },
      promptText: {
        type: 'string',
        description: 'Text for prompt dialog (for handle_dialog action)',
      },
      // file_upload params
      paths: {
        type: 'array',
        items: { type: 'string' },
        description: 'Absolute file paths to upload (for file_upload action)',
      },
      // run_code params
      code: {
        type: 'string',
        description: 'Playwright code snippet: async (page) => { ... } (for run_code action)',
      },
      // Common
      filename: {
        type: 'string',
        description: 'Filename for saving output (for snapshot, screenshot, console, network actions)',
      },
    },
    required: ['action'],
  },
}

/**
 * Tool name for routing
 */
export const BROWSER_CONSOLIDATED_TOOL_NAME = 'browser'

/**
 * Action → Playwright tool name mapping
 */
const ACTION_TO_PLAYWRIGHT: Record<string, string> = {
  navigate: 'playwright_browser_navigate',
  snapshot: 'playwright_browser_snapshot',
  click: 'playwright_browser_click',
  type: 'playwright_browser_type',
  screenshot: 'playwright_browser_take_screenshot',
  evaluate: 'playwright_browser_evaluate',
  tabs: 'playwright_browser_tabs',
  wait: 'playwright_browser_wait_for',
  press_key: 'playwright_browser_press_key',
  fill_form: 'playwright_browser_fill_form',
  select: 'playwright_browser_select_option',
  hover: 'playwright_browser_hover',
  drag: 'playwright_browser_drag',
  close: 'playwright_browser_close',
  back: 'playwright_browser_navigate_back',
  resize: 'playwright_browser_resize',
  console: 'playwright_browser_console_messages',
  network: 'playwright_browser_network_requests',
  handle_dialog: 'playwright_browser_handle_dialog',
  file_upload: 'playwright_browser_file_upload',
  run_code: 'playwright_browser_run_code',
  install: 'playwright_browser_install',
}

/**
 * Execute the consolidated browser tool
 * @dep callers: routeToolCall (mcp/cassicore-gateway.ts), executeConsolidatedGatewayTools (core/intelligence/helix/helix-posture-runner.ts)
 * @dep module: Gateway
 * @dep risk: LOW | 2 callers, 0 flows, 1 module
 */
export async function executeBrowserConsolidatedTool(
  args: any,
  logger: ILogger,
  router: ToolRouter
): Promise<any> {
  const { action, ...restArgs } = args

  if (!action) {
    throw new Error('Missing required parameter: action')
  }

  const playwrightTool = ACTION_TO_PLAYWRIGHT[action]
  if (!playwrightTool) {
    throw new Error(`Unknown browser action: ${action}`)
  }

  logger.debug('Executing consolidated browser tool', { action })

  // Map our param names to Playwright param names where they differ
  switch (action) {
    case 'navigate':
      return await router(playwrightTool, { url: restArgs.url })

    case 'snapshot':
      return await router(playwrightTool, { filename: restArgs.filename })

    case 'click':
      return await router(playwrightTool, {
        ref: restArgs.ref,
        element: restArgs.element,
        button: restArgs.button,
        doubleClick: restArgs.doubleClick,
        modifiers: restArgs.modifiers,
      })

    case 'type':
      return await router(playwrightTool, {
        ref: restArgs.ref,
        text: restArgs.text,
        element: restArgs.element,
        slowly: restArgs.slowly,
        submit: restArgs.submit,
      })

    case 'screenshot':
      return await router(playwrightTool, {
        type: restArgs.screenshotType ?? 'png',
        fullPage: restArgs.fullPage,
        ref: restArgs.ref,
        element: restArgs.element,
        filename: restArgs.filename,
      })

    case 'evaluate':
      return await router(playwrightTool, {
        function: restArgs.function,
        ref: restArgs.ref,
        element: restArgs.element,
      })

    case 'tabs':
      return await router(playwrightTool, {
        action: restArgs.tabAction ?? 'list',
        index: restArgs.index,
      })

    case 'wait':
      return await router(playwrightTool, {
        text: restArgs.text,
        textGone: restArgs.textGone,
        time: restArgs.time,
      })

    case 'press_key':
      return await router(playwrightTool, { key: restArgs.key })

    case 'fill_form':
      return await router(playwrightTool, { fields: restArgs.fields })

    case 'select':
      return await router(playwrightTool, {
        ref: restArgs.ref,
        values: restArgs.values,
        element: restArgs.element,
      })

    case 'hover':
      return await router(playwrightTool, {
        ref: restArgs.ref,
        element: restArgs.element,
      })

    case 'drag':
      return await router(playwrightTool, {
        startRef: restArgs.startRef,
        startElement: restArgs.startElement,
        endRef: restArgs.endRef,
        endElement: restArgs.endElement,
      })

    case 'close':
    case 'back':
    case 'install':
      return await router(playwrightTool, {})

    case 'resize':
      return await router(playwrightTool, {
        width: restArgs.width,
        height: restArgs.height,
      })

    case 'console':
      return await router(playwrightTool, {
        level: restArgs.level ?? 'info',
        filename: restArgs.filename,
      })

    case 'network':
      return await router(playwrightTool, {
        static: restArgs.includeStatic ?? false,
        requestBody: restArgs.requestBody ?? false,
        requestHeaders: restArgs.requestHeaders ?? false,
        filename: restArgs.filename,
      })

    case 'handle_dialog':
      return await router(playwrightTool, {
        accept: restArgs.accept,
        promptText: restArgs.promptText,
      })

    case 'file_upload':
      return await router(playwrightTool, { paths: restArgs.paths })

    case 'run_code':
      return await router(playwrightTool, { code: restArgs.code })

    default:
      throw new Error(`Unknown browser action: ${action}`)
  }
}

/**
 * Get the consolidated browser tool definition
 */
export function getBrowserConsolidatedTool(): typeof BROWSER_CONSOLIDATED_TOOL {
  return BROWSER_CONSOLIDATED_TOOL
}
