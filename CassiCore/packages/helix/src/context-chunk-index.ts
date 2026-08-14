/**
 * ContextChunkIndex — Addressable, scorable chunk store for LLM context.
 *
 * Treats the messages[] array like a database page store — broken into
 * addressable, scorable chunks that brainstems/corpus can explicitly
 * select to retain or evict, giving fine-grained control over what
 * each posture "remembers".
 *
 * Integration points:
 *   - SessionIndexer: reuses classifyParagraph() for tagging
 *   - IntelligentContextWindow: chunks exempt from ICW trimming when pinned
 *   - Brainstem: scores chunks, issues pin/evict/boost directives
 *   - Corpus: emits context_edit directives for cross-Helix coordination
 */

import type { ILogger } from '@cassicore/foundation'
import type { Message, ContentBlock } from '@cassicore/foundation'
import { estimateTokens } from './vendor/core/intelligence/shared/token-estimation.js'

// classifyParagraph imported below for chunk tagging


/** Block types that can appear in message content */
export type BlockType = 'text' | 'tool_use' | 'tool_result'

/** Valid roles for context chunks */
export type ChunkRole = 'user' | 'assistant' | 'system'

/**
 * A single addressable chunk of context.
 * Chunks are derived from message blocks and paragraphs (for text blocks).
 */
export interface ContextChunk {
  /** Stable ID: C{msgIdx}.B{blockIdx}[.P{paraIdx}] */
  id: string
  /** Source message index in the messages array */
  msgIdx: number
  /** Block index within the message */
  blockIdx: number
  /** Paragraph index within text block (undefined for non-text blocks) */
  paraIdx?: number
  /** Message role */
  role: ChunkRole
  /** Type of content block */
  blockType: BlockType
  /** Character count of this chunk */
  charCount: number
  /** Tags from classifyParagraph() or heuristic classification */
  tags: string[]
  /** Preview text (first ~200 chars) */
  preview: string
  /** Relevance score 0-1, assigned by brainstem */
  relevanceScore: number
  /** Recency score 0-1, auto-decayed by iteration count */
  recencyScore: number
  /** If true, never evicted (system prompt, tail anchor, explicitly pinned) */
  pinned: boolean
  /** If true, pending removal (applied lazily in batch) */
  evicted: boolean
  /** Last iteration this chunk was referenced */
  lastReferencedAt: number
  /** Iteration when this chunk was created */
  createdAtIteration: number
}

/**
 * Compact snapshot of the chunk index for brainstem LLM consumption.
 * Omits full content to stay within token budget.
 */
export interface ChunkIndexSnapshot {
  /** Total chunks indexed */
  totalChunks: number
  /** Total characters across all chunks */
  totalChars: number
  /** Number of pinned chunks */
  pinnedCount: number
  /** Number of evicted chunks (pending removal) */
  evictedCount: number
  /** Current iteration number */
  currentIteration: number
  /** Character budget from ContextBudgetCoordinator */
  charBudget: number
  /** Chunks that would be evicted by a greedy trim (lowest scores) */
  atRiskChunks: ChunkSummary[]
  /** Recently referenced chunks (last 3 iterations) */
  hotChunks: ChunkSummary[]
  /** Chunks grouped by tag for pattern analysis */
  tagSummary: Record<string, number>
}

/** Minimal chunk info for snapshots */
export interface ChunkSummary {
  id: string
  role: ChunkRole
  blockType: BlockType
  charCount: number
  tags: string[]
  relevanceScore: number
  recencyScore: number
  pinned: boolean
  preview: string
}

/** Gap marker inserted when chunks are evicted */
export interface GapMarker {
  /** Type discriminator */
  type: 'gap'
  /** Chunk IDs that were evicted */
  evictedChunkIds: string[]
  /** Human-readable summary */
  summary: string
  /** Character count of evicted content */
  charCount: number
}

