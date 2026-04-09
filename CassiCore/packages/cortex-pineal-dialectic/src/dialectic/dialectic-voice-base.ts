/**
 * DialecticVoiceBase — Shared base class for dialectic voices (Yang, Yin, Serenity)
 *
 * Extracts common infrastructure: provider interaction, JSON repair, logging,
 * and dependency wiring. Voice-specific logic remains in subclasses.
 */

import type { PromptOptimizer } from './prompt-optimizer.js';
import type { ILogger , IEventBus } from '../../../types/interfaces.js';
import type { IProvider } from '../../../types/runtime.js';
import type { ModuleSessionRegistry } from '../module-session-registry.js';
import { ActivityTimeout } from '../../utils/activity-timeout.js';

/**
 * Base configuration shared by all dialectic voices
 */
export interface BaseDialecticConfig {
  enabled: boolean;
  model: string;
  temperature: number;
}

/**
 * Options for provider calls
 */
export interface CallProviderOptions {
  provider?: IProvider;
  model?: string;
  maxTokens?: number;
  allowConcurrent?: boolean;
  dedupe?: boolean;
  /** Stall detection: kill if no streaming chunks arrive within this window. */
  inactivityMs?: number;
  signal?: AbortSignal;
}

/**
 * Result from a provider call
 */
export interface ProviderCallResult {
  text: string;
  inputTokens: number;
  outputTokens: number;
}

/**
 * Base class for all dialectic voices (Yang, Yin, Serenity)
 *
 * @template TConfig - Voice-specific config type extending BaseDialecticConfig
 */
export abstract class DialecticVoiceBase<TConfig extends BaseDialecticConfig> {
  /** Voice identifier */
  protected readonly voiceName: string;

  /** Voice configuration */
  protected config: TConfig;

  /** Child logger for this voice */
  protected logger: ILogger;

  /** LLM provider for generation */
  protected provider?: IProvider;

  /** Event bus for emitting signals and repairs */
  protected eventBus?: IEventBus;

  /** Prompt optimizer for variant selection */
  protected promptOptimizer?: PromptOptimizer;

  /** Module session registry for persistent debug sessions */
  protected moduleRegistry?: ModuleSessionRegistry;

  /**
   * The requestId from the most recent callProvider() invocation.
   * Set by the onMeta callback. Used by the dialectic module to tag
   * outcome events (dialectic:signal) for traceability.
   */
  protected _lastRequestId?: string;

  /**
   * Create a new dialectic voice instance
   *
   * @param logger - Root logger
   * @param config - Voice-specific configuration
   * @param name - Voice name for logging
   */
  constructor(logger: ILogger, config: TConfig, name: string) {
    this.voiceName = name;
    this.logger = logger.child?.(name) ?? logger;
    this.config = config;

    if (this.config.enabled) {
      this.logger.info(`${this.constructor.name}: enabled`, { model: this.config.model });
    } else {
      this.logger.info(`${this.constructor.name}: disabled`);
    }
  }

  /**
   * Wire the LLM provider for this voice
   *
   * @param provider - Provider implementation
   */
  setProvider(provider: IProvider): void {
    this.provider = provider;
    this.logger.info(`${this.constructor.name}: provider wired`);
  }

  /** Wire the module session registry for persistent debug sessions. */
  setModuleRegistry(registry: ModuleSessionRegistry): void {
    this.moduleRegistry = registry;
    registry.getOrCreate('dialectic');
  }

  /**
   * Wire the event bus for emitting signals and repairs
   *
   * @param bus - Event bus implementation
   */
  setEventBus(bus: IEventBus): void {
    this.eventBus = bus;
    this.logger.info(`${this.constructor.name}: event bus wired`);
  }

  /**
   * Wire the prompt optimizer for variant selection
   *
   * @param optimizer - Prompt optimizer instance
   */
  setPromptOptimizer(optimizer: PromptOptimizer): void {
    this.promptOptimizer = optimizer;
    this.logger.info(`${this.constructor.name}: prompt optimizer wired`);
  }

