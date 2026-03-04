/**
 * YangObserver — The Principle of Expansion
 *
 * Generates creative, divergent branches of thought.
 * Explores alternatives, edge cases, cross-domain connections, and challenges assumptions.
 */

import type { ILogger } from '../../../types/interfaces.js';
import type { IYangObserver, YangOutput, YangContext, YangBranch } from '../../../types/dialectic.js';
import type { IProvider } from '../../../types/runtime.js';
import type { IEventBus } from '../../../types/interfaces.js';
import { fillTemplate } from './prompt-optimizer.js';
import type { PromptOptimizer } from './prompt-optimizer.js';
import { getModelSpec } from '../../config/system-settings.js'

export interface YangConfig {
  enabled: boolean;
  model: string;           // GPT-5 Mini or equivalent
  temperature: number;     // default 0.7 — creative but coherent
  maxBranches: number;     // default 5
  minConfidence: number;   // default 0.5
}

export class YangObserver implements IYangObserver {
  readonly name = 'yang' as const;

  private logger: ILogger;
  private config: YangConfig;
  private provider?: IProvider;
  private eventBus?: IEventBus;
  private promptOptimizer?: PromptOptimizer;

  constructor(logger: ILogger, config?: Partial<YangConfig>) {
    this.logger = logger.child?.('yang') ?? logger;
    this.config = {
      enabled: config?.enabled ?? true,
      model: config?.model ?? getModelSpec('reasoning'),
      temperature: config?.temperature ?? 0.7,
      maxBranches: config?.maxBranches ?? 5,
      minConfidence: config?.minConfidence ?? 0.5,
    };

    if (this.config.enabled) {
      this.logger.info('YangObserver: enabled', { model: this.config.model });
    } else {
      this.logger.info('YangObserver: disabled');
    }
  }

  setProvider(provider: IProvider): void {
    this.provider = provider;
    this.logger.info('YangObserver: provider wired');
  }

  setEventBus(bus: IEventBus): void {
    this.eventBus = bus;
    this.logger.info('YangObserver: event bus wired');
  }

  setPromptOptimizer(optimizer: PromptOptimizer): void {
    this.promptOptimizer = optimizer;
    this.logger.info('YangObserver: prompt optimizer wired');
  }

