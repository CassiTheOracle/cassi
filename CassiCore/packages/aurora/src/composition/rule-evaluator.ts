/**
 * B1.3 — pure-function evaluator for InvocationRule edge-trigger logic.
 *
 * Stateless except for the `previouslySatisfied` set the caller passes
 * in. Caller (Aurora.evaluateInvocationRules) maintains that set across
 * ticks; evaluator just computes the rising/falling/sustained edges.
 *
 * Match policy: a rule matches if AT LEAST ONE of its `topicKeywords`
 * appears (case-insensitive substring) in any of the supplied
 * `activeConcepts`. Keywords are AND-free — any keyword satisfies.
 */

import type { InvocationRule, InvocationRuleEvaluation } from './types.js'

export function ruleMatchesActiveConcepts(rule: InvocationRule, activeConcepts: ReadonlyArray<string>): boolean {
  if (rule.topicKeywords.length === 0) return false
  if (activeConcepts.length === 0) return false
  const concepts = activeConcepts.map(c => c.toLowerCase())
  for (const kw of rule.topicKeywords) {
    const lower = kw.toLowerCase()
    if (lower.length === 0) continue
    for (const concept of concepts) {
      if (concept.includes(lower)) return true
    }
  }
  return false
}

/**
 * Evaluate every rule's match state against the active concept set.
 * Returns three lists:
 *  - `fired`: rules whose trigger flipped false→true this tick
 *    (caller invokes the bound composition for each).
 *  - `unfired`: rules whose trigger flipped true→false (caller may
 *    decide whether to deactivate the composition; default is to
 *    leave it running through its TTL countdown).
 *  - `stillSatisfied`: rules whose trigger stayed satisfied since
 *    the previous tick (no re-fire).
 *
 * The `previouslySatisfied` set is mutated in place to reflect the
 * post-tick state — callers can pass the same set across calls.
 */
export function evaluateInvocationRules(
  rules: ReadonlyArray<InvocationRule>,
  activeConcepts: ReadonlyArray<string>,
  previouslySatisfied: Set<string>,
): InvocationRuleEvaluation {
  const fired: string[] = []
  const unfired: string[] = []
  const stillSatisfied: string[] = []
  const nowSatisfied = new Set<string>()

  for (const rule of rules) {
    const matches = ruleMatchesActiveConcepts(rule, activeConcepts)
    const wasSatisfied = previouslySatisfied.has(rule.id)
    if (matches) {
      nowSatisfied.add(rule.id)
      if (wasSatisfied) {
        stillSatisfied.push(rule.id)
      } else {
        fired.push(rule.id)
      }
    } else if (wasSatisfied) {
      unfired.push(rule.id)
    }
  }

  // Sync previouslySatisfied to nowSatisfied for the next tick.
  for (const id of [...previouslySatisfied]) {
    if (!nowSatisfied.has(id)) previouslySatisfied.delete(id)
  }
  for (const id of nowSatisfied) {
    previouslySatisfied.add(id)
  }

  return { fired, unfired, stillSatisfied }
}
