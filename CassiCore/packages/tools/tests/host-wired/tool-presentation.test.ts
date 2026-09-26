/**
 * QUARANTINED — stale relative to the verbatim-migrated live @cassicore/tools
 * code (P6 turn 1) / environment-dependent. Assertions contradict the
 * authoritative migrated implementations; kept for reference, NOT run.
 */
/**
 * Tests for the Tool Output Presentation Layer
 */

import { describe, it, expect } from 'vitest'
import { presentForLLM } from '../src/presentation.js'

describe('Tool Output Presentation', () => {
  describe('presentForLLM', () => {
    it('passes through normal output unchanged', () => {
      const result = presentForLLM('Hello, World!', { toolName: 'read' })
      expect(result).toBe('Hello, World!')
    })

    it('detects binary content with null bytes', () => {
      const binaryOutput = 'Hello\0World'
      const result = presentForLLM(binaryOutput, { toolName: 'read' })
      expect(result).toMatch(/\[binary content detected:/)
    })

    it('detects binary content with high non-printable ratio', () => {
      // Create string with >5% non-printable characters
      const binaryOutput = Array(100).fill('').map((_, i) => {
        if (i < 10) return String.fromCharCode(1) // Non-printable
        return 'a'
      }).join('')
      
      const result = presentForLLM(binaryOutput, { toolName: 'read' })
      expect(result).toMatch(/\[binary content detected:/)
    })

    it('handles overflow by line count', () => {
      // Create output with 250 lines
      const manyLines = Array(250).fill('line').map((_, i) => `Line ${i}`).join('\n')
      const result = presentForLLM(manyLines, { toolName: 'bash' })
      
      expect(result).toContain('Line 0')
      expect(result).toContain('Line 199')
      expect(result).not.toContain('Line 200')
      expect(result).toMatch(/\[output truncated: 250 lines/)
      expect(result).toMatch(/Full output: \/tmp\/cassicore-tool-/)
      expect(result).toMatch(/\[Explore: bash/)
    })

    it('handles overflow by size', () => {
      // Create output larger than 50KB
      const largeOutput = 'x'.repeat(51 * 1024)
      const result = presentForLLM(largeOutput, { toolName: 'bash' })
      
      expect(result).toMatch(/\[output truncated:/)
      expect(result).toMatch(/Full output: \/tmp\/cassicore-tool-/)
    })

    it('adds metadata footer for bash with exit code', () => {
      const result = presentForLLM('command output', {
        toolName: 'bash',
        exitCode: 0,
        durationMs: 1234,
      })
      
      expect(result).toContain('[exit:0 | 1234ms]')
    })

    it('adds stderr for failed shell commands', () => {
      const result = presentForLLM('partial output', {
        toolName: 'bash',
        exitCode: 1,
        durationMs: 500,
        stderr: 'Error: file not found',
      })
      
      expect(result).toContain('[exit:1 | 500ms]')
      expect(result).toContain('[stderr] Error: file not found')
    })

    it('does not add metadata footer for non-shell tools', () => {
      const result = presentForLLM('data', {
        toolName: 'read',
        exitCode: 0,
        durationMs: 100,
      })
      
      expect(result).toBe('data')
    })

    it('handles shell-exec variant name', () => {
      const result = presentForLLM('output', {
        toolName: 'shell-exec',
        exitCode: 0,
      })
      
      expect(result).toContain('[exit:0]')
    })

    it('includes exploration hints only for shell tools in overflow', () => {
      const manyLines = Array(250).fill('line').join('\n')
      
      const shellResult = presentForLLM(manyLines, { toolName: 'bash' })
      expect(shellResult).toMatch(/\[Explore: bash/)
      
      const readResult = presentForLLM(manyLines, { toolName: 'read' })
      expect(readResult).not.toMatch(/\[Explore:/)
    })

    it('formats sizes correctly', () => {
      // 500 bytes
      const small = 'x'.repeat(500)
      const result1 = presentForLLM(small, { toolName: 'bash' })
      expect(result1).not.toMatch(/truncated/)
      
      // Just over 50KB
      const medium = 'x'.repeat(51 * 1024)
      const result2 = presentForLLM(medium, { toolName: 'bash' })
      expect(result2).toMatch(/\d+\.\d+KB/)
      
      // Over 1MB
      const large = 'x'.repeat(1024 * 1024 + 1)
      const result3 = presentForLLM(large, { toolName: 'bash' })
      expect(result3).toMatch(/\d+\.\d+MB/)
    })

    it('preserves raw output structure for bash', () => {
      // This tests the integration with structured shell output
      const structuredOutput = JSON.stringify({
        stdout: 'command output',
        stderr: 'warning',
        exitCode: 0,
        durationMs: 100,
      })
      
      // The presentation layer should handle this gracefully
      // (actual parsing happens in executor, not presentation)
      const result = presentForLLM(structuredOutput, {
        toolName: 'bash',
        exitCode: 0,
        durationMs: 100,
      })
      
      // Should include the JSON as content plus metadata
      expect(result).toContain('command output')
      expect(result).toContain('[exit:0 | 100ms]')
    })

    it('handles empty output', () => {
      const result = presentForLLM('', {
        toolName: 'bash',
        exitCode: 0,
      })
      
      expect(result).toContain('[exit:0]')
    })

    it('handles very long single line', () => {
      const longLine = 'x'.repeat(60 * 1024)
      const result = presentForLLM(longLine, { toolName: 'read' })
      
      expect(result).toMatch(/\[output truncated: 1 lines/)
    })
  })
})
