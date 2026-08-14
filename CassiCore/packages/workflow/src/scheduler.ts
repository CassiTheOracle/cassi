/**
 * WorkflowScheduler — manages trigger-based automatic workflow execution.
 *
 * Supports four trigger kinds:
 *   interval — fires every N ms using setInterval
 *   cron     — fires on cron schedule (minute-level, lightweight parser)
 *   event    — fires when a CassiCore event matches a pattern
 *   once     — fires once at a specific time using setTimeout
 *
 * The scheduler:
 *   1. Registers triggers (in memory + optional persistence)
 *   2. Activates enabled triggers (sets timers, subscribes to events)
 *   3. When a trigger fires: executes the associated workflow via the engine
 *   4. Tracks fire count, last/next fire time, errors
 *   5. Automatically deactivates exhausted triggers (maxFires reached)
 */

import type { ILogger, IEventBus } from '@cassicore/foundation'
import type {
  WorkflowTrigger,
  IntervalTrigger,
  CronTrigger,
  EventTrigger,
  OnceTrigger,
  TriggerState,
  WorkflowDefinition,
  IWorkflowTriggerStore,
} from '@cassicore/foundation'
import type { WorkflowEngine } from './engine.js'

export interface WorkflowSchedulerConfig {
  logger: ILogger
  eventBus: IEventBus
  engine: WorkflowEngine
  getDefinition: (workflowId: string) => WorkflowDefinition | undefined
  /** Optional persistence store. When provided, triggers and state survive restarts. */
  store?: IWorkflowTriggerStore
}

interface ActiveTrigger {
  trigger: WorkflowTrigger
  state: TriggerState
  cleanup?: () => void
}

export class WorkflowScheduler {
  private readonly logger: ILogger
  private readonly eventBus: IEventBus
  private readonly engine: WorkflowEngine
  private readonly getDefinition: (workflowId: string) => WorkflowDefinition | undefined
  private readonly store?: IWorkflowTriggerStore

  private readonly triggers = new Map<string, ActiveTrigger>()
  private started = false

  constructor(config: WorkflowSchedulerConfig) {
    this.logger = config.logger.child('workflow-scheduler')
    this.eventBus = config.eventBus
    this.engine = config.engine
    this.getDefinition = config.getDefinition
    this.store = config.store
  }

  /** Register a trigger. If the scheduler is started, activates it immediately. */
  register(trigger: WorkflowTrigger): void {
    const state: TriggerState = {
      triggerId: trigger.id,
      fireCount: 0,
      status: trigger.enabled ? 'active' : 'paused',
    }

    const active: ActiveTrigger = { trigger, state }
    this.triggers.set(trigger.id, active)

    this.persistTrigger(trigger)
    this.persistState(state)

    if (this.started && trigger.enabled) {
      this.activate(active)
    }

    this.logger.debug('Trigger registered', {
      id: trigger.id,
      kind: trigger.kind,
      workflowId: trigger.workflowId,
      enabled: trigger.enabled,
    })
  }

  /** Remove a trigger. Deactivates it first if active. */
  unregister(triggerId: string): boolean {
    const active = this.triggers.get(triggerId)
    if (!active) return false

    this.deactivate(active)
    this.triggers.delete(triggerId)
    this.deleteTriggerFromStore(triggerId)
    return true
  }

  /** Enable a trigger. Activates it if the scheduler is started. */
  enable(triggerId: string): boolean {
    const active = this.triggers.get(triggerId)
    if (!active) return false

    active.trigger = { ...active.trigger, enabled: true }
    active.state.status = 'active'

    this.persistTrigger(active.trigger)
    this.persistState(active.state)

    if (this.started) {
      this.activate(active)
    }
    return true
  }

  /** Disable a trigger. Deactivates its timer/subscription. */
  disable(triggerId: string): boolean {
    const active = this.triggers.get(triggerId)
    if (!active) return false

    this.deactivate(active)
    active.trigger = { ...active.trigger, enabled: false }
    active.state.status = 'paused'

    this.persistTrigger(active.trigger)
    this.persistState(active.state)
    return true
  }

  /** Start the scheduler — loads persisted triggers, then activates all enabled ones. */
  start(): void {
    if (this.started) return
    this.started = true

    this.loadFromStore()

    for (const active of this.triggers.values()) {
      if (active.trigger.enabled && active.state.status !== 'exhausted') {
        this.activate(active)
      }
    }

    this.logger.info('Scheduler started', { triggerCount: this.triggers.size })
  }

  /** Stop the scheduler — deactivates all triggers. */
  stop(): void {
    if (!this.started) return
    this.started = false

    for (const active of this.triggers.values()) {
      this.deactivate(active)
    }

    this.logger.info('Scheduler stopped')
  }

