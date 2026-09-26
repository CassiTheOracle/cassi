/**
 * AI Engineer — Prompt Evolver
 *
 * Implements the three-step differential evolution pipeline for cognitive
 * program upgrades:
 *
 *   Step 1 CRITIQUE  — Identify weaknesses in the current prompt/config value.
 *   Step 2 IMPROVE   — Rewrite the value addressing the identified weaknesses.
 *   Step 3 VALIDATE  — Red-team the rewrite; score it 0–10.
 *
 * A proposal is created only if the validation score is ≥ 7 (VALIDATION_THRESHOLD).
 *
 * Prompts are evolved using structured JSON output so they are easy to parse
 * and validate before being handed to the pipeline for trialing.
 */

import type { UpgradeTarget, UpgradeProposal } from './upgrade-types.js'
import type { IMemory } from '@cassicore/foundation'
import type { ILogger } from '@cassicore/foundation'


/** Minimum validation score to proceed to trial (out of 10). */
const VALIDATION_THRESHOLD = 7

/** LLM temperature for critique (deterministic-ish). */
const CRITIQUE_TEMPERATURE = 0.25

/** LLM temperature for improvement (slightly creative). */
const IMPROVE_TEMPERATURE = 0.45

/** LLM temperature for validation (deterministic). */
const VALIDATE_TEMPERATURE = 0.15

/** Max tokens for each step. */
const MAX_TOKENS_CRITIQUE = 512
const MAX_TOKENS_IMPROVE = 1024
const MAX_TOKENS_VALIDATE = 512


interface CritiqueResult {
  summary: string
  weaknesses: string[]
}

interface ImproveResult {
  rewritten: string
  rationale: string
}

interface ValidateResult {
  score: number           // 0–10
  addressedWeaknesses: boolean
  regressionRisk: string  // description of any potential regression
  verdict: string         // 1-sentence summary
}


export class PromptEvolver {
  constructor(
    private readonly logger: ILogger,
  ) {}

  /**
   * Run the full three-step evolution pipeline for a single upgrade target.
   *
   * @param target   The UpgradeTarget to improve.
   * @param current  The current live value (string for prompts, object for configs).
   * @param memory   The IMemory object (used to access the LLM).
   * @returns An UpgradeProposal if the validation gate passes, or null.
   */
  async evolve(
    target: UpgradeTarget,
    current: string | Record<string, unknown>,
    memory: IMemory,
  ): Promise<UpgradeProposal | null> {
    const currentStr = typeof current === 'string' ? current : JSON.stringify(current, null, 2)

    this.logger.debug('PromptEvolver: starting evolution', { targetId: target.id })

    const critique = await this.critique(target, currentStr, memory)
    if (!critique) {
      this.logger.debug('PromptEvolver: critique step failed', { targetId: target.id })
      return null
    }

    const improved = await this.improve(target, currentStr, critique, memory)
    if (!improved) {
      this.logger.debug('PromptEvolver: improve step failed', { targetId: target.id })
      return null
    }

    const validation = await this.validate(target, currentStr, improved, critique, memory)
    if (!validation) {
      this.logger.debug('PromptEvolver: validate step failed', { targetId: target.id })
      return null
    }

    if (validation.score < VALIDATION_THRESHOLD) {
      this.logger.debug('PromptEvolver: proposal below validation threshold', {
        targetId: target.id,
        score: validation.score,
        threshold: VALIDATION_THRESHOLD,
        verdict: validation.verdict,
      })
      return null
    }

    const after: string | Record<string, unknown> =
      target.kind === 'config' ? parseConfigOrFallback(improved.rewritten, current) : improved.rewritten

    const proposal: UpgradeProposal = {
      id: `proposal-${Date.now()}-${Math.random().toString(36).slice(2, 7)}`,
      targetId: target.id,
      moduleId: target.moduleId,
      generatedAt: Date.now(),
      critique: critique.summary,
      weaknesses: critique.weaknesses,
      before: current,
      after,
      rationale: improved.rationale,
      validationScore: validation.score,
      validationReason: validation.verdict,
    }

    this.logger.info('PromptEvolver: proposal passed validation gate', {
      targetId: target.id,
      score: validation.score,
      regressionRisk: validation.regressionRisk,
    })

    return proposal
  }


