import { NextRequest, NextResponse } from 'next/server'
import { cassiJSON } from '@/lib/cassicore/client'
import { listSessions } from '@/lib/cassicore/webui-sessions'

/**
 * GET /api/sessions
 *
 * Lists CassiCore sessions, shaped into the Agno Sessions contract:
 * { data: SessionEntry[], meta: Pagination }
 *
 * Merges daemon-persisted sessions with webui sessions tracked in BFF memory
 * (daemon's session pipeline doesn't appear in GET /sessions).
 */
export async function GET(req: NextRequest) {
  try {
    const { searchParams } = new URL(req.url)
    const pageParam = parseInt(searchParams.get('page') ?? '1', 10)
    const limitParam = parseInt(searchParams.get('limit') ?? '50', 10)

    // Load daemon sessions (may be empty for webui channel)
    const daemonSessions = await cassiJSON<{ sessions: Array<Record<string, unknown>> }>('/sessions')
      .then(r => r.sessions ?? [])
      .catch(() => [])

    // Load BFF-tracked webui sessions
    const webuiSessions = listSessions()
    const webuiIds = new Set(webuiSessions.map(s => s.id))

    // Merge: daemon sessions first, then webui sessions not already in daemon list
    const daemonEntries = daemonSessions.map((s) => ({
      session_id: String(s.id),
      session_name: (s.title as string | null) ?? (s.firstMessage as string | null) ?? `Session ${String(s.id).slice(0, 8)}`,
      created_at: typeof s.createdAt === 'string'
        ? Math.floor(new Date(s.createdAt as string).getTime() / 1000)
        : typeof s.createdAt === 'number'
          ? Math.floor((s.createdAt as number) / 1000)
          : Math.floor(Date.now() / 1000),
      updated_at: typeof s.lastActiveAt === 'string'
        ? Math.floor(new Date(s.lastActiveAt as string).getTime() / 1000)
        : undefined,
    }))

    const daemonIds = new Set(daemonEntries.map(e => e.session_id))
    const webuiEntries = webuiSessions
      .filter(s => !daemonIds.has(s.id))
      .map(s => ({
        session_id: s.id,
        session_name: s.firstMessage || `Session ${s.id.slice(0, 8)}`,
        created_at: Math.floor(s.createdAt / 1000),
        updated_at: Math.floor(s.lastActiveAt / 1000),
      }))

    // Exclude internal system sessions (thinker, agent:*)
    const allEntries = [...daemonEntries.filter(e =>
      !e.session_id.startsWith('thinker:') &&
      !e.session_id.startsWith('agent:') &&
      !e.session_id.startsWith('team:')
    ), ...webuiEntries]
      .sort((a, b) => (b.updated_at ?? b.created_at) - (a.updated_at ?? a.created_at))

    const total = allEntries.length
    const start = (pageParam - 1) * limitParam
    const page = allEntries.slice(start, start + limitParam)

    return NextResponse.json({
      data: page,
      meta: { page: pageParam, limit: limitParam, total_pages: Math.ceil(Math.max(total, 1) / limitParam), total_count: total },
    })
  } catch (err) {
    return NextResponse.json({ error: String(err) }, { status: 500 })
  }
}
