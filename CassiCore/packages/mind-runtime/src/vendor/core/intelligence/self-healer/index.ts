/**
 * SelfHealingAgent — Autonomous code repair for CassiCore.
 *
 * Closes the loop the Subconscious and Thinker could not:
 *
 *   Detect  →  intelligence:processor-error / WARN events
 *   Analyze →  parse error, locate call site, read actual module API
 *   Patch   →  LLM-assisted edit validated by tsc --noEmit
 *   Rebuild →  npm run build, then signal daemon for graceful restart
 *
 * Error classes handled automatically (high-confidence):
 *   - TypeError: X is not a function  (stale method name on renamed API)
 *   - TypeError: Cannot read properties of undefined (missing optional chain)
 *
 * All repairs are journalled to memory and surfaced via self-healer:* events
 * so the Observatory, Thinker, and admin API can observe what changed.
 */

import { spawn } from 'child_process'
import fs from 'fs'
import path from 'path'

import { BaseCognitiveModule } from '../base/cognitive-module.js'

import type { IMemory } from '@cassicore/foundation'
import type { ILogger , IEventBus } from '@cassicore/foundation'


// process.cwd() is always the workspace root regardless of whether we're running
// from compiled dist/ or source — the daemon always starts from the project root.
// (The ../../.. relative approach is fragile: source depth ≠ compiled depth)
const ROOT = process.cwd()
const COOLDOWN_MS  = 5 * 60 * 1000   // wait 5 min before re-attempting same error
const MAX_ATTEMPTS = 3                // give up after 3 failed repair attempts
const DEBOUNCE_MS  = 10_000          // group identical errors within 10s window
// After this many gave-up / failed records for one processor, suppress that processor
// entirely to prevent a broken module from burning through repair budget indefinitely.
const MAX_PROCESSOR_FAILURES = 5


export interface SelfHealerConfig {
  enabled: boolean
  /** How long (ms) to wait before retrying a failed repair. Default 5 min. */
  cooldownMs?: number
  /** Max repair attempts per unique error before giving up. Default 3. */
  maxAttempts?: number
  /** Whether to apply repairs autonomously or only propose them. Default true. */
  autoApply?: boolean
  /** Whether to trigger a daemon restart after a successful rebuild. Default true. */
  autoRestart?: boolean
}

export interface RepairRecord {
  id: string
  errorSignature: string     // stable key for dedup
  processorName: string
  rawError: string
  filePath?: string          // source file where the call site lives
  proposedPatch?: string     // unified diff or targeted replacement
  /**
   * Status progression:
   *   pending → analyzing → proposed → applied → validated   (success path)
   *   pending → analyzing → not-applicable                    (error type not handled; no attempt consumed)
   *   pending → analyzing → failed                            (repair attempted but failed)
   *   pending → gave-up                                       (maxAttempts exhausted; permanently suppressed)
   */
  status: 'pending' | 'analyzing' | 'proposed' | 'applied' | 'validated' | 'failed' | 'skipped' | 'gave-up' | 'not-applicable'
  attempts: number
  firstSeenAt: number
  lastAttemptAt?: number
  resolvedAt?: number
  failureReason?: string
}

export interface SelfHealerStats {
  totalDetected: number
  totalResolved: number
  totalFailed: number
  totalGaveUp: number
  pending: number
  autoApply: boolean
  autoRestart: boolean
  suppressedProcessors: string[]
  records: RepairRecord[]
}


let counter = 0
/**
 * @dep callers: requestRepair (core/intelligence/self-healer/index.ts), onProcessorError (core/intelligence/self-healer/index.ts)
 * @dep calls: now
 * @dep module: Self-healer
 * @dep risk: LOW | 2 callers, 0 flows, 1 module
 */

function nextId(): string {
  return `repair:${Date.now().toString(36)}:${(++counter).toString(36)}`
}

/** Extract a stable signature from an error string for deduplication. */
/**
 * @dep callers: triggerRepair (core/intelligence/self-healer/index.ts), onProcessorError (core/intelligence/self-healer/index.ts)
 * @dep module: Self-healer
 * @dep risk: LOW | 2 callers, 0 flows, 1 module
 */

