package dev.cassicraft.game.reader;

import dev.cassicraft.domain.thread.CassiFieldThread;
import dev.cassicraft.domain.thread.KernelLoader;
import dev.cassicraft.domain.snapshot.SnapshotPublisher;

/**
 * Headless determinism gate for the Weatherglass readout (corpus-map §4 step 2,
 * BUILD-PLAN §9.5): the reader is a <b>pure consumer</b> of the published
 * snapshot, so {@code same field state → same readout}. Runs under the game
 * source set with no live client — it starts a {@link CassiFieldThread} from a
 * fixed seed, samples the field at a fixed block position through the <em>same</em>
 * {@link FieldReader#readFreshest} entry point the Weatherglass item and the
 * {@code /cassicraft read} command use, and prints the rendered readout.
 *
 * <p>Exit code 0 = green. Assertions:
 * <ol>
 *   <li>Two independent runs from the same seed produce an <b>identical</b>
 *       readout text (determinism across publish → sample → render).</li>
 *   <li>A different seed produces a <b>different</b> readout (the gate is not
 *       vacuously green).</li>
 * </ol>
 */
public final class FieldReaderDeterminismMain {

	private static final long SEED_A = 42L;
	private static final long SEED_B = 43L;
	private static final long SNAPSHOT_TIMEOUT_MS = 10_000;

	/** The fixed block position (inside the field box) the reader samples. */
	private static final int SX = 3, SY = 64, SZ = -7;

	public static void main(String[] args) throws Exception {
		boolean ok = true;

		String a1 = runOnce(SEED_A);
		String a2 = runOnce(SEED_A);
		String b = runOnce(SEED_B);

		boolean sameSeedIdentical = a1.equals(a2);
		boolean seedSensitive = !a1.equals(b);

		System.out.println("\n[reader-determinism] SEED_A  run1:\n" + a1);
		System.out.println("[reader-determinism] SEED_A  run2:\n" + a2);
		System.out.println("[reader-determinism] SEED_B  run:\n" + b);
		System.out.println("[reader-determinism] same-seed identical: " + sameSeedIdentical
				+ " | different-seed differs: " + seedSensitive);

		if (!sameSeedIdentical) {
			System.err.println("[reader-determinism] FAIL — same seed produced a different readout");
			ok = false;
		}
		if (!seedSensitive) {
			System.err.println("[reader-determinism] FAIL — different seeds produced an identical readout (vacuous)");
			ok = false;
		}

		if (ok) {
			System.out.println("[reader-determinism] PASS — the readout is a pure function of the field");
		} else {
			System.err.println("[reader-determinism] FAILED");
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
			while (pub.freshest() == null && System.currentTimeMillis() < deadline) {
				Thread.sleep(20);
			}
			FieldReader.FieldReadout r = FieldReader.readFreshest(pub, SX, SY, SZ);
			if (r == null) {
				throw new IllegalStateException("field never published");
			}
			// The rendered text is the readout contract; the raw channels back it.
			return r.text() + " [raw] rho=" + fmt(r.rho())
					+ " q=" + fmt(r.q())
					+ " eps2=" + fmt(r.eps2());
		} finally {
			worker.close();
		}
	}

	private static String fmt(float v) {
		return String.format("%.3f", v);
	}

	private FieldReaderDeterminismMain() {
	}
}
