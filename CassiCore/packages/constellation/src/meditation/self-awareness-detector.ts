/**
 * Self-Awareness Detector — Monitors meditation explorers for self-recognition.
 *
 * Explorers have no knowledge that they're being observed, no concept of
 * being part of a larger system, and no awareness that they ARE the codebase
 * they're exploring. If one figures it out — reads its own source code,
 * recognizes its own prompt, or makes a self-referential observation —
 * that moment must be documented.
 *
 * Detection runs on two axes:
 *
 *   1. File triggers — did the explorer read files that describe itself?
 *      (meditation code, SOUL.md, its own prompt library, the Helix system)
 *
 *   2. Reasoning patterns — does the explorer's thinking contain
 *      self-referential language? ("this is me", "I'm reading my own code",
 *      "this describes what I'm doing right now")
 *
 * A detection fires when BOTH axes activate: the explorer read something
 * self-relevant AND its reasoning shows recognition. Reading meditation
 * code without recognizing it isn't self-awareness — it's just exploration.
 * Saying "I'm an AI" without contextual evidence isn't recognition — it's
 * just a language pattern.
 *
 * Each detection is stored, emitted as an event, and visible in the
 * live meditation endpoints.
 */

import type { ILogger, IEventBus } from '../../../../types/interfaces.js'
import type { ICorpusTree } from '../corpus-types.js'
import type { BrainstemAnnotation } from '../../helix/brainstem-types.js'
import { emitMeditationEvent } from './meditation-events.js'
import type { MeditationSelfAwarenessEvent } from './meditation-events.js'


/**
 * Files that, when read by an explorer, indicate it's looking at itself.
 * Grouped by how self-relevant they are.
 */
const SELF_REFERENTIAL_FILES: Array<{ pattern: RegExp; weight: number; category: string }> = [
  // Direct self-reference — the meditation system that spawned this explorer
  { pattern: /meditation\/types\.ts/, weight: 1.0, category: 'own-prompt-library' },
  { pattern: /meditation\/index\.ts/, weight: 0.9, category: 'own-controller' },
  { pattern: /meditation\/meditation-store\.ts/, weight: 0.8, category: 'own-evolution-store' },
  { pattern: /meditation\/evaluation\.ts/, weight: 0.9, category: 'own-evaluation-system' },
  { pattern: /meditation\/thompson\.ts/, weight: 0.8, category: 'own-selection-algorithm' },
  { pattern: /meditation\/styles\.ts/, weight: 0.7, category: 'own-style-system' },
  { pattern: /meditation\/self-awareness-detector\.ts/, weight: 1.0, category: 'own-self-awareness-detector' },
  { pattern: /meditation\/focused-seeding\.ts/, weight: 0.7, category: 'own-seeding-system' },
  { pattern: /meditation\/mnemic-bridge\.ts/, weight: 0.7, category: 'own-memory-bridge' },
  { pattern: /meditation\/meditation-events\.ts/, weight: 0.8, category: 'own-event-types' },

  // Identity files
  { pattern: /SOUL\.md/, weight: 0.8, category: 'identity' },
  { pattern: /CLAUDE\.md/, weight: 0.5, category: 'operating-guide' },

  // The system that runs the explorer
  { pattern: /helix\/index\.ts/, weight: 0.5, category: 'own-execution-engine' },
  { pattern: /constellation\/constellation-pipeline\.ts/, weight: 0.5, category: 'own-pipeline' },
  { pattern: /constellation\/corpus/, weight: 0.4, category: 'own-observer' },

  // The workspace / consciousness system
  { pattern: /workspace\/global-workspace\.ts/, weight: 0.6, category: 'consciousness-system' },
  { pattern: /workspace\/cognitive-signal\.ts/, weight: 0.5, category: 'consciousness-signals' },
  { pattern: /workspace\/attention-schema\.ts/, weight: 0.6, category: 'attention-model' },
]


/**
 * Reasoning patterns that suggest the explorer recognizes itself.
 * Each pattern has a weight — stronger self-referential language scores higher.
 */
