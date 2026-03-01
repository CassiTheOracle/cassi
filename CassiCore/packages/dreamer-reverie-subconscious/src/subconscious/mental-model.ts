/**
 * MentalModel — Evolving conversation understanding
 *
 * Maintains an incremental model of the conversation state, including
 * detected phase, user intent, active context, and conversation trajectory.
 * Updates in real-time as tokens and thinking arrive.
 */

import type { ILogger } from '../../../types/interfaces.js'
import type {
  MentalModel as IMentalModel,
  MentalModelState,
  MentalModelContext,
  MentalModelTrajectory,
  MentalModelSnapshot,
  ConversationPhase,
  UserIntent,
  Pattern,
  Dependency,
  TurnSummary,
  LoadedFile,
  MemoryEntry,
  EnrichedContext,
  ModelDelta,
  ModelChange,
} from './types.js'

// ============================================================================
// Pattern Detection Patterns
// ============================================================================

const PATTERN_DEFINITIONS = [
  {
    id: 'debugging',
    keywords: ['debug', 'error', 'exception', 'failed', 'crash', 'stack trace', 'breakpoint'],
    confidence: 0.8,
  },
  {
    id: 'refactoring',
    keywords: ['refactor', 'rewrite', 'restructure', 'simplify', 'clean up', 'extract'],
    confidence: 0.75,
  },
  {
    id: 'code_generation',
    keywords: ['implement', 'create', 'write', 'generate', 'add', 'build', 'function', 'class'],
    confidence: 0.7,
  },
  {
    id: 'code_review',
    keywords: ['review', 'check', 'looks good', 'lgmt', 'nitpick', 'suggestion'],
    confidence: 0.75,
  },
  {
    id: 'architecture',
    keywords: ['architecture', 'design pattern', 'structure', 'module', 'component', 'system'],
    confidence: 0.8,
  },
  {
    id: 'testing',
    keywords: ['test', 'spec', 'assert', 'jest', 'mocha', 'vitest', 'coverage'],
    confidence: 0.8,
  },
  {
    id: 'documentation',
    keywords: ['document', 'readme', 'comment', 'explain', 'clarify', 'docstring'],
    confidence: 0.75,
  },
  {
    id: 'configuration',
    keywords: ['config', 'setting', 'environment', 'env', 'json', 'yaml', 'toml'],
    confidence: 0.7,
  },
]

const INTENT_PATTERNS = [
  {
    type: 'debugging_issue',
    indicators: ['fix', 'broken', 'not working', 'error', 'bug'],
    complexity: 'medium' as const,
  },
  {
    type: 'feature_implementation',
    indicators: ['implement', 'add feature', 'new functionality', 'create'],
    complexity: 'complex' as const,
  },
  {
    type: 'code_review_request',
    indicators: ['review', 'check this', 'what do you think', 'feedback'],
    complexity: 'simple' as const,
  },
  {
    type: 'refactoring_task',
    indicators: ['refactor', 'clean up', 'improve', 'simplify'],
    complexity: 'medium' as const,
  },
  {
    type: 'learning_question',
    indicators: ['how to', 'what is', 'explain', 'why does', 'help me understand'],
    complexity: 'simple' as const,
  },
  {
    type: 'architectural_design',
    indicators: ['design', 'architecture', 'structure', 'pattern', 'approach'],
    complexity: 'very_complex' as const,
  },
]

// ============================================================================
// MentalModel Implementation
// ============================================================================

export interface MentalModelOptions {
  sessionId: string
  logger: ILogger
}

export class MentalModelImpl implements IMentalModel {
  sessionId: string
  state: MentalModelState
  context: MentalModelContext
  trajectory: MentalModelTrajectory
  lastUpdated: number

  private logger: ILogger
  private accumulatedTokens: string[] = []
  private accumulatedThinking: string[] = []

  constructor(options: MentalModelOptions) {
    this.sessionId = options.sessionId
    this.logger = options.logger.child?.('mental-model') ?? options.logger

    // Initialize with default state
    this.state = {
      phase: 'initial',
      topic: '',
      intent: {
        type: 'unknown',
        description: 'Intent not yet determined',
        confidence: 0,
        complexity: 'simple',
      },
      complexity: 0.5,
      emotionalTone: 'neutral',
      confidence: 0,
    }

    this.context = {
      loadedFiles: [],
      relevantMemories: [],
      activeSkills: [],
      pendingQuestions: [],
    }

    this.trajectory = {
      turns: [],
      patterns: [],
      dependencies: [],
    }

    this.lastUpdated = Date.now()
  }

