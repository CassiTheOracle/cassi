/**
 * Centralized System Settings for CassiCore
 * 
 * This file contains all tunable system parameters in one place.
 * Modify values here to adjust behavior across the entire system.
 * 
 * Environment variables can override any setting using the
 * CASSICORE_ prefix (e.g., CASSICORE_CONTEXT_MAX_TOKENS=20000)
 */

// ============================================================================
// Centralized Model Defaults
// ============================================================================
//
// Single source of truth for default model assignments across the entire system.
// Every component that needs a model should reference these constants rather
// than hardcoding provider/model strings. This enables changing the default
// model for an entire tier in one place.
//
// Tiers:
//   main      — User-facing main agent (turn pipeline, sessions)
//   reasoning — Background intelligence modules (thinker, dialectic, memory, etc.)
//   agent     — Spawned sub-agents and team members
//   fast      — Low-latency local operations (reflex, quick parsing)
//
// Format: 'provider/model' combined string, split at consumption sites.

export const MODEL_DEFAULTS = {
  /** Main agent — the user-facing conversational model */
  main: {
    provider: getEnvString('CASSICORE_MODEL_MAIN_PROVIDER', 'kimi-coding'),
    model: getEnvString('CASSICORE_MODEL_MAIN', 'k2p5'),
  },

  /** Background reasoning — intelligence modules (thinker, dialectic, memory, subconscious) */
  reasoning: {
    provider: getEnvString('CASSICORE_MODEL_REASONING_PROVIDER', 'kimi-coding'),
    model: getEnvString('CASSICORE_MODEL_REASONING', 'k2p5'),
  },

  /** Spawned agents — team members, sub-agents, coordinators */
  agent: {
    provider: getEnvString('CASSICORE_MODEL_AGENT_PROVIDER', 'kimi-coding'),
    model: getEnvString('CASSICORE_MODEL_AGENT', 'k2p5'),
  },

  /** Fast local — reflex, quick intent parsing, low-latency operations */
  fast: {
    provider: getEnvString('CASSICORE_MODEL_FAST_PROVIDER', 'lmstudio'),
    model: getEnvString('CASSICORE_MODEL_FAST', 'lfm2.5-1.2b'),
  },

  /** Fallback — used when provider resolution fails entirely */
  fallback: {
    provider: getEnvString('CASSICORE_MODEL_FALLBACK_PROVIDER', 'github-copilot'),
    model: getEnvString('CASSICORE_MODEL_FALLBACK', 'gpt-5-mini'),
  },
} as const

/**
 * Convenience: get a combined 'provider/model' string for a tier.
 */
export function getModelSpec(tier: keyof typeof MODEL_DEFAULTS): string {
  const { provider, model } = MODEL_DEFAULTS[tier]
  return `${provider}/${model}`
}

// ============================================================================
// Context & Memory Settings
// ============================================================================

export const CONTEXT_SETTINGS = {
  /** Maximum tokens for context window (affects all context assembly) */
  maxTokens: getEnvNumber('CASSICORE_CONTEXT_MAX_TOKENS', 20_000),
  // TODO Immediately: create a separate setting for the main agent

  /** Character budget for context assembly (roughly 3-4 chars per token) */
  charBudget: getEnvNumber('CASSICORE_CONTEXT_CHAR_BUDGET', 60_000),

  /** Context manager default char budget */
  contextManagerCharBudget: getEnvNumber('CASSICORE_CONTEXT_MANAGER_BUDGET', 60_000),

  /** Context assembler default char budget */
  assemblerCharBudget: getEnvNumber('CASSICORE_ASSEMBLER_BUDGET', 48_000),

  /** Subconscious context enrichment budget */
  subconsciousContextBudget: getEnvNumber('CASSICORE_SUBCONSCIOUS_CONTEXT_BUDGET', 20_000),

  /** How often to refresh context from ContextManager (ms) */
  contextRefreshIntervalMs: getEnvNumber('CASSICORE_CONTEXT_REFRESH_MS', 1_000),

  /** Cache TTL for context assembly results (ms) */
  contextCacheTtlMs: getEnvNumber('CASSICORE_CONTEXT_CACHE_TTL_MS', 30000),

  /** Maximum history turns to include in context */
  maxHistoryTurns: getEnvNumber('CASSICORE_MAX_HISTORY_TURNS', 100),

  /** Maximum file content size before truncation (chars) */
  maxFileContentChars: getEnvNumber('CASSICORE_MAX_FILE_CONTENT_CHARS', 50_000),
} as const;

