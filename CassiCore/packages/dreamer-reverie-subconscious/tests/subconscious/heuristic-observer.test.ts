/**
 * HeuristicObserver — Real-time Pattern Detection Tests
 *
 * The HeuristicObserver processes every event synchronously as it arrives,
 * detecting known problematic patterns without any LLM cost. It acts as the
 * Subconscious's reflexive awareness — fast, cheap, and always on.
 *
 * Patterns detected:
 * - Provider error bursts: 3+ errors in 30s window indicates cascade failure
 * - Provider rate limits: Track which providers are currently throttled
 * - Plugin crash cycles: 3+ crashes in 2min indicates instability
 * - Budget pressure: Warnings when approaching token limits
 * - Config reloads: Track when hot-reload occurs
 * - Autonomy blocks: Agents waiting for approval
 *
 * All detections respect a 60-second cooldown to prevent alert flooding.
 */

import { describe, it, expect, vi } from 'vitest';
import { HeuristicObserver } from '../../src/subconscious/heuristic-observer.js';
import type { RuntimeEvent } from '@cassicore/foundation';

const mockLogger = () => {
  const l = {
    debug: vi.fn(), info: vi.fn(), warn: vi.fn(), error: vi.fn(),
  };
  return { ...l, child: vi.fn(() => l) };
};

const makeEvent = (type: string, extras: Record<string, unknown> = {}): RuntimeEvent =>
  ({ type, ...extras } as unknown as RuntimeEvent);

describe('HeuristicObserver provider error burst detection', () => {
  it('emits an anomaly when 3+ consecutive errors occur from the same provider', () => {
    const observer = new HeuristicObserver(mockLogger() as any);

    observer.observe(makeEvent('provider:request_error', { providerId: 'openai' }));
    observer.observe(makeEvent('provider:request_error', { providerId: 'openai' }));
    observer.observe(makeEvent('provider:request_error', { providerId: 'openai' }));

    const anomalies = observer.drainAnomalies();
    expect(anomalies.length).toBe(1);
    expect(anomalies[0].description).toContain('openai');
    expect(anomalies[0].eventTypes).toContain('provider:request_error');
  });

  it('does not emit an anomaly for fewer than 3 errors', () => {
    const observer = new HeuristicObserver(mockLogger() as any);

    observer.observe(makeEvent('provider:request_error', { providerId: 'anthropic' }));
    observer.observe(makeEvent('provider:request_error', { providerId: 'anthropic' }));

    expect(observer.drainAnomalies().length).toBe(0);
  });

  it('tracks errors from different providers independently', () => {
    const observer = new HeuristicObserver(mockLogger() as any);

    observer.observe(makeEvent('provider:request_error', { providerId: 'openai' }));
    observer.observe(makeEvent('provider:request_error', { providerId: 'anthropic' }));
    observer.observe(makeEvent('provider:request_error', { providerId: 'anthropic' }));

    expect(observer.drainAnomalies().length).toBe(0);
  });

  it('sets severity based on error count at alert time (3-4=medium, 5+=high)', () => {
    const observer = new HeuristicObserver(mockLogger() as any);

    observer.observe(makeEvent('provider:request_error', { providerId: 'kimi' }));
    observer.observe(makeEvent('provider:request_error', { providerId: 'kimi' }));
    observer.observe(makeEvent('provider:request_error', { providerId: 'kimi' }));

    const anomalies = observer.drainAnomalies();
    expect(anomalies.length).toBe(1);
    expect(anomalies[0].severity).toBe('medium');
  });

  it('clears the burst tracker when provider:error_reset is received', () => {
    const observer = new HeuristicObserver(mockLogger() as any);

    observer.observe(makeEvent('provider:request_error', { providerId: 'openai' }));
    observer.observe(makeEvent('provider:request_error', { providerId: 'openai' }));
    observer.observe(makeEvent('provider:error_reset', { providerId: 'openai' }));

    observer.observe(makeEvent('provider:request_error', { providerId: 'openai' }));
    observer.observe(makeEvent('provider:request_error', { providerId: 'openai' }));

    expect(observer.drainAnomalies().length).toBe(0);
  });
});

describe('HeuristicObserver provider rate limit detection', () => {
  it('emits an observation when a provider is rate-limited', () => {
    const observer = new HeuristicObserver(mockLogger() as any);

    observer.observe(makeEvent('provider:rate_limited', {
      providerId: 'openai',
      retryAfterMs: 5000,
    }));

    const obs = observer.drainObservations();
    expect(obs.length).toBe(1);
    expect(obs[0].summary).toContain('openai');
    expect(obs[0].patterns).toContain('provider_rate_limited');
  });

  it('respects cooldown and suppresses duplicate alerts within 60 seconds', () => {
    const observer = new HeuristicObserver(mockLogger() as any);

    observer.observe(makeEvent('provider:rate_limited', { providerId: 'openai', retryAfterMs: 5000 }));
    observer.drainObservations();

    observer.observe(makeEvent('provider:rate_limited', { providerId: 'openai', retryAfterMs: 5000 }));
    expect(observer.drainObservations().length).toBe(0);
  });
});