  private async critique(
    target: UpgradeTarget,
    currentValue: string,
    memory: IMemory,
  ): Promise<CritiqueResult | null> {
    const prompt = buildCritiquePrompt(target, currentValue)
    const raw = await callLLM(memory, prompt, CRITIQUE_TEMPERATURE, MAX_TOKENS_CRITIQUE)
    if (!raw) return null
    return parseCritiqueJSON(raw)
  }


  private async improve(
    target: UpgradeTarget,
    currentValue: string,
    critique: CritiqueResult,
    memory: IMemory,
  ): Promise<ImproveResult | null> {
    const prompt = buildImprovePrompt(target, currentValue, critique)
    const raw = await callLLM(memory, prompt, IMPROVE_TEMPERATURE, MAX_TOKENS_IMPROVE)
    if (!raw) return null
    return parseImproveJSON(raw)
  }


  private async validate(
    target: UpgradeTarget,
    originalValue: string,
    improved: ImproveResult,
    critique: CritiqueResult,
    memory: IMemory,
  ): Promise<ValidateResult | null> {
    const prompt = buildValidatePrompt(target, originalValue, improved.rewritten, critique)
    const raw = await callLLM(memory, prompt, VALIDATE_TEMPERATURE, MAX_TOKENS_VALIDATE)
    if (!raw) return null
    return parseValidateJSON(raw)
  }
}


/**
 * @dep callers: validate (core/intelligence/ai-engineer/prompt-evolver.ts), improve (core/intelligence/ai-engineer/prompt-evolver.ts), critique (core/intelligence/ai-engineer/prompt-evolver.ts)
 * @dep calls: complete
 * @dep module: Ai-engineer
 * @dep risk: LOW | 3 callers, 0 flows, 1 module
 */

async function callLLM(
  memory: IMemory,
  prompt: string,
  temperature: number,
  maxTokens: number,
): Promise<string | null> {
  try {
    const llm = (memory as any).llm
    if (!llm) return null
    const response = await llm.complete(prompt, {
      temperature,
      maxTokens,
      systemPrompt: 'You are an expert AI systems engineer. Respond only with valid JSON.',
      source: 'ai-engineer:prompt-evolver',
      trigger: 'improvement',
    })
    return response?.content ?? null
  } catch {
    return null
  }
}


function buildCritiquePrompt(target: UpgradeTarget, currentValue: string): string {
  return `You are reviewing a cognitive program used by an AI intelligence module.

## Module
Module: ${target.moduleId}
Target: ${target.name}
Purpose: ${target.description}

## Current Value
\`\`\`
${currentValue}
\`\`\`

## Your Task
Analyse this cognitive program and identify its weaknesses. Focus on:
- Ambiguities that could lead to inconsistent or low-quality outputs
- Missing directives that would improve the module's primary purpose
- Over-prescription that might constrain genuinely useful variation
- Structural issues that reduce effectiveness

Respond with valid JSON only:
{
  "summary": "One sentence summarising the main problem area.",
  "weaknesses": [
    "Weakness 1 — specific and actionable",
    "Weakness 2 — specific and actionable"
  ]
}

Identify 2–4 weaknesses. Be specific — generic feedback like "could be clearer" is not useful.`
}

function buildImprovePrompt(
  target: UpgradeTarget,
  currentValue: string,
  critique: CritiqueResult,
): string {
  return `You are rewriting a cognitive program for an AI intelligence module.

## Module
Module: ${target.moduleId}
Target: ${target.name}
Purpose: ${target.description}

## Current Value
\`\`\`
${currentValue}
\`\`\`

## Identified Weaknesses
${critique.weaknesses.map((w, i) => `${i + 1}. ${w}`).join('\n')}

## Your Task
Rewrite this cognitive program to address the weaknesses listed above.

Rules:
- Preserve what is already working well
- Address each identified weakness directly
- Do NOT add unnecessary length — be as concise as the task allows
- Keep the same general structure and intent unless a weakness is structural
- If the value is a prompt, the rewrite must remain usable as a system prompt

Respond with valid JSON only:
{
  "rewritten": "The complete rewritten value, ready to use as a drop-in replacement.",
  "rationale": "One sentence explaining the key change and why it addresses the main weakness."
}`
}

