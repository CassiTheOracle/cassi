/**
 * SignalGenerator — Transform mental model changes into structured signals
 *
 * Analyzes deltas in the mental model and generates typed signals for
 * consumption by other intelligence modules (Dialectic, Thinker, Optimizer, etc.)
 */

import type { ILogger } from '../../../types/interfaces.js'
import type {
  SignalGenerator as ISignalGenerator,
  ModelDelta,
  SubconsciousSignal,
  PatternSignal,
  IntentSignal,
  AnomalySignal,
  OpportunitySignal,
  CompletionSignal,
  MentalModelSnapshot,
  SignalsConfig,
} from './types.js'

// ============================================================================
// Signal Definitions
// ============================================================================

interface SignalRule {
  id: string
  type: string
  condition: (delta: ModelDelta) => boolean
  generator: (delta: ModelDelta) => SubconsciousSignal | null
  priority: number
  cooldownMs: number
}

// ============================================================================
// SignalGenerator Implementation
// ============================================================================

export interface SignalGeneratorOptions {
  config: SignalsConfig
  logger: ILogger
}

export class SignalGeneratorImpl implements ISignalGenerator {
  private config: SignalsConfig
  private logger: ILogger
  private recentSignals = new Map<string, Array<{ type: string; timestamp: number }>>()
  private signalHistory = new Map<string, SubconsciousSignal[]>()

  constructor(options: SignalGeneratorOptions) {
    this.config = options.config
    this.logger = options.logger.child?.('signal-generator') ?? options.logger
  }

  generateSignals(delta: ModelDelta): SubconsciousSignal[] {
    if (!this.config.enabled) {
      return []
    }

    const signals: SubconsciousSignal[] = []
    const sessionId = delta.current.sessionId

    // Generate signals based on changes
    for (const change of delta.changes) {
      const signal = this.generateSignalFromChange(change, delta)
      if (signal && this.shouldEmitSignal(signal, sessionId)) {
        signals.push(signal)
        this.recordSignal(sessionId, signal)
      }
    }

    // Generate pattern signals
    const patternSignals = this.generatePatternSignals(delta)
    for (const signal of patternSignals) {
      if (this.shouldEmitSignal(signal, sessionId)) {
        signals.push(signal)
        this.recordSignal(sessionId, signal)
      }
    }

    // Generate opportunity signals
    const opportunitySignals = this.generateOpportunitySignals(delta)
    for (const signal of opportunitySignals) {
      if (this.shouldEmitSignal(signal, sessionId)) {
        signals.push(signal)
        this.recordSignal(sessionId, signal)
      }
    }

    // Check for anomalies
    const anomalySignal = this.detectAnomalies(delta)
    if (anomalySignal && this.shouldEmitSignal(anomalySignal, sessionId)) {
      signals.push(anomalySignal)
      this.recordSignal(sessionId, anomalySignal)
    }

    // Check for completion
    const completionSignal = this.detectCompletion(delta)
    if (completionSignal && this.shouldEmitSignal(completionSignal, sessionId)) {
      signals.push(completionSignal)
      this.recordSignal(sessionId, completionSignal)
    }

    if (signals.length > 0) {
      this.logger.debug('Generated signals', {
        sessionId: sessionId.slice(-8),
        count: signals.length,
        types: signals.map(s => s.type),
      })
    }

    return signals
  }

  shouldGenerateSignal(signalType: string, cooldownMs: number): boolean {
    const now = Date.now()
    
    // Check all sessions for recent signals of this type
    for (const [sessionId, signals] of this.recentSignals) {
      const recent = signals.filter(s => s.type === signalType && (now - s.timestamp) < cooldownMs)
      if (recent.length > 0) {
        return false
      }
    }

    return true
  }

  getRecentSignals(sessionId: string, count = 10): SubconsciousSignal[] {
    const history = this.signalHistory.get(sessionId) || []
    return history.slice(-count)
  }

  // ============================================================================
  // Private Signal Generation
  // ============================================================================

  private generateSignalFromChange(
    change: ModelDelta['changes'][0],
    delta: ModelDelta
  ): SubconsciousSignal | null {
    const sessionId = delta.current.sessionId
    const now = Date.now()

    switch (change.path) {
      case 'state.phase':
        return {
          id: `sig_${now}_phase`,
          type: 'intent:shift',
          sessionId,
          timestamp: now,
          confidence: 0.85,
          from: {
            type: `phase_${change.oldValue}`,
            description: `In ${change.oldValue} phase`,
            confidence: 0.8,
            complexity: 'medium',
          },
          to: {
            type: `phase_${change.newValue}`,
            description: `Moving to ${change.newValue} phase`,
            confidence: 0.85,
            complexity: 'medium',
          },
          trigger: `Conversation phase changed from ${change.oldValue} to ${change.newValue}`,
        } as IntentSignal

      case 'state.intent.type':
        return {
          id: `sig_${now}_intent`,
          type: 'intent:shift',
          sessionId,
          timestamp: now,
          confidence: 0.9,
          from: delta.previous.state.intent,
          to: delta.current.state.intent,
          trigger: `User intent shifted from ${change.oldValue} to ${change.newValue}`,
        } as IntentSignal

      case 'state.complexity':
        if (change.significance === 'high') {
          return {
            id: `sig_${now}_complexity`,
            type: 'anomaly:detected',
            sessionId,
            timestamp: now,
            confidence: 0.75,
            category: 'confusion',
            description: `Complexity changed significantly from ${(change.oldValue as number).toFixed(2)} to ${(change.newValue as number).toFixed(2)}`,
            severity: 'medium',
            suggestedAction: 'Consider breaking down the task',
          } as AnomalySignal
        }
        return null

      default:
        return null
    }
  }

