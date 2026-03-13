#!/usr/bin/env node
/**
 * Shared helpers for CassiCore MCP Gateway
 * Common utilities used across all domain modules
 */

import type { ILogger } from '../../types/interfaces.js';

// Configuration
export const GATEWAY_VERSION = '1.0.0';
export const DEFAULT_FETCH_TIMEOUT_MS = 30_000; // 30s default timeout for all fetch calls

/**
 * Create a logger that writes to stderr (stdout reserved for MCP protocol)
 */
export function createLogger(): ILogger {
  return {
    debug: (msg: string, meta?: Record<string, unknown>) => log('debug', msg, meta),
    info: (msg: string, meta?: Record<string, unknown>) => log('info', msg, meta),
    warn: (msg: string, meta?: Record<string, unknown>) => log('warn', msg, meta),
    error: (msg: string, meta?: Record<string, unknown>) => log('error', msg, meta),
    child: () => createLogger(),
  };
}

function log(level: string, message: string, data?: any) {
  const timestamp = new Date().toISOString();
  const logLine = JSON.stringify({ timestamp, level, message, data });
  console.error(logLine);
}

/**
 * Fetch with timeout — wraps global fetch with AbortController to prevent
 * indefinite hangs when the daemon is slow or unresponsive.
 */
export async function fetchWithTimeout(
  url: string | URL,
  init?: RequestInit & { timeoutMs?: number }
): Promise<Response> {
  const timeoutMs = init?.timeoutMs ?? DEFAULT_FETCH_TIMEOUT_MS;
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeoutMs);
  try {
    return await fetch(url.toString(), {
      ...init,
      signal: controller.signal,
    });
  } catch (err: any) {
    if (err?.name === 'AbortError') {
      throw new Error(`Request to ${url} timed out after ${timeoutMs}ms`);
    }
    throw err;
  } finally {
    clearTimeout(timer);
  }
}

/**
 * Helper to fetch JSON from an admin API endpoint.
 * Uses timeout to prevent indefinite hangs and validates Content-Type.
 */
export async function fetchIntelligence(
  baseUrl: string,
  path: string,
  params?: Record<string, string>
): Promise<any> {
  const url = new URL(path, baseUrl);
  if (params) {
    for (const [k, v] of Object.entries(params)) {
      if (v !== undefined && v !== null) url.searchParams.set(k, v);
    }
  }
  const response = await fetchWithTimeout(url.toString());
  if (!response.ok) {
    const text = await response.text().catch(() => '(unreadable body)');
    throw new Error(`Admin API error (${response.status}): ${text}`);
  }
  const contentType = response.headers.get('content-type') || '';
  if (!contentType.includes('json')) {
    const text = await response.text().catch(() => '');
    throw new Error(`Expected JSON from ${path}, got ${contentType}: ${text.slice(0, 200)}`);
  }
  return response.json();
}

/**
 * Resolve the most recent active session ID
 */
export async function resolveSessionId(
  baseUrl: string,
  sessionId?: string
): Promise<string | undefined> {
  if (sessionId) return sessionId;
  try {
    const data = await fetchIntelligence(baseUrl, '/sessions');
    const sessions = data?.sessions;
    if (Array.isArray(sessions) && sessions.length > 0) {
      const sorted = sessions.sort((a: any, b: any) => (b.lastActiveAt || 0) - (a.lastActiveAt || 0));
      return sorted[0]?.id;
    }
  } catch {
    // Sessions endpoint may not be available
  }
  return undefined;
}

/**
 * Format error response for MCP
 */
export function formatError(error: any): { content: Array<{ type: 'text'; text: string }>; isError: true } {
  return {
    content: [
      {
        type: 'text',
        text: JSON.stringify({ error: error.message ?? String(error) }, null, 2),
      },
    ],
    isError: true,
  };
}

/**
 * Format success response with JSON
 */
export function formatJsonResponse(data: any): { content: Array<{ type: 'text'; text: string }> } {
  return {
    content: [
      {
        type: 'text',
        text: JSON.stringify(data, null, 2),
      },
    ],
  };
}

/**
 * Format success response with markdown text
 */
export function formatTextResponse(text: string): { content: Array<{ type: 'text'; text: string }> } {
  return {
    content: [
      {
        type: 'text',
        text,
      },
    ],
  };
}

/** Safe config keys that can be modified via cassi_config_set */
export const SAFE_CONFIG_KEYS = [
  'intelligence.',
  'providers.*.model',
  'providers.*.enabled',
  'channels.*.enabled',
  'logging.level',
];

export function isConfigKeySafe(key: string): boolean {
  return SAFE_CONFIG_KEYS.some(pattern => {
    if (pattern.endsWith('.')) return key.startsWith(pattern);
    // Convert wildcard pattern to regex
    const regex = new RegExp('^' + pattern.replace(/\./g, '\\.').replace(/\*/g, '[^.]+') + '$');
    return regex.test(key);
  });
}
