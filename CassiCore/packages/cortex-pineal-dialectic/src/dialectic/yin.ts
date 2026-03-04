/**
 * YinObserver — The Principle of Refinement
 *
 * Critiques and compresses Yang's expansions.
 * Finds flaws, extracts essence, and determines relevance.
 */

import type { ILogger } from '../../../types/interfaces.js';
import type { IYinObserver, YinOutput, YinCritique, YangOutput, YangBranch } from '../../../types/dialectic.js';
import type { IProvider } from '../../../types/runtime.js';
import type { IEventBus } from '../../../types/interfaces.js';
import { fillTemplate } from './prompt-optimizer.js';
import type { PromptOptimizer } from './prompt-optimizer.js';
import { getModelSpec } from '../../config/system-settings.js'

export interface YinConfig {
  enabled: boolean;
  model: string;           // GPT-5 Mini or equivalent
  temperature: number;     // default 0.3 for precision
  minRelevance: number;    // default 0.6
}

export class YinObserver implements IYinObserver {
  readonly name = 'yin' as const;

  private logger: ILogger;
  private config: YinConfig;
  private provider?: IProvider;
  private eventBus?: IEventBus;
  private promptOptimizer?: PromptOptimizer;

  constructor(logger: ILogger, config?: Partial<YinConfig>) {
    this.logger = logger.child?.('yin') ?? logger;
    this.config = {
      enabled: config?.enabled ?? true,
      model: config?.model ?? getModelSpec('reasoning'),
      temperature: config?.temperature ?? 0.3,
      minRelevance: config?.minRelevance ?? 0.6,
    };

    if (this.config.enabled) {
      this.logger.info('YinObserver: enabled', { model: this.config.model });
    } else {
      this.logger.info('YinObserver: disabled');
    }
  }

  setProvider(provider: IProvider): void {
    this.provider = provider;
    this.logger.info('YinObserver: provider wired');
  }

  setEventBus(bus: IEventBus): void {
    this.eventBus = bus;
    this.logger.info('YinObserver: event bus wired');
  }

  setPromptOptimizer(optimizer: PromptOptimizer): void {
    this.promptOptimizer = optimizer;
    this.logger.info('YinObserver: prompt optimizer wired');
  }

  async observe(sessionId: string, userMessage: string, yangOutput: YangOutput, context?: import('../../../types/dialectic.js').YangContext, opts?: { model?: string; provider?: IProvider; allowConcurrent?: boolean; dedupe?: boolean; signal?: AbortSignal }): Promise<YinOutput> {
    const startTime = Date.now();

    if (!this.config.enabled) {
      return {
        critiques: yangOutput.branches.map(b => this.createNullCritique(b)),
        meta: {
          compressionRatio: 1.0,
          processingTimeMs: 0,
          inputTokens: 0,
          outputTokens: 0,
        },
      };
    }

    const providerToUse = opts?.provider ?? this.provider;
    if (!providerToUse) {
      this.logger.warn('YinObserver: no provider wired, passing through');
      return {
        critiques: yangOutput.branches.map(b => this.createNullCritique(b)),
        meta: {
          compressionRatio: 1.0,
          processingTimeMs: 0,
          inputTokens: 0,
          outputTokens: 0,
        },
      };
    }

    if (yangOutput.branches.length === 0) {
      return {
        critiques: [],
        meta: {
          compressionRatio: 1.0,
          processingTimeMs: 0,
          inputTokens: 0,
          outputTokens: 0,
        },
      };
    }

    try {
      const prompt = this.buildPrompt(sessionId, userMessage, yangOutput.branches, context);
      const response = await this.callProvider(prompt, { provider: providerToUse, model: opts?.model, allowConcurrent: opts?.allowConcurrent, dedupe: opts?.dedupe, timeoutMs: 30000 });
      const critiques = await this.parseResponse(response, yangOutput.branches, providerToUse, opts?.model, opts?.signal);

      // Calculate compression ratio
      const totalOriginalLength = yangOutput.branches.reduce((sum, b) => sum + b.content.length, 0);
      const totalEssenceLength = critiques
        .filter(c => c.valid && c.essence)
        .reduce((sum, c) => sum + (c.essence?.length || 0), 0);
      const compressionRatio = totalOriginalLength > 0
        ? totalEssenceLength / totalOriginalLength
        : 1.0;

      const processingTimeMs = Date.now() - startTime;

      this.logger.info('YinObserver: refinement complete', {
        sessionId,
        branchesCritiqued: critiques.length,
        validBranches: critiques.filter(c => c.valid).length,
        compressionRatio: compressionRatio.toFixed(2),
        processingTimeMs,
      });

      return {
        critiques,
        meta: {
          compressionRatio,
          processingTimeMs,
          inputTokens: response.inputTokens,
          outputTokens: response.outputTokens,
        },
      };
    } catch (error) {
      this.logger.error('YinObserver: refinement failed', {
        sessionId,
        error: String(error)
      });

      // Return null critiques on error
      return {
        critiques: yangOutput.branches.map(b => this.createNullCritique(b)),
        meta: {
          compressionRatio: 1.0,
          processingTimeMs: Date.now() - startTime,
          inputTokens: 0,
          outputTokens: 0,
        },
      };
    }
  }

