import { NextResponse } from 'next/server'
import { cassiFetch } from '@/lib/cassicore/client'

/**
 * GET /api/cassicore/info
 *
 * Returns capability discovery information.
 * Proxies CassiCore's GET /cassicore/info endpoint.
 */
export async function GET() {
  try {
    const res = await cassiFetch('/cassicore/info')
    if (!res.ok) {
      return NextResponse.json(
        { error: 'Failed to fetch info', status: res.status },
        { status: 503 }
      )
    }
    return NextResponse.json(await res.json())
  } catch {
    return NextResponse.json(
      { error: 'CassiCore daemon unreachable', version: 'unknown', capabilities: [] },
      { status: 503 }
    )
  }
}
