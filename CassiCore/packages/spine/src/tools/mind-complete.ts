/**
 * @cassicore/spine — the `mind_complete` model-access bridge (plan §2.3).
 *
 * The ONLY provider-adjacent surface the spine keeps. Registered via `pi.registerTool`.
 * It is NOT forwarded to the runtime — it executes in the spine using ohmypi's own
 * provider path:
 *   1. Resolve `spec.model` ("provider/model-id" OR a role alias like @smol/@slow)
 *      via `ctx.models.resolve(spec)` (recon §1.5/§2.6).
 *   2. Stream ONE completion through ohmypi's provider path.
 *   3. Return `{ content, model }` (+ usage when surfaced).
 *
 * Streaming (Open Item 6): single-shot for P3 — `onUpdate` unused. The retained
 * pure-completion consumers (corpus/brainstem) don't need token-level output.
 *
 * [VERIFY] The exact ohmypi completion transport (`ctx.models.resolve` gives the
 * `Model`, but a raw single-shot completion over the resolved provider is not exposed
 * as a trivial one-liner on `ExtensionContext`). P3 defaults to an injectable
 * `complete` transport (documented above) so the tool is real and contract-testable;
 * the P4 cutover wires the production ohmypi provider stream. If ohmypi never surfaces
 * a faithful completion primitive, mind_internal loops route through task-agents
 * (option A-primary, plan §2.2) instead.
 */

import type { AgentToolResult, ExtensionAPI, ExtensionContext } from '../oh-my-pi-types.js'

/** Structural slice of ohmypi's `Model` (avoid a deep catalog type import). */
export interface ResolvedModel {
  id: string
  family?: string
}

export interface MindCompleteSpec {
  model: string
  messages: Array<{ role: string; content: string }>
  tools?: unknown[]
  effort?: 'minimal' | 'low' | 'medium' | 'high' | 'xhigh' | 'max'
  temperature?: number
}

export type MindCompleteTransport = (
  resolved: ResolvedModel,
  messages: Array<{ role: string; content: string }>,
  opts: { effort?: string; temperature?: number },
) => Promise<{ content: string; usage?: unknown }>

/** Default transport: identical to the brief's shape; wired by the platform at P4.
 *  P3 returns a clear, non-fatal error so callers degrade gracefully. */
const defaultTransport: MindCompleteTransport = async () => {
  throw new Error(
    'mind_complete transport not wired: the ohmypi raw-completion path is a P4 cutover ' +
    '(plan §2.3). Use task-agents for mind-internal reasoning, or wire `capTransport` to ' +
    "ohmypi's provider stream."
  )
}

/** Register the `mind_complete` bridge tool on the extension API. */
export function registerMindCompleteTool(
  pi: ExtensionAPI,
  transport: MindCompleteTransport = defaultTransport,
): void {
  pi.registerTool({
    name: 'mind_complete',
    label: 'mind_complete',
    description:
      'Perform a single model completion through the harness provider stack (no agent session). ' +
      'Used by mind-internal pure-completion primitives (corpus-LLM summarizer, brainstem-LLM). ' +
      `model may be "provider/model-id" or a role alias (@smol/@slow); effort + temperature pass through.`,
    parameters: pi.zod.object({
      model: pi.zod.string(),
      messages: pi.zod.array(pi.zod.object({ role: pi.zod.string(), content: pi.zod.string() })),
      tools: pi.zod.array(pi.zod.any()).optional(),
      effort: pi.zod.enum(['minimal', 'low', 'medium', 'high', 'xhigh', 'max']).optional(),
      temperature: pi.zod.number().optional(),
    }),
    execute: async (_id, params, _signal, _onUpdate, ctx): Promise<AgentToolResult> => {
      const spec = params as MindCompleteSpec
      // 1. Resolve the model.
      const resolved = ctx.models.resolve(spec.model)
      if (!resolved) {
        return { content: [{ type: 'text', text: `model not resolvable: ${spec.model}` }], isError: true }
      }
      // 2. Stream ONE completion through ohmypi's provider path.
      try {
        const { content, usage } = await transport(resolved, spec.messages, {
          effort: spec.effort,
          temperature: spec.temperature,
        })
        return {
          content: [{ type: 'text', text: JSON.stringify({ content, model: resolved.id, usage }) }],
        }
      } catch (err) {
        return { content: [{ type: 'text', text: `mind_complete failed: ${String(err)}` }], isError: true }
      }
    },
  })
}
