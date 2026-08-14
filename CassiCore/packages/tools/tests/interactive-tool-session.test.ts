import { beforeEach, describe, expect, it, vi } from 'vitest'

import {
  InteractiveToolSession,
  splitForTelegram,
  type ToolDefinition,
} from '../src/interactive-tool-session.js'

describe('InteractiveToolSession', () => {
  const fetchMock = vi.fn()

  beforeEach(() => {
    fetchMock.mockReset()
    vi.stubGlobal('fetch', fetchMock)
  })

  it('prompts for required parameters when they are missing', async () => {
    const tool: ToolDefinition = {
      name: 'memory_search',
      description: 'Search memory',
      inputSchema: {
        type: 'object',
        properties: {
          query: { type: 'string', description: 'Search query' },
          limit: { type: 'number', description: 'Max results' },
        },
        required: ['query'],
      },
    }

    const session = new InteractiveToolSession('memory_search', tool)
    const result = await session.start()

    expect('prompt' in result).toBe(true)
    if ('prompt' in result) {
      expect(result.prompt).toContain('memory_search')
      expect(result.prompt).toContain('query')
    }
  })

  it('executes immediately when all required inline params are present', async () => {
    fetchMock.mockResolvedValue({
      ok: true,
      json: async () => ({ content: [{ type: 'text', text: 'ok' }], isError: false }),
    })

    const tool: ToolDefinition = {
      name: 'memory_search',
      description: 'Search memory',
      inputSchema: {
        type: 'object',
        properties: {
          query: { type: 'string' },
        },
        required: ['query'],
      },
    }

    const session = new InteractiveToolSession('memory_search', tool)
    const result = await session.start({ query: 'cassi' })

    expect('result' in result).toBe(true)
    if ('result' in result) {
      expect(result.result).toBe('ok')
      expect(result.isError).toBe(false)
    }
    expect(fetchMock).toHaveBeenCalledOnce()
  })

  it('requires confirmation for dangerous tools', async () => {
    const tool: ToolDefinition = {
      name: 'bash',
      description: 'Run shell command',
      inputSchema: {
        type: 'object',
        properties: {
          command: { type: 'string' },
        },
        required: ['command'],
      },
    }

    const session = new InteractiveToolSession('bash', tool)
    const result = await session.start({ command: 'ls -la' })

    expect('prompt' in result).toBe(true)
    if ('prompt' in result) {
      expect(result.prompt).toContain('/confirm')
      expect(result.prompt).toContain('bash')
    }
  })

  it('supports skipping optional params after filling a required one', async () => {
    fetchMock.mockResolvedValue({
      ok: true,
      json: async () => ({ content: [{ type: 'text', text: 'done' }], isError: false }),
    })

    const tool: ToolDefinition = {
      name: 'memory_search',
      description: 'Search memory',
      inputSchema: {
        type: 'object',
        properties: {
          query: { type: 'string' },
          limit: { type: 'number', default: 10 },
        },
        required: ['query'],
      },
    }

    const session = new InteractiveToolSession('memory_search', tool)
    const start = await session.start()
    expect('prompt' in start).toBe(true)

    const afterRequired = await session.receiveInput('architecture')
    expect('prompt' in afterRequired).toBe(true)
    if ('prompt' in afterRequired) {
      expect(afterRequired.prompt).toContain('/skip')
    }

    const skipped = await session.skip()
    expect('result' in skipped).toBe(true)
    if ('result' in skipped) {
      expect(skipped.result).toBe('done')
    }
  })
})

describe('splitForTelegram', () => {
  it('splits long output into numbered chunks', () => {
    const text = 'x'.repeat(8000)
    const chunks = splitForTelegram(text, 3000)
    expect(chunks.length).toBe(3)
    expect(chunks[0].startsWith('[1/3]')).toBe(true)
    expect(chunks[2].startsWith('[3/3]')).toBe(true)
  })
})