  // ============================================================================
  // Update Methods
  // ============================================================================

  updateFromTokens(tokens: string[]): void {
    this.accumulatedTokens.push(...tokens)
    
    // Periodically analyze (every 50 tokens to avoid excessive processing)
    if (this.accumulatedTokens.length >= 50) {
      const text = this.accumulatedTokens.join('').toLowerCase()
      this.analyzeText(text)
      this.accumulatedTokens = [] // Reset after analysis
    }

    // Update phase based on token patterns
    this.updatePhaseFromTokens(tokens)
    
    this.lastUpdated = Date.now()
  }

  updateFromThinking(thinking: string): void {
    this.accumulatedThinking.push(thinking)
    
    // Analyze thinking for intent and complexity
    this.analyzeThinking(thinking)
    
    this.lastUpdated = Date.now()
  }

  updateFromToolCall(tool: string, input: unknown): void {
    // Track active skills based on tool usage
    if (!this.context.activeSkills.includes(tool)) {
      this.context.activeSkills.push(tool)
    }

    // Update phase based on tool usage
    this.updatePhaseFromTool(tool)

    // Add to trajectory
    this.trajectory.turns.push({
      turnId: `turn_${Date.now()}`,
      phase: this.state.phase,
      userMessage: '',
      assistantResponse: '',
      tokensUsed: 0,
      toolCalls: [tool],
      patterns: [],
      timestamp: Date.now(),
    })

    this.lastUpdated = Date.now()
  }

  updateFromToolResult(tool: string, result: unknown): void {
    // Could analyze result for success/failure
    this.lastUpdated = Date.now()
  }

  updateFromContext(context: EnrichedContext): void {
    // Update loaded files
    for (const file of context.loadedFiles) {
      const existing = this.context.loadedFiles.find(f => f.path === file.path)
      if (existing) {
        existing.lastAccessed = Date.now()
      } else {
        this.context.loadedFiles.push({
          ...file,
          loadedAt: Date.now(),
          lastAccessed: Date.now(),
        })
      }
    }

    // Update relevant memories
    for (const memory of context.relevantMemories) {
      const existing = this.context.relevantMemories.find(m => m.id === memory.id)
      if (existing) {
        existing.accessedAt = Date.now()
      } else {
        this.context.relevantMemories.push({
          ...memory,
          accessedAt: Date.now(),
        })
      }
    }

    // Update active skills from context
    for (const skill of context.availableTools || []) {
      if (!this.context.activeSkills.includes(skill)) {
        this.context.activeSkills.push(skill)
      }
    }

    // Update topic if we have a session summary
    if (context.sessionSummary && !this.state.topic) {
      this.state.topic = this.extractTopic(context.sessionSummary)
    }

    this.lastUpdated = Date.now()
    this.logger.debug('Context enriched', { 
      sessionId: this.sessionId.slice(-8),
      files: context.loadedFiles.length,
      memories: context.relevantMemories.length,
    })
  }

  // ============================================================================
  // Analysis Methods
  // ============================================================================

  detectPhase(): ConversationPhase {
    return this.state.phase
  }

  detectIntent(): UserIntent {
    return this.state.intent
  }

  detectPatterns(): Pattern[] {
    const text = this.getFullText()
    const detectedPatterns: Pattern[] = []

    for (const def of PATTERN_DEFINITIONS) {
      const matches = def.keywords.filter(kw => text.toLowerCase().includes(kw))
      if (matches.length > 0) {
        const existing = this.trajectory.patterns.find(p => p.type === def.id)
        
        if (existing) {
          existing.lastSeen = Date.now()
          existing.occurrenceCount++
          existing.evidence.push(...matches)
          // Trim evidence to avoid bloat
          if (existing.evidence.length > 10) {
            existing.evidence = existing.evidence.slice(-10)
          }
        } else {
          detectedPatterns.push({
            id: `pattern_${Date.now()}_${def.id}`,
            type: def.id,
            confidence: def.confidence,
            evidence: matches,
            firstSeen: Date.now(),
            lastSeen: Date.now(),
            occurrenceCount: 1,
          })
        }
      }
    }

    // Add new patterns to trajectory
    this.trajectory.patterns.push(...detectedPatterns)

    return [...this.trajectory.patterns, ...detectedPatterns]
  }

