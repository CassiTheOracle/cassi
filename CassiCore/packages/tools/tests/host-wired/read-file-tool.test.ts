/**
 * QUARANTINED — stale relative to the verbatim-migrated live @cassicore/tools
 * code (P6 turn 1) / environment-dependent. Assertions contradict the
 * authoritative migrated implementations; kept for reference, NOT run.
 */
/**
 * read_file Tool Tests
 *
 * Tests the read_file tool implementation including:
 * - Reading a file returns content with line numbers
 * - Reading non-existent file returns error message
 * - Tool handler integration with proper context
 * - Temporary directory fixtures with setup/teardown
 * - Error handling for non-existent files
 * - Large file truncation (1MB limit enforcement)
 */

import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest'
import { readFileHandler, readFileDefinition } from '../src/implementations/read-file.js'
import type { ToolExecutionContext } from '../src/types.js'

describe('read_file tool', () => {
  let tmpDir: string
  let testFilePath: string
  let testFileContent: string
  let context: ToolExecutionContext

  beforeEach(async () => {
    // Create temporary directory
    const tmp = await import('node:fs/promises')
    const os = await import('node:os')
    const path = await import('node:path')
    
    tmpDir = await tmp.mkdtemp(path.join(os.tmpdir(), 'read-file-test-'))
    testFilePath = path.join(tmpDir, 'test-file.txt')
    
    // Create test file with content
    testFileContent = `Line 1: First line of text
Line 2: Second line with some content
Line 3: Third line for testing
Line 4: Fourth and final line`
    
    await tmp.writeFile(testFilePath, testFileContent, 'utf-8')
    
    // Setup tool execution context
    const mockLogger = {
      debug: vi.fn(),
      info: vi.fn(),
      warn: vi.fn(),
      error: vi.fn(),
      child: vi.fn(() => mockLogger),
    }
    
    context = {
      sessionId: 'test-session-123',
      workingDir: tmpDir,
      allowedPaths: [tmpDir],
      networkAllowlist: ['*'],
      logger: mockLogger as any,
    }
  })

  afterEach(async () => {
    // Cleanup temporary directory
    if (tmpDir) {
      const tmp = await import('node:fs/promises')
      try {
        await tmp.rm(tmpDir, { recursive: true, force: true })
      } catch (err) {
        // Ignore cleanup errors
      }
    }
  })

  describe('reading existing file', () => {
    it('returns file content with line numbers when reading a file', async () => {
      const result = await readFileHandler({ path: testFilePath }, context)
      
      // Verify content is returned
      expect(result).toContain('Line 1: First line of text')
      expect(result).toContain('Line 2: Second line with some content')
      expect(result).toContain('Line 3: Third line for testing')
      expect(result).toContain('Line 4: Fourth and final line')
      
      // Verify no error message
      expect(result).not.toContain('Error reading file')
      expect(result).not.toContain('file not found')
    })

    it('supports reading with offset parameter', async () => {
      const result = await readFileHandler({ path: testFilePath, offset: 2 }, context)
      
      // Should start from line 2
      expect(result).toContain('Line 2: Second line with some content')
      expect(result).toContain('Line 3: Third line for testing')
      expect(result).toContain('Line 4: Fourth and final line')
      
      // Should NOT contain line 1
      expect(result).not.toContain('Line 1: First line of text')
    })

    it('supports reading with limit parameter', async () => {
      const result = await readFileHandler({ path: testFilePath, limit: 2 }, context)
      
      // Should contain only first 2 lines
      expect(result).toContain('Line 1: First line of text')
      expect(result).toContain('Line 2: Second line with some content')
      
      // Should NOT contain lines 3 and 4
      expect(result).not.toContain('Line 3: Third line for testing')
      expect(result).not.toContain('Line 4: Fourth and final line')
    })

    it('supports reading with both offset and limit parameters', async () => {
      const result = await readFileHandler({ path: testFilePath, offset: 2, limit: 2 }, context)
      
      // Should contain lines 2 and 3
      expect(result).toContain('Line 2: Second line with some content')
      expect(result).toContain('Line 3: Third line for testing')
      
      // Should NOT contain lines 1 and 4
      expect(result).not.toContain('Line 1: First line of text')
      expect(result).not.toContain('Line 4: Fourth and final line')
    })
  })

  describe('error handling - non-existent files', () => {
    it('throws when reading non-existent file within allowed paths', async () => {
      const nonExistentPath = `${tmpDir}/nonexistent-file.txt`

      await expect(readFileHandler({ path: nonExistentPath }, context))
        .rejects.toThrow(/file not found/)
    })

    it('throws with specific error format for non-existent files', async () => {
      const nonExistentPath = `${tmpDir}/does-not-exist.md`

      await expect(readFileHandler({ path: nonExistentPath }, context))
        .rejects.toThrow(/file not found —/)
    })

    it('throws when reading file outside allowed paths', async () => {
      const outsidePath = '/etc/hosts' // Outside tmpDir

      await expect(readFileHandler({ path: outsidePath }, context))
        .rejects.toThrow(/access denied/)
    })

    it('throws isError-eligible exception when reading a directory (not a file)', async () => {
      // WHY: Constellation prompt-log evidence showed read_file({path: directory})
      // returning "Error reading file: ... not a file —" with isError=false. The handler
      // must now throw so the executor produces isError=true.
      await expect(readFileHandler({ path: tmpDir }, context))
        .rejects.toThrow(/not a file/)
    })
  })

  describe('large file handling - 1MB truncation', () => {
    it('truncates files larger than 1MB and includes truncation message', async () => {
      const tmp = await import('node:fs/promises')
      const path = await import('node:path')
      
      // Create a file larger than 1MB (1.5MB)
      const largeFilePath = path.join(tmpDir, 'large-file.txt')
      const oneLine = 'A'.repeat(100) + '\n' // 101 bytes per line
      const linesNeeded = Math.ceil((1.5 * 1024 * 1024) / 101) // ~15,360 lines
      
      let content = ''
      for (let i = 0; i < linesNeeded; i++) {
        content += oneLine
      }
      
      await tmp.writeFile(largeFilePath, content, 'utf-8')
      
      const result = await readFileHandler({ path: largeFilePath }, context)
      
      // Verify truncation message is present
      expect(result).toContain('file truncated at 1MB')
      expect(result).toContain('total file size is')
      
      // Verify some content is still readable
      expect(result).toContain('A'.repeat(100))
      
      // Verify result length is reasonable (should be around 1MB + truncation message)
      expect(result.length).toBeGreaterThan(1024 * 1024) // Should have at least 1MB of content
    })

    it('does not truncate files smaller than 1MB', async () => {
      const tmp = await import('node:fs/promises')
      const path = await import('node:path')
      
      // Create a file smaller than 1MB (500KB)
      const smallFilePath = path.join(tmpDir, 'small-file.txt')
      const oneLine = 'B'.repeat(100) + '\n' // 101 bytes per line
      const linesNeeded = Math.ceil((500 * 1024) / 101) // ~5,050 lines
      
      let content = ''
      for (let i = 0; i < linesNeeded; i++) {
        content += oneLine
      }
      
      await tmp.writeFile(smallFilePath, content, 'utf-8')
      
      const result = await readFileHandler({ path: smallFilePath }, context)
      
      // Verify NO truncation message
      expect(result).not.toContain('file truncated at 1MB')
      
      // Verify all content is present
      expect(result).toContain('B'.repeat(100))
    })
  })

  describe('tool definition', () => {
    it('has correct name and description', () => {
      expect(readFileDefinition.name).toBe('read_file')
      expect(readFileDefinition.description).toContain('Read the contents of a file')
    })

    it('has required path parameter', () => {
      expect(readFileDefinition.parameters.required).toContain('path')
    })

    it('supports optional offset and limit parameters', () => {
      const props = readFileDefinition.parameters.properties
      expect(props.offset).toBeDefined()
      expect(props.limit).toBeDefined()
      expect(props.offset.type).toBe('number')
      expect(props.limit.type).toBe('number')
    })

    it('is marked as read-only and has appropriate timeout', () => {
      expect(readFileDefinition.readOnly).toBe(true)
      expect(readFileDefinition.timeoutMs).toBe(10_000)
    })
  })

  describe('context integration', () => {
    it('uses working directory when resolving relative paths', async () => {
      const fileName = 'test-file.txt'
      const result = await readFileHandler({ path: fileName }, context)
      
      // Should resolve relative to workingDir and find the file
      expect(result).toContain('Line 1: First line of text')
      expect(result).not.toContain('Error reading file')
    })

    it('logs debug information when file is read successfully', async () => {
      await readFileHandler({ path: testFilePath }, context)
      
      // Verify logger was called
      expect(context.logger.debug).toHaveBeenCalled()
    })
  })
})