/** Decision logged to shadow store */
export interface ChunkDecision {
  /** Unique decision ID */
  id: string
  /** Action taken */
  action: 'pin' | 'unpin' | 'evict' | 'boost'
  /** Target chunk IDs */
  chunkIds: string[]
  /** Optional tag filter used */
  tagsFilter?: string[]
  /** Reason for the decision */
  reason: string
  /** Character count affected */
  charCount: number
  /** Iteration when decided */
  iteration: number
  /** Who/what made the decision ('brainstem', 'corpus', 'auto') */
  decidedBy: string
  /** Timestamp */
  timestamp: number
}

/** Configuration for ContextChunkIndex */
export interface ChunkIndexConfig {
  /** Preview length in characters. Default: 200 */
  previewLength: number
  /** Recency decay rate per iteration. Default: 0.95 */
  recencyDecayRate: number
  /** Minimum recency score. Default: 0.1 */
  minRecencyScore: number
  /** Number of tail messages to auto-pin. Default: 3 */
  tailAnchorSize: number
  /** Boost amount for relevance score. Default: 0.2 */
  boostAmount: number
}

export const DEFAULT_CHUNK_INDEX_CONFIG: ChunkIndexConfig = {
  previewLength: 200,
  recencyDecayRate: 0.95,
  minRecencyScore: 0.1,
  tailAnchorSize: 3,
  boostAmount: 0.2,
}


/**
 * Heuristic classifier for non-text blocks.
 * Returns tags based on block type and content patterns.
 */
function classifyBlock(block: ContentBlock): string[] {
  const tags: string[] = []

  if (block.type === 'tool_use') {
    tags.push('tool-use')
    if (block.name) {
      tags.push(`tool:${block.name}`)
    }
  } else if (block.type === 'tool_result') {
    tags.push('tool-result')
    if (block.tool_use_id) {
      tags.push('tool-output')
    }
    // Check for error indicators in content
    const content = typeof block.content === 'string'
      ? block.content
      : JSON.stringify(block.content)
    if (/\b(error|exception|failed|failure)\b/i.test(content)) {
      tags.push('error')
    }
  }

  return tags
}

/**
 * Split text into paragraphs on double-newline boundaries.
 * Empty paragraphs are skipped.
 * @dep callers: indexMessage (core/intelligence/helix/context-chunk-index.ts), indexContentBlock (core/intelligence/helix/context-chunk-index.ts), buildRemainingText (core/intelligence/helix/context-chunk-index.ts)
 * @dep module: Helix
 * @dep risk: LOW | 3 callers, 0 flows, 1 module
 */
function splitParagraphs(text: string): string[] {
  return text
    .split(/\n\n+/)
    .map(p => p.trim())
    .filter(p => p.length > 0)
}

/**
 * Import classifyParagraph from session-indexer for text classification.
 * We re-declare here to avoid circular imports at type level.
 */
/**
 * classifyParagraph used to live in core/intelligence/memory/session-indexer.ts
 * but that module was a no-op stub returning []. Replaced with a local no-op
 * to preserve behavior while removing the dead dependency.
 */
function classifyTextParagraph(_text: string): string[] {
  return []
}

/**
 * Generate a stable chunk ID from indices.
 * Format: C{msgIdx}.B{blockIdx}[.P{paraIdx}]
 */
function generateChunkId(msgIdx: number, blockIdx: number, paraIdx?: number): string {
  if (paraIdx !== undefined) {
    return `C${msgIdx}.B${blockIdx}.P${paraIdx}`
  }
  return `C${msgIdx}.B${blockIdx}`
}

/**
 * Parse a chunk ID into its component indices.
 * Returns null if malformed.
 */
function parseChunkId(id: string): { msgIdx: number; blockIdx: number; paraIdx?: number } | null {
  const match = id.match(/^C(\d+)\.B(\d+)(?:\.P(\d+))?$/)
  if (!match) return null
  return {
    msgIdx: parseInt(match[1], 10),
    blockIdx: parseInt(match[2], 10),
    paraIdx: match[3] ? parseInt(match[3], 10) : undefined,
  }
}