function errorSignature(processorName: string, error: string): string {
  // Normalize: strip memory addresses and line numbers so same logical error
  // maps to the same key even across restarts or minor code drift.
  const normalized = error
    .replace(/0x[0-9a-f]+/gi, '<addr>')
    .replace(/:\d+:\d+\)/g, ':<line>)')
    .slice(0, 200)
  return `${processorName}::${normalized}`
}

/** Run a shell command and return { ok, stdout, stderr }. */
/**
 * @dep callers: rebuild (core/intelligence/self-healer/index.ts), validateBuildWithDiagnostics (core/intelligence/self-healer/index.ts), locateCallSite (core/intelligence/self-healer/index.ts)
 * @dep calls: on
 * @dep module: Self-healer
 * @dep risk: LOW | 3 callers, 0 flows, 1 module
 */

function runCmd(cmd: string, args: string[], cwd: string): Promise<{ ok: boolean; stdout: string; stderr: string }> {
  return new Promise((resolve) => {
    const proc = spawn(cmd, args, { cwd, stdio: ['ignore', 'pipe', 'pipe'] })
    let stdout = ''
    let stderr = ''
    proc.stdout.on('data', (d: Buffer) => { stdout += d.toString() })
    proc.stderr.on('data', (d: Buffer) => { stderr += d.toString() })
    proc.on('close', (code) => resolve({ ok: code === 0, stdout, stderr }))
    proc.on('error', (err) => resolve({ ok: false, stdout, stderr: String(err) }))
  })
}


export class SelfHealingAgent extends BaseCognitiveModule {
  readonly name = 'self-healer' as const
  readonly priority = 10   // lowest priority — runs after everything else

  private cfg: Required<SelfHealerConfig>
  private records = new Map<string, RepairRecord>()
  private debounceTimers = new Map<string, ReturnType<typeof setTimeout>>()
  private _healerMemory?: IMemory  // separate from base class's protected memory
  /** Injected by daemon: calls the provider with a repair prompt. */
  private repairProvider?: (prompt: string) => Promise<string>
  /** Per-processor failure counters — tracks gave-up + failed records. */
  private processorFailureCounts = new Map<string, number>()
  /** Processors that have exceeded MAX_PROCESSOR_FAILURES — permanently suppressed. */
  private suppressedProcessors = new Set<string>()

  constructor(logger: ILogger, config?: SelfHealerConfig) {
    super(logger)
    this.cfg = {
      enabled:      config?.enabled      ?? true,
      cooldownMs:   config?.cooldownMs   ?? COOLDOWN_MS,
      maxAttempts:  config?.maxAttempts  ?? MAX_ATTEMPTS,
      autoApply:    config?.autoApply    ?? true,
      autoRestart:  config?.autoRestart  ?? true,
    }
  }


  setEventBus(bus: IEventBus): void {
    this.eventBus = bus
  }

  setMemory(memory: IMemory): void {
    this._healerMemory = memory
  }

  /**
   * Wire the repair provider.  The daemon passes a thin wrapper around the
   * thinker:repair-request/response event pair so the SelfHealingAgent does
   * not need a direct provider reference.
   */
  setRepairProvider(fn: (prompt: string) => Promise<string>): void {
    this.repairProvider = fn
  }

  /** Runtime toggle: set autoApply on/off without restarting the daemon. */
  setAutoApply(value: boolean): void {
    this.cfg.autoApply = value
    this.logger.info('SelfHealingAgent: autoApply changed', { autoApply: value })
  }

  /** Runtime toggle: set autoRestart on/off without restarting the daemon. */
  setAutoRestart(value: boolean): void {
    this.cfg.autoRestart = value
    this.logger.info('SelfHealingAgent: autoRestart changed', { autoRestart: value })
  }


  override async start(): Promise<void> {
    await super.start()
    if (!this.cfg.enabled) {
      this.logger.info('SelfHealingAgent: disabled')
      return
    }

    // Subscribe to processor errors emitted by IntelligenceLayer
    this.subscribe('intelligence:processor-error', (e) => {
      const ev = e as any
      this.onProcessorError(ev.processorName ?? 'unknown', ev.error ?? '')
    })

    // Also catch raw WARN-level plugin/worker errors that carry TypeError patterns
    this.subscribe('worker:message', (e: any) => {
      const payload = e?.payload
      if (payload?.type === 'error' || payload?.error) {
        const err = String(payload.error ?? payload.message ?? '')
        if (err.includes('is not a function') || err.includes('Cannot read properties')) {
          this.onProcessorError(`worker:${e.pluginId ?? 'unknown'}`, err)
        }
      }
    })

    this.logger.info('SelfHealingAgent: started', {
      autoApply: this.cfg.autoApply,
      autoRestart: this.cfg.autoRestart,
    })
  }


