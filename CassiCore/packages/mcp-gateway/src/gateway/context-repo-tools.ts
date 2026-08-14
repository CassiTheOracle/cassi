import { fetchIntelligence, fetchWithTimeout } from './helpers.js'
import type { ILogger } from '../../types/interfaces.js'

export const CONTEXT_REPO_TOOL = {
  name: 'context_repo',
  description: 'Context Repository operations — git-backed projection of Cassi\'s working memory. Lets humans inspect what Cassi is holding in mind via plain markdown.\n\nActions:\n- show: list current entities by section\n- log: recent commit history\n- diff: working-tree diff (or between refs)\n- inspect: read a specific file\n- rebuild: nuke + re-init the repo (safety net)\n- gc: prune loose objects + dead worktrees\n- stats: file counts, commits, disk usage',
  inputSchema: {
    type: 'object',
    properties: {
      action: { type: 'string', enum: ['show', 'log', 'diff', 'inspect', 'rebuild', 'gc', 'stats'] },
      section: { type: 'string', description: 'For show: system | laminae | entities | skills | sessions' },
      file: { type: 'string', description: 'For inspect: relative file path within the repo' },
      limit: { type: 'number', description: 'For log: number of commits' },
      args: { type: 'array', items: { type: 'string' }, description: 'For diff: extra git diff args' },
    },
    required: ['action'],
  },
}

export const CONTEXT_REPO_TOOL_NAME = 'context_repo'

async function postJSON(baseUrl: string, path: string, body: unknown): Promise<unknown> {
  const r = await fetchWithTimeout(new URL(path, baseUrl), {
    method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body),
  })
  if (!r.ok) throw new Error(`context-repo error (${r.status}): ${await r.text().catch(() => '')}`)
  return r.json()
}

export async function executeContextRepoTool(
  baseUrl: string,
  args: Record<string, unknown>,
  logger: ILogger,
): Promise<unknown> {
  const { action } = args
  if (!action) throw new Error('Missing required parameter: action')
  logger.info('Executing context_repo tool', { action })

  switch (action) {
    case 'show': {
      const params = new URLSearchParams()
      if (args.section) params.set('section', String(args.section))
      const qs = params.toString()
      return await fetchIntelligence(baseUrl, `/context-repo/show${qs ? '?' + qs : ''}`)
    }
    case 'log': {
      const params = new URLSearchParams()
      if (args.limit) params.set('limit', String(args.limit))
      const qs = params.toString()
      return await fetchIntelligence(baseUrl, `/context-repo/log${qs ? '?' + qs : ''}`)
    }
    case 'diff':
      return await postJSON(baseUrl, '/context-repo/diff', { args: args.args ?? [] })
    case 'inspect': {
      if (!args.file) throw new Error('inspect requires: file')
      const params = new URLSearchParams({ file: String(args.file) })
      return await fetchIntelligence(baseUrl, `/context-repo/inspect?${params.toString()}`)
    }
    case 'rebuild':
      return await postJSON(baseUrl, '/context-repo/rebuild', {})
    case 'gc':
      return await postJSON(baseUrl, '/context-repo/gc', {})
    case 'stats':
      return await fetchIntelligence(baseUrl, '/context-repo/stats')
    default:
      throw new Error(`Unknown context_repo action: ${action}`)
  }
}

export function getContextRepoTool(): typeof CONTEXT_REPO_TOOL { return CONTEXT_REPO_TOOL }