export class ContextChunkIndex {
  private logger: ILogger
  private config: ChunkIndexConfig
  private chunks: Map<string, ContextChunk> = new Map()
  private currentIteration: number = 0
  private lastIndexedMsgIdx: number = -1
  private charBudget: number = 24_000 // Default, updated by coordinator

  constructor(logger: ILogger, config: Partial<ChunkIndexConfig> = {}) {
    this.logger = logger.child?.('chunk-index') ?? logger
    this.config = { ...DEFAULT_CHUNK_INDEX_CONFIG, ...config }
  }


  /**
   * Update the character budget from ContextBudgetCoordinator.
   */
  setCharBudget(budget: number): void {
    this.charBudget = budget
    this.logger.debug('Updated character budget', { budget })
  }

  /**
   * Get the current character budget.
   */
  getCharBudget(): number {
    return this.charBudget
  }


  /**
   * Add a synthetic (non-message-backed) chunk to the index.
   * Used by brainstem/corpus to inject file content or other context
   * directly into the posture's awareness. Synthetic chunks are rendered
   * into messages by applyEvictions() if not evicted.
   */
  addSyntheticChunk(opts: {
    id: string
    content: string
    role: ChunkRole
    tags?: string[]
    pinned?: boolean
  }): void {
    const chunk: ContextChunk = {
      id: opts.id,
      msgIdx: -1, // Synthetic — not tied to a message index
      blockIdx: 0,
      paraIdx: undefined,
      role: opts.role,
      blockType: 'text',
      charCount: opts.content.length,
      tags: [...(opts.tags ?? []), 'synthetic'],
      preview: opts.content.slice(0, this.config.previewLength),
      relevanceScore: 0.8, // Higher default — injected content is intentional
      recencyScore: 1.0,
      pinned: opts.pinned ?? false,
      evicted: false,
      lastReferencedAt: this.currentIteration,
      createdAtIteration: this.currentIteration,
    }

    // Store the full content for rendering into messages
    ;(chunk as any)._syntheticContent = opts.content

    this.chunks.set(opts.id, chunk)
    this.logger.debug('Added synthetic chunk', {
      id: opts.id,
      chars: opts.content.length,
      pinned: chunk.pinned,
    })
  }

  /**
   * Incrementally index messages starting from lastIndexedMsgIdx.
   * Splits text blocks into paragraphs for fine-grained addressing.
   */
  indexMessages(messages: Message[], fromIdx?: number): void {
    const startIdx = fromIdx ?? (this.lastIndexedMsgIdx + 1)

    if (startIdx >= messages.length) {
      return // Nothing new to index
    }

    this.logger.debug(
      'Indexing messages',
      { startIdx, count: messages.length - startIdx }
    )

    for (let msgIdx = startIdx; msgIdx < messages.length; msgIdx++) {
      const msg = messages[msgIdx]
      this.indexMessage(msg, msgIdx)
    }

    this.lastIndexedMsgIdx = messages.length - 1

    // Auto-pin system prompt (first message if system) and tail anchor
    this.applyAutoPinning(messages)
  }

  /**
   * Index a single message, breaking it into chunks.
   */
  private indexMessage(msg: Message, msgIdx: number): void {
    const role = msg.role as ChunkRole
    const content = msg.content

    // Handle string content (simple text message)
    if (typeof content === 'string') {
      const paragraphs = splitParagraphs(content)
      if (paragraphs.length === 0) {
        // Empty text - create a single empty chunk
        this.createChunk(msgIdx, 0, undefined, role, 'text', '', 0)
      } else {
        paragraphs.forEach((para, paraIdx) => {
          this.createChunk(msgIdx, 0, paraIdx, role, 'text', para, paraIdx)
        })
      }
      return
    }

    // Handle array of content blocks
    if (Array.isArray(content)) {
      content.forEach((block, blockIdx) => {
        this.indexContentBlock(block, msgIdx, blockIdx, role)
      })
    }
  }

