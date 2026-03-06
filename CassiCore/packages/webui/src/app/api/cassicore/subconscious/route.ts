import { NextResponse } from 'next/server'
import { cassiFetch } from '@/lib/cassicore/client'

/**
 * GET /api/cassicore/subconscious
 *
 * Returns subconscious stats.
 * Proxies CassiCore's GET /intelligence/subconscious/stats endpoint.
 */
export async function GET() {
  try {
    const res = await cassiFetch('/intelligence/subconscious/stats')
    if (!res.ok) {
      return NextResponse.json(
        { error: 'Failed to fetch subconscious stats', status: res.status },
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
