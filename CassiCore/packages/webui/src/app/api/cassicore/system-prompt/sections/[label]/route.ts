import { NextRequest, NextResponse } from 'next/server'
import { cassiFetch } from '@/lib/cassicore/client'

/**
 * POST /api/cassicore/system-prompt/sections/:label
 *
 * Updates a specific persona section (IDENTITY, SOUL, USER, MEMORY_INDEX).
 * Proxies CassiCore's POST /system-prompt/sections/:label endpoint.
 */
export async function POST(
  req: NextRequest,
  { params }: { params: Promise<{ label: string }> }
) {
  try {
    const { label } = await params
    const body = await req.json()

    const res = await cassiFetch(`/system-prompt/sections/${encodeURIComponent(label)}`, {
      method: 'POST',
      body: JSON.stringify(body),
    })
    if (!res.ok) {
      const text = await res.text().catch(() => res.statusText)
      return NextResponse.json(
        { error: `Failed to update section: ${text}`, status: res.status },
        { status: res.status }
      )
    }
    const data = await res.json()
    return NextResponse.json(data)
  } catch {
    return NextResponse.json(
      { error: 'CassiCore daemon unreachable' },
      { status: 503 }
    )
  }
}
