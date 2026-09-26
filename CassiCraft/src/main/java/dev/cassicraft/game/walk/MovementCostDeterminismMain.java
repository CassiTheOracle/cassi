package dev.cassicraft.game.walk;

import dev.cassicraft.domain.snapshot.FieldSnapshot;
import dev.cassicraft.domain.snapshot.SnapshotPublisher;
import dev.cassicraft.domain.thread.CassiFieldThread;
import dev.cassicraft.domain.thread.KernelLoader;
import dev.cassicraft.game.sampler.Quantizer;

/**
 * Headless determinism gate for the movement-cost read (corpus-map §4 step 4;
 * the-walk §4c — a <b>hard</b> gate: same ground, same field state → same
 * stride's cost). Runs under the game source set with no live client. It replays
 * the publish seam — a {@link CassiFieldThread} from a fixed seed, a {@link
 * Quantizer#sampleReading} at a fixed position, and a fixed step direction + load
 * through {@link MovementCost#strideCost} — then compares the readout.
 *
 * <p>Exit code 0 = green. Assertions:
 * <ol>
 *   <li>Two measurements of the <b>same</b> settled field produce the
 *       <b>identical</b> stride cost (measurement determinism across
 *       sample → cost). The two same-seed arms share <b>one</b> settle (the
 *       measurement is a pure read of the settled snapshot — it only calls
 *       {@link Quantizer#sampleReading} + {@link MovementCost#strideCost}, never
 *       a mutation), so the shared settle has nothing to re-settle: the run-2
 *       arm replays the same frozen field and must equal run-1. Settle
 *       determinism itself is not asserted here — it is hard-pinned
 *       byte-identically by the domain-harness gate (and by every mutating gate
 *       that still boots fresh).</li>
 *   <li>A different seed produces a <b>different</b> cost (not vacuous — the
 *       seed-B arm still boots a fresh settle).</li>
 * </ol>
 */
public final class MovementCostDeterminismMain {

	private static final long SEED_A = 42L;
	private static final long SEED_B = 43L;
	private static final long SNAPSHOT_TIMEOUT_MS = 10_000;

	/** The fixed block position, step direction, and load the gate reads. */
	private static final int X = 10, Y = 60, Z = 5;
	private static final double STEP_X = 1.0, STEP_Y = 0.0, STEP_Z = 0.0;
	private static final float LOAD = 0.4f;

	public static void main(String[] args) throws Exception {
		boolean ok = true;
		// The two same-seed arms share ONE settle: boot+settle SEED_A once, then
		// run the (pure-read) measurement twice from the same frozen settled
		// snapshot. The identity assert below proves measurement determinism; the
		// seed-B arm boots a fresh settle for seed sensitivity.
		Settled sa = bootAndSettle(SEED_A);
		String a1 = measureOn(sa);
		String a2 = measureOn(sa);
		String b = runOnce(SEED_B);
		boolean sameSeedIdentical = a1.equals(a2);
		boolean seedSensitive = !a1.equals(b);

		System.out.println("\n[movement-determinism] SEED_A  run1: " + a1);
		System.out.println("[movement-determinism] SEED_A  run2: " + a2);
		System.out.println("[movement-determinism] SEED_B  run:  " + b);
		System.out.println("[movement-determinism] same-seed identical: " + sameSeedIdentical
				+ " | different-seed differs: " + seedSensitive);

		if (!sameSeedIdentical) {
			System.err.println("[movement-determinism] FAIL — same seed produced a different stride cost (gate §4c violated)");
			ok = false;
		}
		if (!seedSensitive) {
			System.err.println("[movement-determinism] FAIL — different seeds produced an identical stride cost (vacuous)");
			ok = false;
		}

		if (ok) {
			System.out.println("[movement-determinism] PASS — the stride cost is a pure, deterministic function of the field");
		} else {
			System.err.println("[movement-determinism] FAILED");
			System.exit(1);
		}
	}

	private static String runOnce(long seed) throws InterruptedException {
		return measureOn(bootAndSettle(seed));
	}

	/** Boot the field thread, await a settled snapshot, capture the frozen
	 * (snapshot + window-center) state, and close the worker. The returned
	 * {@link Settled} is a pure immutable datum — safe to re-read any number of
	 * times. */
	private static Settled bootAndSettle(long seed) throws InterruptedException {
		SnapshotPublisher pub = new SnapshotPublisher();
		CassiFieldThread.Cfg cfg = new CassiFieldThread.Cfg(
				seed, CassiFieldThread.JOB_STEP_CAP, CassiFieldThread.SNAPSHOT_CADENCE,
				new KernelLoader().load(), new double[] { 0, 0, 0 });
		CassiFieldThread worker = new CassiFieldThread(pub);
		worker.start(cfg);
		try {
			long deadline = System.currentTimeMillis() + SNAPSHOT_TIMEOUT_MS;
			FieldSnapshot snap = null;
			while ((snap == null) && System.currentTimeMillis() < deadline) {
				snap = pub.freshest();
				if (snap == null) {
					Thread.sleep(20);
				}
			}
			if (snap == null) {
				throw new IllegalStateException("field never published");
			}
			double[] windowCenter = snap.job() != null && !snap.job().isWindowless()
					? snap.job().windowCenter()
					: new double[] { 0, 0, 0 };
			return new Settled(snap, windowCenter);
		} finally {
			worker.close();
		}
	}

	/** The pure-read measurement over a settled snapshot — never mutates the field. */
	private static String measureOn(Settled settled) {
		Quantizer.FieldReading r = Quantizer.sampleReading(settled.snap(), settled.windowCenter(), X, Y, Z);
		MovementCost.StrideCost c = MovementCost.strideCost(r, STEP_X, STEP_Y, STEP_Z, LOAD);
		return "drag=" + fmt(c.drag())
				+ " waste=" + fmt(c.wasteTerm())
				+ " eps2=" + fmt(c.eps2Term())
				+ " easement=" + fmt(c.descentEasement())
				+ " climb=" + fmt(c.verticalPenalty())
				+ " loadMul=" + fmt(c.loadMult());
	}

	private static String fmt(float v) {
		return String.format("%.3f", v);
	}

	/** The frozen settled field (immutable snapshot + its window center) shared
	 * by the two same-seed measurement arms. */
	private record Settled(FieldSnapshot snap, double[] windowCenter) {
	}

	private MovementCostDeterminismMain() {
	}
}
