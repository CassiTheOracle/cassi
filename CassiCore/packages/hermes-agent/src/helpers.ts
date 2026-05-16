export function log(...args: any[]): void {
  const msg = args.map(a => typeof a === 'string' ? a : JSON.stringify(a)).join(' ')
  process.stderr.write(`[hermes-gateway] ${msg}\n`)
}

export function fetchJson(
  url: string,
  opts: { method?: string; body?: any; timeoutMs?: number } = {},
): Promise<any> {
  const controller = new AbortController()
  const timer = setTimeout(() => controller.abort(), opts.timeoutMs ?? 10_000)
  return fetch(url, {
    method: opts.method ?? 'GET',
    headers: opts.body ? { 'Content-Type': 'application/json' } : undefined,
    body: opts.body ? JSON.stringify(opts.body) : undefined,
    signal: controller.signal,
  }).then(async r => {
    if (!r.ok) {
      const text = await r.text().catch(() => `HTTP ${r.status}`)
      throw new Error(`Daemon returned ${r.status}: ${text.slice(0, 500)}`)
    }
    return r.json()
  }).finally(() => clearTimeout(timer))
}

export function formatError(err: unknown): { content: Array<{ type: 'text'; text: string }>; isError: true } {
  return { content: [{ type: 'text', text: `Error: ${err instanceof Error ? err.message : String(err)}` }], isError: true }
}

export function formatText(text: string): { content: Array<{ type: 'text'; text: string }> } {
  return { content: [{ type: 'text', text }] }
}
