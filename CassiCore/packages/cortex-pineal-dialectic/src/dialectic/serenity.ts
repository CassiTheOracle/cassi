/**
 * Serenity — The Mediator
 *
 * Analyzes the Yang/Yin dialectic and extracts signals of interest.
 * Determines what should be surfaced to the main agent.
 */

import type { ILogger } from '../../../types/interfaces.js';
import type {
  ISerenity,
  SerenityOutput,
  Synthesis,
  DialecticSignal,
  YangOutput,
  YinOutput
} from '../../../types/dialectic.js';
import type { IProvider } from '../../../types/runtime.js';
import type { IEventBus } from '../../../types/interfaces.js';
import { fillTemplate } from './prompt-optimizer.js';
import type { PromptOptimizer } from './prompt-optimizer.js';
import { getModelSpec } from '../../config/system-settings.js'

export interface SerenityConfig {
  enabled: boolean;
  model: string;              // GPT-5 Mini or equivalent
  temperature: number;        // default 0.4 for balanced analysis
  noveltyThreshold: number;   // default 0.5 (lower = more generous with insights)
  relevanceThreshold: number; // default 0.5 (lower = more generous with insights)
  minConfidence: number;      // default 0.6 (lower = more signals surfaced)
  insightPreference: 'generous' | 'balanced' | 'conservative'; // default 'generous'
}

export class Serenity implements ISerenity {
  readonly name = 'serenity' as const;

  private logger: ILogger;
  private config: SerenityConfig;
  private provider?: IProvider;
  private eventBus?: IEventBus;
  private promptOptimizer?: PromptOptimizer;

  constructor(logger: ILogger, config?: Partial<SerenityConfig>) {
    this.logger = logger.child?.('serenity') ?? logger;
    this.config = {
      enabled: config?.enabled ?? true,
      model: config?.model ?? getModelSpec('reasoning'),
      temperature: config?.temperature ?? 0.4,
      noveltyThreshold: config?.noveltyThreshold ?? 0.5,  // More generous - surface more insights
      relevanceThreshold: config?.relevanceThreshold ?? 0.5,  // More generous
      minConfidence: config?.minConfidence ?? 0.6,  // Lower threshold for signals
      insightPreference: config?.insightPreference ?? 'generous',
    };

    if (this.config.enabled) {
      this.logger.info('Serenity: enabled', { model: this.config.model });
    } else {
      this.logger.info('Serenity: disabled');
    }
  }

  setProvider(provider: IProvider): void {
    this.provider = provider;
    this.logger.info('Serenity: provider wired');
  }

  setEventBus(bus: IEventBus): void {
    this.eventBus = bus;
    this.logger.info('Serenity: event bus wired');
  }

  setPromptOptimizer(optimizer: PromptOptimizer): void {
    this.promptOptimizer = optimizer;
    this.logger.info('Serenity: prompt optimizer wired');
  }