  private onProcessorError(processorName: string, rawError: string): void {
    // Suppress: processor has exceeded per-processor failure budget
    if (this.suppressedProcessors.has(processorName)) return

    const sig = errorSignature(processorName, rawError)

    // Debounce — ignore duplicate errors within the window
    if (this.debounceTimers.has(sig)) return
    this.debounceTimers.set(sig, setTimeout(() => {
      this.debounceTimers.delete(sig)
    }, DEBOUNCE_MS))

    // Check existing record
    const existing = this.records.get(sig)
    if (existing) {
      // Permanently terminal states — never retry
      if (existing.status === 'applied' || existing.status === 'validated') return
      if (existing.status === 'gave-up' || existing.status === 'not-applicable') return

      // Exhausted attempts — transition to gave-up, emit explicit event
      if (existing.attempts >= this.cfg.maxAttempts) {
        existing.status = 'gave-up'
        this.emitSelfHealerEvent('self-healer:gave-up', {
          id: existing.id,
          processorName,
          error: rawError.slice(0, 120),
          attempts: existing.attempts,
        })
        this.logger.warn('SelfHealingAgent: max attempts reached, giving up', {
          id: existing.id, processorName, attempts: existing.attempts,
        })
        this.trackProcessorFailure(processorName)
        return
      }

      const elapsed = Date.now() - (existing.lastAttemptAt ?? existing.firstSeenAt)
      if (elapsed < this.cfg.cooldownMs) return // in cooldown
    }

    const record: RepairRecord = existing ?? {
      id: nextId(),
      errorSignature: sig,
      processorName,
      rawError,
      status: 'pending',
      attempts: 0,
      firstSeenAt: Date.now(),
    }

    record.status = 'pending'
    this.records.set(sig, record)

    this.emitSelfHealerEvent('self-healer:error-detected', {
      id: record.id,
      processorName,
      error: rawError,
      attempt: record.attempts + 1,
    })

    this.logger.warn('SelfHealingAgent: error detected, scheduling repair', {
      id: record.id,
      processorName,
      error: rawError.slice(0, 120),
    })

    void this.runRepairCycle(record)
  }

  /**
   * Track a terminal failure (gave-up or failed) for a processor.
   * After MAX_PROCESSOR_FAILURES, the processor is suppressed permanently.
   */
  private trackProcessorFailure(processorName: string): void {
    const count = (this.processorFailureCounts.get(processorName) ?? 0) + 1
    this.processorFailureCounts.set(processorName, count)
    if (count >= MAX_PROCESSOR_FAILURES) {
      this.suppressedProcessors.add(processorName)
      this.logger.warn('SelfHealingAgent: suppressing processor — too many failures', {
        processorName, failureCount: count,
      })
      this.emitSelfHealerEvent('self-healer:processor-suppressed', {
        processorName, failureCount: count,
      })
    }
  }


