/**
 * FieldGenerator — V4: Generation Through the Field
 *
 * Closes the loop between generation and memory. The model generates
 * through its own field: retrieved engrams shape the prompt, and the
 * generated output becomes an engram that reshapes the field through
 * consolidation + potentiation feedback.
 *
 * Architecture:
 *   1. Field retrieval (kindling → engrams)
 *   2. Context assembly (engrams → augmented prompt)
 *   3. LLM generation
 *   4. Post-generation reflection (gateEmbed → field position → activated engrams)
 *   5. Storage + synaptic linking + potentiation boost
 *
 * Levels of integration:
 *   L1 (this phase): pre-retrieval context + post-generation store + feedback
 *   L2 (future): chunked mid-generation re-retrieval at sentence boundaries
 *   L3 (future): per-token hidden-state field query (requires llama.cpp callback)
 */

import type { MnemicField } from './index.js';
import type { MnemicRetrievalHit, EngramCreate } from './types.js';
import type { AttractorExtractor } from './attractor-extractor.js';
import { cosineSimilarity } from './math-utils.js';

export interface FieldGeneratorConfig {
  /** Max number of engrams retrieved from the field. */
  retrievalLimit: number;
  /** Cosine similarity threshold for marking an engram "activated" by generation. */
  activationThreshold: number;
  /** Potentiation boost applied to activated engrams. */
  activationBoost: number;
  /** Whether to store the generation as a 'generation' nodeType engram. */
  storeGeneration: boolean;
  /** Whether to check attractor basins for coarse routing before kindling. */
  useAttractorRouting: boolean;
  /** Max characters per memory card in the augmented prompt. */
  memoryCardChars: number;
}

export interface GenerateResult {
  /** The generated text. */
  generated: string;
  /** Engrams retrieved from the field (pre-generation). */
  retrievalHits: MnemicRetrievalHit[];
  /** Retrieved engrams that were "activated" (cosine > threshold with generated text). */
  activatedHits: MnemicRetrievalHit[];
  /** ID of the stored generation engram (empty if storeGeneration=false). */
  generationEngramId: string;
  /** The gateEmbed position of the generated text (for cross-modal alignment). */
  fieldPosition: number[];
  /** Attractor basin the query fell into (null if none). */
  attractorBasinId: string | null;
}

const DEFAULTS: FieldGeneratorConfig = {
  retrievalLimit: 10,
  activationThreshold: 0.60,
  activationBoost: 0.05,
  storeGeneration: true,
  useAttractorRouting: true,
  memoryCardChars: 300,
};

/** LLM provider interface — any provider that can generate text from a prompt. */
export interface LlmProvider {
  generate(prompt: string): Promise<string>;
}

export class FieldGenerator {
  private field: MnemicField;
  private provider: LlmProvider;
  private config: FieldGeneratorConfig;

  constructor(
    field: MnemicField,
    provider: LlmProvider,
    config: Partial<FieldGeneratorConfig> = {},
  ) {
    this.field = field;
    this.provider = provider;
    this.config = { ...DEFAULTS, ...config };
  }

