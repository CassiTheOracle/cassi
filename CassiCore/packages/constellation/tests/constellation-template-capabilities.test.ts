/**
 * Unit tests for Constellation template capabilities.
 *
 * Tests cover:
 *   - getTemplateCapabilities: all 5 templates return correct structure
 *   - listTemplateCapabilities: returns all templates
 *   - PostureCapabilities: every posture in every template has capabilities
 *   - TemplateCapabilities: aggregate fields are consistent with posture data
 */

import { describe, it, expect } from 'vitest'
import {
  getTemplateCapabilities,
  listTemplateCapabilities,
  listTemplates,
  getTemplatePostures,
} from '../src/templates.js'
import type {
  ConstellationTemplate,
  TemplateCapabilities,
} from '../src/types.js'


describe('getTemplateCapabilities', () => {
  const ALL_TEMPLATES: ConstellationTemplate[] = ['standard', 'research', 'implementation', 'review', 'minimal']

  it.each(ALL_TEMPLATES)('returns valid TemplateCapabilities for "%s"', (template) => {
    const caps = getTemplateCapabilities(template)

    expect(caps.template).toBe(template)
    expect(typeof caps.description).toBe('string')
    expect(caps.description.length).toBeGreaterThan(0)
    expect(caps.postureCount).toBeGreaterThan(0)
    expect(caps.primaryDomains).toBeInstanceOf(Array)
    expect(caps.primaryDomains.length).toBeGreaterThan(0)
    expect(caps.bestFor).toBeInstanceOf(Array)
    expect(caps.bestFor.length).toBeGreaterThan(0)
    expect(typeof caps.dominantModelTier).toBe('string')
  })

  it('standard template has 3 postures', () => {
    const caps = getTemplateCapabilities('standard')
    expect(caps.postureCount).toBe(3)
  })

  it('research template has 5 postures', () => {
    const caps = getTemplateCapabilities('research')
    expect(caps.postureCount).toBe(5)
  })

  it('implementation template has 4 postures', () => {
    const caps = getTemplateCapabilities('implementation')
    expect(caps.postureCount).toBe(4)
  })

  it('review template has 5 postures', () => {
    const caps = getTemplateCapabilities('review')
    expect(caps.postureCount).toBe(5)
  })

  it('minimal template has 2 postures', () => {
    const caps = getTemplateCapabilities('minimal')
    expect(caps.postureCount).toBe(2)
  })

  it('primaryDomains are unique (no duplicates)', () => {
    for (const template of ALL_TEMPLATES) {
      const caps = getTemplateCapabilities(template)
      const unique = new Set(caps.primaryDomains)
      expect(unique.size).toBe(caps.primaryDomains.length)
    }
  })

  it('postureCount matches actual posture array length', () => {
    for (const template of ALL_TEMPLATES) {
      const caps = getTemplateCapabilities(template)
      const postures = getTemplatePostures(template)
      expect(caps.postureCount).toBe(postures.length)
    }
  })

  it('primaryDomains are a subset of posture primary capabilities', () => {
    for (const template of ALL_TEMPLATES) {
      const caps = getTemplateCapabilities(template)
      const postures = getTemplatePostures(template)
      const allPrimary = new Set<string>()
      for (const p of postures) {
        if (p.capabilities?.primary) {
          for (const d of p.capabilities.primary) allPrimary.add(d)
        }
      }
      for (const domain of caps.primaryDomains) {
        expect(allPrimary.has(domain)).toBe(true)
      }
    }
  })

  it('dominantModelTier reflects the most common tier across postures', () => {
    for (const template of ALL_TEMPLATES) {
      const caps = getTemplateCapabilities(template)
      const postures = getTemplatePostures(template)
      const tierCounts = new Map<string, number>()
      for (const p of postures) {
        const tier = p.capabilities?.modelTier ?? 'kimi'
        tierCounts.set(tier, (tierCounts.get(tier) ?? 0) + 1)
      }
      let expectedTier = 'kimi'
      let maxCount = 0
      for (const [tier, count] of tierCounts) {
        if (count > maxCount) { expectedTier = tier; maxCount = count }
      }
      expect(caps.dominantModelTier).toBe(expectedTier)
    }
  })

  it('standard and research share a common base (standard postures)', () => {
    const stdCaps = getTemplateCapabilities('standard')
    const resCaps = getTemplateCapabilities('research')
    // Research is a superset of standard
    expect(resCaps.postureCount).toBeGreaterThan(stdCaps.postureCount)
    for (const domain of stdCaps.primaryDomains) {
      expect(resCaps.primaryDomains).toContain(domain)
    }
  })

  it('implementation template includes "implementation" in primaryDomains', () => {
    const caps = getTemplateCapabilities('implementation')
    expect(caps.primaryDomains).toContain('implementation')
  })

  it('review template includes "review" in primaryDomains', () => {
    const caps = getTemplateCapabilities('review')
    expect(caps.primaryDomains).toContain('review')
  })

  it('minimal template has "background" as dominant tier', () => {
    const caps = getTemplateCapabilities('minimal')
    expect(caps.dominantModelTier).toBe('background')
  })

  it('bestFor arrays contain template-appropriate task types', () => {
    expect(getTemplateCapabilities('standard').bestFor).toContain('general')
    expect(getTemplateCapabilities('research').bestFor).toContain('investigation')
    expect(getTemplateCapabilities('implementation').bestFor).toContain('new-features')
    expect(getTemplateCapabilities('review').bestFor).toContain('code-review')
    expect(getTemplateCapabilities('minimal').bestFor).toContain('quick-fixes')
  })
})


