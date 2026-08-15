/**
 * @cassicore/model-pool — RETAINED `mind_complete` transport (CASSICORE-FOCUS §2.3 / §6 P4)
 *
 * The retained ModelHandle casts completion through an injected
 * `MindCompleteTransport` — a single-shot ohmypi-backed completion that
 * mirrors the spine's `mind_complete` bridge tool (packages/spine/src/tools/
 * mind-complete.ts). The spine/host injects this at bootstrap; model-pool
 * stays decoupled from `@cassicore/spine`.
 *
 * DEFAULT TRANSPORT: the 'not wired' transport throws a documented error. This
 * is the transitional P4 state — standalone host completions ride the shim
 * and fail loudly until the spine/ohmypi path is live (plan P5/P6). Retained
 * consumers that need live completions inject a real transport.
 */

/** Structural slice of an ohmypi-resolved model (mirrors spine ResolvedModel). */
export interface ResolvedModel {
  id: string
  family?: string
}

/** The retained completion transport — one ohmypi-backed single-shot call. */
export type MindCompleteTransport = (
  resolved: ResolvedModel,
  messages: Array<{ role: string; content: string }>,
  opts?: { effort?: string; temperature?: number; model?: string },
) => Promise<{ content: string; usage?: unknown; model?: string }>

/** Default transport: throws until the platform wires mind_complete (plan §2.3). */
export const defaultMindCompleteTransport: MindCompleteTransport = async () => {
  throw new Error(
    'mind_complete transport not wired: the ohmypi raw-completion path is a P4→P5 transition. ' +
      'Inject a `MindCompleteTransport` (e.g. the spine `mind_complete` bridge) into ' +
      '`createMindCompleteAcquirer`, or route mind-internal reasoning through ohmypi task-agents.',
  )
}