  /**
   * Index a single content block, splitting text blocks into paragraphs.
   */
  private indexContentBlock(
    block: ContentBlock,
    msgIdx: number,
    blockIdx: number,
    role: ChunkRole
  ): void {
    if (block.type === 'text') {
      const text = block.text || ''
      const paragraphs = splitParagraphs(text)

      if (paragraphs.length === 0) {
        // Empty text block
        this.createChunk(msgIdx, blockIdx, undefined, role, 'text', '', 0)
      } else if (paragraphs.length === 1) {
        // Single paragraph - no need to split
        this.createChunk(msgIdx, blockIdx, undefined, role, 'text', paragraphs[0]!, 0)
      } else {
        // Multiple paragraphs - create sub-chunks
        paragraphs.forEach((para, paraIdx) => {
          this.createChunk(msgIdx, blockIdx, paraIdx, role, 'text', para, paraIdx)
        })
      }
    } else if (block.type === 'tool_use') {
      const text = block.input
        ? JSON.stringify(block.input)
        : `(tool: ${block.name || 'unknown'})`
      this.createChunk(msgIdx, blockIdx, undefined, role, 'tool_use', text, 0)
    } else if (block.type === 'tool_result') {
      const text = typeof block.content === 'string'
        ? block.content
        : JSON.stringify(block.content)
      this.createChunk(msgIdx, blockIdx, undefined, role, 'tool_result', text, 0)
    }
  }

  /**
   * Create a ContextChunk and add to the index.
   */
  private createChunk(
    msgIdx: number,
    blockIdx: number,
    paraIdx: number | undefined,
    role: ChunkRole,
    blockType: BlockType,
    content: string,
    paraPosition: number
  ): ContextChunk {
    const id = generateChunkId(msgIdx, blockIdx, paraIdx)

    // Generate tags based on content type
    let tags: string[] = []
    if (blockType === 'text') {
      tags = classifyTextParagraph(content)
    } else {
      // For non-text blocks, classify using the block's structural cues
      tags = classifyBlock(
        blockType === 'tool_use'
          ? { type: 'tool_use' as const, id: `tool-${id}`, name: 'unknown', input: {} }
          : { type: 'tool_result' as const, tool_use_id: `tool-${id}`, content }
      )
    }

    // Add role-based tag
    tags.push(`role:${role}`)

    const chunk: ContextChunk = {
      id,
      msgIdx,
      blockIdx,
      paraIdx,
      role,
      blockType,
      charCount: content.length,
      tags,
      preview: content.slice(0, this.config.previewLength),
      relevanceScore: 0.5, // Neutral starting score
      recencyScore: 1.0,   // New chunks start at max recency
      pinned: false,
      evicted: false,
      lastReferencedAt: this.currentIteration,
      createdAtIteration: this.currentIteration,
    }

    this.chunks.set(id, chunk)
    return chunk
  }

  /**
   * Auto-pin system prompt (first message if role=system) and tail anchor messages.
   */
  private applyAutoPinning(messages: Message[]): void {
    const tailAnchorSize = this.config.tailAnchorSize

    for (const chunk of this.chunks.values()) {
      // Pin system prompt (first message if role is system)
      if (chunk.msgIdx === 0 && chunk.role === 'system') {
        chunk.pinned = true
      }

      // Pin tail anchor (last N messages)
      const tailStartIdx = Math.max(0, messages.length - tailAnchorSize)
      if (chunk.msgIdx >= tailStartIdx) {
        chunk.pinned = true
      }
    }
  }


  /**
   * Advance to the next iteration and apply recency decay.
   */
  nextIteration(): void {
    this.currentIteration++

    for (const chunk of this.chunks.values()) {
      if (!chunk.pinned && !chunk.evicted) {
        // Apply exponential decay to recency score
        chunk.recencyScore = Math.max(
          this.config.minRecencyScore,
          chunk.recencyScore * this.config.recencyDecayRate
        )
      }
    }

    this.logger.debug('Advanced iteration', { iteration: this.currentIteration })
  }

  /**
   * Get the current iteration number.
   */
  getCurrentIteration(): number {
    return this.currentIteration
  }