// ============================================================================
// Subconscious Settings
// ============================================================================

export const SUBCONSCIOUS_SETTINGS = {
  /** Enable v2 real-time stream processing */
  v2Enabled: getEnvBoolean('CASSICORE_SUBCONSCIOUS_V2', true),

  /** Token buffer max size (tokens) */
  bufferMaxTokens: getEnvNumber('CASSICORE_SUBCONSCIOUS_BUFFER_MAX', 16384),

  /** Sliding window size for active analysis (tokens) */
  slidingWindowTokens: getEnvNumber('CASSICORE_SUBCONSCIOUS_WINDOW', 6000),

  /** How often to check for patterns (tokens) */
  patternCheckInterval: getEnvNumber('CASSICORE_SUBCONSCIOUS_PATTERN_INTERVAL', 10),

  /** Minimum confidence for signals (0-1) */
  signalMinConfidence: getEnvNumber('CASSICORE_SUBCONSCIOUS_MIN_CONFIDENCE', 0.7),

  /** Cooldown between same signal type (ms) */
  signalCooldownMs: getEnvNumber('CASSICORE_SUBCONSCIOUS_SIGNAL_COOLDOWN', 1000),

  /** Enable dependency tracking in mental model */
  trackDependencies: getEnvBoolean('CASSICORE_SUBCONSCIOUS_TRACK_DEPS', true),

  /** Enable phase detection */
  detectPhases: getEnvBoolean('CASSICORE_SUBCONSCIOUS_DETECT_PHASES', true),

  /** Background consolidation interval (ms) */
  consolidationIntervalMs: getEnvNumber('CASSICORE_SUBCONSCIOUS_CONSOLIDATION_MS', 30_000),
} as const;

// ============================================================================
// Dialectic Settings
// ============================================================================

export const DIALECTIC_SETTINGS = {
  /** Execution mode: 'sequential' | 'parallel' | 'adaptive' */
  mode: getEnvString('CASSICORE_DIALECTIC_MODE', 'parallel') as 'sequential' | 'parallel' | 'adaptive',

  /** Maximum wait time for parallel observers (ms) */
  parallelMaxWaitMs: getEnvNumber('CASSICORE_DIALECTIC_MAX_WAIT_MS', 8000),

  /** Timeout per observer (ms) */
  observerTimeoutMs: getEnvNumber('CASSICORE_DIALECTIC_OBSERVER_TIMEOUT_MS', 6000),

  /** Allow partial results on failure */
  partialResultsOnFailure: getEnvBoolean('CASSICORE_DIALECTIC_PARTIAL_RESULTS', true),

  /** Synchronization strategy */
  synchronization: getEnvString('CASSICORE_DIALECTIC_SYNC', 'best-effort') as 'wait-for-both' | 'best-effort',

  /** Enable task guide generation */
  taskGuideEnabled: getEnvBoolean('CASSICORE_DIALECTIC_TASK_GUIDE', true),

  /** Subconscious context TTL (ms) - how long to use subconscious signals */
  subconsciousContextTtlMs: getEnvNumber('CASSICORE_DIALECTIC_SUBCONSCIOUS_TTL_MS', 5 * 60 * 1000),
} as const;

// ============================================================================
// Thinker Settings
// ============================================================================

export const THINKER_SETTINGS = {
  /** Enable Thinker module */
  enabled: getEnvBoolean('CASSICORE_THINKER_ENABLED', true),

  /** Fire ponder every N turns */
  ponderInterval: getEnvNumber('CASSICORE_THINKER_PONDER_INTERVAL', 5),

  /** Fire think every M turns */
  thinkInterval: getEnvNumber('CASSICORE_THINKER_THINK_INTERVAL', 12),

  /** Model for quick reflections (ponder) — defaults to reasoning tier */
  ponderModel: getEnvString('CASSICORE_THINKER_PONDER_MODEL', MODEL_DEFAULTS.reasoning.model),

  /** Model for deep synthesis (think) — defaults to reasoning tier */
  thinkModel: getEnvString('CASSICORE_THINKER_THINK_MODEL', MODEL_DEFAULTS.reasoning.model),

  /** Enable swarm coordination */
  enableSwarm: getEnvBoolean('CASSICORE_THINKER_SWARM', true),

  /** Enable adaptive strategy */
  enableAdaptation: getEnvBoolean('CASSICORE_THINKER_ADAPTATION', true),
} as const;

// ============================================================================
// Session & Pipeline Settings
// ============================================================================

