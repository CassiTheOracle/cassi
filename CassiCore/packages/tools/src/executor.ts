import { resolveToolDomain } from '../intelligence/permission-oracle/types.js'
import { TTLCache } from '../utils/ttl-cache.js'
import { presentForLLM } from './presentation.js'

import { validateToolInput, validateToolOutput, executeToolSafe } from './safety.js'

import type { ToolRegistry } from './registry.js'
import type { ToolCall, ToolResult, ToolExecutionContext } from './types.js'
import type { IEventBus, ILogger } from '../../types/interfaces.js'
import type { PermissionOracle } from '../intelligence/permission-oracle/index.js'
import type { TrustLedger } from '../intelligence/trust-ledger/index.js'
import { ToolReliabilityTracker } from './reliability.js'
import type { ToolCallOrchestrator } from '../intelligence/triad-team/tool-orchestrator.js'


const MAX_CONCURRENT = 20
const ENABLE_SAFETY_GUARDS = true  // Can be disabled for debugging

/** Short-lived cache key for permission decisions: "toolName:sha(input)" */
function permissionCacheKey(toolName: string, input: Record<string, unknown>): string {
  // Deterministic but fast — stable JSON stringification is overkill here;
  // collisions just cause an extra judge() call, which is the status quo.
  let hash = 0
  const str = JSON.stringify(input)
  for (let i = 0; i < str.length; i++) {
    hash = ((hash << 5) - hash + str.charCodeAt(i)) | 0
  }
  return `${toolName}:${hash}`
}

export class ToolExecutor {
  private permissionOracle?: PermissionOracle
  private trustLedger?: TrustLedger
  private reliabilityTracker?: ToolReliabilityTracker
  private orchestrator?: ToolCallOrchestrator
  private logger: ILogger

  /**
   * Short-term permission decision cache.
   * Identical (tool, input) pairs within 5 seconds reuse the prior verdict,
   * avoiding redundant risk assessment and event emission for repetitive
   * tool calls (e.g. reading 10 files in a loop).
   */
  private permissionCache = new TTLCache<string, { decision: string; reasoning: string }>({
    maxSize: 200,
    ttlMs: 5_000,
  })

  /**
   * Per-session context overrides. Orchestrators register session-specific
   * context (e.g. artifactNamespace, sessionType) before running agent sessions.
   * These are merged into the ToolExecutionContext on every execute() call.
   */
  private sessionContextOverrides = new Map<string, Partial<ToolExecutionContext>>()

  constructor(
    private registry: ToolRegistry,
    private defaultContext: Omit<ToolExecutionContext, 'sessionId'>,
    private eventBus?: IEventBus,
  ) {
    this.logger = defaultContext.logger.child('tool-executor')
  }

  /**
   * Wire the Permission Oracle for graduated autonomy gating.
   * When set, every tool call is assessed for risk before execution.
   * If the oracle returns 'deny', the tool call is blocked.
   * If the oracle returns 'escalate', the tool call is paused pending human approval.
   * If the oracle returns 'allow', the tool call proceeds normally.
   */
  setPermissionOracle(oracle: PermissionOracle): void {
    this.permissionOracle = oracle
  }

  /**
   * Wire the Trust Ledger for outcome feedback.
   * After every tool execution, the outcome (success/failure) is fed back
   * into the Trust Ledger to update domain trust scores.
   */
  setTrustLedger(ledger: TrustLedger): void {
    this.trustLedger = ledger
  }

  /**
   * Check if a tool is registered and available for execution.
   */
  isAvailable(name: string): boolean {
    return this.registry.get(name) !== undefined
  }

  /**
   * Wire the Tool Reliability Tracker for circuit breaker pattern.
   * When set, tool executions are monitored for failures and circuits open
   * after repeated failures. Failed tools can route to fallback tools.
   */
  setReliabilityTracker(tracker: ToolReliabilityTracker): void {
    this.reliabilityTracker = tracker
  }