  /**
   * Reference chunks by ID, updating their lastReferencedAt and boosting recency.
   */
  referenceChunks(chunkIds: string[]): void {
    for (const id of chunkIds) {
      const chunk = this.chunks.get(id)
      if (chunk && !chunk.evicted) {
        chunk.lastReferencedAt = this.currentIteration
        // Slight boost to recency on reference
        chunk.recencyScore = Math.min(1.0, chunk.recencyScore + 0.05)
      }
    }
  }


  /**
   * Pin chunks by ID - prevents eviction.
   */
  pin(chunkIds: string[]): ChunkDecision {
    let charCount = 0
    const affectedIds: string[] = []

    for (const id of chunkIds) {
      const chunk = this.chunks.get(id)
      if (chunk && !chunk.pinned && !chunk.evicted) {
        chunk.pinned = true
        charCount += chunk.charCount
        affectedIds.push(id)
      }
    }

    const decision: ChunkDecision = {
      id: `dec-${Date.now()}-pin`,
      action: 'pin',
      chunkIds: affectedIds,
      reason: 'Explicit pin by brainstem/corpus',
      charCount,
      iteration: this.currentIteration,
      decidedBy: 'brainstem',
      timestamp: Date.now(),
    }

    this.logger.debug('Pinned chunks', { count: affectedIds.length, charCount })
    return decision
  }

  /**
   * Unpin chunks by ID - allows eviction.
   */
  unpin(chunkIds: string[]): ChunkDecision {
    let charCount = 0
    const affectedIds: string[] = []

    for (const id of chunkIds) {
      const chunk = this.chunks.get(id)
      if (chunk && chunk.pinned && !chunk.evicted) {
        // Don't unpin system prompt or tail anchor
        if (this.isAutoPinned(chunk)) {
          continue
        }
        chunk.pinned = false
        charCount += chunk.charCount
        affectedIds.push(id)
      }
    }

    const decision: ChunkDecision = {
      id: `dec-${Date.now()}-unpin`,
      action: 'unpin',
      chunkIds: affectedIds,
      reason: 'Explicit unpin by brainstem/corpus',
      charCount,
      iteration: this.currentIteration,
      decidedBy: 'brainstem',
      timestamp: Date.now(),
    }

    this.logger.debug('Unpinned chunks', { count: affectedIds.length, charCount })
    return decision
  }

  /**
   * Mark chunks for eviction (lazy - applied in batch).
   */
  evict(chunkIds: string[]): ChunkDecision {
    let charCount = 0
    const affectedIds: string[] = []

    for (const id of chunkIds) {
      const chunk = this.chunks.get(id)
      if (chunk && !chunk.pinned && !chunk.evicted) {
        chunk.evicted = true
        charCount += chunk.charCount
        affectedIds.push(id)
      }
    }

    const decision: ChunkDecision = {
      id: `dec-${Date.now()}-evict`,
      action: 'evict',
      chunkIds: affectedIds,
      reason: 'Explicit eviction by brainstem/corpus',
      charCount,
      iteration: this.currentIteration,
      decidedBy: 'brainstem',
      timestamp: Date.now(),
    }

    this.logger.debug('Evicted chunks', { count: affectedIds.length, charCount })
    return decision
  }

  /**
   * Boost relevance score of chunks.
   */
  boost(chunkIds: string[], amount: number = this.config.boostAmount): ChunkDecision {
    let charCount = 0
    const affectedIds: string[] = []

    for (const id of chunkIds) {
      const chunk = this.chunks.get(id)
      if (chunk && !chunk.evicted) {
        chunk.relevanceScore = Math.min(1.0, chunk.relevanceScore + amount)
        charCount += chunk.charCount
        affectedIds.push(id)
      }
    }

    const decision: ChunkDecision = {
      id: `dec-${Date.now()}-boost`,
      action: 'boost',
      chunkIds: affectedIds,
      reason: `Relevance boost by ${amount}`,
      charCount,
      iteration: this.currentIteration,
      decidedBy: 'brainstem',
      timestamp: Date.now(),
    }

    this.logger.debug('Boosted chunks', { count: affectedIds.length, amount })
    return decision
  }

