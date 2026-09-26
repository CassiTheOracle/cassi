/**
 * P8-DEFERRED type stub — ai/src/providers/cassicore/qwen.js (QwenProvider).
 *
 * Vendored for @cassicore/host/src/scripts/qwen-renew-accounts.ts, which uses
 * the QwenProvider OAuth statics + credentials type. The whole `ai/` tree stays
 * in `D:` until P8 `@cassicore/ai`; this faithful consumer-facing surface throws
 * at runtime ("not migrated"). Re-point to `@cassicore/ai` and delete at P8
 * (§3.b of the P7 table).
 */
export interface QwenOAuthCredentials {
  refresh: string
  access: string
  expires: number
  enterpriseUrl?: string
  profileId?: string
}

function notMigrated(name: string): never {
  throw new Error(
    `${name}: @cassicore/ai (ai/) is not migrated — P8-deferred. Re-point packages/host/src/vendor/... to @cassicore/ai and delete this stub at P8.`
  )
}

export interface DeviceCodeResponse {
  device_code: string
  user_code: string
  verification_uri: string
  verification_uri_complete?: string
  expires_in: number
  interval?: number
}

export const QwenProvider = {
  async refreshToken(credentials: QwenOAuthCredentials): Promise<QwenOAuthCredentials> {
    notMigrated('QwenProvider.refreshToken')
  },
  async startDeviceFlow(): Promise<{ deviceCode: DeviceCodeResponse; verifier: string }> {
    notMigrated('QwenProvider.startDeviceFlow')
  },
  async pollForToken(
    _deviceCode: string,
    _verifier: string,
    interval: number,
    expiresIn: number,
  ): Promise<QwenOAuthCredentials> {
    notMigrated('QwenProvider.pollForToken')
  },
} as {
  refreshToken(credentials: QwenOAuthCredentials): Promise<QwenOAuthCredentials>
  startDeviceFlow(): Promise<{ deviceCode: DeviceCodeResponse; verifier: string }>
  pollForToken(
    deviceCode: string,
    verifier: string,
    interval: number | undefined,
    expiresIn: number,
  ): Promise<QwenOAuthCredentials>
}
