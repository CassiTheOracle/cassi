package dev.cassicraft.game.genesis;

import dev.cassicraft.domain.engine.TwoFluidSolver;
import dev.cassicraft.domain.snapshot.FieldSnapshot;
import dev.cassicraft.domain.snapshot.SnapshotPublisher;
import dev.cassicraft.domain.thread.CassiFieldThread;

/**
 * The Q4-lane surface-formation genesis — the game-side hand that steers a denser
 * foundation into the otherwise-uniform field (the measured falsification of
 * {@code SurfaceEmergenceMain}: from t≈1.5 to t≈80 the two-fluid is a uniform
 * ~72–75%-solid sponge with no vertical density plane). This is the corpus's
 * condensation vocabulary put through the write lane: a body is "the merge
 * lineage condensing under the order-selective coherence gate"
 * ({@code atmosphere-orbits-auroras.md} §2.2), and the lane's matched
 * {@code dEY = φ·dEI} write is a <b>coherence-restoring</b> deposit
 * ({@code wiring-requests/q4-write-lane-design.md} §3 — the stilling write at
 * the Yin—Yang ratio). The genesis is the bounded sequence that lets the field
 * organize a denser lower body.
 *
 * <p><b>Honest by construction.</b> Every write goes through the REAL lane
 * ({@link CassiFieldThread#submitPerturbation}) — never directly into the
 * solver, never a block write, never a mint. The magnitudes are matched
 * (coherence-restoring → the overdraw component {@code dEY − φ·dEI ≈ 0}), so
 * the only cap that can engage is the no-mint bound, and the requested
 * magnitudes are chosen <b>well within</b> it (the measured settled sponge
 * carries {@code q ≈ 0.7 → sqrt(q) ≈ 0.84}, so the no-mint cap is ≈ φ⁻¹·0.84
 * ≈ 0.52 per channel; the genesis requests ≈ 10 % of it). <b>Rate-limited</b>
 * — the lane drains at most one perturbation per job (newest-wins), and this
 * coordinator submits each write <em>and waits for a publish generation
 * advance</em> (the drain) before the next, so the full sequence lands as one
 * distinct bound per job — the natural throttle made explicit.
 * <b>Deterministic</b> — the positions, count, and magnitudes are fixed
 * constants (no RNG), so same seed → same drain order → same field outcome.
 *
 * <p>The honesty caps' telemetry is read from the worker's
 * {@link CassiFieldThread#perturbationClampCount()}: a clamp count above the
 * per-design expected level would mean the genesis exceeded its own bounds — a
 * design bug to fix, never a counter to silence. The probe and gate assert the
 * expected level (0 for this matched-φ design).
 */
public final class SurfaceGenesis {

	/** How many bounded writes the genesis submits (a fixed, documented count). */
	public static final int WRITE_COUNT = 32;
	/** The coherence-restoring Yin—Yang write ratio — {@code dEY = φ·dEI} so the
	 * overdraw component {@code dEY − φ·dEI = 0} (a stilling write,
	 * {@code q4-write-lane-design.md} §3; {@code coherence-magic.md} §4.3 — a
	 * perfect φ-lock has no overdraw to clamp). */
	public static final double RESTORE_RATIO = TwoFluidSolver.PHI;
	/** The requested EY magnitude per write — {@code 0.05} is ≈ 10 % of the
	 * measured no-mint cap (≈ 0.52 for the settled sponge's {@code sqrt(q)≈0.84})
	 * and ≈ 8 % of the measured settled EY amplitude, so the lane must not clamp
	 * (the gate asserts this stays 0). */
	public static final double D_EY = 0.05;
	/** The matched EI magnitude — {@code D_EY / φ}, the coherence-restoring leg. */
	public static final double D_EI = D_EY / RESTORE_RATIO;
	/** The Gaussian falloff radius (cells) — a single-cell-ish locality, the Q4
	 * gate's own {@code radius=3} scale. */
	public static final int RADIUS = 3;
	/** The bottom of the deposit band — one third up the anchor's lower half
	 * (box y from anchorY−96 to anchorY+96), the densest foundation stratum. */
	public static final int Y_BAND_LO = -24;
	/** The top of the deposit band — the highest deposit stays below the anchor
	 * ({@code 0}), so the deposit is a lower-body foundation, not a ceiling. */
	public static final int Y_BAND_HI = 0;
	/** Per-write drain-await timeout — the lane is CPU-bound at ≈ 0.23 t/s, so a
	 * job (64 steps ≈ 0.064 t) plus 5 ms sleep lands well inside a few seconds. */
	public static final long DRAIN_TIMEOUT_MS = 30_000;

	private final CassiFieldThread worker;
	private final SnapshotPublisher publisher;
	private final double[] anchor;

	public SurfaceGenesis(CassiFieldThread worker, SnapshotPublisher publisher, double[] anchor) {
		this.worker = worker;
		this.publisher = publisher;
		this.anchor = anchor.clone();
	}

	/**
	 * Run the bound, rate-limited genesis through the real write lane: submit one
	 * coherence-restoring deposit per job, waiting for the drain (a publish
	 * generation advance) between submissions so newest-wins coalescing never
	 * collapses the sequence. Returns the writes actually submitted ({@code ==
	 * WRITE_COUNT} when every write landed).
	 *
	 * @throws InterruptedException if awaiting a drain is interrupted
	 */
	public int run() throws InterruptedException {
		int lastGen = publisher.generation();
		for (int i = 0; i < WRITE_COUNT; i++) {
			int y = Y_BAND_LO + (i * (Y_BAND_HI - Y_BAND_LO)) / (WRITE_COUNT - 1); // even spread up the band
			double wy = anchor[1] + y;
			worker.submitPerturbation(anchor[0], wy, anchor[2], D_EY, D_EI, RADIUS);
			lastGen = awaitGenerationAfter(publisher, lastGen);
		}
		return WRITE_COUNT;
	}

	private static int awaitGenerationAfter(SnapshotPublisher pub, int lastGen) throws InterruptedException {
		long deadline = System.currentTimeMillis() + DRAIN_TIMEOUT_MS;
		while (System.currentTimeMillis() < deadline) {
			FieldSnapshot s = pub.freshest();
			if (s != null && s.generation() > lastGen) {
				return s.generation();
			}
			Thread.sleep(5);
		}
		throw new IllegalStateException("genesis drain never advanced past generation " + lastGen);
	}
}