export const SESSION_SETTINGS = {
  /** Default max context tokens per session */
  defaultMaxContextTokens: getEnvNumber('CASSICORE_SESSION_MAX_TOKENS', 20_000),

  /** Default thinking level: 'none' | 'low' | 'medium' | 'high' */
  defaultThinking: getEnvString('CASSICORE_DEFAULT_THINKING', 'high') as 'none' | 'low' | 'medium' | 'high',

  /** Max tool rounds per turn */
  maxToolRounds: getEnvNumber('CASSICORE_MAX_TOOL_ROUNDS', 999),

  /** Session compaction threshold (turns) */
  compactionThreshold: getEnvNumber('CASSICORE_COMPACTION_THRESHOLD', 100),
} as const;

// ============================================================================
// Provider Settings
// ============================================================================

export const PROVIDER_SETTINGS = {
  /** Default provider ID — defaults to main tier */
  defaultProvider: getEnvString('CASSICORE_DEFAULT_PROVIDER', MODEL_DEFAULTS.main.provider),

  /** Default model — defaults to main tier */
  defaultModel: getEnvString('CASSICORE_DEFAULT_MODEL', MODEL_DEFAULTS.main.model),

  /** Enable request deduplication */
  enableDeduplication: getEnvBoolean('CASSICORE_PROVIDER_DEDUP', true),

  /** Consecutive error threshold for cooldown */
  errorCooldownThreshold: getEnvNumber('CASSICORE_PROVIDER_ERROR_THRESHOLD', 3),

  /** Cooldown duration after errors (ms) */
  errorCooldownMs: getEnvNumber('CASSICORE_PROVIDER_COOLDOWN_MS', 30_000),
} as const;

// ============================================================================
// Request Budget Settings
// ============================================================================
//
// Request-based providers (like GitHub Copilot) have monthly request limits
// rather than token-based billing. These settings control budget tracking
// and progressive degradation of background intelligence tasks as quota depletes.
//
// Some models on metered providers are exempt (e.g., gpt-5-mini on Copilot).
// The cost classifier handles this — see core/providers/cost-classifier.ts.

export const BUDGET_SETTINGS = {
  /** Monthly request limits per provider */
  monthlyLimits: {
    'github-copilot': getEnvNumber('CASSICORE_BUDGET_GITHUB_COPILOT', 1500),
  } as Record<string, number>,

  /** Free offload model for background tasks (must be classified as 'free') */
  freeOffloadModel: getEnvString('CASSICORE_FREE_OFFLOAD_MODEL', 'github-copilot/gpt-5-mini'),

  /** Budget tier thresholds (percentage 0-1) */
  tiers: {
    /** 0-50%: all modules active with preferred models */
    cautious: getEnvNumber('CASSICORE_BUDGET_TIER_CAUTIOUS', 50) / 100,
    /** 50-75%: background tasks prefer free models */
    frugal: getEnvNumber('CASSICORE_BUDGET_TIER_FRUGAL', 75) / 100,
    /** 75-90%: non-essential background tasks disabled */
    critical: getEnvNumber('CASSICORE_BUDGET_TIER_CRITICAL', 90) / 100,
  },
} as const;

// ============================================================================
// Logging & Monitoring Settings
// ============================================================================

export const LOGGING_SETTINGS = {
  /** Default log level */
  logLevel: getEnvString('CASSICORE_LOG_LEVEL', 'info') as 'debug' | 'info' | 'warn' | 'error',

  /** Enable performance metrics */
  enableMetrics: getEnvBoolean('CASSICORE_ENABLE_METRICS', true),

  /** Metrics flush interval (ms) */
  metricsIntervalMs: getEnvNumber('CASSICORE_METRICS_INTERVAL_MS', 600_000),
} as const;

// ============================================================================
// Reflex Settings (Autonomic Tool Execution)
// ============================================================================

