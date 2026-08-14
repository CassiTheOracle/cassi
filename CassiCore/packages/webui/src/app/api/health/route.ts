import { NextResponse } from 'next/server'
import { cassiFetch } from '@/lib/cassicore/client'

/**
 * GET /api/health
 * Proxies CassiCore's health endpoint, returning a simple status code
 * so agent-ui's status check succeeds.
 */
export async function GET() {
  try {
    const res = await cassiFetch('/health')
    const body = await res.json()
    return NextResponse.json(body, { status: res.status })
  } catch {
    return NextResponse.json({ status: 'error', message: 'CassiCore unreachable' }, { status: 503 })
  }
}