  /**
   * observeWithBaseline — For parallel dialectic mode
   *
   * Yin generates its own baseline analysis + self-critique independently,
   * without waiting for Yang's output. This enables parallel execution.
   */
  async observeWithBaseline(
    sessionId: string,
    userMessage: string,
    context: import('../../../types/dialectic.js').YangContext,
    opts?: { model?: string; provider?: IProvider; allowConcurrent?: boolean; dedupe?: boolean; signal?: AbortSignal }
  ): Promise<import('../../../types/dialectic.js').YinBaselineOutput> {
    const startTime = Date.now();

    if (!this.config.enabled) {
      return {
        baselineBranches: [],
        selfCritiques: [],
        meta: {
          compressionRatio: 1.0,
          processingTimeMs: 0,
          inputTokens: 0,
          outputTokens: 0,
          relativeTiming: 'concurrent',
        },
      };
    }

    const providerToUse = opts?.provider ?? this.provider;
    if (!providerToUse) {
      this.logger.warn('YinObserver: no provider wired for baseline mode');
      return {
        baselineBranches: [],
        selfCritiques: [],
        meta: {
          compressionRatio: 1.0,
          processingTimeMs: 0,
          inputTokens: 0,
          outputTokens: 0,
          relativeTiming: 'concurrent',
        },
      };
    }

    try {
      const prompt = this.buildBaselinePrompt(sessionId, userMessage, context);
      const response = await this.callProvider(prompt, {
        provider: providerToUse,
        model: opts?.model,
        allowConcurrent: opts?.allowConcurrent,
        dedupe: opts?.dedupe,
        timeoutMs: 30000,
        signal: opts?.signal,
      });

      const baselineBranches = await this.parseBaselineResponse(response, providerToUse, opts?.model, opts?.signal);

      // Generate self-critiques for the baseline branches
      const selfCritiques = baselineBranches.map((b, idx) => ({
        yangBranchId: b.id,
        valid: b.confidence >= this.config.minRelevance,
        essence: b.content.slice(0, 200),
        critique: b.confidence >= this.config.minRelevance ? 'Valid baseline insight' : 'Low relevance baseline',
        relevance: b.relevanceScore,
        action: b.confidence >= this.config.minRelevance ? ('surface' as const) : ('discard' as const),
      }));

      const processingTimeMs = Date.now() - startTime;

      this.logger.info('YinObserver: baseline analysis complete', {
        sessionId,
        baselineBranches: baselineBranches.length,
        processingTimeMs,
      });

      return {
        baselineBranches,
        selfCritiques,
        meta: {
          compressionRatio: 0.5, // Baseline is already compressed
          processingTimeMs,
          inputTokens: response.inputTokens,
          outputTokens: response.outputTokens,
          relativeTiming: 'concurrent',
        },
      };
    } catch (error) {
      this.logger.error('YinObserver: baseline analysis failed', {
        sessionId,
        error: String(error),
      });

      return {
        baselineBranches: [],
        selfCritiques: [],
        meta: {
          compressionRatio: 1.0,
          processingTimeMs: Date.now() - startTime,
          inputTokens: 0,
          outputTokens: 0,
          relativeTiming: 'concurrent',
        },
      };
    }
  }