  async synchronize(
    sessionId: string,
    userMessage: string,
    yangOutput: YangOutput,
    yinOutput: YinOutput,
    relevantMemories: string[],
    opts?: { model?: string; provider?: IProvider; allowConcurrent?: boolean; dedupe?: boolean; signal?: AbortSignal }
  ): Promise<SerenityOutput> {
    const startTime = Date.now();

    if (!this.config.enabled) {
      return {
        synthesis: {
          hasSignal: false,
          branchesConsidered: yangOutput.branches.length,
          branchesSurfaced: 0,
        },
        meta: {
          dialecticQuality: 0.5,
          processingTimeMs: 0,
          inputTokens: 0,
          outputTokens: 0,
        },
      };
    }

    const providerToUse = opts?.provider ?? this.provider;
    if (!providerToUse) {
      this.logger.warn('Serenity: no provider wired');
      return {
        synthesis: {
          hasSignal: false,
          branchesConsidered: yangOutput.branches.length,
          branchesSurfaced: 0,
        },
        meta: {
          dialecticQuality: 0.5,
          processingTimeMs: 0,
          inputTokens: 0,
          outputTokens: 0,
        },
      };
    }

    // If no valid branches after Yin, skip synchronization
    const validBranches = this.getValidBranches(yangOutput, yinOutput);
    if (validBranches.length === 0) {
      return {
        synthesis: {
          hasSignal: false,
          branchesConsidered: yangOutput.branches.length,
          branchesSurfaced: 0,
        },
        meta: {
          dialecticQuality: this.calculateDialecticQuality(yangOutput, yinOutput),
          processingTimeMs: Date.now() - startTime,
          inputTokens: 0,
          outputTokens: 0,
        },
      };
    }

    try {
      const prompt = this.buildPrompt(sessionId, userMessage, yangOutput, yinOutput, validBranches, relevantMemories);
      const response = await this.callProvider(prompt, { provider: providerToUse, model: opts?.model, allowConcurrent: opts?.allowConcurrent, dedupe: opts?.dedupe, timeoutMs: 30000, signal: opts?.signal });

      const synthesis = await this.parseResponse(response, validBranches, providerToUse, opts?.model, opts?.signal);
      const processingTimeMs = Date.now() - startTime;

      this.logger.info('Serenity: mediation complete', {
        sessionId,
        hasSignal: synthesis.hasSignal,
        branchesConsidered: synthesis.branchesConsidered,
        branchesSurfaced: synthesis.branchesSurfaced,
        processingTimeMs,
      });

      return {
        synthesis,
        meta: {
          dialecticQuality: this.calculateDialecticQuality(yangOutput, yinOutput),
          processingTimeMs,
          inputTokens: response.inputTokens,
          outputTokens: response.outputTokens,
        },
      };
    } catch (error) {
      this.logger.error('Serenity: mediation failed', {
        sessionId,
        error: String(error)
      });

      return {
        synthesis: {
          hasSignal: false,
          branchesConsidered: yangOutput.branches.length,
          branchesSurfaced: 0,
        },
        meta: {
          dialecticQuality: 0.5,
          processingTimeMs: Date.now() - startTime,
          inputTokens: 0,
          outputTokens: 0,
        },
      };
    }
  }

  /**
   * synthesizeDual — Dual synthesis for parallel dialectic mode
   *
   * Synthesizes Yang's expansive branches with Yin's independent baseline analysis.
   * Used when Yang and Yin run in parallel (not sequentially).
   */
  async synthesizeDual(
    sessionId: string,
    input: import('../../../types/dialectic.js').DualSynthesisInput,
    relevantMemories: string[],
    opts?: { model?: string; provider?: IProvider; allowConcurrent?: boolean; dedupe?: boolean; signal?: AbortSignal }
  ): Promise<SerenityOutput> {
    const startTime = Date.now();

    if (!this.config.enabled) {
      return {
        synthesis: {
          hasSignal: false,
          branchesConsidered: input.yang.branches.length + input.yin.baselineBranches.length,
          branchesSurfaced: 0,
        },
        meta: {
          dialecticQuality: 0.5,
          processingTimeMs: 0,
          inputTokens: 0,
          outputTokens: 0,
        },
      };
    }

    const providerToUse = opts?.provider ?? this.provider;
    if (!providerToUse) {
      this.logger.warn('Serenity: no provider wired for dual synthesis');
      return {
        synthesis: {
          hasSignal: false,
          branchesConsidered: input.yang.branches.length + input.yin.baselineBranches.length,
          branchesSurfaced: 0,
        },
        meta: {
          dialecticQuality: 0.5,
          processingTimeMs: Date.now() - startTime,
          inputTokens: 0,
          outputTokens: 0,
        },
      };
    }

    try {
      const prompt = this.buildDualPrompt(sessionId, input, relevantMemories);
      const response = await this.callProvider(prompt, {
        provider: providerToUse,
        model: opts?.model,
        allowConcurrent: opts?.allowConcurrent,
        dedupe: opts?.dedupe,
        timeoutMs: 30000,
        signal: opts?.signal
      });

      const synthesis = await this.parseDualResponse(response, input, providerToUse, opts?.model, opts?.signal);
      const processingTimeMs = Date.now() - startTime;

      this.logger.info('Serenity: dual synthesis complete', {
        sessionId,
        hasSignal: synthesis.hasSignal,
        yangBranches: input.yang.branches.length,
        yinBaselineBranches: input.yin.baselineBranches.length,
        branchesSurfaced: synthesis.branchesSurfaced,
        processingTimeMs,
      });

      return {
        synthesis,
        meta: {
          dialecticQuality: this.calculateDualDialecticQuality(input, synthesis),
          processingTimeMs,
          inputTokens: response.inputTokens,
          outputTokens: response.outputTokens,
        },
      };
    } catch (error) {
      this.logger.error('Serenity: dual synthesis failed', {
        sessionId,
        error: String(error)
      });

      return {
        synthesis: {
          hasSignal: false,
          branchesConsidered: input.yang.branches.length + input.yin.baselineBranches.length,
          branchesSurfaced: 0,
        },
        meta: {
          dialecticQuality: 0.5,
          processingTimeMs: Date.now() - startTime,
          inputTokens: 0,
          outputTokens: 0,
        },
      };
    }
  }

