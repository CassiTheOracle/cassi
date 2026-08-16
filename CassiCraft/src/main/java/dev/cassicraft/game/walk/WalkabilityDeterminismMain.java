package dev.cassicraft.game.walk;

import dev.cassicraft.domain.engine.TwoFluidSolver;
import dev.cassicraft.domain.snapshot.FieldSnapshot;
import dev.cassicraft.domain.snapshot.SnapshotPublisher;
import dev.cassicraft.domain.thread.CassiFieldThread;
import dev.cassicraft.domain.thread.KernelLoader;
import dev.cassicraft.game.sampler.Quantizer;

/**
 * Headless walkability gate for the player-anchored-window fix (corpus-map §4
 * step 1; the "falls through the ground" blocker). With a fixed seed and the
 * box anchored at a spawn position, it asserts the spawn column is <b>standable</b>:
 * a solid floor (ρ ≥ τ_c) with <b>air above within reach</b> — the headless proxy
 * for "the player can stand". It also asserts determinism (same seed → identical
 * profile) and anti-vacuity (different seed → differs).
 *
 * <p>Exit code 0 = green. Run under the game source set via a Gradle JavaExec,
 * no live client. The gate replays the real publish seam (CassiFieldThread →
 * SnapshotPublisher) with the player-anchored window, then samples the vertical
 * column at the anchor (box center horizontally).
 */
public final class WalkabilityDeterminismMain {

	private static final long SEED_A = 42L;
	private static final long SEED_B = 43L;
	private static final long FIRST_TIMEOUT_MS = 12_000;

	/** The fixed spawn anchor (world coords) the box centers on. */
	private static final double ANCHOR_X = 0, ANCHOR_Y = 70, ANCHOR_Z = 0;
	/** A standable column needs air at these heights above the top solid. */
	private static final int HEADROOM = 2;

	public static void main(String[] args) throws Exception {
		boolean ok = true;

		Profile a1 = runOnce(SEED_A);
		Profile a2 = runOnce(SEED_A);
		Profile b = runOnce(SEED_B);

		boolean sameSeedIdentical = a1.signature().equals(a2.signature());
		boolean seedSensitive = !a1.signature().equals(b.signature());
		boolean standableA = a1.standable() && a2.standable();
		boolean standableB = b.standable();

		System.out.println("\n[walkability] SEED_A run1: " + a1);
		System.out.println("[walkability] SEED_A run2: " + a2);
		System.out.println("[walkability] SEED_B run:  " + b);
		System.out.println("[walkability] same-seed identical: " + sameSeedIdentical
				+ " | different-seed differs: " + seedSensitive
				+ " | standable(seedA)=" + standableA + " standable(seedB)=" + standableB);

		if (!standableA) {
			System.err.println("[walkability] FAIL — the spawn column is not standable (no solid floor with air above)");
			ok = false;
		}
		if (!sameSeedIdentical) {
			System.err.println("[walkability] FAIL — same seed produced a different column (non-deterministic)");
			ok = false;
		}
		if (!seedSensitive) {
			System.err.println("[walkability] FAIL — different seeds produced an identical column (vacuous)");
			ok = false;
		}

		if (ok) {
			System.out.println("[walkability] PASS — the player-anchored window yields a standable, deterministic surface");
		} else {
			System.err.println("[walkability] FAILED");
			System.exit(1);
		}
	}

	private record Profile(String signature, boolean standable, int topSolidY, int solidCount) {
		@Override
		public String toString() {
			return "topSolidY=" + topSolidY + " solidCount=" + solidCount
					+ " standable=" + standable + " hash=" + signature.substring(0, 8);
		}
	}

	private static Profile runOnce(long seed) throws InterruptedException {
		double[] anchor = { ANCHOR_X, ANCHOR_Y, ANCHOR_Z };
		SnapshotPublisher pub = new SnapshotPublisher();
		CassiFieldThread.Cfg cfg = new CassiFieldThread.Cfg(
				seed, CassiFieldThread.JOB_STEP_CAP, CassiFieldThread.SNAPSHOT_CADENCE,
				new KernelLoader().load(), anchor);
		CassiFieldThread worker = new CassiFieldThread(pub);
		worker.start(cfg);
		try {
			FieldSnapshot snap = awaitFirst(pub);
			double[] wc = snap.job() != null && !snap.job().isWindowless()
					? snap.job().windowCenter()
					: anchor;
			int ax = (int) Math.round(anchor[0]);
			int az = (int) Math.round(anchor[2]);
			int boxTop = (int) Math.round(anchor[1] + TwoFluidSolver.EXTENT);

			// Scan the anchor column from the box top downward.
			int topSolidY = Integer.MIN_VALUE;
			int solidCount = 0;
			StringBuilder sig = new StringBuilder();
			for (int y = boxTop; y >= boxTop - (int) TwoFluidSolver.EXTENT * 2; y--) {
				Quantizer.CellSample s = Quantizer.sampleAt(snap, wc, ax, y, az);
				boolean solid = s.rho() >= Quantizer.TAU_C;
				if (solid) {
					solidCount++;
					if (topSolidY == Integer.MIN_VALUE) {
						topSolidY = y;
					}
				}
				sig.append(solid ? 'S' : 'A');
			}
			// Standable: a solid floor exists and the two blocks above it are air
			// (headroom for a standing player).
			boolean standable = topSolidY != Integer.MIN_VALUE;
			if (standable) {
				for (int above = 1; above <= HEADROOM; above++) {
					Quantizer.CellSample s = Quantizer.sampleAt(snap, wc, ax, topSolidY + above, az);
					if (s.rho() >= Quantizer.TAU_C) {
						standable = false;
						break;
					}
				}
			}
			return new Profile(sha256(sig.toString()), standable, topSolidY, solidCount);
		} finally {
			worker.close();
		}
	}

	private static FieldSnapshot awaitFirst(SnapshotPublisher pub) throws InterruptedException {
		long deadline = System.currentTimeMillis() + FIRST_TIMEOUT_MS;
		while (System.currentTimeMillis() < deadline) {
			FieldSnapshot s = pub.freshest();
			if (s != null) {
				return s;
			}
			Thread.sleep(20);
		}
		throw new IllegalStateException("no first snapshot within timeout");
	}

	private static String sha256(String s) {
		try {
			byte[] h = java.security.MessageDigest.getInstance("SHA-256").digest(s.getBytes(java.nio.charset.StandardCharsets.UTF_8));
			StringBuilder sb = new StringBuilder(h.length * 2);
			for (byte b : h) {
				sb.append(String.format("%02x", b));
			}
			return sb.toString();
		} catch (java.security.NoSuchAlgorithmException e) {
			throw new IllegalStateException(e);
		}
	}

	private WalkabilityDeterminismMain() {
	}
}
