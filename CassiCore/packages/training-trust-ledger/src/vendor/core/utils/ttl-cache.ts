/**
 * VENDORED RUNTIME STUB — faithful copy of `core/utils/ttl-cache.ts`.
 * The TTLCache + createTTLCache pure in-memory cache (used by TrustLedger).
 * Re-point to `@cassicore/utils` at P6 (§P5b table §C2.2).
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

  constructor(opts: TTLCacheOptions = {}) {
    this.store = new Map<K, CacheEntry<V>>();
    this.maxSize = opts.maxSize ?? DEFAULT_MAX_SIZE;
    this.ttlMs = opts.ttlMs ?? DEFAULT_TTL_MS;
  }

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

  delete(key: K): boolean {
    return this.store.delete(key);
  }

  clear(): void {
    this.store.clear();
  }

  /** Note: includes entries that may have expired but not been accessed yet. */
  get size(): number {
    return this.store.size;
  }

  keys(): IterableIterator<K> {
    return this.store.keys();
  }

  entries(): IterableIterator<[K, V]> {
    const self = this;
    return (function* () {
      for (const [key, entry] of self.store) {
        yield [key, entry.value] as [K, V];
      }
    })();
  }

  [Symbol.iterator](): IterableIterator<[K, V]> {
    return this.entries();
  }

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

/** Factory function to create a TTLCache. */
export function createTTLCache<K, V>(opts?: TTLCacheOptions): TTLCache<K, V> {
  return new TTLCache<K, V>(opts);
}