  private getValidBranches(yangOutput: YangOutput, yinOutput: YinOutput): Array<{
    yang: typeof yangOutput.branches[0];
    yin: typeof yinOutput.critiques[0];
  }> {
    const valid: Array<{ yang: typeof yangOutput.branches[0]; yin: typeof yinOutput.critiques[0] }> = [];

    for (const yin of yinOutput.critiques) {
      if (yin.valid) {
        const yang = yangOutput.branches.find(b => b.id === yin.yangBranchId);
        if (yang) {
          valid.push({ yang, yin });
        }
      }
    }

    return valid;
  }

  private calculateDialecticQuality(yangOutput: YangOutput, yinOutput: YinOutput): number {
    if (yangOutput.branches.length === 0) return 0.5;

    const validCount = yinOutput.critiques.filter(c => c.valid).length;
    const validationRate = validCount / yangOutput.branches.length;

    const avgYangNovelty = yangOutput.branches.reduce((sum, b) => sum + b.noveltyScore, 0)
      / yangOutput.branches.length;

    const avgYinRelevance = yinOutput.critiques.reduce((sum, c) => sum + c.relevance, 0)
      / yinOutput.critiques.length || 0;

    // Quality = mix of validation rate, novelty, and refined relevance
    return (validationRate * 0.3) + (avgYangNovelty * 0.4) + (avgYinRelevance * 0.3);
  }

  private buildPrompt(
    sessionId: string,
    userMessage: string,
    yangOutput: YangOutput,
    yinOutput: YinOutput,
    validBranches: Array<{ yang: any; yin: any }>,
    relevantMemories: string[]
  ): string {
    const yangBlock = yangOutput.branches.map(b => `\n[${b.id}] ${b.type} (novelty: ${b.noveltyScore}, confidence: ${b.confidence})\n${b.content}\n`).join('\n');

    const yinBlock = yinOutput.critiques.map(c => {
      const branch = yangOutput.branches.find(b => b.id === c.yangBranchId);
      return `\n[${c.yangBranchId}] ${c.valid ? 'VALID' : 'INVALID'} — relevance: ${c.relevance}, action: ${c.action}\nEssence: ${c.essence || 'N/A'}\nCritique: ${c.critique}\n`;
    }).join('\n');

    const memoryBlock = relevantMemories.length > 0
      ? `Relevant memories:\n${relevantMemories.map(m => `- ${m}`).join('\n')}\n\n`
      : '';

    return `You are SERENITY — synthesizer of Yang (expansion) and Yin (refinement).\n\nUSER MESSAGE:\n"""${userMessage}"""\n\n${memoryBlock}YANG'S EXPANSIONS:\n${yangBlock}\n\nYIN'S CRITIQUES:\n${yinBlock}\n\nVALID BRANCHES TO CONSIDER (${validBranches.length}):\n${validBranches.map(({ yang, yin }) => `- ${yang.id}: ${yin.essence || yang.content}`).join('\n')}\n\nFind the single most valuable insight by comparing Yang and Yin:\n- CONVERGENCE: Both identified the same point → high confidence\n- TENSION: Creative vs. grounded conflict → reveals assumptions\n- GAP: One sees what the other misses → complementary insight\n\nThresholds: novelty > ${this.config.noveltyThreshold} AND relevance > ${this.config.relevanceThreshold} → surface.\n\nA signal that merely RESTATES the user's message is worthless. Only surface what changes the response.\n\nIf no genuine insight exists, set hasSignal: false.\n\nIMPORTANT: Frame the signal content as guidance for the AI assistant — what should it do differently or consider because of this insight? Do NOT describe the user. Write as: "Consider X because Y" or "Watch for Z" or "The approach may need to account for W".\n\nOUTPUT (JSON):\n{\n  "hasSignal": true,\n  "signal": {\n    "type": "edge_case|alternative|assumption|connection|contradiction|convergence|tension|gap",\n    "content": "What the AI should do differently or consider — 1-2 sentences of guidance, not a user description",\n    "confidence": 0.0-1.0,\n    "urgency": "immediate|background"\n  },\n  "branchesConsidered": 4,\n  "branchesSurfaced": 1\n}\n\nReturn ONLY valid JSON. No markdown fences, no explanation, no extra text.`;
  }


