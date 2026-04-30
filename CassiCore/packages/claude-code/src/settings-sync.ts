/**
 * Settings Sync — Auto-migration of ~/.claude/settings.json.
 *
 * On proxy startup, this module:
 *  1. Reads ~/.claude/settings.json
 *  2. Strips provider-specific env vars (API keys, model names, base URLs)
 *  3. Ensures ANTHROPIC_BASE_URL points to the local proxy
 *  4. Backs up the original file
 *  5. Writes the updated settings
 *
 * This replaces the manual env configuration with dynamic provider routing
 * managed by the proxy's provider registry.
 */

import fs from "node:fs";
import path from "node:path";
import os from "node:os";
import { integrationLogger } from "./logger.js";

const logger = integrationLogger.child("settings-sync");

const SETTINGS_PATH = path.join(os.homedir(), ".claude", "settings.json");
const PROXY_URL = "http://localhost:7435";

/**
 * Env vars that should be removed from settings.json —
 * credentials and base URLs are managed by the proxy's provider registry.
 * Model overrides are KEPT because Claude Code needs them to know which
 * models map to opus/sonnet/haiku.
 */
const REMOVED_ENV_VARS = [
  "ANTHROPIC_AUTH_TOKEN",
  "API_TIMEOUT_MS",
];

/**
 * Env vars that should be set/overridden by the proxy.
 */
const REQUIRED_ENV: Record<string, string> = {
  ANTHROPIC_BASE_URL: PROXY_URL,
};

interface ClaudeSettings {
  env?: Record<string, string>;
  [key: string]: unknown;
}

/**
 * Run the settings sync. Returns true if changes were made.
 */
export function syncSettings(): boolean {
  // Check if settings file exists
  if (!fs.existsSync(SETTINGS_PATH)) {
    logger.info("No ~/.claude/settings.json found — skipping sync");
    return false;
  }

  let raw: string;
  try {
    raw = fs.readFileSync(SETTINGS_PATH, "utf-8");
  } catch (err) {
    logger.warn(`Cannot read ${SETTINGS_PATH}: ${String(err)}`);
    return false;
  }

  let settings: ClaudeSettings;
  try {
    settings = JSON.parse(raw);
  } catch (err) {
    logger.warn(`Cannot parse ${SETTINGS_PATH}: ${String(err)}`);
    return false;
  }

  // Check if migration is needed
  if (!needsMigration(settings)) {
    logger.info("Settings already synced — no changes needed");
    return false;
  }

  // Backup original
  const backupPath = `${SETTINGS_PATH}.backup-${Date.now()}`;
  try {
    fs.writeFileSync(backupPath, raw, "utf-8");
    logger.info(`Backed up original settings to ${backupPath}`);
  } catch (err) {
    logger.warn(`Cannot backup settings: ${String(err)} — proceeding anyway`);
  }

  // Apply migration
  const migrated = migrateSettings(settings);

  // Write updated settings
  try {
    fs.writeFileSync(SETTINGS_PATH, JSON.stringify(migrated, null, 2) + "\n", "utf-8");
    logger.info("Settings migrated successfully — provider env vars replaced with proxy routing");
    return true;
  } catch (err) {
    logger.error(`Cannot write ${SETTINGS_PATH}: ${String(err)}`);
    return false;
  }
}

/**
 * Check if the settings need migration.
 */
function needsMigration(settings: ClaudeSettings): boolean {
  const env = settings.env ?? {};

  // If ANTHROPIC_BASE_URL already points to our proxy and no removed vars exist, we're done
  const baseUrlOk = env.ANTHROPIC_BASE_URL === PROXY_URL;
  const hasRemovedVars = REMOVED_ENV_VARS.some(v => v in env);

  if (baseUrlOk && !hasRemovedVars) return false;

  // Migration needed if any removed vars exist or base URL is wrong
  return true;
}

/**
 * Migrate the settings object.
 */
function migrateSettings(settings: ClaudeSettings): ClaudeSettings {
  const env = { ...(settings.env ?? {}) };

  // Remove provider-specific env vars
  for (const key of REMOVED_ENV_VARS) {
    if (key in env) {
      logger.info(`Removing env var: ${key}`);
      delete env[key];
    }
  }

  // Set required env vars
  for (const [key, value] of Object.entries(REQUIRED_ENV)) {
    if (env[key] !== value) {
      logger.info(`Setting env var: ${key}=${value}`);
      env[key] = value;
    }
  }

  // Clean up empty env block
  const cleanedEnv = Object.keys(env).length > 0 ? env : undefined;

  return {
    ...settings,
    env: cleanedEnv,
  };
}

/**
 * Extract provider credentials from the current settings BEFORE migration.
 * This allows the proxy to pick up existing keys from settings.json
 * on first run (before the user creates a .env file).
 */
export function extractCredentialsFromSettings(): {
  zAiApiKey?: string;
  zAiBaseUrl?: string;
  anthropicApiKey?: string;
} {
  if (!fs.existsSync(SETTINGS_PATH)) return {};

  try {
    const raw = fs.readFileSync(SETTINGS_PATH, "utf-8");
    const settings: ClaudeSettings = JSON.parse(raw);
    const env = settings.env ?? {};

    return {
      zAiApiKey: env.ANTHROPIC_AUTH_TOKEN,
      zAiBaseUrl: env.ANTHROPIC_BASE_URL !== PROXY_URL
        ? env.ANTHROPIC_BASE_URL
        : undefined,
      // No anthropic direct key in current settings — that's new
    };
  } catch {
    return {};
  }
}
