import type { EngramCreate, MnemicSynapse } from '@cassicore/mnemic-field';

/**
 * The neuron-like direct-encoding seam: a brain write becomes a two-fluid
 * field deposition at the engram's own cylindrical (x, y, z) coordinates.
 *
 * `encode` / `depositEngram` / `depositSynapse` return charge tuples the
 * field engine consumes. The default is a Noop encoder — the brain runs
 * bit-identical with or without the field attached (the Stage-1 parity
 * guarantee by construction).
 *
 * contract: encode() must be side-effect-free, never throw, and never
 * depend on harness state; a failure must be swallowed by the caller.
 */
export interface MindFieldEncoder {
  /** Whether deposits flow right now (false => no-op, parity mode). */
  isOpen(): boolean;

  /** Total deposits sent (telemetry/smoke). */
  depositsSent(): number;

  /** Open or close the deposit channel (shadow-bridge control). */
  setOpen(open: boolean): void;

  /** Called for every engram write. Return true if the encoder consumed it. */
  encode(e: EngramCreate): boolean;

  /** [x, y, z, cy, ci, sigma] — a point charge at the engram's field coords. */
  depositEngram(e: EngramCreate): [number, number, number, number, number, number];

  /** [x, y, z, cy, ci, sigma] — a synapse thread charge. */
  depositSynapse(s: MnemicSynapse): [number, number, number, number, number, number];
}
