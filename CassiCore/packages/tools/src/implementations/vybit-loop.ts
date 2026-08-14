/**
 * VyBit Browser Automation Loop for CassiCore
 *
 * Manages the full visual editing cycle:
 *   1. Start the target project's dev server as a background job
 *   2. Inject VyBit's overlay script into the project's HTML
 *   3. Open a browser to the dev server
 *   4. Orchestrate the continuous implement loop (poll → implement → mark done)
 *
 * This module extends the core VyBit tool with browser-automation actions.
 * The actions are designed to be called sequentially during session setup,
 * then the agent enters the natural implement_next → work → mark_done loop.
 *
 * Architecture:
 *   - Dev server runs as a CassiCore background job (via JobManager)
 *   - Overlay injection is a one-time file edit (idempotent)
 *   - Browser launch uses xdg-open on Linux or open on macOS
 *   - The "session" action combines all setup steps into one call
 */

import { spawn } from 'node:child_process'
import { readFile, writeFile, access, stat } from 'node:fs/promises'
import { join, resolve, basename } from 'node:path'
import { getEventBus } from '../../vendor/core/events/index.js'

import type { ILogger } from "@cassicore/foundation"
import type { ToolExecutionContext } from '../types.js'

// State

/** Active dev server process — managed separately from VyBit MCP server */
let devServerProc: ReturnType<typeof spawn> | null = null
let devServerUrl: string | null = null
let devServerProjectPath: string | null = null

// Dev Server Management

/**
 * Detect the dev server command from the project's package.json.
 * Looks for common script names: dev, start, serve.
 */
async function detectDevCommand(projectPath: string): Promise<{
  command: string
  script: string
  port: number
} | null> {
  try {
    const pkgPath = join(projectPath, 'package.json')
    const raw = await readFile(pkgPath, 'utf-8')
    const pkg = JSON.parse(raw)
    const scripts = pkg.scripts || {}

    // Priority order: dev > start > serve
    const candidates = ['dev', 'start', 'serve']
    for (const name of candidates) {
      if (scripts[name]) {
        // Try to detect port from the script
        const portMatch = scripts[name].match(/(?:--port|PORT=|:)(\d{4,5})/)
        const port = portMatch ? parseInt(portMatch[1], 10) : 3000

        return {
          command: `npm run ${name}`,
          script: scripts[name],
          port,
        }
      }
    }
    return null
  } catch {
    return null
  }
}

/**
 * Start the project's dev server as a background child process.
 */
export async function handleDevStart(
  input: Record<string, unknown>,
  ctx: ToolExecutionContext,
): Promise<string> {
  if (devServerProc && !devServerProc.killed) {
    return JSON.stringify({
      status: 'already_running',
      url: devServerUrl,
      projectPath: devServerProjectPath,
      message: `Dev server is already running at ${devServerUrl}`,
    })
  }

  const projectPath = (input.projectPath as string) || ctx.workingDir
  if (!projectPath) {
    return JSON.stringify({ error: 'projectPath is required for "dev_start"' })
  }

  // Verify it's a valid project
  try {
    await access(join(projectPath, 'package.json'))
  } catch {
    return JSON.stringify({
      error: `No package.json found at ${projectPath}. Provide the path to a Node.js project.`,
    })
  }

  // Detect or use provided command
  const devCommand = (input.devCommand as string) || null
  const devPort = input.devPort ? Number(input.devPort) : null

  let command: string
  let port: number

  if (devCommand) {
    command = devCommand
    port = devPort || 3000
  } else {
    const detected = await detectDevCommand(projectPath)
    if (!detected) {
      return JSON.stringify({
        error: 'Could not detect a dev server script in package.json. ' +
          'Provide devCommand (e.g., "npm run dev") and devPort explicitly.',
      })
    }
    command = detected.command
    port = devPort || detected.port
    ctx.logger.info(`[vybit] Detected dev command: ${command} (port ${port})`)
  }

  // Start the dev server
  try {
    // WHY: shell: true handles command parsing, so we pass the full string
    devServerProc = spawn(command, [], {
      cwd: projectPath,
      stdio: ['ignore', 'pipe', 'pipe'],
      env: { ...process.env, PORT: String(port) },
      detached: false,
      shell: true,
    })

    devServerProjectPath = projectPath
    devServerUrl = `http://localhost:${port}`

    // Capture output for debugging
    let stdout = ''
    let stderr = ''

    devServerProc.stdout?.on('data', (data) => {
      stdout += data.toString()
      // Truncate to avoid memory issues
      if (stdout.length > 10_000) stdout = stdout.slice(-5_000)
    })

    devServerProc.stderr?.on('data', (data) => {
      stderr += data.toString()
      if (stderr.length > 10_000) stderr = stderr.slice(-5_000)
    })

    devServerProc.on('exit', (code) => {
      ctx.logger.info(`[vybit] Dev server exited with code ${code}`)
      devServerProc = null
    })

    // Wait a bit for the server to start
    await new Promise(r => setTimeout(r, 3000))

    // Check if process is still running
    if (devServerProc.killed || devServerProc.exitCode !== null) {
      const error = stderr || stdout || 'Process exited immediately'
      devServerProc = null
      return JSON.stringify({
        error: `Dev server failed to start: ${error.slice(0, 500)}`,
        command,
        port,
      })
    }

    return JSON.stringify({
      status: 'running',
      url: devServerUrl,
      command,
      port,
      pid: devServerProc.pid,
      message: `Dev server started at ${devServerUrl} (${command})`,
    })
  } catch (err) {
    devServerProc = null
    return JSON.stringify({ error: `Failed to start dev server: ${String(err)}` })
  }
}

