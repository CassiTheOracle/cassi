/**
 * Subconscious v2 — Types for real-time stream processing
 * 
 * The Subconscious serves as the interlay between the main agent's thought
 * stream and the rest of the CassiCore intelligence layer.
 */

import type { IEventBus, ILogger } from '../../../types/interfaces.js'
import type { IMemory } from '../../../types/intelligence.js'
import { SUBCONSCIOUS_SETTINGS, CONTEXT_SETTINGS } from '../../config/system-settings.js'

// ============================================================================
// Token Stream Processing
// ============================================================================

export interface TokenMetadata {
  timestamp: number
  model?: string
  provider?: string
}

export interface ToolCallRecord {
  id: string
  tool: string
  input: unknown
  result?: unknown
  timestamp: number
  durationMs?: number
}

export interface TokenBuffer {
  sessionId: string
  tokens: string[]
  thinking: string[]
  toolCalls: ToolCallRecord[]
  lastActivity: number
  createdAt: number

  // Buffer management
  append(token: string): void
  appendThinking(thinking: string): void
  addToolCall(tool: string, input: unknown): string
  addToolResult(callId: string, result: unknown): void
  
  // Sliding window
  trimToMaxTokens(maxTokens: number): void
  getRecentTokens(count: number): string[]
  
  // Accessors
  getText(): string
  getThinking(): string
  getRecentThinking(maxChars?: number): string
  getToolHistory(): ToolCallRecord[]
  getStats(): BufferStats
}

export interface BufferStats {
  totalTokens: number
  totalThinkingChars: number
  totalToolCalls: number
  activeToolCalls: number
  sessionDurationMs: number
}

export interface StreamIngestor {
  onToken(sessionId: string, token: string, metadata?: TokenMetadata): void
  onThinking(sessionId: string, thinking: string): void
  onToolCall(sessionId: string, tool: string, input: unknown): void
  onToolResult(sessionId: string, tool: string, result: unknown, callId?: string): void
  getBuffer(sessionId: string): TokenBuffer | undefined
  cleanupSession(sessionId: string): void
  getActiveSessions(): string[]
}

// ============================================================================
// Mental Model — Conversation Understanding
// ============================================================================

export type ConversationPhase = 
  | 'initial'       // First few turns, establishing context
  | 'clarifying'    // Asking questions, understanding requirements
  | 'executing'     // Doing the work (coding, researching, etc.)
  | 'synthesizing'  // Combining results, summarizing
  | 'concluding'    // Wrapping up, final answers

export interface UserIntent {
  type: string                    // e.g., 'code_generation', 'debugging', 'refactoring'
  description: string             // Human-readable description
  confidence: number              // 0-1
  complexity: 'simple' | 'medium' | 'complex' | 'very_complex'
  estimatedTurns?: number         // How many turns might this take?
}

export interface LoadedFile {
  path: string
  content: string
  loadedAt: number
  lastAccessed: number
}

export interface MemoryEntry {
  id: string
  content: string
  type: string
  score: number
  accessedAt: number
}

export interface TurnSummary {
  turnId: string
  phase: ConversationPhase
  userMessage: string
  assistantResponse: string
  tokensUsed: number
  toolCalls: string[]
  patterns: string[]
  timestamp: number
}

export interface Pattern {
  id: string
  type: string
  confidence: number
  evidence: string[]
  firstSeen: number
  lastSeen: number
  occurrenceCount: number
}

export interface Dependency {
  id: string
  fromTurn: string
  toTurn: string
  type: 'reference' | 'continuation' | 'correction' | 'clarification'
  description: string
}

export interface MentalModelState {
  phase: ConversationPhase
  topic: string
  intent: UserIntent
  complexity: number           // 0-1 overall complexity score
  emotionalTone: string        // e.g., 'neutral', 'frustrated', 'excited'
  confidence: number           // How confident are we in this model?
}

export interface MentalModelContext {
  loadedFiles: LoadedFile[]
  relevantMemories: MemoryEntry[]
  activeSkills: string[]
  pendingQuestions: string[]
}

export interface MentalModelTrajectory {
  turns: TurnSummary[]
  patterns: Pattern[]
  dependencies: Dependency[]
}

export interface MentalModel {
  sessionId: string
  state: MentalModelState
  context: MentalModelContext
  trajectory: MentalModelTrajectory
  lastUpdated: number

