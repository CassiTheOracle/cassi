import type { Affect, AffectConfig, AffectLabel, AffectState } from './types.js'
import { AFFECT_DEFAULTS } from './types.js'
import { lerp, clamp } from '@cassicore/utils'


interface MarkerSet {
  patterns: RegExp[]
  valenceShift: number
  arousalShift: number
}

const MARKER_SETS: MarkerSet[] = [
  {
    patterns: [/\bsucce(ss|eded|ssful)\b/i, /\bfixed\b/i, /\bresolved\b/i, /\bworking\b/i, /\bpassed\b/i, /\bcompleted?\b/i],
    valenceShift: 0.4,
    arousalShift: 0.2,
  },
  {
    patterns: [/\bperfect(ly)?\b/i, /\bexactly\b/i, /\bclean\b/i, /\belegant\b/i, /\bbeautiful\b/i],
    valenceShift: 0.5,
    arousalShift: 0.1,
  },
  {
    patterns: [/\bfail(ed|ure|s|ing)?\b/i, /\bbroke[n]?\b/i, /\bcrash(ed|es|ing)?\b/i, /\berror\b/i],
    valenceShift: -0.5,
    arousalShift: 0.4,
  },
  {
    patterns: [/\bagain\b/i, /\bstill\b/i, /\bkeeps?\b/i, /\bwon'?t\b/i, /\bcan'?t\b/i],
    valenceShift: -0.3,
    arousalShift: 0.3,
  },
  {
    patterns: [/\bunclear\b/i, /\bconfus(ed|ing)\b/i, /\bunsure\b/i, /\bunknown\b/i, /\bweird\b/i],
    valenceShift: -0.2,
    arousalShift: 0.2,
  },
  {
    patterns: [/\bdiscover(ed|y)?\b/i, /\bfound\b.*\b(that|new|interesting)\b/i, /\binsight\b/i, /\bsurpris(e|ing)\b/i],
    valenceShift: 0.3,
    arousalShift: 0.4,
  },
  {
    patterns: [/\blearned?\b/i, /\bunderstoo?d\b/i, /\breali[sz]e[d]?\b/i],
    valenceShift: 0.2,
    arousalShift: 0.15,
  },
  {
    patterns: [/\burgent(ly)?\b/i, /\bcritical\b/i, /\bimmediate(ly)?\b/i, /\basap\b/i, /\bblocked\b/i],
    valenceShift: -0.1,
    arousalShift: 0.6,
  },
  {
    patterns: [/\bthanks?\b/i, /\bthank\s?you\b/i, /\bappreciate\b/i, /\bgrateful\b/i],
    valenceShift: 0.4,
    arousalShift: 0.05,
  },
  {
    patterns: [/\bimplement\b/i, /\bship\b/i, /\bdeliver\b/i, /\bdeploy\b/i, /\brelease\b/i],
    valenceShift: 0.1,
    arousalShift: 0.3,
  },
  {
    patterns: [/\bunexpect(ed)?\b/i, /\bstrange(ly)?\b/i, /\bodd(ly)?\b/i, /\bwhat\?/i],
    valenceShift: 0,
    arousalShift: 0.35,
  },
]

export function attune(content: string): Affect {
  let valence = 0
  let arousal = 0
  let matchCount = 0

  for (const set of MARKER_SETS) {
    for (const pattern of set.patterns) {
      if (pattern.test(content)) {
        valence += set.valenceShift
        arousal += set.arousalShift
        matchCount++
        break
      }
    }
  }

  if (matchCount === 0) return { valence: 0, arousal: 0 }

  return {
    valence: clamp(valence / Math.max(matchCount, 1), -1, 1),
    arousal: clamp(arousal / Math.max(matchCount, 1), 0, 1),
  }
}


interface DecayedPair { valence: number; arousal: number }

function decayPair(
  valence: number, arousal: number,
  rate: number, elapsedMinutes: number,
  negMod: number, baselineV: number, baselineA: number,
): DecayedPair {
  const baseFactor = Math.pow(1 - rate, elapsedMinutes)
  const valenceFactor = valence < 0
    ? Math.pow(1 - rate * negMod, elapsedMinutes)
    : baseFactor
  return {
    valence: lerp(baselineV, valence, valenceFactor),
    arousal: lerp(baselineA, arousal, baseFactor),
  }
}


export class AffectRegister {
  private emotionValence: number
  private emotionArousal: number
  private moodValence: number
  private moodArousal: number
  private lastDecay: number
  private config: AffectConfig

  constructor(config?: Partial<AffectConfig>) {
    this.config = { ...AFFECT_DEFAULTS, ...config }
    this.emotionValence = this.config.baselineValence
    this.emotionArousal = this.config.baselineArousal
    this.moodValence = this.config.baselineValence
    this.moodArousal = this.config.baselineArousal
    this.lastDecay = Date.now()
  }

  getState(): AffectState {
    this.decay()
    const w = this.config.emotionWeight
    const valence = w * this.emotionValence + (1 - w) * this.moodValence
    const arousal = w * this.emotionArousal + (1 - w) * this.moodArousal
    return {
      valence,
      arousal,
      dominance: computeDominance(valence, arousal),
      label: resolveLabel({ valence, arousal }),
      updatedAt: Date.now(),
    }
  }

  getAffect(): Affect {
    this.decay()
    const w = this.config.emotionWeight
    return {
      valence: w * this.emotionValence + (1 - w) * this.moodValence,
      arousal: w * this.emotionArousal + (1 - w) * this.moodArousal,
    }
  }

