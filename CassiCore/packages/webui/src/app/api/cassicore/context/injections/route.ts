import { NextRequest, NextResponse } from 'next/server'
import { cassiFetch } from '@/lib/cassicore/client'

/**
 * GET /api/cassicore/context/injections
 *
 * Returns current pending injections for the active session.
 * Proxies CassiCore's GET /context/inject/:sessionId endpoint.
 * 
 * If no sessionId is provided, attempts to use '*' (all sessions).
 */
export async function GET(req: NextRequest) {
  try {
    const { searchParams } = new URL(req.url)
    const sessionId = searchParams.get('sessionId') ?? '*'

    const res = await cassiFetch(`/context/inject/${encodeURIComponent(sessionId)}`)
    if (!res.ok) {
      // If the endpoint doesn't exist yet or session not found, return empty
      if (res.status === 404 || res.status === 503) {
        return NextResponse.json({ parts: [], totalChars: 0 })
      }
      return NextResponse.json(
        { error: 'Failed to fetch injections', status: res.status },
        { status: 503 }
      )
    }
    const data = await res.json()
    // Normalize response shape
    const parts = data.parts ?? data.injections ?? []
    const totalChars = data.totalChars ?? parts.reduce((sum: number, p: { charCount?: number }) => sum + (p.charCount ?? 0), 0)
    return NextResponse.json({ parts, totalChars })
  } catch {
    return NextResponse.json(
      { parts: [], totalChars: 0 },
      { status: 200 } // Degrade gracefully
    )
  }
}
