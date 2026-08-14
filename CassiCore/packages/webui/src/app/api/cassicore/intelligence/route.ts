import { NextResponse } from 'next/server'
import { cassiFetch } from '@/lib/cassicore/client'

/**
 * GET /api/cassicore/intelligence
 *
 * Returns the comprehensive intelligence activity snapshot.
 * Proxies CassiCore's GET /intelligence/activity endpoint.
 */
export async function GET() {
  try {
    const res = await cassiFetch('/intelligence/activity')
    if (!res.ok) {
      return NextResponse.json(
        { error: 'Failed to fetch intelligence activity', status: res.status },
        { status: 503 }
      )
    }
    const data = await res.json()
    // Deduplicate modules by name (daemon sometimes registers same module twice)
    if (data?.modules && Array.isArray(data.modules)) {
      const seen = new Set<string>()
      data.modules = data.modules.filter((m: Record<string, unknown>) => {
        const key = String(m.name)
        if (seen.has(key)) return false
        seen.add(key)
        return true
      })
    }
    return NextResponse.json(data)
  } catch {
    return NextResponse.json(
      { error: 'CassiCore daemon unreachable', modules: [] },
      { status: 503 }
    )
  }
}
