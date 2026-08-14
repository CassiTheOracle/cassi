import { NextRequest, NextResponse } from 'next/server'
import { cassiFetch } from '@/lib/cassicore/client'

interface CommandBody {
  command: string
}

/**
 * POST /api/cassicore/sessions/[sessionId]/command
 *
 * Executes a slash command in a session.
 * Body: { command }
 * Proxies CassiCore's POST /sessions/:id/command endpoint.
 */
export async function POST(
  req: NextRequest,
  { params }: { params: Promise<{ sessionId: string }> }
) {
  const { sessionId } = await params

  try {
    const body = (await req.json()) as CommandBody
    const { command } = body

    if (!command || typeof command !== 'string') {
      return NextResponse.json(
        { error: 'Command is required' },
        { status: 400 }
      )
    }

    const res = await cassiFetch(`/sessions/${sessionId}/command`, {
      method: 'POST',
      body: JSON.stringify({ command }),
    })

    if (!res.ok) {
      const text = await res.text().catch(() => res.statusText)
      return NextResponse.json(
        { error: text, status: res.status },
        { status: res.status }
      )
    }

    return NextResponse.json(await res.json())
  } catch {
    return NextResponse.json(
      { error: 'CassiCore daemon unreachable' },
      { status: 503 }
    )
  }
}
