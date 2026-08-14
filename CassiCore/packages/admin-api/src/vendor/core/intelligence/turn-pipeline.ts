/**
 * VENDOR TYPE STUB — core/turn-pipeline.ts (host-coupled, P7 host publishes).
 *
 * Type placeholder for the host-side turn-pipeline surface consumed by the
 * vendored context-assembler (`getPipeline?: () => TurnPipeline`). Mirrors the
 * tools package's vendor type stub. Re-pointed to @cassicore/host when the host
 * package publishes its turn-pipeline module.
 */
import type { InboundMessage, TurnResult } from '@cassicore/foundation'

/** Process a turn against the pipeline and return the result. */
export interface TurnPipeline {
  process(inbound: InboundMessage): Promise<TurnResult>
}
