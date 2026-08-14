import { listProviderConfigKeys } from '@cassicore/providers'
import type { RenewResult, AccountEntry } from '../vendor/core/scripts/qwen-renew-accounts.js'

import type { ILogger } from '@cassicore/foundation'
import type http from 'node:http'

import type { AdminRuntimeFacade } from './runtime.js'

export interface ProvidersRoutesDeps {
  runtime: AdminRuntimeFacade
  logger: ILogger
  sendJSON: (res: http.ServerResponse, code: number, obj: unknown) => void
  parseBody: (req: http.IncomingMessage) => Promise<any>
  isObject: (v: unknown) => v is Record<string, unknown>
  mergeDeep: (target: any, src: any) => any
}

/**
 * @dep callers: handler (core/admin-api.ts)
 * @dep calls: sendJSON, defaultAccountsPath, renewAccountsFile, parseBody, setOverride [+15]
 * @dep flows: HandleProvidersRoutes → Json (1/4)
 * @dep module: Scripts
 * @dep risk: LOW | 1 caller, 1 flow, 1 module
 */

export async function handleProvidersRoutes(
  deps: ProvidersRoutesDeps,
  req: http.IncomingMessage,
  res: http.ServerResponse,
  method: string,
  pathname: string
): Promise<boolean> {
  const { runtime, sendJSON, parseBody, isObject, mergeDeep } = deps
  const layered = runtime.getConfig() as any

  // GET /providers
  if (method === 'GET' && pathname === '/providers') {
    try {
      const providersMap = runtime.getProviders()
      if (!providersMap) {
        sendJSON(res, 503, { error: 'providers not initialised' })
        return true
      }

      const ids = Array.from(providersMap.keys())
      sendJSON(res, 200, { providers: ids })
      return true
    } catch (err) {
      sendJSON(res, 500, { error: String(err) })
      return true
    }
  }

  // GET /providers/metrics
  if (method === 'GET' && pathname === '/providers/metrics') {
    try {
      const metrics = runtime.getProviderMetrics()
      if (metrics.providers.length === 0) {
        sendJSON(res, 503, { error: 'providers not initialised' })
        return true
      }

      sendJSON(res, 200, metrics)
      return true
    } catch (err) {
      sendJSON(res, 500, { error: String(err) })
      return true
    }
  }

  // GET /providers/qwen/stats
  if (method === 'GET' && pathname === '/providers/qwen/stats') {
    try {
      const providersMap = runtime.getProviders()
      if (!providersMap) {
        sendJSON(res, 503, { error: 'providers not initialised' })
        return true
      }

      const qwenProvider = providersMap.get('qwen')
      if (!qwenProvider) {
        sendJSON(res, 404, { error: 'qwen provider not found' })
        return true
      }

      if (typeof (qwenProvider as any).getStats === 'function') {
        const stats = (qwenProvider as any).getStats()
        const activeCount = typeof (qwenProvider as any).getActiveCount === 'function'
          ? (qwenProvider as any).getActiveCount()
          : undefined

        sendJSON(res, 200, {
          loadBalancing: true,
          activeCount,
          accounts: stats,
        })
        return true
      }

      sendJSON(res, 200, { loadBalancing: false, accounts: 1 })
      return true
    } catch (err) {
      sendJSON(res, 500, { error: String(err) })
      return true
    }
  }

  // GET /providers/qwen/accounts — list Qwen accounts from the accounts file
  if (method === 'GET' && pathname === '/providers/qwen/accounts') {
    try {
      const fs = await import('fs/promises')
      const file = (await import('../vendor/core/scripts/qwen-renew-accounts.js')).defaultAccountsPath()
      let accounts: AccountEntry[] = []
      try {
        const raw = await fs.readFile(file, 'utf-8')
        accounts = JSON.parse(raw) as AccountEntry[]
      } catch {
        // No accounts file yet
      }

      sendJSON(res, 200, {
        file,
        count: accounts.length,
        accounts: accounts.map(a => ({
          profileId: a.profileId,
          hasCredentials: !!a.credentials,
          hasApiKey: !!a.apiKey,
          baseUrl: a.baseUrl,
        })),
      })
      return true
    } catch (err) {
      sendJSON(res, 500, { error: String(err) })
      return true
    }
  }

  // POST /providers/qwen/renew — bulk renew all Qwen OAuth accounts
  if (method === 'POST' && pathname === '/providers/qwen/renew') {
    try {
      deps.logger.info('Starting Qwen account renewal')
      const { renewAccountsFile } = await import('../vendor/core/scripts/qwen-renew-accounts.js')
      const result: RenewResult = await renewAccountsFile()
      deps.logger.info('Qwen account renewal complete', { renewed: result.renewed, reauthenticated: result.reauthenticated, failed: result.failed })
      sendJSON(res, 200, { ok: true, ...result })
      return true
    } catch (err) {
      deps.logger.error('Qwen account renewal failed', { error: String(err) })
      sendJSON(res, 500, { error: String(err) })
      return true
    }
  }

  // GET /providers/config
  if (method === 'GET' && pathname === '/providers/config') {
    try {
      const getWithSource = typeof layered?.getWithSource === 'function'
        ? (k: string) => layered.getWithSource(k)
        : (k: string) => ({ value: layered?.get?.(k, undefined), source: undefined })

      const keys = [
        'providers.global.windowMs',
        'providers.global.maxRequestsPerWindow',
        'providers.global.timeoutMs',
      ]

      const configView: Record<string, unknown> = {}
      for (const k of keys) {
        try {
          configView[k] = getWithSource(k)
        } catch (err) {
          configView[k] = { value: runtime.getConfig()?.get(k, undefined), source: undefined }
        }
      }

      const overrides = typeof layered?.getOverrides === 'function' ? layered.getOverrides() : {}

      sendJSON(res, 200, { config: configView, overrides })
      return true
    } catch (err) {
      sendJSON(res, 500, { error: String(err) })
      return true
    }
  }

  // GET /providers/config/keys
  if (method === 'GET' && pathname === '/providers/config/keys') {
    try {
      const keys = listProviderConfigKeys()
      sendJSON(res, 200, { keys })
      return true
    } catch (err) {
      sendJSON(res, 500, { error: String(err) })
      return true
    }
  }

  // POST /providers/config
  if (method === 'POST' && pathname === '/providers/config') {
    try {
      const body = await parseBody(req)
      if (!body || typeof body !== 'object') {
        sendJSON(res, 400, { error: 'missing body' })
        return true
      }

      const mapping: Record<string, string> = {
        timeoutMs: 'providers.global.timeoutMs',
      }

      const updated: string[] = []

      if (typeof body.key === 'string' && Object.prototype.hasOwnProperty.call(body, 'value')) {
        const k = String(body.key)
        try {
          const existing = layered.get(k, undefined)
          const newVal = isObject(existing) && isObject(body.value) ? mergeDeep(existing, body.value) : body.value
          layered.setOverride(k, newVal, { reason: body.reason || 'admin' })
          updated.push(k)
        } catch (err) {
          sendJSON(res, 500, { error: String(err) })
          return true
        }
      } else {
        for (const friendly of Object.keys(mapping)) {
          if (Object.prototype.hasOwnProperty.call(body, friendly)) {
            const k = mapping[friendly]
            try {
              const existing = layered.get(k, undefined)
              const provided = (body as any)[friendly]
              const newVal = isObject(existing) && isObject(provided) ? mergeDeep(existing, provided) : provided
              layered.setOverride(k, newVal, { reason: body.reason || 'admin' })
              updated.push(k)
            } catch (err) {
              sendJSON(res, 500, { error: String(err) })
              return true
            }
          }
        }
      }

      try { if (typeof layered?.persistOverrides === 'function') await layered.persistOverrides() } catch (err) { deps.logger.warn('Failed to persist config overrides', { error: String(err) }); }
      try { await runtime.reloadConfig() } catch (err) { deps.logger.warn('Failed to reload daemon config', { error: String(err) }); }

      sendJSON(res, 200, { ok: true, updated })
      return true
    } catch (err) {
      sendJSON(res, 500, { error: String(err) })
      return true
    }
  }

  // DELETE /providers/config
  if (method === 'DELETE' && pathname === '/providers/config') {
    try {
      const body = await parseBody(req)
      const mapping: Record<string, string> = {
        timeoutMs: 'providers.global.timeoutMs',
      }

      let toRemove: string[] = []
      if (body && Array.isArray(body.keys)) {
        toRemove = body.keys.map(String)
      } else if (body && typeof body.key === 'string') {
        toRemove = [String(body.key)]
      } else if (body && typeof body === 'object' && Object.keys(body).length > 0) {
        for (const friendly of Object.keys(mapping)) {
          if ((body as any)[friendly]) toRemove.push(mapping[friendly])
        }
      } else {
        toRemove = Object.values(mapping)
      }

      const removed: string[] = []
      for (const k of toRemove) {
        try {
          layered.clearOverride(k)
          removed.push(k)
        } catch (err) { deps.logger.debug('Failed to clear config override', { key: k, error: String(err) }); }
      }

      try { if (typeof layered?.persistOverrides === 'function') await layered.persistOverrides() } catch (err) { deps.logger.warn('Failed to persist config overrides', { error: String(err) }); }
      try { await runtime.reloadConfig() } catch (err) { deps.logger.warn('Failed to reload daemon config', { error: String(err) }); }

      sendJSON(res, 200, { ok: true, removed })
      return true
    } catch (err) {
      sendJSON(res, 500, { error: String(err) })
      return true
    }
  }

  // POST /providers/config/set
  if (method === 'POST' && pathname === '/providers/config/set') {
    try {
      const body = await parseBody(req)
      if (!body || typeof body !== 'object') {
        sendJSON(res, 400, { error: 'missing body' })
        return true
      }

      const updated: string[] = []

      if (Array.isArray(body.updates)) {
        for (const u of body.updates) {
          if (!u || typeof u.key !== 'string' || !Object.prototype.hasOwnProperty.call(u, 'value')) continue
          const k = String(u.key)
          const v = (u as any).value
          try {
            const existing = layered.get(k, undefined)
            const newVal = isObject(existing) && isObject(v) ? mergeDeep(existing, v) : v
            layered.setOverride(k, newVal, { reason: u.reason || 'admin' })
            updated.push(k)
          } catch (err) { deps.logger.debug('Failed to set config override', { key: k, error: String(err) }); }
        }
      } else if (typeof body.key === 'string' && Object.prototype.hasOwnProperty.call(body, 'value')) {
        const k = String(body.key)
        const v = body.value
        try {
          const existing = layered.get(k, undefined)
          const newVal = isObject(existing) && isObject(v) ? mergeDeep(existing, v) : v
          layered.setOverride(k, newVal, { reason: body.reason || 'admin' })
          updated.push(k)
        } catch (err) {
          sendJSON(res, 500, { error: String(err) })
          return true
        }
      } else {
        sendJSON(res, 400, { error: 'expected { key, value } or { updates: [{ key, value }] }' })
        return true
      }

      try { if (typeof layered?.persistOverrides === 'function') await layered.persistOverrides() } catch (err) { deps.logger.warn('Failed to persist config overrides', { error: String(err) }); }
      try { await runtime.reloadConfig() } catch (err) { deps.logger.warn('Failed to reload daemon config', { error: String(err) }); }

      sendJSON(res, 200, { ok: true, updated })
      return true
    } catch (err) {
      sendJSON(res, 500, { error: String(err) })
      return true
    }
  }

  // POST /providers/config/apply
  if (method === 'POST' && pathname === '/providers/config/apply') {
    try {
      const body = await parseBody(req)
      if (!body || typeof body !== 'object') {
        sendJSON(res, 400, { error: 'missing body' })
        return true
      }

      const mapping: Record<string, string> = {
        timeoutMs: 'providers.global.timeoutMs',
      }

      const updated: string[] = []

      if (typeof body.key === 'string' && Object.prototype.hasOwnProperty.call(body, 'value')) {
        const k = String(body.key)
        try {
          const existing = layered.get(k, undefined)
          const newVal = isObject(existing) && isObject(body.value) ? mergeDeep(existing, body.value) : body.value
          layered.setOverride(k, newVal, { reason: body.reason || 'admin' })
          updated.push(k)
        } catch (err) {
          sendJSON(res, 500, { error: String(err) })
          return true
        }
      } else if (Array.isArray(body.updates)) {
        for (const u of body.updates) {
          if (!u || typeof u.key !== 'string' || !Object.prototype.hasOwnProperty.call(u, 'value')) continue
          const k = String(u.key)
          try {
            const existing = layered.get(k, undefined)
            const newVal = isObject(existing) && isObject(u.value) ? mergeDeep(existing, u.value) : u.value
            layered.setOverride(k, newVal, { reason: u.reason || 'admin' })
            updated.push(k)
          } catch (err) { deps.logger.debug('Failed to set config override', { key: k, error: String(err) }); }
        }
      } else {
        for (const friendly of Object.keys(mapping)) {
          if (Object.prototype.hasOwnProperty.call(body, friendly)) {
            const k = mapping[friendly]
            try {
              const existing = layered.get(k, undefined)
              const provided = (body as any)[friendly]
              const newVal = isObject(existing) && isObject(provided) ? mergeDeep(existing, provided) : provided
              layered.setOverride(k, newVal, { reason: body.reason || 'admin' })
              updated.push(k)
            } catch (err) {
              sendJSON(res, 500, { error: String(err) })
              return true
            }
          }
        }
      }

      try { if (typeof layered?.persistOverrides === 'function') await layered.persistOverrides() } catch (err) { deps.logger.warn('Failed to persist config overrides', { error: String(err) }); }
      try { await runtime.reloadConfig() } catch (err) { deps.logger.warn('Failed to reload daemon config', { error: String(err) }); }

      const metrics = runtime.getProviderMetrics()
      if (metrics.providers.length === 0) {
        sendJSON(res, 503, { error: 'providers not initialised' })
        return true
      }

      sendJSON(res, 200, { ok: true, updated, metrics })
      return true
    } catch (err) {
      sendJSON(res, 500, { error: String(err) })
      return true
    }
  }

  // POST /providers/reset
  if (method === 'POST' && pathname === '/providers/reset') {
    try {
      const body = await parseBody(req)
      const providerId = typeof body?.providerId === 'string' ? body.providerId : undefined
      const resetErrors = body?.resetErrors !== false
      const resetRateLimits = body?.resetRateLimits === true

      const providersMap = runtime.getProviders()
      if (!providersMap) {
        sendJSON(res, 503, { error: 'providers not initialised' })
        return true
      }

      const results: Array<{ id: string; resetErrors?: boolean; resetRateLimits?: boolean; error?: string }> = []

      for (const [id, prov] of providersMap) {
        if (providerId && id !== providerId) continue

        const result: typeof results[number] = { id }
        try {
          if (resetErrors && typeof prov.resetErrorState === 'function') {
            prov.resetErrorState()
            result.resetErrors = true
          }
          if (resetRateLimits && typeof prov.resetRateLimitHistory === 'function') {
            prov.resetRateLimitHistory()
            result.resetRateLimits = true
          }
        } catch (err) {
          result.error = String(err)
        }
        results.push(result)
      }

      sendJSON(res, 200, { ok: true, results })
      return true
    } catch (err) {
      sendJSON(res, 500, { error: String(err) })
      return true
    }
  }

  return false
}
