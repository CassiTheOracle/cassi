/**
 * VENDOR TYPE STUB — core/tools/executor.ts
 * Faithful type surface for helix consumers (ToolExecutor class). No runtime.
 * Re-pointed to `@cassicore/tools` at P6; delete this stub then.
 * Foundation + sibling tools stubs only; self-contained.
 */
import type { IEventBus } from '@cassicore/foundation'
import type { ToolRegistry } from './registry.js'
import type { ToolCall, ToolResult, ToolExecutionContext } from './types.js'

/**
 * Executes registered tools with permission/safety orchestration. Helix drives
 * `execute(call, sessionId)` for work-stream tool calls.
 */
export class ToolExecutor {
  constructor(
    private registry: ToolRegistry,
    private defaultContext: Omit<ToolExecutionContext, 'sessionId'>,
    private eventBus?: IEventBus,
  ) {
    void registry
    void defaultContext
    void eventBus
  }

  clearToolCache(): void {
    // no-op
  }

  setPermissionOracle(oracle: unknown): void {
    void oracle
  }

  setTrustLedger(ledger: unknown): void {
    void ledger
  }

  isAvailable(name: string): boolean {
    void name
    return false
  }

  setReliabilityTracker(tracker: unknown): void {
    void tracker
  }

  setSessionContext(sessionId: string, overrides: Partial<ToolExecutionContext>): void {
    void sessionId
    void overrides
  }

  clearSessionContext(sessionId: string): void {
    void sessionId
  }

  hasSessionContext(sessionId: string): boolean {
    void sessionId
    return false
  }

  setExternalHooks(config: unknown): void {
    void config
  }

  async execute(
    call: ToolCall,
    sessionId: string,
    opts?: { workingDir?: string },
  ): Promise<ToolResult> {
    void call
    void sessionId
    void opts
    throw new Error('not connected (lands at P6 @cassicore/tools)')
  }

  async executeAll(calls: ToolCall[], sessionId: string): Promise<ToolResult[]> {
    void calls
    void sessionId
    throw new Error('not connected (lands at P6 @cassicore/tools)')
  }
}
