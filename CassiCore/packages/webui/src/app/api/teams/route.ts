import { NextResponse } from 'next/server'
import { cassiJSON } from '@/lib/cassicore/client'

/**
 * GET /api/teams
 *
 * Returns the list of CassiCore multi-agent teams.
 * Proxies GET /teams from the daemon.
 */
export async function GET() {
  try {
    const data = await cassiJSON<{ teams?: Array<Record<string, unknown>> }>('/teams')
    // Daemon returns { teams: [...] } — Agno expects a plain array
    const teams = data.teams ?? (Array.isArray(data) ? data : [])
    // Shape into Agno-compatible format
    return NextResponse.json(teams.map(t => ({
      team_id: t.id,
      name: t.goal ?? `Team ${String(t.id).slice(0, 8)}`,
      status: t.status ?? 'unknown',
      agent_count: t.agentCount ?? 0,
      started_at: t.startedAt,
    })))
  } catch {
    return NextResponse.json([])
  }
}