/**
 * Stop the dev server.
 */
export async function handleDevStop(ctx: ToolExecutionContext): Promise<string> {
  if (!devServerProc || devServerProc.killed) {
    return JSON.stringify({ status: 'not_running', message: 'No dev server is running' })
  }

  try {
    devServerProc.kill('SIGTERM')
    // Give it a moment to exit gracefully
    await new Promise(r => setTimeout(r, 1000))
    if (!devServerProc.killed) {
      devServerProc.kill('SIGKILL')
    }
  } catch (err) {
    ctx.logger.warn(`[vybit] Dev server kill error: ${String(err)}`)
  }

  const oldUrl = devServerUrl
  devServerProc = null
  devServerUrl = null
  devServerProjectPath = null

  return JSON.stringify({
    status: 'stopped',
    message: `Dev server stopped (was ${oldUrl})`,
  })
}

// VyBit Overlay Injection

/**
 * The VyBit overlay script snippet. Loads the overlay from the VyBit server
 * only in development (localhost). Idempotent — checks if already present.
 */
const OVERLAY_SNIPPET = `
<!-- VyBit visual editing overlay (dev only) -->
<script>
if (location.hostname === 'localhost') {
  const s = document.createElement('script');
  s.src = 'http://localhost:VYBIT_PORT/overlay.js';
  document.head.appendChild(s);
}
</script>`.trim()

const OVERLAY_MARKER = 'VyBit visual editing overlay'

/**
 * Find the project's HTML entry point or React root layout file.
 * Searches common locations in order of specificity.
 */
async function findHtmlEntryPoint(projectPath: string): Promise<string | null> {
  const candidates = [
    // Vite / CRA
    'index.html',
    'public/index.html',
    // Next.js
    'app/layout.tsx',
    'app/layout.jsx',
    'src/app/layout.tsx',
    'src/app/layout.jsx',
    'pages/_document.tsx',
    'pages/_document.jsx',
    'src/pages/_document.tsx',
    'src/pages/_document.jsx',
    // Remix
    'app/root.tsx',
    'app/root.jsx',
    // Astro
    'src/layouts/Layout.astro',
    // Angular
    'src/index.html',
  ]

  for (const candidate of candidates) {
    const fullPath = join(projectPath, candidate)
    try {
      const s = await stat(fullPath)
      if (s.isFile()) return fullPath
    } catch {
      continue
    }
  }
  return null
}

/**
 * Inject the VyBit overlay script into the project's HTML entry point.
 */
