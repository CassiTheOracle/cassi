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
 *   <li>Two independent runs from the same seed produce the <b>identical</b>
 *       stride cost (determinism across publish → sample → cost).</li>
 *   <li>A different seed produces a <b>different</b> cost (not vacuous).</li>
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

		String a1 = runOnce(SEED_A);
		String a2 = runOnce(SEED_A);
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
			Quantizer.FieldReading r = Quantizer.sampleReading(snap, windowCenter, X, Y, Z);
			MovementCost.StrideCost c = MovementCost.strideCost(r, STEP_X, STEP_Y, STEP_Z, LOAD);
			return "drag=" + fmt(c.drag())
					+ " waste=" + fmt(c.wasteTerm())
					+ " eps2=" + fmt(c.eps2Term())
					+ " easement=" + fmt(c.descentEasement())
					+ " climb=" + fmt(c.verticalPenalty())
					+ " loadMul=" + fmt(c.loadMult());
		} finally {
			worker.close();
		}
	}

	private static String fmt(float v) {
		return String.format("%.3f", v);
	}

	private MovementCostDeterminismMain() {
	}
}
