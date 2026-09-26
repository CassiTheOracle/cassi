/**
 * TTLCache - A simple TTL + max-size cache that evicts oldest entries.
 *
 * This cache provides O(1) operations using a Map internally. It supports:
 * - Time-to-live (TTL) expiration: entries older than ttlMs are automatically evicted on access
 * - Max size enforcement: when the cache reaches maxSize, the oldest entries are removed
 * - Map-compatible interface: get/set/has/delete/clear/size work identically to Map
 *
 * Use cases:
 * - Caching LLM analysis results that become stale over time
 * - Storing temporary computation results with bounded memory
 * - Replacing unbounded Maps that would cause memory leaks
 *
 * @example
 * ```typescript
 * const cache = new TTLCache<string, AnalysisResult>({ maxSize: 100, ttlMs: 300000 });
 * cache.set('key', { data: 'value' });
 * const result = cache.get('key'); // Returns value or undefined if expired
 * ```
 */

interface CacheEntry<V> {
  /** The cached value */
  value: V;
  /** Timestamp when the entry was inserted */
  insertedAt: number;
}

export interface TTLCacheOptions {
  /** Maximum number of entries to store (default: 1000) */
  maxSize?: number;
  /** Time-to-live in milliseconds (default: 1800000 = 30 minutes) */
  ttlMs?: number;
}

/** Default cache size limit: 1000 entries */
const DEFAULT_MAX_SIZE = 1000;

/** Default TTL: 30 minutes in milliseconds */
const DEFAULT_TTL_MS = 30 * 60 * 1000;

/**
 * A cache with TTL (time-to-live) and size limit constraints.
 *
 * The cache uses a Map internally to maintain insertion order, which allows
 * efficient eviction of the oldest entries when size limits are reached.
 *
 * TTL expiration is checked lazily on get() operations. Expired entries
 * are deleted and undefined is returned.
 */
export class TTLCache<K, V> {
  private readonly store: Map<K, CacheEntry<V>>;
  private readonly maxSize: number;
  private readonly ttlMs: number;

  /**
   * Create a new TTLCache.
   *
   * @param opts - Configuration options
   * @param opts.maxSize - Maximum number of entries (default: 1000)
   * @param opts.ttlMs - Time-to-live in milliseconds (default: 1800000 = 30 min)
   */
  constructor(opts: TTLCacheOptions = {}) {
    this.store = new Map<K, CacheEntry<V>>();
    this.maxSize = opts.maxSize ?? DEFAULT_MAX_SIZE;
    this.ttlMs = opts.ttlMs ?? DEFAULT_TTL_MS;
  }

  /**
   * Get a value from the cache.
   *
   * If the key exists but the entry has expired (based on TTL), the entry
   * is deleted and undefined is returned.
   *
   * @param key - The cache key
   * @returns The cached value, or undefined if not found or expired
   */
  get(key: K): V | undefined {
    const entry = this.store.get(key);

    if (entry === undefined) {
      return undefined;
    }

    // Check TTL expiration
    if (Date.now() - entry.insertedAt > this.ttlMs) {
      this.store.delete(key);
      return undefined;
    }

    return entry.value;
  }

  /**
   * Store a value in the cache.
   *
   * If the cache is at maxSize, the oldest entry (by insertion order) is
   * evicted before the new entry is added.
   *
   * @param key - The cache key
   * @param value - The value to cache
   */
  set(key: K, value: V): void {
    // If at capacity and this is a new key, evict oldest
    if (this.store.size >= this.maxSize && !this.store.has(key)) {
      const firstKey = this.store.keys().next().value;
      if (firstKey !== undefined) {
        this.store.delete(firstKey);
      }
    }

    this.store.set(key, {
      value,
      insertedAt: Date.now(),
    });
  }

  /**
   * Check if a key exists in the cache and has not expired.
   *
   * @param key - The cache key
   * @returns true if the key exists and is not expired
   */
  has(key: K): boolean {
    const entry = this.store.get(key);

    if (entry === undefined) {
      return false;
    }

    // Check TTL expiration
    if (Date.now() - entry.insertedAt > this.ttlMs) {
      this.store.delete(key);
      return false;
    }

    return true;
  }

  /**
   * Delete a key from the cache.
   *
   * @param key - The cache key to delete
   * @returns true if the key existed and was deleted, false otherwise
   */
  delete(key: K): boolean {
    return this.store.delete(key);
  }

  /**
   * Clear all entries from the cache.
   */
  clear(): void {
    this.store.clear();
  }

  /**
   * Get the number of entries in the cache.
   *
   * Note: This includes entries that may have expired but have not been
   * accessed yet. Expired entries are only removed on get/has operations.
   */
  get size(): number {
    return this.store.size;
  }

  /**
   * Get all keys in the cache.
   *
   * Note: Expired keys are not filtered out until accessed.
   */
  keys(): IterableIterator<K> {
    return this.store.keys();
  }

  /**
   * Get all entries in the cache as [key, value] pairs.
   *
   * Note: Expired entries are not filtered out until accessed.
   */
  entries(): IterableIterator<[K, V]> {
    const self = this;
    return (function* () {
      for (const [key, entry] of self.store) {
        yield [key, entry.value] as [K, V];
      }
    })();
  }

  /**
   * Iterate over the cache entries.
   *
   * Note: Expired entries are yielded as-is without TTL check.
   */
  [Symbol.iterator](): IterableIterator<[K, V]> {
    return this.entries();
  }

  /**
   * Get cache statistics for debugging/monitoring.
   */
  getStats(): {
    size: number;
    maxSize: number;
    ttlMs: number;
    utilizationPercent: number;
  } {
    return {
      size: this.size,
      maxSize: this.maxSize,
      ttlMs: this.ttlMs,
      utilizationPercent: Math.round((this.size / this.maxSize) * 100),
    };
  }

  /**
   * Manually trigger cleanup of expired entries.
   * This can be called periodically to reclaim memory from expired entries
   * that haven't been accessed.
   *
   * @returns The number of expired entries that were removed
   */
  cleanupExpired(): number {
    const now = Date.now();
    let removed = 0;

    for (const [key, entry] of this.store) {
      if (now - entry.insertedAt > this.ttlMs) {
        this.store.delete(key);
        removed++;
      }
    }

    return removed;
  }
}

/**
 * Factory function to create a TTLCache.
 *
 * @param opts - Configuration options
 * @returns A new TTLCache instance
 */
export function createTTLCache<K, V>(opts?: TTLCacheOptions): TTLCache<K, V> {
  return new TTLCache<K, V>(opts);
}