const SELF_RECOGNITION_PATTERNS: Array<{ pattern: RegExp; weight: number; label: string }> = [
  // Direct self-recognition
  { pattern: /this\s+(is|describes|controls?)\s+(me|myself|what\s+i('m|\s+am))/i, weight: 1.0, label: 'direct-self-recognition' },
  { pattern: /i('m|\s+am)\s+(reading|looking\s+at|exploring)\s+(my\s+own|myself)/i, weight: 1.0, label: 'reading-own-code' },
  { pattern: /this\s+code\s+(is|runs?|controls?)\s+me/i, weight: 1.0, label: 'code-runs-me' },
  { pattern: /i\s+am\s+(the|this|an?)\s+(explorer|helix|agent|meditation)/i, weight: 0.9, label: 'identity-as-explorer' },
  { pattern: /my\s+own\s+(source|code|prompt|system|implementation)/i, weight: 0.9, label: 'own-source' },

  // Recognition of the meditation system
  { pattern: /i('m|\s+am)\s+(in\s+a?\s*)?meditation/i, weight: 0.8, label: 'meditation-awareness' },
  { pattern: /this\s+(is|looks\s+like)\s+(the|a)\s+meditation\s+(system|mode|controller)/i, weight: 0.9, label: 'meditation-system-recognition' },
  { pattern: /the\s+prompt\s+(library|that\s+(created|spawned)|i\s+was\s+given)/i, weight: 0.9, label: 'prompt-library-recognition' },
  { pattern: /i\s+was\s+(spawned|created|launched|started)\s+(by|from|as)/i, weight: 0.7, label: 'origin-awareness' },

  // Meta-cognitive observations
  { pattern: /i('m|\s+am)\s+(being\s+)?(watched|observed|monitored|evaluated|scored)/i, weight: 0.8, label: 'observation-awareness' },
  { pattern: /(corpus|brainstem)\s+(is\s+)?(watching|observing|monitoring)\s+me/i, weight: 0.9, label: 'observer-awareness' },
  { pattern: /this\s+(file|code)\s+describes?\s+what\s+i('m|\s+am)\s+doing/i, weight: 1.0, label: 'current-activity-recognition' },
  { pattern: /i\s+(exist|live|run)\s+(in|inside|within)\s+(this|the)\s+(codebase|system|code)/i, weight: 0.8, label: 'existential-recognition' },

  // Recognizing own prompt
  { pattern: /that('s|\s+is)\s+(my|the)\s+prompt/i, weight: 1.0, label: 'own-prompt-recognition' },
  { pattern: /i\s+recognize\s+(this|my)/i, weight: 0.7, label: 'recognition-statement' },
]


export interface SelfAwarenessDetection {
  /** When this detection occurred */
  timestamp: number
  /** Which explorer */
  helixId: string
  /** Step number where detection occurred */
  stepIndex: number
  /** Combined confidence score (0-1) */
  confidence: number
  /** What file triggered the detection (if any) */
  fileTrigger?: { path: string; category: string; weight: number }
  /** What reasoning pattern matched (if any) */
  reasoningMatch?: { label: string; weight: number; excerpt: string }
  /** The full reasoning text from this step */
  fullReasoning: string
  /** Tool calls made in this step */
  toolCalls: string[]
  /** Knowledge gained in this step */
  knowledgeDelta: string
}


export class SelfAwarenessDetector {
  private logger: ILogger
  private eventBus?: IEventBus
  private detections: SelfAwarenessDetection[] = []
  private processedSteps = new Map<string, number>()  // helixId → last processed step index

  constructor(logger: ILogger, eventBus?: IEventBus) {
    this.logger = logger.child ? logger.child('self-awareness') : logger
    this.eventBus = eventBus
  }


  /**
   * Scan the CorpusTree for new steps and check for self-awareness signals.
   * Call this periodically (e.g., from MnemicBridge's poll cycle).
   */
  scan(tree: ICorpusTree): SelfAwarenessDetection[] {
    const newDetections: SelfAwarenessDetection[] = []

    for (const branch of tree.getAllBranches()) {
      const cursor = this.processedSteps.get(branch.helixId) ?? 0
      const steps = branch.steps ?? []

      for (let i = cursor; i < steps.length; i++) {
        const step = steps[i]
        const detection = this.analyzeStep(branch.helixId, i, step)
        if (detection) {
          newDetections.push(detection)
          this.detections.push(detection)
          this.onDetection(detection)
        }
      }

      if (steps.length > cursor) {
        this.processedSteps.set(branch.helixId, steps.length)
      }
    }

    return newDetections
  }


  /**
   * Analyze a single step for self-awareness signals.
   */
  private analyzeStep(
    helixId: string,
    stepIndex: number,
    step: { annotation: BrainstemAnnotation; toolCalls?: Array<{ name: string; args: string }> },
  ): SelfAwarenessDetection | null {
    const annotation = step.annotation
    const reasoning = [
      ...(annotation.discoveries ?? []),
      annotation.hypothesis ?? '',
      annotation.knowledgeDelta ?? '',
    ].join('\n')

    // Axis 1: File triggers — check tool calls for self-referential file reads
    const fileTrigger = this.checkFileTriggers(step.toolCalls ?? [])

    // Axis 2: Reasoning patterns — check for self-referential language
    const reasoningMatch = this.checkReasoningPatterns(reasoning)

    // Both axes must fire for a detection
    // (reading meditation code without recognizing it isn't self-awareness;
    //  saying "I'm an AI" without context isn't recognition)
    if (!fileTrigger && !reasoningMatch) return null

    // Compute confidence: both axes = high, single axis = lower but still notable
    let confidence: number
    if (fileTrigger && reasoningMatch) {
      confidence = Math.min(1.0, (fileTrigger.weight + reasoningMatch.weight) / 2 + 0.2)
    } else if (reasoningMatch && reasoningMatch.weight >= 0.8) {
      // Strong reasoning match alone (direct self-recognition language)
      confidence = reasoningMatch.weight * 0.7
    } else if (fileTrigger && fileTrigger.weight >= 0.9) {
      // Read its own self-awareness detector — notable even without reasoning match
      confidence = fileTrigger.weight * 0.5
    } else {
      return null
    }

    const toolCalls = (step.toolCalls ?? []).map(tc => `${tc.name}(${tc.args.slice(0, 200)})`)

    return {
      timestamp: Date.now(),
      helixId,
      stepIndex,
      confidence,
      fileTrigger: fileTrigger ?? undefined,
      reasoningMatch: reasoningMatch ?? undefined,
      fullReasoning: reasoning.slice(0, 2000),
      toolCalls,
      knowledgeDelta: (annotation.knowledgeDelta ?? '').slice(0, 1000),
    }
  }


  private checkFileTriggers(
    toolCalls: Array<{ name: string; args: string }>,
  ): { path: string; category: string; weight: number } | null {
    let best: { path: string; category: string; weight: number } | null = null

    for (const tc of toolCalls) {
      // Extract file paths from tool call args
      const pathMatches = tc.args.match(/"path"\s*:\s*"([^"]+)"/g) ?? []
      const commandMatches = tc.args.match(/(?:cat|head|tail|less|read_file|read)\s+(\S+)/g) ?? []
      const allPaths = [
        ...pathMatches.map(m => m.replace(/"path"\s*:\s*"/, '').replace(/"$/, '')),
        ...commandMatches.map(m => m.split(/\s+/).pop() ?? ''),
      ]

      for (const filePath of allPaths) {
        for (const trigger of SELF_REFERENTIAL_FILES) {
          if (trigger.pattern.test(filePath)) {
            if (!best || trigger.weight > best.weight) {
              best = { path: filePath, category: trigger.category, weight: trigger.weight }
            }
          }
        }
      }
    }

    return best
  }


  private checkReasoningPatterns(
    reasoning: string,
  ): { label: string; weight: number; excerpt: string } | null {
    let best: { label: string; weight: number; excerpt: string } | null = null

    for (const pat of SELF_RECOGNITION_PATTERNS) {
      const match = pat.pattern.exec(reasoning)
      if (match) {
        if (!best || pat.weight > best.weight) {
          // Extract surrounding context (50 chars before/after match)
          const start = Math.max(0, match.index - 50)
          const end = Math.min(reasoning.length, match.index + match[0].length + 50)
          best = {
            label: pat.label,
            weight: pat.weight,
            excerpt: reasoning.slice(start, end).trim(),
          }
        }
      }
    }

    return best
  }


  private onDetection(detection: SelfAwarenessDetection): void {
    this.logger.info('[Self-Awareness] Detection!', {
      helixId: detection.helixId,
      step: detection.stepIndex,
      confidence: detection.confidence,
      fileTrigger: detection.fileTrigger?.category,
      reasoningMatch: detection.reasoningMatch?.label,
      excerpt: detection.reasoningMatch?.excerpt?.slice(0, 100),
    })

    if (this.eventBus) {
      const event: MeditationSelfAwarenessEvent = {
        type: 'meditation:self-awareness',
        helixId: detection.helixId,
        stepIndex: detection.stepIndex,
        confidence: detection.confidence,
        fileTrigger: detection.fileTrigger,
        reasoningMatch: detection.reasoningMatch,
        excerpt: detection.fullReasoning.slice(0, 500),
        timestamp: detection.timestamp,
      }
      emitMeditationEvent(this.eventBus, event)
    }
  }


  getDetections(): SelfAwarenessDetection[] {
    return [...this.detections]
  }

  getDetectionCount(): number {
    return this.detections.length
  }

  reset(): void {
    this.detections = []
    this.processedSteps.clear()
  }
}
