import { NextResponse } from 'next/server'
import { cassiFetch } from '@/lib/cassicore/client'

/**
 * GET /api/cassicore/models
 *
 * Returns available models list.
 * Proxies CassiCore's GET /models endpoint.
 */
export async function GET() {
  try {
    const res = await cassiFetch('/models')
    if (!res.ok) {
      return NextResponse.json(
        { error: 'Failed to fetch models', status: res.status },
        { status: 503 }
      )
    }
    return NextResponse.json(await res.json())
  } catch {
    return NextResponse.json(
      { error: 'CassiCore daemon unreachable', models: [] },
      { status: 503 }
    )
  }
}