  /**
   * buildDualPrompt — Build prompt for dual synthesis (parallel mode)
   */
  private buildDualPrompt(
    sessionId: string,
    input: import('../../../types/dialectic.js').DualSynthesisInput,
    relevantMemories: string[]
  ): string {
    const yangBlock = input.yang.branches.map(b =>
      `\n[${b.id}] ${b.type} (novelty: ${b.noveltyScore}, confidence: ${b.confidence})\n${b.content}\n`
    ).join('\n');

    const yinBlock = input.yin.baselineBranches.map(b =>
      `\n[${b.id}] ${b.type} (relevance: ${b.relevanceScore}, confidence: ${b.confidence})\n${b.content}\n`
    ).join('\n');

    const memoryBlock = relevantMemories.length > 0
      ? `Relevant memories:\n${relevantMemories.map(m => `- ${m}`).join('\n')}\n\n`
      : '';

    // Use optimizer variant if available and enabled
    if (this.promptOptimizer?.enabled) {
      const variant = this.promptOptimizer.selectSerenity();
      return fillTemplate(variant.template, {
        userMessage: input.userMessage,
        memoryBlock,
        yangBlock,
        yinBlock,
        yangBranchCount: String(input.yang.branches.length),
        yinBranchCount: String(input.yin.baselineBranches.length),
        noveltyThreshold: String(this.config.noveltyThreshold),
        relevanceThreshold: String(this.config.relevanceThreshold),
        branchesConsidered: String(input.yang.branches.length + input.yin.baselineBranches.length),
        sessionId,
      });
    }

    return `You are SERENITY — synthesizer of Yang (expansion) and Yin (grounding).\n\nUSER MESSAGE:\n"""${input.userMessage}"""\n\n${memoryBlock}YANG (${input.yang.branches.length} branches):\n${yangBlock}\n\nYIN (${input.yin.baselineBranches.length} branches):\n${yinBlock}\n\nFind the single most valuable insight by comparing Yang and Yin:\n- CONVERGENCE: Both independently identified the same point → high confidence\n- TENSION: Creative vs. grounded conflict → reveals hidden assumptions\n- GAP: One sees what the other misses → complementary insight\n\nThresholds: novelty > ${this.config.noveltyThreshold} AND relevance > ${this.config.relevanceThreshold} → surface.\n\nA signal that merely RESTATES the user's message is worthless. Only surface what changes the response.\n\nIf no genuine insight exists, set hasSignal: false.\n\nIMPORTANT: Frame the signal content as guidance for the AI assistant — what should it do differently or consider because of this insight? Do NOT describe the user. Write as: "Consider X because Y" or "Watch for Z" or "The approach may need to account for W".\n\nOUTPUT (JSON):\n{\n  "hasSignal": true,\n  "signal": {\n    "type": "edge_case|alternative|assumption|connection|contradiction|convergence|tension|gap",\n    "content": "What the AI should do differently or consider — 1-2 sentences of guidance, not a user description",\n    "confidence": 0.0-1.0,\n    "urgency": "immediate|background"\n  },\n  "branchesConsidered": ${input.yang.branches.length + input.yin.baselineBranches.length},\n  "branchesSurfaced": 1\n}\n\nReturn ONLY valid JSON. No markdown fences, no explanation, no extra text.`;
  }

