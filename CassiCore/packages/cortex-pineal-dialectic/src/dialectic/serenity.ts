/**
 * Serenity — The Mediator
 *
 * Analyzes the Yang/Yin dialectic and extracts signals of interest.
 * Determines what should be surfaced to the main agent.
 */

import { getModelSpec } from '../../config/system-settings.js';

import { DialecticVoiceBase, type BaseDialecticConfig } from './dialectic-voice-base.js';
import { fillTemplate } from './prompt-optimizer.js';

import type { PromptOptimizer } from './prompt-optimizer.js';
import type {
  ISerenity,
  SerenityOutput,
  Synthesis,
  DialecticSignal,
  YangOutput,
  YinOutput,
  DualSynthesisInput,
} from '../../../types/dialectic.js';
import type { ILogger } from '../../../types/interfaces.js';
import type { IProvider } from '../../../types/runtime.js';





/**
 * Configuration for Serenity (Synthesizer)
 */
export interface SerenityConfig extends BaseDialecticConfig {
  noveltyThreshold: number;
  relevanceThreshold: number;
  minConfidence: number;
  insightPreference: 'generous' | 'balanced' | 'conservative';
}

/**
 * Serenity — The Mediator
 *
 * Analyzes the Yang/Yin dialectic and extracts signals of interest.
 * Determines what should be surfaced to the main agent.
 */
export class Serenity extends DialecticVoiceBase<SerenityConfig> implements ISerenity {
  readonly name = 'serenity' as const;

  /**
   * Create a new Serenity instance
   *
   * @param logger - Root logger
   * @param config - Optional configuration overrides
   */
  constructor(logger: ILogger, config?: Partial<SerenityConfig>) {
    super(
      logger,
      {
        enabled: config?.enabled ?? true,
        model: config?.model ?? getModelSpec('reasoning'),
        temperature: config?.temperature ?? 0.4,
        noveltyThreshold: config?.noveltyThreshold ?? 0.5,
        relevanceThreshold: config?.relevanceThreshold ?? 0.5,
        minConfidence: config?.minConfidence ?? 0.6,
        insightPreference: config?.insightPreference ?? 'generous',
      },
      'serenity',
    );
  }

  /**
   * Wire the prompt optimizer for variant selection
   *
   * @param optimizer - Prompt optimizer instance
   */
  override setPromptOptimizer(optimizer: PromptOptimizer): void {
    this.promptOptimizer = optimizer;
    this.logger.info('Serenity: prompt optimizer wired');
  }