  /**
   * Pin all chunks matching tag filter.
   */
  pinByTags(tags: string[]): ChunkDecision {
    const matchingIds: string[] = []

    for (const chunk of this.chunks.values()) {
      if (!chunk.pinned && !chunk.evicted && tags.some(t => chunk.tags.includes(t))) {
        matchingIds.push(chunk.id)
      }
    }

    const decision = this.pin(matchingIds)
    decision.tagsFilter = tags
    decision.reason = `Pin by tags: ${tags.join(', ')}`
    return decision
  }

  /**
   * Evict all chunks matching tag filter.
   */
  evictByTags(tags: string[]): ChunkDecision {
    const matchingIds: string[] = []

    for (const chunk of this.chunks.values()) {
      if (!chunk.pinned && !chunk.evicted && tags.some(t => chunk.tags.includes(t))) {
        matchingIds.push(chunk.id)
      }
    }

    const decision = this.evict(matchingIds)
    decision.tagsFilter = tags
    decision.reason = `Evict by tags: ${tags.join(', ')}`
    return decision
  }

  /**
   * Check if a chunk is auto-pinned (system prompt or tail anchor).
   */
  private isAutoPinned(chunk: ContextChunk): boolean {
    // System prompt is msgIdx 0 with role system
    if (chunk.msgIdx === 0 && chunk.role === 'system') {
      return true
    }
    return false
  }


  /**
   * Get a chunk by ID.
   */
  getChunk(id: string): ContextChunk | undefined {
    return this.chunks.get(id)
  }

  /**
   * Get all chunks for a message.
   */
  getChunksForMessage(msgIdx: number): ContextChunk[] {
    return Array.from(this.chunks.values())
      .filter(c => c.msgIdx === msgIdx)
      .sort((a, b) => {
        if (a.blockIdx !== b.blockIdx) return a.blockIdx - b.blockIdx
        if (a.paraIdx !== undefined && b.paraIdx !== undefined) {
          return a.paraIdx - b.paraIdx
        }
        return 0
      })
  }

  /**
   * Get all chunks.
   */
  getAllChunks(): ContextChunk[] {
    return Array.from(this.chunks.values())
  }

  /**
   * Get chunks by tag.
   */
  getChunksByTag(tag: string): ContextChunk[] {
    return Array.from(this.chunks.values()).filter(c => c.tags.includes(tag))
  }

  /**
   * Get total retained character count.
   */
  getRetainedChars(): number {
    return Array.from(this.chunks.values())
      .filter(c => !c.evicted)
      .reduce((sum, c) => sum + c.charCount, 0)
  }

  /**
   * Get total evicted character count.
   */
  getEvictedChars(): number {
    return Array.from(this.chunks.values())
      .filter(c => c.evicted)
      .reduce((sum, c) => sum + c.charCount, 0)
  }

  /**
   * Get count of pinned chunks.
   */
  getPinnedCount(): number {
    return Array.from(this.chunks.values()).filter(c => c.pinned && !c.evicted).length
  }


  /**
   * Create a compact snapshot for brainstem LLM consumption.
   */
  snapshot(): ChunkIndexSnapshot {
    const allChunks = Array.from(this.chunks.values()).filter(c => !c.evicted)
    const sortedByScore = [...allChunks].sort((a, b) => {
      const scoreA = a.relevanceScore * a.recencyScore
      const scoreB = b.relevanceScore * b.recencyScore
      return scoreA - scoreB // Lowest first (at risk)
    })

    // At-risk: lowest 20% or bottom 10, whichever is larger
    const atRiskCount = Math.max(10, Math.floor(allChunks.length * 0.2))
    const atRiskChunks = sortedByScore.slice(0, atRiskCount).map(c => this.toChunkSummary(c))

    // Hot chunks: referenced in last 3 iterations
    const hotChunks = allChunks
      .filter(c => this.currentIteration - c.lastReferencedAt <= 3)
      .map(c => this.toChunkSummary(c))

    // Tag summary
    const tagSummary: Record<string, number> = {}
    for (const chunk of allChunks) {
      for (const tag of chunk.tags) {
        tagSummary[tag] = (tagSummary[tag] || 0) + 1
      }
    }

    return {
      totalChunks: allChunks.length,
      totalChars: this.getRetainedChars(),
      pinnedCount: this.getPinnedCount(),
      evictedCount: Array.from(this.chunks.values()).filter(c => c.evicted).length,
      currentIteration: this.currentIteration,
      charBudget: this.charBudget,
      atRiskChunks,
      hotChunks,
      tagSummary,
    }
  }