  // Update methods
  updateFromTokens(tokens: string[]): void
  updateFromThinking(thinking: string): void
  updateFromToolCall(tool: string, input: unknown): void
  updateFromToolResult(tool: string, result: unknown): void
  updateFromContext(context: EnrichedContext): void

  // Analysis methods
  detectPhase(): ConversationPhase
  detectIntent(): UserIntent
  detectPatterns(): Pattern[]
  getDependencies(): Dependency[]

  // Serialization
  toJSON(): MentalModelSnapshot
  fromJSON(snapshot: MentalModelSnapshot): void
}

export interface MentalModelSnapshot {
  sessionId: string
  state: MentalModelState
  context: MentalModelContext
  trajectory: MentalModelTrajectory
  lastUpdated: number
  version: number
}

export interface EnrichedContext {
  loadedFiles: LoadedFile[]
  relevantMemories: MemoryEntry[]
  recentHistory: string[]
  availableTools: string[]
  sessionSummary?: string
}

export interface ModelDelta {
  previous: MentalModelSnapshot
  current: MentalModelSnapshot
  changes: ModelChange[]
}

export interface ModelChange {
  path: string           // e.g., 'state.phase', 'context.activeSkills'
  oldValue: unknown
  newValue: unknown
  significance: 'low' | 'medium' | 'high' | 'critical'
}

// ============================================================================
// Signal Generation
// ============================================================================

export type SignalType = 
  | 'pattern:detected'
  | 'intent:shift'
  | 'anomaly:detected'
  | 'opportunity:present'
  | 'task:complete'
  | 'task:blocked'
  | 'task:needs_clarification'

export interface BaseSignal {
  id: string
  type: SignalType
  sessionId: string
  timestamp: number
  confidence: number
}

export interface PatternSignal extends BaseSignal {
  type: 'pattern:detected'
  pattern: string                    // e.g., 'debugging', 'refactoring', 'code_review'
  evidence: string[]                 // Supporting text snippets
  relevance: 'low' | 'medium' | 'high' | 'critical'
  suggestedAction?: string
}

export interface IntentSignal extends BaseSignal {
  type: 'intent:shift'
  from: UserIntent
  to: UserIntent
  trigger: string                    // What caused the shift
}

export interface AnomalySignal extends BaseSignal {
  type: 'anomaly:detected'
  category: 'contradiction' | 'confusion' | 'repetition' | 'error' | 'stuck'
  description: string
  severity: 'low' | 'medium' | 'high' | 'critical'
  suggestedAction?: string
  autoRecoverable?: boolean
}

export interface OpportunitySignal extends BaseSignal {
  type: 'opportunity:present'
  opportunity: string                // e.g., 'spawn_subagent', 'surface_memory', 'suggest_skill'
  payload: unknown                   // Module-specific data
  expiresAt?: number                 // Opportunity window closes
}

export interface CompletionSignal extends BaseSignal {
  type: 'task:complete' | 'task:blocked' | 'task:needs_clarification'
  taskId: string
  summary: string
  nextSteps?: string[]
  deliverables?: string[]
}

export type SubconsciousSignal = 
  | PatternSignal 
  | IntentSignal 
  | AnomalySignal 
  | OpportunitySignal 
  | CompletionSignal

export interface SignalGenerator {
  generateSignals(delta: ModelDelta): SubconsciousSignal[]
  shouldGenerateSignal(signalType: string, cooldownMs: number): boolean
  getRecentSignals(sessionId: string, count?: number): SubconsciousSignal[]
}

// ============================================================================
// Events
// ============================================================================

export interface SubconsciousEvents {
  // Stream events (real-time)
  'subconscious:token': { 
    sessionId: string
    token: string
    bufferSize: number
    timestamp: number
  }
  'subconscious:thinking': { 
    sessionId: string
    thinking: string
    timestamp: number
  }
  'subconscious:tool': { 
    sessionId: string
    tool: string
    direction: 'call' | 'result'
    timestamp: number
  }
  
  // State events (mental model updates)
  'subconscious:state:updated': { 
    sessionId: string
    state: MentalModelState
    delta: ModelDelta
    timestamp: number
  }
  'subconscious:context:enriched': { 
    sessionId: string
    context: EnrichedContext
    timestamp: number
  }
  