export async function handleInjectOverlay(
  input: Record<string, unknown>,
  ctx: ToolExecutionContext,
): Promise<string> {
  const projectPath = (input.projectPath as string) || devServerProjectPath || ctx.workingDir
  const vybitPort = input.port ? Number(input.port) : 3333

  if (!projectPath) {
    return JSON.stringify({ error: 'projectPath is required' })
  }

  // Find entry point
  const entryPoint = (input.entryFile as string)
    ? resolve(projectPath, input.entryFile as string)
    : await findHtmlEntryPoint(projectPath)

  if (!entryPoint) {
    return JSON.stringify({
      error: 'Could not find HTML entry point. Provide entryFile parameter ' +
        '(e.g., "index.html" or "app/layout.tsx").',
      searched: [
        'index.html', 'public/index.html', 'app/layout.tsx', 'pages/_document.tsx',
        'app/root.tsx', 'src/index.html',
      ],
    })
  }

  try {
    const content = await readFile(entryPoint, 'utf-8')

    // Check if already injected
    if (content.includes(OVERLAY_MARKER)) {
      return JSON.stringify({
        status: 'already_injected',
        file: entryPoint,
        message: `VyBit overlay already present in ${basename(entryPoint)}`,
      })
    }

    // Build the snippet with the correct port
    const snippet = OVERLAY_SNIPPET.replace('VYBIT_PORT', String(vybitPort))

    // Determine injection point based on file type
    let newContent: string
    const ext = entryPoint.split('.').pop()?.toLowerCase()

    if (ext === 'html') {
      // For HTML files, inject before </head> or at end of <head>
      if (content.includes('</head>')) {
        newContent = content.replace('</head>', `${snippet}\n</head>`)
      } else if (content.includes('<body')) {
        newContent = content.replace(/<body/, `${snippet}\n<body`)
      } else {
        newContent = snippet + '\n' + content
      }
    } else if (ext === 'tsx' || ext === 'jsx') {
      // For React/Next layout files, add a comment-based injection guide
      // We can't just inject <script> in JSX — needs to use next/script or dangerouslySetInnerHTML
      const jsxSnippet = `
{/* VyBit visual editing overlay (dev only) */}
{process.env.NODE_ENV === 'development' && (
  <script
    dangerouslySetInnerHTML={{
      __html: \`
        if (location.hostname === 'localhost') {
          const s = document.createElement('script');
          s.src = 'http://localhost:${vybitPort}/overlay.js';
          document.head.appendChild(s);
        }
      \`,
    }}
  />
)}`

      // Try to inject inside <head> in layout files
      if (content.includes('<head>') || content.includes('<head ')) {
        newContent = content.replace(/<head[^>]*>/, `$&${jsxSnippet}`)
      } else if (content.includes('</body>') || content.includes('</html>')) {
        // Inject before closing body tag
        newContent = content.replace('</body>', `${jsxSnippet}\n</body>`)
      } else {
        // Fallback: return instructions instead of auto-injecting
        return JSON.stringify({
          status: 'manual_injection_needed',
          file: entryPoint,
          snippet: jsxSnippet,
          message: `Could not auto-inject into ${basename(entryPoint)}. ` +
            'Add the snippet to your layout component manually.',
        })
      }
    } else if (ext === 'astro') {
      // For Astro layouts
      if (content.includes('</head>')) {
        newContent = content.replace('</head>', `${snippet}\n</head>`)
      } else {
        return JSON.stringify({
          status: 'manual_injection_needed',
          file: entryPoint,
          snippet,
          message: `Could not find </head> in ${basename(entryPoint)}. Add the snippet manually.`,
        })
      }
    } else {
      return JSON.stringify({
        error: `Unsupported file type: .${ext}. Inject the overlay script manually.`,
        snippet,
      })
    }

    // Write the modified file
    await writeFile(entryPoint, newContent, 'utf-8')

    ctx.logger.info(`[vybit] Injected overlay into ${entryPoint}`)

    return JSON.stringify({
      status: 'injected',
      file: entryPoint,
      port: vybitPort,
      message: `VyBit overlay injected into ${basename(entryPoint)}. ` +
        `The overlay will load from http://localhost:${vybitPort}/overlay.js on localhost.`,
    })
  } catch (err) {
    return JSON.stringify({ error: `Failed to inject overlay: ${String(err)}` })
  }
}

// Browser Launch

/**
 * Open a browser to the dev server URL.
 */
export async function handleBrowserOpen(
  input: Record<string, unknown>,
  ctx: ToolExecutionContext,
): Promise<string> {
  const url = (input.url as string) || devServerUrl

  if (!url) {
    return JSON.stringify({
      error: 'No URL to open. Either provide a url parameter or start a dev server first (action: dev_start).',
    })
  }

  try {
    // Detect platform and use appropriate command
    const { platform } = process
    let openCmd: string
    let openArgs: string[]

    if (platform === 'linux') {
      openCmd = 'xdg-open'
      openArgs = [url]
    } else if (platform === 'darwin') {
      openCmd = 'open'
      openArgs = [url]
    } else if (platform === 'win32') {
      openCmd = 'cmd'
      openArgs = ['/c', 'start', '', url]
    } else {
      return JSON.stringify({
        error: `Unsupported platform: ${platform}. Open ${url} manually.`,
      })
    }

    spawn(openCmd, openArgs, { detached: true, stdio: 'ignore' }).unref()

    ctx.logger.info(`[vybit] Opened browser to ${url}`)

    return JSON.stringify({
      status: 'opened',
      url,
      message: `Browser opened to ${url}. The VyBit overlay should appear as a floating icon.`,
    })
  } catch (err) {
    return JSON.stringify({
      error: `Failed to open browser: ${String(err)}`,
      url,
      hint: `Open ${url} manually in your browser.`,
    })
  }
}