  private createNullCritique(branch: YangBranch): YinCritique {
    return {
      yangBranchId: branch.id,
      valid: true,
      essence: branch.content,
      critique: 'Passed through (Yin disabled or error)',
      relevance: branch.confidence,
      action: 'surface',
    };
  }

  private buildPrompt(sessionId: string, userMessage: string, branches: YangBranch[], context?: import('../../../types/dialectic.js').YangContext): string {
    const guideBlock = context?.taskGuide
      ? `TASK GUIDE:\n${context.taskGuide}\n\n`
      : '';

    const branchesBlock = branches.map((b, idx) => `\nBRANCH ${idx + 1} [${b.id}]:\n- Type: ${b.type}\n- Content: ${b.content}\n- Yang Confidence: ${b.confidence}\n- Yang Novelty: ${b.noveltyScore}\n`).join('\n');

    // Use optimizer variant if available and enabled
    if (this.promptOptimizer?.enabled) {
      const variant = this.promptOptimizer.selectYinCritique();
      return fillTemplate(variant.template, {
        guideBlock,
        userMessage,
        branchesBlock,
        branchCount: String(branches.length),
        sessionId,
      });
    }

    return `${guideBlock}You are YIN — evidence-based validation.\n\nUSER MESSAGE:\n"""${userMessage}"""\n\nYANG'S EXPANSIONS:\n${branchesBlock}\n\nFor EACH branch, classify using a 3-tier verdict:\n- surface: Has clear merit AND changes how the AI responds — include as-is\n- compress: Has some merit but needs trimming — include a compressed 1-sentence essence\n- discard: Flawed reasoning, irrelevant, or does not change the response — exclude\n\nProvide exactly ${branches.length} critiques in order.\n\nOUTPUT (JSON):\n{\n  "critiques": [\n    {\n      "yangBranchId": "yang-1",\n      "essence": "Core insight in 1 sentence (required when action is surface or compress)",\n      "critique": "Reasoning for verdict",\n      "relevance": 0.0-1.0,\n      "action": "surface|compress|discard"\n    }\n  ]\n}\n\nReturn ONLY valid JSON. No markdown fences, no explanation, no extra text.`;
  }


  /**
   * buildBaselinePrompt — Prompt for independent baseline analysis (parallel mode)
   */
  private buildBaselinePrompt(
    sessionId: string,
    userMessage: string,
    context: import('../../../types/dialectic.js').YangContext
  ): string {
    const guideBlock = context?.taskGuide
      ? `TASK GUIDE:\n${context.taskGuide}\n\n`
      : '';

    const memoryBlock = context?.recentMemories?.length
      ? `Recent context:\n${context.recentMemories.map(m => `- ${m.slice(0, 200)}`).join('\n')}\n\n`
      : '';

    // Use optimizer variant if available and enabled
    if (this.promptOptimizer?.enabled) {
      const variant = this.promptOptimizer.selectYinBaseline();
      return fillTemplate(variant.template, {
        guideBlock,
        memoryBlock,
        userMessage,
        sessionId,
      });
    }

    return `${guideBlock}${memoryBlock}You are YIN — constraint extractor.\n\nUSER MESSAGE:\n"""${userMessage}"""\n\nGenerate 3-5 analyses extracting what the user hasn't explicitly stated:\n- grounding: What concrete facts/context are assumed?\n- constraint: What boundaries or limitations exist but aren't mentioned?\n- reality_check: What assumption should be verified before proceeding?\n- prioritization: What matters most based on emphasis and ordering?\n- risk_assessment: What could go wrong that the user hasn't considered?\n\nQUALITY GATE: "What unstated constraint, if violated, would invalidate the user's approach?"\n\nEach analysis: 2-4 sentences. Assign confidence and relevanceScore as 0.0-1.0.\n\nOUTPUT (JSON):\n{\n  "baselineBranches": [\n    {\n      "id": "yin-1",\n      "type": "grounding|constraint|reality_check|prioritization|risk_assessment",\n      "content": "2-4 sentences",\n      "confidence": 0.0-1.0,\n      "relevanceScore": 0.0-1.0\n    }\n  ]\n}\n\nReturn ONLY valid JSON. No markdown fences, no explanation, no extra text.`;
  }