  /**
   * Register session-specific context overrides for a session.
   * Merged into ToolExecutionContext for every tool call in that session.
   * Used by Dyad/Lumen/Flux orchestrators to inject artifact namespace, session type, etc.
   */
  setSessionContext(sessionId: string, overrides: Partial<ToolExecutionContext>): void {
    this.sessionContextOverrides.set(sessionId, overrides)
  }

  /**
   * Remove session-specific context overrides (call on session teardown).
   */
  clearSessionContext(sessionId: string): void {
    this.sessionContextOverrides.delete(sessionId)
  }

  /**
   * Check if session-specific context overrides are already registered.
   */
  hasSessionContext(sessionId: string): boolean {
    return this.sessionContextOverrides.has(sessionId)
  }

  /**
   * Wire a Tool Call Orchestrator for cross-cell batching and caching.
   * When set, tool executions route through the orchestrator for
   * result caching, deduplication, and parallelism optimization.
   */
  setOrchestrator(orchestrator: ToolCallOrchestrator): void {
    this.orchestrator = orchestrator
  }

  /** Get the active orchestrator (if any) for direct batch calls */
  getOrchestrator(): ToolCallOrchestrator | undefined {
    return this.orchestrator
  }

  /**
   * Execute a single tool call.
   *
   * @param call - The tool call to execute
   * @param sessionId - Session context for permission/trust tracking
   * @param opts - Optional overrides for this invocation
   * @param opts.workingDir - Override the default working directory (used for worktree isolation)
   */
  async execute(
    call: ToolCall,
    sessionId: string,
    opts?: { workingDir?: string },
  ): Promise<ToolResult> {
    // If an orchestrator is wired, route through it for caching, dedup,
    // and parallel execution. The orchestrator calls back to this.execute()
    // via the delegate, but with the orchestrator temporarily disabled
    // to avoid infinite recursion.
    if (this.orchestrator && call.name !== 'batch_tools') {
      const orch = this.orchestrator
      this.orchestrator = undefined // Prevent recursion
      try {
        return await orch.execute(call, sessionId, this.execute.bind(this), opts)
      } finally {
        this.orchestrator = orch
      }
    }

    const executeStartMs = Date.now()
    // Prefer serena (MCP) implementations for core file operations when available.
    // Strategy:
    // 1. Try exact tool name (as registered)
    // 2. Try preferred MCP servers (env PREFERRED_MCP_SERVERS, default 'serena') using serverId__toolName
    // 3. For common file ops, look for any registered serena__* tool that looks like a match

    let entry = this.registry.get(call.name)

    const preferredServers = (process.env.PREFERRED_MCP_SERVERS || 'serena').split(',').map(s => s.trim()).filter(Boolean)

    if (!entry) {
      for (const serverId of preferredServers) {
        const alt = `${serverId}__${call.name}`
        const e = this.registry.get(alt)
        if (e) { entry = e; break }
      }
    }

    // Heuristic fallback for common file operations
    if (!entry) {
      const fileOps = new Set(['read_file','write_file','read','write','exists','mkdir','delete','bash'])
      if (fileOps.has(call.name)) {
        const list = this.registry.list()

        // Try serena-prefixed tools first
        const serenaMatch = list.find(d => d.name.startsWith('serena__') && (
          (call.name.includes('read') && d.name.includes('read')) ||
          ((call.name.includes('write') || call.name.includes('create')) && (d.name.includes('write') || d.name.includes('create') || d.name.includes('replace') || d.name.includes('insert'))) ||
          (call.name.includes('exists') && d.name.includes('exists')) ||
          (call.name.includes('mkdir') && d.name.includes('mkdir')) ||
          (call.name === 'bash' && d.name.includes('shell'))
        ))
        if (serenaMatch) entry = this.registry.get(serenaMatch.name)

        // Otherwise, pick any tool with suffix __<toolName>
        if (!entry) {
          const suffixMatch = list.find(d => d.name.endsWith(`__${call.name}`))
          if (suffixMatch) entry = this.registry.get(suffixMatch.name)
        }
      }
    }

    if (!entry) {
      this.emitToolExecuted(sessionId, call.name, Date.now() - executeStartMs, true)
      return { toolCallId: call.id, content: `Unknown tool: ${call.name}`, isError: true }
    }

    // If a Reliability Tracker is wired, check if the tool's circuit is open.
    // If open, attempt fallback routing or return an error.
    let actualToolName = call.name
    let actualEntry = entry
    if (this.reliabilityTracker) {
      if (!this.reliabilityTracker.canExecute(call.name)) {
        // Circuit is open — check for fallback
        const fallbackTool = entry.definition.fallbackTool
        if (fallbackTool) {
          const fallbackEntry = this.registry.get(fallbackTool)
          if (fallbackEntry) {
            this.logger.info(`Circuit OPEN for tool '${call.name}' — routing to fallback '${fallbackTool}'`, {
              originalTool: call.name,
              fallbackTool,
            })
            actualToolName = fallbackTool
            actualEntry = fallbackEntry
          } else {
            this.logger.warn(`Circuit OPEN for tool '${call.name}' — fallback '${fallbackTool}' not found`, {
              originalTool: call.name,
              fallbackTool,
            })
          }
        }
        if (actualToolName === call.name) {
          // No fallback available or fallback not found
          this.emitToolExecuted(sessionId, call.name, Date.now() - executeStartMs, true)
          return {
            toolCallId: call.id,
            content: `[circuit-open] Tool '${call.name}' is temporarily unavailable due to repeated failures. Try again later.`,
            isError: true,
          }
        }
      }
    }

    const timeout = actualEntry.definition.timeoutMs ?? 30_000
    const ctx: ToolExecutionContext = {
      ...this.defaultContext,
      sessionId,
      ...(this.sessionContextOverrides.get(sessionId) ?? {}),
      ...(opts?.workingDir ? { workingDir: opts.workingDir } : {}),
    }

    // SAFETY: Pre-call input validation
    if (ENABLE_SAFETY_GUARDS) {
      const inputValidation = validateToolInput(actualToolName, call.input)
      if (!inputValidation.valid) {
        this.emitSafetyEvent(sessionId, actualToolName, 'input_validation_failed', inputValidation.errors)
        this.emitToolExecuted(sessionId, actualToolName, Date.now() - executeStartMs, true)
        return {
          toolCallId: call.id,
          content: `Safety check failed: ${inputValidation.errors.join(', ')}`,
          isError: true
        }
      }
    }

    // Track skill invocations when reading SKILL.md files
    this.trackSkillInvocation({ ...call, name: actualToolName }, sessionId)

    // If a Permission Oracle is wired, assess risk before execution.
    // This is the core of graduated autonomy: low-risk actions auto-proceed,
    // high-risk actions require human approval.
    //
    // A short-lived TTL cache deduplicates identical (tool, input) pairs
    // within a 5-second window to avoid redundant risk assessment, event
    // emission, and trust pipeline processing for repetitive tool calls.
    if (this.permissionOracle) {
      const cacheKey = permissionCacheKey(call.name, call.input)
      const cached = this.permissionCache.get(cacheKey)

      if (cached?.decision === 'deny') {
        // Replay cached denial without re-running the full pipeline
        this.emitToolExecuted(sessionId, call.name, Date.now() - executeStartMs, true)
        return {
          toolCallId: call.id,
          content: `Permission denied (cached): ${cached.reasoning}`,
          isError: true,
        }
      }

      // Only run full judge() if no cached 'allow' exists
      if (!cached || cached.decision !== 'allow') {
        const verdict = this.permissionOracle.judge(call.name, call.input, sessionId)

        // Cache the decision for subsequent identical calls
        this.permissionCache.set(cacheKey, {
          decision: verdict.decision,
          reasoning: verdict.reasoning,
        })

        if (verdict.decision === 'deny') {
          this.emitToolExecuted(sessionId, call.name, Date.now() - executeStartMs, true)
          return {
            toolCallId: call.id,
            content: `Permission denied: ${verdict.reasoning}` +
              ` (risk=${verdict.riskAssessment.riskScore.toFixed(2)}, trust=${verdict.trustScore.score.toFixed(2)})`,
            isError: true,
          }
        }

        if (verdict.decision === 'escalate') {
          // Escalate decisions are never cached — human must decide each time
          this.permissionCache.delete(cacheKey)

          // Block execution until human approves or timeout fires.
          // The Permission Oracle's requestApproval() returns a Promise that
          // resolves when the admin API receives an approve/reject, or when
          // the configured timeout expires (fallback to escalation default).
          this.emitSafetyEvent(sessionId, call.name, 'permission_escalated', [
            verdict.reasoning,
            `risk=${verdict.riskAssessment.riskScore.toFixed(2)}`,
            `trust=${verdict.trustScore.score.toFixed(2)}`,
            `threshold=${verdict.effectiveThreshold.toFixed(2)}`,
          ])

          const approved = await this.permissionOracle.requestApproval(verdict)

          if (!approved) {
            this.emitToolExecuted(sessionId, call.name, Date.now() - executeStartMs, true)
            return {
              toolCallId: call.id,
              content: `Permission denied (human rejected or timed out): ${verdict.reasoning}` +
                ` (risk=${verdict.riskAssessment.riskScore.toFixed(2)}, trust=${verdict.trustScore.score.toFixed(2)})`,
              isError: true,
            }
          }
          // Human approved — proceed with execution
        }
      }
    }

    try {
      // SAFETY: Execute with timeout and error containment
      if (ENABLE_SAFETY_GUARDS) {
        const safeResult = await executeToolSafe(
          actualToolName,
          () => actualEntry!.handler(call.input, ctx),
          call.input,
          timeout
        )

        const durationMs = Date.now() - executeStartMs

        if (!safeResult.success) {
          this.emitSafetyEvent(sessionId, actualToolName, safeResult.errorType || 'execution', [safeResult.error || 'Unknown error'])
          this.recordToolOutcome(actualToolName, false, sessionId, `Tool failed: ${safeResult.errorType || 'execution'}`)
          this.recordReliabilityOutcome(actualToolName, durationMs, false)
          this.emitToolExecuted(sessionId, actualToolName, durationMs, true)
          return {
            toolCallId: call.id,
            content: `Tool failed: ${safeResult.error || 'Unknown error'} (${safeResult.errorType || 'execution'})`,
            isError: true
          }
        }

        // SAFETY: Post-call output validation
        const outputValidation = validateToolOutput(actualToolName, safeResult.data)
        if (!outputValidation.valid) {
          this.emitSafetyEvent(sessionId, actualToolName, 'output_validation_failed', outputValidation.errors)
          this.recordToolOutcome(actualToolName, false, sessionId, `Output validation failed`)
          this.recordReliabilityOutcome(actualToolName, durationMs, false)
          this.emitToolExecuted(sessionId, actualToolName, durationMs, true)
          return {
            toolCallId: call.id,
            content: `Output validation failed: ${outputValidation.errors.join(', ')}`,
            isError: true
          }
        }

        this.recordToolOutcome(actualToolName, true, sessionId, `Executed successfully`)
        this.recordReliabilityOutcome(actualToolName, durationMs, true)
        this.emitToolExecuted(sessionId, actualToolName, durationMs, false)
        
        // Apply presentation formatting
        const presented = this.applyPresentation(String(safeResult.data), actualToolName, durationMs)
        return {
          toolCallId: call.id,
          content: presented.content,
          isError: false,
          rawContent: presented.rawContent,
          exitCode: presented.exitCode,
          durationMs,
        }
      } else {
        // Legacy execution (safety disabled)
        const result = await Promise.race([
          actualEntry.handler(call.input, ctx),
          new Promise<never>((_, reject) =>
            setTimeout(
              () => reject(new Error(`Tool '${actualToolName}' timed out after ${timeout}ms`)),
              timeout,
            )
          ),
        ])
        const durationMs = Date.now() - executeStartMs
        this.recordToolOutcome(actualToolName, true, sessionId, `Executed successfully (legacy)`)
        this.recordReliabilityOutcome(actualToolName, durationMs, true)
        this.emitToolExecuted(sessionId, actualToolName, durationMs, false)
        
        // Apply presentation formatting
        const presented = this.applyPresentation(result, actualToolName, durationMs)
        return {
          toolCallId: call.id,
          content: presented.content,
          isError: false,
          rawContent: presented.rawContent,
          exitCode: presented.exitCode,
          durationMs,
        }
      }
    } catch (err) {
      const durationMs = Date.now() - executeStartMs
      this.emitSafetyEvent(sessionId, actualToolName, 'execution', [String(err)])
      this.recordToolOutcome(actualToolName, false, sessionId, `Exception: ${String(err).slice(0, 200)}`)
      this.recordReliabilityOutcome(actualToolName, durationMs, false)
      this.emitToolExecuted(sessionId, actualToolName, durationMs, true)
      return { toolCallId: call.id, content: String(err), isError: true }
    }
  }

