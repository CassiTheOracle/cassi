import type { ToolCall, ToolResult, ToolExecutionContext } from './types.js'
import type { ToolRegistry } from './registry.js'
import type { IEventBus } from '../../types/interfaces.js'
import { validateToolInput, validateToolOutput, executeToolSafe } from './safety.js'

const MAX_CONCURRENT = 20
const ENABLE_SAFETY_GUARDS = true  // Can be disabled for debugging

export class ToolExecutor {
  constructor(
    private registry: ToolRegistry,
    private defaultContext: Omit<ToolExecutionContext, 'sessionId'>,
    private eventBus?: IEventBus,
  ) {}

  async execute(call: ToolCall, sessionId: string): Promise<ToolResult> {
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
      return { toolCallId: call.id, content: `Unknown tool: ${call.name}`, isError: true }
    }

    const timeout = entry.definition.timeoutMs ?? 30_000
    const ctx: ToolExecutionContext = { ...this.defaultContext, sessionId }

    // SAFETY: Pre-call input validation
    if (ENABLE_SAFETY_GUARDS) {
      const inputValidation = validateToolInput(call.name, call.input)
      if (!inputValidation.valid) {
        this.emitSafetyEvent(sessionId, call.name, 'input_validation_failed', inputValidation.errors)
        return {
          toolCallId: call.id,
          content: `Safety check failed: ${inputValidation.errors.join(', ')}`,
          isError: true
        }
      }
    }

    // Track skill invocations when reading SKILL.md files
    this.trackSkillInvocation(call, sessionId)

    try {
      // SAFETY: Execute with timeout and error containment
      if (ENABLE_SAFETY_GUARDS) {
        const safeResult = await executeToolSafe(
          call.name,
          () => entry!.handler(call.input, ctx),
          call.input,
          timeout
        )

        if (!safeResult.success) {
          this.emitSafetyEvent(sessionId, call.name, safeResult.errorType || 'execution', [safeResult.error || 'Unknown error'])
          return {
            toolCallId: call.id,
            content: `Tool failed: ${safeResult.error || 'Unknown error'} (${safeResult.errorType || 'execution'})`,
            isError: true
          }
        }

        // SAFETY: Post-call output validation
        const outputValidation = validateToolOutput(call.name, safeResult.data)
        if (!outputValidation.valid) {
          this.emitSafetyEvent(sessionId, call.name, 'output_validation_failed', outputValidation.errors)
          return {
            toolCallId: call.id,
            content: `Output validation failed: ${outputValidation.errors.join(', ')}`,
            isError: true
          }
        }

        return { toolCallId: call.id, content: String(safeResult.data), isError: false }
      } else {
        // Legacy execution (safety disabled)
        const result = await Promise.race([
          entry.handler(call.input, ctx),
          new Promise<never>((_, reject) =>
            setTimeout(
              () => reject(new Error(`Tool '${call.name}' timed out after ${timeout}ms`)),
              timeout,
            )
          ),
        ])
        return { toolCallId: call.id, content: result, isError: false }
      }
    } catch (err) {
      this.emitSafetyEvent(sessionId, call.name, 'execution', [String(err)])
      return { toolCallId: call.id, content: String(err), isError: true }
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

  /** Execute up to MAX_CONCURRENT tool calls concurrently */
  async executeAll(calls: ToolCall[], sessionId: string): Promise<ToolResult[]> {
    const results: ToolResult[] = []
    for (let i = 0; i < calls.length; i += MAX_CONCURRENT) {
      const batch = calls.slice(i, i + MAX_CONCURRENT)
      const batchResults = await Promise.all(batch.map(c => this.execute(c, sessionId)))
      results.push(...batchResults)
    }
    return results
  }
}