  async observe(sessionId: string, userMessage: string, context: YangContext, opts?: { model?: string; provider?: IProvider; allowConcurrent?: boolean; dedupe?: boolean; signal?: AbortSignal }): Promise<YangOutput> {
    const startTime = Date.now();

    if (!this.config.enabled) {
      return {
        branches: [],
        meta: {
          expansionTemperature: this.config.temperature,
          generationTimeMs: 0,
          inputTokens: 0,
          outputTokens: 0,
        },
      };
    }

    const providerToUse = opts?.provider ?? this.provider;
    if (!providerToUse) {
      this.logger.warn('YangObserver: no provider wired, skipping');
      return {
        branches: [],
        meta: {
          expansionTemperature: this.config.temperature,
          generationTimeMs: 0,
          inputTokens: 0,
          outputTokens: 0,
        },
      };
    }

    try {
      // If maxBranches <= 1, use legacy single-call behaviour
      const targetBranches = Math.max(1, this.config.maxBranches);
      const modelSpec = opts?.model ?? this.config.model;
      const slash = modelSpec.indexOf('/');
      const modelName = slash >= 0 ? modelSpec.slice(slash + 1) : modelSpec;

      if (targetBranches <= 1) {
        const prompt = this.buildPrompt(sessionId, userMessage, context);
        const response = await this.callProvider(prompt, { provider: providerToUse, model: opts?.model, allowConcurrent: opts?.allowConcurrent, dedupe: opts?.dedupe, timeoutMs: 30000 });
        const branches = await this.parseResponse(response, providerToUse, opts?.model, opts?.signal);
        const filteredBranches = branches.filter(b => b.confidence >= this.config.minConfidence).slice(0, targetBranches);
        const generationTimeMs = Date.now() - startTime;
        this.logger.info('YangObserver: expansion complete', {
          sessionId,
          branchesGenerated: branches.length,
          branchesKept: filteredBranches.length,
          generationTimeMs,
        });
        return {
          branches: filteredBranches,
          meta: {
            expansionTemperature: this.config.temperature,
            generationTimeMs,
            inputTokens: response.inputTokens,
            outputTokens: response.outputTokens,
          },
        };
      }

      // Asynchronous branch generation: spawn parallel requests that each produce one branch.
      // Pre-assign types so the diversity hint in each prompt lists what other branches are exploring.
      const types: YangBranch['type'][] = ['alternative_interpretation','edge_case','cross_domain','what_if','assumption_challenge'];
      const assignedTypes = Array.from({ length: targetBranches }, (_, i) => types[i % types.length]);

      const generationTasks: Promise<YangBranch | null>[] = [];
      for (let bi = 0; bi < targetBranches; bi++) {
        const preferredType = assignedTypes[bi];
        const otherTypes = assignedTypes.filter((_, i) => i !== bi);
        const branchPrompt = this.buildBranchPrompt(sessionId, userMessage, context, bi + 1, targetBranches, preferredType, otherTypes);
        generationTasks.push((async () => {
          try {
            const resp = await this.callProvider(branchPrompt, { provider: providerToUse, model: modelName, allowConcurrent: true, dedupe: false, maxTokens: 400, timeoutMs: 30000 });
            const parsed = await this.parseResponse(resp, providerToUse, modelName, opts?.signal);
            if (parsed && parsed.length > 0) {
              return parsed[0];
            }
            return null;
          } catch (err) {
            try { this.logger?.warn?.('YangObserver: branch generation failed', { index: bi + 1, error: String(err) }) } catch {}
            return null;
          }
        })());
      }

      const settled = await Promise.allSettled(generationTasks);
      const branches: YangBranch[] = [];
      for (const s of settled) {
        if (s.status === 'fulfilled' && s.value) branches.push(s.value);
      }

      // Filter and cap
      const filtered = branches.filter(b => b.confidence >= this.config.minConfidence).slice(0, this.config.maxBranches);
      const generationTimeMs = Date.now() - startTime;
      this.logger.info('YangObserver: async expansion complete', { sessionId, branchesGenerated: branches.length, branchesKept: filtered.length, generationTimeMs });

      return {
        branches: filtered,
        meta: {
          expansionTemperature: this.config.temperature,
          generationTimeMs,
          inputTokens: 0,
          outputTokens: 0,
        },
      };
    } catch (error) {
      this.logger.error('YangObserver: expansion failed', {
        sessionId,
        error: String(error)
      });

      return {
        branches: [],
        meta: {
          expansionTemperature: this.config.temperature,
          generationTimeMs: Date.now() - startTime,
          inputTokens: 0,
          outputTokens: 0,
        },
      };
    }
  }

  private buildPrompt(sessionId: string, userMessage: string, context: YangContext): string {
    const guideBlock = context?.taskGuide
      ? `TASK GUIDE:\n${context.taskGuide}\n\n`
      : '';

    const memoryBlock = context.recentMemories.length > 0
      ? `Recent conversation context:\n${context.recentMemories.map(m => `- ${m}`).join('\n')}\n\n`
      : '';

    const toolsBlock = context.availableTools.length > 0
      ? `Available tools: ${context.availableTools.join(', ')}\n\n`
      : '';

    // Use optimizer variant if available and enabled
    if (this.promptOptimizer?.enabled) {
      const variant = this.promptOptimizer.selectYang();
      return fillTemplate(variant.template, {
        guideBlock,
        memoryBlock,
        toolsBlock,
        userMessage,
        maxBranches: String(this.config.maxBranches),
        sessionId,
      });
    }

    return `${guideBlock}${memoryBlock}${toolsBlock}You are YANG — systematic analytical expansion.\n\nUSER MESSAGE:\n"""${userMessage}"""\n\nGenerate ${this.config.maxBranches} observations. For each, pick ONE analytical lens:\n- assumption_challenge: What unstated assumption could be wrong?\n- edge_case: What boundary condition or corner case exists?\n- alternative_interpretation: What else could this mean?\n- cross_domain: What structural parallel from another domain applies?\n- what_if: What changes if a key constraint is removed/inverted?\n\nQUALITY GATE: Would this observation change how the AI responds? If not, skip it.\n\nEnsure each branch uses a different lens. Each observation: 2-4 sentences. Assign confidence (how likely relevant) and noveltyScore (how non-obvious) as 0.0-1.0.\n\nOUTPUT (JSON):\n{\n  "branches": [\n    {\n      "id": "yang-1",\n      "type": "alternative_interpretation|edge_case|cross_domain|what_if|assumption_challenge",\n      "content": "2-4 sentences",\n      "confidence": 0.0-1.0,\n      "noveltyScore": 0.0-1.0\n    }\n  ]\n}\n\nReturn ONLY valid JSON. No markdown fences, no explanation, no extra text.`;
  }