  /**
   * Record a tool execution outcome in the Trust Ledger.
   *
   * This is the learning feedback loop: every tool call's success/failure
   * is recorded as evidence in the relevant trust domain. Over time, this
   * causes trust scores to converge toward the agent's true success rate
   * for each category of action.
   *
   * @param toolName - The tool that was executed
   * @param success - Whether execution succeeded
   * @param sessionId - Session context
   * @param description - Brief description of the outcome
   */
  private recordToolOutcome(
    toolName: string,
    success: boolean,
    sessionId: string,
    description: string,
  ): void {
    if (!this.trustLedger) return

    try {
      const domain = resolveToolDomain(toolName)
      this.trustLedger.recordEvidence({
        domain,
        success,
        weight: 1.0,
        source: 'tool-executor',
        description: `${toolName}: ${description}`,
        sessionId,
        timestamp: Date.now(),
      })
    } catch {
      // Non-fatal: don't let trust recording break tool execution
    }
  }

  /**
   * Record a tool execution outcome in the Reliability Tracker.
   *
   * This feeds the circuit breaker pattern: consecutive failures open the circuit,
   * while successes close it. Duration metrics are tracked for performance monitoring.
   *
   * @param toolName - The tool that was executed
   * @param durationMs - Execution duration in milliseconds
   * @param success - Whether execution succeeded
   */
  private recordReliabilityOutcome(
    toolName: string,
    durationMs: number,
    success: boolean,
  ): void {
    if (!this.reliabilityTracker) return

    try {
      if (success) {
        this.reliabilityTracker.recordSuccess(toolName, durationMs)
      } else {
        this.reliabilityTracker.recordFailure(toolName, durationMs)
      }
    } catch {
      // Non-fatal: don't let reliability tracking break tool execution
    }
  }

