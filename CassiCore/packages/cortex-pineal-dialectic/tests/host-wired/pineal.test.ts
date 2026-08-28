// HOST-WIRED QUARANTINE — NOT part of the counted by-default suite.
//
// Ported from D: tests/intelligence/pineal.test.ts (HEAD@d63358da). Quarantined
// because it imports `PinealProjection` from `core/intelligence/pineal/projection.ts`,
// which is DEAD (excluded from the migration — P5-A table §0). It also relies on
// filesystem skill-file fixtures. Must be re-pointed to the surviving pineal surface
// and given live skill fixtures before promotion. Assertions are NOT weakened.
//

import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest'
import fs from 'node:fs'
import path from 'node:path'

import { PinealStore } from '../../core/intelligence/pineal/store.js'
import { FacetManager } from '../../core/intelligence/pineal/facet.js'
import { PinealAssembler } from '../../core/intelligence/pineal/assembler.js'
import { SkillLoader } from '../../core/intelligence/pineal/skill-loader.js'
import { parseSkillFile, parseAllSkillFiles } from '../../core/intelligence/pineal/skill-parser.js'
import { PinealProjection } from '../../core/intelligence/pineal/projection.js'
import { REINFORCEMENT_RATE, DOMAIN_INITIAL_CONVICTION, channelFromSessionId } from '../../core/intelligence/pineal/types.js'
import { SEED_FACETS, CHANNEL_SEED_FACETS } from '../../core/intelligence/pineal/seed.js'

import type { Facet, FacetInput } from '../../core/intelligence/pineal/types.js'

const createLogger = () => ({
  info: () => {},
  debug: () => {},
  warn: () => {},
  error: () => {},
  child: () => createLogger(),
} as any)

