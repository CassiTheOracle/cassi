/**
 * VENDOR TYPE STUB — `core/intelligence/permission-oracle/index.ts`
 * (`PermissionOracle`).
 *
 * Type-placeholder for the permission-oracle surface consumed by executor.ts
 * (tools): `judge` (returns a verdict with decision/reasoning/risk/trust) and
 * `requestApproval` (returns whether the human approved). Never constructed by
 * the tools (injected host-side). Owned by
 * `@cassicore/training-trust-ledger` (P5); re-pointed there (Open-6).
 */

import type { ILogger } from '@cassicore/foundation'

/** The three possible permission outcomes. */
export type PermissionDecision = 'allow' | 'deny' | 'escalate'

/** Risk assessment shape returned on a verdict. */
export interface RiskAssessment {
  riskScore: number
  level: 'low' | 'medium' | 'high' | 'critical'
  reasons?: string[]
}

/** Trust score shape returned on a verdict. */
export interface TrustScore {
  domain: string
  score: number
}

/** A permission-verdict returned by `judge`. */
export interface PermissionVerdict {
  decision: PermissionDecision
  reasoning: string
  riskAssessment: RiskAssessment
  trustScore: TrustScore
  effectiveThreshold: number
}

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

  judge(
    toolName: string,
    input: unknown,
    sessionId: string,
    opts?: { sessionType?: string },
  ): PermissionVerdict {
    void toolName; void input; void sessionId; void opts
    return {
      decision: 'allow',
      reasoning: '',
      riskAssessment: { riskScore: 0, level: 'low', reasons: [] },
      trustScore: { domain: '', score: 1 },
      effectiveThreshold: 0.7,
    }
  }

  async requestApproval(_verdict: PermissionVerdict): Promise<boolean> {
    return true
  }
}
