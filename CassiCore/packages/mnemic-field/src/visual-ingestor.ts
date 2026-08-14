/**
 * VisualIngestor — V5a: Multimodal Ingestion (Vision Bridge)
 *
 * Ingests images into the Mnemic Field via caption→gateEmbed→store.
 * When the native gateImage N-API binding becomes available in LARQL,
 * the caption step can be bypassed for direct visual embedding.
 *
 * Architecture:
 *   1. Accept image (path, URL, or base64 data)
 *   2. Optionally caption via vision LLM (or accept pre-computed caption)
 *   3. gateEmbed(caption) → field position in S¹⁵³⁵
 *   4. Store as visual_memory engram with image metadata
 *   5. Create visual_similar synapses to text engrams with similar descriptions
 *
 * Levels of integration:
 *   L1 (this phase): caption→gateEmbed→store
 *   L2 (future): direct gateImage when N-API exposes Gemma 4 vision encoder
 */

import type { MnemicField } from './index.js';
import type { MnemicRetrievalHit, EngramCreate } from './types.js';
import { cosineSimilarity, STRUCTURAL_NODE_TYPES, simpleHash } from './math-utils.js';

export interface VisualIngestorConfig {
  /** Whether to auto-caption images via vision LLM. */
  autoCaption: boolean;
  /** Max description chars for the caption (passed to vision LLM). */
  maxCaptionChars: number;
  /** Whether to auto-link visual memories to similar text engrams. */
  autoLink: boolean;
  /** Max number of text engrams to link via visual_similar synapses. */
  maxLinks: number;
  /** Cosine similarity threshold for creating visual_similar links. */
  linkThreshold: number;
}

export interface VisualMemoryHit {
  id: string;
  content: string;
  caption: string;
  imagePath: string;
  imageHash: string;
  potentiation: number;
  tags: string[];
  createdAt: string;
  /** Text engrams linked via visual_similar synapses. */
  linkedEngrams: string[];
}

export interface IngestResult {
  engramId: string;
  caption: string;
  fieldPosition: number[];
  linkedEngramIds: string[];
}

/** Vision provider for captioning images. */
export interface VisionProvider {
  caption(imageUrl: string, maxChars?: number): Promise<string>;
}

const DEFAULTS: VisualIngestorConfig = {
  autoCaption: true,
  maxCaptionChars: 500,
  autoLink: true,
  maxLinks: 5,
  linkThreshold: 0.55,
};

export class VisualIngestor {
  private field: MnemicField;
  private vision: VisionProvider | null;
  private config: VisualIngestorConfig;

  constructor(
    field: MnemicField,
    vision?: VisionProvider,
    config: Partial<VisualIngestorConfig> = {},
  ) {
    this.field = field;
    this.vision = vision ?? null;
    this.config = { ...DEFAULTS, ...config };
  }

  /**
   * Ingest an image into the field.
   *
   * @param imagePath — local file path, data URL, or http URL
   * @param metadata — additional metadata to store on the engram
   */
  async ingest(imagePath: string, metadata?: Record<string, unknown>): Promise<IngestResult> {
    const embedder = (this.field as any)._vindexEmbedder as
      | ((text: string, opts?: any) => Float32Array | null)
      | undefined;

    // Generate caption
    let caption = '';
    if (this.config.autoCaption) {
      if (this.vision) {
        try {
          caption = await this.vision.caption(imagePath, this.config.maxCaptionChars);
        } catch (err) {
          caption = `[image: ${imagePath.split('/').pop() ?? 'unknown'}]`;
        }
      } else {
        // No vision provider — use filename as minimal caption
        caption = `[image: ${imagePath.split('/').pop() ?? 'unknown'}]`;
      }
    }

    return this.ingestWithCaption(imagePath, caption, metadata);
  }

