package dev.cassicraft.game.life;

import dev.cassicraft.domain.snapshot.SnapshotPublisher;
import dev.cassicraft.domain.thread.CassiFieldThread;
import dev.cassicraft.domain.thread.KernelLoader;
import dev.cassicraft.game.sampler.Quantizer;

import java.util.List;

/**
 * Headless determinism gate for the Life-Signal classifier (corpus-map §4 step 3;
 * life-signal.md §6d — a <b>hard</b> gate: same field state → same class). Runs
 * under the game source set with no live client. It replays the publish seam —
 * starts a {@link CassiFieldThread} from a fixed seed and collects a {@link
 * LifeSignal#WINDOW_LEN}-sample maintenance window at a fixed block position
 * across successive published generations — then classifies.
 *
 * <p>Exit code 0 = green. Assertions:
 * <ol>
 *   <li>Two independent runs from the same seed classify the <b>same</b> class
 *       (determinism across publish → window → classify).</li>
 *   <li>A different seed classifies a <b>different</b> class or channel series
 *       (the gate is not vacuous).</li>
 * </ol>
 */
public final class LifeSignalDeterminismMain {

	private static final long SEED_A = 42L;
	private static final long SEED_B = 43L;
	private static final long SNAPSHOT_TIMEOUT_MS = 15_000;

	/** The fixed block position (inside the field box) the classifier reads. */
	private static final int X = 3, Y = 64, Z = -7;

	public static void main(String[] args) throws Exception {
		boolean ok = true;

		String a1 = runOnce(SEED_A);
		String a2 = runOnce(SEED_A);
		String b = runOnce(SEED_B);

		boolean sameSeedIdentical = a1.equals(a2);
		boolean seedSensitive = !a1.equals(b);

		System.out.println("\n[life-determinism] SEED_A  run1: " + a1);
		System.out.println("[life-determinism] SEED_A  run2: " + a2);
		System.out.println("[life-determinism] SEED_B  run:  " + b);
		System.out.println("[life-determinism] same-seed identical: " + sameSeedIdentical
				+ " | different-seed differs: " + seedSensitive);

		if (!sameSeedIdentical) {
			System.err.println("[life-determinism] FAIL — same seed produced a different class (gate §6d violated)");
			ok = false;
		}
		if (!seedSensitive) {
			System.err.println("[life-determinism] FAIL — different seeds produced an identical signature (vacuous)");
			ok = false;
		}

		if (ok) {
			System.out.println("[life-determinism] PASS — the life read is a pure, deterministic function of the field");
		} else {
			System.err.println("[life-determinism] FAILED");
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
			List<Quantizer.FieldReading> window = LifeSignal.collectWindow(
					pub, new double[] { 0, 0, 0 }, X, Y, Z, LifeSignal.WINDOW_LEN, SNAPSHOT_TIMEOUT_MS);
			LifeSignal.LifeReading life = LifeSignal.classify(window);
			return life.cls() + " | wasteMean=" + fmt(life.wasteMean())
					+ " pulse=" + fmt(life.wastePulse())
					+ " epsGrad=" + fmt(life.epsGrad())
					+ " lean=(" + fmt(life.leanX()) + "," + fmt(life.leanY()) + "," + fmt(life.leanZ()) + ")";
		} finally {
			worker.close();
		}
	}

	private static String fmt(float v) {
		return String.format("%.3f", v);
	}

	private LifeSignalDeterminismMain() {
	}
}
