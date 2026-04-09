import type { Affect, AffectConfig, AffectLabel, AffectState } from './types.js'
import { AFFECT_DEFAULTS } from './types.js'


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


export class AffectRegister {
  private valence: number
  private arousal: number
  private lastDecay: number
  private config: AffectConfig

  constructor(config?: Partial<AffectConfig>) {
    this.config = { ...AFFECT_DEFAULTS, ...config }
    this.valence = this.config.baselineValence
    this.arousal = this.config.baselineArousal
    this.lastDecay = Date.now()
  }

  getState(): AffectState {
    this.decay()
    return {
      valence: this.valence,
      arousal: this.arousal,
      label: resolveLabel({ valence: this.valence, arousal: this.arousal }),
      updatedAt: Date.now(),
    }
  }

  getAffect(): Affect {
    this.decay()
    return { valence: this.valence, arousal: this.arousal }
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
      this.valence = lerp(this.valence, avgValence, this.config.activationAbsorption)
      this.arousal = lerp(this.arousal, avgArousal, this.config.activationAbsorption)
    }

    if (outcome === 'success') {
      this.valence = lerp(this.valence, 0.6, this.config.signalAbsorption)
    } else if (outcome === 'failure') {
      this.valence = lerp(this.valence, -0.5, this.config.signalAbsorption)
      this.arousal = lerp(this.arousal, 0.6, this.config.signalAbsorption)
    }
  }

  absorbSignal(signal: { valence?: number; arousal?: number }): void {
    this.decay()
    if (signal.valence !== undefined) {
      this.valence = lerp(this.valence, signal.valence, this.config.signalAbsorption)
    }
    if (signal.arousal !== undefined) {
      this.arousal = lerp(this.arousal, signal.arousal, this.config.signalAbsorption)
    }
  }

  private decay(): void {
    const now = Date.now()
    const elapsedMinutes = (now - this.lastDecay) / 60_000
    if (elapsedMinutes < 0.1) return

    const factor = Math.pow(1 - this.config.decayRate, elapsedMinutes)
    this.valence = lerp(this.config.baselineValence, this.valence, factor)
    this.arousal = lerp(this.config.baselineArousal, this.arousal, factor)
    this.lastDecay = now
  }
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


function lerp(a: number, b: number, t: number): number {
  return a + (b - a) * t
}

function clamp(value: number, min: number, max: number): number {
  return Math.max(min, Math.min(max, value))
}
