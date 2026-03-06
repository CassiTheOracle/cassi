import { NextRequest, NextResponse } from 'next/server'
import { cassiFetch } from '@/lib/cassicore/client'

interface SearchBody {
  query: string
  limit?: number
}

/**
 * POST /api/cassicore/memory/search
 *
 * Universal memory search endpoint.
 * Body: { query, limit? }
 * Proxies CassiCore's POST /memory/universal-search endpoint.
 */
export async function POST(req: NextRequest) {
  try {
    const body = (await req.json()) as SearchBody
    const { query, limit = 10 } = body

    if (!query || typeof query !== 'string') {
      return NextResponse.json(
        { error: 'Query is required' },
        { status: 400 }
      )
    }

    const res = await cassiFetch('/memory/universal-search', {
      method: 'POST',
      body: JSON.stringify({ query, limit }),
    })

    if (!res.ok) {
      return NextResponse.json(
        { error: 'Search failed', status: res.status },
        { status: 503 }
      )
    }

    return NextResponse.json(await res.json())
  } catch {
    return NextResponse.json(
      { error: 'CassiCore daemon unreachable', results: [] },
      { status: 503 }
    )
  }
}