  /**
   * Generate text through the field.
   */
  async generate(prompt: string): Promise<GenerateResult> {
    const field = this.field;
    const embedder = (field as any)._vindexEmbedder as
      | ((text: string, opts?: any) => Float32Array | null)
      | undefined;

    // 1. RETRIEVE — check attractor basins for coarse routing
    const { activationBoost, attractorBasinId } = this.tryAttractorBoost(prompt, embedder, field);

    const hits = await field.retrieve(prompt, {
      limit: this.config.retrievalLimit,
    });

    // Apply attractor basin boost if relevant
    let retrievalHits = hits;
    if (activationBoost && activationBoost.size > 0) {
      retrievalHits = hits.map(h => {
        const boost = activationBoost!.get(h.id) ?? 0;
        return boost > 0 ? { ...h, score: h.score * (1 + boost) } : h;
      }).sort((a, b) => b.score - a.score);
    }

    // 2. ASSEMBLE CONTEXT
    const augmentedPrompt = buildAugmentedPrompt(prompt, retrievalHits, this.config.memoryCardChars);

    // 3. GENERATE
    const generated = await this.provider.generate(augmentedPrompt);

    // 4. REFLECT
    let fieldPosition: number[] = [];
    const activatedHits: MnemicRetrievalHit[] = [];

    if (embedder && generated.length > 10) {
      try {
        const genPos = embedder(generated.slice(0, 1000), { minScore: 0.05 });
        if (genPos) {
          fieldPosition = Array.from(genPos);

          for (const hit of retrievalHits) {
            const hitPos = embedder(hit.content.slice(0, 500), { minScore: 0.05 });
            if (hitPos) {
              const sim = cosineSimilarity(genPos, hitPos);
              if (sim >= this.config.activationThreshold) {
                activatedHits.push({ ...hit, charge: sim });
              }
            }
          }
        }
      } catch { /* reflection is best-effort */ }
    }

    // 5. STORE
    let generationEngramId = '';

    if (this.config.storeGeneration && generated.trim().length > 0) {
      try {
        const engram = field.store({
          nodeType: 'generation',
          content: generated,
          initialPotentiation: 0.5,
          tags: ['v4_generation'],
          metadata: {
            query: prompt.slice(0, 500),
            retrievalHitCount: retrievalHits.length,
            retrievalHitIds: retrievalHits.map(h => h.id),
            activatedHitIds: activatedHits.map(h => h.id),
            activationCount: activatedHits.length,
            generatedAt: new Date().toISOString(),
            fieldPosition,
          },
          embedding: fieldPosition.length > 0
            ? new Float32Array(fieldPosition)
            : undefined,
        } as EngramCreate);

        generationEngramId = engram.id;

        // Create 'activated_by' synapses
        const cortex = field.getCortex();
        for (const hit of activatedHits) {
          try {
            cortex.createSynapse({
              fromId: generationEngramId,
              toId: hit.id,
              type: 'activated_by',
              weight: hit.charge ?? 0.7,
            } as any);
          } catch { /* best-effort synapse */ }
        }

        // Boost potentiation of activated engrams
        if (activatedHits.length > 0) {
          try {
            const updates = activatedHits.map(h => ({
              id: h.id,
              potentiation: Math.min(1, (h.potentiation ?? 0.5) + this.config.activationBoost),
            }));
            cortex.bulkUpdatePotentiation(updates);
          } catch { /* best-effort boost */ }
        }
      } catch (err) {
        (field as any).logger?.warn?.('FieldGenerator: store failed', { error: String(err) });
      }
    }

    return {
      generated,
      retrievalHits,
      activatedHits,
      generationEngramId,
      fieldPosition,
      attractorBasinId,
    };
  }

  /**
   * Try to match the query to an attractor basin and return boost weights.
   */
  private tryAttractorBoost(
    prompt: string,
    embedder: ((text: string, opts?: any) => Float32Array | null) | undefined,
    field: MnemicField,
  ): { activationBoost?: Map<string, number>; attractorBasinId: string | null } {
    if (!this.config.useAttractorRouting) return { attractorBasinId: null };
    const extractor = (field as any).__attractorExtractor as AttractorExtractor | undefined;
    if (!extractor || !embedder) return { attractorBasinId: null };

    try {
      const queryPos = embedder(prompt, { minScore: 0.05 });
      if (!queryPos) return { attractorBasinId: null };

      const attractors = extractor.getAttractors();
      for (const attr of attractors) {
        let sim = 0;
        let count = 0;
        for (const m of attr.members.slice(0, 3)) {
          const mPos = embedder(m.concept, { minScore: 0.05 });
          if (mPos) { sim += cosineSimilarity(queryPos, mPos); count++; }
        }
        if (count > 0 && sim / count > 0.65) {
          const boost = new Map<string, number>();
          const basinIds = extractor.getBasinEngramIds(attr.id);
          for (const id of basinIds) boost.set(id, 0.05);
          return { activationBoost: boost, attractorBasinId: attr.id };
        }
      }
    } catch { /* best-effort */ }
    return { attractorBasinId: null };
  }
}

/**
 * Build an augmented prompt with memory context from retrieved engrams.
 */
export function buildAugmentedPrompt(
  prompt: string,
  hits: MnemicRetrievalHit[],
  maxChars: number = 300,
): string {
  if (hits.length === 0) return prompt;

  const memoryCards: string[] = [];
  for (let i = 0; i < hits.length; i++) {
    const h = hits[i];
    const excerpt = h.content.length > maxChars
      ? h.content.slice(0, maxChars) + '...'
      : h.content;
    memoryCards.push(
      `[Memory #${i + 1} (score: ${h.score.toFixed(2)}, type: ${h.nodeType})]: ${excerpt}`,
    );
  }

  return [
    '[SYSTEM MEMORY CONTEXT]',
    'The following memories were retrieved from the Mnemic Field.',
    'Use them to inform your response if relevant.',
    '',
    ...memoryCards,
    '',
    '[USER PROMPT]',
    prompt,
  ].join('\n');
}