  private buildBranchPrompt(sessionId: string, userMessage: string, context: YangContext, branchIndex: number, totalBranches: number, preferredType: YangBranch['type'], otherTypes: YangBranch['type'][] = []): string {
    const guideBlock = context?.taskGuide ? `TASK GUIDE:\n${context.taskGuide}\n\n` : '';
    const memoryBlock = context.recentMemories.length > 0 ? `Recent context:\n${context.recentMemories.map(m => `- ${m}`).join('\n')}\n\n` : '';

    // List the distinct perspectives covered by other branches so this one stays non-overlapping
    const otherPerspectives = [...new Set(otherTypes)].filter(t => t !== preferredType);
    const diversityNote = otherPerspectives.length > 0
      ? `Other perspectives being explored in parallel: ${otherPerspectives.join(', ')}. Stay distinctly within your assigned angle — do NOT overlap with or paraphrase those perspectives.\n\n`
      : '';

    return `${guideBlock}${memoryBlock}You are YANG (branch ${branchIndex}/${totalBranches}) — perspective: ${preferredType}.\n\n${diversityNote}USER MESSAGE:\n"""${userMessage}"""\n\nQUALITY GATE: Would this observation change how the AI responds to the message above? If not, skip it.\n\nGenerate ONE non-obvious observation specifically from the ${preferredType} angle.\n\nOUTPUT (JSON):\n{"id":"yang-${branchIndex}","type":"${preferredType}","content":"2-4 sentences","confidence":0.0-1.0,"noveltyScore":0.0-1.0}\n\nReturn ONLY valid JSON. No markdown fences, no explanation.`;
  }

