/**
 * TYPE STUB — field-encoder/types.ts (core/intelligence/field-encoder/types.ts).
 *
 * Faithful type surface for the symbol mnemic-field consumes: `MindFieldEncoder`
 * (the overhaul session's direct-encoding seam). **TYPE-ONLY — NO journal hooks.**
 *
 * Coordination handshake (CASSI-MIND-PLAN §7): the overhaul session is re-wiring
 * Mnemic Field into a journal with MindFieldEncoder hooks at store/update/delete/
 * connect/spike/consolidate. Per the agreed boundary-first default, this stub
 * keeps `setFieldEncoder`/`fieldDepositsSent`/`drainFieldDeposits` compiling, and
 * the store-port (src/ports/store.ts) exposes the future onWrite observer seam —
 * but NO hooks are implemented here. When the overhaul's field-encoder publishes,
 * re-point this stub to the real package.
 */
import type { EngramCreate, MnemicSynapse } from '../../../../types.js'

/**
 * The neuron-like direct-encoding seam: a brain write becomes a two-fluid
 * field deposition at the engram's own cylindrical (x, y, z) coordinates.
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
