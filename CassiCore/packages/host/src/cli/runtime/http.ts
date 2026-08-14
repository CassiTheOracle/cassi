import { fail } from './output.js'

const DEFAULT_ADMIN_URL = process.env.CASSICORE_URL || 'http://127.0.0.1:7433'

export interface RequestOptions {
  query?: Record<string, string | number | boolean | undefined>
  body?: unknown
  allowNotOk?: boolean
  /** Request timeout in milliseconds. Default: 30000 */
  timeout?: number
}

export interface JsonResponse<T> {
  status: number
  ok: boolean
  data: T
}

export function getAdminUrl(): string {
  const normalized = DEFAULT_ADMIN_URL.replace(/\/$/, '')
  return normalized.replace('://localhost', '://127.0.0.1')
}

export function buildUrl(pathname: string, query?: Record<string, string | number | boolean | undefined>): string {
  const url = new URL(pathname, `${getAdminUrl()}/`)
  if (query) {
    for (const [key, value] of Object.entries(query)) {
      if (value === undefined) continue
      url.searchParams.set(key, String(value))
    }
  }
  return url.toString()
}

export async function getJson<T>(pathname: string, options: RequestOptions = {}): Promise<JsonResponse<T>> {
  return requestJson<T>('GET', pathname, options)
}

export async function postJson<T>(pathname: string, options: RequestOptions = {}): Promise<JsonResponse<T>> {
  return requestJson<T>('POST', pathname, options)
}

export async function deleteJson<T>(pathname: string, options: RequestOptions = {}): Promise<JsonResponse<T>> {
  return requestJson<T>('DELETE', pathname, options)
}

const DEFAULT_TIMEOUT_MS = 30000

async function requestJson<T>(method: string, pathname: string, options: RequestOptions): Promise<JsonResponse<T>> {
  const timeoutMs = options.timeout ?? DEFAULT_TIMEOUT_MS
  const controller = new AbortController()
  const timeoutId = setTimeout(() => controller.abort(), timeoutMs)

  try {
    const response = await fetch(buildUrl(pathname, options.query), {
      method,
      headers: options.body === undefined ? undefined : { 'content-type': 'application/json' },
      body: options.body === undefined ? undefined : JSON.stringify(options.body),
      signal: controller.signal,
    })

    const rawText = await response.text()
    const data = parseJson<T>(rawText)

    if (!response.ok && !options.allowNotOk) {
      const message = getErrorMessage(data, response.status, response.statusText)
      fail(`${method} ${pathname} failed (${response.status}): ${message}`)
    }

    return {
      status: response.status,
      ok: response.ok,
      data,
    }
  } catch (error) {
    if (controller.signal.aborted) {
      fail(`${method} ${pathname} timed out after ${timeoutMs}ms`)
    }
    throw error
  } finally {
    clearTimeout(timeoutId)
  }
}

function parseJson<T>(text: string): T {
  if (!text.trim()) {
    return {} as T
  }

  try {
    return JSON.parse(text) as T
  } catch (error) {
    fail(`Failed to parse daemon response: ${String(error)}`)
  }
}

function getErrorMessage(value: unknown, status: number, fallback: string): string {
  if (value && typeof value === 'object' && 'error' in value) {
    return String((value as { error: unknown }).error)
  }

  return fallback || `HTTP ${status}`
}