  private async runRepairCycle(record: RepairRecord): Promise<void> {
    record.attempts++
    record.lastAttemptAt = Date.now()
    record.status = 'analyzing'

    try {
      // 1. Locate the call site
      const callSite = await this.locateCallSite(record)
      if (!callSite) {
        // The error type is not one the self-healer can handle (e.g. not a TypeError
        // about renamed methods). This is not a failed attempt — mark as not-applicable
        // and undo the attempt increment so it doesn't count against maxAttempts.
        record.attempts--
        record.status = 'not-applicable'
        record.failureReason = 'error type not handled by self-healer'
        this.logger.info('SelfHealingAgent: error type not applicable, skipping permanently', { id: record.id })
        this.emitSelfHealerEvent('self-healer:not-applicable', { id: record.id, reason: record.failureReason })
        return
      }

      record.filePath = callSite.filePath

      // 2. Build repair prompt
      let prompt = this.buildRepairPrompt(record, callSite)

      // 3. Repair loop — try up to 3 times, feeding tsc errors back on retry
      const MAX_REPAIR_ATTEMPTS = 3
      let patchText: string | null = null
      let valid = false

      for (let attempt = 1; attempt <= MAX_REPAIR_ATTEMPTS; attempt++) {
        // 3a. Ask the Thinker (or fallback provider) for a patch
        record.status = 'analyzing'
        patchText = await this.requestRepair(prompt)
        if (!patchText) {
          record.status = 'failed'
          record.failureReason = 'repair provider returned empty response'
          this.logger.warn('SelfHealingAgent: empty repair response', { id: record.id, attempt })
          return
        }

        record.proposedPatch = patchText
        record.status = 'proposed'
        this.emitSelfHealerEvent('self-healer:repair-proposed', { id: record.id, filePath: record.filePath, patch: patchText, attempt })

        if (!this.cfg.autoApply) {
          this.logger.info('SelfHealingAgent: patch proposed (autoApply=false)', { id: record.id })
          return
        }

        // 3b. Apply the patch
        const applied = await this.applyPatch(record, callSite, patchText)
        if (!applied) return

        record.status = 'applied'
        this.emitSelfHealerEvent('self-healer:repair-applied', { id: record.id, filePath: record.filePath! })

        // 3c. Validate: tsc --noEmit
        const result = await this.validateBuildWithDiagnostics(record)
        if (result.valid) {
          valid = true
          break
        }

        // tsc failed — if we have more attempts, feed the error back into the prompt
        if (attempt < MAX_REPAIR_ATTEMPTS) {
          this.logger.info('SelfHealingAgent: tsc failed, retrying with error context', {
            id: record.id, attempt, diagnostics: result.diagnostics.slice(0, 200),
          })
          prompt = this.buildRepairRetryPrompt(record, callSite, patchText, result.diagnostics)
        }
      }

      if (!valid) return

      record.status = 'validated'
      record.resolvedAt = Date.now()
      this.emitSelfHealerEvent('self-healer:repair-validated', { id: record.id, filePath: record.filePath })

      // 6. Full rebuild
      this.logger.info('SelfHealingAgent: repair validated — triggering rebuild', { id: record.id })
      const built = await this.rebuild(record)
      if (!built) return

      // 7. Persist to memory
      await this.persistRepair(record)

      // 8. Signal for restart if enabled
      if (this.cfg.autoRestart) {
        this.logger.info('SelfHealingAgent: rebuild succeeded — requesting daemon restart', { id: record.id })
        this.emitSelfHealerEvent('self-healer:restart-requested', {
          id: record.id,
          reason: `Self-healed: ${record.rawError.slice(0, 100)}`,
        })
        // Give the event a tick to propagate, then request graceful shutdown
        // so the daemon can clean up resources (close DBs, flush buffers).
        // The process manager (systemd / start-daemon.sh) will handle restart.
        setTimeout(() => {
          this.emitSelfHealerEvent('self-healer:shutdown-requested', {
            id: record.id,
            reason: `Self-healed: ${record.rawError.slice(0, 100)}`,
          })
          // Fallback hard exit if daemon doesn't shut down within 5s
          setTimeout(() => process.exit(0), 5000)
        }, 500)
      }
    } catch (err) {
      record.status = 'failed'
      record.failureReason = String(err)
      this.logger.error('SelfHealingAgent: repair cycle threw', {
        id: record.id,
        error: String(err),
      })
      this.emitSelfHealerEvent('self-healer:repair-failed', { id: record.id, error: String(err) })
      this.trackProcessorFailure(record.processorName)
    }
  }


  private async locateCallSite(record: RepairRecord): Promise<CallSiteInfo | null> {
    // Extract method name from TypeError patterns:
    //   "this.X.Y is not a function"
    //   "module.method is not a function"
    //   "someMethod is not a function"
    const match = record.rawError.match(/TypeError:\s+(?:[\w.]+\.)?(\w+)\s+is not a function/)
    if (!match) return null
    const methodName = match[1]

    // Strategy 1: parse the stack trace directly for an explicit file:line reference
    // Matches:  at ClassName.methodName (relative/path/file.ts:84:22)
    //        or at ClassName.methodName (relative/path/file.ts:84:22)
    const stackLineMatch = record.rawError.match(
      /at [\w.<>]+\s+\(([^)]*\.ts):(\d+):\d+\)/
    )
    if (stackLineMatch) {
      const relPath = stackLineMatch[1].trim()
      const lineNum = parseInt(stackLineMatch[2], 10)
      // Try relative to ROOT first, then as-is
      const candidates = [
        path.resolve(ROOT, relPath),
        path.isAbsolute(relPath) ? relPath : null,
      ].filter(Boolean) as string[]

      for (const absPath of candidates) {
        if (fs.existsSync(absPath)) {
          const source = fs.readFileSync(absPath, 'utf-8')
          return { filePath: absPath, lineNum, methodName, source }
        }
      }
    }

