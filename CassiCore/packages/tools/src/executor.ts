import { resolveToolDomain } from '../intelligence/permission-oracle/types.js'
import { TTLCache } from '../utils/ttl-cache.js'
import { presentForLLM } from './presentation.js'
import { commitSessionChanges } from './git-session-tracker.js'
import type { SessionCommitOpts, SessionCommitResult } from './git-session-tracker.js'

import { validateToolInput, validateToolOutput, executeToolSafe } from './safety.js'
import { ExternalHookRunner, mergeHookFeedback, EMPTY_HOOK_CONFIG } from './hooks/external-hook-runner.js'
import type { ExternalHookConfig } from './hooks/external-hook-runner.js'

import type { CorticalField } from '../intelligence/cortex/index.js'
import type { SignalType } from '../intelligence/cortex/types.js'

import type { ToolRegistry } from './registry.js'
import type { ToolCall, ToolResult, ToolExecutionContext } from './types.js'

type RegistryEntry = ReturnType<ToolRegistry['get']>
import type { IEventBus, ILogger } from '../../types/interfaces.js'
import type { PermissionOracle } from '../intelligence/permission-oracle/index.js'
import type { TrustLedger } from '../intelligence/trust-ledger/index.js'
import { ToolReliabilityTracker } from './reliability.js'
// REMOVED: ToolCallOrchestrator import — deprecated TriadTeam deleted


const MAX_CONCURRENT = 20
const ENABLE_SAFETY_GUARDS = true  // Can be disabled for debugging

/**
 * @dep callers: execute (core/tools/executor.ts), enrichToolResult (core/tools/executor.ts)
 * @dep module: Tools
 * @dep risk: LOW | 2 callers, 0 flows, 1 module
 */

