import type { ToolDefinition, ToolHandler, ToolExecutionContext } from '../types.js'

export const webFetchDefinition: ToolDefinition = {
  name: 'web_fetch',
  description: 'Fetch the content of a URL and return it as plain text (HTML stripped).',
  parameters: {
    type: 'object',
    properties: {
      url:       { type: 'string', description: 'URL to fetch (http or https)' },
      max_chars: { type: 'number', description: 'Maximum characters to return (default 50000)' },
    },
    required: ['url'],
  },
  timeoutMs: 30_000,
}

const DEFAULT_MAX = 50_000

export const webFetchHandler: ToolHandler = async (input, ctx: ToolExecutionContext) => {
  const url      = input['url'] as string
  const maxChars = (input['max_chars'] as number | undefined) ?? DEFAULT_MAX

  // Domain allowlist check
  if (ctx.networkAllowlist.length > 0 && !ctx.networkAllowlist.includes('*')) {
    let hostname: string
    try { hostname = new URL(url).hostname } catch { return `Error: invalid URL — ${url}` }
    const allowed = ctx.networkAllowlist.some(d => hostname.endsWith(d))
    if (!allowed) return `Error: domain ${hostname} not in network allowlist`
  }

  let res: Response
  try {
    res = await fetch(url, {
      headers: { 'User-Agent': 'CassieCore/0.1 (+https://github.com/cassiecore)' },
      signal: AbortSignal.timeout(25_000),
    })
  } catch (err) {
    return `Error fetching ${url}: ${String(err)}`
  }

  if (!res.ok) return `Error: HTTP ${res.status} from ${url}`

  let text = await res.text().catch(() => '')

  // Strip HTML to readable text
  text = stripHtml(text)

  if (text.length > maxChars) {
    text = text.slice(0, maxChars) + `\n[content truncated at ${maxChars} chars]`
  }

  return text || '(empty response)'
}

/** Minimal HTML → plain text: strip tags, decode common entities */
function stripHtml(html: string): string {
  return html
    .replace(/<script[\s\S]*?<\/script>/gi, '')
    .replace(/<style[\s\S]*?<\/style>/gi, '')
    .replace(/<[^>]+>/g, ' ')
    .replace(/&amp;/g, '&')
    .replace(/&lt;/g, '<')
    .replace(/&gt;/g, '>')
    .replace(/&quot;/g, '"')
    .replace(/&#39;/g, "'")
    .replace(/&nbsp;/g, ' ')
    .replace(/\s{3,}/g, '\n\n')
    .trim()
}
