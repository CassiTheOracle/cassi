/**
 * YangObserver — The Principle of Expansion
 *
 * Generates creative, divergent branches of thought.
 * Explores alternatives, edge cases, cross-domain connections, and challenges assumptions.
 */

import { getModelSpec } from '../../config/system-settings.js';

import { DialecticVoiceBase, type BaseDialecticConfig } from './dialectic-voice-base.js';
import { fillTemplate } from './prompt-optimizer.js';

import type { PromptOptimizer } from './prompt-optimizer.js';
import type { IYangObserver, YangOutput, YangContext, YangBranch } from '../../../types/dialectic.js';
import type { ILogger } from '../../../types/interfaces.js';
import type { IProvider } from '../../../types/runtime.js';





/**
 * Configuration for Yang observer
 */
export interface YangConfig extends BaseDialecticConfig {
  maxBranches: number;
  minConfidence: number;
}

/**
 * YangObserver — The Principle of Expansion
 *
 * Generates creative, divergent branches of thought.
 * Explores alternatives, edge cases, cross-domain connections, and challenges assumptions.
 */
export class YangObserver extends DialecticVoiceBase<YangConfig> implements IYangObserver {
  readonly name = 'yang' as const;

  /**
   * Create a new YangObserver instance
   *
   * @param logger - Root logger
   * @param config - Optional configuration overrides
   */
  constructor(logger: ILogger, config?: Partial<YangConfig>) {
    super(
      logger,
      {
        enabled: config?.enabled ?? true,
        model: config?.model ?? getModelSpec('reasoning'),
        temperature: config?.temperature ?? 0.7,
        maxBranches: config?.maxBranches ?? 5,
        minConfidence: config?.minConfidence ?? 0.5,
      },
      'yang',
    );
  }

  /**
   * Wire the prompt optimizer for variant selection
   *
   * Overrides base to add type-specific logging
   *
   * @param optimizer - Prompt optimizer instance
   */
  override setPromptOptimizer(optimizer: PromptOptimizer): void {
    this.promptOptimizer = optimizer;
    this.logger.info('YangObserver: prompt optimizer wired');
  }