    // Strategy 2: grep the source tree for the call site
    const result = await runCmd('grep', [
      '-rn', '--include=*.ts',
      `\\.${methodName}(`,
      'core/', 'workers/', 'types/',
    ], ROOT)

    if (!result.ok && !result.stdout) return null

    const lines = result.stdout.split('\n').filter(Boolean)
    // Prefer lines that match the processor name (e.g. "ThinkerProcessor" file)
    const processorHint = record.processorName.toLowerCase().replace(/processor$/i, '')
    const best = lines.find(l => l.toLowerCase().includes(processorHint)) ?? lines[0]
    if (!best) return null

    const [filePart, linePart] = best.split(':')
    const absPath = path.resolve(ROOT, filePart.trim())
    const lineNum = parseInt(linePart, 10)

    if (!fs.existsSync(absPath)) return null

    const source = fs.readFileSync(absPath, 'utf-8')

    return { filePath: absPath, lineNum, methodName, source }
  }


  private buildRepairPrompt(record: RepairRecord, callSite: CallSiteInfo): string {
    // Read a window around the broken call site for context
    const lines = callSite.source.split('\n')
    const start = Math.max(0, callSite.lineNum - 10)
    const end   = Math.min(lines.length, callSite.lineNum + 10)
    const window = lines.slice(start, end).map((l, i) => `${start + i + 1}: ${l}`).join('\n')

    // Try to read the module's actual public API from the types directory
    const moduleHint = record.processorName.toLowerCase().replace(/processor$/i, '')
    let apiContext = ''
    try {
      const typeFiles = [
        path.join(ROOT, 'types', 'intelligence.ts'),
        path.join(ROOT, `core/intelligence/${moduleHint}/index.ts`),
      ]
      for (const f of typeFiles) {
        if (fs.existsSync(f)) {
          const src = fs.readFileSync(f, 'utf-8').slice(0, 3000)
          apiContext += `\n\n// ${path.relative(ROOT, f)}\n${src}`
        }
      }
    } catch { /* best-effort */ }

    return `You are a TypeScript expert. A CassiCore intelligence processor is failing with:

ERROR: ${record.rawError}

The call site is in ${path.relative(ROOT, callSite.filePath)} around line ${callSite.lineNum}:

\`\`\`typescript
${window}
\`\`\`

Here is the actual API of the module being called:
${apiContext || '(not found — infer from the error and context above)'}

Task: Produce a minimal, correct TypeScript replacement for ONLY the failing line(s).
- Do not rewrite the whole file.
- Output ONLY a JSON object in this exact format:
  {"oldCode": "<exact text to replace>", "newCode": "<replacement text>"}
- The replacement must compile without errors.
- If the method does not exist, use the correct alternative from the actual API.
- If no safe fix is possible, output: {"oldCode": "", "newCode": ""}
`
  }


  private async requestRepair(prompt: string): Promise<string | null> {
    if (this.repairProvider) {
      try {
        return await this.repairProvider(prompt)
      } catch (err) {
        this.logger.warn('SelfHealingAgent: repairProvider failed', { error: String(err) })
      }
    }

    // Fallback: emit thinker:repair-request and wait for response
    if (!this.eventBus) return null

    return new Promise((resolve) => {
      const id = nextId()
      const timeout = setTimeout(() => {
        (this.eventBus as any)?.off?.('thinker:repair-response', handler)
        resolve(null)
      }, 30_000)

      const handler = (e: any) => {
        if (e?.id !== id) return
        clearTimeout(timeout)
        ;(this.eventBus as any)?.off?.('thinker:repair-response', handler)
        resolve(e?.text ?? null)
      }

      ;(this.eventBus as any)?.on?.('thinker:repair-response', handler)
      ;(this.eventBus as any)?.emit?.({ type: 'thinker:repair-request', id, prompt })
    })
  }


  private async applyPatch(record: RepairRecord, callSite: CallSiteInfo, patchText: string): Promise<boolean> {
    let parsed: { oldCode: string; newCode: string }
    try {
      // Extract JSON from the response (LLM may wrap it in markdown)
      const jsonMatch = patchText.match(/\{[\s\S]*"oldCode"[\s\S]*"newCode"[\s\S]*\}/)
      if (!jsonMatch) throw new Error('no JSON found in repair response')
      parsed = JSON.parse(jsonMatch[0])
    } catch (err) {
      record.status = 'failed'
      record.failureReason = `patch parse failed: ${String(err)}`
      this.logger.warn('SelfHealingAgent: patch parse failed', { id: record.id, error: String(err) })
      this.emitSelfHealerEvent('self-healer:repair-failed', { id: record.id, error: record.failureReason })
      return false
    }

    if (!parsed.oldCode || !parsed.newCode) {
      record.status = 'skipped'
      record.failureReason = 'LLM indicated no safe fix available'
      this.logger.warn('SelfHealingAgent: LLM returned no-op patch, skipping', { id: record.id })
      return false
    }

    const source = fs.readFileSync(callSite.filePath, 'utf-8')
    if (!source.includes(parsed.oldCode)) {
      record.status = 'failed'
      record.failureReason = 'oldCode not found in source file — patch is stale'
      this.logger.warn('SelfHealingAgent: oldCode not found in source', { id: record.id })
      this.emitSelfHealerEvent('self-healer:repair-failed', { id: record.id, error: record.failureReason })
      return false
    }

    // Write backup
    fs.writeFileSync(`${callSite.filePath}.selfhealer.bak`, source, 'utf-8')

    // Apply
    const patched = source.replace(parsed.oldCode, parsed.newCode)
    fs.writeFileSync(callSite.filePath, patched, 'utf-8')

    this.logger.info('SelfHealingAgent: patch applied', {
      id: record.id,
      file: path.relative(ROOT, callSite.filePath),
      oldCode: parsed.oldCode.slice(0, 80),
      newCode: parsed.newCode.slice(0, 80),
    })
    return true
  }


  private async validateBuildWithDiagnostics(record: RepairRecord): Promise<{ valid: boolean; diagnostics: string }> {
    this.logger.info('SelfHealingAgent: running tsc --noEmit', { id: record.id })
    const result = await runCmd('npx', ['tsc', '--noEmit', '--project', 'tsconfig.json'], ROOT)

    // tsc writes diagnostics to stdout; stderr may also contain process errors
    const diagnostics = (result.stdout + result.stderr).slice(0, 500)

    if (result.ok) {
      this.logger.info('SelfHealingAgent: tsc passed', { id: record.id })
      return { valid: true, diagnostics: '' }
    }

    // TypeScript validation failed — roll back the patch
    this.logger.warn('SelfHealingAgent: tsc failed, rolling back', {
      id: record.id,
      diagnostics: diagnostics.slice(0, 300),
    })
    const bak = `${record.filePath!}.selfhealer.bak`
    if (fs.existsSync(bak)) {
      fs.copyFileSync(bak, record.filePath!)
      fs.unlinkSync(bak)
    }
    record.status = 'failed'
    record.failureReason = `tsc --noEmit failed: ${diagnostics.slice(0, 200)}`
    this.emitSelfHealerEvent('self-healer:repair-failed', { id: record.id, error: record.failureReason })
    return { valid: false, diagnostics }
  }

  /** Build a follow-up prompt that feeds tsc error context back to the LLM for self-correction. */
  private buildRepairRetryPrompt(
    record: RepairRecord,
    callSite: CallSiteInfo,
    previousPatch: string,
    tscDiagnostics: string,
  ): string {
    const src = fs.readFileSync(callSite.filePath, 'utf-8')
    const lines = src.split('\n')
    const start = Math.max(0, callSite.lineNum - 5)
    const end   = Math.min(lines.length, callSite.lineNum + 10)
    const excerpt = lines.slice(start, end).join('\n')

    return [
      `Your previous patch for ${path.relative(ROOT, callSite.filePath)} failed TypeScript compilation.`,
      '',
      'TypeScript errors:',
      '```',
      tscDiagnostics.trim(),
      '```',
      '',
      'Your previous patch:',
      '```json',
      previousPatch.trim(),
      '```',
      '',
      'Current file content around the error site:',
      '```typescript',
      excerpt,
      '```',
      '',
      'Original runtime error:',
      record.rawError.split('\n')[0],
      '',
      'Please provide a corrected patch that fixes both the original runtime error AND the TypeScript compilation errors.',
      '- Output ONLY a JSON object in this exact format:',
      '  {"oldCode": "<exact text to replace>", "newCode": "<replacement text>"}',
      '- The newCode must compile without errors under strict TypeScript.',
      '- Do not include any explanation or wrapping.',
    ].join('\n')
  }


  private async rebuild(record: RepairRecord): Promise<boolean> {
    this.logger.info('SelfHealingAgent: running npm run build', { id: record.id })
    this.emitSelfHealerEvent('self-healer:rebuild-started', { id: record.id })

    const result = await runCmd('npm', ['run', 'build'], ROOT)

    if (result.ok) {
      this.logger.info('SelfHealingAgent: build succeeded', { id: record.id })
      this.emitSelfHealerEvent('self-healer:rebuild-succeeded', { id: record.id })
      // Clean up backup
      const bak = `${record.filePath!}.selfhealer.bak`
      if (fs.existsSync(bak)) fs.unlinkSync(bak)
      return true
    }

    this.logger.error('SelfHealingAgent: build failed, rolling back', {
      id: record.id,
      stderr: result.stderr.slice(0, 400),
    })
    const bak = `${record.filePath!}.selfhealer.bak`
    if (fs.existsSync(bak)) {
      fs.copyFileSync(bak, record.filePath!)
      fs.unlinkSync(bak)
    }
    record.status = 'failed'
    record.failureReason = `npm run build failed: ${result.stderr.slice(0, 200)}`
    this.emitSelfHealerEvent('self-healer:rebuild-failed', { id: record.id, error: record.failureReason })
    return false
  }


  private async persistRepair(record: RepairRecord): Promise<void> {
    if (!this._healerMemory) return
    try {
      await (this._healerMemory as any).add?.({
        type: 'insight',
        content: `[SelfHealingAgent] Automatically repaired: ${record.rawError.slice(0, 120)}\nFile: ${record.filePath ?? 'unknown'}\nPatch: ${record.proposedPatch?.slice(0, 200) ?? 'n/a'}`,
        metadata: {
          source: 'self-healer',
          trigger: 'anomaly',
          repairId: record.id,
          processorName: record.processorName,
          resolvedAt: record.resolvedAt,
        },
        importance: 0.9,
      })
    } catch (err) {
      this.logger.warn('SelfHealingAgent: failed to persist repair to memory', { error: String(err) })
    }
  }


  /**
   * Stop the self-healer and clean up all pending timers.
   */
  override async stop(): Promise<void> {
    // Clear all debounce timers
    for (const timer of this.debounceTimers.values()) {
      clearTimeout(timer)
    }
    this.debounceTimers.clear()
    await super.stop()
  }


  getStats(): SelfHealerStats {
    const records = Array.from(this.records.values())
    return {
      totalDetected:       records.length,
      totalResolved:       records.filter(r => r.status === 'validated').length,
      totalFailed:         records.filter(r => r.status === 'failed').length,
      totalGaveUp:         records.filter(r => r.status === 'gave-up').length,
      pending:             records.filter(r => ['pending', 'analyzing', 'proposed'].includes(r.status)).length,
      autoApply:           this.cfg.autoApply,
      autoRestart:         this.cfg.autoRestart,
      suppressedProcessors: Array.from(this.suppressedProcessors),
      records,
    }
  }

  /** Manually trigger a repair for a given error string (e.g. from admin API). */
  async triggerRepair(processorName: string, rawError: string): Promise<string> {
    const sig = errorSignature(processorName, rawError)
    const existing = this.records.get(sig)
    if (existing) {
      existing.attempts = 0   // reset so it can retry
      existing.status = 'pending'
    }
    this.onProcessorError(processorName, rawError)
    return existing?.id ?? sig
  }


  private emitSelfHealerEvent(type: string, payload: Record<string, unknown>): void {
    try {
      this.emit({ type, ...payload } as any)
    } catch { /* best-effort */ }
  }
}


interface CallSiteInfo {
  filePath: string
  lineNum: number
  methodName: string
  source: string
}


export function createSelfHealingAgent(
  logger: ILogger,
  config?: SelfHealerConfig,
): SelfHealingAgent {
  return new SelfHealingAgent(logger, config)
}