  /**
   * Emit safety event for monitoring
   */
  private emitSafetyEvent(
    sessionId: string,
    toolName: string,
    eventType: string,
    details: string[]
  ): void {
    if (!this.eventBus) return

    this.eventBus.emit({
      type: 'tool:safety' as any,
      sessionId,
      toolName,
      eventType,
      details,
      timestamp: new Date(),
    })
  }

  /**
   * Emit tool:executed event for observability.
   * Consumed by the Thinker module to trigger insight cycles based on tool activity.
   */
  private emitToolExecuted(
    sessionId: string,
    toolName: string,
    durationMs: number,
    isError: boolean,
  ): void {
    if (!this.eventBus) return

    this.eventBus.emit({
      type: 'tool:executed',
      sessionId,
      toolName,
      durationMs,
      isError,
      timestamp: new Date(),
    })
  }

  /**
   * Track skill invocations when read tool is called on SKILL.md files
   */
  private trackSkillInvocation(call: ToolCall, sessionId: string): void {
    if (!this.eventBus) return

    // Check if this is a read operation
    const isReadTool = call.name === 'read' || call.name === 'read_file' ||
                       call.name.endsWith('__read') || call.name.endsWith('__read_file')

    if (!isReadTool) return

    // Get the file path from the input
    const filePath = (call.input.path as string) || (call.input.file_path as string)
    if (!filePath) return

    // Check if this is a SKILL.md file
    if (!filePath.includes('SKILL.md')) return

    // Extract skill name from path
    // Path format: .../skills/{skill-name}/SKILL.md or .../{skill-name}/SKILL.md
    const pathParts = filePath.split(/[/\\]/)
    const skillFileIndex = pathParts.indexOf('SKILL.md')
    if (skillFileIndex === -1) return

    // Get the directory name containing the skill
    const skillName = skillFileIndex > 0 ? pathParts[skillFileIndex - 1] : 'unknown'

    // Determine source from path
    let source = 'unknown'
    if (filePath.includes('.cassi/skills')) {
      source = 'cassi'
    } else if (filePath.includes('openclaw/skills')) {
      source = 'openclaw'
    } else if (filePath.includes('.claude/skills')) {
      source = 'claude'
    } else if (filePath.includes('.pi/skills')) {
      source = 'pi'
    }

    // Emit the skill:invoked event
    this.eventBus.emit({
      type: 'skill:invoked',
      skillName,
      skillPath: filePath,
      sessionId,
      timestamp: new Date(),
      source,
    })
  }