  /**
   * Synthesize Yang and Yin outputs to extract signals
   *
   * @param sessionId - Session identifier
   * @param userMessage - User's message text
   * @param yangOutput - Yang's expansion output
   * @param yinOutput - Yin's critique output
   * @param relevantMemories - Relevant memories for context
   * @param opts - Optional overrides (model, provider, etc.)
   * @returns Serenity output with synthesis and metadata
   */
  async synchronize(
    sessionId: string,
    userMessage: string,
    yangOutput: YangOutput,
    yinOutput: YinOutput,
    relevantMemories: string[],
    opts?: {
      model?: string;
      provider?: IProvider;
      allowConcurrent?: boolean;
      dedupe?: boolean;
      signal?: AbortSignal;
    },
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
      const response = await this.callProvider(prompt, {
        provider: providerToUse,
        model: opts?.model,
        allowConcurrent: opts?.allowConcurrent,
        dedupe: opts?.dedupe,
        timeoutMs: 30000,
        signal: opts?.signal,
      });

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
        error: String(error),
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
   * Dual synthesis for parallel dialectic mode
   *
   * @param sessionId - Session identifier
   * @param input - Dual synthesis input (Yang + Yin)
   * @param relevantMemories - Relevant memories for context
   * @param opts - Optional overrides (model, provider, etc.)
   * @returns Serenity output with synthesis and metadata
   */
  async synthesizeDual(
    sessionId: string,
    input: DualSynthesisInput,
    relevantMemories: string[],
    opts?: {
      model?: string;
      provider?: IProvider;
      allowConcurrent?: boolean;
      dedupe?: boolean;
      signal?: AbortSignal;
    },
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
        signal: opts?.signal,
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
        error: String(error),
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

  /**
   * Get valid branches that passed Yin's critique
   *
   * @param yangOutput - Yang's expansion output
   * @param yinOutput - Yin's critique output
   * @returns Array of valid branch pairs
   */
  private getValidBranches(
    yangOutput: YangOutput,
    yinOutput: YinOutput,
  ): Array<{ yang: (typeof yangOutput.branches)[0]; yin: (typeof yinOutput.critiques)[0] }> {
    const valid: Array<{ yang: (typeof yangOutput.branches)[0]; yin: (typeof yinOutput.critiques)[0] }> = [];

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

  /**
   * Calculate dialectic quality metric
   *
   * @param yangOutput - Yang's expansion output
   * @param yinOutput - Yin's critique output
   * @returns Quality score (0-1)
   */
  private calculateDialecticQuality(yangOutput: YangOutput, yinOutput: YinOutput): number {
    if (yangOutput.branches.length === 0) return 0.5;

    const validCount = yinOutput.critiques.filter(c => c.valid).length;
    const validationRate = validCount / yangOutput.branches.length;

    const avgYangNovelty =
      yangOutput.branches.reduce((sum, b) => sum + b.noveltyScore, 0) / yangOutput.branches.length;

    const avgYinRelevance =
      yinOutput.critiques.reduce((sum, c) => sum + c.relevance, 0) / yinOutput.critiques.length || 0;

    return validationRate * 0.3 + avgYangNovelty * 0.4 + avgYinRelevance * 0.3;
  }

  /**
   * Build the prompt for sequential synthesis
   *
   * @param sessionId - Session identifier
   * @param userMessage - User's message text
   * @param yangOutput - Yang's expansion output
   * @param yinOutput - Yin's critique output
   * @param validBranches - Valid branch pairs
   * @param relevantMemories - Relevant memories
   * @returns Formatted prompt string
   */
  private buildPrompt(
    sessionId: string,
    userMessage: string,
    yangOutput: YangOutput,
    yinOutput: YinOutput,
    validBranches: Array<{ yang: any; yin: any }>,
    relevantMemories: string[],
  ): string {
    const yangBlock = yangOutput.branches
      .map(b => `\n[${b.id}] ${b.type} (novelty: ${b.noveltyScore}, confidence: ${b.confidence})\n${b.content}\n`)
      .join('\n');

    const yinBlock = yinOutput.critiques
      .map(c => {
        const branch = yangOutput.branches.find(b => b.id === c.yangBranchId);
        return `\n[${c.yangBranchId}] ${c.valid ? 'VALID' : 'INVALID'} — relevance: ${c.relevance}, action: ${c.action}\nEssence: ${c.essence || 'N/A'}\nCritique: ${c.critique}\n`;
      })
      .join('\n');

    const memoryBlock =
      relevantMemories.length > 0 ? `Relevant memories:\n${relevantMemories.map(m => `- ${m}`).join('\n')}\n\n` : '';

    return `You are SERENITY — synthesizer of Yang (expansion) and Yin (refinement).\n\nUSER MESSAGE:\n"""${userMessage}"""\n\n${memoryBlock}YANG'S EXPANSIONS:\n${yangBlock}\n\nYIN'S CRITIQUES:\n${yinBlock}\n\nVALID BRANCHES TO CONSIDER (${validBranches.length}):\n${validBranches.map(({ yang, yin }) => `- ${yang.id}: ${yin.essence || yang.content}`).join('\n')}\n\nFind the single most valuable insight by comparing Yang and Yin:\n- CONVERGENCE: Both identified the same point → high confidence\n- TENSION: Creative vs. grounded conflict → reveals assumptions\n- GAP: One sees what the other misses → complementary insight\n\nThresholds: novelty > ${this.config.noveltyThreshold} AND relevance > ${this.config.relevanceThreshold} → surface.\n\nA signal that merely RESTATES the user's message is worthless. Only surface what changes the response.\n\nIf no genuine insight exists, set hasSignal: false.\n\nIMPORTANT: Frame the signal content as guidance for the AI assistant — what should it do differently or consider because of this insight? Do NOT describe the user. Write as: "Consider X because Y" or "Watch for Z" or "The approach may need to account for W".\n\nOUTPUT (JSON):\n{\n  "hasSignal": true,\n  "signal": {\n    "type": "edge_case|alternative|assumption|connection|contradiction|convergence|tension|gap",\n    "content": "What the AI should do differently or consider — 1-2 sentences of guidance, not a user description",\n    "confidence": 0.0-1.0,\n    "urgency": "immediate|background"\n  },\n  "branchesConsidered": 4,\n  "branchesSurfaced": 1\n}\n\nReturn ONLY valid JSON. No markdown fences, no explanation, no extra text.`;
  }

  /**
   * Build the prompt for dual synthesis (parallel mode)
   *
   * @param sessionId - Session identifier
   * @param input - Dual synthesis input
   * @param relevantMemories - Relevant memories
   * @returns Formatted prompt string
   */
  private buildDualPrompt(sessionId: string, input: DualSynthesisInput, relevantMemories: string[]): string {
    const yangBlock = input.yang.branches
      .map(b => `\n[${b.id}] ${b.type} (novelty: ${b.noveltyScore}, confidence: ${b.confidence})\n${b.content}\n`)
      .join('\n');

    const yinBlock = input.yin.baselineBranches
      .map(b => `\n[${b.id}] ${b.type} (relevance: ${b.relevanceScore}, confidence: ${b.confidence})\n${b.content}\n`)
      .join('\n');

    const memoryBlock =
      relevantMemories.length > 0 ? `Relevant memories:\n${relevantMemories.map(m => `- ${m}`).join('\n')}\n\n` : '';

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
   * Parse synthesis from dual response
   *
   * @param response - Provider response
   * @param input - Dual synthesis input
   * @param provider - Provider for repair attempts
   * @param modelOverride - Optional model override
   * @param signal - Abort signal
   * @returns Synthesis result
   */
  private async parseDualResponse(
    response: { text: string },
    input: DualSynthesisInput,
    provider?: IProvider,
    modelOverride?: string,
    signal?: AbortSignal,
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
          confidence: this.clamp(parsed.signal?.confidence || 0.5, 0, 1),
          sourceBranches: [
            ...input.yang.branches.slice(0, 2).map(b => b.id),
            ...input.yin.baselineBranches.slice(0, 2).map(b => b.id),
          ],
          urgency: parsed.signal?.urgency || 'background',
        };

        return {
          hasSignal: true,
          signal,
          branchesConsidered: parsed.branchesConsidered || input.yang.branches.length + input.yin.baselineBranches.length,
          branchesSurfaced: parsed.branchesSurfaced || 1,
        };
      }

      return this.fallbackDualSynthesis(input);
    } catch (error) {
      this.logger.warn('Serenity: failed to parse dual response', { error: String(error) });
      return this.fallbackDualSynthesis(input);
    }
  }

  /**
   * Fallback synthesis when LLM fails
   *
   * @param input - Dual synthesis input
   * @returns Heuristic synthesis
   */
  private fallbackDualSynthesis(input: DualSynthesisInput): Synthesis {
    const tokenize = (s: string) =>
      new Set(s.toLowerCase().replace(/[^\w\s]/g, ' ').split(/\s+/).filter(w => w.length > 3));

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
        sourceBranches: [
          ...input.yang.branches.slice(0, 2).map(b => b.id),
          ...input.yin.baselineBranches.slice(0, 2).map(b => b.id),
        ],
        urgency: 'background',
      };

      return {
        hasSignal: true,
        signal,
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
   * Calculate quality metric for parallel dialectic
   *
   * @param input - Dual synthesis input
   * @param synthesis - Synthesis result
   * @returns Quality score (0-1)
   */
  private calculateDualDialecticQuality(input: DualSynthesisInput, synthesis: Synthesis): number {
    const yangNovelty =
      input.yang.branches.reduce((sum, b) => sum + b.noveltyScore, 0) / Math.max(1, input.yang.branches.length);

    const yinRelevance =
      input.yin.baselineBranches.reduce((sum, b) => sum + b.relevanceScore, 0) /
      Math.max(1, input.yin.baselineBranches.length);

    const synthesisBonus = synthesis.hasSignal ? 0.2 : 0;

    return yangNovelty * 0.3 + yinRelevance * 0.3 + 0.2 + synthesisBonus;
  }

  /**
   * Parse synthesis from provider response
   *
   * @param response - Provider response
   * @param validBranches - Valid branch pairs
   * @param provider - Provider for repair attempts
   * @param modelOverride - Optional model override
   * @param signal - Abort signal
   * @returns Synthesis result
   */
  private async parseResponse(
    response: { text: string },
    validBranches: any[],
    provider?: IProvider,
    modelOverride?: string,
    signal?: AbortSignal,
  ): Promise<Synthesis> {
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
          confidence: this.clamp(parsed.signal?.confidence || 0.5, 0, 1),
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

      // Attempt repair via Thinker
      const schema = `{\n  "hasSignal": true,\n  "signal": {\n    "type": "edge_case|alternative|assumption|connection|contradiction|convergence|tension|gap",\n    "content": "string",\n    "confidence": 0.0-1.0,\n    "urgency": "immediate|background"\n  },\n  "branchesConsidered": 0,\n  "branchesSurfaced": 0\n}`;
      const thinkerResult = await this.attemptThinkerRepair(text, schema);

      if (thinkerResult) {
        try {
          const parsed2 = JSON.parse(thinkerResult);
          if (typeof parsed2.hasSignal !== 'undefined') {
            if (parsed2.hasSignal) {
              const signal: DialecticSignal = {
                type: parsed2.signal?.type || 'connection',
                content: parsed2.signal?.content || '',
                confidence: this.clamp(parsed2.signal?.confidence || 0.5, 0, 1),
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
            return {
              hasSignal: false,
              branchesConsidered: parsed2.branchesConsidered || validBranches.length,
              branchesSurfaced: 0,
            };
          }
        } catch {
          // Fall through to provider repair
        }
      }

      // Attempt repair via Provider
      if (provider) {
        const providerResult = await this.attemptProviderRepair(text, schema, provider, modelOverride, signal);
        if (providerResult) {
          try {
            const parsed2 = JSON.parse(providerResult);
            if (typeof parsed2.hasSignal !== 'undefined') {
              if (parsed2.hasSignal) {
                const signal: DialecticSignal = {
                  type: parsed2.signal?.type || 'connection',
                  content: parsed2.signal?.content || '',
                  confidence: this.clamp(parsed2.signal?.confidence || 0.5, 0, 1),
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
              return {
                hasSignal: false,
                branchesConsidered: parsed2.branchesConsidered || validBranches.length,
                branchesSurfaced: 0,
              };
            }
          } catch {
            // Fall through to fallback
          }
        }
      }

      // Structured fallback
      return this.fallbackParseResponse(text, validBranches);
    } catch (error) {
      this.logger.warn('Serenity: failed to parse response', { error: String(error) });
      return {
        hasSignal: false,
        branchesConsidered: validBranches.length,
        branchesSurfaced: 0,
      };
    }
  }

  /**
   * Fallback parsing for response
   *
   * @param text - Raw response text
   * @param validBranches - Valid branch pairs
   * @returns Synthesis result
   */
  private fallbackParseResponse(text: string, validBranches: any[]): Synthesis {
    const items = this.parseIntoItems(text);

    const urgentKeywords = ['urgent', 'immediate', 'critical', 'must', 'should', 'warning', 'danger', 'important', 'priority', 'alert', 'asap'];
    const assumptionKeywords = ['assume', 'assumption', 'presume', 'presuppose', 'suppose'];
    const contradictionKeywords = ['contradict', 'contradiction', 'inconsistent', 'conflict', 'contradicts'];

    // Find urgent item
    for (const it of items) {
      if (new RegExp(`\\b(${urgentKeywords.join('|')})\\b`, 'i').test(it)) {
        const signal: DialecticSignal = {
          type: 'edge_case',
          content: it.trim().slice(0, 1000),
          confidence: Math.max(0.5, Math.min(0.95, 0.6 + it.length / 800)),
          sourceBranches: validBranches.map(b => b.yang.id),
          urgency: 'immediate',
        };
        return { hasSignal: true, signal, branchesConsidered: validBranches.length, branchesSurfaced: 1 };
      }
    }

    // Find assumption
    for (const it of items) {
      if (new RegExp(`\\b(${assumptionKeywords.join('|')})\\b`, 'i').test(it)) {
        const signal: DialecticSignal = {
          type: 'assumption',
          content: it.trim().slice(0, 1000),
          confidence: Math.max(0.4, Math.min(0.85, 0.55 + it.length / 1000)),
          sourceBranches: validBranches.map(b => b.yang.id),
          urgency: 'background',
        };
        return { hasSignal: true, signal, branchesConsidered: validBranches.length, branchesSurfaced: 1 };
      }
    }

    // Find contradiction
    for (const it of items) {
      if (new RegExp(`\\b(${contradictionKeywords.join('|')})\\b`, 'i').test(it)) {
        const signal: DialecticSignal = {
          type: 'contradiction',
          content: it.trim().slice(0, 1000),
          confidence: Math.max(0.5, Math.min(0.9, 0.6 + it.length / 900)),
          sourceBranches: validBranches.map(b => b.yang.id),
          urgency: 'immediate',
        };
        return { hasSignal: true, signal, branchesConsidered: validBranches.length, branchesSurfaced: 1 };
      }
    }

    // Score branches and surface top candidate
    const scored = validBranches
      .map(v => {
        const y = v.yang || {};
        const yi = v.yin || {};
        const score = ((y.noveltyScore ?? 0.5) * 0.6) + ((yi.relevance ?? 0.5) * 0.4);
        return { score, yang: y, yin: yi };
      })
      .sort((a, b) => b.score - a.score);

    if (scored.length > 0 && scored[0].score >= this.config.minConfidence) {
      const top = scored[0];
      const confidence = this.clamp(top.score, 0, 1);
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

    // Default: surface most prominent item as background connection
    if (items.length >= 1) {
      const it = items[0];
      const signal: DialecticSignal = {
        type: 'connection',
        content: it.trim().slice(0, 1000),
        confidence: Math.max(0.3, Math.min(0.7, 0.45 + it.length / 1200)),
        sourceBranches: validBranches.map(b => b.yang.id),
        urgency: 'background',
      };
      return { hasSignal: true, signal, branchesConsidered: validBranches.length, branchesSurfaced: 1 };
    }

    return {
      hasSignal: false,
      branchesConsidered: validBranches.length,
      branchesSurfaced: 0,
    };
  }
}

/**
 * Factory function to create a Serenity instance
 *
 * @param logger - Root logger
 * @param config - Optional configuration overrides
 * @returns Serenity instance
 */
export const createSerenity = (logger: ILogger, config?: Partial<SerenityConfig>): Serenity => new Serenity(logger, config);