  /**
   * Observe a user message and generate expansion branches
   *
   * @param sessionId - Session identifier
   * @param userMessage - User's message text
   * @param context - Observation context (memories, tools, etc.)
   * @param opts - Optional overrides (model, provider, etc.)
   * @returns Yang output with branches and metadata
   */
  async observe(
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
  ): Promise<YangOutput> {
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
      const targetBranches = Math.max(1, this.config.maxBranches);
      const modelSpec = opts?.model ?? this.config.model;
      const slash = modelSpec.indexOf('/');
      const modelName = slash >= 0 ? modelSpec.slice(slash + 1) : modelSpec;

      if (targetBranches <= 1) {
        const prompt = this.buildPrompt(sessionId, userMessage, context);
        const response = await this.callProvider(prompt, {
          provider: providerToUse,
          model: opts?.model,
          allowConcurrent: opts?.allowConcurrent,
          dedupe: opts?.dedupe,
          timeoutMs: 30000,
        });
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

      // Asynchronous branch generation: spawn parallel requests
      const types: YangBranch['type'][] = [
        'alternative_interpretation',
        'edge_case',
        'cross_domain',
        'what_if',
        'assumption_challenge',
      ];
      const assignedTypes = Array.from({ length: targetBranches }, (_, i) => types[i % types.length]);

      const generationTasks: Promise<YangBranch | null>[] = [];
      for (let bi = 0; bi < targetBranches; bi++) {
        const preferredType = assignedTypes[bi];
        const otherTypes = assignedTypes.filter((_, i) => i !== bi);
        const branchPrompt = this.buildBranchPrompt(
          sessionId,
          userMessage,
          context,
          bi + 1,
          targetBranches,
          preferredType,
          otherTypes,
        );
        generationTasks.push(
          (async () => {
            try {
              const resp = await this.callProvider(branchPrompt, {
                provider: providerToUse,
                model: modelName,
                allowConcurrent: true,
                dedupe: false,
                maxTokens: 400,
                timeoutMs: 30000,
              });
              const parsed = await this.parseResponse(resp, providerToUse, modelName, opts?.signal);
              if (parsed && parsed.length > 0) {
                return parsed[0];
              }
              return null;
            } catch (err) {
              try {
                this.logger?.warn?.('YangObserver: branch generation failed', {
                  index: bi + 1,
                  error: String(err),
                });
              } catch {}
              return null;
            }
          })(),
        );
      }

      const settled = await Promise.allSettled(generationTasks);
      const branches: YangBranch[] = [];
      for (const s of settled) {
        if (s.status === 'fulfilled' && s.value) branches.push(s.value);
      }

      const filtered = branches.filter(b => b.confidence >= this.config.minConfidence).slice(0, this.config.maxBranches);
      const generationTimeMs = Date.now() - startTime;

      this.logger.info('YangObserver: async expansion complete', {
        sessionId,
        branchesGenerated: branches.length,
        branchesKept: filtered.length,
        generationTimeMs,
      });

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
        error: String(error),
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

  /**
   * Build the prompt for single-call mode
   *
   * @param sessionId - Session identifier
   * @param userMessage - User's message text
   * @param context - Observation context
   * @returns Formatted prompt string
   */
  private buildPrompt(sessionId: string, userMessage: string, context: YangContext): string {
    const guideBlock = context?.taskGuide ? `TASK GUIDE:\n${context.taskGuide}\n\n` : '';

    const memoryBlock =
      context.recentMemories.length > 0
        ? `Recent conversation context:\n${context.recentMemories.map(m => `- ${m}`).join('\n')}\n\n`
        : '';

    const toolsBlock =
      context.availableTools.length > 0 ? `Available tools: ${context.availableTools.join(', ')}\n\n` : '';

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

  /**
   * Build a prompt for a single branch in parallel generation mode
   *
   * @param sessionId - Session identifier
   * @param userMessage - User's message text
   * @param context - Observation context
   * @param branchIndex - Index of this branch (1-based)
   * @param totalBranches - Total number of branches being generated
   * @param preferredType - Type lens for this branch
   * @param otherTypes - Types assigned to other branches (for diversity)
   * @returns Formatted prompt string
   */
  private buildBranchPrompt(
    sessionId: string,
    userMessage: string,
    context: YangContext,
    branchIndex: number,
    totalBranches: number,
    preferredType: YangBranch['type'],
    otherTypes: YangBranch['type'][] = [],
  ): string {
    const guideBlock = context?.taskGuide ? `TASK GUIDE:\n${context.taskGuide}\n\n` : '';
    const memoryBlock =
      context.recentMemories.length > 0
        ? `Recent context:\n${context.recentMemories.map(m => `- ${m}`).join('\n')}\n\n`
        : '';

    const otherPerspectives = [...new Set(otherTypes)].filter(t => t !== preferredType);
    const diversityNote =
      otherPerspectives.length > 0
        ? `Other perspectives being explored in parallel: ${otherPerspectives.join(', ')}. Stay distinctly within your assigned angle — do NOT overlap with or paraphrase those perspectives.\n\n`
        : '';

    return `${guideBlock}${memoryBlock}You are YANG (branch ${branchIndex}/${totalBranches}) — perspective: ${preferredType}.\n\n${diversityNote}USER MESSAGE:\n"""${userMessage}"""\n\nQUALITY GATE: Would this observation change how the AI responds to the message above? If not, skip it.\n\nGenerate ONE non-obvious observation specifically from the ${preferredType} angle.\n\nOUTPUT (JSON):\n{"id":"yang-${branchIndex}","type":"${preferredType}","content":"2-4 sentences","confidence":0.0-1.0,"noveltyScore":0.0-1.0}\n\nReturn ONLY valid JSON. No markdown fences, no explanation.`;
  }

  /**
   * Parse the provider response into Yang branches
   *
   * @param response - Provider response with text
   * @param provider - Provider for repair attempts
   * @param modelOverride - Optional model override
   * @param signal - Abort signal for cancellation
   * @returns Array of parsed branches
   */
  private async parseResponse(
    response: { text: string },
    provider?: IProvider,
    modelOverride?: string,
    signal?: AbortSignal,
  ): Promise<YangBranch[]> {
    try {
      const text = (response.text || '').trim();
      const jsonMatch = text.match(/\{[\s\S]*\}|\[[\s\S]*\]/);

      if (jsonMatch) {
        const parsed = JSON.parse(jsonMatch[0]);
        if (parsed && parsed.branches && Array.isArray(parsed.branches)) {
          return parsed.branches.map((b: any, idx: number) => ({
            id: b.id || `yang-${idx + 1}`,
            type: b.type || 'alternative_interpretation',
            content: b.content || '',
            confidence: this.clamp(b.confidence || 0.5, 0, 1),
            noveltyScore: this.clamp(b.noveltyScore || 0.5, 0, 1),
          }));
        }

        if (parsed && typeof parsed === 'object' && parsed.id && parsed.content) {
          return [
            {
              id: parsed.id || 'yang-1',
              type: parsed.type || 'alternative_interpretation',
              content: parsed.content || '',
              confidence: this.clamp(parsed.confidence || 0.5, 0, 1),
              noveltyScore: this.clamp(parsed.noveltyScore || 0.5, 0, 1),
            },
          ];
        }
      }

      // Attempt repair via Thinker
      const schema = `{\n  "id": "string",\n  "type": "alternative_interpretation|edge_case|cross_domain|what_if|assumption_challenge",\n  "content": "string",\n  "confidence": 0.0-1.0,\n  "noveltyScore": 0.0-1.0\n}`;
      const thinkerResult = await this.attemptThinkerRepair(text, schema);

      if (thinkerResult) {
        try {
          const parsed2 = JSON.parse(thinkerResult);
          if (parsed2 && parsed2.branches && Array.isArray(parsed2.branches)) {
            return parsed2.branches.map((b: any, idx: number) => ({
              id: b.id || `yang-${idx + 1}`,
              type: b.type || 'alternative_interpretation',
              content: b.content || '',
              confidence: this.clamp(b.confidence || 0.5, 0, 1),
              noveltyScore: this.clamp(b.noveltyScore || 0.5, 0, 1),
            }));
          }
          if (parsed2 && parsed2.id && parsed2.content) {
            return [
              {
                id: parsed2.id,
                type: parsed2.type || 'alternative_interpretation',
                content: parsed2.content,
                confidence: this.clamp(parsed2.confidence || 0.5, 0, 1),
                noveltyScore: this.clamp(parsed2.noveltyScore || 0.5, 0, 1),
              },
            ];
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
            if (parsed2.branches && Array.isArray(parsed2.branches)) {
              this.logger.info('YangObserver: JSON repair succeeded (provider)');
              return parsed2.branches.map((b: any, idx: number) => ({
                id: b.id || `yang-${idx + 1}`,
                type: b.type || 'alternative_interpretation',
                content: b.content || '',
                confidence: this.clamp(b.confidence || 0.5, 0, 1),
                noveltyScore: this.clamp(b.noveltyScore || 0.5, 0, 1),
              }));
            }
            if (parsed2 && parsed2.id && parsed2.content) {
              return [
                {
                  id: parsed2.id,
                  type: parsed2.type || 'alternative_interpretation',
                  content: parsed2.content,
                  confidence: this.clamp(parsed2.confidence || 0.5, 0, 1),
                  noveltyScore: this.clamp(parsed2.noveltyScore || 0.5, 0, 1),
                },
              ];
            }
          } catch {
            // Fall through to structured fallback
          }
        }
      }

      // Structured fallback parsing
      this.logger.info('YangObserver: falling back to structured parsing of plain text');
      const items = this.parseIntoItems(text);

      if (items.length > 1) {
        const types: Array<YangBranch['type']> = [
          'alternative_interpretation',
          'edge_case',
          'cross_domain',
          'what_if',
          'assumption_challenge',
        ];
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
        this.logger.info('YangObserver: falling back to single raw-text branch');
        return [
          {
            id: 'yang-1',
            type: 'alternative_interpretation',
            content: text,
            confidence: 0.6,
            noveltyScore: 0.5,
          },
        ];
      }

      this.logger.warn('YangObserver: no JSON found in response and no text to parse');
      return [];
    } catch (error) {
      this.logger.warn('YangObserver: failed to parse response', { error: String(error) });
      return [];
    }
  }
}

/**
 * Factory function to create a YangObserver instance
 *
 * @param logger - Root logger
 * @param config - Optional configuration overrides
 * @returns YangObserver instance
 */
export const createYangObserver = (logger: ILogger, config?: Partial<YangConfig>): YangObserver =>
  new YangObserver(logger, config);
