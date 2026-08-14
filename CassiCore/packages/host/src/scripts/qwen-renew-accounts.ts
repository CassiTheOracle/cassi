#!/usr/bin/env tsx
/**
 * scripts/qwen-renew-accounts.ts
 *
 * Bulk renew Qwen OAuth accounts stored in ~/.cassicore/qwen-accounts.json
 */

import fs from 'fs/promises'
import path from 'path'
import os from 'os'
import { QwenProvider, type QwenOAuthCredentials } from '../vendor/core/ai/src/providers/cassicore/qwen.js'

export interface AccountEntry {
  profileId: string
  apiKey?: string
  baseUrl?: string
  credentials?: QwenOAuthCredentials
  /** Temporary — set during device flow, cleared on completion */
  _device?: { deviceCode: { user_code: string; device_code: string }; verifier: string }
}

export interface RenewResult {
  renewed: number
  reauthenticated: number
  failed: number
  details: Array<{ profileId: string; status: string; error?: string }>
}

/**
 * Read accounts file from canonical location
 * @dep callers: handleProvidersRoutes (core/admin-api/providers.ts), renewAccountsFile (scripts/qwen-renew-accounts.ts)
 * @dep flows: HandleProvidersRoutes → DefaultAccountsPath (3/3)
 * @dep module: Providers
 * @dep risk: LOW | 2 callers, 1 flow, 1 module
 */
export function defaultAccountsPath(): string {
  return path.join(os.homedir(), '.cassicore', 'qwen-accounts.json')
}

/**
 * Renew all accounts in the provided file. Returns summary and writes updated file.
 * @dep callers: qwen-account-renewal.test.ts (tests/qwen-account-renewal.test.ts), handleProvidersRoutes (core/admin-api/providers.ts)
 * @dep calls: pollForToken, refreshToken, startDeviceFlow, now, defaultAccountsPath
 * @dep flows: HandleProvidersRoutes → DefaultAccountsPath (2/3), HandleProvidersRoutes → Now (2/3)
 * @dep module: Providers
 * @dep risk: LOW | 2 callers, 2 flows, 1 module
 */
export async function renewAccountsFile(accountsFile?: string): Promise<RenewResult> {
  const file = accountsFile || defaultAccountsPath()
  let raw: string
  try {
    raw = await fs.readFile(file, 'utf-8')
  } catch (err) {
    throw new Error(`Failed to read accounts file: ${String(err)}`)
  }

  let accounts: AccountEntry[]
  try {
    accounts = JSON.parse(raw) as AccountEntry[]
  } catch (err) {
    throw new Error(`Invalid accounts JSON: ${String(err)}`)
  }

  const details: RenewResult['details'] = []
  let renewed = 0
  let reauthenticated = 0
  let failed = 0

  // For accounts that need device flow, collect polling promises
  const polls: Array<Promise<void>> = []

  for (const acc of accounts) {
    const pid = acc.profileId || '<unknown>'

    // Try token refresh first if credentials have a refresh token
    if (acc.credentials?.refresh) {
      try {
        const newCreds = await QwenProvider.refreshToken(acc.credentials)
        acc.credentials = newCreds
        renewed++
        details.push({ profileId: pid, status: 'renewed' })
        continue
      } catch {
        // Refresh failed — fall through to device flow
      }
    }

    // Start device flow for accounts without refresh tokens or where refresh failed
    try {
      const { deviceCode, verifier } = await QwenProvider.startDeviceFlow()
      acc._device = { deviceCode, verifier }

      // Track the pending_device detail index so we can update it on completion
      const detailIdx = details.length
      details.push({ profileId: pid, status: 'pending_device', error: deviceCode.user_code })

      // Poll in background
      const p = (async () => {
        try {
          const creds = await QwenProvider.pollForToken(deviceCode.device_code, verifier, deviceCode.interval, deviceCode.expires_in)
          acc.credentials = creds
          reauthenticated++
          delete acc._device
          // Update the existing detail entry rather than pushing a duplicate
          details[detailIdx] = { profileId: pid, status: 'reauthenticated' }
        } catch (err) {
          failed++
          details[detailIdx] = { profileId: pid, status: 'failed', error: String(err) }
        }
      })()

      polls.push(p)
    } catch (err) {
      failed++
      details.push({ profileId: pid, status: 'failed_start', error: String(err) })
    }
  }

  // Wait for all device flow polls to finish
  if (polls.length > 0) {
    await Promise.allSettled(polls)
  }

  // Persist updated accounts atomically (write to tmp, then rename)
  try {
    const dir = path.dirname(file)
    await fs.mkdir(dir, { recursive: true })
    // Strip transient _device fields before persisting
    const cleaned = accounts.map(({ _device, ...rest }) => rest)
    const tmp = `${file}.${Date.now()}.tmp`
    await fs.writeFile(tmp, JSON.stringify(cleaned, null, 2), 'utf-8')
    await fs.rename(tmp, file)
  } catch (err) {
    throw new Error(`Failed to write accounts file: ${String(err)}`)
  }

  return { renewed, reauthenticated, failed, details }
}
