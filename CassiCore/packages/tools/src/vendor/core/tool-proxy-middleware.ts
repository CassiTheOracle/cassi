/**
 * VENDOR RUNTIME STUB — `core/tool-proxy-middleware.ts` (host, P7).
 *
 * Placeholder for the tool proxy middleware seam consumed by shell-exec.ts
 * (tools). Signature-faithful (`executeToolWithProxy`, `isToolProxyEnabled`);
 * no proxy endpoint configured in the stub — falls through to the native
 * executor, matching the source's "no CASSI_TOOL_PROXY_URL" path. Owned by the
 * host package (P7). Re-pointed there.
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
