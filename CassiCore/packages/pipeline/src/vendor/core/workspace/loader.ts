/**
 * VENDOR RUNTIME STUB — `core/workspace/loader.ts` (buildSystemPrompt).
 *
 * `adapter/SessionPipeline.ts` imports `buildSystemPrompt` from
 * `core/workspace/loader.js`. `core/workspace/` is NOT a P6 package (owning
 * home is TBD — P7 @cassicore/host or a @cassicore/workspace package, plan
 * Open-3). This stub returns the canonical persona prompt string inferred from
 * the repo's instruction-discovery fixtures; re-point to the real owner at P7.
 */
import type { ILogger } from '@cassicore/foundation'

/** Build the system prompt for a session (faithful structural surface). */
export function buildSystemPrompt(_logger?: ILogger): string {
  return [
    'You are CassiCore, an autonomous research and coding engine.',
    'Operate in a loop: propose -> act -> inspect -> verify -> commit.',
    'Prefer direct file edits and runnable commands over prose.',
  ].join('\n')
}
