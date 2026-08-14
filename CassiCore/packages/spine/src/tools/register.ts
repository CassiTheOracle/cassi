/**
 * @cassicore/spine — retained mind-tool registration (plan §4.2).
 *
 * Registers the retained mind tools via `pi.registerTool` as THIN DELEGATES: the
 * parameter schema is rebuilt from the retained `@cassicore/tools` definition for
 * name/param fidelity, and `execute` forwards `{tool, params, sessionId}` to the mind
 * runtime channel, returning the retained handler's string result as
 * `AgentToolResult.content` (Open Item 7: no structured-content wrapper for P3).
 *
 * Registration set:
 *  - RETAINED (visible): collect_thoughts, graph_discover, list_sessions, list_subagents,
 *    get_subagent_status, get_subagent_result, system_health, debug_session,
 *    universal_search, cassandra_query_events, cassandra_context_inspect, query_events.
 *    (12 retained + mind_complete = the 13 plan §4.2 tools; mind_complete is registered
 *    separately in tools/mind-complete.ts.)
 *  - SEAM (`hidden: true, defaultInactive: true`): _reflect / _remember / _coordinate /
 *    _check_peers / remember / memory_search — P5-deletion seam; kept registered but
 *    inactive until the ratified deletion lands (§7.5). Their execute still delegates
 *    to the runtime (the retained handlers are registered there too).
 */

import type { ToolDefinition as CassiToolDefinition } from '@cassicore/tools'
import {
  collectThoughtsDefinition,
  graphDiscoverDefinition,
  reflectDefinition,
  cognitiveRememberDefinition,
  coordinateDefinition,
  checkPeersDefinition,
  memorySearchDefinition,
  rememberDefinition,
  listSubagentsDefinition,
  getSubagentStatusDefinition,
  getSubagentResultDefinition,
  systemHealthDefinition,
  debugSessionDefinition,
  universalSearchDefinition,
  cassandraQueryEventsDef,
  cassandraContextInspectDef,
  queryEventsDefinition,
} from '@cassicore/tools'
import type { AgentToolResult, ExtensionAPI, ExtensionContext } from '../oh-my-pi-types.js'

import type { ChannelClient } from '../channel/client.js'
import { zodFromParamSchema } from '../schemas.js'

/** A retained mind tool to register (definition + whether it's a hidden seam). */
interface RetainedRegistration {
  definition: CassiToolDefinition
  /** hidden + inactive for the P5-deletion seam tools (plan §7.5). */
  seam?: boolean
}

const RETAINED_TOOLS: RetainedRegistration[] = [
  { definition: collectThoughtsDefinition },
  { definition: graphDiscoverDefinition },
  { definition: listSubagentsDefinition },
  { definition: getSubagentStatusDefinition },
  { definition: getSubagentResultDefinition },
  { definition: systemHealthDefinition },
  { definition: debugSessionDefinition },
  { definition: universalSearchDefinition },
  { definition: cassandraQueryEventsDef },
  { definition: cassandraContextInspectDef },
  { definition: queryEventsDefinition },
]

const SEAM_TOOLS: RetainedRegistration[] = [
  { definition: reflectDefinition, seam: true },
  { definition: cognitiveRememberDefinition, seam: true },
  { definition: coordinateDefinition, seam: true },
  { definition: checkPeersDefinition, seam: true },
  { definition: rememberDefinition, seam: true },
  { definition: memorySearchDefinition, seam: true },
]

// ── Factory shape helpers ──────────────────────────────────────────────────

function textResult(text: string, isError?: boolean): AgentToolResult {
  return { content: [{ type: 'text', text }], isError }
}

/** Execute a retained tool via the runtime channel (thin delegate). */
async function delegateTool(
  client: ChannelClient,
  name: string,
  params: Record<string, unknown>,
  ctx: ExtensionContext,
): Promise<AgentToolResult> {
  const sessionId = ctx.sessionManager.getSessionId()
  try {
    const res = await client.executeTool(name, params, sessionId)
    if (res.ok) return textResult(res.result ?? '')
    return textResult(res.error ?? `tool ${name} failed`, true)
  } catch (err) {
    return textResult(`tool ${name} failed: ${String(err)}`, true)
  }
}

/**
 * Register the retained mind tools (visible + seam) on the extension API. `list_sessions`
 * is included here so the retained tool set mirrors the plan §4.2 list exactly (the 12
 * retained mind tools; mind_complete adds the 13th).
 */
export function registerMindToolDelegates(pi: ExtensionAPI, client: ChannelClient): void {
  const all: RetainedRegistration[] = [
    { definition: { name: 'list_sessions', description: 'List all active CassiCore sessions with their IDs and last activity.', parameters: { type: 'object', properties: {}, required: [] } } },
    ...RETAINED_TOOLS,
    ...SEAM_TOOLS,
  ]

  for (const { definition, seam } of all) {
    const schema = zodFromParamSchema(pi.zod, definition.parameters)
    pi.registerTool({
      name: definition.name,
      label: definition.name,
      description: definition.description,
      parameters: schema,
      hidden: seam ? true : undefined,
      defaultInactive: seam ? true : undefined,
      execute: (_id, params, _signal, _onUpdate, ctx) =>
        delegateTool(client, definition.name, params as Record<string, unknown>, ctx),
    })
  }
}

export { RETAINED_TOOLS, SEAM_TOOLS }