describe('HeuristicObserver plugin crash cycle detection', () => {
  it('emits a high-severity anomaly after 3+ crashes from the same plugin', () => {
    const observer = new HeuristicObserver(mockLogger() as any);

    for (let i = 0; i < 3; i++) {
      observer.observe(makeEvent('plugin:crashed', { pluginId: 'my-plugin', error: 'SIGSEGV' }));
    }

    const anomalies = observer.drainAnomalies();
    expect(anomalies.length).toBe(1);
    expect(anomalies[0].description).toContain('my-plugin');
    expect(anomalies[0].severity).toBe('high');
  });

  it('does not emit an anomaly for fewer than 3 crashes', () => {
    const observer = new HeuristicObserver(mockLogger() as any);

    observer.observe(makeEvent('plugin:crashed', { pluginId: 'my-plugin' }));
    observer.observe(makeEvent('plugin:crashed', { pluginId: 'my-plugin' }));

    expect(observer.drainAnomalies().length).toBe(0);
  });
});

describe('HeuristicObserver budget warning detection', () => {
  it('emits an anomaly on budget warning with usage percentage', () => {
    const observer = new HeuristicObserver(mockLogger() as any);

    observer.observe(makeEvent('budget:warning', {
      tier: 'frugal',
      percentUsed: 75,
      remaining: 1000,
      providerId: 'anthropic',
    }));

    const anomalies = observer.drainAnomalies();
    expect(anomalies.length).toBe(1);
    expect(anomalies[0].description).toContain('75');
  });

  it('emits high severity anomaly on critical budget tier', () => {
    const observer = new HeuristicObserver(mockLogger() as any);

    observer.observe(makeEvent('budget:warning', {
      tier: 'critical',
      percentUsed: 92,
      remaining: 100,
    }));

    const anomalies = observer.drainAnomalies();
    expect(anomalies.length).toBe(1);
    expect(anomalies[0].severity).toBe('high');
  });

  it('respects cooldown for repeated budget warnings', () => {
    const observer = new HeuristicObserver(mockLogger() as any);

    observer.observe(makeEvent('budget:warning', { tier: 'frugal', percentUsed: 75, remaining: 1000 }));
    observer.drainAnomalies();

    observer.observe(makeEvent('budget:warning', { tier: 'frugal', percentUsed: 80, remaining: 900 }));
    expect(observer.drainAnomalies().length).toBe(0);
  });
});

describe('HeuristicObserver config reload detection', () => {
  it('emits an observation when configuration is hot-reloaded', () => {
    const observer = new HeuristicObserver(mockLogger() as any);

    observer.observe(makeEvent('config:reloaded'));

    const obs = observer.drainObservations();
    expect(obs.length).toBe(1);
    expect(obs[0].patterns).toContain('config_reloaded');
  });

  it('respects cooldown for repeated config reloads', () => {
    const observer = new HeuristicObserver(mockLogger() as any);

    observer.observe(makeEvent('config:reloaded'));
    observer.drainObservations();
    observer.observe(makeEvent('config:reloaded'));

    expect(observer.drainObservations().length).toBe(0);
  });
});

describe('HeuristicObserver autonomy block detection', () => {
  it('emits an observation when an autonomy agent is blocked', () => {
    const observer = new HeuristicObserver(mockLogger() as any);

    observer.observe(makeEvent('autonomy:blocked', { agentId: 'agent-1', reason: 'approval required' }));

    const obs = observer.drainObservations();
    expect(obs.length).toBe(1);
    expect(obs[0].summary).toContain('agent-1');
    expect(obs[0].patterns).toContain('autonomy_blocked');
  });
});

describe('HeuristicObserver buffer drain pattern', () => {
  it('clears the observations buffer when drainObservations is called', () => {
    const observer = new HeuristicObserver(mockLogger() as any);

    observer.observe(makeEvent('config:reloaded'));

    expect(observer.drainObservations().length).toBe(1);
    expect(observer.drainObservations().length).toBe(0);
  });

  it('clears the anomalies buffer when drainAnomalies is called', () => {
    const observer = new HeuristicObserver(mockLogger() as any);

    for (let i = 0; i < 3; i++) {
      observer.observe(makeEvent('provider:request_error', { providerId: 'openai' }));
    }

    expect(observer.drainAnomalies().length).toBe(1);
    expect(observer.drainAnomalies().length).toBe(0);
  });

  it('maintains independent buffers for observations and anomalies', () => {
    const observer = new HeuristicObserver(mockLogger() as any);

    observer.observe(makeEvent('config:reloaded'));

    for (let i = 0; i < 3; i++) {
      observer.observe(makeEvent('provider:request_error', { providerId: 'kimi' }));
    }

    expect(observer.drainObservations().length).toBe(1);
    expect(observer.drainAnomalies().length).toBe(1);
  });
});