describe('listTemplateCapabilities', () => {
  it('returns capabilities for all templates', () => {
    const allCaps = listTemplateCapabilities()
    const templates = listTemplates()
    expect(allCaps.length).toBe(templates.length)
  })

  it('each entry has a unique template name', () => {
    const allCaps = listTemplateCapabilities()
    const names = allCaps.map(c => c.template)
    expect(new Set(names).size).toBe(names.length)
  })

  it('covers every template from listTemplates()', () => {
    const allCaps = listTemplateCapabilities()
    const templates = listTemplates()
    const capTemplates = new Set(allCaps.map(c => c.template))
    for (const t of templates) {
      expect(capTemplates.has(t)).toBe(true)
    }
  })

  it('returns the same data as calling getTemplateCapabilities individually', () => {
    const allCaps = listTemplateCapabilities()
    for (const caps of allCaps) {
      const individual = getTemplateCapabilities(caps.template)
      expect(caps).toEqual(individual)
    }
  })
})


describe('posture capabilities consistency', () => {
  const ALL_TEMPLATES: ConstellationTemplate[] = ['standard', 'research', 'implementation', 'review', 'minimal']

  it('every posture in every template has capabilities defined', () => {
    for (const template of ALL_TEMPLATES) {
      const postures = getTemplatePostures(template)
      for (const p of postures) {
        expect(p.capabilities).toBeDefined()
        expect(p.capabilities!.primary).toBeInstanceOf(Array)
        expect(p.capabilities!.primary.length).toBeGreaterThan(0)
      }
    }
  })

  it('every posture has a modelTier', () => {
    for (const template of ALL_TEMPLATES) {
      const postures = getTemplatePostures(template)
      for (const p of postures) {
        expect(p.capabilities?.modelTier).toBeDefined()
        expect(typeof p.capabilities!.modelTier).toBe('string')
      }
    }
  })

  it('every posture has trait values in 0-1 range', () => {
    for (const template of ALL_TEMPLATES) {
      const postures = getTemplatePostures(template)
      for (const p of postures) {
        const traits = p.capabilities?.traits
        if (traits) {
          for (const [key, value] of Object.entries(traits)) {
            expect(value).toBeGreaterThanOrEqual(0)
            expect(value).toBeLessThanOrEqual(1)
          }
        }
      }
    }
  })

  it('every posture traits include at least divergent, convergent, and executive', () => {
    for (const template of ALL_TEMPLATES) {
      const postures = getTemplatePostures(template)
      for (const p of postures) {
        const traits = p.capabilities?.traits
        expect(traits).toBeDefined()
        expect(typeof traits!.divergent).toBe('number')
        expect(typeof traits!.convergent).toBe('number')
        expect(typeof traits!.executive).toBe('number')
      }
    }
  })
})
