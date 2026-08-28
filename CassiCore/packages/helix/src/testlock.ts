/**
 * TestLock — Sealed Test Paradigm for Helix.
 *
 * Adapted from the Sealed Test Paradigm (STP). When Yin (stress-tester) identifies
 * critical behaviors that MUST be tested, it seals test expectations with a content
 * hash. Yang cannot modify sealed specs, and Unity cannot signal_done without
 * verifying that sealed tests pass.
 *
 * Three formal invariants (from STP):
 *   TEMPORAL:    Test spec sealed before code changes are considered complete
 *   STRUCTURAL:  Sealed specs are content-hashed and immutable
 *   BEHAVIORAL:  Completion gate requires sealed tests to pass
 *
 * HOW: The TestLock is stored in-memory per Helix session. It does not persist
 * across sessions — each Helix run starts with a clean slate. Sealed specs are
 * visible to all postures via the `list_test_locks` tool.
 */

import { createHash } from 'node:crypto'

/** Severity determines whether a sealed spec blocks signal_done */
export type TestLockSeverity = 'critical' | 'important' | 'advisory'

/** Verification status of a sealed test spec */
export type TestLockVerificationStatus = 'pending' | 'passed' | 'failed'

/**
 * A sealed test expectation.
 * Once sealed, the contentHash makes the spec immutable.
 */
export interface SealedTestSpec {
  /** Unique identifier (e.g., "ts-auth-token-expiry") */
  specId: string
  /** What this test verifies */
  description: string
  /** Expected test file path */
  testFile?: string
  /** Command to run the test */
  testCommand: string
  /** Expected outcome description */
  expectedOutcome?: string
  /** Severity level */
  severity: TestLockSeverity
  /** SHA-256 hash of the spec content (makes it immutable) */
  contentHash: string
  /** Who sealed it (posture name) */
  sealedBy: string
  /** When it was sealed */
  sealedAt: number
  /** Current verification status */
  verificationStatus: TestLockVerificationStatus
  /** Verification attempts */
  verificationAttempts: TestLockVerification[]
}

/** A single verification attempt */
export interface TestLockVerification {
  /** When the verification was attempted */
  attemptedAt: number
  /** Whether the test passed */
  passed: boolean
  /** Test runner output */
  output?: string
  /** Optional notes */
  notes?: string
  /** Who verified (posture name) */
  verifiedBy: string
}

/**
 * Callback interface for persisting TestLock state.
 * The TestLock class doesn't depend on the store directly — instead, it calls
 * these callbacks when state changes need to be persisted.
 *
 * WHY: This keeps TestLock testable without a database. The posture runner
 * wires these callbacks to the HelixStore.
 */
export interface TestLockPersistence {
  onSeal(spec: SealedTestSpec): void
  onVerify(specId: string, verificationStatus: TestLockVerificationStatus, verifications: TestLockVerification[]): void
}

/**
 * TestLock store — manages sealed test specs for a single Helix session.
 *
 * Thread-safe for single-session use (not shared across sessions).
 */
export class TestLock {
  private specs = new Map<string, SealedTestSpec>()
  private persistence?: TestLockPersistence

  // WHY: Prevent DoS by Yin sealing unlimited specs that block Unity
  private static readonly MAX_TOTAL_SPECS = 20
  private static readonly MAX_CRITICAL_SPECS = 5

  constructor(persistence?: TestLockPersistence) {
    this.persistence = persistence
  }

  /**
   * Restore sealed specs from persistent storage (e.g., after crash recovery).
   * Called once at construction time with specs loaded from the DB.
   */
  restore(specs: SealedTestSpec[]): void {
    for (const spec of specs) {
      this.specs.set(spec.specId, spec)
    }
  }

  /**
   * Seal a test spec. Creates a content hash to make it immutable.
   * Returns the sealed spec or an error if already sealed.
   */
  seal(opts: {
    specId: string
    description: string
    testFile?: string
    testCommand: string
    expectedOutcome?: string
    severity: TestLockSeverity
    sealedBy: string
  }): { sealed: boolean; spec?: SealedTestSpec; error?: string } {
    if (this.specs.has(opts.specId)) {
      return { sealed: false, error: `Test spec "${opts.specId}" is already sealed and cannot be modified.` }
    }

    // Enforce limits
    if (this.specs.size >= TestLock.MAX_TOTAL_SPECS) {
      return { sealed: false, error: `Maximum of ${TestLock.MAX_TOTAL_SPECS} sealed test specs reached. Remove advisory specs or consolidate.` }
    }
    if (opts.severity === 'critical') {
      const criticalCount = [...this.specs.values()].filter(s => s.severity === 'critical').length
      if (criticalCount >= TestLock.MAX_CRITICAL_SPECS) {
        return { sealed: false, error: `Maximum of ${TestLock.MAX_CRITICAL_SPECS} critical test specs reached. Use 'important' for additional specs.` }
      }
    }

    // WHY: The content hash covers all substantive fields. Once sealed,
    // any attempt to create a spec with the same ID will fail.
    const hashInput = [
      opts.specId,
      opts.description,
      opts.testFile ?? '',
      opts.testCommand,
      opts.expectedOutcome ?? '',
      opts.severity,
    ].join('|')

    const contentHash = createHash('sha256').update(hashInput).digest('hex')

    const spec: SealedTestSpec = {
      specId: opts.specId,
      description: opts.description,
      testFile: opts.testFile,
      testCommand: opts.testCommand,
      expectedOutcome: opts.expectedOutcome,
      severity: opts.severity,
      contentHash,
      sealedBy: opts.sealedBy,
      sealedAt: Date.now(),
      verificationStatus: 'pending',
      verificationAttempts: [],
    }

    this.specs.set(opts.specId, spec)

    // Persist to DB if wired
    if (this.persistence) {
      this.persistence.onSeal(spec)
    }

    return { sealed: true, spec }
  }

