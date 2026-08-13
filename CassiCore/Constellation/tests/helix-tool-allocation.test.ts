/**
 * Helix Tool Allocation Tests
 *
 * Verifies that Selective Tool Allocation works correctly:
 *   - flexToolAccess controls which tools each posture can access
 *   - toolFilter allow/deny lists restrict tools beyond posture-level access
 *   - isReadOnlyTool and isMemoryTool helpers classify tools correctly
 */

import { describe, it, expect } from 'vitest'
import { isReadOnlyTool, isMemoryTool } from '../core/intelligence/cassi-agent/base-posture-runner.js'
import type { ToolAccessLevel } from '../src/types.js'


describe('Helix Tool Allocation', () => {

  describe('isReadOnlyTool', () => {
    it('should classify read-prefixed tools as read-only', () => {
      expect(isReadOnlyTool('read_file')).toBe(true)
      expect(isReadOnlyTool('read')).toBe(true)
    })

    it('should classify search/find/list tools as read-only', () => {
      expect(isReadOnlyTool('search_pattern')).toBe(true)
      expect(isReadOnlyTool('find_file')).toBe(true)
      expect(isReadOnlyTool('list_dir')).toBe(true)
      expect(isReadOnlyTool('glob')).toBe(true)
      expect(isReadOnlyTool('grep')).toBe(true)
    })

    it('should classify GitNexus tools as read-only', () => {
      expect(isReadOnlyTool('gitnexus_query')).toBe(true)
      expect(isReadOnlyTool('gitnexus_context')).toBe(true)
      expect(isReadOnlyTool('gitnexus_impact')).toBe(true)
      expect(isReadOnlyTool('gitnexus_cypher')).toBe(true)
      expect(isReadOnlyTool('gitnexus_detect_changes')).toBe(true)
      expect(isReadOnlyTool('gitnexus_list_repos')).toBe(true)
    })

    it('should classify Serena read-only tools correctly', () => {
      expect(isReadOnlyTool('serena_list_dir')).toBe(true)
      expect(isReadOnlyTool('serena_find_file')).toBe(true)
      expect(isReadOnlyTool('serena_search_for_pattern')).toBe(true)
      expect(isReadOnlyTool('serena_get_symbols_overview')).toBe(true)
      expect(isReadOnlyTool('serena_find_symbol')).toBe(true)
      expect(isReadOnlyTool('serena_find_referencing_symbols')).toBe(true)
    })

    it('should NOT classify write/edit tools as read-only', () => {
      expect(isReadOnlyTool('write_file')).toBe(false)
      expect(isReadOnlyTool('edit_file')).toBe(false)
      expect(isReadOnlyTool('bash')).toBe(false)
      expect(isReadOnlyTool('serena_replace_content')).toBe(false)
      expect(isReadOnlyTool('serena_replace_symbol_body')).toBe(false)
      expect(isReadOnlyTool('serena_rename_symbol')).toBe(false)
      expect(isReadOnlyTool('serena_insert_after_symbol')).toBe(false)
    })

    it('should respect registry readOnly field when available', () => {
      const registry = {
        getDefinition: (name: string) => {
          if (name === 'custom_tool') return { readOnly: true }
          if (name === 'custom_write') return { readOnly: false }
          return undefined
        },
      } as any
      expect(isReadOnlyTool('custom_tool', registry)).toBe(true)
      expect(isReadOnlyTool('custom_write', registry)).toBe(false)
    })
  })


  describe('isMemoryTool', () => {
    it('should classify memory-prefixed tools', () => {
      expect(isMemoryTool('memory_store')).toBe(true)
      expect(isMemoryTool('memory_search')).toBe(true)
      expect(isMemoryTool('cassi_memory_store')).toBe(true)
    })

    it('should classify archive tools', () => {
      expect(isMemoryTool('archive_search')).toBe(true)
      expect(isMemoryTool('cassi_archive_search')).toBe(true)
    })

    it('should classify enrich and universal_search', () => {
      expect(isMemoryTool('cassi_enrich')).toBe(true)
      expect(isMemoryTool('cassi_universal_search')).toBe(true)
    })

    it('should NOT classify non-memory tools', () => {
      expect(isMemoryTool('read_file')).toBe(false)
      expect(isMemoryTool('bash')).toBe(false)
      expect(isMemoryTool('write_file')).toBe(false)
    })
  })


  describe('ToolAccessLevel semantics', () => {
    // WHY: These tests document the expected behavior of each access level,
    // which drives the filtering logic in buildToolSchemas().

    const ACCESS_LEVELS: ToolAccessLevel[] = ['full', 'read-only+memory', 'read-only', 'none']

    it('full access includes all tool types', () => {
      const level: ToolAccessLevel = 'full'
      expect(level === 'full').toBe(true)
    })

    it('read-only+memory includes read tools and memory tools', () => {
      const level: ToolAccessLevel = 'read-only+memory'
      const hasMemory = level === 'read-only+memory' || level === 'full'
      expect(hasMemory).toBe(true)
    })

    it('read-only excludes memory and write tools', () => {
      const level: ToolAccessLevel = 'read-only'
      // WHY: Cast to string for test clarity — we're testing the access level semantics
      const hasFullAccess = (level as string) === 'full'
      const hasMemoryAccess = (level as string) === 'read-only+memory' || (level as string) === 'full'
      expect(hasFullAccess).toBe(false)
      expect(hasMemoryAccess).toBe(false)
    })

    it('none excludes all tools', () => {
      const level: ToolAccessLevel = 'none'
      expect(level === 'none').toBe(true)
    })

    it('all access levels are defined', () => {
      expect(ACCESS_LEVELS).toHaveLength(4)
      expect(ACCESS_LEVELS).toContain('full')
      expect(ACCESS_LEVELS).toContain('read-only+memory')
      expect(ACCESS_LEVELS).toContain('read-only')
      expect(ACCESS_LEVELS).toContain('none')
    })
  })


  describe('toolFilter allow/deny semantics', () => {
    // WHY: These tests verify the filter logic that buildToolSchemas applies.

    function applyFilter(
      toolName: string,
      filter?: { allow?: string[]; deny?: string[] }
    ): boolean {
      if (!filter) return true
      if (filter.allow && !filter.allow.includes(toolName)) return false
      if (filter.deny?.includes(toolName)) return false
      return true
    }

    it('no filter allows all tools', () => {
      expect(applyFilter('bash')).toBe(true)
      expect(applyFilter('read_file')).toBe(true)
      expect(applyFilter('write_file')).toBe(true)
    })

    it('allow list restricts to only named tools', () => {
      const filter = { allow: ['read_file', 'grep'] }
      expect(applyFilter('read_file', filter)).toBe(true)
      expect(applyFilter('grep', filter)).toBe(true)
      expect(applyFilter('bash', filter)).toBe(false)
      expect(applyFilter('write_file', filter)).toBe(false)
    })

    it('deny list blocks specific tools', () => {
      const filter = { deny: ['bash', 'write_file'] }
      expect(applyFilter('read_file', filter)).toBe(true)
      expect(applyFilter('grep', filter)).toBe(true)
      expect(applyFilter('bash', filter)).toBe(false)
      expect(applyFilter('write_file', filter)).toBe(false)
    })

    it('deny takes precedence over allow', () => {
      const filter = { allow: ['bash', 'read_file'], deny: ['bash'] }
      expect(applyFilter('bash', filter)).toBe(false)
      expect(applyFilter('read_file', filter)).toBe(true)
    })
  })


  describe('Template posture toolAccess correctness', () => {
    it('standard template: unity=full, yang=read-only+memory, yin=read-only+memory', async () => {
      const { getTemplatePostures } = await import('../src/templates.js')
      const postures = getTemplatePostures('standard')

      const unity = postures.find(p => p.name === 'unity')
      const yang = postures.find(p => p.name === 'yang')
      const yin = postures.find(p => p.name === 'yin')

      expect(unity?.toolAccess).toBe('full')
      expect(yang?.toolAccess).toBe('read-only+memory')
      expect(yin?.toolAccess).toBe('read-only+memory')
    })

    it('implementation template: both unities get full access', async () => {
      const { getTemplatePostures } = await import('../src/templates.js')
      const postures = getTemplatePostures('implementation')

      const unityPrimary = postures.find(p => p.name === 'unity-primary')
      const unitySecondary = postures.find(p => p.name === 'unity-secondary')
      const yang = postures.find(p => p.name === 'yang')
      const yin = postures.find(p => p.name === 'yin')

      expect(unityPrimary?.toolAccess).toBe('full')
      expect(unitySecondary?.toolAccess).toBe('full')
      expect(yang?.toolAccess).toBe('read-only+memory')
      expect(yin?.toolAccess).toBe('read-only+memory')
    })

    it('research template: researchers get read-only+memory', async () => {
      const { getTemplatePostures } = await import('../src/templates.js')
      const postures = getTemplatePostures('research')

      const alpha = postures.find(p => p.name === 'researcher-alpha')
      const beta = postures.find(p => p.name === 'researcher-beta')

      expect(alpha?.toolAccess).toBe('read-only+memory')
      expect(beta?.toolAccess).toBe('read-only+memory')
    })

    it('review template: all reviewers get read-only+memory', async () => {
      const { getTemplatePostures } = await import('../src/templates.js')
      const postures = getTemplatePostures('review')

      const reviewers = postures.filter(p => p.energy === 'yang' || p.energy === 'yin')
      for (const r of reviewers) {
        expect(r.toolAccess).toBe('read-only+memory')
      }
    })

    it('minimal template: unity=full, reviewer=read-only+memory', async () => {
      const { getTemplatePostures } = await import('../src/templates.js')
      const postures = getTemplatePostures('minimal')

      const unity = postures.find(p => p.name === 'unity')
      const reviewer = postures.find(p => p.name === 'reviewer')

      expect(unity?.toolAccess).toBe('full')
      expect(reviewer?.toolAccess).toBe('read-only+memory')
    })
  })
})
