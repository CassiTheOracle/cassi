import type { EngramType, EngramCreate, MnemicSynapse, SynapseType } from '@cassicore/mnemic-field';
import type { MindFieldEncoder } from './types.js';

/**
 * The neuron-like encoding model: how a brain event becomes a two-fluid
 * field deposition.
 *
 * The Mnemic Field already stores engrams in a cylindrical (r, theta, t)
 * space in [-1, 1]^3 — which IS the field-engine grid. So the encoding is
 * a charge deposition at the engram's own coordinates, exactly as a neuron
 * deposits charge onto its field. No hash, no re-mapping: the brain state
 * and the field state share one coordinate system.
 *
 * charge (cy, ci, sigma) is derived from fixed lookups so the mapping is
 * deterministic and reproducible (the numpy-gate culture): same engram
 * type → same charge envelope, forever.
 */
export class StandardMindFieldEncoder implements MindFieldEncoder {
  private readonly open = true;
  private deposits = 0;

  /** nodeType → (yang charge, yin charge, envelope sigma). */
  private static readonly TYPE_CHARGE: Partial<Record<EngramType, [number, number, number]>> = {
    fact: [1.618, 1.0, 2.0],
    episode: [1.0, 1.618, 2.5],
    decision: [1.618, 0.618, 2.0],
    pattern: [0.618, 1.618, 2.0],
    abstraction: [0.382, 1.618, 3.0],
    goal: [1.618, 0.382, 1.5],
    outcome: [1.0, 1.0, 2.0],
    concern: [0.382, 1.618, 3.0],
    anomaly: [0.382, 0.618, 3.0],
    tool: [0.618, 0.382, 1.0],
    message: [1.0, 1.0, 1.0],
  };
  private static readonly DEFAULT_CHARGE: [number, number, number] = [1.0, 1.0, 2.0];

  isOpen(): boolean {
    return this.open;
  }

  depositsSent(): number {
    return this.deposits;
  }

  setOpen(_open: boolean): void {
    // Standard encoder is always open; a future gate-shaped encoder will
    // modulate openness from the field's (1-q) state (Stage 2).
  }

  encode(e: EngramCreate): boolean {
    return true;
  }

  depositEngram(e: EngramCreate): [number, number, number, number, number, number] {
    const [cy, ci, sigma] = this.chargeFor(e.nodeType);
    const pow = Math.max(0.05, Math.min(1.5, this.powerFor(e.nodeType)));
    const x = e.x ?? 0;
    const y = e.y ?? 0;
    const z = e.z ?? 0;
    this.deposits += 1;
    return [x, y, z, cy * pow, ci * pow, sigma];
  }

  depositSynapse(s: MnemicSynapse): [number, number, number, number, number, number] {
    const [cy, ci, sigma] = this.chargeFor(s.edgeType);
    this.deposits += 1;
    // Synapses are threads; deposit a small thread-charge near the tonic
    // center (consolidation region) — position resolution comes in Stage 2.
    return [0, 0, 0.3, cy * 0.6, ci * 0.6, sigma];
  }

  private chargeFor(t: EngramType | SynapseType): [number, number, number] {
    return StandardMindFieldEncoder.TYPE_CHARGE[t as EngramType] ?? StandardMindFieldEncoder.DEFAULT_CHARGE;
  }

  private powerFor(t: EngramType): number {
    // Low-level nodes (message, tool) are thin and coherent; abstractions
    // and goals are broad but rarer. A monotone function of type rank.
    const rank = {
      message: 0.1, tool: 0.25, file: 0.3,
      outcome: 0.6, decision: 0.8, fact: 0.9, pattern: 1.0,
      goal: 0.9, abstraction: 1.1, concern: 0.8, anomaly: 0.7,
    } as Record<string, number>;
    return rank[t] ?? 0.5;
  }
}

export class NoopMindFieldEncoder implements MindFieldEncoder {
  isOpen(): boolean {
    return false;
  }
  depositsSent(): number {
    return 0;
  }
  setOpen(_open: boolean): void {}
  encode(_e: EngramCreate): boolean {
    return false;
  }
  depositEngram(_e: EngramCreate): [number, number, number, number, number, number] {
    return [0, 0, 0, 0, 0, 0];
  }
  depositSynapse(_s: MnemicSynapse): [number, number, number, number, number, number] {
    return [0, 0, 0, 0, 0, 0];
  }
}
