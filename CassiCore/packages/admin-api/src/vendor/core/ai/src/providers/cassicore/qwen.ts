/**
 * P8-DEFERRED type stub — ai/src/providers/cassicore/qwen.js (QwenProvider).
 *
 * Vendored for @cassicore/admin-api/src/vendor/core/scripts/qwen-renew-
 * accounts.ts, which uses only the QwenProvider OAuth statics + credentials
 * type. The whole `ai/` tree stays in `D:` until P8 `@cassicore/ai`; this
 * faithful consumer-facing surface throws at runtime ("not connected").
 * Re-point to `@cassicore/ai` and delete at P8 (§3.b of the P7 table).
 */
export interface QwenOAuthCredentials {
  refresh: string
  access: string
  expires: number
  enterpriseUrl?: string
}

function notMigrated(name: string): never {
  throw new Error(
    `${name}: @cassicore/ai (ai/) is not migrated — P8-deferred. Re-point packages/admin-api/src/vendor/core/ai/... to @cassicore/ai and delete this stub at P8.`
  )
}

interface DeviceCodeResponse {
  device_code: string
  user_code: string
  verification_uri: string
  verification_uri_complete?: string
  expires_in: number
  interval?: number
}

/** OAuth-enabled Qwen provider — static device-flow surface used by qwen-renew. */
export class QwenProvider {
  readonly id = 'qwen'
  readonly models: string[] = []
  constructor(apiKey?: string, baseUrl?: string, credentials?: QwenOAuthCredentials) {
    notMigrated('QwenProvider')
  }
  static startDeviceFlow(): Promise<{ deviceCode: DeviceCodeResponse; verifier: string }> {
    return notMigrated('QwenProvider.startDeviceFlow')
  }
  static pollForToken(
    _deviceCode: string,
    _verifier: string,
    _intervalSeconds: number | undefined,
    _expiresIn: number,
    _signal?: AbortSignal
  ): Promise<QwenOAuthCredentials> {
    return notMigrated('QwenProvider.pollForToken')
  }
  static refreshToken(credentials: QwenOAuthCredentials): Promise<QwenOAuthCredentials> {
    return notMigrated('QwenProvider.refreshToken')
  }
}