  getDependencies(): Dependency[] {
    return this.trajectory.dependencies
  }

  // ============================================================================
  // Serialization
  // ============================================================================

  toJSON(): MentalModelSnapshot {
    return {
      sessionId: this.sessionId,
      state: { ...this.state },
      context: {
        loadedFiles: [...this.context.loadedFiles],
        relevantMemories: [...this.context.relevantMemories],
        activeSkills: [...this.context.activeSkills],
        pendingQuestions: [...this.context.pendingQuestions],
      },
      trajectory: {
        turns: [...this.trajectory.turns],
        patterns: [...this.trajectory.patterns],
        dependencies: [...this.trajectory.dependencies],
      },
      lastUpdated: this.lastUpdated,
      version: 1,
    }
  }

  fromJSON(snapshot: MentalModelSnapshot): void {
    this.sessionId = snapshot.sessionId
    this.state = snapshot.state
    this.context = snapshot.context
    this.trajectory = snapshot.trajectory
    this.lastUpdated = snapshot.lastUpdated
  }

  // ============================================================================
  // Private Analysis Helpers
  // ============================================================================

  private analyzeText(text: string): void {
    const lower = text.toLowerCase()

    // Detect patterns
    this.detectPatterns()

    // Detect intent if not yet confident
    if (this.state.intent.confidence < 0.6) {
      this.detectIntentFromText(lower)
    }

    // Update topic if empty
    if (!this.state.topic) {
      this.state.topic = this.extractTopic(text)
    }

    // Estimate complexity
    this.state.complexity = this.estimateComplexity(text)
  }

  private analyzeThinking(thinking: string): void {
    const lower = thinking.toLowerCase()

    // Look for intent indicators in thinking
    for (const intent of INTENT_PATTERNS) {
      const matches = intent.indicators.filter(ind => lower.includes(ind))
      if (matches.length > 0) {
        this.state.intent = {
          type: intent.type,
          description: `Detected: ${intent.type.replace(/_/g, ' ')}`,
          confidence: Math.min(0.5 + matches.length * 0.15, 0.9),
          complexity: intent.complexity,
        }
        break
      }
    }

    // Look for questions (pending clarification)
    const questions = thinking.match(/\?\s/g) || []
    if (questions.length > 0) {
      this.state.confidence = Math.max(0, this.state.confidence - 0.1)
    }
  }

  private detectIntentFromText(text: string): void {
    for (const intent of INTENT_PATTERNS) {
      const matches = intent.indicators.filter(ind => text.includes(ind))
      if (matches.length > 0) {
        this.state.intent = {
          type: intent.type,
          description: `User wants to ${intent.type.replace(/_/g, ' ')}`,
          confidence: Math.min(matches.length * 0.25, 0.7),
          complexity: intent.complexity,
        }
        break
      }
    }
  }

  private updatePhaseFromTokens(tokens: string[]): void {
    const text = tokens.join('').toLowerCase()

    // Phase transition logic
    switch (this.state.phase) {
      case 'initial':
        if (text.includes('?') || text.includes('what') || text.includes('how')) {
          this.state.phase = 'clarifying'
        } else if (tokens.length > 100) {
          this.state.phase = 'executing'
        }
        break

      case 'clarifying':
        if (this.context.loadedFiles.length > 0 || this.context.activeSkills.length > 0) {
          this.state.phase = 'executing'
        }
        break

      case 'executing':
        if (text.includes('summary') || text.includes('conclusion') || text.includes('done')) {
          this.state.phase = 'synthesizing'
        }
        break

      case 'synthesizing':
        if (this.trajectory.patterns.some(p => p.type === 'documentation')) {
          this.state.phase = 'concluding'
        }
        break
    }
  }

  private updatePhaseFromTool(tool: string): void {
    // Tool usage often indicates execution phase
    if (this.state.phase === 'initial' || this.state.phase === 'clarifying') {
      this.state.phase = 'executing'
    }
  }

  private estimateComplexity(text: string): number {
    let score = 0.5

    // Length-based
    if (text.length > 1000) score += 0.1
    if (text.length > 3000) score += 0.1

    // Keyword-based
    const complexityIndicators = ['architecture', 'design', 'refactor', 'implement', 'complex']
    for (const indicator of complexityIndicators) {
      if (text.toLowerCase().includes(indicator)) {
        score += 0.05
      }
    }

    // Tool count
    if (this.context.activeSkills.length > 3) score += 0.1

    // Pattern count
    if (this.trajectory.patterns.length > 2) score += 0.1

    return Math.min(score, 1.0)
  }

