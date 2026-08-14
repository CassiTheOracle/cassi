import { NextResponse } from 'next/server'
import { cassiFetch } from '@/lib/cassicore/client'

/**
 * GET /api/cassicore/thinker
 *
 * Returns thinker statistics.
 * Proxies CassiCore's GET /intelligence/thinker/stats endpoint.
 */
export async function GET() {
  try {
    const res = await cassiFetch('/intelligence/thinker/stats')
    if (!res.ok) {
      return NextResponse.json(
        { error: 'Failed to fetch thinker stats', status: res.status },
        { status: 503 }
      )
    }
    return NextResponse.json(await res.json())
  } catch {
    return NextResponse.json(
      { error: 'CassiCore daemon unreachable', stats: null },
      { status: 503 }
    )
  }
}
