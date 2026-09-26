/**
 * HOST-WIRED — Helix Wiring Tests.
 *
 * These test the daemon-facing `createHelix()` orchestrator entry point. They
 * exercise dependency-injection setters and the 'Helix requires a ModelPool'
 * guard. In the standalone @cassicore/helix package the orchestrator's runtime
 * (ModelPool, ToolExecutor, stores, model acquisition) is not mounted, so these
 * are quarantined here and run via `npm run test:host-wired`. Once a host wires
 * the package behind a port (P7), they are expected to run against the mounted
 * implementation. They are NOT counted in `npm test`.
 */

/**
 * Helix Wiring Tests — Verify ModelPool and dependency injection
 *
 * Tests that createHelix() correctly validates its dependencies:
 *   - Throws when ModelPool is not set
 *   - Accepts ModelPool via setModelPool()
 *   - Setter methods work without errors
 */

import { describe, it, expect, vi, beforeEach } from 'vitest'
import { EventEmitter } from 'events'
import { createHelix } from '../../src/index.js'
import type { ILogger, IEventBus } from '@cassicore/foundation'

// Mock Helpers

function createMockLogger(): ILogger {
  const calls: { level: string; msg: string; meta?: any }[] = []
  const make = (level: string) => (msg: string, meta?: any) => calls.push({ level, msg, meta })
  const logger: ILogger = {
    debug: make('debug'),
    info: make('info'),
    warn: make('warn'),
    error: make('error'),
    child: () => logger,
  }
  ;(logger as any)._calls = calls
  return logger
}

function createMockEventBus(): IEventBus {
  const emitter = new EventEmitter()
  const events: any[] = []

  return {
    emit: vi.fn(async (event: any) => {
      events.push(event)
      emitter.emit(event.type, event)
    }),
    on: (type: string, handler: (e: any) => void) => {
      emitter.on(type, handler)
      return () => emitter.off(type, handler)
    },
    once: (type: string, handler: (e: any) => void) => {
      emitter.once(type, handler)
    },
    subscribe: (type: string, handler: (e: any) => void) => {
      emitter.on(type, handler)
      return () => emitter.off(type, handler)
    },
    removeListener: (type: string, handler: (e: any) => void) => {
      emitter.off(type, handler)
    },
    _events: events,
  } as any
}

let logger: ILogger
let eventBus: IEventBus

beforeEach(() => {
  logger = createMockLogger()
  eventBus = createMockEventBus()
})

describe('Helix Wiring', () => {
  it('should create a Helix orchestrator without errors', () => {
    const helix = createHelix(logger, eventBus)
    expect(helix).toBeDefined()
    expect(helix.project).toBeInstanceOf(Function)
    expect(helix.setModelPool).toBeInstanceOf(Function)
    expect(helix.setToolRegistry).toBeInstanceOf(Function)
    expect(helix.setToolExecutor).toBeInstanceOf(Function)
    expect(helix.setStore).toBeInstanceOf(Function)
    expect(helix.setModelDirective).toBeInstanceOf(Function)
    expect(helix.setContextDistiller).toBeInstanceOf(Function)
  })

  it('should throw "Helix requires a ModelPool" when ModelPool is not set', async () => {
    const helix = createHelix(logger, eventBus)

    await expect(helix.project({ goal: 'Test goal' })).rejects.toThrow('Helix requires a ModelPool')
  })

  it('should accept ModelPool via setModelPool()', () => {
    const helix = createHelix(logger, eventBus)

    const mockModelPool = {
      acquire: vi.fn(),
      release: vi.fn(),
      dispose: vi.fn(),
    }

    // Should not throw
    expect(() => helix.setModelPool(mockModelPool as any)).not.toThrow()
  })

  it('should accept all setter injections without errors', () => {
    const helix = createHelix(logger, eventBus)

    const mockModelPool = { acquire: vi.fn(), release: vi.fn() }
    const mockToolRegistry = { getTools: vi.fn(), register: vi.fn() }
    const mockToolExecutor = { execute: vi.fn() }
    const mockStore = { saveSession: vi.fn(), getSession: vi.fn() }
    const mockModelDirective = { resolve: vi.fn(), consumeNextJob: vi.fn() }
    const mockContextDistiller = { distill: vi.fn() }

    expect(() => helix.setModelPool(mockModelPool as any)).not.toThrow()
    expect(() => helix.setToolRegistry(mockToolRegistry as any)).not.toThrow()
    expect(() => helix.setToolExecutor(mockToolExecutor as any)).not.toThrow()
    expect(() => helix.setStore(mockStore as any)).not.toThrow()
    expect(() => helix.setModelDirective(mockModelDirective as any)).not.toThrow()
    expect(() => helix.setContextDistiller(mockContextDistiller as any)).not.toThrow()
  })

  it('should report health status', () => {
    const helix = createHelix(logger, eventBus)
    const health = helix.getHealth()

    // Health depends on ModelPool being set and error count
    expect(health.errorCount).toBe(0)
    expect(health.lastRun).toBeUndefined()
    expect(health.modelPoolAvailable).toBe(false)
    // Not healthy until ModelPool is set
    expect(health.healthy).toBe(false)
  })

  it('should not throw "Helix requires a ModelPool" when ModelPool IS set', async () => {
    const helix = createHelix(logger, eventBus)

    const mockModelPool = {
      acquire: vi.fn().mockRejectedValue(new Error('test: no provider')),
      release: vi.fn(),
    }

    helix.setModelPool(mockModelPool as any)

    // Should fail with a different error (model acquisition), NOT "Helix requires a ModelPool"
    await expect(helix.project({ goal: 'Test goal' })).rejects.not.toThrow('Helix requires a ModelPool')
  })
})
