import { randomBytes } from 'node:crypto';

/**
 * Generate a short alphanumeric ID.
 * Defaults to 8 characters which provides ~218 trillion combinations (36^8).
 * More than enough for thousands of sessions while staying very readable.
 */
export function generateShortId(length = 8): string {
  return randomBytes(Math.ceil(length / 2))
    .toString('hex')
    .slice(0, length);
}

/**
 * Generate a human-friendly timestamp-based ID.
 * Example: 240225-abcd
 */
export function generateReadableId(prefix?: string): string {
  const date = new Date().toISOString().slice(2, 10).replace(/-/g, '');
  const suffix = generateShortId(4);
  const id = `${date}-${suffix}`;
  return prefix ? `${prefix}-${id}` : id;
}
