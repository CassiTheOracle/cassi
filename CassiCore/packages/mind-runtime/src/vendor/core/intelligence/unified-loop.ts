/**
 * Unified Intelligence Loop
 *
 * Cross-session background coordinator for all intelligence modules.
 * Runs periodic heartbeat cycles that:
 *  1. Aggregate module health for observability
 *  2. Trigger cross-session consolidation (subconscious, memory)
 *  3. Run memory maintenance (stale KV cleanup, archive compaction)
 *  4. Detect and clean up stale sessions
 *  5. Emit coordination events for downstream consumers
 *
 * This does NOT replace Subconscious per-turn orchestration — it operates
 * at a longer timescale (minutes, not turns) for cross-session concerns.
 *
 * Phase 1+ hooks (outcome tracking, pattern correlation, adaptive behavior)
 * will register as cycle extensions via `addCycleHook()`.
 */

import type { ILogger, IEventBus } from '@cassicore/foundation';
import { isGamingMode } from './gaming-mode.js';


/** Lightweight health probe that any intelligence module can expose */
export interface ModuleHealthProbe {
  readonly name: string;
  /** Is the module operational? */
  isHealthy(): boolean;
  /** Unix timestamp of last meaningful activity (turn processed, consolidation ran, etc.) */
  lastActivityAt(): number;
  /** Optional: structured stats for observability */
  getStats?(): Record<string, unknown>;
}

/** Hook that runs on each background cycle */
export interface CycleHook {
  readonly name: string;
  /** Run every N cycles (1 = every cycle, 3 = every 3rd cycle) */
  readonly cadence: number;
  /** Execute the hook. Return value is logged for observability. */
  execute(cycleNumber: number): Promise<string | void>;
}


export interface UnifiedLoopConfig {
  enabled: boolean;
  /** Interval between background cycles in ms (default: 60s) */
  backgroundIntervalMs: number;
  /** Cycles between cross-session consolidation triggers (default: 5 = every 5 min at 60s interval) */
  consolidationCadence: number;
  /** Cycles between memory maintenance runs (default: 10 = every 10 min at 60s interval) */
  maintenanceCadence: number;
  /** Max age in ms for sessions considered "stale" (default: 30 min) */
  staleSessionThresholdMs: number;
}

export const DEFAULT_UNIFIED_LOOP_CONFIG: UnifiedLoopConfig = {
  enabled: true,
  backgroundIntervalMs: 60_000,
  consolidationCadence: 5,
  maintenanceCadence: 10,
  staleSessionThresholdMs: 30 * 60_000,
};


/** References to intelligence modules that the loop can coordinate */
export interface UnifiedLoopModules {
  /** Subconscious — for cross-session consolidation triggers */
  subconscious?: {
    persistMentalModels?(): Promise<void>;
    getStats?(): Record<string, unknown>;
  };
  /** Memory — for maintenance, stale KV cleanup */
  memory?: {
    kv_get?<T>(key: string): Promise<T | undefined>;
    kv_set?(key: string, value: unknown): Promise<void>;
    cleanup?(): Promise<void>;
    getStats?(): Record<string, unknown>;
  };
  /** REMOVED: optimizer — OptimizerModule deleted */
  /** All intelligence modules for health aggregation */
  all?: Array<{ name: string; priority: number }>;
}


export class UnifiedIntelligenceLoop {
  private readonly logger: ILogger;
  private readonly bus: IEventBus;
  private config: UnifiedLoopConfig;

  // Module references (set after construction via wire())
  private modules: UnifiedLoopModules = {};
  private healthProbes: ModuleHealthProbe[] = [];
  private cycleHooks: CycleHook[] = [];

  // State
  private backgroundTimer?: ReturnType<typeof setInterval>;
  private running = false;
  private cycleNumber = 0;
  private startedAt = 0;
  private lastCycleAt = 0;
  private lastCycleDurationMs = 0;
  private consecutiveErrors = 0;
  private readonly MAX_CONSECUTIVE_ERRORS = 5;
  /** Max time for any single cycle step (consolidation, maintenance, hook) */
  private readonly CYCLE_STEP_TIMEOUT_MS = 30_000; // 30s

