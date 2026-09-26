/**
 * Permission Oracle — Type Definitions
 *
 * The Permission Oracle makes the actual allow/deny/escalate decision
 * for every gated action. It combines the Consequence Estimator's risk
 * assessment with the Trust Ledger's domain trust score to determine
 * whether the agent should proceed autonomously, ask for permission,
 * or be blocked entirely.
 *
 * The core formula:
 *   effectiveThreshold = baseThreshold × (1 + trustBonus × domainTrust)
 *
 * Where:
 *   - baseThreshold is the minimum risk score that requires escalation
 *   - trustBonus is how much trust can raise that threshold (default 0.5)
 *   - domainTrust is the Trust Ledger's score for the relevant domain
 *
 * This means:
 *   - At trust 0.0: threshold = baseThreshold (strictest)
 *   - At trust 1.0: threshold = baseThreshold × 1.5 (most lenient)
 *   - Critical risk (>0.7) ALWAYS escalates regardless of trust
 *   - Irreversible actions ALWAYS escalate regardless of trust
 */

import type { RiskAssessment, RiskLevel } from '../consequence-estimator/types.js'
import type { TrustScore, AutonomyLevel } from '@cassicore/training-trust-ledger'


/**
 * The three possible permission outcomes.
 *
 * allow:    Proceed without human involvement
 * deny:     Block the action entirely (hard safety constraint violated)
 * escalate: Ask a human for approval before proceeding
 */
export type PermissionDecision = 'allow' | 'deny' | 'escalate'

/**
 * Complete permission decision with full reasoning trail.
 * This is the output of the Permission Oracle for every gated action.
 */
export interface PermissionVerdict {
  /** The tool or action being judged */
  toolName: string
  /** The final decision */
  decision: PermissionDecision
  /** Risk assessment from the Consequence Estimator */
  riskAssessment: RiskAssessment
  /** Trust score for the relevant domain */
  trustScore: TrustScore
  /** The effective threshold used for this decision */
  effectiveThreshold: number
  /** Current autonomy level */
  autonomyLevel: AutonomyLevel
  /** Human-readable explanation of why this decision was made */
  reasoning: string
  /** Which hard gate triggered (if any) */
  hardGate?: string
  /** Session context */
  sessionId: string
  /** Unix timestamp */
  decidedAt: number
}


/**
 * Hard gates are non-negotiable safety constraints that cannot be
 * overridden by trust scores. They exist because some actions are
 * simply too dangerous to ever auto-approve.
 *
 * The Permission Oracle checks hard gates BEFORE the trust-adjusted
 * threshold calculation. If a hard gate fires, the action is always
 * escalated (or denied), regardless of trust level.
 */
export interface HardGate {
  /** Unique identifier for this gate */
  id: string
  /** Human-readable description */
  description: string
  /** What risk level triggers this gate */
  triggerLevel: RiskLevel
  /** Whether to deny outright or escalate to human */
  action: 'deny' | 'escalate'
  /** Which risk dimensions trigger this gate (if specific) */
  dimensions?: Array<keyof import('../consequence-estimator/types.js').RiskDimensions>
  /** Tool name patterns that this gate applies to (glob-like) */
  toolPatterns?: string[]
}

/**
 * Default hard gates — non-negotiable safety constraints.
 */
export const DEFAULT_HARD_GATES: HardGate[] = [
  {
    id: 'critical-risk-always-escalate',
    description: 'Critical risk actions always require human approval',
    triggerLevel: 'critical',
    action: 'escalate',
  },
  {
    id: 'irreversible-always-escalate',
    description: 'Irreversible actions always require human approval',
    triggerLevel: 'moderate', // even moderate risk + irreversible = escalate
    action: 'escalate',
  },
  {
    id: 'high-data-loss-escalate',
    description: 'High data loss risk requires human approval',
    triggerLevel: 'high',
    action: 'escalate',
    dimensions: ['dataLoss'],
  },
  {
    id: 'production-deploy-deny',
    description: 'Production deployment is never auto-approved',
    triggerLevel: 'moderate',
    action: 'deny',
    dimensions: ['externalImpact'],
    toolPatterns: ['deploy*', '*push*'],
  },
]


/**
 * Configuration for the Permission Oracle.
 */
