import { NextResponse } from 'next/server'
import { cassiFetch } from '@/lib/cassicore/client'

/**
 * GET /api/cassicore/system-prompt
 *
 * Returns the current system prompt with individual sections.
 * Proxies CassiCore's GET /system-prompt endpoint.
 */
export async function GET() {
  try {
    const res = await cassiFetch('/system-prompt')
    if (!res.ok) {
      return NextResponse.json(
        { error: 'Failed to fetch system prompt', status: res.status },
        { status: 503 }
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

/**
 * POST /api/cassicore/system-prompt
 *
 * Triggers a system prompt reload from disk.
 * Proxies CassiCore's POST /system-prompt/reload endpoint.
 */
export async function POST() {
  try {
    const res = await cassiFetch('/system-prompt/reload', { method: 'POST' })
    if (!res.ok) {
      return NextResponse.json(
        { error: 'Failed to reload system prompt', status: res.status },
        { status: 503 }
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