  // Optional getters wired by daemon for heartbeat enrichment
  private activeRequestsGetter?: () => number;
  private activeSessionsGetter?: () => number;

  constructor(
    logger: ILogger,
    eventBus: IEventBus,
    config?: Partial<UnifiedLoopConfig>,
  ) {
    this.logger = logger.child?.('unified-loop') ?? logger;
    this.bus = eventBus;
    this.config = {
      ...DEFAULT_UNIFIED_LOOP_CONFIG,
      ...config,
    };
  }


  /**
   * Wire module references for background coordination.
   * Called by daemon after all modules are created.
   */
  wire(modules: UnifiedLoopModules): void {
    this.modules = modules;
    this.logger.info('Modules wired', {
      subconscious: !!modules.subconscious,
      memory: !!modules.memory,
      moduleCount: modules.all?.length ?? 0,
    });
  }

  /**
   * Set a getter that returns the number of in-flight provider requests.
   * Used to enrich intelligence:heartbeat with activeRequests.
   */
  setActiveRequestsGetter(getter: () => number): void {
    this.activeRequestsGetter = getter;
  }

  /**
   * Set a getter that returns the number of active sessions.
   * Used to enrich intelligence:heartbeat with activeSessions.
   */
  setActiveSessionsGetter(getter: () => number): void {
    this.activeSessionsGetter = getter;
  }

  /**
   * Register a health probe for a module.
   * Probes are polled each cycle for health aggregation.
   */
  addHealthProbe(probe: ModuleHealthProbe): void {
    this.healthProbes.push(probe);
    this.logger.debug('Health probe registered', { module: probe.name });
  }

  /**
   * Register a cycle hook.
   * Hooks run during the background cycle at their configured cadence.
   * This is the extension point for Phase 1-4 features.
   */
  addCycleHook(hook: CycleHook): void {
    this.cycleHooks.push(hook);
    this.logger.info('Cycle hook registered', { name: hook.name, cadence: hook.cadence });
  }


  async start(): Promise<void> {
    if (this.running || !this.config.enabled) {
      return;
    }

    this.running = true;
    this.startedAt = Date.now();
    this.cycleNumber = 0;
    this.consecutiveErrors = 0;

    this.logger.info('Starting unified intelligence loop', {
      intervalMs: this.config.backgroundIntervalMs,
      consolidationCadence: this.config.consolidationCadence,
      maintenanceCadence: this.config.maintenanceCadence,
      hookCount: this.cycleHooks.length,
      probeCount: this.healthProbes.length,
    });

    // Listen for daemon shutdown
    try {
      (this.bus as any).on('daemon:shutdown', () => {
        void this.stop('daemon-shutdown');
      });
    } catch (err) {
      this.logger.warn('Failed to register daemon:shutdown listener', { error: String(err) });
    }

    // Start background timer
    this.backgroundTimer = setInterval(() => {
      if (this.running) {
        void this.runCycle();
      }
    }, this.config.backgroundIntervalMs);

    // Unref so the timer doesn't prevent process exit
    try { (this.backgroundTimer as any).unref?.(); } catch { /* ignore */ }

    // Emit started event
    try {
      (this.bus as any).emit({
        type: 'intelligence:loop:started',
        intervalMs: this.config.backgroundIntervalMs,
        timestamp: new Date(),
      });
    } catch { /* ignore if event type not registered */ }

    this.logger.info('Unified intelligence active');
  }

  async stop(reason = 'manual'): Promise<void> {
    if (!this.running) return;

    this.running = false;
    this.logger.info('Stopping unified intelligence loop', { reason });

    if (this.backgroundTimer) {
      clearInterval(this.backgroundTimer);
      this.backgroundTimer = undefined;
    }

    // Emit stopped event
    try {
      (this.bus as any).emit({
        type: 'intelligence:loop:stopped',
        reason,
        cyclesCompleted: this.cycleNumber,
        timestamp: new Date(),
      });
    } catch { /* ignore */ }

    this.logger.info('Stopped', {
      cyclesCompleted: this.cycleNumber,
      uptimeMs: Date.now() - this.startedAt,
    });
  }


