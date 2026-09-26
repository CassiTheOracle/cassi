/**
 * tool-filter.ts — Authority asymmetry registry for Reverie/Primary/Pineal.
 *
 * Reverie can rethink user-model and promote engrams; primary cannot.
 * Primary can read everything and append/replace ordinary laminae.
 * Pineal-owned (read-only) laminae are off-limits to all but Pineal itself.
 *
 * This is enforced at the LaminaStore level via owner+ownerExclusive+readOnly.
 * The filter here documents and validates "intended" agent capabilities so that
 * Reverie's structured output can be rejected before any side effects happen.
 */

export type LaminaAction = 'read' | 'create' | 'append' | 'replace' | 'rethink'
export type MnemicAction = 'read' | 'store' | 'promote' | 'demote'

export interface AgentAuthority {
  agentId: string
  /** Lamina labels this agent has exclusive rethink rights to. */
  exclusiveRethink: string[]
  /** Mnemic actions this agent is allowed to perform. */
  mnemicActions: MnemicAction[]
  /** Labels this agent is forbidden from touching at all. */
  forbiddenLabels: string[]
}

const PRIMARY: AgentAuthority = {
  agentId: 'primary',
  exclusiveRethink: ['active-task', 'open-hypotheses', 'session-decisions'],
  mnemicActions: ['read', 'store'],
  forbiddenLabels: [], // primary may read pineal:* but cannot mutate (enforced by readOnly)
}

const REVERIE: AgentAuthority = {
  agentId: 'reverie',
  exclusiveRethink: ['user-model', 'active-task'],
  mnemicActions: ['read', 'store', 'promote'],
  forbiddenLabels: ['pineal:identity', 'pineal:wisdom', 'pineal:philosophy'],
}

const MEDITATION: AgentAuthority = {
  agentId: 'meditation',
  exclusiveRethink: [],
  mnemicActions: ['read', 'store', 'promote', 'demote'],
  forbiddenLabels: ['pineal:identity', 'pineal:wisdom', 'pineal:philosophy'],
}

const HELIX_PARENT: AgentAuthority = {
  agentId: 'helix-parent',
  exclusiveRethink: [],
  mnemicActions: ['read', 'store'],
  forbiddenLabels: [],
}

const PINEAL: AgentAuthority = {
  agentId: 'pineal',
  exclusiveRethink: ['pineal:identity', 'pineal:wisdom', 'pineal:philosophy'],
  mnemicActions: ['read', 'store'],
  forbiddenLabels: [],
}

const ALL = [PRIMARY, REVERIE, MEDITATION, HELIX_PARENT, PINEAL]

export class ToolFilterRegistry {
  private byAgent = new Map<string, AgentAuthority>(ALL.map(a => [a.agentId, a]))

  get(agentId: string): AgentAuthority | undefined {
    return this.byAgent.get(agentId)
  }

  register(authority: AgentAuthority): void {
    this.byAgent.set(authority.agentId, authority)
  }

  /**
   * Decide whether an agent may perform a lamina action on a label.
   * Returns null on allow, or a short denial reason string.
   */
  checkLamina(agentId: string, action: LaminaAction, label: string): string | null {
    const auth = this.byAgent.get(agentId)
    if (!auth) return `unknown agent '${agentId}'`
    if (auth.forbiddenLabels.includes(label)) return `agent '${agentId}' forbidden from label '${label}'`
    if (action === 'rethink') {
      // If any agent claims exclusive rethink on this label, only that agent may rethink
      const claimers = ALL.filter(a => a.exclusiveRethink.includes(label))
      if (claimers.length > 0 && !claimers.some(a => a.agentId === agentId)) {
        return `rethink on '${label}' is exclusive to '${claimers[0].agentId}'`
      }
    }
    return null
  }

  /** Decide whether an agent may perform a mnemic action. */
  checkMnemic(agentId: string, action: MnemicAction): string | null {
    const auth = this.byAgent.get(agentId)
    if (!auth) return `unknown agent '${agentId}'`
    if (!auth.mnemicActions.includes(action)) {
      return `agent '${agentId}' not allowed to ${action} mnemic`
    }
    return null
  }
}

export const DEFAULT_TOOL_FILTER = new ToolFilterRegistry()
