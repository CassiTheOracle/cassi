/**
 * TOOLS PORT — `TurnPipeline` (injected seam).
 *
 * The turn-pipeline surface consumed by the tools (spawn-subagent-impl's
 * `pipeline.process(...)`). TYPE-ONLY port: the tools never construct a
 * pipeline — the host injects its real `TurnPipeline` at boot via
 * `CoreToolDeps.getPipeline` (a lazy getter because tools are registered
 * before the pipeline is built).
 *
 * Declared here (self-contained, no `@cassicore/host` import) so the tools
 * package compiles against a stable seam without depending on the host —
 * P1 host↔tools|mcp cycle resolution.
 */
import type { InboundMessage, TurnResult } from '@cassicore/foundation'

/** Process a turn against the pipeline and return the result. */
export interface TurnPipeline {
  process(inbound: InboundMessage): Promise<TurnResult>
}