  /**
   * Record a verification attempt for a sealed test spec.
   */
  verify(specId: string, opts: {
    passed: boolean
    output?: string
    notes?: string
    verifiedBy: string
  }): { verified: boolean; spec?: SealedTestSpec; error?: string } {
    const spec = this.specs.get(specId)
    if (!spec) {
      return { verified: false, error: `Test spec "${specId}" not found.` }
    }

    const attempt: TestLockVerification = {
      attemptedAt: Date.now(),
      passed: opts.passed,
      output: opts.output,
      notes: opts.notes,
      verifiedBy: opts.verifiedBy,
    }

    spec.verificationAttempts.push(attempt)
    spec.verificationStatus = opts.passed ? 'passed' : 'failed'

    // Persist verification update to DB if wired
    if (this.persistence) {
      this.persistence.onVerify(specId, spec.verificationStatus, spec.verificationAttempts)
    }

    return { verified: true, spec }
  }

  /**
   * Check if all blocking test specs have been verified as passing.
   * Returns true if signal_done can proceed.
   */
  canComplete(): { allowed: boolean; blockers: SealedTestSpec[] } {
    const blockers: SealedTestSpec[] = []

    for (const spec of this.specs.values()) {
      if (spec.severity === 'advisory') continue
      if (spec.verificationStatus !== 'passed') {
        blockers.push(spec)
      }
    }

    return {
      allowed: blockers.length === 0,
      blockers,
    }
  }

  /**
   * Get all sealed test specs.
   */
  getAll(): SealedTestSpec[] {
    return [...this.specs.values()]
  }

  /**
   * Get a specific test spec.
   */
  get(specId: string): SealedTestSpec | undefined {
    return this.specs.get(specId)
  }

  /**
   * Get summary counts.
   */
  getSummary(): { total: number; pending: number; passed: number; failed: number; critical: number; blocking: number } {
    let total = 0, pending = 0, passed = 0, failed = 0, critical = 0, blocking = 0
    for (const spec of this.specs.values()) {
      total++
      if (spec.verificationStatus === 'pending') pending++
      if (spec.verificationStatus === 'passed') passed++
      if (spec.verificationStatus === 'failed') failed++
      if (spec.severity === 'critical') critical++
      if (spec.severity !== 'advisory' && spec.verificationStatus !== 'passed') blocking++
    }
    return { total, pending, passed, failed, critical, blocking }
  }

  /**
   * Format all specs as a human-readable summary.
   */
  formatSummary(): string {
    const specs = this.getAll()
    if (specs.length === 0) return 'No sealed test specs.'

    const summary = this.getSummary()
    const lines: string[] = [
      `**Sealed Test Specs** — ${summary.total} total, ${summary.passed} passed, ${summary.pending} pending, ${summary.failed} failed, ${summary.blocking} blocking`,
      '',
    ]

    for (const spec of specs) {
      const status = spec.verificationStatus === 'passed' ? '[PASS]'
        : spec.verificationStatus === 'failed' ? '[FAIL]'
        : '[PENDING]'
      const block = spec.severity !== 'advisory' ? ' (BLOCKING)' : ''
      lines.push(`${status} ${spec.specId} — ${spec.description}${block}`)
      lines.push(`  Severity: ${spec.severity} | Command: ${spec.testCommand}`)
      lines.push(`  Hash: ${spec.contentHash.slice(0, 16)}... | Sealed by: ${spec.sealedBy}`)
      if (spec.verificationAttempts.length > 0) {
        const lastAttempt = spec.verificationAttempts[spec.verificationAttempts.length - 1]
        lines.push(`  Last attempt: ${lastAttempt.passed ? 'PASSED' : 'FAILED'} by ${lastAttempt.verifiedBy}`)
      }
      lines.push('')
    }

    return lines.join('\n')
  }
}
