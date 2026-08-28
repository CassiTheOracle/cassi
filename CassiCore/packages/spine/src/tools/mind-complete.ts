/**
 * @cassicore/spine — the `mind_complete` model-access bridge (plan §2.3).
 *
 * The ONLY provider-adjacent surface the spine keeps. Registered via `pi.registerTool`.
 * It is NOT forwarded to the runtime — it executes in the spine using the retained
 * completion transport:
 *   1. Resolve `spec.model` ("provider/model-id" OR a role alias like @smol/@slow)
 *      via `ctx.models.resolve(spec)` (recon §1.5/§2.6).
 *   2. Send ONE completion through the transport (by default, the local
 *      OpenAI-compatible llama-server loopback adapter).
 *   3. Return `{ content, model }` (+ usage when surfaced).
 *
 * Streaming (Open Item 6): single-shot — `onUpdate` is unused. The retained
 * pure-completion consumers (corpus/brainstem) don't need token-level output.
 *
 * The production default intentionally uses the existing local llama-server adapter
 * rather than adding a provider path to CassiCore. Hosts may still inject an explicit
 * `MindCompleteTransport`; ordinary ohmypi provider sessions remain owned by ohmypi.
 * Configure the default loopback adapter with `CASSI_LLAMA_SERVER_URL` /
 * `CASSI_LLAMA_SERVER_TOKEN` / `CASSI_LLAMA_SERVER_TIMEOUT_MS` /
 * `CASSI_WORLD_PROVIDER_URL` (the corresponding `LLAMA_SERVER_*` names are
 * accepted as compatibility aliases).
 */

import type { AgentToolResult, ExtensionAPI } from '../oh-my-pi-types.js'
import { createLlamaServerTransport } from './llama-server-transport.js'

function firstNonEmptyEnv(...names: string[]): string | undefined {
  for (const name of names) {
    const value = process.env[name]?.trim()
    if (value) return value
  }
  return undefined
}

/** Build the default local transport at registration time so env overrides are read
 * after the host has initialized its process configuration. */
function createDefaultTransport(): MindCompleteTransport {
  const timeoutText = firstNonEmptyEnv(
    'CASSI_LLAMA_SERVER_TIMEOUT_MS',
    'LLAMA_SERVER_TIMEOUT_MS',
  )
  return createLlamaServerTransport({
    baseUrl: firstNonEmptyEnv('CASSI_LLAMA_SERVER_URL', 'LLAMA_SERVER_URL'),
    worldModeUrl: firstNonEmptyEnv('CASSI_WORLD_PROVIDER_URL') ?? 'http://127.0.0.1:8082',
    apiToken: firstNonEmptyEnv('CASSI_LLAMA_SERVER_TOKEN', 'LLAMA_SERVER_TOKEN'),
    timeoutMs: timeoutText === undefined ? undefined : Number(timeoutText),
  })
}

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
  cassi_world_mode?: 'closed_loop'
}

export type MindCompleteTransport = (
  resolved: ResolvedModel,
  messages: Array<{ role: string; content: string }>,
  opts: { effort?: string; temperature?: number; cassi_world_mode?: 'closed_loop' },
) => Promise<{ content: string; usage?: unknown }>

/** Register the `mind_complete` bridge tool on the extension API. */
export function registerMindCompleteTool(
  pi: ExtensionAPI,
  transport: MindCompleteTransport = createDefaultTransport(),
): void {
  pi.registerTool({
    name: 'mind_complete',
    label: 'mind_complete',
    description:
      'Perform a single model completion through the retained transport (default: local ' +
      'OpenAI-compatible llama-server; no agent session). ' +
      'Used by mind-internal pure-completion primitives (corpus-LLM summarizer, brainstem-LLM). ' +
      `model may be "provider/model-id" or a role alias (@smol/@slow); effort + temperature pass through.`,
    parameters: pi.zod.object({
      model: pi.zod.string(),
      messages: pi.zod.array(pi.zod.object({ role: pi.zod.string(), content: pi.zod.string() })),
      tools: pi.zod.array(pi.zod.any()).optional(),
      effort: pi.zod.enum(['minimal', 'low', 'medium', 'high', 'xhigh', 'max']).optional(),
      temperature: pi.zod.number().optional(),
      cassi_world_mode: pi.zod.enum(['closed_loop']).optional(),
    }),
    execute: async (_id, params, _signal, _onUpdate, ctx): Promise<AgentToolResult> => {
      const spec = params as MindCompleteSpec
      // 1. Resolve the model.
      const resolved = ctx.models.resolve(spec.model)
      if (!resolved) {
        return { content: [{ type: 'text', text: `model not resolvable: ${spec.model}` }], isError: true }
      }
      // 2. Send ONE completion through the retained transport.
      try {
        const { content, usage } = await transport(resolved, spec.messages, {
          effort: spec.effort,
          temperature: spec.temperature,
          cassi_world_mode: spec.cassi_world_mode,
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
