package dev.cassicraft.game.reader;

import dev.cassicraft.domain.thread.CassiFieldThread;
import dev.cassicraft.domain.thread.KernelLoader;
import dev.cassicraft.domain.snapshot.FieldSnapshot;
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
 *   <li>Two measurements of the <b>same</b> settled field produce an
 *       <b>identical</b> readout text (measurement determinism across
 *       read → render). The two same-seed arms share <b>one</b> settle — the
 *       readout path only reads the frozen snapshot
 *       ({@link FieldReader#read}, never a mutation) — so the run-2 arm replays
 *       the same captured snapshot and must equal run-1. Settle determinism is
 *       not re-proved here; it is hard-pinned byte-identically by the
 *       domainHarness gate (and by every mutating gate that still boots fresh).</li>
 *   <li>A different seed produces a <b>different</b> readout (the gate is not
 *       vacuously green — the seed-B arm boots a fresh settle).</li>
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

		// The two same-seed arms share ONE settle: boot+settle SEED_A once, run
		// the pure readout twice from the same frozen snapshot, and assert the
		// readouts match (measurement determinism). The seed-B arm boots a fresh
		// settle for seed sensitivity.
		Settled sa = bootAndSettle(SEED_A);
		String a1 = measureOn(sa);
		String a2 = measureOn(sa);
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
		return measureOn(bootAndSettle(seed));
	}

	/** Boot the field thread, await a settled snapshot, capture the frozen
	 * (snapshot + window-center) state, and close the worker. The returned
	 * {@link Settled} is a pure immutable datum — safe to re-read. */
	private static Settled bootAndSettle(long seed) throws InterruptedException {
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
			FieldSnapshot snap = pub.freshest();
			if (snap == null) {
				throw new IllegalStateException("field never published");
			}
			double[] wc = snap.job() != null && !snap.job().isWindowless()
					? snap.job().windowCenter()
					: new double[] { 0, 0, 0 };
			return new Settled(snap, wc);
		} finally {
			worker.close();
		}
	}

	/** The pure-read readout over a settled snapshot — never mutates the field. */
	private static String measureOn(Settled settled) {
		FieldReader.FieldReadout r = FieldReader.read(settled.snap(), settled.windowCenter(), SX, SY, SZ);
		// The rendered text is the readout contract; the raw channels back it.
		return r.text() + " [raw] rho=" + fmt(r.rho())
				+ " q=" + fmt(r.q())
				+ " eps2=" + fmt(r.eps2());
	}

	private static String fmt(float v) {
		return String.format("%.3f", v);
	}

	/** The frozen settled field (immutable snapshot + its window center) shared
	 * by the two same-seed measurement arms. */
	private record Settled(FieldSnapshot snap, double[] windowCenter) {
	}

	private FieldReaderDeterminismMain() {
	}
}
