import type { WorkUnit } from './vendor/helix/work-types.js'
import type { BrainstemAnnotation, SharedTreeReader } from './vendor/helix/brainstem-types.js'
import type { BranchApproach, ICorpusTree, CorpusDirective } from './corpus-types.js'
import type { CrossBranchDeliveryTarget } from './cross-helix-dialectic.js'


export interface ObserverBranchStateOpts {
  helixId: string
  goal: string
  corpusTree: ICorpusTree
  sharedTree: SharedTreeReader
}


export class ObserverBranchState implements CrossBranchDeliveryTarget {
  private helixId: string
  private goal: string
  private corpusTree: ICorpusTree
  private sharedTree: SharedTreeReader
  private workUnits = 0
  private filesActive = new Set<string>()
  private discoveries: string[] = []
  private outputs: string[] = []
  private blockers: string[] = []
  private lastReasoning = ''
  private currentApproach: BranchApproach = 'exploration'
  // WHY: Queue of cross-branch directives from CrossHelixDialectic.
  // These get included in the next digest so the Corpus and other observers
  // can see inter-branch communication. (c-36 postmortem Root Cause A)
  private pendingDirectives: string[] = []

  constructor(opts: ObserverBranchStateOpts) {
    this.helixId = opts.helixId
    this.goal = opts.goal
    this.corpusTree = opts.corpusTree
    this.sharedTree = opts.sharedTree
  }

  onWorkUnit(workUnit: WorkUnit, iteration: number): void {
    this.workUnits++
    this.lastReasoning = workUnit.reasoning ?? ''
    this.currentApproach = inferApproach(workUnit)

    for (const f of workUnit.filesModified ?? []) {
      if (f.path) this.filesActive.add(f.path)
      if (f.summary) this.outputs.push(f.summary)
    }

    const toolNames = workUnit.toolCalls.map(t => t.name)
    for (const result of workUnit.toolResults ?? []) {
      if (result.isError) this.blockers.push(result.content.slice(0, 200))
    }
    if (workUnit.reasoning) {
      const factual = extractFactualContent(workUnit.reasoning)
      if (factual) this.discoveries.push(factual)
    }

    this.discoveries = this.discoveries.slice(-12)
    this.outputs = this.outputs.slice(-12)
    this.blockers = this.blockers.slice(-6)

    const annotation = this.toAnnotation(workUnit, iteration, toolNames)
    const toolCalls = workUnit.toolCalls.map(tc => ({
      name: tc.name,
      args: JSON.stringify(tc.input ?? {}).slice(0, 500),
    }))

    this.corpusTree.pushAnnotation(this.helixId, annotation, toolCalls)
    this.publishDigest()
  }

  updateLiveStreamSnippet(snippet: string): void {
    this.sharedTree.updateLiveStreamSnippet(snippet)
  }

  /**
   * Receive a cross-branch directive from CrossHelixDialectic.
   * WHY: Implements CrossBranchDeliveryTarget so ObserverBranchState can
   * participate in inter-branch communication without requiring a Brainstem.
   * (c-36 postmortem Root Cause A)
   */
  onCorpusDirective(directive: CorpusDirective): void {
    const label = `[${directive.urgency?.toUpperCase() ?? 'MEDIUM'} ${directive.reason ?? 'cross-branch'}]`
    const text = `${label} ${directive.text}`
    this.pendingDirectives.push(text.slice(0, 500))
    // Keep only the most recent 10 directives
    this.pendingDirectives = this.pendingDirectives.slice(-10)
    // Update the live stream so the Corpus sees the directive immediately
    this.sharedTree.updateLiveStreamSnippet(text.slice(0, 1000))
  }

  /**
   * Drain pending cross-branch directives. Called by the pipeline after
   * injecting them into the posture context so they're not re-delivered.
   */
  drainDirectives(): string[] {
    const pending = this.pendingDirectives
    this.pendingDirectives = []
    return pending
  }

  private toAnnotation(workUnit: WorkUnit, iteration: number, toolNames: string[]): BrainstemAnnotation {
    const hasOutput = (workUnit.filesModified?.length ?? 0) > 0 || toolNames.some(t => /test|bash|write|edit|file|code/.test(t))
    const progress = hasOutput ? 0.6 : 0.25
    const novelty = workUnit.toolCalls.length > 0 ? 0.55 : 0.35
    const goalAlignment = 0.6
    const score = goalAlignment * 0.3 + novelty * 0.3 + progress * 0.4

    return {
      workUnitId: workUnit.id,
      score,
      annotation: this.currentApproach === 'debugging' ? 'revision' : this.currentApproach as any,
      synthesis: workUnit.reasoning ?? '',
      pattern: 'none' as any,
      guidance: null,
      guidanceUrgency: 'low' as any,
      trainingNote: 'Observer-native raw work unit annotation; no Brainstem LLM scoring.',
      axonStep: iteration,
      timestamp: workUnit.timestamp,
      goalAlignment,
      novelty,
      progress,
      discoveries: workUnit.reasoning ? [workUnit.reasoning.slice(0, 400)] : [],
      decisions: [],
      hypothesis: '',
      outputs: workUnit.filesModified.map(f => `${f.action}: ${f.path}`),
      blockers: workUnit.toolResults.filter(r => r.isError).map(r => r.content.slice(0, 200)),
      nextSteps: [],
      knowledgeDelta: workUnit.toolResults.map(r => r.content.slice(0, 200)).join('\n'),
    }
  }