  /** Wrap an async operation with a timeout to prevent cycle hangs */
  private async withTimeout<T>(label: string, fn: () => Promise<T>): Promise<T> {
    return Promise.race([
      fn(),
      new Promise<never>((_, reject) =>
        setTimeout(
          () => reject(new Error(`Cycle step "${label}" timed out after ${this.CYCLE_STEP_TIMEOUT_MS}ms`)),
          this.CYCLE_STEP_TIMEOUT_MS,
        )
      ),
    ]);
  }

  private async runCycle(): Promise<void> {
    // WHY: Skip the entire cycle during gaming mode. The unified loop does
    // health aggregation, consolidation, maintenance, and session cleanup —
    // all of which involve SQLite reads/writes and event bus chatter that
    // can cause micro-stutters.
    if (isGamingMode()) {
      this.logger.debug('Gaming mode active — skipping intelligence cycle');
      return;
    }

    const cycleStart = Date.now();
    this.cycleNumber++;

    try {
      this.logger.debug('Running background cycle', { cycle: this.cycleNumber });

      // 1. Aggregate module health
      const moduleStatuses = this.aggregateHealth();

      // 2. Emit heartbeat event (enriched with request/session context when available)
      try {
        (this.bus as any).emit({
          type: 'intelligence:heartbeat',
          cycleNumber: this.cycleNumber,
          uptimeMs: cycleStart - this.startedAt,
          moduleStatuses,
          activeRequests: this.activeRequestsGetter?.() ?? undefined,
          activeSessions: this.activeSessionsGetter?.() ?? undefined,
          timestamp: new Date(),
        });
      } catch { /* ignore */ }

      // 3. Cross-session consolidation (at configured cadence)
      if (this.cycleNumber % this.config.consolidationCadence === 0) {
        await this.withTimeout('consolidation', () => this.runConsolidation());
      }

      // 4. Memory maintenance (at configured cadence)
      if (this.cycleNumber % this.config.maintenanceCadence === 0) {
        await this.withTimeout('maintenance', () => this.runMaintenance());
      }

      // 5. Run registered cycle hooks
      await this.withTimeout('hooks', () => this.runHooks());

      // Reset error counter on success
      this.consecutiveErrors = 0;
      this.lastCycleAt = cycleStart;
      this.lastCycleDurationMs = Date.now() - cycleStart;

    } catch (err) {
      this.consecutiveErrors++;
      this.logger.warn('Background cycle failed', {
        cycle: this.cycleNumber,
        error: String(err),
        consecutiveErrors: this.consecutiveErrors,
      });

      // Circuit breaker: if too many consecutive errors, increase interval
      if (this.consecutiveErrors >= this.MAX_CONSECUTIVE_ERRORS) {
        this.logger.error('Too many consecutive errors — backing off', {
          errors: this.consecutiveErrors,
          newIntervalMs: this.config.backgroundIntervalMs * 2,
        });
        // Double the interval (capped at 10 min)
        const newInterval = Math.min(this.config.backgroundIntervalMs * 2, 10 * 60_000);
        this.updateConfig({ backgroundIntervalMs: newInterval });
        this.consecutiveErrors = 0;
      }
    }
  }


  private aggregateHealth(): Array<{ name: string; healthy: boolean; lastActivity?: number }> {
    const statuses: Array<{ name: string; healthy: boolean; lastActivity?: number }> = [];

    // Poll registered health probes
    for (const probe of this.healthProbes) {
      try {
        statuses.push({
          name: probe.name,
          healthy: probe.isHealthy(),
          lastActivity: probe.lastActivityAt(),
        });
      } catch (err) {
        statuses.push({
          name: probe.name,
          healthy: false,
        });
        this.logger.warn('Health probe failed', { module: probe.name, error: String(err) });
      }
    }

    // If no probes registered, report on known modules
    if (statuses.length === 0 && this.modules.all) {
      for (const mod of this.modules.all) {
        statuses.push({
          name: mod.name,
          healthy: true, // Assume healthy if no probe — we'll improve this in Phase 4
        });
      }
    }

    return statuses;
  }


