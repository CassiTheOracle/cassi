import { NextRequest, NextResponse } from 'next/server'
import { cassiFetch } from '@/lib/cassicore/client'

/**
 * POST /api/cassicore/sessions
 *
 * Creates a new CassiCore session with optional custom name and permanent flag.
 * Proxies CassiCore's POST /sessions endpoint.
 *
 * Body:
 *   name?:      string  — custom session title (default: "Untitled")
 *   channelId?: string  — channel identifier (default: "channel:webui")
 *   senderId?:  string  — sender identifier (default: "webui-user")
 *   permanent?: boolean — marks session as non-ephemeral (to-be-implemented)
 *   sessionId?: string  — optional custom session ID
 */
export async function POST(req: NextRequest) {
  try {
    const body = await req.json()

    const res = await cassiFetch('/sessions', {
      method: 'POST',
      body: JSON.stringify(body),
    })
    if (!res.ok) {
      const text = await res.text().catch(() => res.statusText)
      return NextResponse.json(
        { error: `Failed to create session: ${text}`, status: res.status },
        { status: res.status }
      )
    }
    const data = await res.json()
    return NextResponse.json(data, { status: 201 })
  } catch {
    return NextResponse.json(
      { error: 'CassiCore daemon unreachable' },
      { status: 503 }
    )
  }
}
