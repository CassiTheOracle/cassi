package dev.cassicraft.game.sampler;

import dev.cassicraft.domain.snapshot.FieldSnapshot;
import dev.cassicraft.domain.snapshot.SnapshotPublisher;
import dev.cassicraft.domain.thread.CassiFieldThread;
import dev.cassicraft.domain.thread.KernelLoader;

/**
 * Headless determinism gate for the living-terrain quantizer (BUILD-PLAN.md
 * §9.5): <b>same field state → same blocks, every run.</b> Replays the real
 * publish seam — starts a {@link CassiFieldThread} from a fixed seed, consumes
 * the first cadence snapshot through the same {@link SnapshotPublisher} handoff
 * the server tick uses, runs the pure {@link Quantizer} over a bounded region,
 * and hashes the non-air block positions.
 *
 * <p>Runs as a plain {@code main} under the game source set with no live
 * Minecraft server — the domain worker is a normal JVM thread (BUILD-PLAN.md
 * §3.3) and never touches the MC host, so the gate is CI-runnable via a Gradle
 * {@code JavaExec} task. Exit code 0 = green.
 *
 * <p>The gate asserts:
 * <ol>
 *   <li>Two independent runs from the same seed produce the <b>identical</b>
 *       block-state hash (determinism across the whole publish→quantize path).</li>
 *   <li>A different seed produces a <b>different</b> block-state hash (the gate
 *       is not vacuously green — the field actually seeds the terrain).</li>
 * </ol>
 */
public final class QuantizerDeterminismMain {

	/** The fixed (non-zero) seeds the gate replays. */
	private static final long SEED_A = 42L;
	private static final long SEED_B = 43L;

	/** The bounded `region` re-quantized by the gate (a player-vicinity-sized cube). */
	private static final int REGION_MIN = -32;
	private static final int REGION_SIZE = 64;   // 64³ blocks, ~0.3% of the 192³ volume

	private static final long SNAPSHOT_TIMEOUT_MS = 10_000;

	public static void main(String[] args) throws Exception {
		boolean ok = true;

		String hashA1 = runOnce(SEED_A);
		String hashA2 = runOnce(SEED_A);
		String hashB = runOnce(SEED_B);

		boolean sameSeedIdentical = hashA1.equals(hashA2);
		boolean seedSensitive = !hashA1.equals(hashB);

		System.out.println("\n[quantizer-determinism] SEED_A  run1 = " + hashA1);
		System.out.println("[quantizer-determinism] SEED_A  run2 = " + hashA2);
		System.out.println("[quantizer-determinism] SEED_B  run  = " + hashB);
		System.out.println("[quantizer-determinism] same-seed identical: " + sameSeedIdentical
				+ " | different-seed differs: " + seedSensitive);

		if (!sameSeedIdentical) {
			System.err.println("[quantizer-determinism] FAIL — same seed produced different blocks");
			ok = false;
		}
		if (!seedSensitive) {
			System.err.println("[quantizer-determinism] FAIL — different seeds produced identical blocks (gate is vacuous)");
			ok = false;
		}

		if (ok) {
			System.out.println("[quantizer-determinism] PASS — same field state → same blocks, every run");
		} else {
			System.err.println("[quantizer-determinism] FAILED");
			System.exit(1);
		}
	}

	/** Start a field thread from {@code seed}, take the first cadence snapshot, quantize, hash. */
	private static String runOnce(long seed) throws InterruptedException {
		SnapshotPublisher pub = new SnapshotPublisher();
		CassiFieldThread.Cfg cfg = new CassiFieldThread.Cfg(
				seed,
				CassiFieldThread.JOB_STEP_CAP,
				CassiFieldThread.SNAPSHOT_CADENCE,
				new KernelLoader().load(),
				new double[] { 0, 0, 0 });
		CassiFieldThread worker = new CassiFieldThread(pub);
		worker.start(cfg);
		try {
			FieldSnapshot snap = awaitFirstSnapshot(pub);
			double[] window = snap.job() != null && !snap.job().isWindowless()
					? snap.job().windowCenter()
					: new double[] { 0, 0, 0 };
			Quantizer.QuantizedRegion region = Quantizer.quantizeRegion(
					snap, window, REGION_MIN, REGION_MIN, REGION_MIN,
					REGION_SIZE, REGION_SIZE, REGION_SIZE);
			String hash = region.contentHash();
			System.out.println("[quantizer-determinism] seed=" + seed
					+ " gen=" + snap.generation()
					+ " executed=" + (snap.job() == null ? "?" : snap.job().executed())
					+ " non-air blocks=" + region.quantizedCount());
			return hash;
		} finally {
			worker.close();
		}
	}

	private static FieldSnapshot awaitFirstSnapshot(SnapshotPublisher pub) throws InterruptedException {
		long deadline = System.currentTimeMillis() + SNAPSHOT_TIMEOUT_MS;
		while (System.currentTimeMillis() < deadline) {
			FieldSnapshot snap = pub.freshest();
			if (snap != null) {
				return snap;
			}
			Thread.sleep(20);
		}
		throw new IllegalStateException("field thread never published a snapshot within " + SNAPSHOT_TIMEOUT_MS + " ms");
	}

	private QuantizerDeterminismMain() {
	}
}
