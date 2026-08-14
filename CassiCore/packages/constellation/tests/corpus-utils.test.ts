/**
 * Tests for corpus-utils — Stateless utility functions extracted from Corpus.
 */

import { describe, it, expect } from 'vitest'
import {
  normalizeDirectiveType,
  normalizeUrgency,
  extractFilePaths,
} from '../src/corpus/corpus-utils.js'


describe('normalizeDirectiveType', () => {
  it('normalizes guidance variants', () => {
    expect(normalizeDirectiveType('guidance')).toBe('guidance')
    expect(normalizeDirectiveType('guide')).toBe('guidance')
    expect(normalizeDirectiveType('suggest')).toBe('guidance')
  })

  it('normalizes redirect variants', () => {
    expect(normalizeDirectiveType('redirect')).toBe('redirect')
    expect(normalizeDirectiveType('refocus')).toBe('redirect')
    expect(normalizeDirectiveType('change')).toBe('redirect')
  })

  it('normalizes throttle variants', () => {
    expect(normalizeDirectiveType('throttle')).toBe('throttle')
    expect(normalizeDirectiveType('slow')).toBe('throttle')
  })

  it('normalizes priority-shift variants', () => {
    expect(normalizeDirectiveType('priority-shift')).toBe('priority-shift')
    expect(normalizeDirectiveType('priority')).toBe('priority-shift')
    expect(normalizeDirectiveType('prioritize')).toBe('priority-shift')
  })

  it('normalizes cancel variants', () => {
    expect(normalizeDirectiveType('cancel')).toBe('cancel')
    expect(normalizeDirectiveType('stop')).toBe('cancel')
    expect(normalizeDirectiveType('abort')).toBe('cancel')
  })

  it('returns null for unknown types', () => {
    expect(normalizeDirectiveType('unknown')).toBeNull()
    expect(normalizeDirectiveType('invalid')).toBeNull()
    expect(normalizeDirectiveType('')).toBeNull()
  })
})


describe('normalizeUrgency', () => {
  it('normalizes low urgency', () => {
    expect(normalizeUrgency('low')).toBe('low')
  })

  it('normalizes medium variants', () => {
    expect(normalizeUrgency('medium')).toBe('medium')
    expect(normalizeUrgency('med')).toBe('medium')
    expect(normalizeUrgency('moderate')).toBe('medium')
  })

  it('normalizes high urgency', () => {
    expect(normalizeUrgency('high')).toBe('high')
  })

  it('normalizes critical variants', () => {
    expect(normalizeUrgency('critical')).toBe('critical')
    expect(normalizeUrgency('urgent')).toBe('critical')
  })

  it('returns null for unknown urgency', () => {
    expect(normalizeUrgency('unknown')).toBeNull()
    expect(normalizeUrgency('')).toBeNull()
  })
})


describe('extractFilePaths', () => {
  it('extracts from object with path field', () => {
    const args = { path: '/src/file.ts' }
    expect(extractFilePaths(args)).toEqual(['/src/file.ts'])
  })

  it('extracts from object with relative_path field', () => {
    const args = { relative_path: 'src/file.ts' }
    expect(extractFilePaths(args)).toEqual(['src/file.ts'])
  })

  it('extracts from object with filePath field', () => {
    const args = { filePath: 'core/intelligence/file.ts' }
    expect(extractFilePaths(args)).toEqual(['core/intelligence/file.ts'])
  })

  it('extracts multiple path fields', () => {
    const args = { path: '/a.ts', file: '/b.ts' }
    expect(extractFilePaths(args)).toEqual(['/a.ts', '/b.ts'])
  })

  it('extracts from JSON string', () => {
    const args = '{"path":"/src/file.ts"}'
    expect(extractFilePaths(args)).toEqual(['/src/file.ts'])
  })

  it('returns empty array for invalid JSON string', () => {
    expect(extractFilePaths('not json')).toEqual([])
  })

  it('returns empty array for non-object', () => {
    expect(extractFilePaths('string value')).toEqual([])
    expect(extractFilePaths(123)).toEqual([])
    expect(extractFilePaths(null)).toEqual([])
    expect(extractFilePaths(undefined)).toEqual([])
  })

  it('skips non-string path values', () => {
    const args = { path: { nested: 'value' } }
    expect(extractFilePaths(args)).toEqual([])
  })
})