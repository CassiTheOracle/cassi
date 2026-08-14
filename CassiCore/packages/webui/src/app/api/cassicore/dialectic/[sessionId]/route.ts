import { NextRequest, NextResponse } from 'next/server'
import { cassiFetch } from '@/lib/cassicore/client'

/**
 * GET /api/cassicore/dialectic/[sessionId]
 *
 * Returns recent Yang/Yin/Synthesis analyses for a session.
 * Proxies CassiCore's GET /dialectic/:sessionId/history endpoint.
 */
export async function GET(
  req: NextRequest,
  { params }: { params: Promise<{ sessionId: string }> }
) {
  const { sessionId } = await params
  const { searchParams } = new URL(req.url)
  const limit = searchParams.get('limit') ?? '10'

  try {
    const res = await cassiFetch(`/dialectic/${sessionId}/history?limit=${limit}`)
    if (!res.ok) {
      return NextResponse.json({ history: [] })
    }
    return NextResponse.json(await res.json())
  } catch {
    return NextResponse.json({ history: [] })
  }
}
