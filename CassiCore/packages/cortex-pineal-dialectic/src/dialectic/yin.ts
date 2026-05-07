/**
 * YinObserver — The Principle of Refinement
 *
 * Critiques and compresses Yang's expansions.
 * Finds flaws, extracts essence, and determines relevance.
 */

import { getModelSpec } from '../../config/system-settings.js';
import { composeSystemPrompt } from '../shared/posture-store.js';

import { DialecticVoiceBase, type BaseDialecticConfig } from './dialectic-voice-base.js';
import { YIN_CRITIQUE_SCHEMA, YIN_BASELINE_SCHEMA, JSON_INSTRUCTION } from './prompt-templates.js';

import type {
  IYinObserver,
  YinOutput,
  YinCritique,
  YangOutput,
  YangBranch,
  YangContext,
  YinBaselineOutput,
  YinBaselineBranch,
  YinAction,
} from '../../../types/dialectic.js';
import type { ILogger } from '../../../types/interfaces.js';
import type { IProvider } from '../../../types/runtime.js';





/**
 * Configuration for Yin observer
 */
export interface YinConfig extends BaseDialecticConfig {
  minRelevance: number;
}

/**
 * YinObserver — The Principle of Refinement
 *
 * Critiques and compresses Yang's expansions.
 * Finds flaws, extracts essence, and determines relevance.
 */
export class YinObserver extends DialecticVoiceBase<YinConfig> implements IYinObserver {
  readonly name = 'yin' as const;

  /**
   * Create a new YinObserver instance
   *
   * @param logger - Root logger
   * @param config - Optional configuration overrides
   */
  constructor(logger: ILogger, config?: Partial<YinConfig>) {
    super(
      logger,
      {
        enabled: config?.enabled ?? true,
        model: config?.model ?? getModelSpec('reasoning'),
        temperature: config?.temperature ?? 0.3,
        minRelevance: config?.minRelevance ?? 0.6,
      },
      'yin',
    );
  }

