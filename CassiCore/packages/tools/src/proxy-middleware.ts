/**
 * TOOLS-LOCAL — tool proxy middleware seam (shell-exec).
 *
 * Signature-faithful proxy seam for shell execution (`executeToolWithProxy`,
 * `isToolProxyEnabled`). This is a tools-owned capability, NOT a host-vendored
 * dependency: when `CASSI_TOOL_PROXY_URL` is unset (default) it falls through
 * to the native executor, matching the source's "no CASSI_TOOL_PROXY_URL"
 * path. Relocated out of `vendor/core/` (where it was mislabeled as a host
 * stub) into the tools package proper — P1 host↔tools|mcp cycle resolution.
 */

/** Proxy tool call request shape. */
export interface ToolCall {
  tool_name: string
  parameters: Record<string, any>
}

/** Proxy tool result shape. */
export interface ToolResult {
  [key: string]: any
}

const PROXY_URL: string | undefined = process.env.CASSI_TOOL_PROXY_URL

/**
 * Execute a tool, routing through the proxy middleware when configured.
 * Falls back to the native executor otherwise.
 */
export async function executeToolWithProxy(
  toolName: string,
  params: Record<string, any>,
  nativeExecutor?: () => Promise<string>,
): Promise<string> {
  if (PROXY_URL) {
    try {
      const response = await fetch(PROXY_URL, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ tool_name: toolName, parameters: params }),
      })
      if (!response.ok) throw new Error(`Proxy error: ${response.status}`)
      const result = (await response.json()) as ToolResult
      return result.stdout || result.content || JSON.stringify(result)
    } catch {
      /* fall through to native on proxy failure */
    }
  }
  if (nativeExecutor) return nativeExecutor()
  throw new Error(`No executor for: ${toolName}`)
}

/** Whether the proxy middleware is enabled. */
export function isToolProxyEnabled(): boolean {
  return !!PROXY_URL
}
