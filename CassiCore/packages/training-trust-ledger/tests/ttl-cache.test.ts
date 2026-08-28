/**
 * TTLCache Tests
 *
 * Tests for the TTL + size-limited cache utility.
 */

import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { TTLCache, createTTLCache } from '../src/vendor/core/utils/ttl-cache.js';

describe('TTLCache', () => {
  beforeEach(() => {
    vi.useFakeTimers();
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  describe('basic operations', () => {
    it('should store and retrieve values', () => {
      const cache = new TTLCache<string, number>();
      cache.set('key1', 100);
      expect(cache.get('key1')).toBe(100);
    });

    it('should return undefined for non-existent keys', () => {
      const cache = new TTLCache<string, number>();
      expect(cache.get('nonexistent')).toBeUndefined();
    });

    it('should check if key exists', () => {
      const cache = new TTLCache<string, number>();
      cache.set('key1', 100);
      expect(cache.has('key1')).toBe(true);
      expect(cache.has('key2')).toBe(false);
    });

    it('should delete keys', () => {
      const cache = new TTLCache<string, number>();
      cache.set('key1', 100);
      expect(cache.delete('key1')).toBe(true);
      expect(cache.get('key1')).toBeUndefined();
      expect(cache.delete('key1')).toBe(false);
    });

    it('should clear all entries', () => {
      const cache = new TTLCache<string, number>();
      cache.set('key1', 100);
      cache.set('key2', 200);
      cache.clear();
      expect(cache.get('key1')).toBeUndefined();
      expect(cache.get('key2')).toBeUndefined();
      expect(cache.size).toBe(0);
    });

    it('should track size correctly', () => {
      const cache = new TTLCache<string, number>();
      expect(cache.size).toBe(0);
      cache.set('key1', 100);
      expect(cache.size).toBe(1);
      cache.set('key2', 200);
      expect(cache.size).toBe(2);
      cache.delete('key1');
      expect(cache.size).toBe(1);
    });
  });

  describe('TTL expiration', () => {
    it('should return undefined for expired entries', () => {
      const cache = new TTLCache<string, number>({ ttlMs: 5000 });
      cache.set('key1', 100);
      expect(cache.get('key1')).toBe(100);

      vi.advanceTimersByTime(4000);
      expect(cache.get('key1')).toBe(100); // Not yet expired

      vi.advanceTimersByTime(2000);
      expect(cache.get('key1')).toBeUndefined(); // Expired
    });

    it('should return false for has() on expired entries', () => {
      const cache = new TTLCache<string, number>({ ttlMs: 5000 });
      cache.set('key1', 100);
      expect(cache.has('key1')).toBe(true);

      vi.advanceTimersByTime(6000);
      expect(cache.has('key1')).toBe(false);
    });

    it('should delete expired entries on access', () => {
      const cache = new TTLCache<string, number>({ ttlMs: 5000 });
      cache.set('key1', 100);

      vi.advanceTimersByTime(3000);
      cache.set('key2', 200); // key2 inserted 3 seconds after key1

      vi.advanceTimersByTime(3000); // Total: key1=6s (expired), key2=3s (not expired)
      cache.get('key1'); // Access expired entry

      expect(cache.size).toBe(1); // key1 deleted, key2 remains
      expect(cache.get('key2')).toBe(200);
    });

    it('should use default TTL of 30 minutes', () => {
      const cache = new TTLCache<string, number>(); // No explicit ttlMs
      cache.set('key1', 100);

      vi.advanceTimersByTime(29 * 60 * 1000); // 29 minutes
      expect(cache.get('key1')).toBe(100);

      vi.advanceTimersByTime(2 * 60 * 1000); // +2 minutes = 31 total
      expect(cache.get('key1')).toBeUndefined();
    });
  });

  describe('max size enforcement', () => {
    it('should evict oldest entries when maxSize is reached', () => {
      const cache = new TTLCache<string, number>({ maxSize: 3 });
      cache.set('key1', 100);
      cache.set('key2', 200);
      cache.set('key3', 300);
      expect(cache.size).toBe(3);

      cache.set('key4', 400); // Should evict key1
      expect(cache.size).toBe(3);
      expect(cache.get('key1')).toBeUndefined();
      expect(cache.get('key2')).toBe(200);
      expect(cache.get('key3')).toBe(300);
      expect(cache.get('key4')).toBe(400);
    });

    it('should use default maxSize of 1000', () => {
      const cache = new TTLCache<string, number>();
      // Add 1001 entries
      for (let i = 0; i < 1001; i++) {
        cache.set(`key${i}`, i);
      }
      expect(cache.size).toBe(1000);
      expect(cache.get('key0')).toBeUndefined(); // First entry evicted
      expect(cache.get('key1')).toBe(1); // Second entry still there
    });

    it('should not evict when updating existing key', () => {
      const cache = new TTLCache<string, number>({ maxSize: 3 });
      cache.set('key1', 100);
      cache.set('key2', 200);
      cache.set('key3', 300);

      cache.set('key2', 250); // Update existing key
      expect(cache.size).toBe(3);
      expect(cache.get('key1')).toBe(100);
      expect(cache.get('key2')).toBe(250);
      expect(cache.get('key3')).toBe(300);
    });
  });

  describe('complex values', () => {
    it('should cache objects', () => {
      interface TestObject {
        name: string;
        value: number;
      }
      const cache = new TTLCache<string, TestObject>();
      const obj: TestObject = { name: 'test', value: 42 };
      cache.set('obj1', obj);
      expect(cache.get('obj1')).toEqual(obj);
    });

    it('should cache arrays', () => {
      const cache = new TTLCache<string, number[]>();
      const arr = [1, 2, 3];
      cache.set('arr1', arr);
      expect(cache.get('arr1')).toEqual(arr);
    });
  });

  describe('iteration', () => {
    it('should iterate over entries', () => {
      const cache = new TTLCache<string, number>();
      cache.set('a', 1);
      cache.set('b', 2);
      cache.set('c', 3);

      const entries: Array<[string, number]> = [];
      for (const entry of cache) {
        entries.push(entry);
      }

      expect(entries).toHaveLength(3);
      expect(entries.map(e => e[0]).sort()).toEqual(['a', 'b', 'c']);
    });

    it('should provide keys iterator', () => {
      const cache = new TTLCache<string, number>();
      cache.set('a', 1);
      cache.set('b', 2);

      const keys = Array.from(cache.keys());
      expect(keys.sort()).toEqual(['a', 'b']);
    });
  });

  describe('cleanupExpired', () => {
    it('should remove all expired entries', () => {
      const cache = new TTLCache<string, number>({ ttlMs: 5000 });
      cache.set('key1', 100);
      cache.set('key2', 200);
      cache.set('key3', 300);

      vi.advanceTimersByTime(3000);
      cache.set('key4', 400); // Fresh entry

      vi.advanceTimersByTime(3000); // key1-3 expired, key4 not

      const removed = cache.cleanupExpired();
      expect(removed).toBe(3);
      expect(cache.size).toBe(1);
      expect(cache.get('key4')).toBe(400);
    });

    it('should return 0 when no entries expired', () => {
      const cache = new TTLCache<string, number>({ ttlMs: 5000 });
      cache.set('key1', 100);
      cache.set('key2', 200);

      const removed = cache.cleanupExpired();
      expect(removed).toBe(0);
      expect(cache.size).toBe(2);
    });
  });

  describe('getStats', () => {
    it('should return cache statistics', () => {
      const cache = new TTLCache<string, number>({ maxSize: 100, ttlMs: 60000 });
      cache.set('a', 1);
      cache.set('b', 2);

      const stats = cache.getStats();
      expect(stats.size).toBe(2);
      expect(stats.maxSize).toBe(100);
      expect(stats.ttlMs).toBe(60000);
      expect(stats.utilizationPercent).toBe(2);
    });
  });

  describe('factory function', () => {
    it('should create a TTLCache via factory', () => {
      const cache = createTTLCache<string, number>({ maxSize: 50, ttlMs: 10000 });
      cache.set('key', 42);
      expect(cache.get('key')).toBe(42);
      expect(cache.getStats().maxSize).toBe(50);
      expect(cache.getStats().ttlMs).toBe(10000);
    });

    it('should create a TTLCache with defaults via factory', () => {
      const cache = createTTLCache<string, number>();
      cache.set('key', 42);
      expect(cache.get('key')).toBe(42);
    });
  });

  describe('Map compatibility', () => {
    it('should be usable as a Map replacement', () => {
      // This test verifies that TTLCache can replace Map in common patterns
      const cache = new TTLCache<string, number>();

      // Test all Map-like methods used in the codebase
      cache.set('key1', 100);
      expect(cache.has('key1')).toBe(true);
      expect(cache.get('key1')).toBe(100);
      expect(cache.delete('key1')).toBe(true);
      expect(cache.has('key1')).toBe(false);

      cache.set('key2', 200);
      cache.clear();
      expect(cache.size).toBe(0);
    });

    it('should handle the specific pattern from archivist', () => {
      interface Analysis {
        summary: string;
        importance: number;
      }

      const cache = new TTLCache<string, Analysis>({ maxSize: 100, ttlMs: 5 * 60 * 1000 });
      const key = 'conversation:Hello world';
      const analysis: Analysis = {
        summary: 'A greeting',
        importance: 0.5,
      };

      if (!cache.has(key)) {
        cache.set(key, analysis);
      }

      expect(cache.get(key)).toEqual(analysis);
    });
  });
});