function buildValidatePrompt(
  target: UpgradeTarget,
  originalValue: string,
  rewrittenValue: string,
  critique: CritiqueResult,
): string {
  return `You are validating a proposed improvement to a cognitive program.

## Module
Module: ${target.moduleId}
Target: ${target.name}
Purpose: ${target.description}

## Original
\`\`\`
${originalValue}
\`\`\`

## Proposed Rewrite
\`\`\`
${rewrittenValue}
\`\`\`

## Weaknesses the rewrite was supposed to address
${critique.weaknesses.map((w, i) => `${i + 1}. ${w}`).join('\n')}

## Your Task
Evaluate the proposed rewrite as an adversarial reviewer. 
Consider:
1. Does the rewrite actually address the listed weaknesses?
2. Has it introduced new problems not present in the original?
3. Is it likely to improve the module's actual outputs?

Score it 0–10 where:
  0–4 = worse than or equivalent to original (do not use)
  5–6 = minor improvement but not worth the risk of changing a live system
  7–8 = clear improvement with manageable regression risk
  9–10 = significant improvement with minimal regression risk

Respond with valid JSON only:
{
  "score": 7,
  "addressedWeaknesses": true,
  "regressionRisk": "Short description of any regression concern, or 'none' if none.",
  "verdict": "One sentence summary of your decision."
}`
}


function parseCritiqueJSON(raw: string): CritiqueResult | null {
  try {
    const parsed = extractJSON(raw)
    if (
      typeof parsed?.summary === 'string' &&
      Array.isArray(parsed?.weaknesses) &&
      parsed.weaknesses.every((w: unknown) => typeof w === 'string')
    ) {
      return { summary: parsed.summary, weaknesses: parsed.weaknesses }
    }
  } catch {}
  return null
}

function parseImproveJSON(raw: string): ImproveResult | null {
  try {
    const parsed = extractJSON(raw)
    if (typeof parsed?.rewritten === 'string' && typeof parsed?.rationale === 'string') {
      return { rewritten: parsed.rewritten, rationale: parsed.rationale }
    }
  } catch {}
  return null
}

function parseValidateJSON(raw: string): ValidateResult | null {
  try {
    const parsed = extractJSON(raw)
    if (
      typeof parsed?.score === 'number' &&
      parsed.score >= 0 &&
      parsed.score <= 10 &&
      typeof parsed?.verdict === 'string'
    ) {
      return {
        score: parsed.score,
        addressedWeaknesses: parsed.addressedWeaknesses === true,
        regressionRisk: typeof parsed?.regressionRisk === 'string' ? parsed.regressionRisk : 'unknown',
        verdict: parsed.verdict,
      }
    }
  } catch {}
  return null
}

/**
 * Extract the first JSON object from a possibly-prefixed LLM response.
 * Handles cases where the model wraps the JSON in markdown code fences.
 * @dep callers: parseConfigOrFallback (core/intelligence/ai-engineer/prompt-evolver.ts), parseValidateJSON (core/intelligence/ai-engineer/prompt-evolver.ts), parseImproveJSON (core/intelligence/ai-engineer/prompt-evolver.ts), parseCritiqueJSON (core/intelligence/ai-engineer/prompt-evolver.ts)
 * @dep calls: trim
 * @dep module: Ai-engineer
 * @dep risk: MEDIUM | 4 callers, 0 flows, 1 module
 */
function extractJSON(raw: string): Record<string, unknown> | null {
  // Strip markdown code fences
  const stripped = raw.replace(/```(?:json)?/g, '').replace(/```/g, '').trim()
  // Find first { ... }
  const start = stripped.indexOf('{')
  const end = stripped.lastIndexOf('}')
  if (start === -1 || end === -1 || end <= start) return null
  return JSON.parse(stripped.slice(start, end + 1)) as Record<string, unknown>
}

/**
 * For config-kind targets, attempt to parse the rewritten value as JSON.
 * Falls back to the original config if parsing fails.
 */
function parseConfigOrFallback(
  rewritten: string,
  original: string | Record<string, unknown>,
): Record<string, unknown> {
  try {
    const parsed = extractJSON(rewritten)
    if (parsed && typeof parsed === 'object') return parsed
  } catch {}
  // If parsing fails, return original (pipeline will skip this proposal)
  return typeof original === 'object' ? original : {}
}