export interface PermissionOracleConfig {
  /** Whether the permission oracle is enabled */
  enabled: boolean
  /** Base risk threshold for escalation (before trust adjustment) */
  baseThreshold: number
  /** How much trust can raise the threshold (0.0–1.0) */
  trustBonusFactor: number
  /** Hard gates that cannot be overridden */
  hardGates: HardGate[]
  /** Whether to log all decisions (useful for auditing) */
  auditLog: boolean
  /** Default decision when estimation fails */
  fallbackDecision: PermissionDecision
  /** Timeout for human escalation response (ms). After timeout, apply fallback. */
  escalationTimeoutMs: number
}

export const DEFAULT_PERMISSION_ORACLE_CONFIG: PermissionOracleConfig = {
  enabled: false,              // Disabled — trust scoring blocks autonomous agents with no safety benefit
  baseThreshold: 0.3,        // Escalate anything above 0.3 risk by default
  trustBonusFactor: 0.5,     // At max trust, threshold rises to 0.45
  hardGates: DEFAULT_HARD_GATES,
  auditLog: true,
  fallbackDecision: 'escalate', // When in doubt, ask the human
  escalationTimeoutMs: 300_000, // 5 minutes
}


/**
 * Maps tool names to trust domains.
 * This determines which domain's trust score is consulted
 * when making permission decisions for a given tool.
 */
export const TOOL_DOMAIN_MAP: Record<string, string> = {
  // File operations
  'read': 'file-read',
  'read_file': 'file-read',
  'cassi_read': 'file-read',
  'serena__read_file': 'file-read',
  'grep': 'file-read',
  'glob': 'file-read',
  'write': 'file-write',
  'write_file': 'file-write',
  'cassi_write': 'file-write',
  'edit': 'file-write',
  'cassi_edit': 'file-write',
  'serena__replace_content': 'file-write',
  'serena__replace_symbol_body': 'file-write',
  'serena__insert_after_symbol': 'file-write',
  'serena__insert_before_symbol': 'file-write',
  'delete': 'file-delete',
  'cassi_delete': 'file-delete',
  // Shell
  'bash': 'shell-execution',
  'cassi_bash': 'shell-execution',
  'shell_exec': 'shell-execution',
  // Network
  'web_fetch': 'network-fetch',
  'cassi_web_fetch': 'network-fetch',
  'cassi_web_search': 'network-fetch',
  // Memory
  'memory_store': 'memory-operations',
  'memory_delete': 'memory-operations',
}

/**
 * Resolve a tool name to its trust domain.
 * Falls back to 'shell-execution' (highest risk) for unknown tools.
 * @dep callers: permission-oracle.test.ts (tests/permission-oracle.test.ts), recordToolOutcome (core/tools/executor.ts), judge (core/intelligence/permission-oracle/index.ts)
 * @dep module: Permission-oracle
 * @dep risk: LOW | 3 callers, 0 flows, 1 module
 */
export function resolveToolDomain(toolName: string): string {
  if (typeof toolName !== 'string' || toolName.length === 0) {
    return 'shell-execution'
  }

  // Direct match
  if (TOOL_DOMAIN_MAP[toolName]) return TOOL_DOMAIN_MAP[toolName]

  // Strip MCP server prefix (e.g., 'serena__find_file' → 'find_file')
  if (toolName.includes('__')) {
    const baseName = toolName.split('__').pop()!
    if (TOOL_DOMAIN_MAP[baseName]) return TOOL_DOMAIN_MAP[baseName]
  }

  // Heuristic: classify by name patterns
  if (toolName.includes('read') || toolName.includes('search') || toolName.includes('find') || toolName.includes('list') || toolName.includes('get')) {
    return 'file-read'
  }
  if (toolName.includes('write') || toolName.includes('edit') || toolName.includes('replace') || toolName.includes('insert') || toolName.includes('create')) {
    return 'file-write'
  }
  if (toolName.includes('delete') || toolName.includes('remove')) {
    return 'file-delete'
  }
  if (toolName.includes('fetch') || toolName.includes('web') || toolName.includes('http') || toolName.includes('url')) {
    return 'network-fetch'
  }
  if (toolName.includes('git') || toolName.includes('commit') || toolName.includes('push') || toolName.includes('branch')) {
    return 'git-operations'
  }
  if (toolName.includes('bash') || toolName.includes('shell') || toolName.includes('exec')) {
    return 'shell-execution'
  }

  // Unknown tool → treat as shell execution (high baseline risk)
  return 'shell-execution'
}
