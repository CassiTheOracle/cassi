/**
 * VENDOR TYPE STUB — `core/turn-pipeline.ts` (host, P7).
 *
 * Type placeholder for the host-side turn pipeline surface consumed by the
 * tools (spawn-subagent-impl's `pipeline.process(...)`). Owned by the host
 * package (P7). Re-pointed there.
 */
import type { InboundMessage, TurnResult } from '@cassicore/foundation'

/** Process a turn against the pipeline and return the result. */
export interface TurnPipeline {
  process(inbound: InboundMessage): Promise<TurnResult>
}