  absorbActivation(engrams: Array<{ affect: Affect | null; charge: number }>, outcome?: string): void {
    this.decay()

    let totalValence = 0
    let totalArousal = 0
    let totalWeight = 0

    for (const e of engrams) {
      if (!e.affect) continue
      totalValence += e.affect.valence * e.charge
      totalArousal += e.affect.arousal * e.charge
      totalWeight += e.charge
    }

    if (totalWeight > 0) {
      const avgValence = totalValence / totalWeight
      const avgArousal = totalArousal / totalWeight
      const moodRate = this.config.activationAbsorption * this.config.moodAbsorptionRatio
      this.emotionValence = lerp(this.emotionValence, avgValence, this.config.activationAbsorption)
      this.emotionArousal = lerp(this.emotionArousal, avgArousal, this.config.activationAbsorption)
      this.moodValence = lerp(this.moodValence, avgValence, moodRate)
      this.moodArousal = lerp(this.moodArousal, avgArousal, moodRate)
    }

    if (outcome === 'success') {
      this.emotionValence = lerp(this.emotionValence, 0.6, this.config.signalAbsorption)
    } else if (outcome === 'failure') {
      this.emotionValence = lerp(this.emotionValence, -0.5, this.config.signalAbsorption)
      this.emotionArousal = lerp(this.emotionArousal, 0.6, this.config.signalAbsorption)
    }
  }

  absorbSignal(signal: { valence?: number; arousal?: number }): void {
    this.decay()
    const moodRate = this.config.signalAbsorption * this.config.moodAbsorptionRatio
    if (signal.valence !== undefined) {
      this.emotionValence = lerp(this.emotionValence, signal.valence, this.config.signalAbsorption)
      this.moodValence = lerp(this.moodValence, signal.valence, moodRate)
    }
    if (signal.arousal !== undefined) {
      this.emotionArousal = lerp(this.emotionArousal, signal.arousal, this.config.signalAbsorption)
      this.moodArousal = lerp(this.moodArousal, signal.arousal, moodRate)
    }
  }

  /**
   * Absorb a resonant affect signal from the memory bridge.
   *
   * Resonant signals are grounded in actual model/memory interaction,
   * so they carry more weight than text-based attune() signals.
   * The blend factor controls how much resonance overrides text-based affect.
   *
   * The resonant signal also shifts mood more strongly because it reflects
   * sustained computational reality, not momentary word choice.
   */
  absorbResonantSignal(
    signal: { valence: number; arousal: number },
    blendFactor: number = 0.5,
  ): void {
    this.decay()

    // Resonant signals absorb at a higher rate than text signals
    const resonantAbsorption = this.config.signalAbsorption * (1 + blendFactor)
    const resonantMoodRate = resonantAbsorption * this.config.moodAbsorptionRatio * 1.5

    this.emotionValence = lerp(this.emotionValence, signal.valence, resonantAbsorption)
    this.emotionArousal = lerp(this.emotionArousal, signal.arousal, resonantAbsorption)

    // Mood absorbs resonant signals more readily — they reflect computational ground truth
    this.moodValence = lerp(this.moodValence, signal.valence, resonantMoodRate)
    this.moodArousal = lerp(this.moodArousal, signal.arousal, resonantMoodRate)
  }

  private decay(): void {
    const now = Date.now()
    const elapsedMinutes = (now - this.lastDecay) / 60_000
    if (elapsedMinutes < 0.1) return

    const negMod = this.config.negativeDecayModifier
    const bv = this.config.baselineValence
    const ba = this.config.baselineArousal

    const emotion = decayPair(
      this.emotionValence, this.emotionArousal,
      this.config.decayRate, elapsedMinutes, negMod, bv, ba,
    )
    this.emotionValence = emotion.valence
    this.emotionArousal = emotion.arousal

    const mood = decayPair(
      this.moodValence, this.moodArousal,
      this.config.moodDecayRate, elapsedMinutes, negMod, bv, ba,
    )
    this.moodValence = mood.valence
    this.moodArousal = mood.arousal

    this.lastDecay = now
  }
}

export function computeDominance(valence: number, arousal: number): number {
  return clamp(0.5 + valence * 0.5 - arousal * 0.5, 0, 1)
}

export function resolveLabel(affect: Affect): AffectLabel {
  const { valence: v, arousal: a } = affect

  if (Math.abs(v) < 0.15 && a < 0.3) return 'neutral'

  if (v > 0.3) {
    if (a > 0.5) return 'excited'
    if (a > 0.3) return 'engaged'
    if (v > 0.5) return 'delighted'
    return 'content'
  }

  if (v > 0) {
    if (a < 0.2) return 'calm'
    return 'warm'
  }

  if (v < -0.3) {
    if (a > 0.5) return 'alarmed'
    if (a > 0.3) return 'frustrated'
    return 'melancholy'
  }

  if (a > 0.4) return 'uneasy'
  if (a < 0.2) return 'fatigued'
  return 'neutral'
}

export function emotionalIntensity(affect: Affect): number {
  return Math.max(Math.abs(affect.valence), affect.arousal)
}

export function affectSimilarity(a: Affect, b: Affect): number {
  const dv = a.valence - b.valence
  const da = a.arousal - b.arousal
  return 1 - Math.sqrt(dv * dv + da * da) / Math.sqrt(4 + 1)
}