  private publishDigest(): void {
    const progress = Math.min(0.95, this.workUnits / 12)
    // WHY: Include cross-branch directives in keyFindings so the Corpus and
    // other consumers can see inter-branch communication in the digest.
    const combinedFindings = [...this.discoveries, ...this.pendingDirectives]
    this.sharedTree.updateDigest({
      helixId: this.helixId,
      goalSummary: this.goal,
      approach: this.currentApproach,
      progress,
      filesActive: Array.from(this.filesActive).slice(-20),
      keyFindings: combinedFindings.slice(-8),
      blockers: this.blockers.slice(-5),
      currentStrategy: describeStrategy(this.currentApproach),
      rollingScore: 0.55 + Math.min(0.25, progress * 0.25),
      workUnitsProcessed: this.workUnits,
      updatedAt: Date.now(),
      allDiscoveries: combinedFindings.slice(-10),
      recentOutputs: this.outputs.slice(-10),
      liveStreamSnippet: this.lastReasoning.slice(-1000),
      currentBlockers: this.blockers.slice(-5).map(b => ({
        description: b,
        detectedAt: Date.now(),
        severity: 'medium' as const,
      })),
      confidenceLevel: {
        score: Math.min(0.8, 0.35 + progress * 0.45),
        trend: 'stable',
        factors: ['observer-native digest'],
        updatedAt: Date.now(),
      },
    })
  }
}


function inferApproach(workUnit: WorkUnit): BranchApproach {
  const toolNames = workUnit.toolCalls.map(t => t.name).join(' ').toLowerCase()
  const reasoning = (workUnit.reasoning ?? '').toLowerCase()
  if (/test|verify|pytest|vitest/.test(toolNames + reasoning)) return 'testing'
  if (/write|edit|replace|insert|code/.test(toolNames)) return 'implementation'
  if (/error|failed|fix|debug/.test(reasoning) || workUnit.toolResults.some(r => r.isError)) return 'debugging'
  if (/review|risk|edge|concern/.test(reasoning)) return 'research'
  return 'exploration'
}


function describeStrategy(approach: BranchApproach): string {
  switch (approach) {
    case 'implementation': return 'Producing or changing concrete artifacts.'
    case 'testing': return 'Checking behavior and validating results.'
    case 'debugging': return 'Investigating errors or failed assumptions.'
    case 'research': return 'Reviewing risks, evidence, and alternatives.'
    case 'revision': return 'Revising prior work.'
    case 'coordinating': return 'Integrating nearby work.'
    default: return 'Exploring the problem space.'
  }
}


/**
 * Filter agent monologue from reasoning to extract factual content only.
 * WHY: Previously the digest extractor pushed raw reasoning into discoveries,
 * resulting in entries like "Iteration 5: 1 tool calls" and "Let me start my
 * investigation" instead of actual findings. (c-36 postmortem BUG I)
 */
const MONOLOGUE_PATTERNS = [
  // Iteration counters
  /^Iteration \d+:\s*\d+\s*tool\s*calls?$/im,
  // Process narration — "Let me start", "I need to check"
  /^Let me\s/im,
  /^I need to\s/im,
  /^I should\s/im,
  /^I will\s/im,
  /^I'm going to\s/im,
  /^Now I\s/im,
  /^Next,?\s*I\s/im,
  /^I'll\s/im,
  /^I can\s/im,
  /^I want to\s/im,
  /^My (?:next|first|current)\s/im,
  /^Based on\s+my\s/im,
  /^I think I\s/im,
  /^Let's\s/im,
  // First-person state reports — "I've read both files", "I see the issue"
  /^I've\s/im,
  /^I (?:read|see|notice|observe|found|checked|looked|examined|reviewed|analyzed|completed|finished|done)\s/im,
  /^I (?:also|already|just|still|now|then|first|finally)\s/im,
  // Acknowledgments and confirmations
  /^(?:OK|Okay|Got it|Understood|Sure|Right|Yes|No)\b/im,
  // Hedging and uncertainty narration
  /^(?:Hmm|Huh|Wait|Actually|Well|So)\b/im,
  // Meta-commentary about process
  /^(?:Looking|Checking|Searching|Reading|Examining|Analyzing|Investigating|Starting|Moving|Continuing|Going)\s/im,
]

function extractFactualContent(reasoning: string): string | null {
  if (reasoning.length < 30) return null
  const sentences = reasoning.split(/(?<=[.!?])\s+/)
  const factual = sentences.filter(s => {
    const trimmed = s.trim()
    // Skip very short sentences — almost always narration, never findings
    if (trimmed.length < 25) return false
    // Skip first-person process narration
    if (MONOLOGUE_PATTERNS.some(p => p.test(trimmed))) return false
    // Skip sentences that are just "X does Y" single-clause observations
    // without specific detail (file paths, function names, error messages)
    if (trimmed.length < 50 && !/[./\\_]/.test(trimmed) && !/\d{2,}/.test(trimmed)) return false
    return true
  })
  if (factual.length === 0) return null
  return factual.join(' ').slice(0, 500)
}