  /**
   * Call the LLM provider with retry logic for deduplication errors
   *
   * Handles streaming responses, timeout management, and token counting.
   * Retries up to 3 times on deduplication errors with exponential backoff.
   *
   * @param prompt - The prompt to send
   * @param opts - Call options (provider override, model, maxTokens, etc.)
   * @returns Provider response with text and token counts
   */
  protected async callProvider(prompt: string, opts?: CallProviderOptions): Promise<ProviderCallResult> {
    const messages = [{ role: 'user' as const, content: prompt }];

    const modelSpec = opts?.model ?? this.config.model;
    const slashIdx = modelSpec.indexOf('/');
    const modelName = slashIdx >= 0 ? modelSpec.slice(slashIdx + 1) : modelSpec;

    // Reset before the call — onMeta fires synchronously after requestId generation
    this._lastRequestId = undefined;

    const callOpts: any = {
      model: modelName,
      stream: true as const,
      maxTokens: opts?.maxTokens ?? 2000,
      temperature: this.config.temperature,
      thinking: 'none' as const,
      source: `dialectic:${this.constructor.name.toLowerCase()}`,
      onMeta: (meta: { requestId: string }) => { this._lastRequestId = meta.requestId },
      // Bind to persistent module debug session for Telegram observability
      sessionId: this.moduleRegistry?.getSessionId('dialectic'),
    };

    if (opts?.allowConcurrent) callOpts.allowConcurrent = true;
    if (opts?.dedupe === false) callOpts.dedupe = false;

    const provider = opts?.provider ?? this.provider!;

    const isDedupError = (err: any): boolean => {
      const s = String(err || '');
      return /Request already in progress|already has in-flight|deduplicat|dedupe/i.test(s);
    };

    const maxRetries = 3;
    let attempt = 0;
    const baseDelay = 150;
    const inactivityMs = opts?.inactivityMs ?? 30_000;

    while (true) {
      attempt++;
      try {
        try {
          this.logger?.info?.(`${this.constructor.name}.callProvider: invoking provider`, {
            model: modelName,
            allowConcurrent: callOpts.allowConcurrent,
            dedupe: callOpts.dedupe,
          });
        } catch {}

        const stream = (provider as any).complete(messages, callOpts as any, undefined, opts?.signal) as AsyncIterable<any>;

        let text = '';
        let outputTokens = 0;

        const activityTimeout = new ActivityTimeout({
          inactivityMs,
          label: `dialectic:${this.constructor.name}`,
          parentSignal: opts?.signal,
        });

        try {
          for await (const chunk of ActivityTimeout.wrapIterator(stream, activityTimeout)) {
            if (chunk.type === 'token' && chunk.text) {
              text += chunk.text;
              outputTokens += chunk.tokensUsed || Math.ceil(chunk.text.length / 4);
            } else if (chunk.type === 'error') {
              if (isDedupError(chunk.error)) throw new Error(chunk.error || 'Request deduplicated');
              throw new Error(chunk.error || 'Provider error');
            } else if (chunk.type === 'done') {
              break;
            }
          }

          if (activityTimeout.fired) {
            throw new Error(`Provider request timed out (${activityTimeout.reason})`);
          }
        } finally {
          activityTimeout.dispose();
        }

        const inputTokens = Math.ceil(prompt.length / 4);
        return { text: text.trim(), inputTokens, outputTokens };
      } catch (err) {
        if (isDedupError(err) && attempt < maxRetries) {
          const wait = baseDelay * Math.pow(2, attempt - 1) + Math.round(Math.random() * 100);
          try {
            this.logger?.warn?.(`${this.constructor.name}: provider request deduped, backing off and retrying`, {
              attempt,
              wait,
              error: String(err),
            });
          } catch {}
          await new Promise(res => setTimeout(res, wait));
          continue;
        }
        throw err;
      }
    }
  }

