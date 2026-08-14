import { NextRequest, NextResponse } from 'next/server'
import { cassiFetch } from '@/lib/cassicore/client'

/**
 * GET /api/cassicore/memory/recent
 *
 * Returns recent memories.
 * Proxies CassiCore's GET /memory/recent endpoint.
 */
export async function GET(req: NextRequest) {
  try {
    const { searchParams } = new URL(req.url)
    const limit = searchParams.get('limit') ?? '10'

    const res = await cassiFetch(`/memory/recent?limit=${limit}`)
    if (!res.ok) {
      return NextResponse.json(
        { error: 'Failed to fetch recent memories', status: res.status },
        { status: 503 }
      )
    }
    return NextResponse.json(await res.json())
  } catch {
    return NextResponse.json(
      { error: 'CassiCore daemon unreachable', memories: [] },
      { status: 503 }
    )
  }
}
