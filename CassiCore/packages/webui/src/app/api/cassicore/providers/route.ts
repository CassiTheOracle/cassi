import { NextResponse } from 'next/server'
import { cassiFetch } from '@/lib/cassicore/client'

/**
 * GET /api/cassicore/providers
 *
 * Returns provider health with account details.
 * Proxies CassiCore's GET /health/providers endpoint.
 */
export async function GET() {
  try {
    const res = await cassiFetch('/health/providers')
    if (!res.ok) {
      return NextResponse.json(
        { error: 'Failed to fetch providers', status: res.status },
        { status: 503 }
      )
    }
    return NextResponse.json(await res.json())
  } catch {
    return NextResponse.json(
      { error: 'CassiCore daemon unreachable', providers: [] },
      { status: 503 }
    )
  }
}