  /**
   * parseDualResponse — Parse response from dual synthesis
   */
  private async parseDualResponse(
    response: { text: string },
    input: import('../../../types/dialectic.js').DualSynthesisInput,
    provider?: IProvider,
    modelOverride?: string,
    signal?: AbortSignal
  ): Promise<Synthesis> {
    try {
      const text = (response.text || '').trim();
      const jsonMatch = text.match(/\{[\s\S]*\}/);

      if (jsonMatch) {
        const parsed = JSON.parse(jsonMatch[0]);
        if (!parsed.hasSignal) {
          return {
            hasSignal: false,
            branchesConsidered: parsed.branchesConsidered || input.yang.branches.length + input.yin.baselineBranches.length,
            branchesSurfaced: 0,
          };
        }

        const signal: DialecticSignal = {
          type: parsed.signal?.type || 'connection',
          content: parsed.signal?.content || '',
          confidence: Math.max(0, Math.min(1, parsed.signal?.confidence || 0.5)),
          sourceBranches: [
            ...input.yang.branches.slice(0, 2).map(b => b.id),
            ...input.yin.baselineBranches.slice(0, 2).map(b => b.id),
          ],
          urgency: parsed.signal?.urgency || 'background',
        };

        return {
          hasSignal: true,
          signal: signal,
          branchesConsidered: parsed.branchesConsidered || input.yang.branches.length + input.yin.baselineBranches.length,
          branchesSurfaced: parsed.branchesSurfaced || 1,
        };
      }

      // Fallback: heuristic analysis
      return this.fallbackDualSynthesis(input);
    } catch (error) {
      this.logger.warn('Serenity: failed to parse dual response', { error: String(error) });
      return this.fallbackDualSynthesis(input);
    }
  }

  /**
   * fallbackDualSynthesis — Heuristic synthesis when LLM fails
   */
  private fallbackDualSynthesis(
    input: import('../../../types/dialectic.js').DualSynthesisInput
  ): Synthesis {
    const tokenize = (s: string) => new Set(
      s.toLowerCase().replace(/[^\w\s]/g, ' ').split(/\s+/).filter(w => w.length > 3)
    );

    const yangTokens = input.yang.branches.flatMap(b => [...tokenize(b.content)]);
    const yinTokens = input.yin.baselineBranches.flatMap(b => [...tokenize(b.content)]);

    const yangSet = new Set(yangTokens);
    const yinSet = new Set(yinTokens);

    const overlaps = [...yangSet].filter(t => yinSet.has(t));

    if (overlaps.length >= 2) {
      const signal: DialecticSignal = {
        type: 'convergence',
        content: `Both Yang and Yin independently identified: ${overlaps.slice(0, 3).join(', ')}`,
        confidence: Math.min(0.95, 0.6 + overlaps.length * 0.1),
        sourceBranches: [...input.yang.branches.slice(0, 2).map(b => b.id), ...input.yin.baselineBranches.slice(0, 2).map(b => b.id)],
        urgency: 'background',
      };

      return {
        hasSignal: true,
        signal: signal,
        branchesConsidered: input.yang.branches.length + input.yin.baselineBranches.length,
        branchesSurfaced: 1,
      };
    }

    return {
      hasSignal: false,
      branchesConsidered: input.yang.branches.length + input.yin.baselineBranches.length,
      branchesSurfaced: 0,
    };
  }

