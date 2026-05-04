/**
 * Tests for Replay Diversity Floor (N3).
 */

import { describe, it, expect } from 'vitest'

import { DiversityFloor, DEFAULT_DIVERSITY_CONFIG } from './diversity-floor.js'
import type { DiversityCategory, DiversityFloorConfig } from './diversity-floor.js'
import type { ILogger } from '../../../types/interfaces.js'



const silentLogger: ILogger = {
  info: () => {},
  warn: () => {},
  error: () => {},
  debug: () => {},
  child: () => silentLogger,
}

function makeFloor(config?: Partial<DiversityFloorConfig>): DiversityFloor {
  return new DiversityFloor(config ?? {}, silentLogger)
}

/** Record N decisions in a category, `novel` controlling the ratio. */
function recordBatch(
  floor: DiversityFloor,
  category: DiversityCategory,
  count: number,
  novelRatio: number,
): void {
  const novelCount = Math.round(count * novelRatio)
  for (let i = 0; i < count; i++) {
    const isNovel = i < novelCount
    floor.record(category, `pattern-${i}`, isNovel)
  }
}



describe('DiversityFloor', () => {
  it('starts with novelty ratio 1 (empty window)', () => {
    const floor = makeFloor()
    const state = floor.getCategoryState('b3_replay')
    expect(state.noveltyRatio).toBe(1)
    expect(state.pressure).toBe(0)
  })

  it('records decisions and computes ratio', () => {
    const floor = makeFloor()
    recordBatch(floor, 'b3_replay', 20, 0.5)

    const state = floor.getCategoryState('b3_replay')
    expect(state.novelCount).toBe(10)
    expect(state.reusedCount).toBe(10)
    expect(state.noveltyRatio).toBeCloseTo(0.5, 2)
  })

  it('trims to window size', () => {
    const floor = makeFloor({
      categories: {
        ...DEFAULT_DIVERSITY_CONFIG.categories,
        b3_replay: { windowSize: 10, noveltyFloor: 0.3 },
      },
    } as Partial<DiversityFloorConfig>)
    recordBatch(floor, 'b3_replay', 20, 0.5)

    const state = floor.getCategoryState('b3_replay')
    expect(state.windowSize).toBe(10)
  })

  it('isNovel returns false for previously recorded identifiers', () => {
    const floor = makeFloor()
    floor.record('b3_replay', 'trace-abc', false)

    expect(floor.isNovel('b3_replay', 'trace-abc')).toBe(false)
    expect(floor.isNovel('b3_replay', 'trace-xyz')).toBe(true)
  })

  it('isNovel returns true for identifiers that fell out of the window', () => {
    const floor = makeFloor({
      categories: {
        ...DEFAULT_DIVERSITY_CONFIG.categories,
        b3_replay: { windowSize: 5, noveltyFloor: 0.3 },
      },
    } as Partial<DiversityFloorConfig>)

    floor.record('b3_replay', 'old-trace', false)
    // Push 5 more decisions to push it out
    for (let i = 0; i < 5; i++) {
      floor.record('b3_replay', `filler-${i}`, true)
    }

    expect(floor.isNovel('b3_replay', 'old-trace')).toBe(true)
  })



  it('reports zero pressure when novelty ratio is above floor', () => {
    const floor = makeFloor()
    recordBatch(floor, 'b3_replay', 20, 0.5) // 50% > 30% floor

    expect(floor.getPressure('b3_replay')).toBe(0)
  })

  it('reports positive pressure when novelty is below floor', () => {
    const floor = makeFloor()
    recordBatch(floor, 'b3_replay', 20, 0.1) // 10% < 30% floor

    const pressure = floor.getPressure('b3_replay')
    expect(pressure).toBeGreaterThan(0)
  })

  it('pressure approaches 1 when all decisions are reused', () => {
    const floor = makeFloor()
    recordBatch(floor, 'b3_replay', 50, 0) // 0% novel

    const pressure = floor.getPressure('b3_replay')
    expect(pressure).toBeGreaterThanOrEqual(0.9)
  })

  it('returns zero pressure when disabled', () => {
    const floor = makeFloor({ enabled: false })
    recordBatch(floor, 'b3_replay', 50, 0)

    expect(floor.getPressure('b3_replay')).toBe(0)
  })



  it('composite starts with weightedNoveltyRatio 1', () => {
    const floor = makeFloor()
    const composite = floor.getComposite()

    expect(composite.weightedNoveltyRatio).toBe(1)
    expect(composite.trend).toBe('stable')
  })

  it('composite detects falling trend when recent decisions are mostly reused', () => {
    const floor = makeFloor()
    // First half: mostly novel
    recordBatch(floor, 'b3_replay', 25, 0.8)
    // Second half: mostly reused
    recordBatch(floor, 'b3_replay', 25, 0.1)

    const composite = floor.getComposite()
    expect(composite.trend).toBe('falling')
  })

  it('composite identifies worst category', () => {
    const floor = makeFloor()
    // b3_replay: high novelty
    recordBatch(floor, 'b3_replay', 20, 0.8)
    // c1_meditation_seed: low novelty
    recordBatch(floor, 'c1_meditation_seed', 20, 0.1)

    const composite = floor.getComposite()
    expect(composite.worstCategory).toBe('c1_meditation_seed')
  })

  it('composite recommends investigate_pattern when worst ratio < 0.2', () => {
    const floor = makeFloor()
    recordBatch(floor, 'c3_overlay_candidate', 20, 0.05)

    const composite = floor.getComposite()
    expect(composite.recommendation).toBe('investigate_pattern')
  })



  it('renderSummary produces a non-empty string with percentage', () => {
    const floor = makeFloor()
    recordBatch(floor, 'b3_replay', 20, 0.5)

    const summary = floor.renderSummary()
    expect(summary).toContain('Diversity:')
    expect(summary).toMatch(/\d+%/)
  })



  it('updateCategoryFloor changes the floor without losing other settings', () => {
    const floor = makeFloor()
    floor.updateCategoryFloor('b3_replay', { noveltyFloor: 0.6 })

    const state = floor.getCategoryState('b3_replay')
    expect(state.noveltyFloor).toBe(0.6)
    // windowSize should remain default
    expect(state.windowSize).toBeLessThanOrEqual(DEFAULT_DIVERSITY_CONFIG.categories.b3_replay.windowSize)
  })

  it('getConfig returns current config', () => {
    const floor = makeFloor({ enabled: false })
    const config = floor.getConfig()

    expect(config.enabled).toBe(false)
  })



  it('different categories track independently', () => {
    const floor = makeFloor()
    recordBatch(floor, 'b3_replay', 20, 0.1)
    recordBatch(floor, 'c1_meditation_seed', 20, 0.8)

    const b3 = floor.getCategoryState('b3_replay')
    const c1 = floor.getCategoryState('c1_meditation_seed')

    expect(b3.noveltyRatio).toBeLessThan(c1.noveltyRatio)
    expect(b3.pressure).toBeGreaterThan(c1.pressure)
  })
})