export const REFLEX_SETTINGS = {
  /** Enable the Reflex module */
  enabled: getEnvBoolean('CASSICORE_REFLEX_ENABLED', true),

  /** LLM provider for intent parsing — defaults to fast tier */
  providerId: getEnvString('CASSICORE_REFLEX_PROVIDER', MODEL_DEFAULTS.fast.provider),

  /** Model for intent parsing — defaults to fast tier */
  model: getEnvString('CASSICORE_REFLEX_MODEL', MODEL_DEFAULTS.fast.model),

  /** Temperature for intent parsing (lower = more deterministic) */
  temperature: getEnvNumber('CASSICORE_REFLEX_TEMPERATURE', 0.1),

  /** Max tokens for intent parsing response */
  maxTokens: getEnvNumber('CASSICORE_REFLEX_MAX_TOKENS', 512),

  /** Timeout for LLM inference (ms) */
  inferenceTimeoutMs: getEnvNumber('CASSICORE_REFLEX_INFERENCE_TIMEOUT_MS', 5_000),

  /** Cooldown between reflex triggers for the same tool (ms) */
  toolCooldownMs: getEnvNumber('CASSICORE_REFLEX_TOOL_COOLDOWN_MS', 3_000),

  /** Maximum concurrent tool executions */
  maxConcurrentTools: getEnvNumber('CASSICORE_REFLEX_MAX_CONCURRENT', 2),

  /** Maximum tool execution time (ms) — safety guard */
  toolTimeoutMs: getEnvNumber('CASSICORE_REFLEX_TOOL_TIMEOUT_MS', 15_000),

  /** Minimum confidence from LLM to trigger a tool (0-1) */
  minConfidence: getEnvNumber('CASSICORE_REFLEX_MIN_CONFIDENCE', 0.6),

  /** Allowed read-only tools (whitelist) */
  allowedTools: getEnvString('CASSICORE_REFLEX_ALLOWED_TOOLS',
    'gitnexus_query,gitnexus_context,gitnexus_impact,read_file,find_symbol,web_search,memory_search'
  ).split(',').map(t => t.trim()),
} as const;

// ============================================================================
// Prompt Optimizer Settings (Dialectic Prompt Variant Selection)
// ============================================================================

export const PROMPT_OPTIMIZER_SETTINGS = {
  /** Enable prompt variant optimization */
  enabled: getEnvBoolean('CASSICORE_PROMPT_OPTIMIZER_ENABLED', true),

  /** Epsilon for exploration vs exploitation (0 = always exploit, 1 = always explore) */
  epsilon: getEnvNumber('CASSICORE_PROMPT_OPTIMIZER_EPSILON', 0.2),

  /** EMA smoothing factor (higher = faster adaptation, lower = more stable) */
  alpha: getEnvNumber('CASSICORE_PROMPT_OPTIMIZER_ALPHA', 0.3),

  /** Minimum uses before a variant is eligible for exploitation */
  minUsesForExploitation: getEnvNumber('CASSICORE_PROMPT_OPTIMIZER_MIN_USES', 3),
} as const;

// ============================================================================
// Helper Functions
// ============================================================================

function getEnvString(key: string, defaultValue: string): string {
  const value = process.env[key];
  return value !== undefined ? value : defaultValue;
}

function getEnvNumber(key: string, defaultValue: number): number {
  const value = process.env[key];
  if (value === undefined) return defaultValue;
  const parsed = parseInt(value, 10);
  return isNaN(parsed) ? defaultValue : parsed;
}

function getEnvBoolean(key: string, defaultValue: boolean): boolean {
  const value = process.env[key];
  if (value === undefined) return defaultValue;
  return value.toLowerCase() === 'true' || value === '1';
}

// ============================================================================
// Export All Settings
// ============================================================================

export const SYSTEM_SETTINGS = {
  models: MODEL_DEFAULTS,
  context: CONTEXT_SETTINGS,
  subconscious: SUBCONSCIOUS_SETTINGS,
  dialectic: DIALECTIC_SETTINGS,
  thinker: THINKER_SETTINGS,
  session: SESSION_SETTINGS,
  provider: PROVIDER_SETTINGS,
  budget: BUDGET_SETTINGS,
  logging: LOGGING_SETTINGS,
  reflex: REFLEX_SETTINGS,
  promptOptimizer: PROMPT_OPTIMIZER_SETTINGS,
} as const;

/** 
 * Get a setting value with type safety
 * Usage: getSetting('context', 'maxTokens')
 */
export function getSetting<T extends keyof typeof SYSTEM_SETTINGS>(
  module: T,
  key: keyof typeof SYSTEM_SETTINGS[T]
): typeof SYSTEM_SETTINGS[T][typeof key] {
  return SYSTEM_SETTINGS[module][key];
}

/** 
 * Override settings at runtime (for testing/dynamic config)
 * Usage: overrideSetting('context', 'maxTokens', 30000)
 */
export function overrideSetting<T extends keyof typeof SYSTEM_SETTINGS>(
  module: T,
  key: keyof typeof SYSTEM_SETTINGS[T],
  value: typeof SYSTEM_SETTINGS[T][typeof key]
): void {
  (SYSTEM_SETTINGS[module] as any)[key] = value;
}

export default SYSTEM_SETTINGS;