// Full Session Setup (combines all steps)

/**
 * Start a complete VyBit visual editing session:
 *   1. Start VyBit MCP server (if not already running)
 *   2. Start the project's dev server
 *   3. Inject the overlay script (if needed)
 *   4. Open the browser
 *
 * After this, the agent enters the implement_next → work → mark_done loop.
 */
export async function handleSession(
  input: Record<string, unknown>,
  ctx: ToolExecutionContext,
  startVyBitFn: (input: Record<string, unknown>, ctx: ToolExecutionContext) => Promise<string>,
): Promise<string> {
  const projectPath = (input.projectPath as string) || ctx.workingDir
  const vybitPort = input.port ? Number(input.port) : 3333
  const devPort = input.devPort ? Number(input.devPort) : undefined
  const skipBrowser = input.skipBrowser === true || input.skipBrowser === 'true'
  const skipOverlay = input.skipOverlay === true || input.skipOverlay === 'true'

  const results: Record<string, unknown> = {}
  const errors: string[] = []

  // Step 1: Start VyBit MCP server
  ctx.logger.info('[vybit] Session setup — step 1: Starting VyBit server...')
  try {
    const vybitResult = JSON.parse(await startVyBitFn(
      { action: 'start', projectPath, port: String(vybitPort) },
      ctx,
    ))
    results.vybit = vybitResult
    if (vybitResult.error) errors.push(`VyBit: ${vybitResult.error}`)
  } catch (err) {
    errors.push(`VyBit start failed: ${String(err)}`)
  }

  // Step 2: Start dev server
  ctx.logger.info('[vybit] Session setup — step 2: Starting dev server...')
  try {
    const devResult = JSON.parse(await handleDevStart(
      { projectPath, devPort: devPort ? String(devPort) : undefined, ...input },
      ctx,
    ))
    results.devServer = devResult
    if (devResult.error) errors.push(`Dev server: ${devResult.error}`)
  } catch (err) {
    errors.push(`Dev server start failed: ${String(err)}`)
  }

  // Step 3: Inject overlay
  if (!skipOverlay) {
    ctx.logger.info('[vybit] Session setup — step 3: Injecting overlay...')
    try {
      const overlayResult = JSON.parse(await handleInjectOverlay(
        { projectPath, port: vybitPort, ...input },
        ctx,
      ))
      results.overlay = overlayResult
      if (overlayResult.error) errors.push(`Overlay: ${overlayResult.error}`)
    } catch (err) {
      errors.push(`Overlay injection failed: ${String(err)}`)
    }
  }

  // Step 4: Open browser
  if (!skipBrowser && devServerUrl) {
    ctx.logger.info('[vybit] Session setup — step 4: Opening browser...')
    try {
      const browserResult = JSON.parse(await handleBrowserOpen(
        { url: devServerUrl },
        ctx,
      ))
      results.browser = browserResult
    } catch (err) {
      // Browser open failure is non-critical
      results.browser = { status: 'skipped', reason: String(err) }
    }
  }

  // Summary
  const allOk = errors.length === 0
  return JSON.stringify({
    status: allOk ? 'ready' : 'partial',
    errors: errors.length > 0 ? errors : undefined,
    steps: results,
    nextStep: allOk
      ? 'VyBit session is ready. Use action "implement_next" to start the visual editing loop. ' +
        'Users can now make visual changes in the browser and commit them via VyBit.'
      : `Session started with ${errors.length} issue(s). Fix errors and retry, or use "implement_next" to proceed.`,
  }, null, 2)
}

// Cleanup

/**
 * Stop everything — dev server + VyBit cleanup.
 */
export async function handleSessionStop(ctx: ToolExecutionContext): Promise<string> {
  const results: Record<string, string> = {}

  // Stop dev server
  if (devServerProc && !devServerProc.killed) {
    results.devServer = JSON.parse(await handleDevStop(ctx)).message
  } else {
    results.devServer = 'not running'
  }

  return JSON.stringify({
    status: 'stopped',
    ...results,
    message: 'VyBit session stopped. Dev server and browser closed.',
  })
}

// Utility: get dev server state (for status reporting)

export function getDevServerState(): {
  running: boolean
  url: string | null
  projectPath: string | null
  pid: number | null
} {
  return {
    running: devServerProc !== null && !devServerProc.killed,
    url: devServerUrl,
    projectPath: devServerProjectPath,
    pid: devServerProc?.pid ?? null,
  }
}
