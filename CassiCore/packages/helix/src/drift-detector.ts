/**
 * Drift Detector — Concrete drift detection for Helix step execution.
 *
 * Hooks into tool execution, compares shell commands against goal verb whitelist,
 * and injects self-correction prompt on mismatch.
 *
 * Detects "exploration paralysis" — repeated file listing, grep searches, and
 * reading without implementation.
 */

import type { ILogger } from '../../../types/interfaces.js'

// ─── Goal Verb Whitelist ───────────────────────────────────────────────────

/**
 * Whitelist of goal-aligned verbs for shell commands.
 * Commands starting with these verbs are considered "implementation" actions.
 * All other shell commands are flagged as potential drift.
 */
export const GOAL_VERB_WHITELIST = new Set([
  // File creation/modification
  'write',
  'create',
  'edit',
  'modify',
  'update',
  'append',
  'insert',
  'replace',
  'patch',
  // Code generation
  'generate',
  'build',
  'compile',
  'transpile',
  'bundle',
  // Testing/verification
  'test',
  'run',
  'execute',
  'verify',
  'check',
  'validate',
  // Installation/setup
  'install',
  'setup',
  'init',
  'configure',
  // Git operations (implementation-related)
  'git add',
  'git commit',
  'git push',
  'git checkout -b',
  // Package management
  'npm install',
  'npm run',
  'npm test',
  'npm build',
  'npm publish',
  'pnpm',
  'yarn',
  // Build tools
  'make',
  'cmake',
  'cargo',
  'go build',
  'go test',
  'go run',
  'python',
  'python3',
  'node',
  'deno',
  'bun',
  // Deployment
  'deploy',
  'publish',
  'release',
  'docker build',
  'docker push',
  // Migration
  'migrate',
  'seed',
  'prisma migrate',
  'prisma generate',
  // Database
  'psql',
  'mysql',
  'mongo',
  'redis-cli',
])

// ─── Drift Patterns ────────────────────────────────────────────────────────

/**
 * Patterns that indicate exploration/drift behavior.
 * These are shell commands that suggest "reading without implementation".
 */
export const DRIFT_PATTERNS = [
  // File listing (exploration)
  /^\s*ls\s+/i,
  /^\s*ll\s+/i,
  /^\s*la\s+/i,
  /^\s*find\s+.*-type\s+f/i,
  /^\s*tree\s+/i,
  /^\s*dir\s+/i,
  // Searching (exploration)
  /^\s*grep\s+/i,
  /^\s*rg\s+/i,
  /^\s*ack\s+/i,
  /^\s*ag\s+/i,
  /^\s*find\s+.*-exec\s+grep/i,
  // Reading files (exploration)
  /^\s*cat\s+/i,
  /^\s*less\s+/i,
  /^\s*more\s+/i,
  /^\s*head\s+/i,
  /^\s*tail\s+/i,
  /^\s*bat\s+/i,
  // Navigation (exploration)
  /^\s*cd\s+/i,
  /^\s*pwd\s*/i,
  // Git status (exploration without commit)
  /^\s*git status\s*/i,
  /^\s*git log\s*/i,
  /^\s*git diff\s*/i,
  /^\s*git show\s*/i,
  /^\s*git branch\s*/i,
  // Package inspection (exploration)
  /^\s*npm list\s*/i,
  /^\s*npm view\s*/i,
  /^\s*npm search\s*/i,
]

// ─── Drift Detection State ─────────────────────────────────────────────────

export interface DriftDetectionState {
  /** Count of consecutive drift-detected commands */
  consecutiveDriftCount: number
  /** Total drift detections this session */
  totalDriftCount: number
  /** Last command that was flagged as drift */
  lastDriftCommand?: string
  /** Whether self-correction has been injected this step */
  selfCorrectionInjected: boolean
  /** Timestamp of first drift detection */
  firstDriftTime?: number
}

// ─── Drift Detector ────────────────────────────────────────────────────────

export interface DriftDetectorOpts {
  logger?: ILogger
  /** Max consecutive drift commands before forcing correction */
  maxConsecutiveDrift?: number
  /** Custom whitelist in addition to default */
  customWhitelist?: string[]
  /** Custom drift patterns in addition to default */
  customDriftPatterns?: RegExp[]
}

export class DriftDetector {
  private logger?: ILogger
  private maxConsecutiveDrift: number
  private whitelist: Set<string>
  private driftPatterns: RegExp[]
  private state: DriftDetectionState

  constructor(opts: DriftDetectorOpts = {}) {
    this.logger = opts.logger
    this.maxConsecutiveDrift = opts.maxConsecutiveDrift ?? 3
    this.whitelist = new Set([
      ...GOAL_VERB_WHITELIST,
      ...(opts.customWhitelist ?? []),
    ])
    this.driftPatterns = [
      ...DRIFT_PATTERNS,
      ...(opts.customDriftPatterns ?? []),
    ]
    this.state = {
      consecutiveDriftCount: 0,
      totalDriftCount: 0,
      selfCorrectionInjected: false,
    }
  }