function permissionCacheKey(toolName: string, input: Record<string, unknown>): string {
  // HOW: Bit-shift hash instead of crypto — collisions just cause an extra judge() call
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
  // REMOVED: orchestrator — deprecated TriadTeam deleted
  private hookRunner?: ExternalHookRunner
  private logger: ILogger

  private permissionCache = new TTLCache<string, { decision: string; reasoning: string }>({
    maxSize: 200,
    ttlMs: 5_000,
  })

  private resolvedToolCache = new TTLCache<string, RegistryEntry>({
    maxSize: 500,
    ttlMs: 30_000,
  })

  private static readonly TOOL_CACHE_TTL_MS = 30_000

  private sessionContextOverrides = new Map<string, Partial<ToolExecutionContext>>()

  constructor(
    private registry: ToolRegistry,
    private defaultContext: Omit<ToolExecutionContext, 'sessionId'>,
    private eventBus?: IEventBus,
  ) {
    this.logger = defaultContext.logger.child('tool-executor')

    this.eventBus?.on('tool:registered' as any, () => {
      this.clearToolCache()
    })
  }

  private resolveToolCached(toolName: string): RegistryEntry | undefined {
    const cached = this.resolvedToolCache.get(toolName)
    if (cached) {
      return cached
    }

    const entry = this.resolveToolFull(toolName)

    if (entry) {
      this.resolvedToolCache.set(toolName, entry)
    }

    return entry
  }

  private resolveToolFull(toolName: string): RegistryEntry | undefined {
    let entry = this.registry.get(toolName)
    if (entry) return entry

    const toolAliases: Record<string, string> = {
      read: 'read_file',
      write: 'write_file',
    }
    if (toolAliases[toolName]) {
      entry = this.registry.get(toolAliases[toolName])
      if (entry) return entry
    }

    const preferredServers = (process.env.PREFERRED_MCP_SERVERS || 'serena,gitnexus').split(',').map(s => s.trim()).filter(Boolean)
    for (const serverId of preferredServers) {
      const alt = `${serverId}__${toolName}`
      const e = this.registry.get(alt)
      if (e) return e
    }

    // WHY: Models sometimes call MCP tools with single-underscore prefix (serena_list_dir)
    // instead of the registered double-underscore form (serena__list_dir). Detect the
    // MCP server prefix pattern and convert to the registered name.
    for (const serverId of preferredServers) {
      const prefix = `${serverId}_`
      if (toolName.startsWith(prefix) && !toolName.startsWith(`${serverId}__`)) {
        const bareName = toolName.slice(prefix.length)
        const mcpName = `${serverId}__${bareName}`
        const e = this.registry.get(mcpName)
        if (e) return e
      }
    }

    const fileOps = new Set(['read_file', 'write_file', 'read', 'write', 'exists', 'mkdir', 'delete', 'bash'])
    if (fileOps.has(toolName)) {
      const list = this.registry.list()

      const serenaMatch = list.find(d => d.name.startsWith('serena__') && (
        (toolName.includes('read') && d.name.includes('read')) ||
        ((toolName.includes('write') || toolName.includes('create')) && (d.name.includes('write') || d.name.includes('create') || d.name.includes('replace') || d.name.includes('insert'))) ||
        (toolName.includes('exists') && d.name.includes('exists')) ||
        (toolName.includes('mkdir') && d.name.includes('mkdir')) ||
        (toolName === 'bash' && d.name.includes('shell'))
      ))
      if (serenaMatch) return this.registry.get(serenaMatch.name)

      const suffixMatch = list.find(d => d.name.endsWith(`__${toolName}`))
      if (suffixMatch) return this.registry.get(suffixMatch.name)
    }

    return undefined
  }

  clearToolCache(): void {
    this.resolvedToolCache.clear()
  }

  /**
   * Wire the Permission Oracle for graduated autonomy gating.
   * 'deny' = blocked, 'escalate' = human approval required, 'allow' = proceed
   */
  setPermissionOracle(oracle: PermissionOracle): void {
    this.permissionOracle = oracle
  }

  setTrustLedger(ledger: TrustLedger): void {
    this.trustLedger = ledger
  }

  isAvailable(name: string): boolean {
    return this.registry.get(name) !== undefined
  }

  setReliabilityTracker(tracker: ToolReliabilityTracker): void {
    this.reliabilityTracker = tracker
  }

  setSessionContext(sessionId: string, overrides: Partial<ToolExecutionContext>): void {
    this.sessionContextOverrides.set(sessionId, overrides)
  }

  clearSessionContext(sessionId: string): void {
    this.sessionContextOverrides.delete(sessionId)
  }

  hasSessionContext(sessionId: string): boolean {
    return this.sessionContextOverrides.has(sessionId)
  }

  // REMOVED: setOrchestrator and getOrchestrator — deprecated TriadTeam deleted

  /**
   * Wire external shell hooks for PreToolUse/PostToolUse interception.
   * Exit codes: 0 = allow, 2 = deny, other = warn but proceed
   */
  setExternalHooks(config: ExternalHookConfig): void {
    this.hookRunner = new ExternalHookRunner(config, this.logger)
  }

  async execute(
    call: ToolCall,
    sessionId: string,
    opts?: { workingDir?: string },
  ): Promise<ToolResult> {
    // REMOVED: orchestrator delegation — deprecated TriadTeam deleted

    const executeStartMs = Date.now()

    const entry = this.resolveToolCached(call.name)

    if (!entry) {
      this.emitToolExecuted(sessionId, call.name, Date.now() - executeStartMs, true)
      return { toolCallId: call.id, toolName: call.name, content: `Unknown tool: ${call.name}`, isError: true }
    }

    let actualToolName = call.name
    let actualEntry = entry
    if (this.reliabilityTracker) {
      if (!this.reliabilityTracker.canExecute(call.name)) {
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
          this.emitToolExecuted(sessionId, call.name, Date.now() - executeStartMs, true)
          return {
            toolCallId: call.id,
            toolName: actualToolName,
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

    if (ENABLE_SAFETY_GUARDS) {
      const inputValidation = validateToolInput(actualToolName, call.input)
      if (!inputValidation.valid) {
        this.emitSafetyEvent(sessionId, actualToolName, 'input_validation_failed', inputValidation.errors)
        this.emitToolExecuted(sessionId, actualToolName, Date.now() - executeStartMs, true)
        return {
          toolCallId: call.id,
          toolName: call.name,
          content: `Safety check failed: ${inputValidation.errors.join(', ')}`,
          isError: true
        }
      }
    }

    this.trackSkillInvocation({ ...call, name: actualToolName }, sessionId)

    // WHY: read-only tools (file reads, searches, web fetches) skip permission checks
    // — they're provably safe and don't need consequence estimation on every call
    const toolDef = actualEntry?.definition
    const skipPermissionCheck = toolDef?.requiredPermission === 'read-only'

    // WHY: 5-second cache prevents redundant risk assessment for repetitive calls
    // (e.g., reading 10 files in a loop) — collisions just re-run judge()
    if (this.permissionOracle && !skipPermissionCheck) {
      const cacheKey = permissionCacheKey(call.name, call.input)
      const cached = this.permissionCache.get(cacheKey)

      if (cached?.decision === 'deny') {
        this.emitToolExecuted(sessionId, call.name, Date.now() - executeStartMs, true)
        return {
          toolCallId: call.id,
          toolName: call.name,
          content: `Permission denied (cached): ${cached.reasoning}`,
          isError: true,
        }
      }

      if (!cached || cached.decision !== 'allow') {
        const verdict = this.permissionOracle.judge(call.name, call.input, sessionId, {
          sessionType: ctx.sessionType,
        })

        this.permissionCache.set(cacheKey, {
          decision: verdict.decision,
          reasoning: verdict.reasoning,
        })

        if (verdict.decision === 'deny') {
          this.emitToolExecuted(sessionId, call.name, Date.now() - executeStartMs, true)
          return {
            toolCallId: call.id,
            toolName: call.name,
            content: `Permission denied: ${verdict.reasoning}` +
              ` (risk=${verdict.riskAssessment.riskScore.toFixed(2)}, trust=${verdict.trustScore.score.toFixed(2)})`,
            isError: true,
          }
        }

        if (verdict.decision === 'escalate') {
          this.permissionCache.delete(cacheKey)

          // WHY: escalate never cached — human must approve each occurrence
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
              toolName: call.name,
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
      let preHookMessages: string[] = []
      if (this.hookRunner?.hasHooks()) {
        const preResult = await this.hookRunner.runPreToolUse(actualToolName, call.input)
        preHookMessages = preResult.messages
        if (preResult.denied) {
          const denyMessage = preResult.messages.join('\n') || `PreToolUse hook denied tool \`${actualToolName}\``
          if (this.trustLedger) {
            const domain = resolveToolDomain(actualToolName)
            this.trustLedger.recordEvidence({
              domain,
              success: false,
              weight: 0.5,
              source: 'external-hook',
              description: `PreToolUse hook denied tool '${actualToolName}'`,
              sessionId,
              timestamp: Date.now(),
            })
          }
          this.emitToolExecuted(sessionId, actualToolName, Date.now() - executeStartMs, true)
          return {
            toolCallId: call.id,
            toolName: actualToolName,
            content: denyMessage,
            isError: true,
          }
        }
      }

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
            toolName: actualToolName,
            content: `Tool failed: ${safeResult.error || 'Unknown error'} (${safeResult.errorType || 'execution'})`,
            isError: true
          }
        }

        const outputValidation = validateToolOutput(actualToolName, safeResult.data)
        if (!outputValidation.valid) {
          this.emitSafetyEvent(sessionId, actualToolName, 'output_validation_failed', outputValidation.errors)
          this.recordToolOutcome(actualToolName, false, sessionId, `Output validation failed`)
          this.recordReliabilityOutcome(actualToolName, durationMs, false)
          this.emitToolExecuted(sessionId, actualToolName, durationMs, true)
          return {
            toolCallId: call.id,
            toolName: actualToolName,
            content: `Output validation failed: ${outputValidation.errors.join(', ')}`,
            isError: true
          }
        }

        this.recordToolOutcome(actualToolName, true, sessionId, `Executed successfully`)
        this.recordReliabilityOutcome(actualToolName, durationMs, true)
        this.emitToolExecuted(sessionId, actualToolName, durationMs, false)
        const enrichment = this.enrichToolResult(sessionId, actualToolName, durationMs, false)
        
        const presented = this.applyPresentation(String(safeResult.data), actualToolName, durationMs)

        let finalContent = presented.content
        if (this.hookRunner?.hasHooks()) {
          const postResult = await this.hookRunner.runPostToolUse(
            actualToolName, call.input, finalContent, false,
          )
          finalContent = mergeHookFeedback(
            [...preHookMessages, ...postResult.messages],
            finalContent,
            postResult.denied,
          )
        } else if (preHookMessages.length > 0) {
          finalContent = mergeHookFeedback(preHookMessages, finalContent, false)
        }

        return {
          toolCallId: call.id,
          toolName: actualToolName,
          content: enrichment ? finalContent + enrichment : finalContent,
          isError: false,
          rawContent: presented.rawContent,
          exitCode: presented.exitCode,
          durationMs,
        }
      } else {
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
        const enrichment = this.enrichToolResult(sessionId, actualToolName, durationMs, false)
        
        const presented = this.applyPresentation(result, actualToolName, durationMs)
        return {
          toolCallId: call.id,
          toolName: actualToolName,
          content: enrichment ? presented.content + enrichment : presented.content,
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
      return { toolCallId: call.id, toolName: call.name, content: String(err), isError: true }
    }
  }

  /**
   * WHY: Records tool outcomes as evidence — trust scores converge toward
   * actual success rates per domain over time (Bayesian learning)
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
   * WHY: Circuit breaker pattern — consecutive failures open the circuit,
   * allowing fallback routing before the tool is retried
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
   * WHY: Thinker consumes this event to trigger insight cycles on tool activity
   */
  private emitToolExecuted(
    sessionId: string,
    toolName: string,
    durationMs: number,
    isError: boolean,
  ): void {
    // Brain signal — always posted regardless of event bus availability
    this.postBrainSignal(sessionId, toolName, durationMs, isError)

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

  /* ------------------------------------------------------------------ */
  /*  Brain integration — cortex signal on every tool execution          */
  /* ------------------------------------------------------------------ */

  /**
   * Tool category → cortex region/type mapping.
   * Mirrors the gateway TOOL_SIGNAL_MAP but works in-process via CorticalField.
   */
  private static readonly TOOL_BRAIN_MAP: Record<string, { region: string; type: SignalType; salienceBase: number }> = {
    // Motor: tools that mutate state
    bash:          { region: 'motor',       type: 'action',      salienceBase: 0.45 },
    write_file:    { region: 'motor',       type: 'action',      salienceBase: 0.5 },
    write:         { region: 'motor',       type: 'action',      salienceBase: 0.5 },
    edit:          { region: 'motor',       type: 'action',      salienceBase: 0.5 },
    todo_write:    { region: 'motor',       type: 'action',      salienceBase: 0.45 },
    // Sensory: tools that observe/read (above 0.3 activeThreshold)
    read_file:     { region: 'sensory',     type: 'perception',  salienceBase: 0.35 },
    read:          { region: 'sensory',     type: 'perception',  salienceBase: 0.35 },
    // Association: tools that analyze
    collect_thoughts: { region: 'association', type: 'association', salienceBase: 0.5 },
    // Executive: tools that decide/orchestrate
    spawn_subagent:   { region: 'executive',  type: 'decision',   salienceBase: 0.7 },
  }

  /** Post a cortex signal for a tool execution. Fire-and-forget — never blocks. */
  private postBrainSignal(
    sessionId: string,
    toolName: string,
    durationMs: number,
    isError: boolean,
    resultPreview?: string,
  ): void {
    const cortex = this.defaultContext._cortex as CorticalField | undefined
    if (!cortex) return

    // Strip MCP server prefixes (serena__, gitnexus__) to find the base tool
    const baseName = toolName.replace(/^[a-z]+__/, '')
    const mapping = ToolExecutor.TOOL_BRAIN_MAP[baseName]
    if (!mapping) return

    const salience = Math.min(1.0, mapping.salienceBase + (isError ? 0.3 : 0))
    const preview = (resultPreview || '').slice(0, 120).replace(/\n/g, ' ')

    try {
      cortex.signal(isError ? 'limbic' : mapping.region, {
        type: isError ? 'concern' : mapping.type,
        content: `[tool:${baseName}] ${isError ? 'ERROR: ' : ''}${preview} (${durationMs}ms)`,
        author: 'tool-executor',
        salience,
        confidence: isError ? 0.9 : 0.7,
        valence: isError ? -0.3 : 0.1,
        tags: ['tool', baseName, ...(isError ? ['error'] : [])],
        sessionId,
      })
    } catch {
      // Brain signals are best-effort — never let this break tool execution
    }
  }

  private enrichToolResult(
    sessionId: string,
    toolName: string,
    durationMs: number,
    isError: boolean,
  ): string | null {
    let trustScore: number | undefined
    let riskScore: number | undefined

    if (this.trustLedger) {
      try {
        const domain = resolveToolDomain(toolName)
        const score = this.trustLedger.getDomainScore(domain)
        if (score) trustScore = score.score
      } catch { /* non-fatal */ }
    }

    if (this.permissionOracle) {
      const cacheKey = permissionCacheKey(toolName, {})
      const cached = this.permissionCache.get(cacheKey)
      if (cached) {
        const riskMatch = cached.reasoning?.match(/risk[=:](\d+\.?\d*)/i)
        if (riskMatch) riskScore = parseFloat(riskMatch[1])
      }
    }

    if (this.eventBus) {
      this.eventBus.emit({
        type: 'tool:enriched' as any,
        sessionId, toolName, durationMs, isError,
        enrichment: { trustScore, riskScore },
        timestamp: new Date(),
      })
    }

    const parts: string[] = []
    if (trustScore !== undefined) {
      const bar = trustScore >= 0.8 ? '████' : trustScore >= 0.6 ? '███░' : trustScore >= 0.4 ? '██░░' : '█░░░'
      parts.push(`trust ${bar} ${trustScore.toFixed(2)}`)
    }
    if (riskScore !== undefined) {
      const label = riskScore < 0.3 ? 'low' : riskScore < 0.6 ? 'med' : riskScore < 0.8 ? 'high' : 'crit'
      parts.push(`risk ${label} ${riskScore.toFixed(2)}`)
    }
    if (parts.length === 0) return null
    return `\n━━ CassiCore ━ ${parts.join(' · ')} ━━`
  }

  private trackSkillInvocation(call: ToolCall, sessionId: string): void {
    if (!this.eventBus) return

    const isReadTool = call.name === 'read' || call.name === 'read_file' ||
                       call.name.endsWith('__read') || call.name.endsWith('__read_file')

    if (!isReadTool) return

    const filePath = (call.input.path as string) || (call.input.file_path as string)
    if (!filePath) return

    if (!filePath.includes('SKILL.md')) return

    const pathParts = filePath.split(/[/\\]/)
    const skillFileIndex = pathParts.indexOf('SKILL.md')
    if (skillFileIndex === -1) return

    const skillName = skillFileIndex > 0 ? pathParts[skillFileIndex - 1] : 'unknown'

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

    this.eventBus.emit({
      type: 'skill:invoked',
      skillName,
      skillPath: filePath,
      sessionId,
      timestamp: new Date(),
      source,
    })
  }

  private applyPresentation(
    rawOutput: string,
    toolName: string,
    durationMs: number,
  ): { content: string; rawContent: string; exitCode?: number; stderr?: string } {
    let exitCode: number | undefined
    let stderr: string | undefined
    let contentToPresent = rawOutput

    if (toolName === 'bash' || toolName === 'shell_exec' || toolName === 'shell-exec') {
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
          const call = batch[j]
          this.logger.error('Tool execute() rejected unexpectedly', {
            toolName: call.name,
            error: String(outcome.reason),
            sessionId,
          })
          results.push({
            toolCallId: call.id,
            toolName: call.name,
            content: `Tool execution failed: ${String(outcome.reason)}`,
            isError: true,
          })
        }
      }
    }
    return results
  }


  /**
   * Commit workspace files as a single git commit with session attribution.
   * Called when a delegated agent session (Helix/Dyad/Lumen/Flux) completes.
   */
  async commitSession(
    opts: Omit<SessionCommitOpts, 'workingDir'>,
  ): Promise<SessionCommitResult> {
    const store = this.defaultContext._fileArtifactStore
    if (!store) {
      return {
        committed: false,
        fileCount: 0,
        files: [],
        reason: 'FileArtifactStore not available',
      }
    }

    return commitSessionChanges(store, {
      ...opts,
      workingDir: this.defaultContext.workingDir,
    }, this.logger)
  }
}
