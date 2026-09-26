import { randomBytes } from 'node:crypto';

/**
 * Generate a short alphanumeric ID.
 * Defaults to 8 characters which provides ~218 trillion combinations (36^8).
 * More than enough for thousands of sessions while staying very readable.
 * @dep callers: start (core/daemon.ts), getOrCreate (core/session-manager.ts), createContinuityMarker (core/intelligence/branching-conversation/manager.ts), createDecisionPoint (core/intelligence/branching-conversation/manager.ts), addTurn (core/intelligence/branching-conversation/manager.ts) [+8]
 * @dep flows: HandleDialecticControlRoutes → GenerateShortId (5/5)
 * @dep module: Branching-conversation
 * @dep risk: CRITICAL | 13 callers, 1 flow, 1 module
 */
export function generateShortId(length = 8): string {
  return randomBytes(Math.ceil(length / 2))
    .toString('hex')
    .slice(0, length);
}

/**
 * Generate a human-friendly timestamp-based ID.
 * Example: 240225-abcd
 * @dep callers: addChild (core/intelligence/goal-tree.ts), createRoot (core/intelligence/goal-tree.ts), spawnDialecticCassis (core/intelligence/multi-agent/index.ts), spawnSerenaSwarm (core/intelligence/multi-agent/index.ts), createTask (core/intelligence/multi-agent/index.ts) [+1]
 * @dep calls: generateShortId, toISOString
 * @dep flows: HandleDialecticControlRoutes → GenerateShortId (4/5)
 * @dep module: Multi-agent
 * @dep risk: MEDIUM | 6 callers, 1 flow, 1 module
 */
export function generateReadableId(prefix?: string): string {
  const date = new Date().toISOString().slice(2, 10).replace(/-/g, '');
  const suffix = generateShortId(4);
  const id = `${date}-${suffix}`;
  return prefix ? `${prefix}-${id}` : id;
}