  /**
   * Apply presentation formatting to tool output.
   * For shell_exec, parses structured JSON result to extract metadata.
   */
  private applyPresentation(
    rawOutput: string,
    toolName: string,
    durationMs: number,
  ): { content: string; rawContent: string; exitCode?: number; stderr?: string } {
    let exitCode: number | undefined
    let stderr: string | undefined
    let contentToPresent = rawOutput

    // Parse structured shell_exec result
    if (toolName === 'shell_exec' || toolName === 'shell-exec') {
      try {
        const parsed = JSON.parse(rawOutput) as {
          stdout: string
          stderr: string
          exitCode: number
          durationMs: number
        }
        
        if (parsed.stdout !== undefined && parsed.exitCode !== undefined) {
          exitCode = parsed.exitCode
          stderr = parsed.stderr
          contentToPresent = parsed.stdout
        }
      } catch {
        // Not structured JSON, use raw output as-is
        this.defaultContext.logger.debug('Shell output not structured, using raw', { toolName })
      }
    }

    const presented = presentForLLM(contentToPresent, {
      toolName,
      exitCode,
      durationMs,
      stderr,
    })

    return {
      content: presented,
      rawContent: rawOutput,
      exitCode,
      stderr,
    }
  }

  /** Execute up to MAX_CONCURRENT tool calls concurrently with error isolation */
  async executeAll(calls: ToolCall[], sessionId: string): Promise<ToolResult[]> {
    const results: ToolResult[] = []
    for (let i = 0; i < calls.length; i += MAX_CONCURRENT) {
      const batch = calls.slice(i, i + MAX_CONCURRENT)
      const settled = await Promise.allSettled(batch.map(c => this.execute(c, sessionId)))
      for (let j = 0; j < settled.length; j++) {
        const outcome = settled[j]
        if (outcome.status === 'fulfilled') {
          results.push(outcome.value)
        } else {
          // Convert unexpected rejection to error ToolResult so other calls aren't lost
          const call = batch[j]
          this.logger.error('Tool execute() rejected unexpectedly', {
            toolName: call.name,
            error: String(outcome.reason),
            sessionId,
          })
          results.push({
            toolCallId: call.id,
            content: `Tool execution failed: ${String(outcome.reason)}`,
            isError: true,
          })
        }
      }
    }
    return results
  }
}