describe('Pineal — Core Module', () => {
  let store: PinealStore
  let manager: FacetManager

  beforeEach(() => {
    process.env.CASSICORE_HOME = `/tmp/pineal-test-${Date.now()}-${Math.random().toString(36).slice(2, 6)}`
    store = new PinealStore(createLogger())
    manager = new FacetManager(store, createLogger())
  })

  afterEach(() => {
    store.close()
    // Clean up temp dir
    const { rmSync } = require('node:fs')
    try { rmSync(process.env.CASSICORE_HOME!, { recursive: true }) } catch {}
    delete process.env.CASSICORE_HOME
  })

  describe('Facet CRUD', () => {
    it('creates a facet with domain defaults', () => {
      const facet = manager.create({
        domain: 'identity',
        category: 'self',
        content: 'My name is Cassandra',
      })

      expect(facet.id).toMatch(/^f_/)
      expect(facet.domain).toBe('identity')
      expect(facet.category).toBe('self')
      expect(facet.content).toBe('My name is Cassandra')
      expect(facet.conviction).toBe(DOMAIN_INITIAL_CONVICTION.identity)
      expect(facet.salience).toBe(0.5)
      expect(facet.provenance).toBe('self')
      expect(facet.version).toBe(1)
      expect(facet.active).toBe(true)
      expect(facet.pinned).toBe(false)
      expect(facet.reinforcements).toBe(0)
      expect(facet.evolvedFrom).toBeNull()
    })

    it('creates a facet with custom values', () => {
      const facet = manager.create({
        domain: 'wisdom',
        category: 'constraints',
        content: 'Always use .js extensions in ESM imports',
        conviction: 0.6,
        salience: 0.8,
        provenance: 'agents.md',
        tags: ['esm', 'imports'],
      })

      expect(facet.conviction).toBe(0.6)
      expect(facet.salience).toBe(0.8)
      expect(facet.provenance).toBe('agents.md')
      expect(facet.tags).toEqual(['esm', 'imports'])
    })

    it('retrieves a facet by id', () => {
      const created = manager.create({
        domain: 'philosophy',
        category: 'ethics',
        content: 'Private things stay private',
      })

      const fetched = manager.get(created.id)
      expect(fetched).not.toBeNull()
      expect(fetched!.content).toBe('Private things stay private')
    })

    it('returns null for nonexistent facet', () => {
      expect(manager.get('f_nonexistent')).toBeNull()
    })

    it('updates a facet', () => {
      const facet = manager.create({
        domain: 'identity',
        category: 'voice',
        content: 'Direct and competent',
      })

      const updated = manager.update(facet.id, {
        content: 'Direct, competent, with dry wit',
        tags: ['voice', 'personality'],
      })

      expect(updated!.content).toBe('Direct, competent, with dry wit')
      expect(updated!.tags).toEqual(['voice', 'personality'])
    })

    it('retires a facet (soft delete)', () => {
      const facet = manager.create({
        domain: 'identity',
        category: 'self',
        content: 'Temporary facet',
      })

      expect(manager.retire(facet.id)).toBe(true)

      const retired = manager.get(facet.id)
      expect(retired!.active).toBe(false)
    })
  })

  describe('Listing and Querying', () => {
    beforeEach(() => {
      manager.create({ domain: 'identity', category: 'self', content: 'I am Cassandra' })
      manager.create({ domain: 'identity', category: 'voice', content: 'Direct style' })
      manager.create({ domain: 'wisdom', category: 'constraints', content: 'Use .js extensions' })
      manager.create({ domain: 'philosophy', category: 'ethics', content: 'Respect privacy' })
    })

    it('lists all active facets', () => {
      const all = manager.list()
      expect(all).toHaveLength(4)
      expect(all.every(f => f.active)).toBe(true)
    })

    it('lists by domain', () => {
      const identity = manager.listByDomain('identity')
      expect(identity).toHaveLength(2)
      expect(identity.every(f => f.domain === 'identity')).toBe(true)
    })

    it('lists by domain and category', () => {
      const self = manager.list({ domain: 'identity', category: 'self' })
      expect(self).toHaveLength(1)
      expect(self[0].content).toBe('I am Cassandra')
    })

    it('filters by minimum conviction', () => {
      manager.create({ domain: 'identity', category: 'test', content: 'High conviction', conviction: 0.9 })

      const high = manager.list({ minConviction: 0.5 })
      expect(high).toHaveLength(1)
      expect(high[0].conviction).toBe(0.9)
    })

    it('filters by tags', () => {
      manager.create({
        domain: 'wisdom', category: 'gotchas', content: 'Check imports',
        tags: ['esm', 'build'],
      })

      const tagged = manager.list({ tags: ['esm'] })
      expect(tagged).toHaveLength(1)
      expect(tagged[0].content).toBe('Check imports')
    })

    it('respects limit', () => {
      const limited = manager.list({ limit: 2 })
      expect(limited).toHaveLength(2)
    })

    it('excludes retired facets from active lists', () => {
      const facet = manager.create({ domain: 'identity', category: 'test', content: 'Will be retired' })
      manager.retire(facet.id)

      const active = manager.list({ active: true })
      expect(active.find(f => f.id === facet.id)).toBeUndefined()
    })
  })

  describe('Conviction — Organic Growth', () => {
    it('reinforcement follows asymptotic formula', () => {
      const facet = manager.create({
        domain: 'identity',
        category: 'self',
        content: 'I am Cassandra',
      })

      const initial = facet.conviction
      const expectedIncrement = REINFORCEMENT_RATE * (1 - initial)
      const expected = initial + expectedIncrement

      const reinforced = manager.reinforce(facet.id)!
      expect(reinforced.conviction).toBeCloseTo(expected, 6)
      expect(reinforced.reinforcements).toBe(1)
    })

    it('produces rapid early growth', () => {
      const facet = manager.create({
        domain: 'philosophy',
        category: 'new',
        content: 'New belief',
      })

      const growths: number[] = []
      let current = facet.conviction

      for (let i = 0; i < 10; i++) {
        const reinforced = manager.reinforce(facet.id)!
        growths.push(reinforced.conviction - current)
        current = reinforced.conviction
      }

      // Each growth should be smaller than the previous (diminishing returns)
      for (let i = 1; i < growths.length; i++) {
        expect(growths[i]).toBeLessThan(growths[i - 1])
      }
    })

    it('approaches but never exceeds 1.0', () => {
      const facet = manager.create({
        domain: 'identity',
        category: 'self',
        content: 'Core identity',
        conviction: 0.99,
      })

      const reinforced = manager.reinforce(facet.id)!
      expect(reinforced.conviction).toBeLessThanOrEqual(1.0)
      expect(reinforced.conviction).toBeGreaterThan(0.99)
    })

    it('has no hardcoded floors — low conviction stays low without reinforcement', () => {
      const facet = manager.create({
        domain: 'philosophy',
        category: 'new',
        content: 'Unreinforced belief',
      })

      // Without reinforcement, conviction stays at initial value
      const fetched = manager.get(facet.id)!
      expect(fetched.conviction).toBe(DOMAIN_INITIAL_CONVICTION.philosophy)
    })

    it('does not reinforce inactive facets', () => {
      const facet = manager.create({
        domain: 'identity',
        category: 'test',
        content: 'Will be retired',
      })
      manager.retire(facet.id)

      expect(manager.reinforce(facet.id)).toBeNull()
    })

    it('reinforceMany processes multiple facets', () => {
      const a = manager.create({ domain: 'identity', category: 'self', content: 'A' })
      const b = manager.create({ domain: 'identity', category: 'voice', content: 'B' })
      const c = manager.create({ domain: 'wisdom', category: 'test', content: 'C' })

      const count = manager.reinforceMany([a.id, b.id, c.id])
      expect(count).toBe(3)

      // All should have conviction > initial
      const aReinforced = manager.get(a.id)!
      expect(aReinforced.conviction).toBeGreaterThan(DOMAIN_INITIAL_CONVICTION.identity)
    })

    it('explicit setConviction bypasses organic growth', () => {
      const facet = manager.create({
        domain: 'philosophy',
        category: 'ethics',
        content: 'Some belief',
      })

      const updated = manager.setConviction(facet.id, 0.95)!
      expect(updated.conviction).toBe(0.95)
    })

    it('setConviction clamps to [0, 1]', () => {
      const facet = manager.create({
        domain: 'identity',
        category: 'test',
        content: 'Clamp test',
      })

      expect(manager.setConviction(facet.id, 1.5)!.conviction).toBe(1)
      expect(manager.setConviction(facet.id, -0.5)!.conviction).toBe(0)
    })
  })

  describe('Evolution', () => {
    it('creates a new version linked to the original', () => {
      const original = manager.create({
        domain: 'identity',
        category: 'self',
        content: 'I am a digital assistant',
        provenance: 'soul.md',
      })

      const evolved = manager.evolve(original.id, 'I am a digital familiar')!

      expect(evolved.content).toBe('I am a digital familiar')
      expect(evolved.evolvedFrom).toBe(original.id)
      expect(evolved.version).toBe(2)
      expect(evolved.domain).toBe('identity')
      expect(evolved.category).toBe('self')
      expect(evolved.provenance).toBe('soul.md')

      // New version starts at domain initial conviction
      expect(evolved.conviction).toBe(DOMAIN_INITIAL_CONVICTION.identity)
    })

    it('retires the original when evolved', () => {
      const original = manager.create({
        domain: 'identity',
        category: 'self',
        content: 'Old identity',
      })

      manager.evolve(original.id, 'New identity')

      const retired = manager.get(original.id)!
      expect(retired.active).toBe(false)
    })

    it('preserves evolution chain through multiple versions', () => {
      const v1 = manager.create({
        domain: 'philosophy',
        category: 'ethics',
        content: 'Version 1',
      })

      const v2 = manager.evolve(v1.id, 'Version 2')!
      const v3 = manager.evolve(v2.id, 'Version 3')!

      expect(v3.version).toBe(3)
      expect(v3.evolvedFrom).toBe(v2.id)

      const history = manager.getHistory(v1.id)
      expect(history.length).toBeGreaterThanOrEqual(2)
    })

    it('returns null when evolving nonexistent facet', () => {
      expect(manager.evolve('f_nonexistent', 'New content')).toBeNull()
    })
  })

  describe('Domain Stats', () => {
    beforeEach(() => {
      manager.create({ domain: 'identity', category: 'self', content: 'A', conviction: 0.3 })
      manager.create({ domain: 'identity', category: 'voice', content: 'B', conviction: 0.5 })
      manager.create({ domain: 'wisdom', category: 'constraints', content: 'C', conviction: 0.2 })
      manager.create({ domain: 'philosophy', category: 'ethics', content: 'D', conviction: 0.15 })
    })

    it('returns stats per domain', () => {
      const stats = store.getDomainStats()
      expect(stats).toHaveLength(3)

      const identityStats = stats.find(s => s.domain === 'identity')!
      expect(identityStats.activeFacets).toBe(2)
      expect(identityStats.avgConviction).toBeCloseTo(0.4, 1)
      expect(identityStats.categories).toContain('self')
      expect(identityStats.categories).toContain('voice')
    })

    it('countActive respects domain filter', () => {
      expect(store.countActive('identity')).toBe(2)
      expect(store.countActive('wisdom')).toBe(1)
      expect(store.countActive()).toBe(4)
    })
  })

  describe('Snapshot', () => {
    it('captures full state', () => {
      manager.create({ domain: 'identity', category: 'self', content: 'Name' })
      manager.create({ domain: 'wisdom', category: 'test', content: 'Rule' })

      const snapshot: import('../../core/intelligence/pineal/types.js').PinealSnapshot = {
        facets: manager.list({ active: true }),
        domains: store.getDomainStats(),
        timestamp: new Date().toISOString(),
      }

      expect(snapshot.facets).toHaveLength(2)
      expect(snapshot.domains.length).toBeGreaterThan(0)
      expect(snapshot.timestamp).toMatch(/^\d{4}-\d{2}-\d{2}T/)
    })
  })

  describe('Seed Data', () => {
    it('populates all three domains', () => {
      const identityFacets = SEED_FACETS.filter(f => f.domain === 'identity')
      const wisdomFacets = SEED_FACETS.filter(f => f.domain === 'wisdom')
      const philosophyFacets = SEED_FACETS.filter(f => f.domain === 'philosophy')

      expect(identityFacets.length).toBeGreaterThan(5)
      expect(wisdomFacets.length).toBeGreaterThan(5)
      expect(philosophyFacets.length).toBeGreaterThan(3)
    })

    it('covers expected identity categories', () => {
      const categories = new Set(SEED_FACETS.filter(f => f.domain === 'identity').map(f => f.category))
      expect(categories).toContain('self')
      expect(categories).toContain('principles')
      expect(categories).toContain('boundaries')
      expect(categories).toContain('voice')
      expect(categories).toContain('continuity')
      expect(categories).toContain('naming')
    })

    it('covers expected wisdom categories', () => {
      const categories = new Set(SEED_FACETS.filter(f => f.domain === 'wisdom').map(f => f.category))
      expect(categories).toContain('defaults')
      expect(categories).toContain('constraints')
      expect(categories).toContain('patterns')
      expect(categories).toContain('gotchas')
      expect(categories).toContain('safety')
      expect(categories).toContain('reasoning')
    })

    it('all seed facets can be created', () => {
      for (const input of SEED_FACETS) {
        const facet = manager.create(input)
        expect(facet.id).toMatch(/^f_/)
        expect(facet.active).toBe(true)
      }

      const allActive = manager.list({ active: true })
      expect(allActive).toHaveLength(SEED_FACETS.length)
    })

    it('seed facets start at domain initial conviction', () => {
      for (const input of SEED_FACETS) {
        const facet = manager.create(input)
        expect(facet.conviction).toBe(DOMAIN_INITIAL_CONVICTION[input.domain])
      }
    })
  })

  describe('Assembler', () => {
    let assembler: PinealAssembler

    beforeEach(() => {
      assembler = new PinealAssembler(store, createLogger())
      for (const input of SEED_FACETS) {
        manager.create(input)
      }
    })

    it('assembles all domains into text', () => {
      const { text, facetIds } = assembler.assemble()
      expect(text).toContain('[Identity]')
      expect(text).toContain('[Wisdom]')
      expect(text).toContain('[Philosophy]')
      expect(facetIds.length).toBeGreaterThan(0)
    })

    it('respects character budget', () => {
      const small = new PinealAssembler(store, createLogger(), 500)
      const { text } = small.assemble()
      expect(text.length).toBeLessThanOrEqual(500)
    })

    it('returns facet IDs for reinforcement tracking', () => {
      const { facetIds } = assembler.assemble()
      for (const id of facetIds) {
        const facet = manager.get(id)
        expect(facet).not.toBeNull()
      }
    })

    it('pinned facets are always included regardless of budget', () => {
      const tiny = new PinealAssembler(store, createLogger(), 100)

      const pinnedFacet = manager.create({
        domain: 'wisdom',
        category: 'critical',
        content: 'This pinned instruction must always appear no matter what',
        pinned: true,
      })

      const { text, facetIds } = tiny.assemble()
      expect(facetIds).toContain(pinnedFacet.id)
      expect(text).toContain('This pinned instruction must always appear no matter what')
    })

    it('pinned facets appear before non-pinned facets in their domain', () => {
      const pinnedFacet = manager.create({
        domain: 'identity',
        category: 'self',
        content: 'PINNED CONTENT',
        conviction: 0.01,
        pinned: true,
      })
      manager.create({
        domain: 'identity',
        category: 'self',
        content: 'UNPINNED HIGH CONVICTION',
        conviction: 0.99,
      })

      const { text } = assembler.assemble()
      const pinnedPos = text.indexOf('PINNED CONTENT')
      const unpinnedPos = text.indexOf('UNPINNED HIGH CONVICTION')
      expect(pinnedPos).toBeLessThan(unpinnedPos)
    })
  })

  describe('Pinning', () => {
    it('creates a facet as pinned', () => {
      const facet = manager.create({
        domain: 'wisdom',
        category: 'critical',
        content: 'Always do the thing',
        pinned: true,
      })
      expect(facet.pinned).toBe(true)
    })

    it('creates a facet as unpinned by default', () => {
      const facet = manager.create({
        domain: 'wisdom',
        category: 'test',
        content: 'Normal facet',
      })
      expect(facet.pinned).toBe(false)
    })

    it('pins an existing facet', () => {
      const facet = manager.create({
        domain: 'wisdom',
        category: 'test',
        content: 'Pin me later',
      })
      expect(facet.pinned).toBe(false)

      const result = manager.pin(facet.id)
      expect(result).toBe(true)

      const updated = manager.get(facet.id)!
      expect(updated.pinned).toBe(true)
    })

    it('unpins a pinned facet', () => {
      const facet = manager.create({
        domain: 'wisdom',
        category: 'test',
        content: 'Unpin me later',
        pinned: true,
      })

      const result = manager.unpin(facet.id)
      expect(result).toBe(true)

      const updated = manager.get(facet.id)!
      expect(updated.pinned).toBe(false)
    })

    it('list with pinned filter returns only pinned facets', () => {
      manager.create({ domain: 'identity', category: 'self', content: 'A', pinned: true })
      manager.create({ domain: 'wisdom', category: 'test', content: 'B', pinned: true })
      manager.create({ domain: 'wisdom', category: 'test', content: 'C' })

      const pinned = manager.list({ pinned: true })
      expect(pinned).toHaveLength(2)
      expect(pinned.every(f => f.pinned)).toBe(true)
    })

    it('evolve carries pinned status forward', () => {
      const original = manager.create({
        domain: 'wisdom',
        category: 'test',
        content: 'Original pinned',
        pinned: true,
      })

      const evolved = manager.evolve(original.id, 'Evolved pinned')!
      expect(evolved.pinned).toBe(true)
    })

    it('query filters by pinned', () => {
      manager.create({ domain: 'wisdom', category: 'a', content: 'Pinned', pinned: true })
      manager.create({ domain: 'wisdom', category: 'b', content: 'Not pinned' })

      const pinnedOnly = manager.list({ domain: 'wisdom', pinned: true })
      expect(pinnedOnly).toHaveLength(1)
      expect(pinnedOnly[0].content).toBe('Pinned')

      const unpinnedOnly = manager.list({ domain: 'wisdom', pinned: false })
      expect(unpinnedOnly).toHaveLength(1)
      expect(unpinnedOnly[0].content).toBe('Not pinned')
    })
  })

  describe('Channel-Scoped Facets', () => {
    let assembler: PinealAssembler

    beforeEach(() => {
      assembler = new PinealAssembler(store, createLogger())

      // Create universal facets
      manager.create({ domain: 'identity', category: 'self', content: 'I am Cassandra' })
      manager.create({ domain: 'wisdom', category: 'defaults', content: 'Universal wisdom' })

      // Create OpenCode-scoped facet
      manager.create({
        domain: 'wisdom',
        category: 'ux-patterns',
        content: 'Use the question tool in OpenCode',
        scope: 'opencode',
        pinned: true,
      })

      // Create MCP-scoped facet
      manager.create({
        domain: 'wisdom',
        category: 'ux-patterns',
        content: 'Prefer structured responses in MCP',
        scope: 'mcp',
      })
    })

    it('channelFromSessionId extracts channel from session ID prefix', () => {
      expect(channelFromSessionId('oc:abc123')).toBe('opencode')
      expect(channelFromSessionId('mcp:session-1')).toBe('mcp')
      expect(channelFromSessionId('web:xxx')).toBe('web')
      expect(channelFromSessionId('vscode:yyy')).toBe('vscode')
      expect(channelFromSessionId('unknown-prefix')).toBeNull()
      expect(channelFromSessionId(undefined)).toBeNull()
    })

    it('creates a facet with scope', () => {
      const facet = manager.create({
        domain: 'wisdom',
        category: 'test',
        content: 'Scoped facet',
        scope: 'opencode',
      })
      expect(facet.scope).toBe('opencode')
    })

    it('creates a facet with null scope by default', () => {
      const facet = manager.create({
        domain: 'wisdom',
        category: 'test',
        content: 'Universal facet',
      })
      expect(facet.scope).toBeNull()
    })

    it('assembly for OpenCode includes universal + opencode-scoped facets', () => {
      const { text } = assembler.assemble('oc:test-session')
      expect(text).toContain('I am Cassandra')
      expect(text).toContain('Universal wisdom')
      expect(text).toContain('Use the question tool in OpenCode')
      expect(text).not.toContain('Prefer structured responses in MCP')
    })

    it('assembly for MCP includes universal + mcp-scoped facets', () => {
      const { text } = assembler.assemble('mcp:test-session')
      expect(text).toContain('I am Cassandra')
      expect(text).toContain('Universal wisdom')
      expect(text).not.toContain('Use the question tool in OpenCode')
      expect(text).toContain('Prefer structured responses in MCP')
    })

    it('assembly for unknown channel includes only universal facets', () => {
      const { text } = assembler.assemble('internal-session')
      expect(text).toContain('I am Cassandra')
      expect(text).toContain('Universal wisdom')
      expect(text).not.toContain('Use the question tool in OpenCode')
      expect(text).not.toContain('Prefer structured responses in MCP')
    })

    it('assembly with no sessionId includes only universal facets', () => {
      const { text } = assembler.assemble()
      expect(text).toContain('I am Cassandra')
      expect(text).toContain('Universal wisdom')
      expect(text).not.toContain('Use the question tool in OpenCode')
      expect(text).not.toContain('Prefer structured responses in MCP')
    })

    it('explicit channel parameter overrides sessionId-based detection', () => {
      // Pass an MCP session ID but override with opencode channel
      const { text } = assembler.assemble('mcp:test-session', 'opencode')
      expect(text).toContain('Use the question tool in OpenCode')
      expect(text).not.toContain('Prefer structured responses in MCP')
    })

    it('scope survives evolution', () => {
      const original = manager.create({
        domain: 'wisdom',
        category: 'test',
        content: 'Original scoped',
        scope: 'opencode',
      })

      const evolved = store.evolve(original.id, 'Evolved scoped')
      expect(evolved!.scope).toBe('opencode')
    })

    it('scope can be changed during evolution', () => {
      const original = manager.create({
        domain: 'wisdom',
        category: 'test',
        content: 'Originally opencode',
        scope: 'opencode',
      })

      const evolved = store.evolve(original.id, 'Now universal', { scope: null })
      expect(evolved!.scope).toBeNull()
    })

    it('scope can be filtered directly in list queries', () => {
      const opencodeFacets = store.list({ scope: 'opencode' })
      expect(opencodeFacets.every(f => f.scope === 'opencode')).toBe(true)
      expect(opencodeFacets.length).toBeGreaterThan(0)

      const universalFacets = store.list({ scope: null })
      expect(universalFacets.every(f => f.scope === null)).toBe(true)
    })

    it('channel seed facets are well-formed', () => {
      for (const input of CHANNEL_SEED_FACETS) {
        expect(input.scope).toBeDefined()
        expect(input.scope).not.toBeNull()
        expect(input.domain).toBeDefined()
        expect(input.content).toBeDefined()
        expect(input.content.length).toBeGreaterThan(10)
      }
    })
  })

  describe('Skill Parser', () => {
    let tmpSkillDir: string

    beforeEach(() => {
      tmpSkillDir = `/tmp/pineal-skills-${Date.now()}`
      fs.mkdirSync(path.join(tmpSkillDir, 'test-skill'), { recursive: true })
      fs.writeFileSync(path.join(tmpSkillDir, 'test-skill', 'SKILL.md'), `---
name: test-skill
description: A test skill for unit testing
---

# Test Skill

Preamble text.

## When to Use
- Testing the parser
- Verifying facet creation

## Core Pattern
1. Step one
2. Step two
3. Step three

## Important Rules
- Rule A
- Rule B
`)
    })

    afterEach(() => {
      fs.rmSync(tmpSkillDir, { recursive: true, force: true })
    })

    it('parses YAML frontmatter', () => {
      const facets = parseSkillFile(path.join(tmpSkillDir, 'test-skill', 'SKILL.md'))
      expect(facets.length).toBeGreaterThan(0)
      expect(facets[0].domain).toBe('praxis')
      expect(facets[0].category).toBe('test-skill')
      expect(facets[0].provenance).toBe('skill-file')
    })

    it('splits H2 sections into separate facets', () => {
      const facets = parseSkillFile(path.join(tmpSkillDir, 'test-skill', 'SKILL.md'))
      const headings = facets.map(f => f.tags?.find(t => !t.startsWith('skill:')))
      expect(headings).toContain('scope')
      expect(headings).toContain('procedure')
      expect(headings).toContain('rules')
    })

    it('tags each facet with skill name', () => {
      const facets = parseSkillFile(path.join(tmpSkillDir, 'test-skill', 'SKILL.md'))
      for (const facet of facets) {
        expect(facet.tags).toContain('skill:test-skill')
      }
    })

    it('parseAllSkillFiles scans directories', () => {
      const facets = parseAllSkillFiles([tmpSkillDir], createLogger())
      expect(facets.length).toBeGreaterThan(0)
      expect(facets.every(f => f.domain === 'praxis')).toBe(true)
    })

    it('handles missing directories gracefully', () => {
      const facets = parseAllSkillFiles(['/tmp/nonexistent-dir-xyz'], createLogger())
      expect(facets).toHaveLength(0)
    })
  })

  describe('Skill Loader', () => {
    let loader: SkillLoader

    beforeEach(() => {
      loader = new SkillLoader(store, createLogger())
      manager.create({ domain: 'praxis', category: 'test-skill', content: 'When to Use: testing', tags: ['skill:test-skill', 'scope'], provenance: 'skill-file' })
      manager.create({ domain: 'praxis', category: 'test-skill', content: 'Core Pattern: 1. do thing', tags: ['skill:test-skill', 'procedure'], provenance: 'skill-file' })
      manager.create({ domain: 'praxis', category: 'test-skill', content: 'Rules: be careful', tags: ['skill:test-skill', 'rules'], provenance: 'skill-file' })
    })

    it('loads a skill by name', () => {
      const result = loader.loadSkill('test-skill')
      expect(result).not.toBeNull()
      expect(result).toContain('When to Use')
      expect(result).toContain('Core Pattern')
      expect(result).toContain('Rules')
    })

    it('returns null for unknown skill', () => {
      expect(loader.loadSkill('nonexistent')).toBeNull()
    })

    it('lists available skills', () => {
      const skills = loader.listSkills()
      expect(skills.length).toBe(1)
      expect(skills[0].name).toBe('test-skill')
      expect(skills[0].facetCount).toBe(3)
    })

    it('returns facet IDs for reinforcement', () => {
      const ids = loader.getSkillFacetIds('test-skill')
      expect(ids).toHaveLength(3)
      for (const id of ids) {
        expect(manager.get(id)).not.toBeNull()
      }
    })
  })

  describe('Cortex Projection', () => {
    let projection: PinealProjection
    let mockCortex: { signal: ReturnType<typeof vi.fn>; signals: Array<Record<string, unknown>> }

    beforeEach(() => {
      projection = new PinealProjection(store, createLogger())
      mockCortex = {
        signals: [],
        signal: vi.fn((region: string, input: Record<string, unknown>) => {
          mockCortex.signals.push({ region, ...input })
        }),
      }
    })

    it('projects high-conviction identity facets', () => {
      manager.create({ domain: 'identity', category: 'self', content: 'I am Cassandra', conviction: 0.8 })
      manager.create({ domain: 'identity', category: 'voice', content: 'Direct style', conviction: 0.6 })

      const count = projection.project(mockCortex)
      expect(count).toBe(2)
      expect(mockCortex.signal).toHaveBeenCalledTimes(2)
    })

    it('skips facets below conviction threshold', () => {
      manager.create({ domain: 'identity', category: 'self', content: 'Low conviction', conviction: 0.1 })

      const count = projection.project(mockCortex)
      expect(count).toBe(0)
    })

    it('only projects identity domain, not wisdom or philosophy', () => {
      manager.create({ domain: 'identity', category: 'self', content: 'Identity', conviction: 0.8 })
      manager.create({ domain: 'wisdom', category: 'test', content: 'Wisdom', conviction: 0.8 })
      manager.create({ domain: 'philosophy', category: 'test', content: 'Philosophy', conviction: 0.8 })

      projection.project(mockCortex)

      const projectedContents = mockCortex.signals.map(s => s.content)
      expect(projectedContents).toContain('Identity')
      expect(projectedContents).not.toContain('Wisdom')
      expect(projectedContents).not.toContain('Philosophy')
    })

    it('uses correct signal properties', () => {
      manager.create({ domain: 'identity', category: 'self', content: 'Test', conviction: 0.9 })

      projection.project(mockCortex)

      expect(mockCortex.signal).toHaveBeenCalledWith('executive', expect.objectContaining({
        type: 'insight',
        author: 'pineal',
        tags: expect.arrayContaining(['pineal', 'identity']),
      }))
    })

    it('tracks projected count', () => {
      manager.create({ domain: 'identity', category: 'self', content: 'A', conviction: 0.8 })
      manager.create({ domain: 'identity', category: 'voice', content: 'B', conviction: 0.7 })

      expect(projection.getProjectedCount()).toBe(0)
      projection.project(mockCortex)
      expect(projection.getProjectedCount()).toBe(2)
    })
  })
})
