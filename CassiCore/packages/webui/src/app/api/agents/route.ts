import { NextResponse } from 'next/server'
import { cassiJSON, CASSICORE_URL } from '@/lib/cassicore/client'

/**
 * GET /api/agents
 *
 * Agno expects a list of agents. CassiCore exposes a single "Cassi" agent
 * whose identity is synthesized from the daemon's health/providers data.
 */
export async function GET() {
  try {
    // Fetch active model info from the daemon
    const health = await cassiJSON<{ version?: string; checks?: Array<{ name: string }> }>(
      '/health'
    ).catch(() => ({ version: 'unknown' }))

    const agent = {
      // Use both `id` and `agent_id` for compatibility with Agno and internal types
      id: 'cassi',
      agent_id: 'cassi',
      name: 'Cassi',
      description: 'CassiCore cognitive agent daemon',
      model: {
        name: 'CassiCore',
        model: 'cassi',
        provider: 'cassicore',
      },
      storage: true,
      endpoint: CASSICORE_URL,
      version: (health as Record<string, unknown>).version ?? 'unknown',
    }

    return NextResponse.json([agent])
  } catch (err) {
    return NextResponse.json({ error: String(err) }, { status: 503 })
  }
}
