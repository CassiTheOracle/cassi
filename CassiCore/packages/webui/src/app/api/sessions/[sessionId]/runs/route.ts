import { NextRequest, NextResponse } from 'next/server'
import { cassiJSON } from '@/lib/cassicore/client'

interface CassiMessage {
  role: 'user' | 'assistant' | 'system'
  content: string | unknown[]
}

/**
 * GET /api/sessions/[sessionId]/runs
 *
 * Returns session message history shaped as Agno ChatEntry[].
 * Maps CassiCore's linear history (user+assistant pairs) to the
 * { message, response } pair format that agent-ui renders.
 */
export async function GET(
  _req: NextRequest,
  { params }: { params: Promise<{ sessionId: string }> }
) {
  const { sessionId } = await params
  try {
    const result = await cassiJSON<{ messages: CassiMessage[] }>(
      `/sessions/${sessionId}/messages?limit=200`
    )

    const messages = result.messages ?? []
    const now = Math.floor(Date.now() / 1000)

    // Pair up user/assistant messages into Agno ChatEntry format
    const runs: unknown[] = []
    for (let i = 0; i < messages.length; i++) {
      const msg = messages[i]
      if (msg.role === 'user') {
        const userContent = typeof msg.content === 'string'
          ? msg.content
          : JSON.stringify(msg.content)
        // Look ahead for the matching assistant response
        const next = messages[i + 1]
        const assistantContent =
          next?.role === 'assistant'
            ? typeof next.content === 'string'
              ? next.content
              : JSON.stringify(next.content)
            : ''
        if (next?.role === 'assistant') i++

        runs.push({
          message: {
            role: 'user',
            content: userContent,
            created_at: now,
          },
          response: {
            content: assistantContent,
            created_at: now,
          },
        })
      }
    }

    return NextResponse.json({ data: runs })
  } catch (err) {
    // Return empty history gracefully — session may be new
    console.error(`[webui] Failed to load session history for ${sessionId}:`, err)
    return NextResponse.json({ data: [] })
  }
}