  /**
   * Check if a shell command matches the goal verb whitelist.
   * Returns true if the command is goal-aligned (not drift).
   */
  isGoalAligned(command: string): boolean {
    const trimmed = command.trim().toLowerCase()

    // Check whitelist prefixes
    for (const verb of this.whitelist) {
      if (trimmed.startsWith(verb.toLowerCase())) {
        return true
      }
    }

    return false
  }

  /**
   * Check if a shell command matches drift patterns.
   * Returns true if the command is flagged as drift.
   */
  isDrift(command: string): boolean {
    const trimmed = command.trim()

    // Check drift patterns
    for (const pattern of this.driftPatterns) {
      if (pattern.test(trimmed)) {
        return true
      }
    }

    // If not goal-aligned and matches common shell patterns, it's drift
    if (!this.isGoalAligned(command)) {
      // Any shell command that's not explicitly whitelisted is potential drift
      const shellPattern = /^(ls|cat|grep|find|cd|pwd|echo|printf|test|\[)/i
      if (shellPattern.test(trimmed)) {
        return true
      }
    }

    return false
  }

  /**
   * Analyze a shell command and update drift state.
   * Returns detection result with self-correction trigger if needed.
   */
  analyzeCommand(command: string): DriftAnalysisResult {
    const isDrift = this.isDrift(command)
    const now = Date.now()

    if (isDrift) {
      this.state.consecutiveDriftCount++
      this.state.totalDriftCount++
      this.state.lastDriftCommand = command
      if (!this.state.firstDriftTime) {
        this.state.firstDriftTime = now
      }

      this.logger?.debug(
        `[DriftDetector] Drift detected (${this.state.consecutiveDriftCount} consecutive): ${command.slice(0, 100)}`,
      )
    } else {
      // Reset consecutive counter on goal-aligned command
      this.state.consecutiveDriftCount = 0
      this.state.selfCorrectionInjected = false
      this.state.firstDriftTime = undefined
    }

    const shouldSelfCorrect =
      isDrift &&
      this.state.consecutiveDriftCount >= this.maxConsecutiveDrift &&
      !this.state.selfCorrectionInjected

    if (shouldSelfCorrect) {
      this.state.selfCorrectionInjected = true
    }

    return {
      isDrift,
      consecutiveDriftCount: this.state.consecutiveDriftCount,
      totalDriftCount: this.state.totalDriftCount,
      shouldSelfCorrect,
      selfCorrectionPrompt: shouldSelfCorrect
        ? this.generateSelfCorrectionPrompt()
        : undefined,
    }
  }

  /**
   * Generate a self-correction prompt for the LLM.
   * Injected when drift exceeds threshold.
   */
  private generateSelfCorrectionPrompt(): string {
    return `
⚠️ DRIFT DETECTED — Self-Correction Required

You have executed ${this.state.consecutiveDriftCount} consecutive exploration commands without implementation.
Detected pattern: "read-only" behavior (listing files, searching, reading) without writing code.

STOP EXPLORING. START IMPLEMENTING.

Your next action MUST be one of:
1. Write/create a file with working code
2. Edit/modify an existing file
3. Run tests to verify implementation
4. Execute a build/compilation command

Do NOT:
- List more files or directories
- Run more searches or greps
- Read more file contents
- Analyze the codebase further

The goal requires concrete implementation, not further study.
`.trim()
  }

  /**
   * Get current drift detection state.
   */
  getState(): DriftDetectionState {
    return { ...this.state }
  }

  /**
   * Reset drift detection state.
   */
  reset(): void {
    this.state = {
      consecutiveDriftCount: 0,
      totalDriftCount: 0,
      selfCorrectionInjected: false,
    }
  }
}

// ─── Types ─────────────────────────────────────────────────────────────────

export interface DriftAnalysisResult {
  /** Whether this command was flagged as drift */
  isDrift: boolean
  /** Current consecutive drift count */
  consecutiveDriftCount: number
  /** Total drift detections this session */
  totalDriftCount: number
  /** Whether self-correction should be injected */
  shouldSelfCorrect: boolean
  /** Self-correction prompt to inject (if shouldSelfCorrect is true) */
  selfCorrectionPrompt?: string
}

// ─── Hook for Helix Posture Runner ─────────────────────────────────────────

export interface DriftDetectionHook {
  /** Analyze a shell command and return self-correction if needed */
  onShellCommand(command: string): DriftAnalysisResult
  /** Get current drift state for metrics/reporting */
  getState(): DriftDetectionState
  /** Reset drift detection */
  reset(): void
}

/**
 * Create a drift detection hook for integration into Helix step execution.
 */
export function createDriftDetector(opts?: DriftDetectorOpts): DriftDetectionHook {
  const detector = new DriftDetector(opts)

  return {
    onShellCommand: (command: string) => detector.analyzeCommand(command),
    getState: () => detector.getState(),
    reset: () => detector.reset(),
  }
}
