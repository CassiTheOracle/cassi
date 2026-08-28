// WHY: OrchestrationBus intentionally creates a private EventBus instance for internal event coordination.
// This isolates subagent lifecycle events (registered, updated, completed, stalled) from the global bus
// to prevent noise in the main event stream. The private bus is only used for internal orchestration
// callbacks (e.g. notifying listeners within the orchestration system). If you need global bus access,
// pass the global EventBus separately or emit events through the main bus.

import fs from 'node:fs/promises'
import os from 'node:os'
import path from 'node:path'

import { EventBus } from '@cassicore/events'

import type { ILogger } from '@cassicore/foundation'

export interface SubagentRecord {
  id: string;
  label: string;
  task: string;
  status: 'running' | 'completed' | 'failed' | 'stalled';
  spawnedAt: number;
  completedAt?: number;
  parentId?: string;
  result?: string;
  progress?: string;
}

export interface IOrchestrationBus {
  register(agent: Omit<SubagentRecord, 'spawnedAt'>): void;
  update(id: string, patch: Partial<SubagentRecord>): void;
  list(status?: SubagentRecord['status']): SubagentRecord[];
  get(id: string): SubagentRecord | undefined;
  complete(id: string, result: string): void;
  detectStalled(thresholdMs?: number): SubagentRecord[];
  on(event: 'registered' | 'updated' | 'completed' | 'stalled', cb: (agent: SubagentRecord) => void): () => void;
  persist(): Promise<void>;
  load(): Promise<void>;
  getSummary(): string;
  destroy(): void;
}

const DEFAULT_PATH = path.join(os.homedir(), '.cassicore', 'orchestration-state.json')

export function createOrchestrationBus(logger: ILogger): IOrchestrationBus {
  const store = new Map<string, SubagentRecord>()
  const eb = new EventBus()
  let persistTimer: NodeJS.Timeout | undefined
  let stalledInterval: NodeJS.Timeout | undefined

  async function persist(): Promise<void> {
    const dir = path.dirname(DEFAULT_PATH)
    await fs.mkdir(dir, { recursive: true })
    const arr = Array.from(store.values())
    await fs.writeFile(DEFAULT_PATH, JSON.stringify(arr, null, 2), 'utf8')
    logger.debug('state persisted')
  }

  async function load(): Promise<void> {
    try {
      const data = await fs.readFile(DEFAULT_PATH, 'utf8')
      const arr = JSON.parse(data) as SubagentRecord[]
      for (const a of arr) store.set(a.id, a)
      logger.debug('state loaded')
    } catch (err) {
      // ignore missing file
    }
  }

  function schedulePersist() {
    if (persistTimer) clearTimeout(persistTimer)
    persistTimer = setTimeout(() => { void persist() }, 2000)
    try { (persistTimer as any).unref?.() } catch {}
  }

  // start stalled checker
  stalledInterval = setInterval(() => {
    try { detectStalled() } catch (err) { logger.warn('stalled detection error') }
  }, 60 * 1000)
  try { stalledInterval.unref?.() } catch {}

  function register(agent: Omit<SubagentRecord, 'spawnedAt'>) {
    const rec: SubagentRecord = { ...agent, spawnedAt: Date.now() }
    store.set(rec.id, rec)
    schedulePersist()
    eb.emit({ type: 'registered', payload: rec } as any)
  }

  function update(id: string, patch: Partial<SubagentRecord>) {
    const cur = store.get(id)
    if (!cur) return
    const merged = { ...cur, ...patch }
    store.set(id, merged)
    schedulePersist()
    eb.emit({ type: 'updated', payload: merged } as any)
  }

  function list(status?: SubagentRecord['status']) {
    const arr = Array.from(store.values())
    return status ? arr.filter((a) => a.status === status) : arr
  }

  function get(id: string) { return store.get(id) }

  function complete(id: string, result: string) {
    const cur = store.get(id)
    if (!cur) return
    cur.status = 'completed'
    cur.completedAt = Date.now()
    cur.result = result.slice(0, 500)
    store.set(id, cur)
    schedulePersist()
    eb.emit({ type: 'completed', payload: cur } as any)
  }

  function detectStalled(thresholdMs = 5 * 60 * 1000) {
    const now = Date.now()
    const stalled: SubagentRecord[] = []
    for (const a of store.values()) {
      if (a.status === 'running') {
        const last = a.completedAt ?? a.spawnedAt
        if (now - last > thresholdMs) {
          a.status = 'stalled'
          store.set(a.id, a)
          stalled.push(a)
          eb.emit({ type: 'stalled', payload: a } as any)
        }
      }
    }
    if (stalled.length) schedulePersist()
    return stalled
  }

  function on(event: 'registered' | 'updated' | 'completed' | 'stalled', cb: (agent: SubagentRecord) => void) {
    const wrapped = (e: any) => cb(e.payload as SubagentRecord)
    return eb.on(event as any, wrapped as any)
  }

  function destroy() {
    if (stalledInterval) {
      clearInterval(stalledInterval)
      stalledInterval = undefined
    }
    if (persistTimer) {
      clearTimeout(persistTimer)
      persistTimer = undefined
    }
  }

  function getSummary() {
    const counts = { running: 0, completed: 0, failed: 0, stalled: 0 }
    for (const a of store.values()) counts[a.status]++
    return `${counts.running} running, ${counts.completed} completed, ${counts.failed} failed, ${counts.stalled} stalled`
  }

  return { register, update, list, get, complete, detectStalled, on, persist, load, getSummary, destroy }
}
