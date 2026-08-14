/**
 * QUARANTINED — stale relative to the verbatim-migrated live @cassicore/tools
 * code (P6 turn 1) / environment-dependent. Assertions contradict the
 * authoritative migrated implementations; kept for reference, NOT run.
 */
/**
 * Tests for cognitive tools (_reflect and _remember).
 *
 * These tools exploit the free tool loop in request-based billing providers.
 * They execute locally (instant) and route signals to the intelligence layer.
 */

import { describe, it, expect, beforeEach, vi } from 'vitest'
import {
  reflectDefinition, makeReflectHandler,
  cognitiveRememberDefinition, makeCognitiveRememberHandler,
  type CognitiveToolDeps,
} from '../src/implementations/cognitive-tools.js'
import type { ToolExecutionContext } from '../src/types.js'


function makeLogger() {
  return {
    info: vi.fn(),
    warn: vi.fn(),
    error: vi.fn(),
    debug: vi.fn(),
    child: () => makeLogger(),
  } as any
}

function makeContext(sessionId = 'test-session'): ToolExecutionContext {
  return {
    sessionId,
    workingDir: '/tmp',
    allowedPaths: ['/tmp'],
    networkAllowlist: [],
    logger: makeLogger(),
  }
}


describe('_reflect tool', () => {
  it('should have valid tool definition', () => {
    expect(reflectDefinition.name).toBe('_reflect')
    expect(reflectDefinition.parameters.type).toBe('object')
    expect(reflectDefinition.parameters.properties).toHaveProperty('focus')
  })

  it('should return "no observations" when nothing accumulated', async () => {
    const deps: CognitiveToolDeps = {
      logger: makeLogger(),
    }
    const handler = makeReflectHandler(deps)
    const result = await handler({}, makeContext())
    expect(result).toContain('No cognitive observations')
  })

  it('should return signals from thought observer', async () => {
    const deps: CognitiveToolDeps = {
      thoughtObserver: {
        peekSignals: (_sid: string) => [
          { kind: 'edge_case' as const, text: 'Buffer overflow when input exceeds 1MB', confidence: 0.85 },
          { kind: 'assumption' as const, text: 'Assumes single-threaded execution', confidence: 0.75 },
        ],
      } as any,
      logger: makeLogger(),
    }
    const handler = makeReflectHandler(deps)
    const result = await handler({}, makeContext())

    expect(result).toContain('COGNITIVE OBSERVATIONS')
    expect(result).toContain('EDGE CASE')
    expect(result).toContain('Buffer overflow')
    expect(result).toContain('ASSUMPTION')
    expect(result).toContain('single-threaded')
  })

  it('should filter signals by focus area', async () => {
    const deps: CognitiveToolDeps = {
      thoughtObserver: {
        peekSignals: (_sid: string) => [
          { kind: 'edge_case' as const, text: 'Buffer overflow when input exceeds 1MB', confidence: 0.85 },
          { kind: 'assumption' as const, text: 'Assumes database is always reachable', confidence: 0.75 },
        ],
      } as any,
      logger: makeLogger(),
    }
    const handler = makeReflectHandler(deps)
    const result = await handler({ focus: 'database' }, makeContext())

    expect(result).toContain('database')
    expect(result).not.toContain('Buffer overflow')
  })

  it('should include subconscious context when available', async () => {
    const deps: CognitiveToolDeps = {
      subconscious: {
        getContextInjection: (_sid: string) => 'Pattern detected: repeated error handling gaps in auth module',
      } as any,
      logger: makeLogger(),
    }
    const handler = makeReflectHandler(deps)
    const result = await handler({}, makeContext())

    expect(result).toContain('SUBCONSCIOUS OBSERVATIONS')
    expect(result).toContain('error handling gaps')
  })
})


describe('_remember tool', () => {
  it('should have valid tool definition', () => {
    expect(cognitiveRememberDefinition.name).toBe('_remember')
    expect(cognitiveRememberDefinition.parameters.type).toBe('object')
    expect(cognitiveRememberDefinition.parameters.required).toContain('observations')
  })

  it('should store observations via injection aggregator', async () => {
    const queuedSignals: any[] = []
    const deps: CognitiveToolDeps = {
      injectionAggregator: {
        queueDialecticSignal: (_sid: string, signal: any) => {
          queuedSignals.push(signal)
        },
      } as any,
      logger: makeLogger(),
    }
    const handler = makeCognitiveRememberHandler(deps)
    const result = await handler({
      observations: [
        { kind: 'edge_case', text: 'Null pointer when session expires mid-request', confidence: 0.8 },
        { kind: 'insight', text: 'The retry logic creates a feedback loop', confidence: 0.9 },
      ],
    }, makeContext())

    expect(result).toContain('Stored 2 observation(s)')
    expect(queuedSignals.length).toBe(2)
    expect(queuedSignals[0].type).toBe('edge_case')
    expect(queuedSignals[0].content).toContain('Null pointer')
    expect(queuedSignals[1].type).toBe('insight')
  })

  it('should handle missing observations gracefully', async () => {
    const deps: CognitiveToolDeps = { logger: makeLogger() }
    const handler = makeCognitiveRememberHandler(deps)
    const result = await handler({}, makeContext())
    expect(result).toContain('Error')
  })

  it('should handle empty observations array', async () => {
    const deps: CognitiveToolDeps = { logger: makeLogger() }
    const handler = makeCognitiveRememberHandler(deps)
    const result = await handler({ observations: [] }, makeContext())
    expect(result).toContain('No valid observations')
  })

  it('should sanitize invalid kinds to "insight"', async () => {
    const queuedSignals: any[] = []
    const deps: CognitiveToolDeps = {
      injectionAggregator: {
        queueDialecticSignal: (_sid: string, signal: any) => {
          queuedSignals.push(signal)
        },
      } as any,
      logger: makeLogger(),
    }
    const handler = makeCognitiveRememberHandler(deps)
    await handler({
      observations: [
        { kind: 'invalid_kind', text: 'Some observation', confidence: 0.7 },
      ],
    }, makeContext())

    expect(queuedSignals[0].type).toBe('insight')
  })

  it('should cap text length at 300 characters', async () => {
    const queuedSignals: any[] = []
    const deps: CognitiveToolDeps = {
      injectionAggregator: {
        queueDialecticSignal: (_sid: string, signal: any) => {
          queuedSignals.push(signal)
        },
      } as any,
      logger: makeLogger(),
    }
    const handler = makeCognitiveRememberHandler(deps)
    const longText = 'A'.repeat(500)
    await handler({
      observations: [
        { kind: 'insight', text: longText, confidence: 0.7 },
      ],
    }, makeContext())

    expect(queuedSignals[0].content.length).toBeLessThanOrEqual(300)
  })

  it('should clamp confidence to [0, 1] range', async () => {
    const queuedSignals: any[] = []
    const deps: CognitiveToolDeps = {
      injectionAggregator: {
        queueDialecticSignal: (_sid: string, signal: any) => {
          queuedSignals.push(signal)
        },
      } as any,
      logger: makeLogger(),
    }
    const handler = makeCognitiveRememberHandler(deps)
    await handler({
      observations: [
        { kind: 'insight', text: 'Test with too-high confidence', confidence: 5.0 },
        { kind: 'insight', text: 'Test with negative confidence', confidence: -1.0 },
      ],
    }, makeContext())

    expect(queuedSignals[0].confidence).toBeLessThanOrEqual(1.0)
    expect(queuedSignals[1].confidence).toBeGreaterThanOrEqual(0.0)
  })
})