  /**
   * parseBaselineResponse — Parse baseline branches from response
   */
  private async parseBaselineResponse(
    response: { text: string },
    provider?: IProvider,
    modelOverride?: string,
    signal?: AbortSignal
  ): Promise<import('../../../types/dialectic.js').YinBaselineBranch[]> {
    try {
      const text = (response.text || '').trim();
      const jsonMatch = text.match(/\{[\s\S]*\}/);

      if (jsonMatch) {
        const parsed = JSON.parse(jsonMatch[0]);
        if (parsed.baselineBranches && Array.isArray(parsed.baselineBranches)) {
          return parsed.baselineBranches.map((b: any, idx: number) => ({
            id: b.id || `yin-${idx + 1}`,
            type: b.type || 'grounding',
            content: b.content || '',
            confidence: Math.max(0, Math.min(1, b.confidence || 0.5)),
            relevanceScore: Math.max(0, Math.min(1, b.relevanceScore || 0.5)),
          }));
        }
      }

      // Fallback: parse as list items
      const items = text
        .split(/\n\s*\n/)
        .map(p => p.trim())
        .filter(p => p.length > 50);

      if (items.length >= 2) {
        const types: Array<import('../../../types/dialectic.js').YinBaselineBranch['type']> = [
          'grounding', 'constraint', 'reality_check', 'prioritization', 'risk_assessment'
        ];
        return items.slice(0, 5).map((item, idx) => ({
          id: `yin-${idx + 1}`,
          type: types[idx % types.length],
          content: item.slice(0, 500),
          confidence: 0.6 + (idx * 0.05),
          relevanceScore: 0.7,
        }));
      }

      return [];
    } catch (error) {
      this.logger.warn('YinObserver: failed to parse baseline response', { error: String(error) });
      return [];
    }
  }
  private async callProvider(prompt: string, opts?: { provider?: IProvider; model?: string; maxTokens?: number; allowConcurrent?: boolean; dedupe?: boolean; timeoutMs?: number; signal?: AbortSignal }): Promise<{ text: string; inputTokens: number; outputTokens: number }> {
    const messages = [{ role: 'user' as const, content: prompt }];

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
      return /Request already in progress|already has in-flight|deduplicat|dedupe/i.test(s)
    }

    const maxRetries = 3
    let attempt = 0
    const baseDelay = 150
    const timeoutMs = opts?.timeoutMs ?? 30_000