  private async callProvider(prompt: string, opts?: { provider?: IProvider; model?: string; maxTokens?: number; allowConcurrent?: boolean; dedupe?: boolean; timeoutMs?: number; signal?: AbortSignal }): Promise<{ text: string; inputTokens: number; outputTokens: number }> {
    const messages = [{ role: 'user' as const, content: prompt }];

    // Prefer explicit model override, fall back to observer config
    const modelSpec = opts?.model ?? this.config.model;
    const slashIdx = modelSpec.indexOf('/');
    const modelName = slashIdx >= 0 ? modelSpec.slice(slashIdx + 1) : modelSpec;

    const callOpts: any = {
      model: modelName,
      stream: true as const,
      maxTokens: opts?.maxTokens ?? 2000,
      temperature: this.config.temperature,
      thinking: 'none' as const,
    };

    if (opts?.allowConcurrent) callOpts.allowConcurrent = true;
    if (opts?.dedupe === false) callOpts.dedupe = false;

    const provider = opts?.provider ?? this.provider!;

    const isDedupError = (err: any) => {
      const s = String(err || '')
      return /Request already in progress|already has in-flight|deduplicat|dedupe|http\s*429|rate_limit_reached|rate limited|Rate limited|retry after/i.test(s)
    }

    const maxRetries = 3
    let attempt = 0
    const baseDelay = 150
    const timeoutMs = opts?.timeoutMs ?? 30_000

    while (true) {
      attempt++
      try {
        try { this.logger?.info?.('YangObserver.callProvider: invoking provider', { model: modelName, allowConcurrent: callOpts.allowConcurrent, dedupe: callOpts.dedupe }) } catch {}
        const stream = (provider as any).complete(messages, callOpts as any, undefined, opts?.signal) as AsyncIterable<any>;
        const iterator = (stream as any)[Symbol.asyncIterator]() as AsyncIterator<any>;

        let text = ''
        let outputTokens = 0
        const start = Date.now()

        while (true) {
          const timeLeft = Math.max(0, timeoutMs - (Date.now() - start))
          if (timeLeft <= 0) {
            try { await iterator.return?.() } catch {}
            throw new Error('Provider request timed out')
          }

          const nextPromise = iterator.next()
          const timeoutPromise = new Promise<never>((_, rej) => setTimeout(() => rej(new Error('timeout')), timeLeft))

          try {
            const res = await Promise.race([nextPromise, timeoutPromise]) as IteratorResult<any>
            if (res.done) break
            const chunk = res.value
            if (chunk.type === 'token' && chunk.text) {
              text += chunk.text;
              outputTokens += chunk.tokensUsed || Math.ceil(chunk.text.length / 4);
            } else if (chunk.type === 'error') {
              if (isDedupError(chunk.error)) throw new Error(chunk.error || 'Request deduplicated');
              throw new Error(chunk.error || 'Provider error');
            } else if (chunk.type === 'done') {
              break;
            }
          } catch (err) {
            if ((err as Error).message === 'timeout') {
              try { await iterator.return?.() } catch {}
              throw new Error('Provider request timed out')
            }
            throw err
          }
        }

        const inputTokens = Math.ceil(prompt.length / 4)
        return { text: text.trim(), inputTokens, outputTokens }
      } catch (err) {
        if (isDedupError(err) && attempt < maxRetries) {
          const wait = baseDelay * Math.pow(2, attempt - 1) + Math.round(Math.random() * 100)
          try { this.logger?.warn?.('YangObserver: provider request deduped, backing off and retrying', { attempt, wait, error: String(err) }) } catch {}
          await new Promise(res => setTimeout(res, wait))
          continue
        }
        // Exhausted retries or other error — rethrow
        throw err
      }
    }
  }