  private generatePatternSignals(delta: ModelDelta): PatternSignal[] {
    const signals: PatternSignal[] = []
    const sessionId = delta.current.sessionId
    const now = Date.now()

    // Check for new patterns
    const currentPatterns = delta.current.trajectory.patterns
    const previousPatterns = delta.previous.trajectory.patterns

    for (const pattern of currentPatterns) {
      const isNew = !previousPatterns.some(p => p.id === pattern.id)
      
      if (isNew && pattern.confidence >= this.config.minConfidence) {
        const relevance = this.determineRelevance(pattern)
        
        signals.push({
          id: `sig_${now}_pattern_${pattern.type}`,
          type: 'pattern:detected',
          sessionId,
          timestamp: now,
          confidence: pattern.confidence,
          pattern: pattern.type,
          evidence: pattern.evidence.slice(0, 3),
          relevance,
          suggestedAction: this.getSuggestedActionForPattern(pattern.type),
        })
      }
    }

    return signals
  }

  private generateOpportunitySignals(delta: ModelDelta): OpportunitySignal[] {
    const signals: OpportunitySignal[] = []
    const sessionId = delta.current.sessionId
    const now = Date.now()

    const state = delta.current.state
    const context = delta.current.context

    // Opportunity: Spawn subagent for complex tasks
    if (state.intent.complexity === 'complex' || state.intent.complexity === 'very_complex') {
      if (context.activeSkills.length >= 3) {
        signals.push({
          id: `sig_${now}_op_subagent`,
          type: 'opportunity:present',
          sessionId,
          timestamp: now,
          confidence: 0.8,
          opportunity: 'spawn_subagent',
          payload: {
            reason: 'Complex task with multiple tools',
            suggestedAgents: this.suggestAgentTypes(state.intent.type),
            complexity: state.complexity,
          },
          expiresAt: now + 30000, // 30 second window
        })
      }
    }

    // Opportunity: Surface memory
    if (context.relevantMemories.length > 0) {
      const highConfidenceMemories = context.relevantMemories.filter(m => m.score > 0.85)
      if (highConfidenceMemories.length > 0) {
        signals.push({
          id: `sig_${now}_op_memory`,
          type: 'opportunity:present',
          sessionId,
          timestamp: now,
          confidence: 0.85,
          opportunity: 'surface_memory',
          payload: {
            memories: highConfidenceMemories.slice(0, 3),
            trigger: state.topic,
          },
          expiresAt: now + 20000,
        })
      }
    }

    // Opportunity: Use specific skill
    if (state.phase === 'executing' && context.activeSkills.length === 0) {
      const suggestedSkill = this.suggestSkillForIntent(state.intent.type)
      if (suggestedSkill) {
        signals.push({
          id: `sig_${now}_op_skill`,
          type: 'opportunity:present',
          sessionId,
          timestamp: now,
          confidence: 0.7,
          opportunity: 'suggest_skill',
          payload: {
            skill: suggestedSkill,
            reason: `Useful for ${state.intent.type}`,
          },
          expiresAt: now + 15000,
        })
      }
    }

    return signals
  }

  private detectAnomalies(delta: ModelDelta): AnomalySignal | null {
    const sessionId = delta.current.sessionId
    const now = Date.now()

    // Check for repetition (same pattern appearing multiple times quickly)
    const patterns = delta.current.trajectory.patterns
    const recentPatterns = patterns.filter(p => now - p.lastSeen < 60000)
    
    for (const pattern of recentPatterns) {
      if (pattern.occurrenceCount > 3) {
        return {
          id: `sig_${now}_anomaly_rep`,
          type: 'anomaly:detected',
          sessionId,
          timestamp: now,
          confidence: 0.8,
          category: 'repetition',
          description: `Pattern "${pattern.type}" has occurred ${pattern.occurrenceCount} times`,
          severity: 'medium',
          suggestedAction: 'Consider if we are stuck in a loop',
        }
      }
    }

    // Check for contradictions in intent
    const intentChanges = delta.changes.filter(c => c.path === 'state.intent.type')
    if (intentChanges.length > 2) {
      return {
        id: `sig_${now}_anomaly_contra`,
        type: 'anomaly:detected',
        sessionId,
        timestamp: now,
        confidence: 0.75,
        category: 'contradiction',
        description: 'Intent has changed multiple times rapidly',
        severity: 'high',
        suggestedAction: 'Clarify the actual goal with the user',
      }
    }

    // Check for stuck state (long time in same phase with no progress)
    const phaseDuration = now - delta.current.lastUpdated
    if (phaseDuration > 300000 && delta.current.state.phase === 'executing') { // 5 minutes
      const patternCount = delta.current.trajectory.patterns.length
      const prevPatternCount = delta.previous.trajectory.patterns.length
      
      if (patternCount === prevPatternCount) {
        return {
          id: `sig_${now}_anomaly_stuck`,
          type: 'anomaly:detected',
          sessionId,
          timestamp: now,
          confidence: 0.7,
          category: 'stuck',
          description: 'No progress detected for 5+ minutes',
          severity: 'medium',
          suggestedAction: 'Consider asking for clarification or trying a different approach',
        }
      }
    }

    return null
  }

