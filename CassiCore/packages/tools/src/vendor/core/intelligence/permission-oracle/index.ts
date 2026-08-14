/**
 * VENDOR TYPE STUB — `core/intelligence/permission-oracle/index.ts`
 * (`PermissionOracle`).
 *
 * Type-placeholder for the permission-oracle surface consumed by executor.ts
 * (tools). Tools hold `PermissionOracle` only as a type (field + setter arg);
 * never constructed or method-called by tools. Owned by
 * `@cassicore/training-trust-ledger` (P5); re-pointed there (Open-6).
 */

import type { ILogger } from '@cassicore/foundation'

/** The three possible permission outcomes. */
export type PermissionDecision = 'allow' | 'deny' | 'escalate'

/** A pending human-approval request. */
export interface PendingApproval {
  requestId: string
  toolName: string
  reason: string
  requestedAt: number
}

/** The Permission Oracle makes allow/deny/escalate decisions for gated actions. */
export class PermissionOracle {
  constructor(_logger: ILogger) {
    /* type-stub — no runtime */
  }
}
