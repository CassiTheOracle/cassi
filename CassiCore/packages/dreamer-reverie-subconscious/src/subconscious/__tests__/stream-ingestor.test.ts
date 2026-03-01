/**
 * StreamIngestor Tests
 */
// @ts-nocheck

import { describe, it, expect, beforeEach, jest } from '@jest/globals'
import { StreamIngestorImpl, createStreamIngestor } from '../stream-ingestor.js'
import { DEFAULT_SUBCONSCIOUS_CONFIG_V2 } from '../types.js'

const mockLogger = {
  child: () => mockLogger,
  debug: jest.fn(),
  info: jest.fn(),
  warn: jest.fn(),
  error: jest.fn(),
}

const mockEventBus = {
  emit: jest.fn(),
  on: jest.fn(),
}

describe('StreamIngestor', () => {
  let ingestor: StreamIngestorImpl

  beforeEach(() => {
    jest.clearAllMocks()
    ingestor = createStreamIngestor(
      DEFAULT_SUBCONSCIOUS_CONFIG_V2.stream,
      mockLogger as any,
      mockEventBus as any
    )
  })

  describe('Token Buffering', () => {
    it('should create buffer on first token', () => {
      ingestor.onToken('session-1', 'Hello')
      const buffer = ingestor.getBuffer('session-1')
      expect(buffer).toBeDefined()
      expect(buffer?.getText()).toBe('Hello')
    })

    it('should accumulate tokens', () => {
      ingestor.onToken('session-1', 'Hello')
      ingestor.onToken('session-1', ' ')
      ingestor.onToken('session-1', 'World')
      const buffer = ingestor.getBuffer('session-1')
      expect(buffer?.getText()).toBe('Hello World')
    })

    it('should maintain separate buffers per session', () => {
      ingestor.onToken('session-1', 'A')
      ingestor.onToken('session-2', 'B')
      expect(ingestor.getBuffer('session-1')?.getText()).toBe('A')
      expect(ingestor.getBuffer('session-2')?.getText()).toBe('B')
    })
  })

  describe('Thinking Blocks', () => {
    it('should accumulate thinking separately', () => {
      ingestor.onThinking('session-1', 'Let me think...')
      ingestor.onThinking('session-1', 'The answer is clear.')
      const buffer = ingestor.getBuffer('session-1')
      expect(buffer?.getThinking()).toBe('Let me think...The answer is clear.')
    })
  })

  describe('Tool Calls', () => {
    it('should track tool calls', () => {
      ingestor.onToolCall('session-1', 'read_file', { path: '/test.txt' })
      const buffer = ingestor.getBuffer('session-1')
      expect(buffer?.getToolHistory()).toHaveLength(1)
      expect(buffer?.getToolHistory()[0].tool).toBe('read_file')
    })

    it('should match tool results to calls', () => {
      ingestor.onToolCall('session-1', 'read_file', { path: '/test.txt' })
      ingestor.onToolResult('session-1', 'read_file', 'file content')
      const buffer = ingestor.getBuffer('session-1')
      expect(buffer?.getToolHistory()[0].result).toBe('file content')
    })
  })

  describe('Event Emission', () => {
    it('should emit token events', () => {
      ingestor.onToken('session-1', 'test')
      expect(mockEventBus.emit).toHaveBeenCalledWith(
        expect.objectContaining({
          type: 'subconscious:token',
          sessionId: 'session-1',
          token: 'test',
        })
      )
    })

    it('should emit buffer updated events', () => {
      ingestor.onToken('session-1', 'test')
      expect(mockEventBus.emit).toHaveBeenCalledWith(
        expect.objectContaining({
          type: 'subconscious:buffer:updated',
          sessionId: 'session-1',
        })
      )
    })
  })

  describe('Session Management', () => {
    it('should list active sessions', () => {
      ingestor.onToken('session-1', 'A')
      ingestor.onToken('session-2', 'B')
      expect(ingestor.getActiveSessions()).toContain('session-1')
      expect(ingestor.getActiveSessions()).toContain('session-2')
    })

    it('should cleanup sessions', () => {
      ingestor.onToken('session-1', 'A')
      ingestor.cleanupSession('session-1')
      expect(ingestor.getBuffer('session-1')).toBeUndefined()
    })
  })
})
