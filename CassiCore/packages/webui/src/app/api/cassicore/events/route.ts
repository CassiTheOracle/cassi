import { NextRequest, NextResponse } from 'next/server'
import { CASSICORE_URL } from '@/lib/cassicore/client'

/**
 * GET /api/cassicore/events
 *
 * Server-Sent Events (SSE) proxy for CassiCore's event stream.
 * Proxies GET /events/stream?sessionId=* with streaming pass-through.
 */
export async function GET(req: NextRequest) {
  const { searchParams } = new URL(req.url)
  // Default to '*' (all sessions) if not specified — daemon supports wildcard
  const sessionId = searchParams.get('sessionId') ?? '*'

  try {
    const upstreamUrl = `${CASSICORE_URL}/events/stream?sessionId=${encodeURIComponent(sessionId)}`
    const upstreamRes = await fetch(upstreamUrl)

    if (!upstreamRes.ok) {
      return NextResponse.json(
        { error: 'Failed to connect to event stream', status: upstreamRes.status },
        { status: 503 }
      )
    }

    // Stream the response through - pass SSE headers and body as-is
    const headers = new Headers()
    headers.set('Content-Type', 'text/event-stream')
    headers.set('Cache-Control', 'no-cache')
    headers.set('Connection', 'keep-alive')

    // Copy any other SSE-related headers from upstream
    const upstreamContentType = upstreamRes.headers.get('content-type')
    if (upstreamContentType) {
      headers.set('Content-Type', upstreamContentType)
    }

    return new Response(upstreamRes.body, {
      status: 200,
      headers,
    })
  } catch {
    return NextResponse.json(
      { error: 'CassiCore daemon unreachable' },
      { status: 503 }
    )
  }
}