  /**
   * Convert a ContextChunk to ChunkSummary.
   */
  private toChunkSummary(chunk: ContextChunk): ChunkSummary {
    return {
      id: chunk.id,
      role: chunk.role,
      blockType: chunk.blockType,
      charCount: chunk.charCount,
      tags: chunk.tags,
      relevanceScore: chunk.relevanceScore,
      recencyScore: chunk.recencyScore,
      pinned: chunk.pinned,
      preview: chunk.preview,
    }
  }


  /**
   * Apply pending evictions to messages array.
   * Replaces evicted paragraphs with gap markers.
   * Returns new messages array (may share structure with input).
   */
  applyEvictions(messages: Message[]): Message[] {
    const evictedChunks = Array.from(this.chunks.values()).filter(c => c.evicted)
    if (evictedChunks.length === 0) {
      return messages
    }

    this.logger.info(
      'Applying evictions',
      { evictedCount: evictedChunks.length, evictedChars: this.getEvictedChars() }
    )

    // Group evicted chunks by message index
    const byMessage = new Map<number, ContextChunk[]>()
    for (const chunk of evictedChunks) {
      const list = byMessage.get(chunk.msgIdx) || []
      list.push(chunk)
      byMessage.set(chunk.msgIdx, list)
    }

    // Process each message that has evicted chunks
    const result: Message[] = []
    for (let msgIdx = 0; msgIdx < messages.length; msgIdx++) {
      const msg = messages[msgIdx]
      const evicted = byMessage.get(msgIdx)

      if (!evicted || evicted.length === 0) {
        // No evictions for this message
        result.push(msg)
        continue
      }

      // Rebuild message with gap markers
      const newMsg = this.rebuildMessageWithGaps(msg, evicted, msgIdx)
      result.push(newMsg)
    }

    // Clear evicted chunks from index after application
    for (const chunk of evictedChunks) {
      this.chunks.delete(chunk.id)
    }

    return result
  }

  /**
   * Rebuild a message, replacing evicted chunks with gap markers.
   */
  private rebuildMessageWithGaps(
    msg: Message,
    evictedChunks: ContextChunk[],
    msgIdx: number
  ): Message {
    // Group evicted chunks by block
    const byBlock = new Map<number, ContextChunk[]>()
    for (const chunk of evictedChunks) {
      const list = byBlock.get(chunk.blockIdx) || []
      list.push(chunk)
      byBlock.set(chunk.blockIdx, list)
    }

    // If message has string content, convert to text block first
    if (typeof msg.content === 'string') {
      const evictedParas = byBlock.get(0) || []
      if (evictedParas.length === 0) {
        return msg // Nothing evicted from this message
      }

      // Build gap marker
      const gapText = this.buildGapMarker(evictedParas, msgIdx)
      const remainingText = this.buildRemainingText(msg.content, evictedParas)

      if (remainingText.length === 0) {
        // All content evicted - just gap marker
        return {
          ...msg,
          content: gapText,
        }
      }

      // Gap marker + remaining content
      return {
        ...msg,
        content: `${gapText}\n\n${remainingText}`,
      }
    }

    // Handle array content
    if (!Array.isArray(msg.content)) {
      return msg
    }

    const newContent: ContentBlock[] = []
    for (let blockIdx = 0; blockIdx < msg.content.length; blockIdx++) {
      const block = msg.content[blockIdx]
      const evictedFromBlock = byBlock.get(blockIdx)

      if (!evictedFromBlock || evictedFromBlock.length === 0) {
        // No evictions from this block
        newContent.push(block)
        continue
      }

      if (block.type === 'text') {
        const gapText = this.buildGapMarker(evictedFromBlock, msgIdx)
        const remainingText = this.buildRemainingText(block.text || '', evictedFromBlock)

        if (remainingText.length > 0) {
          newContent.push({
            type: 'text',
            text: `${gapText}\n\n${remainingText}`,
          })
        } else {
          newContent.push({
            type: 'text',
            text: gapText,
          })
        }
      } else {
        // Non-text blocks - replace with gap marker
        const gapText = this.buildGapMarker(evictedFromBlock, msgIdx)
        newContent.push({
          type: 'text',
          text: gapText,
        })
      }
    }

    return {
      ...msg,
      content: newContent,
    }
  }