  /**
   * Ingest with a pre-computed caption (skip vision LLM call).
   */
  async ingestWithCaption(
    imagePath: string,
    caption: string,
    metadata?: Record<string, unknown>,
  ): Promise<IngestResult> {
    const embedder = (this.field as any)._vindexEmbedder as
      | ((text: string, opts?: any) => Float32Array | null)
      | undefined;

    // Compute field position from caption
    let fieldPosition: number[] = [];
    if (embedder && caption.length > 5) {
      try {
        const pos = embedder(caption, { minScore: 0.05 });
        if (pos) fieldPosition = Array.from(pos);
      } catch { /* best-effort */ }
    }

    // Compute simple hash for dedup detection
    const imageHash = simpleHash(imagePath);

    // Store as visual_memory engram
    const engram = this.field.store({
      nodeType: 'visual_memory',
      content: caption,
      initialPotentiation: 0.4,
      tags: ['visual', 'v5a_ingestion'],
      metadata: {
        imagePath,
        imageHash,
        caption,
        fieldPosition,
        ingestedAt: new Date().toISOString(),
        ...metadata,
      },
      embedding: fieldPosition.length > 0
        ? new Float32Array(fieldPosition)
        : undefined,
    } as EngramCreate);

    // Auto-link to similar text engrams
    const linkedEngramIds: string[] = [];
    if (this.config.autoLink && fieldPosition.length > 0) {
      try {
        const queryPos = new Float32Array(fieldPosition);
        const cortex = this.field.getCortex();

        // Get recent high-potentiation text engrams (non-visual, non-structural)
        const candidates = cortex.listEngrams(this.config.maxLinks * 5);
        const textEngrams = candidates.filter(e => {
          if (e.nodeType === 'visual_memory') return false;
          if (STRUCTURAL_NODE_TYPES.has(e.nodeType)) return false;
          return (e.potentiation ?? 0) > 0.1;
        });

        // Score by cosine similarity
        const scored: Array<{ id: string; sim: number }> = [];
        for (const e of textEngrams) {
          const ePos = embedder?.(e.content.slice(0, 500), { minScore: 0.05 });
          if (ePos) {
            const sim = cosineSimilarity(queryPos, ePos);
            if (sim >= this.config.linkThreshold) {
              scored.push({ id: e.id, sim });
            }
          }
        }
        scored.sort((a, b) => b.sim - a.sim);

        // Create visual_similar synapses
        for (let i = 0; i < Math.min(this.config.maxLinks, scored.length); i++) {
          try {
            cortex.createSynapse({
              fromId: engram.id,
              toId: scored[i].id,
              type: 'visual_similar',
              weight: scored[i].sim,
            } as any);
            linkedEngramIds.push(scored[i].id);
          } catch { /* best-effort */ }
        }
      } catch (err) {
        (this.field as any).logger?.debug?.('VisualIngestor: auto-link skipped', { error: String(err) });
      }
    }

    return {
      engramId: engram.id,
      caption,
      fieldPosition,
      linkedEngramIds,
    };
  }

  /**
   * Find visual memories similar to a text query.
   */
  async queryVisual(query: string, limit: number = 10): Promise<VisualMemoryHit[]> {
    const hits = await this.field.retrieve(query, { limit });
    const visualHits = hits.filter(h => h.nodeType === 'visual_memory');

    const cortex = this.field.getCortex();
    return visualHits.map(h => {
      const meta = h.metadata ?? {};
      return {
        id: h.id,
        content: h.content,
        caption: (meta.caption as string) ?? h.content,
        imagePath: (meta.imagePath as string) ?? '',
        imageHash: (meta.imageHash as string) ?? '',
        potentiation: h.potentiation,
        tags: h.tags,
        createdAt: (meta.ingestedAt as string) ?? '',
        linkedEngrams: [],
      };
    });
  }

  /**
   * Get a single visual memory by ID.
   */
  getVisualMemory(id: string): VisualMemoryHit | null {
    const cortex = this.field.getCortex();
    const engram = cortex.getEngram(id);
    if (!engram || engram.nodeType !== 'visual_memory') return null;

    const meta = engram.metadata ?? {};
    return {
      id: engram.id,
      content: engram.content,
      caption: (meta.caption as string) ?? engram.content,
      imagePath: (meta.imagePath as string) ?? '',
      imageHash: (meta.imageHash as string) ?? '',
      potentiation: engram.potentiation ?? 0,
      tags: engram.tags ?? [],
      createdAt: engram.createdAt ?? '',
      linkedEngrams: [],
    };
  }

  /**
   * List all visual memories (most recent first).
   */
  listVisualMemories(limit: number = 50): VisualMemoryHit[] {
    const cortex = this.field.getCortex();
    const engrams = cortex.listEngrams(limit, 'visual_memory');
    return engrams.map(e => ({
      id: e.id,
      content: e.content,
      caption: (e.metadata?.caption as string) ?? e.content,
      imagePath: (e.metadata?.imagePath as string) ?? '',
      imageHash: (e.metadata?.imageHash as string) ?? '',
      potentiation: e.potentiation ?? 0,
      tags: e.tags ?? [],
      createdAt: e.createdAt ?? '',
      linkedEngrams: [],
    }));
  }
}