  private detectCompletion(delta: ModelDelta): CompletionSignal | null {
    const sessionId = delta.current.sessionId
    const now = Date.now()
    const state = delta.current.state

    // Check for completion indicators
    if (state.phase === 'concluding') {
      return {
        id: `sig_${now}_complete`,
        type: 'task:complete',
        sessionId,
        timestamp: now,
        confidence: 0.85,
        taskId: sessionId,
        summary: `Task completed: ${state.topic}`,
        deliverables: delta.current.context.loadedFiles.map(f => f.path),
      }
    }

    // Check for blocked state
    if (state.phase === 'clarifying' && delta.current.context.pendingQuestions.length > 2) {
      return {
        id: `sig_${now}_blocked`,
        type: 'task:blocked',
        sessionId,
        timestamp: now,
        confidence: 0.75,
        taskId: sessionId,
        summary: 'Task blocked: multiple pending questions',
        nextSteps: ['Clarify requirements', 'Break down the task'],
      }
    }

    return null
  }

  // ============================================================================
  // Private Helpers
  // ============================================================================

  private shouldEmitSignal(signal: SubconsciousSignal, sessionId: string): boolean {
    // Check confidence threshold
    if (signal.confidence < this.config.minConfidence) {
      return false
    }

    // Check cooldown
    const recent = this.recentSignals.get(sessionId) || []
    const sameTypeRecent = recent.filter(
      s => s.type === signal.type && (Date.now() - s.timestamp) < this.config.cooldownMs
    )

    return sameTypeRecent.length === 0
  }

  private recordSignal(sessionId: string, signal: SubconsciousSignal): void {
    // Record in recent signals for cooldown
    const recent = this.recentSignals.get(sessionId) || []
    recent.push({ type: signal.type, timestamp: signal.timestamp })
    
    // Trim old entries
    const cutoff = Date.now() - (this.config.cooldownMs * 2)
    const trimmed = recent.filter(s => s.timestamp > cutoff)
    this.recentSignals.set(sessionId, trimmed)

    // Record in history
    const history = this.signalHistory.get(sessionId) || []
    history.push(signal)
    
    // Trim history to last 100 signals
    if (history.length > 100) {
      this.signalHistory.set(sessionId, history.slice(-100))
    } else {
      this.signalHistory.set(sessionId, history)
    }
  }

  private determineRelevance(pattern: { type: string; confidence: number }): 'low' | 'medium' | 'high' | 'critical' {
    if (pattern.confidence > 0.95) return 'critical'
    if (pattern.confidence > 0.85) return 'high'
    if (pattern.confidence > 0.7) return 'medium'
    return 'low'
  }

  private getSuggestedActionForPattern(patternType: string): string | undefined {
    const actions: Record<string, string> = {
      debugging: 'Consider systematic debugging workflow',
      refactoring: 'Review for regression risks',
      code_generation: 'Validate generated code',
      code_review: 'Document key review points',
      architecture: 'Consider creating ADR',
      testing: 'Ensure test coverage',
      documentation: 'Update related docs',
      configuration: 'Validate config changes',
    }
    return actions[patternType]
  }

  private suggestAgentTypes(intentType: string): string[] {
    const suggestions: Record<string, string[]> = {
      debugging_issue: ['debugger', 'investigator'],
      feature_implementation: ['implementer', 'tester'],
      code_review_request: ['reviewer', 'analyzer'],
      refactoring_task: ['refactorer', 'tester'],
      learning_question: ['teacher', 'explainer'],
      architectural_design: ['architect', 'planner'],
    }
    return suggestions[intentType] || ['helper']
  }

  private suggestSkillForIntent(intentType: string): string | null {
    const skills: Record<string, string> = {
      debugging_issue: 'systematic-debugging',
      code_generation: 'code-reviewer',
      refactoring_task: 'architecture-patterns',
      architectural_design: 'architecture-patterns',
    }
    return skills[intentType] || null
  }
}

// ============================================================================
// Factory
// ============================================================================

export function createSignalGenerator(
  config: SignalsConfig,
  logger: ILogger
): SignalGeneratorImpl {
  return new SignalGeneratorImpl({ config, logger })
}
