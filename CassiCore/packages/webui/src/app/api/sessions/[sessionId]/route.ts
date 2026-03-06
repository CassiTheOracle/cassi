import { NextRequest, NextResponse } from 'next/server'
import { cassiFetch } from '@/lib/cassicore/client'

/**
 * DELETE /api/sessions/[sessionId]
 * Proxies session deletion to CassiCore.
 */
export async function DELETE(
  _req: NextRequest,
  { params }: { params: Promise<{ sessionId: string }> }
) {
  const { sessionId } = await params
  try {
    const res = await cassiFetch(`/sessions/${sessionId}`, { method: 'DELETE' })
    if (!res.ok) {
      const text = await res.text().catch(() => res.statusText)
      return NextResponse.json({ error: text }, { status: res.status })
    }
    return new NextResponse(null, { status: 204 })
  } catch (err) {
    return NextResponse.json({ error: String(err) }, { status: 500 })
  }
}
