import { describe, it, expect, vi } from 'vitest';
import { SessionManager } from '../src/session/SessionManager.js';
import type { ISessionStore, SessionState } from '../src/session/types.js';

describe('SessionManager', () => {
  it('should create a new session successfully', async () => {
    const mockStore: ISessionStore = {
      save: async (id, state) => {},
      load: async (id) => null,
      delete: async (id) => {},
      list: async () => [],
      clear: async () => {},
    };

    const mockLogger = {
      info: vi.fn(),
      debug: vi.fn(),
      warn: vi.fn(),
      error: vi.fn(),
    };

    const sessionManager = new SessionManager({ 
      store: mockStore, 
      logger: mockLogger,
      defaultModel: 'test-model',
      defaultSystemPrompt: 'test-prompt'
    });

    await sessionManager.getOrCreate('test-channel', 'test-sender');

    expect(mockLogger.info).toHaveBeenCalled();
  });

  it('should throw error when loading non-existent session', async () => {
    const mockStore: ISessionStore = {
      save: async (id, state) => {},
      load: async (id) => null,
      delete: async (id) => {},
      list: async () => [],
      clear: async () => {},
    };

    const mockLogger = {
      info: vi.fn(),
      debug: vi.fn(),
      warn: vi.fn(),
      error: vi.fn(),
    };

    const sessionManager = new SessionManager({ 
      store: mockStore, 
      logger: mockLogger,
      defaultModel: 'test-model',
      defaultSystemPrompt: 'test-prompt'
    });

    const session = await sessionManager.get('non_existent');
    expect(session).toBeNull();
  });
});