  /**
   * Attempt to repair malformed JSON via the Thinker module
   *
   * Emits a repair request to the event bus and waits for a response.
   * Returns null if repair fails or times out.
   *
   * @param text - Raw text that failed to parse
   * @param schema - JSON schema description for the repair
   * @param timeoutMs - Maximum time to wait for repair response
   * @returns Repaired JSON string or null
   */
  protected async attemptThinkerRepair(text: string, schema: string, timeoutMs = 5000): Promise<string | null> {
    if (!this.eventBus) return null;

    try {
      const reqId = `${this.voiceName}-repair-${Date.now()}-${Math.random().toString(36).slice(2, 6)}`;
      const repairPrompt = `The previous response failed to produce valid JSON. Convert the following TEXT into valid JSON matching EXACTLY this schema and WRAP the JSON between the literal markers ---BEGIN_JSON--- and ---END_JSON---. Return NOTHING else.\n\nSCHEMA:\n${schema}\n\nTEXT:"""${text}"""\n\nReturn exactly: ---BEGIN_JSON---<JSON>---END_JSON---`;

      try {
        (this.eventBus as any).emit?.({ type: 'thinker:repair-request', id: reqId, prompt: repairPrompt });
      } catch (e) {
        // Ignore emit errors
      }

      const resp = await new Promise<string | null>((resolve) => {
        let done = false;
        const handler = (ev: any) => {
          try {
            if (!ev || ev?.id !== reqId) return;
            done = true;
            try { (this.eventBus as any).off?.('thinker:repair-response', handler); } catch {}
            if (ev.error) return resolve(null);
            resolve(ev.text || null);
          } catch (err) {
            resolve(null);
          }
        };
        try {
          (this.eventBus as any).on?.('thinker:repair-response', handler);
        } catch (err) {
          return resolve(null);
        }
        setTimeout(() => {
          if (!done) {
            try { (this.eventBus as any).off?.('thinker:repair-response', handler); } catch {}
            resolve(null);
          }
        }, timeoutMs);
      });

      if (resp) {
        const m = resp.match(/---BEGIN_JSON---([\s\S]*?)---END_JSON---/);
        return m ? m[1] : (resp.match(/\{[\s\S]*\}/) || [])[0] || null;
      }
      return null;
    } catch (err) {
      this.logger?.warn?.(`${this.constructor.name}: thinker repair failed`, { error: String(err) });
      return null;
    }
  }

  /**
   * Attempt to repair malformed JSON via the LLM provider
   *
   * Sends a repair prompt to the provider with strict schema instructions.
   * Returns null if repair fails or times out.
   *
   * @param text - Raw text that failed to parse
   * @param schema - JSON schema description for the repair
   * @param provider - Provider to use for repair
   * @param modelOverride - Optional model override
   * @param signal - Abort signal for cancellation
   * @returns Repaired JSON string or null
   */
  protected async attemptProviderRepair(
    text: string,
    schema: string,
    provider: IProvider,
    modelOverride?: string,
    signal?: AbortSignal,
  ): Promise<string | null> {
    try {
      const modelSpec = modelOverride ?? this.config.model;
      const slashIdx = modelSpec.indexOf('/');
      const modelName = slashIdx >= 0 ? modelSpec.slice(slashIdx + 1) : modelSpec;

      const prompt = `The previous response failed to produce valid JSON. Convert the following TEXT into valid JSON matching EXACTLY this schema and WRAP the JSON between the literal markers ---BEGIN_JSON--- and ---END_JSON---. Return NOTHING else.\n\nSCHEMA:\n${schema}\n\nTEXT:"""${text}"""\n\nReturn exactly: ---BEGIN_JSON---<JSON>---END_JSON---`;

      this.logger.info(`${this.constructor.name}: no JSON found — attempting JSON repair call to provider (attempt 1)`);
      const messages = [{ role: 'user' as const, content: prompt }];
      const callOpts: any = { model: modelName, stream: true as const, maxTokens: 2000, temperature: 0.0, allowConcurrent: true };
      const stream = (provider as any).complete(messages, callOpts as any, undefined, signal) as AsyncIterable<any>;
      let collected = '';
      const iterator = (stream as any)[Symbol.asyncIterator]() as AsyncIterator<any>;
      const start = Date.now();
      const repairTimeout = 10000;

      while (true) {
        const timeLeft = Math.max(0, repairTimeout - (Date.now() - start));
        if (timeLeft <= 0) {
          try { await iterator.return?.(); } catch {}
          break;
        }
        const nextPromise = iterator.next();
        const timeoutPromise = new Promise<never>((_, rej) =>
          setTimeout(() => rej(new Error('timeout')), timeLeft),
        );
        try {
          const res = await Promise.race([nextPromise, timeoutPromise]) as IteratorResult<any>;
          if (res.done) break;
          const ch = res.value;
          if ((ch.type === 'token' || ch.type === 'thinking') && ch.text) collected += ch.text;
          else if (ch.type === 'error') throw new Error(ch.error || 'Provider error');
          else if (ch.type === 'done') break;
        } catch (err) {
          if ((err as Error).message === 'timeout') {
            try { await iterator.return?.(); } catch {}
            break;
          }
          break;
        }
      }

      const repairText = (collected || '').trim();
      const markersMatch = repairText.match(/---BEGIN_JSON---([\s\S]*?)---END_JSON---/);
      return markersMatch ? markersMatch[1] : (repairText.match(/\{[\s\S]*\}/) || [])[0] || null;
    } catch (err) {
      this.logger.warn(`${this.constructor.name}: provider repair attempt failed`, { error: String(err) });
      return null;
    }
  }