  /** Get trigger state by id. */
  getState(triggerId: string): TriggerState | undefined {
    return this.triggers.get(triggerId)?.state
  }

  /** Get trigger by id. */
  getTrigger(triggerId: string): WorkflowTrigger | undefined {
    return this.triggers.get(triggerId)?.trigger
  }

  /** List all triggers with their states. */
  listTriggers(): Array<{ trigger: WorkflowTrigger; state: TriggerState }> {
    return [...this.triggers.values()].map((a) => ({
      trigger: a.trigger,
      state: a.state,
    }))
  }

  /** Whether the scheduler is running. */
  get isStarted(): boolean {
    return this.started
  }

  // Activation / deactivation

  private activate(active: ActiveTrigger): void {
    // Deactivate first to avoid double activation
    this.deactivate(active)

    const { trigger } = active

    switch (trigger.kind) {
      case 'interval':
        this.activateInterval(active, trigger)
        break
      case 'cron':
        this.activateCron(active, trigger)
        break
      case 'event':
        this.activateEvent(active, trigger)
        break
      case 'once':
        this.activateOnce(active, trigger)
        break
    }
  }

  private deactivate(active: ActiveTrigger): void {
    if (active.cleanup) {
      active.cleanup()
      active.cleanup = undefined
    }
  }

  private activateInterval(active: ActiveTrigger, trigger: IntervalTrigger): void {
    const timer = setInterval(() => {
      void this.fire(active)
    }, trigger.intervalMs)
    // WHY: unref so the timer doesn't prevent Node from exiting
    if (typeof timer === 'object' && 'unref' in timer) timer.unref()

    active.state.nextFireAt = new Date(Date.now() + trigger.intervalMs).toISOString()
    active.cleanup = () => clearInterval(timer)
  }

  private activateCron(active: ActiveTrigger, trigger: CronTrigger): void {
    const timer = setInterval(() => {
      if (this.cronMatches(trigger.cronExpression, new Date())) {
        void this.fire(active)
      }
    }, 60_000)
    if (typeof timer === 'object' && 'unref' in timer) timer.unref()

    active.cleanup = () => clearInterval(timer)
  }

  private activateEvent(active: ActiveTrigger, trigger: EventTrigger): void {
    const unsubscribe = this.eventBus.on('*' as any, (event: any) => {
      const eventType = event?.type as string | undefined
      if (!eventType) return

      if (this.eventMatches(trigger.eventPattern, eventType)) {
        // Check optional filter
        if (trigger.eventFilter && !trigger.eventFilter(event)) {
          return
        }

        // WHY: Fire-and-forget to avoid blocking the event bus listener.
        // Errors are caught inside fire() and logged.
        void this.fire(active, event)
      }
    })

    active.cleanup = typeof unsubscribe === 'function' ? unsubscribe : undefined
  }

  private activateOnce(active: ActiveTrigger, trigger: OnceTrigger): void {
    const fireTime = new Date(trigger.fireAt).getTime()
    const delay = Math.max(0, fireTime - Date.now())

    const timer = setTimeout(() => {
      void this.fire(active)
    }, delay)
    if (typeof timer === 'object' && 'unref' in timer) timer.unref()

    active.state.nextFireAt = trigger.fireAt
    active.cleanup = () => clearTimeout(timer)
  }

  // WHY: Tracks trigger IDs that are currently mid-execution.
  // Prevents re-entrancy when a workflow's lifecycle events match the same
  // trigger pattern. This is cleared in the finally block after execution.
  private firing = new Set<string>()

  // Trigger firing

  private async fire(active: ActiveTrigger, eventData?: unknown): Promise<void> {
    const { trigger, state } = active

    // Re-entrancy guard for event triggers only — interval/cron/once won't
    // re-enter because they use timers, not event bus listeners.
    if (trigger.kind === 'event' && this.firing.has(trigger.id)) return

    if (trigger.kind === 'event') {
      this.firing.add(trigger.id)
    }

    // Check max fires
    if (trigger.maxFires && trigger.maxFires > 0 && state.fireCount >= trigger.maxFires) {
      this.deactivate(active)
      state.status = 'exhausted'
      this.persistState(state)
      this.firing.delete(trigger.id)
      return
    }

    // Find the workflow definition
    const definition = this.getDefinition(trigger.workflowId)
    if (!definition) {
      state.status = 'error'
      state.lastError = `Workflow "${trigger.workflowId}" not found in registry`
      this.persistState(state)
      this.logger.warn('Trigger fire failed: workflow not found', {
        triggerId: trigger.id,
        workflowId: trigger.workflowId,
      })
      this.firing.delete(trigger.id)
      return
    }

    state.fireCount++
    state.lastFiredAt = new Date().toISOString()

    this.logger.info('Trigger fired', {
      triggerId: trigger.id,
      kind: trigger.kind,
      workflowId: trigger.workflowId,
      fireCount: state.fireCount,
    })

    try {
      const input = eventData ?? trigger.input ?? null
      await this.engine.execute(definition, input)
    } catch (err) {
      state.lastError = String(err)
      this.logger.error('Trigger execution failed', {
        triggerId: trigger.id,
        error: String(err),
      })
    } finally {
      this.firing.delete(trigger.id)
    }

    // Update next fire time for interval triggers
    if (trigger.kind === 'interval') {
      state.nextFireAt = new Date(Date.now() + trigger.intervalMs).toISOString()
    }

    // Check if exhausted after firing
    if (trigger.maxFires && trigger.maxFires > 0 && state.fireCount >= trigger.maxFires) {
      this.deactivate(active)
      state.status = 'exhausted'
    }

    this.persistState(state)
    this.firing.delete(trigger.id)
  }

