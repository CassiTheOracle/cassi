/**
 * CachedValue - A simple single-value cache with TTL and manual invalidation.
 *
 * Unlike TTLCache which holds multiple key-value pairs, CachedValue holds exactly
 * one value. It's useful for caching the result of expensive operations where
 * only the most recent value matters.
 *
 * Use cases:
 * - Caching a single expensive computation result
 * - Storing the latest fetched data with automatic expiration
 * - Simple memoization of a function result
 *
 * @example
 * ```typescript
 * const cache = new CachedValue<UserData>({ ttlMs: 60000 });
 * cache.set({ id: 1, name: 'Alice' });
 * const data = cache.get(); // Returns value or null if expired
 * ```
 */

export interface CachedValueOptions {
  /** Time-to-live in milliseconds. If 0 or Infinity, value never expires (default: 60000) */
  ttlMs?: number;
}

/** Default TTL: 60 seconds in milliseconds */
const DEFAULT_TTL_MS = 60 * 1000;

/**
 * A single-value cache with TTL (time-to-live) expiration.
 *
 * The cache holds exactly one value at a time. The value expires after the
 * configured TTL, or can be manually invalidated.
 *
 * TTL expiration is checked lazily on get() and isStale() operations.
 */
export class CachedValue<T> {
  private readonly ttlMs: number;
  private _value: T | null;
  private _cachedAt: number | null;

  /**
   * Create a new CachedValue.
   *
   * @param opts - Configuration options
   * @param opts.ttlMs - Time-to-live in milliseconds (default: 60000 = 60s).
   *                     If 0 or Infinity, the value never expires.
   */
  constructor(opts: CachedValueOptions = {}) {
    const ttl = opts.ttlMs ?? DEFAULT_TTL_MS;
    this.ttlMs = ttl === 0 || ttl === Infinity ? Infinity : ttl;
    this._value = null;
    this._cachedAt = null;
  }

  /**
   * Get the cached value.
   *
   * If the value has expired (based on TTL), null is returned.
   *
   * @returns The cached value, or null if not set or expired
   */
  get(): T | null {
    if (this._value === null || this._cachedAt === null) {
      return null;
    }

    // Check TTL expiration
    if (this.ttlMs !== Infinity && Date.now() - this._cachedAt > this.ttlMs) {
      return null;
    }

    return this._value;
  }

  /**
   * Store a value in the cache.
   *
   * @param value - The value to cache
   */
  set(value: T): void {
    this._value = value;
    this._cachedAt = Date.now();
  }

  /**
   * Clear the cached value immediately.
   *
   * This is an alias for invalidate().
   */
  invalidate(): void {
    this.clear();
  }

  /**
   * Clear the cached value immediately.
   */
  clear(): void {
    this._value = null;
    this._cachedAt = null;
  }

  /**
   * Check if the cached value is stale.
   *
   * A value is stale if:
   * - No value has been set, or
   * - The TTL has elapsed since the value was cached
   *
   * @returns true if the value is stale or not set, false otherwise
   */
  isStale(): boolean {
    if (this._value === null || this._cachedAt === null) {
      return true;
    }

    // Never stale if TTL is infinite
    if (this.ttlMs === Infinity) {
      return false;
    }

    return Date.now() - this._cachedAt > this.ttlMs;
  }

  /**
   * Get the raw cached value without TTL check.
   *
   * This is useful for diagnostics or debugging. Use get() for normal
   * access as it respects TTL expiration.
   *
   * @returns The cached value, or null if never set
   */
  get value(): T | null {
    return this._value;
  }

  /**
   * Get the timestamp when the value was cached.
   *
   * @returns The cache timestamp in milliseconds since epoch, or null if no value
   */
  get cachedAt(): number | null {
    return this._cachedAt;
  }
}

/**
 * Factory function to create a CachedValue.
 *
 * @param opts - Configuration options
 * @returns A new CachedValue instance
 */
export function createCachedValue<T>(opts?: CachedValueOptions): CachedValue<T> {
  return new CachedValue<T>(opts);
}