  /**
   * calculateDualDialecticQuality — Quality metric for parallel dialectic
   */
  private calculateDualDialecticQuality(
    input: import('../../../types/dialectic.js').DualSynthesisInput,
    synthesis: Synthesis
  ): number {
    const yangNovelty = input.yang.branches.reduce((sum, b) => sum + b.noveltyScore, 0) /
      Math.max(1, input.yang.branches.length);

    const yinRelevance = input.yin.baselineBranches.reduce((sum, b) => sum + b.relevanceScore, 0) /
      Math.max(1, input.yin.baselineBranches.length);

    const synthesisBonus = synthesis.hasSignal ? 0.2 : 0;

    return (yangNovelty * 0.3) + (yinRelevance * 0.3) + 0.2 + synthesisBonus;
  }
  private async callProvider(prompt: string, opts?: { provider?: IProvider; model?: string; maxTokens?: number; allowConcurrent?: boolean; dedupe?: boolean; timeoutMs?: number; signal?: AbortSignal }): Promise<{ text: string; inputTokens: number; outputTokens: number }> {
    const messages = [{ role: 'user' as const, content: prompt }];

    const modelSpec = opts?.model ?? this.config.model;
    const slashIdx = modelSpec.indexOf('/');
    const modelName = slashIdx >= 0 ? modelSpec.slice(slashIdx + 1) : modelSpec;

    const callOpts: any = {
      model: modelName,
      stream: true as const,
      maxTokens: opts?.maxTokens ?? 4000,
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
        try { this.logger?.info?.('Serenity.callProvider: invoking provider', { model: modelName, allowConcurrent: callOpts.allowConcurrent, dedupe: callOpts.dedupe }) } catch {}
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
          try { this.logger?.warn?.('Serenity: provider request deduped, backing off and retrying', { attempt, wait, error: String(err) }) } catch {}
          await new Promise(res => setTimeout(res, wait))
          continue
        }
        throw err
      }
    }
  }

  private async parseResponse(response: { text: string }, validBranches: any[], provider?: IProvider, modelOverride?: string, signal?: AbortSignal): Promise<Synthesis> {
    try {
      const text = (response.text || '').trim();
      const jsonMatch = text.match(/\{[\s\S]*\}/);
      if (jsonMatch) {
        const parsed = JSON.parse(jsonMatch[0]);
        if (!parsed.hasSignal) {
          return {
            hasSignal: false,
            branchesConsidered: parsed.branchesConsidered || validBranches.length,
            branchesSurfaced: 0,
          };
        }

        const signal: DialecticSignal = {
          type: parsed.signal?.type || 'connection',
          content: parsed.signal?.content || '',
          confidence: Math.max(0, Math.min(1, parsed.signal?.confidence || 0.5)),
          sourceBranches: validBranches.map(b => b.yang.id),
          urgency: parsed.signal?.urgency || 'background',
        };

        return {
          hasSignal: true,
          signal,
          branchesConsidered: parsed.branchesConsidered || validBranches.length,
          branchesSurfaced: parsed.branchesSurfaced || 1,
        };
      }

      // Delegate repair to Thinker if available (single attempt)
      if (this.eventBus) {
        try {
          const reqId = `serenity-repair-${Date.now()}-${Math.random().toString(36).slice(2,6)}`;
          const schema = `{\n  "hasSignal": true,\n  "signal": {\n    "type": "edge_case|alternative|assumption|connection|contradiction|convergence|tension|gap",\n    "content": "string",\n    "confidence": 0.0-1.0,\n    "urgency": "immediate|background"\n  },\n  "branchesConsidered": 0,\n  "branchesSurfaced": 0\n}`;
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
                if (typeof parsed2.hasSignal !== 'undefined') {
                  if (parsed2.hasSignal) {
                    const signal: DialecticSignal = {
                      type: parsed2.signal?.type || 'connection',
                      content: parsed2.signal?.content || '',
                      confidence: Math.max(0, Math.min(1, parsed2.signal?.confidence || 0.5)),
                      sourceBranches: validBranches.map(b => b.yang.id),
                      urgency: parsed2.signal?.urgency || 'background',
                    };
                    return {
                      hasSignal: true,
                      signal,
                      branchesConsidered: parsed2.branchesConsidered || validBranches.length,
                      branchesSurfaced: parsed2.branchesSurfaced || 1,
                    };
                  }
                  // explicit false -> no signal
                  return { hasSignal: false, branchesConsidered: parsed2.branchesConsidered || validBranches.length, branchesSurfaced: 0 };
                }
              } catch (err) { /* fall through */ }
            }
          }
        } catch (err) {
          this.logger.warn('Serenity: thinker repair failed', { error: String(err) });
        }
      }

      // Single provider repair attempt (short timeout)
      if (provider) {
        try {
          const modelSpec = modelOverride ?? this.config.model;
          const slashIdx = modelSpec.indexOf('/');
          const modelName = slashIdx >= 0 ? modelSpec.slice(slashIdx + 1) : modelSpec;
          const schema = `{\n  "hasSignal": true,\n  "signal": {\n    "type": "edge_case|alternative|assumption|connection|contradiction|convergence|tension|gap",\n    "content": "string",\n    "confidence": 0.0-1.0,\n    "urgency": "immediate|background"\n  },\n  "branchesConsidered": 0,\n  "branchesSurfaced": 0\n}`;

          const prompt = `The previous response failed to produce valid JSON. Convert the following TEXT into valid JSON matching EXACTLY this schema and WRAP the JSON between the literal markers ---BEGIN_JSON--- and ---END_JSON---. Return NOTHING else.\n\nSCHEMA:\n${schema}\n\nTEXT:\n"""${text}"""\n\nReturn exactly: ---BEGIN_JSON---<JSON>---END_JSON---`;

          this.logger.info('Serenity: no JSON found — attempting JSON repair call to provider (attempt 1)');
          const messages = [{ role: 'user' as const, content: prompt }];
          const callOpts: any = { model: modelName, stream: true as const, maxTokens: 2000, temperature: 0.0, allowConcurrent: true };
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
              if (typeof parsed2.hasSignal !== 'undefined') {
                if (parsed2.hasSignal) {
                  const signal: DialecticSignal = {
                    type: parsed2.signal?.type || 'connection',
                    content: parsed2.signal?.content || '',
                    confidence: Math.max(0, Math.min(1, parsed2.signal?.confidence || 0.5)),
                    sourceBranches: validBranches.map(b => b.yang.id),
                    urgency: parsed2.signal?.urgency || 'background',
                  };
                  return { hasSignal: true, signal, branchesConsidered: parsed2.branchesConsidered || validBranches.length, branchesSurfaced: parsed2.branchesSurfaced || 1 };
                }
                return { hasSignal: false, branchesConsidered: parsed2.branchesConsidered || validBranches.length, branchesSurfaced: 0 };
              }
            } catch (err) { this.logger.warn('Serenity: provider repair parse failed', { error: String(err) }) }
          }
        } catch (err) {
          this.logger.warn('Serenity: provider repair attempt failed', { error: String(err) });
        }
      }

      // Structured fallback: attempt to infer a signal from plain text
      if (text) {
        this.logger.info('Serenity: attempting structured fallback to infer signals from plain text');

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

        const urgentKeywords = ['urgent','immediate','critical','must','should','warning','danger','important','priority','alert','asap'];
        const assumptionKeywords = ['assume','assumption','presume','presuppose','suppose'];
        const contradictionKeywords = ['contradict','contradiction','inconsistent','conflict','contradicts'];

        // find urgent item
        for (const it of items) {
          if (new RegExp(`\\b(${urgentKeywords.join('|')})\\b`, 'i').test(it)) {
            const confidence = Math.max(0.5, Math.min(0.95, 0.6 + (it.length / 800)));
            const signal: DialecticSignal = {
              type: 'edge_case',
              content: it.trim().slice(0, 1000),
              confidence,
              sourceBranches: validBranches.map(b => b.yang.id),
              urgency: 'immediate',
            };
            return { hasSignal: true, signal, branchesConsidered: validBranches.length, branchesSurfaced: 1 };
          }
        }

        // find assumption
        for (const it of items) {
          if (new RegExp(`\\b(${assumptionKeywords.join('|')})\\b`, 'i').test(it)) {
            const confidence = Math.max(0.4, Math.min(0.85, 0.55 + (it.length / 1000)));
            const signal: DialecticSignal = {
              type: 'assumption',
              content: it.trim().slice(0, 1000),
              confidence,
              sourceBranches: validBranches.map(b => b.yang.id),
              urgency: 'background',
            };
            return { hasSignal: true, signal, branchesConsidered: validBranches.length, branchesSurfaced: 1 };
          }
        }

        // find contradiction
        for (const it of items) {
          if (new RegExp(`\\b(${contradictionKeywords.join('|')})\\b`, 'i').test(it)) {
            const confidence = Math.max(0.5, Math.min(0.9, 0.6 + (it.length / 900)));
            const signal: DialecticSignal = {
              type: 'contradiction',
              content: it.trim().slice(0, 1000),
              confidence,
              sourceBranches: validBranches.map(b => b.yang.id),
              urgency: 'immediate',
            };
            return { hasSignal: true, signal, branchesConsidered: validBranches.length, branchesSurfaced: 1 };
          }
        }

        // Additional heuristic fallbacks using validBranches
        const tokenize = (s: string) => Array.from(new Set(String(s || '').toLowerCase().replace(/[^\w\s]/g, ' ').split(/\s+/).filter(Boolean)));
        const jaccard = (a: string, b: string) => {
          const A = tokenize(a);
          const B = tokenize(b);
          if (A.length === 0 || B.length === 0) return 0;
          const setA = new Set(A);
          const inter = A.filter(x => B.includes(x)).length;
          const union = new Set([...A, ...B]).size;
          return union === 0 ? 0 : inter / union;
        };

        // Detect contradictions between high-relevance/high-novelty branches
        for (let i = 0; i < validBranches.length; i++) {
          for (let j = i + 1; j < validBranches.length; j++) {
            const a = validBranches[i];
            const b = validBranches[j];
            const relA = a.yin?.relevance ?? 0;
            const relB = b.yin?.relevance ?? 0;
            const novA = a.yang?.noveltyScore ?? 0;
            const novB = b.yang?.noveltyScore ?? 0;
            if (relA >= 0.6 && relB >= 0.6 && novA >= 0.5 && novB >= 0.5) {
              const sim = jaccard(a.yang.content || '', b.yang.content || '');
              if (sim < 0.25) {
                const confidence = Math.max(0.6, Math.min(0.95, (novA + novB + relA + relB) / 4));
                const signal: DialecticSignal = {
                  type: 'contradiction',
                  content: `Contradictory insights detected between ${a.yang.id} and ${b.yang.id}: ${a.yang.content.slice(0, 400)} ... vs ... ${b.yang.content.slice(0, 400)}`,
                  confidence,
                  sourceBranches: [a.yang.id, b.yang.id],
                  urgency: 'immediate',
                };
                return { hasSignal: true, signal, branchesConsidered: validBranches.length, branchesSurfaced: 2 };
              }
            }
          }
        }

        // Score branches and surface the top candidate if it meets minConfidence
        const scored = validBranches.map(v => {
          const y = v.yang || {};
          const yi = v.yin || {};
          const score = ((y.noveltyScore ?? 0.5) * 0.6) + ((yi.relevance ?? 0.5) * 0.4);
          return { score, yang: y, yin: yi };
        }).sort((a, b) => b.score - a.score);

        if (scored.length > 0 && scored[0].score >= (this.config.minConfidence ?? 0.7)) {
          const top = scored[0];
          const confidence = Math.max(0, Math.min(1, top.score));
          const urgency = confidence >= 0.85 ? 'immediate' : 'background';
          const signal: DialecticSignal = {
            type: 'alternative',
            content: (top.yang?.content || '').slice(0, 1000),
            confidence,
            sourceBranches: [top.yang?.id || 'yang-1'],
            urgency,
          };
          return { hasSignal: true, signal, branchesConsidered: validBranches.length, branchesSurfaced: 1 };
        }

        // default: if there are multiple items, surface the most prominent as a background connection
        if (items.length >= 1) {
          const it = items[0];
          const confidence = Math.max(0.3, Math.min(0.7, 0.45 + (it.length / 1200)));
          const signal: DialecticSignal = {
            type: 'connection',
            content: it.trim().slice(0, 1000),
            confidence,
            sourceBranches: validBranches.map(b => b.yang.id),
            urgency: 'background',
          };
          return { hasSignal: true, signal, branchesConsidered: validBranches.length, branchesSurfaced: 1 };
        }
      }

      return {
        hasSignal: false,
        branchesConsidered: validBranches.length,
        branchesSurfaced: 0,
      };
    } catch (error) {
      this.logger.warn('Serenity: failed to parse response', { error: String(error) });
      return {
        hasSignal: false,
        branchesConsidered: validBranches.length,
        branchesSurfaced: 0,
      };
    }
  }
}

export const createSerenity = (logger: ILogger, config?: Partial<SerenityConfig>): Serenity =>
  new Serenity(logger, config);