    while (true) {
      attempt++
      try {
        try { this.logger?.info?.('YinObserver.callProvider: invoking provider', { model: modelName, allowConcurrent: callOpts.allowConcurrent, dedupe: callOpts.dedupe }) } catch {}
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
            } else if (chunk.type === 'done') break;
          } catch (err) {
            if ((err as Error).message === 'timeout') {
              try { await iterator.return?.() } catch {}
              throw new Error('Provider request timed out')
            }
            throw err
          }
        }

        const inputTokens = Math.ceil(prompt.length / 4);

        return { text: text.trim(), inputTokens, outputTokens }
      } catch (err) {
        if (isDedupError(err) && attempt < maxRetries) {
          const wait = baseDelay * Math.pow(2, attempt - 1) + Math.round(Math.random() * 100)
          try { this.logger?.warn?.('YinObserver: provider request deduped, backing off and retrying', { attempt, wait, error: String(err) }) } catch {}
          await new Promise(res => setTimeout(res, wait))
          continue
        }
        throw err
      }
    }
  }

  private async parseResponse(response: { text: string }, branches: YangBranch[], provider?: IProvider, modelOverride?: string, signal?: AbortSignal): Promise<YinCritique[]> {
    try {
      const text = (response.text || '').trim();
      const jsonMatch = text.match(/\{[\s\S]*\}/);
      if (jsonMatch) {
        const parsed = JSON.parse(jsonMatch[0]);
        if (!parsed.critiques || !Array.isArray(parsed.critiques)) {
          this.logger.warn('YinObserver: invalid critiques array in response');
          return branches.map(b => this.createNullCritique(b));
        }

        return parsed.critiques.map((c: any, idx: number) => {
          const branch = branches[idx] || branches.find(b => b.id === c.yangBranchId);
          const validActions: import('../../../types/dialectic.js').YinAction[] = ['surface', 'compress', 'discard'];
          // Support old 'refine'→'compress' and 'ignore'→'discard' for any cached/legacy responses
          const rawAction = c.action === 'refine' ? 'compress' : c.action === 'ignore' ? 'discard' : c.action;
          const action = (validActions.includes(rawAction) ? rawAction : 'surface') as import('../../../types/dialectic.js').YinAction;
          const valid = action !== 'discard';
          return {
            yangBranchId: c.yangBranchId || branch?.id || `yang-${idx + 1}`,
            valid,
            essence: c.essence,
            critique: c.critique || '',
            relevance: Math.max(0, Math.min(1, c.relevance || 0.5)),
            action,
          };
        });
      }

      // Delegate repair to Thinker if available
      if (this.eventBus) {
        try {
          const reqId = `yin-repair-${Date.now()}-${Math.random().toString(36).slice(2,6)}`;
          const schema = `{"critiques":[{"yangBranchId":"string","essence":"string","critique":"string","relevance":0.0-1.0,"action":"surface|compress|discard"}]}`;
          const repairPrompt = `The previous response failed to produce valid JSON. Convert the following TEXT into valid JSON matching EXACTLY this schema and WRAP the JSON between the literal markers ---BEGIN_JSON--- and ---END_JSON---. Return NOTHING else.\n\nSCHEMA:\n${schema}\n\nTEXT:\n"""${text}"""\n\nReturn exactly: ---BEGIN_JSON---<JSON>---END_JSON---`;

          try { (this.eventBus as any).emit?.({ type: 'thinker:repair-request', id: reqId, prompt: repairPrompt }) } catch (e) {}

          const resp = await new Promise<string | null>((resolve) => {
            let done = false
            const handler = (ev: any) => {
              try {
                if (!ev || ev?.id !== reqId) return
                done = true
                try { (this.eventBus as any).off?.('thinker:repair-response', handler) } catch {}
                if (ev.error) return resolve(null)
                resolve(ev.text || null)
              } catch (err) { resolve(null) }
            }
            try { (this.eventBus as any).on?.('thinker:repair-response', handler) } catch (err) { return resolve(null) }
            setTimeout(() => { if (!done) { try { (this.eventBus as any).off?.('thinker:repair-response', handler) } catch {} ; resolve(null) } }, 5000)
          })

          if (resp) {
            const m = resp.match(/---BEGIN_JSON---([\s\S]*?)---END_JSON---/);
            const candidate = m ? m[1] : (resp.match(/\{[\s\S]*\}/) || [])[0];
            if (candidate) {
              try {
                const parsed2 = JSON.parse(candidate);
                if (parsed2.critiques && Array.isArray(parsed2.critiques)) {
                  this.logger.info('YinObserver: JSON repair succeeded (thinker)');
                  return parsed2.critiques.map((c: any, idx: number) => {
                    const branch = branches[idx] || branches.find(b => b.id === c.yangBranchId);
                    return {
                      yangBranchId: c.yangBranchId || branch?.id || `yang-${idx + 1}`,
                      valid: c.valid ?? true,
                      essence: c.essence,
                      critique: c.critique || '',
                      relevance: Math.max(0, Math.min(1, c.relevance || 0.5)),
                      action: c.action || 'surface',
                    };
                  });
                }
              } catch (err) { /* fall through */ }
            }
          }
        } catch (err) {
          this.logger.warn('YinObserver: thinker repair failed', { error: String(err) });
        }
      }

      // Single provider repair attempt (marker-enforced) with short timeout
      if (provider) {
        try {
          const modelSpec = modelOverride ?? this.config.model;
          const slashIdx = modelSpec.indexOf('/');
          const modelName = slashIdx >= 0 ? modelSpec.slice(slashIdx + 1) : modelSpec;
          const schema = `{"critiques":[{"yangBranchId":"string","essence":"string","critique":"string","relevance":0.0-1.0,"action":"surface|compress|discard"}]}`;
          const prompt = `The previous response failed to produce valid JSON. Convert the following TEXT into valid JSON matching EXACTLY this schema and WRAP the JSON between the literal markers ---BEGIN_JSON--- and ---END_JSON---. Return NOTHING else.\n\nSCHEMA:\n${schema}\n\nTEXT:\n"""${text}"""\n\nReturn exactly: ---BEGIN_JSON---<JSON>---END_JSON---`;

          this.logger.info('YinObserver: no JSON found — attempting JSON repair call to provider (attempt 1)');
          const messages = [{ role: 'user' as const, content: prompt }];
          const callOpts: any = { model: modelName, stream: true as const, maxTokens: 1500, temperature: 0.0, allowConcurrent: true };
          const stream = (provider as any).complete(messages, callOpts as any, undefined, signal) as AsyncIterable<any>;
          let collected = '';
          const iterator = (stream as any)[Symbol.asyncIterator]() as AsyncIterator<any>;
          const start = Date.now();
          const repairTimeout = 10000;
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
          const markersMatch = repairText.match(/---BEGIN_JSON---([\s\S]*?)---END_JSON---/);
          const candidate = markersMatch ? markersMatch[1] : (repairText.match(/\{[\s\S]*\}/) || [])[0];
          if (candidate) {
            try {
              const parsed2 = JSON.parse(candidate);
              if (parsed2.critiques && Array.isArray(parsed2.critiques)) {
                this.logger.info(`YinObserver: JSON repair succeeded (provider)`);
                return parsed2.critiques.map((c: any, idx: number) => {
                  const branch = branches[idx] || branches.find(b => b.id === c.yangBranchId);
                  return {
                    yangBranchId: c.yangBranchId || branch?.id || `yang-${idx + 1}`,
                    valid: c.valid ?? true,
                    essence: c.essence,
                    critique: c.critique || '',
                    relevance: Math.max(0, Math.min(1, c.relevance || 0.5)),
                    action: c.action || 'surface',
                  };
                });
              }
            } catch (err) { this.logger.warn('YinObserver: provider repair parse failed', { error: String(err) }) }
          }
        } catch (err) {
          this.logger.warn('YinObserver: provider repair attempt failed', { error: String(err) });
        }
      }

      // Structured fallback parsing for critiques
      if (text) {
        this.logger.info('YinObserver: no JSON found — attempting structured fallback parsing for critiques');

        const parseIntoItems = (raw: string): string[] => {
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
        };

        const items = parseIntoItems(text);

        if (items.length >= 1) {
          // Map parsed items to branches. If there are fewer items than branches,
          // apply items to the first N branches and pass-through the rest.
          return branches.map((b, idx) => {
            const item = items[idx] ?? items[0];
            const essence = String(item).split(/\n+/)[0].trim().slice(0, 200);
            const action: import('../../../types/dialectic.js').YinAction = /compress|trim|short|condense/i.test(item) ? 'compress' : 'surface';
            const valid = !/invalid|no|not valid|flaw|error|discard/i.test(item);
            return {
              yangBranchId: b.id,
              valid,
              essence,
              critique: item,
              relevance: b.confidence,
              action,
            };
          });
        }

        // Fallback to previous behavior
        this.logger.info('YinObserver: falling back to raw-text critiques (no structured list detected)');
        return branches.map((b, idx) => ({
          yangBranchId: b.id,
          valid: true,
          essence: idx === 0 ? text : b.content,
          critique: idx === 0 ? 'Auto-generated critique (raw fallback)' : 'Passed through',
          relevance: b.confidence,
          action: 'surface',
        }));
      }

      this.logger.warn('YinObserver: no JSON found in response');
      return branches.map(b => this.createNullCritique(b));
    } catch (error) {
      this.logger.warn('YinObserver: failed to parse response', { error: String(error) });
      return branches.map(b => this.createNullCritique(b));
    }
  }
}

export const createYinObserver = (logger: ILogger, config?: Partial<YinConfig>): YinObserver =>
  new YinObserver(logger, config);
