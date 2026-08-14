/**
 * QUARANTINED — stale relative to the verbatim-migrated live @cassicore/tools
 * code (P6 turn 1) / environment-dependent. Assertions contradict the
 * authoritative migrated implementations; kept for reference, NOT run.
 */
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { ToolExecutor } from '../src/executor.js';
import { ToolRegistry } from '../src/registry.js';
import type { ToolDefinition, ToolHandler, ToolExecutionContext, ToolCall } from '../src/types.js';
import type { IEventBus, ILogger } from '@cassicore/foundation';

/**
 * ToolExecutor — Executes tool calls with safety guards and error handling.
 *
 * The ToolExecutor provides:
 * - Tool lookup with MCP server preference resolution
 * - Safety validation (input and output)
 * - Timeout enforcement
 * - Error handling and containment
 * - Concurrent execution with batching
 * - Event emission for monitoring
 */
describe('ToolExecutor', () => {
  let registry: ToolRegistry;
  let executor: ToolExecutor;
  let mockEventBus: IEventBus;
  let mockLogger: ILogger;
  let defaultContext: Omit<ToolExecutionContext, 'sessionId'>;

  beforeEach(() => {
    registry = new ToolRegistry();

    mockLogger = {
      info: vi.fn(),
      warn: vi.fn(),
      error: vi.fn(),
      debug: vi.fn(),
      child: () => mockLogger,
    };

    mockEventBus = {
      emit: vi.fn(),
      on: vi.fn(),
      off: vi.fn(),
      once: vi.fn(),
      onAll: vi.fn(),
      listenerCount: vi.fn().mockReturnValue(0),
    };

    defaultContext = {
      workingDir: '/test',
      allowedPaths: ['/test'],
      networkAllowlist: ['*'],
      logger: mockLogger,
    };

    executor = new ToolExecutor(registry, defaultContext, mockEventBus);
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  /**
   * Execution — executes a registered tool with params
   */
  describe('execute', () => {
    it('executes a registered tool with input parameters', async () => {
      const handler = vi.fn().mockResolvedValue('execution result');

      registry.register(
        {
          name: 'test_tool',
          description: 'A test tool',
          parameters: {
            type: 'object',
            properties: {
              param1: { type: 'string' },
            },
            required: ['param1'],
          },
        },
        handler
      );

      const toolCall: ToolCall = {
        id: 'call-1',
        name: 'test_tool',
        input: { param1: 'test value' },
      };

      const result = await executor.execute(toolCall, 'session-123');

      expect(result.toolCallId).toBe('call-1');
      expect(result.content).toBe('execution result');
      expect(result.isError).toBe(false);
      expect(handler).toHaveBeenCalledWith(
        { param1: 'test value' },
        expect.objectContaining({
          sessionId: 'session-123',
          workingDir: '/test',
        })
      );
    });

    it('passes correct context to the handler', async () => {
      const handler = vi.fn().mockResolvedValue('done');

      registry.register(
        {
          name: 'context_test',
          description: 'Tests context passing',
          parameters: { type: 'object', properties: {} },
        },
        handler
      );

      const toolCall: ToolCall = {
        id: 'call-ctx',
        name: 'context_test',
        input: {},
      };

      await executor.execute(toolCall, 'session-abc');

      const passedContext = handler.mock.calls[0][1] as ToolExecutionContext;
      expect(passedContext.sessionId).toBe('session-abc');
      expect(passedContext.workingDir).toBe('/test');
      expect(passedContext.allowedPaths).toEqual(['/test']);
      expect(passedContext.networkAllowlist).toEqual(['*']);
      expect(passedContext.logger).toBe(mockLogger);
    });

    it('respects custom timeout from tool definition', async () => {
      const handler = vi.fn().mockImplementation(async () => {
        await new Promise(resolve => setTimeout(resolve, 5000));
        return 'slow result';
      });

      registry.register(
        {
          name: 'slow_tool',
          description: 'A slow tool',
          parameters: { type: 'object', properties: {} },
          timeoutMs: 50, // Very short timeout for testing
        },
        handler
      );

      const toolCall: ToolCall = {
        id: 'call-slow',
        name: 'slow_tool',
        input: {},
      };

      const result = await executor.execute(toolCall, 'session-1');

      expect(result.isError).toBe(true);
      expect(result.content).toContain('Timeout');
    });
  });

  /**
   * Error handling — handles tool execution errors
   */
  describe('error handling', () => {
    it('returns error result when handler throws an exception', async () => {
      registry.register(
        {
          name: 'failing_tool',
          description: 'A tool that always fails',
          parameters: { type: 'object', properties: {} },
        },
        vi.fn().mockRejectedValue(new Error('Something went wrong'))
      );

      const toolCall: ToolCall = {
        id: 'call-fail',
        name: 'failing_tool',
        input: {},
      };

      const result = await executor.execute(toolCall, 'session-1');

      expect(result.isError).toBe(true);
      expect(result.toolCallId).toBe('call-fail');
      expect(result.content).toContain('Something went wrong');
    });

    it('returns error result for non-Error throws', async () => {
      registry.register(
        {
          name: 'string_throw_tool',
          description: 'Throws a string',
          parameters: { type: 'object', properties: {} },
        },
        vi.fn().mockImplementation(() => {
          throw 'String error';
        })
      );

      const toolCall: ToolCall = {
        id: 'call-str',
        name: 'string_throw_tool',
        input: {},
      };

      const result = await executor.execute(toolCall, 'session-1');

      expect(result.isError).toBe(true);
      expect(result.content).toContain('String error');
    });

    it('emits safety event on execution error when eventBus is provided', async () => {
      registry.register(
        {
          name: 'error_emit_tool',
          description: 'Emits error event',
          parameters: { type: 'object', properties: {} },
        },
        vi.fn().mockRejectedValue(new Error('Fatal error'))
      );

      const toolCall: ToolCall = {
        id: 'call-emit',
        name: 'error_emit_tool',
        input: {},
      };

      await executor.execute(toolCall, 'session-xyz');

      expect(mockEventBus.emit).toHaveBeenCalledWith(
        expect.objectContaining({
          type: 'tool:safety',
          sessionId: 'session-xyz',
          toolName: 'error_emit_tool',
          eventType: 'execution',
          details: expect.arrayContaining([expect.stringContaining('Fatal error')]),
        })
      );
    });
  });

  /**
   * Timeout — handles tool execution timeout
   */
  describe('timeout handling', () => {
    it('returns error when tool exceeds timeout', async () => {
      registry.register(
        {
          name: 'timeout_tool',
          description: 'Times out',
          parameters: { type: 'object', properties: {} },
          timeoutMs: 10,
        },
        vi.fn().mockImplementation(async () => {
          await new Promise(resolve => setTimeout(resolve, 100));
          return 'too late';
        })
      );

      const toolCall: ToolCall = {
        id: 'call-timeout',
        name: 'timeout_tool',
        input: {},
      };

      const result = await executor.execute(toolCall, 'session-1');

      expect(result.isError).toBe(true);
      expect(result.content).toContain('Timeout');
    });

    it('uses default timeout (30s) when not specified', async () => {
      const handler = vi.fn().mockResolvedValue('quick result');

      registry.register(
        {
          name: 'default_timeout_tool',
          description: 'Uses default timeout',
          parameters: { type: 'object', properties: {} },
          // No timeoutMs specified
        },
        handler
      );

      const toolCall: ToolCall = {
        id: 'call-default',
        name: 'default_timeout_tool',
        input: {},
      };

      const result = await executor.execute(toolCall, 'session-1');

      expect(result.isError).toBe(false);
      expect(result.content).toBe('quick result');
    });
  });

  /**
   * Missing tool — handles executing unregistered tool
   */
  describe('missing tool handling', () => {
    it('returns error result for unknown tool', async () => {
      const toolCall: ToolCall = {
        id: 'call-unknown',
        name: 'non_existent_tool',
        input: {},
      };

      const result = await executor.execute(toolCall, 'session-1');

      expect(result.isError).toBe(true);
      expect(result.toolCallId).toBe('call-unknown');
      expect(result.content).toContain('Unknown tool');
      expect(result.content).toContain('non_existent_tool');
    });

    it('attempts MCP server fallback for file operations', async () => {
      // Register a serena-prefixed tool
      const serenaHandler = vi.fn().mockResolvedValue('serena file content');
      registry.register(
        {
          name: 'serena__read_file',
          description: 'Serena read file',
          parameters: {
            type: 'object',
            properties: {
              path: { type: 'string' },
            },
          },
        },
        serenaHandler
      );

      // Try to call with unprefixed name
      const toolCall: ToolCall = {
        id: 'call-fallback',
        name: 'read_file',
        input: { path: '/test/file.txt' },
      };

      const result = await executor.execute(toolCall, 'session-1');

      expect(result.isError).toBe(false);
      expect(result.content).toBe('serena file content');
      expect(serenaHandler).toHaveBeenCalled();
    });

    it('attempts fallback using PREFERRED_MCP_SERVERS env var', async () => {
      const originalEnv = process.env.PREFERRED_MCP_SERVERS;
      process.env.PREFERRED_MCP_SERVERS = 'custom_mcp';

      const customHandler = vi.fn().mockResolvedValue('custom result');
      registry.register(
        {
          name: 'custom_mcp__read',
          description: 'Custom MCP read',
          parameters: { type: 'object', properties: {} },
        },
        customHandler
      );

      const toolCall: ToolCall = {
        id: 'call-env',
        name: 'read',
        input: {},
      };

      const result = await executor.execute(toolCall, 'session-1');

      expect(result.isError).toBe(false);
      expect(customHandler).toHaveBeenCalled();

      // Restore env
      process.env.PREFERRED_MCP_SERVERS = originalEnv;
    });
  });

  /**
   * Result format — returns proper result structure
   */
  describe('result format', () => {
    it('returns successful result with string content', async () => {
      registry.register(
        {
          name: 'string_result_tool',
          description: 'Returns string',
          parameters: { type: 'object', properties: {} },
        },
        vi.fn().mockResolvedValue('string output')
      );

      const toolCall: ToolCall = {
        id: 'call-str',
        name: 'string_result_tool',
        input: {},
      };

      const result = await executor.execute(toolCall, 'session-1');

      expect(result).toEqual({
        toolCallId: 'call-str',
        content: 'string output',
        isError: false,
        rawContent: 'string output',
        exitCode: undefined,
        durationMs: expect.any(Number),
      });
    });

    it('converts non-string results to strings', async () => {
      registry.register(
        {
          name: 'number_result_tool',
          description: 'Returns number',
          parameters: { type: 'object', properties: {} },
        },
        vi.fn().mockResolvedValue(42)
      );

      const toolCall: ToolCall = {
        id: 'call-num',
        name: 'number_result_tool',
        input: {},
      };

      const result = await executor.execute(toolCall, 'session-1');

      expect(result.content).toBe('42');
      expect(result.isError).toBe(false);
    });

    it('preserves toolCallId in result', async () => {
      registry.register(
        {
          name: 'echo_tool',
          description: 'Echoes input',
          parameters: { type: 'object', properties: {} },
        },
        vi.fn().mockResolvedValue('echo')
      );

      const toolCall: ToolCall = {
        id: 'unique-id-12345',
        name: 'echo_tool',
        input: {},
      };

      const result = await executor.execute(toolCall, 'session-1');

      expect(result.toolCallId).toBe('unique-id-12345');
    });
  });

  /**
   * Batch execution
   */
  describe('executeAll', () => {
    it('executes multiple tool calls concurrently', async () => {
      const handler1 = vi.fn().mockResolvedValue('result1');
      const handler2 = vi.fn().mockResolvedValue('result2');

      registry.register(
        { name: 'tool1', description: 'Tool 1', parameters: { type: 'object', properties: {} } },
        handler1
      );
      registry.register(
        { name: 'tool2', description: 'Tool 2', parameters: { type: 'object', properties: {} } },
        handler2
      );

      const calls: ToolCall[] = [
        { id: 'call-1', name: 'tool1', input: {} },
        { id: 'call-2', name: 'tool2', input: {} },
      ];

      const results = await executor.executeAll(calls, 'session-1');

      expect(results).toHaveLength(2);
      expect(results[0].content).toBe('result1');
      expect(results[1].content).toBe('result2');
    });

    it('processes calls in batches of 20 (MAX_CONCURRENT)', async () => {
      const handler = vi.fn().mockResolvedValue('ok');

      registry.register(
        { name: 'batch_tool', description: 'Batch tool', parameters: { type: 'object', properties: {} } },
        handler
      );

      // Create 25 calls to test batching
      const calls: ToolCall[] = Array.from({ length: 25 }, (_, i) => ({
        id: `call-${i}`,
        name: 'batch_tool',
        input: {},
      }));

      const results = await executor.executeAll(calls, 'session-1');

      expect(results).toHaveLength(25);
      expect(handler).toHaveBeenCalledTimes(25);
    });

    it('returns errors for individual failed calls without failing entire batch', async () => {
      registry.register(
        { name: 'success_tool', description: 'Succeeds', parameters: { type: 'object', properties: {} } },
        vi.fn().mockResolvedValue('success')
      );
      registry.register(
        { name: 'fail_tool', description: 'Fails', parameters: { type: 'object', properties: {} } },
        vi.fn().mockRejectedValue(new Error('Failed'))
      );

      const calls: ToolCall[] = [
        { id: 'call-1', name: 'success_tool', input: {} },
        { id: 'call-2', name: 'fail_tool', input: {} },
        { id: 'call-3', name: 'success_tool', input: {} },
      ];

      const results = await executor.executeAll(calls, 'session-1');

      expect(results[0].isError).toBe(false);
      expect(results[1].isError).toBe(true);
      expect(results[2].isError).toBe(false);
    });
  });

  /**
   * Safety validation integration
   */
  describe('safety validation', () => {
    it('validates tool input before execution', async () => {
      // read_file has validation rules requiring 'path' parameter
      registry.register(
        {
          name: 'read_file',
          description: 'Read a file',
          parameters: {
            type: 'object',
            properties: {
              path: { type: 'string' },
              offset: { type: 'number' },
              limit: { type: 'number' },
            },
            required: ['path'],
          },
        },
        vi.fn().mockResolvedValue('content')
      );

      const toolCall: ToolCall = {
        id: 'call-bad-input',
        name: 'read_file',
        input: { offset: 0 }, // Missing required 'path'
      };

      const result = await executor.execute(toolCall, 'session-1');

      expect(result.isError).toBe(true);
      expect(result.content).toContain('Safety check failed');
    });

    it('emits safety event on input validation failure', async () => {
      registry.register(
        {
          name: 'write_file',
          description: 'Write a file',
          parameters: {
            type: 'object',
            properties: {
              path: { type: 'string' },
              content: { type: 'string' },
            },
            required: ['path', 'content'],
          },
        },
        vi.fn().mockResolvedValue('written')
      );

      const toolCall: ToolCall = {
        id: 'call-validation',
        name: 'write_file',
        input: { path: '/test.txt' }, // Missing required 'content'
      };

      await executor.execute(toolCall, 'session-1');

      expect(mockEventBus.emit).toHaveBeenCalledWith(
        expect.objectContaining({
          type: 'tool:safety',
          eventType: 'input_validation_failed',
        })
      );
    });

    it('validates tool output after execution', async () => {
      // Register a tool that returns null (invalid output)
      registry.register(
        {
          name: 'null_tool',
          description: 'Returns null',
          parameters: { type: 'object', properties: {} },
        },
        vi.fn().mockResolvedValue(null)
      );

      const toolCall: ToolCall = {
        id: 'call-null',
        name: 'null_tool',
        input: {},
      };

      const result = await executor.execute(toolCall, 'session-1');

      expect(result.isError).toBe(true);
      expect(result.content).toContain('Output validation failed');
    });
  });

  /**
   * Skill invocation tracking
   */
  describe('skill invocation tracking', () => {
    it('emits skill:invoked event when reading SKILL.md files', async () => {
      registry.register(
        {
          name: 'read',
          description: 'Read file',
          parameters: { type: 'object', properties: {} },
        },
        vi.fn().mockResolvedValue('skill content')
      );

      const toolCall: ToolCall = {
        id: 'call-skill',
        name: 'read',
        input: { path: '/home/user/.claude/skills/test-skill/SKILL.md' },
      };

      await executor.execute(toolCall, 'session-1');

      expect(mockEventBus.emit).toHaveBeenCalledWith(
        expect.objectContaining({
          type: 'skill:invoked',
          skillName: 'test-skill',
          skillPath: '/home/user/.claude/skills/test-skill/SKILL.md',
          sessionId: 'session-1',
          source: 'claude',
        })
      );
    });

    it('detects different skill sources from path', async () => {
      registry.register(
        {
          name: 'read',
          description: 'Read file',
          parameters: { type: 'object', properties: {} },
        },
        vi.fn().mockResolvedValue('skill content')
      );

      // Test cassi source
      let toolCall: ToolCall = {
        id: 'call-1',
        name: 'read',
        input: { path: '/home/user/.cassi/skills/my-skill/SKILL.md' },
      };

      await executor.execute(toolCall, 'session-1');

      expect(mockEventBus.emit).toHaveBeenCalledWith(
        expect.objectContaining({
          type: 'skill:invoked',
          skillName: 'my-skill',
          source: 'cassi',
        })
      );

      // Test pi source
      toolCall = {
        id: 'call-2',
        name: 'read',
        input: { path: '/home/user/.pi/skills/another-skill/SKILL.md' },
      };

      await executor.execute(toolCall, 'session-2');

      expect(mockEventBus.emit).toHaveBeenCalledWith(
        expect.objectContaining({
          type: 'skill:invoked',
          skillName: 'another-skill',
          source: 'pi',
        })
      );
    });

    it('does not emit skill event for non-skill files', async () => {
      registry.register(
        {
          name: 'read',
          description: 'Read file',
          parameters: { type: 'object', properties: {} },
        },
        vi.fn().mockResolvedValue('regular content')
      );

      const toolCall: ToolCall = {
        id: 'call-regular',
        name: 'read',
        input: { path: '/home/user/document.txt' },
      };

      // Get all calls to the mock
      const skillCalls = (mockEventBus.emit as ReturnType<typeof vi.fn>).mock.calls.filter(
        (call: any[]) => call[0]?.type === 'skill:invoked'
      );

      expect(skillCalls).toHaveLength(0);
    });
  });

  /**
   * Constructor variations
   */
  describe('constructor variations', () => {
    it('works without an eventBus (optional parameter)', async () => {
      const executorWithoutBus = new ToolExecutor(registry, defaultContext);

      registry.register(
        {
          name: 'simple_tool',
          description: 'Simple tool',
          parameters: { type: 'object', properties: {} },
        },
        vi.fn().mockResolvedValue('result')
      );

      const toolCall: ToolCall = {
        id: 'call-1',
        name: 'simple_tool',
        input: {},
      };

      const result = await executorWithoutBus.execute(toolCall, 'session-1');

      expect(result.isError).toBe(false);
      expect(result.content).toBe('result');
    });

    it('works with empty network allowlist', async () => {
      const restrictedContext: Omit<ToolExecutionContext, 'sessionId'> = {
        workingDir: '/test',
        allowedPaths: ['/test'],
        networkAllowlist: [],
        logger: mockLogger,
      };

      const restrictedExecutor = new ToolExecutor(registry, restrictedContext, mockEventBus);

      registry.register(
        {
          name: 'restricted_tool',
          description: 'Restricted tool',
          parameters: { type: 'object', properties: {} },
        },
        vi.fn().mockResolvedValue('local result')
      );

      const toolCall: ToolCall = {
        id: 'call-restricted',
        name: 'restricted_tool',
        input: {},
      };

      const result = await restrictedExecutor.execute(toolCall, 'session-1');

      expect(result.isError).toBe(false);
    });
  });
});