  // Signal events (for other modules)
  'subconscious:signal': { 
    sessionId: string
    signal: SubconsciousSignal
    timestamp: number
  }
  'subconscious:pattern': { 
    sessionId: string
    pattern: PatternSignal
    timestamp: number
  }
  'subconscious:intent': { 
    sessionId: string
    intent: IntentSignal
    timestamp: number
  }
  'subconscious:anomaly': { 
    sessionId: string
    anomaly: AnomalySignal
    timestamp: number
  }
  'subconscious:opportunity': { 
    sessionId: string
    opportunity: OpportunitySignal
    timestamp: number
  }
  
  // Buffer events
  'subconscious:buffer:updated': {
    sessionId: string
    stats: BufferStats
    timestamp: number
  }
  
  // Lifecycle events
  'subconscious:session:started': { 
    sessionId: string
    timestamp: number
  }
  'subconscious:session:ended': { 
    sessionId: string
    summary: SessionSummary
    timestamp: number
  }
  'subconscious:learning': {
    learning: SubconsciousLearning
    timestamp: number
  }
}

// ============================================================================
// Session & Learning
// ============================================================================

export interface SessionSummary {
  sessionId: string
  durationMs: number
  turnCount: number
  tokenCount: number
  finalPhase: ConversationPhase
  detectedPatterns: string[]
  keyLearnings: string[]
  outcome: 'success' | 'partial' | 'blocked' | 'abandoned'
}

export interface SubconsciousLearning {
  id: string
  type: 'pattern' | 'preference' | 'workflow' | 'insight'
  summary: string
  confidence: number
  evidence: string[]
  firstSeen: number
  lastSeen: number
  occurrenceCount: number
  metadata?: Record<string, unknown>
}

// ============================================================================
// Configuration
// ============================================================================

export interface StreamConfig {
  bufferMaxTokens: number
  slidingWindowTokens: number
  patternCheckInterval: number
}

export interface ContextConfig {
  refreshIntervalMs: number
  charBudget: number
  includeHistory: boolean
}

export interface SignalsConfig {
  enabled: boolean
  minConfidence: number
  cooldownMs: number
}

export interface MentalModelConfig {
  trackDependencies: boolean
  detectPhases: boolean
  sentimentAnalysis: boolean
}

export interface ConsolidationConfig {
  enabled: boolean
  intervalMs: number
  persistLearnings: boolean
}

export interface SubconsciousConfigV2 {
  enabled: boolean
  v2: boolean  // Feature flag for gradual rollout
  
  stream: StreamConfig
  context: ContextConfig
  signals: SignalsConfig
  mentalModel: MentalModelConfig
  consolidation: ConsolidationConfig
}

// ============================================================================
// Default Configuration
// ============================================================================

export const DEFAULT_SUBCONSCIOUS_CONFIG_V2: SubconsciousConfigV2 = {
  enabled: true,
  v2: SUBCONSCIOUS_SETTINGS.v2Enabled,
  
  stream: {
    bufferMaxTokens: SUBCONSCIOUS_SETTINGS.bufferMaxTokens,
    slidingWindowTokens: SUBCONSCIOUS_SETTINGS.slidingWindowTokens,
    patternCheckInterval: SUBCONSCIOUS_SETTINGS.patternCheckInterval,
  },
  
  context: {
    refreshIntervalMs: CONTEXT_SETTINGS.contextRefreshIntervalMs,
    charBudget: CONTEXT_SETTINGS.subconsciousContextBudget,
    includeHistory: true,
  },
  
  signals: {
    enabled: true,
    minConfidence: SUBCONSCIOUS_SETTINGS.signalMinConfidence,
    cooldownMs: SUBCONSCIOUS_SETTINGS.signalCooldownMs,
  },
  
  mentalModel: {
    trackDependencies: SUBCONSCIOUS_SETTINGS.trackDependencies,
    detectPhases: SUBCONSCIOUS_SETTINGS.detectPhases,
    sentimentAnalysis: false,
  },
  
  consolidation: {
    enabled: true,
    intervalMs: SUBCONSCIOUS_SETTINGS.consolidationIntervalMs,
    persistLearnings: true,
  },
}

// ============================================================================
// Utility Types
// ============================================================================

export type SubconsciousEventBus = Pick<IEventBus, 'emit' | 'on'>

export interface SubconsciousDependencies {
  logger: ILogger
  eventBus?: SubconsciousEventBus
  memory?: IMemory
}