  /**
   * Build a human-readable gap marker for evicted chunks.
   */
  private buildGapMarker(chunks: ContextChunk[], msgIdx: number): string {
    const sortedChunks = [...chunks].sort((a, b) => {
      if (a.blockIdx !== b.blockIdx) return a.blockIdx - b.blockIdx
      if (a.paraIdx !== undefined && b.paraIdx !== undefined) {
        return a.paraIdx - b.paraIdx
      }
      return 0
    })

    const chunkIds = sortedChunks.map(c => c.id)
    const totalChars = sortedChunks.reduce((sum, c) => sum + c.charCount, 0)

    // Build range description
    const firstChunk = sortedChunks[0]!
    const lastChunk = sortedChunks[sortedChunks.length - 1]!

    let rangeDesc: string
    if (firstChunk.id === lastChunk.id) {
      rangeDesc = firstChunk.id
    } else if (firstChunk.blockIdx === lastChunk.blockIdx) {
      // Same block, different paragraphs
      rangeDesc = `${firstChunk.id}-${lastChunk.paraIdx ?? 'B' + lastChunk.blockIdx}`
    } else {
      // Different blocks
      rangeDesc = `${firstChunk.id} to ${lastChunk.id}`
    }

    // Count paragraphs if applicable
    const paraCount = sortedChunks.filter(c => c.paraIdx !== undefined).length
    const paraDesc = paraCount > 0 ? ` — ${paraCount} paragraphs` : ''

    return `[evicted: ${rangeDesc}${paraDesc}, ~${totalChars} chars]`
  }

  /**
   * Build remaining text after removing evicted paragraphs.
   */
  private buildRemainingText(fullText: string, evictedChunks: ContextChunk[]): string {
    const paragraphs = splitParagraphs(fullText)
    const evictedParaIndices = new Set(
      evictedChunks
        .filter(c => c.paraIdx !== undefined)
        .map(c => c.paraIdx!)
    )

    return paragraphs
      .filter((_, idx) => !evictedParaIndices.has(idx))
      .join('\n\n')
  }


  /**
   * Clear all chunks (for testing or reset).
   */
  clear(): void {
    this.chunks.clear()
    this.lastIndexedMsgIdx = -1
    this.currentIteration = 0
    this.logger.debug('Cleared all chunks')
  }

  /**
   * Get index statistics.
   */
  getStats(): {
    totalChunks: number
    retainedChunks: number
    evictedChunks: number
    pinnedChunks: number
    retainedChars: number
    evictedChars: number
    currentIteration: number
  } {
    const all = Array.from(this.chunks.values())
    const retained = all.filter(c => !c.evicted)
    const evicted = all.filter(c => c.evicted)
    const pinned = retained.filter(c => c.pinned)

    return {
      totalChunks: all.length,
      retainedChunks: retained.length,
      evictedChunks: evicted.length,
      pinnedChunks: pinned.length,
      retainedChars: this.getRetainedChars(),
      evictedChars: this.getEvictedChars(),
      currentIteration: this.currentIteration,
    }
  }
}


export type { ContentBlock }