  /**
   * Parse plain text into structured items using heuristics
   *
   * Handles various list formats: numbered items, bullet points, paragraphs.
   * Used as a fallback when JSON parsing fails.
   *
   * @param raw - Raw text to parse
   * @returns Array of extracted items
   */
  protected parseIntoItems(raw: string): string[] {
    const lines = raw.split(/\r?\n/);
    const markerRegex = /^\s*(?:\d+[\.\)]|[-*•])\s+(.*)$/;
    let markerCount = 0;
    for (const l of lines) if (markerRegex.test(l)) markerCount++;

    if (markerCount >= 2) {
      const items: string[] = [];
      let current: string[] = [];
      for (const line of lines) {
        const m = line.match(markerRegex);
        if (m) {
          if (current.length) items.push(current.join(' ').trim());
          current = [m[1].trim()];
        } else {
          if (!line.trim()) continue;
          if (!current.length) current = [line.trim()];
          else current.push(line.trim());
        }
      }
      if (current.length) items.push(current.join(' ').trim());
      return items.filter(Boolean);
    }

    const paras = raw.split(/\n\s*\n+/).map(p => p.trim()).filter(Boolean);
    if (paras.length >= 2) return paras;

    const numberedParts = raw.split(/\n(?=\d+[\.\)]\s)/).map(p => p.trim()).filter(Boolean);
    if (numberedParts.length >= 2) return numberedParts;

    const longLines = lines.map(l => l.trim()).filter(l => l.length > 40);
    if (longLines.length >= 2) return longLines;

    return [raw.trim()];
  }

  /**
   * Extract JSON from a text response
   *
   * Looks for JSON objects or arrays wrapped in markers or raw.
   *
   * @param text - Text potentially containing JSON
   * @returns Extracted JSON string or null
   */
  protected extractJson(text: string): string | null {
    // Look for marker-wrapped JSON first
    const markerMatch = text.match(/---BEGIN_JSON---([\s\S]*?)---END_JSON---/);
    if (markerMatch) return markerMatch[1].trim();

    // Look for raw JSON object or array
    const jsonMatch = text.match(/\{[\s\S]*\}|\[[\s\S]*\]/);
    return jsonMatch ? jsonMatch[0] : null;
  }

  /**
   * Clamp a number between min and max
   *
   * @param value - Value to clamp
   * @param min - Minimum allowed value
   * @param max - Maximum allowed value
   * @returns Clamped value
   */
  protected clamp(value: number, min: number, max: number): number {
    return Math.max(min, Math.min(max, value));
  }

  /**
   * Check if the voice is enabled
   *
   * @returns True if enabled
   */
  get enabled(): boolean {
    return this.config.enabled;
  }
}