  private async runConsolidation(): Promise<void> {
    this.logger.debug('Running cross-session consolidation');

    try {
      (this.bus as any).emit({
        type: 'intelligence:maintenance',
        task: 'consolidation',
        detail: `cycle ${this.cycleNumber}`,
        timestamp: new Date(),
      });
    } catch { /* ignore */ }

    // Trigger subconscious mental model persistence
    if (this.modules.subconscious?.persistMentalModels) {
      try {
        await this.modules.subconscious.persistMentalModels();
        this.logger.debug('Subconscious mental models persisted');
      } catch (err) {
        this.logger.warn('Subconscious consolidation failed', { error: String(err) });
      }
    }

    // Persist loop state to memory KV (survives daemon restarts)
    if (this.modules.memory?.kv_set) {
      try {
        await this.modules.memory.kv_set('unified-loop:state', {
          cycleNumber: this.cycleNumber,
          lastCycleAt: this.lastCycleAt,
          startedAt: this.startedAt,
          consecutiveErrors: this.consecutiveErrors,
        });
      } catch (err) {
        this.logger.debug('Failed to persist loop state', { error: String(err) });
      }
    }
  }


  private async runMaintenance(): Promise<void> {
    this.logger.debug('Running memory maintenance');

    try {
      (this.bus as any).emit({
        type: 'intelligence:maintenance',
        task: 'memory-maintenance',
        detail: `cycle ${this.cycleNumber}`,
        timestamp: new Date(),
      });
    } catch { /* ignore */ }

    // Trigger memory cleanup if available
    if (this.modules.memory?.cleanup) {
      try {
        await this.modules.memory.cleanup();
        this.logger.debug('Memory cleanup completed');
      } catch (err) {
        this.logger.warn('Memory cleanup failed', { error: String(err) });
      }
    }
  }


  private async runHooks(): Promise<void> {
    for (const hook of this.cycleHooks) {
      if (this.cycleNumber % hook.cadence !== 0) continue;

      try {
        const result = await hook.execute(this.cycleNumber);
        if (result) {
          this.logger.debug('Hook completed', { name: hook.name, result });
        }
      } catch (err) {
        this.logger.warn('Hook failed', { name: hook.name, error: String(err) });
      }
    }
  }


  getStatus(): {
    running: boolean;
    config: UnifiedLoopConfig;
    cycleNumber: number;
    uptimeMs: number;
    lastCycleAt: number;
    lastCycleDurationMs: number;
    consecutiveErrors: number;
    hookCount: number;
    probeCount: number;
  } {
    return {
      running: this.running,
      config: { ...this.config },
      cycleNumber: this.cycleNumber,
      uptimeMs: this.running ? Date.now() - this.startedAt : 0,
      lastCycleAt: this.lastCycleAt,
      lastCycleDurationMs: this.lastCycleDurationMs,
      consecutiveErrors: this.consecutiveErrors,
      hookCount: this.cycleHooks.length,
      probeCount: this.healthProbes.length,
    };
  }

  updateConfig(config: Partial<UnifiedLoopConfig>): void {
    const oldInterval = this.config.backgroundIntervalMs;
    this.config = { ...this.config, ...config };

    // If interval changed and we're running, restart the timer
    if (config.backgroundIntervalMs && config.backgroundIntervalMs !== oldInterval && this.running) {
      if (this.backgroundTimer) {
        clearInterval(this.backgroundTimer);
      }
      this.backgroundTimer = setInterval(() => {
        if (this.running) {
          void this.runCycle();
        }
      }, this.config.backgroundIntervalMs);
      try { (this.backgroundTimer as any).unref?.(); } catch { /* ignore */ }

      this.logger.info('Timer interval updated', {
        oldMs: oldInterval,
        newMs: this.config.backgroundIntervalMs,
      });
    }

    this.logger.info('Configuration updated', { config: this.config });
  }
}


/**
 * @dep callers: unified-loop.test.ts (tests/unified-loop.test.ts), start (core/daemon.ts)
 * @dep module: Intelligence
 * @dep risk: LOW | 2 callers, 0 flows, 1 module
 */

export function createUnifiedIntelligenceLoop(
  logger: ILogger,
  eventBus: IEventBus,
  config?: Partial<UnifiedLoopConfig>,
): UnifiedIntelligenceLoop {
  return new UnifiedIntelligenceLoop(logger, eventBus, config);
}

export default UnifiedIntelligenceLoop;