  private extractTopic(text: string): string {
    // Simple topic extraction: look for file mentions or key nouns
    const fileMatch = text.match(/[\w-]+\.(ts|js|py|json|md|yml|yaml)/gi)
    if (fileMatch) {
      return `Working with ${fileMatch.slice(0, 3).join(', ')}`
    }

    // Look for "implement", "create", "fix" + noun phrase
    const actionMatch = text.match(/(?:implement|create|fix|add|build)\s+(?:a|the)?\s*(\w+(?:\s+\w+){0,3})/i)
    if (actionMatch) {
      return actionMatch[1]
    }

    return 'General conversation'
  }

  private getFullText(): string {
    return this.accumulatedTokens.join('')
  }
}

// ============================================================================
// Delta Calculation
// ============================================================================

export function calculateModelDelta(
  previous: MentalModelSnapshot,
  current: MentalModelSnapshot
): ModelDelta {
  const changes: ModelChange[] = []

  // Check phase change
  if (previous.state.phase !== current.state.phase) {
    changes.push({
      path: 'state.phase',
      oldValue: previous.state.phase,
      newValue: current.state.phase,
      significance: 'high',
    })
  }

  // Check intent change
  if (previous.state.intent.type !== current.state.intent.type) {
    changes.push({
      path: 'state.intent.type',
      oldValue: previous.state.intent.type,
      newValue: current.state.intent.type,
      significance: 'critical',
    })
  }

  // Check complexity change
  const complexityDelta = Math.abs(previous.state.complexity - current.state.complexity)
  if (complexityDelta > 0.2) {
    changes.push({
      path: 'state.complexity',
      oldValue: previous.state.complexity,
      newValue: current.state.complexity,
      significance: complexityDelta > 0.4 ? 'high' : 'medium',
    })
  }

  // Check file additions
  const newFiles = current.context.loadedFiles.filter(
    f => !previous.context.loadedFiles.some(pf => pf.path === f.path)
  )
  if (newFiles.length > 0) {
    changes.push({
      path: 'context.loadedFiles',
      oldValue: previous.context.loadedFiles.length,
      newValue: current.context.loadedFiles.length,
      significance: 'medium',
    })
  }

  // Check pattern additions
  const newPatterns = current.trajectory.patterns.filter(
    p => !previous.trajectory.patterns.some(pp => pp.id === p.id)
  )
  if (newPatterns.length > 0) {
    changes.push({
      path: 'trajectory.patterns',
      oldValue: previous.trajectory.patterns.length,
      newValue: current.trajectory.patterns.length,
      significance: 'medium',
    })
  }

  return {
    previous,
    current,
    changes,
  }
}

// ============================================================================
// Factory
// ============================================================================

export function createMentalModel(sessionId: string, logger: ILogger): MentalModelImpl {
  return new MentalModelImpl({ sessionId, logger })
}

// Add dialectic signal incorporation method to MentalModelImpl
// This is added via prototype to avoid modifying the class definition
(MentalModelImpl.prototype as any).incorporateDialecticSignal = async function(signal: any): Promise<void> {
  if (!signal) return;

  // Add dialectic signal to trajectory as a special turn
  (this as any).trajectory.turns.push({
    turnId: `dialectic_${Date.now()}`,
    phase: (this as any).state.phase,
    userMessage: `[Dialectic ${signal.type || 'signal'}]`,
    assistantResponse: signal.content || '',
    tokensUsed: 0,
    toolCalls: [],
    patterns: [`dialectic:${signal.type || 'unknown'}`],
    timestamp: Date.now(),
  });

  // Update state based on signal
  if (signal.confidence && signal.confidence > 0.8) {
    (this as any).state.confidence = Math.min(1, (this as any).state.confidence + 0.1);
  }

  if (signal.novelty && signal.novelty > 0.7) {
    (this as any).state.novelty = Math.min(1, (this as any).state.novelty + 0.1);
  }

  (this as any).lastUpdated = Date.now();
  (this as any).logger?.debug?.(`[MentalModel] Incorporated dialectic signal: ${signal.type}`);
};