  private async parseResponse(response: { text: string }, provider?: IProvider, modelOverride?: string, signal?: AbortSignal): Promise<YangBranch[]> {
    try {
      const text = (response.text || '').trim();
      // Attempt to parse JSON object or JSON-wrapped array
      const jsonMatch = text.match(/\{[\s\S]*\}|\[[\s\S]*\]/);
      if (jsonMatch) {
        const parsed = JSON.parse(jsonMatch[0]);
        // If a top-level object with 'branches' array
        if (parsed && parsed.branches && Array.isArray(parsed.branches)) {
          return parsed.branches.map((b: any, idx: number) => ({
            id: b.id || `yang-${idx + 1}`,
            type: b.type || 'alternative_interpretation',
            content: b.content || '',
            confidence: Math.max(0, Math.min(1, b.confidence || 0.5)),
            noveltyScore: Math.max(0, Math.min(1, b.noveltyScore || 0.5)),
          }));
        }

        // If a single-branch object representation
        if (parsed && typeof parsed === 'object' && parsed.id && parsed.content) {
          return [{
            id: parsed.id || 'yang-1',
            type: parsed.type || 'alternative_interpretation',
            content: parsed.content || '',
            confidence: Math.max(0, Math.min(1, parsed.confidence || 0.5)),
            noveltyScore: Math.max(0, Math.min(1, parsed.noveltyScore || 0.5)),
          }];
        }
      }

      // No JSON found — delegate repair to Thinker (fast, local) if available
      if (this.eventBus) {
        try {
          const reqId = `yang-repair-${Date.now()}-${Math.random().toString(36).slice(2,6)}`;
          const schema = `{\n  "id": "string",\n  "type": "alternative_interpretation|edge_case|cross_domain|what_if|assumption_challenge",\n  "content": "string",\n  "confidence": 0.0-1.0,\n  "noveltyScore": 0.0-1.0\n}`;
          const repairPrompt = `The previous response failed to produce valid JSON. Convert the following TEXT into valid JSON matching EXACTLY this schema and WRAP the JSON between the literal markers ---BEGIN_JSON--- and ---END_JSON---. Return NOTHING else.\n\nSCHEMA:\n${schema}\n\nTEXT:\n"""${text}"""\n\nReturn exactly: ---BEGIN_JSON---<JSON>---END_JSON---`;

          // emit repair request to thinker (non-blocking)
          try { (this.eventBus as any).emit?.({ type: 'thinker:repair-request', id: reqId, prompt: repairPrompt }) } catch (e) {}

          // wait for response up to 5s
          const resp = await new Promise<string | null>((resolve, reject) => {
            let done = false
            const handler = (ev: any) => {
              try {
                if (!ev || ev?.id !== reqId) return
                done = true
                try { (this.eventBus as any).off?.('thinker:repair-response', handler) } catch {}
                if (ev.error) return resolve(null)
                resolve(ev.text || null)
              } catch (err) { /* ignore */ }
            }
            try { (this.eventBus as any).on?.('thinker:repair-response', handler) } catch (err) { return resolve(null) }
            setTimeout(() => {
              if (!done) {
                try { (this.eventBus as any).off?.('thinker:repair-response', handler) } catch {}
                resolve(null)
              }
            }, 5000)
          })

          if (resp) {
            const m = resp.match(/---BEGIN_JSON---([\s\S]*?)---END_JSON---/);
            const candidate = m ? m[1] : resp;
            try {
              const parsed2 = JSON.parse(candidate);
              if (parsed2 && parsed2.branches && Array.isArray(parsed2.branches)) {
                return parsed2.branches.map((b: any, idx: number) => ({
                  id: b.id || `yang-${idx + 1}`,
                  type: b.type || 'alternative_interpretation',
                  content: b.content || '',
                  confidence: Math.max(0, Math.min(1, b.confidence || 0.5)),
                  noveltyScore: Math.max(0, Math.min(1, b.noveltyScore || 0.5)),
                }));
              }
              if (parsed2 && parsed2.id && parsed2.content) {
                return [{ id: parsed2.id, type: parsed2.type || 'alternative_interpretation', content: parsed2.content, confidence: Math.max(0, Math.min(1, parsed2.confidence || 0.5)), noveltyScore: Math.max(0, Math.min(1, parsed2.noveltyScore || 0.5)) }];
              }
            } catch (err) {
              // fall through
            }
          }
        } catch (err) {
          try { this.logger?.warn?.('YangObserver: thinker repair failed', { error: String(err) }) } catch {}
        }
      }

      // If provider available, ask it once (single attempt) to re-emit JSON wrapped in markers
      if (provider) {
        try {
          const modelSpec = modelOverride ?? this.config.model;
          const slash = modelSpec.indexOf('/');
          const modelName = slash >= 0 ? modelSpec.slice(slash + 1) : modelSpec;

          const schema = `{\n  "id": "string",\n  "type": "alternative_interpretation|edge_case|cross_domain|what_if|assumption_challenge",\n  "content": "string",\n  "confidence": 0.0-1.0,\n  "noveltyScore": 0.0-1.0\n}`;

          const prompt = `The previous response failed to produce valid JSON. Convert the following TEXT into valid JSON matching EXACTLY this schema and WRAP the JSON between the literal markers ---BEGIN_JSON--- and ---END_JSON---. Return NOTHING else.\n\nSCHEMA:\n${schema}\n\nTEXT:\n"""${text}"""\n\nReturn exactly: ---BEGIN_JSON---<JSON>---END_JSON---`;

          this.logger.info('YangObserver: no JSON found — attempting JSON repair call to provider (attempt 1)');
          const messages = [{ role: 'user' as const, content: prompt }];
          const callOpts: any = { model: modelName, stream: true as const, maxTokens: 1500, temperature: 0.0, allowConcurrent: true };
          const stream = (provider as any).complete(messages, callOpts as any, undefined, signal) as AsyncIterable<any>;
          let collected = '';
          const iterator = (stream as any)[Symbol.asyncIterator]() as AsyncIterator<any>;
          const start = Date.now();
          const repairTimeout = 10000; // 10s
          while (true) {
            const timeLeft = Math.max(0, repairTimeout - (Date.now() - start));
            if (timeLeft <= 0) { try { await iterator.return?.() } catch {} break }
            const nextPromise = iterator.next();
            const timeoutPromise = new Promise<never>((_, rej) => setTimeout(() => rej(new Error('timeout')), timeLeft));
            try {
              const res = await Promise.race([nextPromise, timeoutPromise]) as IteratorResult<any>;
              if (res.done) break;
              const ch = res.value;
              if ((ch.type === 'token' || ch.type === 'thinking') && ch.text) collected += ch.text;
              else if (ch.type === 'error') throw new Error(ch.error || 'Provider error');
              else if (ch.type === 'done') break;
            } catch (err) {
              if ((err as Error).message === 'timeout') { try { await iterator.return?.() } catch {} break }
              break;
            }
          }

          const repairText = (collected || '').trim();
          const m2 = repairText.match(/---BEGIN_JSON---([\s\S]*?)---END_JSON---/);
          const candidate = m2 ? m2[1] : (repairText.match(/\{[\s\S]*\}/) || [])[0];
          if (candidate) {
            try {
              const parsed2 = JSON.parse(candidate);
              if (parsed2.branches && Array.isArray(parsed2.branches)) {
                this.logger.info('YangObserver: JSON repair succeeded (provider)');
                return parsed2.branches.map((b: any, idx: number) => ({
                  id: b.id || `yang-${idx + 1}`,
                  type: b.type || 'alternative_interpretation',
                  content: b.content || '',
                  confidence: Math.max(0, Math.min(1, b.confidence || 0.5)),
                  noveltyScore: Math.max(0, Math.min(1, b.noveltyScore || 0.5)),
                }));
              }
              if (parsed2 && parsed2.id && parsed2.content) {
                return [{ id: parsed2.id, type: parsed2.type || 'alternative_interpretation', content: parsed2.content, confidence: Math.max(0, Math.min(1, parsed2.confidence || 0.5)), noveltyScore: Math.max(0, Math.min(1, parsed2.noveltyScore || 0.5)) }];
              }
            } catch (err) {
              // parse failed — fall through
            }
          }
        } catch (err) {
          this.logger.warn('YangObserver: provider repair attempt failed', { error: String(err) });
        }
      }

      // Structured fallback parsing (heuristic)
      this.logger.info('YangObserver: falling back to structured parsing of plain text');
      const parseIntoItems = (raw: string): string[] => {
        const lines = raw.split(/\r?\n/);
        const markerRegex = /^\s*(?:\d+[\.\)]|[-*•])\s+(.*)$/;
        let markerCount = 0;
        for (const l of lines) if (markerRegex.test(l)) markerCount++;
        const items: string[] = [];
        if (markerCount >= 2) {
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
      };

      const items = parseIntoItems(text);
      if (items.length > 1) {
        const types: Array<YangBranch['type']> = ['alternative_interpretation','edge_case','cross_domain','what_if','assumption_challenge'];
        return items.map((it, idx) => ({
          id: `yang-${idx + 1}`,
          type: types[idx % types.length],
          content: it,
          confidence: 0.6,
          noveltyScore: Math.max(0.2, Math.min(0.95, it.length / 400 + 0.3)),
        }));
      }

      // Single item fallback
      if (text) {
        this.logger.info('YangObserver: falling back to single raw-text branch (no structured list detected)');
        return [{
          id: 'yang-1',
          type: 'alternative_interpretation',
          content: text,
          confidence: 0.6,
          noveltyScore: 0.5,
        }];
      }

      this.logger.warn('YangObserver: no JSON found in response and no text to parse');
      return [];
    } catch (error) {
      this.logger.warn('YangObserver: failed to parse response', { error: String(error) });
      return [];
    }
  }
}

export const createYangObserver = (logger: ILogger, config?: Partial<YangConfig>): YangObserver =>
  new YangObserver(logger, config);