  // Persistence helpers — no-ops when store is not configured

  /** Load all persisted triggers and their states into memory. */
  private loadFromStore(): void {
    if (!this.store) return

    try {
      const triggers = this.store.listTriggers({ limit: 1000 })
      let loaded = 0

      for (const trigger of triggers) {
        // WHY: Skip triggers that are already registered in memory.
        // register() is called before start() in some flows, so
        // the in-memory version takes precedence.
        if (this.triggers.has(trigger.id)) continue

        const storedState = this.store.loadState(trigger.id)
        const state: TriggerState = storedState ?? {
          triggerId: trigger.id,
          fireCount: 0,
          status: trigger.enabled ? 'active' : 'paused',
        }

        this.triggers.set(trigger.id, { trigger, state })
        loaded++
      }

      if (loaded > 0) {
        this.logger.info('Loaded triggers from store', { loaded, total: this.triggers.size })
      }
    } catch (err) {
      this.logger.error('Failed to load triggers from store', { error: String(err) })
    }
  }

  private persistTrigger(trigger: WorkflowTrigger): void {
    if (!this.store) return
    try {
      this.store.saveTrigger(trigger)
    } catch (err) {
      this.logger.error('Failed to persist trigger', { triggerId: trigger.id, error: String(err) })
    }
  }

  private persistState(state: TriggerState): void {
    if (!this.store) return
    try {
      this.store.saveState(state)
    } catch (err) {
      this.logger.error('Failed to persist trigger state', { triggerId: state.triggerId, error: String(err) })
    }
  }

  private deleteTriggerFromStore(triggerId: string): void {
    if (!this.store) return
    try {
      this.store.deleteTrigger(triggerId)
    } catch (err) {
      this.logger.error('Failed to delete trigger from store', { triggerId, error: String(err) })
    }
  }

  // Cron matching (lightweight — no external dependency)

  /** Match a 5-field cron expression against a date. */
  cronMatches(expression: string, date: Date): boolean {
    const fields = expression.trim().split(/\s+/)
    if (fields.length !== 5) return false

    const minute = date.getMinutes()
    const hour = date.getHours()
    const dayOfMonth = date.getDate()
    const month = date.getMonth() + 1
    const dayOfWeek = date.getDay()

    return (
      this.fieldMatches(fields[0], minute, 0, 59) &&
      this.fieldMatches(fields[1], hour, 0, 23) &&
      this.fieldMatches(fields[2], dayOfMonth, 1, 31) &&
      this.fieldMatches(fields[3], month, 1, 12) &&
      this.fieldMatches(fields[4], dayOfWeek, 0, 6)
    )
  }

  /** Match a single cron field against a value. */
  private fieldMatches(field: string, value: number, min: number, max: number): boolean {
    if (field === '*') return true

    // Handle step: */N
    if (field.startsWith('*/')) {
      const step = parseInt(field.slice(2), 10)
      return !isNaN(step) && step > 0 && value % step === 0
    }

    // Handle range: N-M
    if (field.includes('-')) {
      const [lo, hi] = field.split('-').map(Number)
      return value >= lo && value <= hi
    }

    // Handle list: N,M,P
    if (field.includes(',')) {
      const values = field.split(',').map(Number)
      return values.includes(value)
    }

    // Single value
    const num = parseInt(field, 10)
    return num === value
  }

  /** Match an event type against a pattern (supports * wildcard). */
  private eventMatches(pattern: string, eventType: string): boolean {
    if (pattern === '*') return true
    if (pattern === eventType) return true

    // Simple glob: workflow:* matches workflow:started, workflow:completed, etc.
    if (pattern.endsWith('*')) {
      const prefix = pattern.slice(0, -1)
      return eventType.startsWith(prefix)
    }

    return false
  }
}