  /**
   * Observe Yang's output and generate critiques
   *
   * @param sessionId - Session identifier
   * @param userMessage - User's message text
   * @param yangOutput - Yang's expansion output
   * @param context - Optional observation context
   * @param opts - Optional overrides (model, provider, etc.)
   * @returns Yin output with critiques and metadata
   */
  async observe(
    sessionId: string,
    userMessage: string,
    yangOutput: YangOutput,
    context?: YangContext,
    opts?: {
      model?: string;
      provider?: IProvider;
      allowConcurrent?: boolean;
      dedupe?: boolean;
      signal?: AbortSignal;
    },
  ): Promise<YinOutput> {
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
      const response = await this.callProvider(prompt, {
        provider: providerToUse,
        model: opts?.model,
        allowConcurrent: opts?.allowConcurrent,
        dedupe: opts?.dedupe,
        inactivityMs: 30_000,
      });
      const critiques = await this.parseResponse(response, yangOutput.branches, providerToUse, opts?.model, opts?.signal);

      const totalOriginalLength = yangOutput.branches.reduce((sum, b) => sum + b.content.length, 0);
      const totalEssenceLength = critiques
        .filter(c => c.valid && c.essence)
        .reduce((sum, c) => sum + (c.essence?.length || 0), 0);
      const compressionRatio = totalOriginalLength > 0 ? totalEssenceLength / totalOriginalLength : 1.0;

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
        error: String(error),
      });

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
   * Generate independent baseline analysis for parallel mode
   *
   * @param sessionId - Session identifier
   * @param userMessage - User's message text
   * @param context - Observation context
   * @param opts - Optional overrides (model, provider, etc.)
   * @returns Baseline output with branches and self-critiques
   */
  async observeWithBaseline(
    sessionId: string,
    userMessage: string,
    context: YangContext,
    opts?: {
      model?: string;
      provider?: IProvider;
      allowConcurrent?: boolean;
      dedupe?: boolean;
      signal?: AbortSignal;
    },
  ): Promise<YinBaselineOutput> {
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
        inactivityMs: 30_000,
        signal: opts?.signal,
      });

      const baselineBranches = await this.parseBaselineResponse(response, providerToUse, opts?.model, opts?.signal);

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
          compressionRatio: 0.5,
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

  /**
   * Create a null critique for pass-through mode
   *
   * @param branch - Yang branch to critique
   * @returns Null critique
   */
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

  /**
   * Build the prompt for critiquing Yang branches
   *
   * @param sessionId - Session identifier
   * @param userMessage - User's message text
   * @param branches - Yang branches to critique
   * @param context - Optional observation context
   * @returns Formatted prompt string
   */
  private buildPrompt(
    _sessionId: string,
    userMessage: string,
    branches: YangBranch[],
    context?: YangContext,
  ): string {
    const guideBlock = context?.taskGuide ? `TASK GUIDE:\n${context.taskGuide}` : '';

    const branchesBlock = `YANG'S EXPANSIONS:\n` + branches
      .map(
        (b, idx) =>
          `\nBRANCH ${idx + 1} [${b.id}]:\n- Type: ${b.type}\n- Content: ${b.content}\n- Yang Confidence: ${b.confidence}\n- Yang Novelty: ${b.noveltyScore}`,
      )
      .join('\n');

    const sessionContext = [
      guideBlock,
      `MODE: critique`,
      `USER MESSAGE:\n"""${userMessage}"""`,
      branchesBlock,
      `Provide exactly ${branches.length} critiques in order, one per Yang branch. Verdict per branch: surface, compress, or discard.`,
      `OUTPUT JSON SCHEMA:\n${YIN_CRITIQUE_SCHEMA}`,
      JSON_INSTRUCTION,
    ].filter(s => s.length > 0).join('\n\n');

    return composeSystemPrompt('yin', 'dialectic', sessionContext);
  }

  /**
   * Build the prompt for baseline analysis (parallel mode)
   *
   * @param sessionId - Session identifier
   * @param userMessage - User's message text
   * @param context - Observation context
   * @returns Formatted prompt string
   */
  private buildBaselinePrompt(_sessionId: string, userMessage: string, context: YangContext): string {
    const guideBlock = context?.taskGuide ? `TASK GUIDE:\n${context.taskGuide}` : '';
    const memoryBlock = context?.recentMemories?.length
      ? `Recent context:\n${context.recentMemories.map(m => `- ${m.slice(0, 200)}`).join('\n')}`
      : '';

    const sessionContext = [
      guideBlock,
      memoryBlock,
      `MODE: baseline`,
      `USER MESSAGE:\n"""${userMessage}"""`,
      `Generate 3-5 baseline observations of what is missing or unstated in the user's message.`,
      `OUTPUT JSON SCHEMA:\n${YIN_BASELINE_SCHEMA}`,
      JSON_INSTRUCTION,
    ].filter(s => s.length > 0).join('\n\n');

    return composeSystemPrompt('yin', 'dialectic', sessionContext);
  }

  /**
   * Parse baseline branches from provider response
   *
   * @param response - Provider response
   * @param provider - Provider for repair attempts
   * @param modelOverride - Optional model override
   * @param signal - Abort signal
   * @returns Array of baseline branches
   */
  private async parseBaselineResponse(
    response: { text: string },
    provider?: IProvider,
    modelOverride?: string,
    signal?: AbortSignal,
  ): Promise<YinBaselineBranch[]> {
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
            confidence: this.clamp(b.confidence || 0.5, 0, 1),
            relevanceScore: this.clamp(b.relevanceScore || 0.5, 0, 1),
          }));
        }
      }

      // Fallback: parse as list items
      const items = text
        .split(/\n\s*\n/)
        .map(p => p.trim())
        .filter(p => p.length > 50);

      if (items.length >= 2) {
        const types: Array<YinBaselineBranch['type']> = [
          'grounding',
          'constraint',
          'reality_check',
          'prioritization',
          'risk_assessment',
        ];
        return items.slice(0, 5).map((item, idx) => ({
          id: `yin-${idx + 1}`,
          type: types[idx % types.length],
          content: item.slice(0, 500),
          confidence: 0.6 + idx * 0.05,
          relevanceScore: 0.7,
        }));
      }

      return [];
    } catch (error) {
      this.logger.warn('YinObserver: failed to parse baseline response', { error: String(error) });
      return [];
    }
  }

  /**
   * Parse critiques from provider response
   *
   * @param response - Provider response
   * @param branches - Original Yang branches
   * @param provider - Provider for repair attempts
   * @param modelOverride - Optional model override
   * @param signal - Abort signal
   * @returns Array of critiques
   */
  private async parseResponse(
    response: { text: string },
    branches: YangBranch[],
    provider?: IProvider,
    modelOverride?: string,
    signal?: AbortSignal,
  ): Promise<YinCritique[]> {
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
          const validActions: YinAction[] = ['surface', 'compress', 'discard'];
          const rawAction = c.action === 'refine' ? 'compress' : c.action === 'ignore' ? 'discard' : c.action;
          const action = (validActions.includes(rawAction) ? rawAction : 'surface') as YinAction;
          const valid = action !== 'discard';
          return {
            yangBranchId: c.yangBranchId || branch?.id || `yang-${idx + 1}`,
            valid,
            essence: c.essence,
            critique: c.critique || '',
            relevance: this.clamp(c.relevance || 0.5, 0, 1),
            action,
          };
        });
      }

      // Attempt repair via Thinker
      const schema = `{"critiques":[{"yangBranchId":"string","essence":"string","critique":"string","relevance":0.0-1.0,"action":"surface|compress|discard"}]}`;
      const thinkerResult = await this.attemptThinkerRepair(text, schema);

      if (thinkerResult) {
        try {
          const parsed2 = JSON.parse(thinkerResult);
          if (parsed2.critiques && Array.isArray(parsed2.critiques)) {
            this.logger.info('YinObserver: JSON repair succeeded (thinker)');
            return parsed2.critiques.map((c: any, idx: number) => {
              const branch = branches[idx] || branches.find(b => b.id === c.yangBranchId);
              return {
                yangBranchId: c.yangBranchId || branch?.id || `yang-${idx + 1}`,
                valid: c.valid ?? true,
                essence: c.essence,
                critique: c.critique || '',
                relevance: this.clamp(c.relevance || 0.5, 0, 1),
                action: c.action || 'surface',
              };
            });
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
            if (parsed2.critiques && Array.isArray(parsed2.critiques)) {
              this.logger.info('YinObserver: JSON repair succeeded (provider)');
              return parsed2.critiques.map((c: any, idx: number) => {
                const branch = branches[idx] || branches.find(b => b.id === c.yangBranchId);
                return {
                  yangBranchId: c.yangBranchId || branch?.id || `yang-${idx + 1}`,
                  valid: c.valid ?? true,
                  essence: c.essence,
                  critique: c.critique || '',
                  relevance: this.clamp(c.relevance || 0.5, 0, 1),
                  action: c.action || 'surface',
                };
              });
            }
          } catch {
            // Fall through to fallback parsing
          }
        }
      }

      // Structured fallback parsing
      if (text) {
        this.logger.info('YinObserver: attempting structured fallback parsing for critiques');
        const items = this.parseIntoItems(text);

        if (items.length >= 1) {
          return branches.map((b, idx) => {
            const item = items[idx] ?? items[0];
            const essence = String(item).split(/\n+/)[0].trim().slice(0, 200);
            const action: YinAction = /compress|trim|short|condense/i.test(item) ? 'compress' : 'surface';
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

        this.logger.info('YinObserver: falling back to raw-text critiques');
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

/**
 * Factory function to create a YinObserver instance
 *
 * @param logger - Root logger
 * @param config - Optional configuration overrides
 * @returns YinObserver instance
 */
export const createYinObserver = (logger: ILogger, config?: Partial<YinConfig>): YinObserver =>
  new YinObserver(logger, config);
