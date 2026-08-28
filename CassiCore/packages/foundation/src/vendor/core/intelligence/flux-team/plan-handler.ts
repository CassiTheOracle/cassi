/**
 * VENDOR TYPE STUB — `core/intelligence/flux-team/plan-handler.ts`
 *
 * Type-only placeholder for the `PlanHandler` surface consumed by the P1 live-set
 * (`types/cassi-agent.ts`). Self-contained; builtin types only; no runtime.
 * Re-pointed to `@cassicore/flux-team` at P3.
 */

/** The posture mode being executed. */
export type PlanPosture = string

/** Coordinates plan/tool-call handling across a flux-team. */
export class PlanHandler {
  /** Handle a tool call within the given posture. */
  handleToolCall(toolName: string, input: Record<string, unknown>, posture: PlanPosture): string {
    throw new Error('vendor stub: no runtime implementation')
  }
}
