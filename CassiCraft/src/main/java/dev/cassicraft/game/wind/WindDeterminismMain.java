package dev.cassicraft.game.wind;

import dev.cassicraft.domain.snapshot.FieldSnapshot;
import dev.cassicraft.domain.snapshot.SnapshotPublisher;
import dev.cassicraft.domain.thread.CassiFieldThread;
import dev.cassicraft.domain.thread.KernelLoader;
import dev.cassicraft.game.sampler.Quantizer;

import java.nio.ByteBuffer;
import java.util.ArrayList;
import java.util.List;

/**
 * The Wind determinism gate (the-wind.md §7 gate (c), HARD): same window, same
 * field state → same wind. Fingerprints the {@link WindRead} over a fixed
 * sample grid of positions from a settled field and asserts:
 *
 * <ol>
 *   <li><b>Measurement determinism:</b> two grid reads of the <b>same</b>
 *       settled field give an identical fingerprint. The two same-seed arms share
 *       <b>one</b> settle — the grid read is a pure read of the published
 *       snapshot (the current is never a seeded gust roll, no mutation) — so the
 *       run-2 arm replays the same frozen settled snapshot and must equal run-1.
 *       Settle determinism is not re-proved here; it is hard-pinned
 *       byte-identically by the domainHarness gate (and by every mutating gate
 *       that still boots fresh).</li>
 *   <li><b>Seed sensitivity (anti-vacuous):</b> a different seed differs — the
 *       reader actually read the field, not a constant.</li>
 *   <li><b>Positive-count anti-vacuity:</b> across the grid at least one
 *       position has a non-CALM current and at least two differ in direction —
 *       the reader genuinely separates states (the wind is not everywhere CALM
 *       or everywhere pointing one way).</li>
 *   <li><b>Pure-function:</b> reading the same snapshot at the same position
 *       twice returns an identical {@link WindRead.WindReading} (no internal
 *       state, no RNG in the classification).</li>
 * </ol>
 *
 * <p>Reads the published snapshot only, never writes; headless under the game
 * runtime classpath (the TerrainCensusMain pattern). Exit 0 = green.
 */
public final class WindDeterminismMain {

	private static final long SEED_A = 42L;
	private static final long SEED_B = 43L;

	private static final double ANCHOR_X = 0, ANCHOR_Y = 70, ANCHOR_Z = 0;
	private static final int EXTENT = (int) dev.cassicraft.domain.engine.TwoFluidSolver.EXTENT;

	private static final long FIRST_TIMEOUT_MS = 12_000;
	private static final long SETTLE_TIMEOUT_MS = 30_000;
	private static final int SETTLE_GENERATIONS = 12;

	/** The fixed sample grid stride (blocks) — a sparse spread so the wind's spatial variance is read. */
	private static final int GRID_STRIDE = 16;

	public static void main(String[] args) throws Exception {
		// The two same-seed arms share ONE settle: boot+settle SEED_A once, run
		// the pure grid read twice from the same frozen snapshot, and assert the
		// fingerprints match (measurement determinism). The seed-B arm boots a
		// fresh settle for seed sensitivity.
		Settled sa = bootAndSettle(SEED_A);
		Fingerprint a1 = measureOn(sa);
		Fingerprint a2 = measureOn(sa);
		Fingerprint b = runOnce(SEED_B);

		boolean sameSeedIdentical = a1.hash().equals(a2.hash());
		boolean seedSensitive = !a1.hash().equals(b.hash());
		boolean nonCalm = a1.nonCalmCount() >= 1 && a2.nonCalmCount() >= 1;
		// The reader separates states: at least two distinct directions on the grid.
		boolean directionSeparates = a1.directionSet() >= 2 && a2.directionSet() >= 2;
		// Pure function: a re-read of the same snapshot at the first non-CALM grid
		// position is byte-identical.
		boolean pure = pureFunction(a1);

		System.out.println("\n[wind-determinism] SEED_A run1: " + a1.summary());
		System.out.println("[wind-determinism] SEED_A run2: " + a2.summary());
		System.out.println("[wind-determinism] SEED_B run:  " + b.summary());
		System.out.println("[wind-determinism] same-seed identical: " + sameSeedIdentical
				+ " | different-seed differs: " + seedSensitive
				+ " | non-CALM grid points(A)=" + a1.nonCalmCount()
				+ " | distinct directions(A)=" + a1.directionSet()
				+ " | pure function: " + pure);

		boolean ok = true;
		if (!sameSeedIdentical) {
			System.err.println("[wind-determinism] FAIL \u2014 same seed produced a different wind (non-deterministic current)");
			ok = false;
		}
		if (!seedSensitive) {
			System.err.println("[wind-determinism] FAIL \u2014 different seeds produced an identical wind (vacuous: the reader did not read the field)");
			ok = false;
		}
		if (!nonCalm) {
			System.err.println("[wind-determinism] FAIL \u2014 no position in the grid read a non-CALM current (the wind was everywhere calm, or the read is broken)");
			ok = false;
		}
		if (!directionSeparates) {
			System.err.println("[wind-determinism] FAIL \u2014 the wind read the same direction everywhere (the reader does not separate states)");
			ok = false;
		}
		if (!pure) {
			System.err.println("[wind-determinism] FAIL \u2014 reading the same snapshot twice gave a different wind (the classifier is not a pure function)");
			ok = false;
		}

		if (ok) {
			System.out.println("[wind-determinism] PASS \u2014 the wind is a deterministic, seed-sensitive, state-separating pure function of the published field (the-wind.md \u00a77 gate (c))");
		} else {
			System.err.println("[wind-determinism] FAILED");
			System.exit(1);
		}
	}

	/** Boot a settled field, read the wind over the fixed grid, return its fingerprint. */
	private static Fingerprint runOnce(long seed) throws InterruptedException {
		return measureOn(bootAndSettle(seed));
	}

	/** Boot the field thread, await the settled snapshot, capture the frozen
	 * (snapshot + window-center) state, and close the worker. The returned
	 * {@link Settled} is a pure immutable datum — safe to re-read. */
	private static Settled bootAndSettle(long seed) throws InterruptedException {
		double[] anchor = { ANCHOR_X, ANCHOR_Y, ANCHOR_Z };
		SnapshotPublisher pub = new SnapshotPublisher();
		CassiFieldThread.Cfg cfg = new CassiFieldThread.Cfg(
				seed, CassiFieldThread.JOB_STEP_CAP, CassiFieldThread.SNAPSHOT_CADENCE,
				new KernelLoader().load(), anchor);
		CassiFieldThread worker = new CassiFieldThread(pub);
		try {
			worker.start(cfg);
			FieldSnapshot snap = awaitSettled(pub);
			double[] window = centerOf(snap, anchor);
			return new Settled(snap, window);
		} finally {
			worker.close();
		}
	}

	/** The pure grid-read measurement over a settled snapshot — never mutates. */
	private static Fingerprint measureOn(Settled s) {
		return fingerprint(s.snap(), s.windowCenter());
	}

	private static FieldSnapshot awaitSettled(SnapshotPublisher pub) throws InterruptedException {
		long deadline = System.currentTimeMillis() + SETTLE_TIMEOUT_MS;
		while (System.currentTimeMillis() < deadline) {
			FieldSnapshot s = pub.freshest();
			if (s != null && s.generation() >= SETTLE_GENERATIONS) {
				return s;
			}
			Thread.sleep(20);
		}
		throw new IllegalStateException("field never settled within timeout");
	}

	private static double[] centerOf(FieldSnapshot snap, double[] anchor) {
		if (snap.job() != null && !snap.job().isWindowless()) {
			return snap.job().windowCenter();
		}
		return anchor.clone();
	}

	/** A fixed sparse grid of block positions across the central box (the reading window). */
	private static int[][] sampleGrid() {
		List<int[]> pts = new ArrayList<>();
		int cx = (int) Math.round(ANCHOR_X);
		int cy = (int) Math.round(ANCHOR_Y);
		int cz = (int) Math.round(ANCHOR_Z);
		int half = EXTENT / 2;
		for (int dx = -half; dx <= half; dx += GRID_STRIDE) {
			for (int dz = -half; dz <= half; dz += GRID_STRIDE) {
				for (int dy = -half; dy <= half; dy += GRID_STRIDE) {
					pts.add(new int[] { cx + dx, cy + dy, cz + dz });
				}
			}
		}
		return pts.toArray(new int[0][]);
	}

	/** Read the wind over the grid and accumulate a deterministic hash + counts. */
	private static Fingerprint fingerprint(FieldSnapshot snap, double[] window) {
		int[][] grid = sampleGrid();
		ByteBuffer bb = ByteBuffer.allocate(grid.length * (4 + 4 + 4 + 4 + 4 + 4));
		int nonCalm = 0;
		java.util.Set<WindRead.Direction> dirs = new java.util.LinkedHashSet<>();
		List<int[]> nonCalmPts = new ArrayList<>();
		for (int[] p : grid) {
			WindRead.WindReading w = WindRead.read(snap, window, p[0], p[1], p[2]);
			bb.putInt(w.direction().ordinal());
			bb.putInt(w.strength().ordinal());
			bb.putInt(Float.floatToIntBits(w.strengthValue()));
			bb.putInt(w.carry().ordinal());
			bb.putInt(Float.floatToIntBits(w.costAid()));
			bb.putInt(Float.floatToIntBits(w.gradH()));
			if (!w.isCalm()) {
				nonCalm++;
				dirs.add(w.direction());
				nonCalmPts.add(p);
			}
		}
		String hash = sha256(bb.array());
		// Remember the first non-CALM grid point for the pure-function re-read.
		int[] probe = nonCalmPts.isEmpty() ? grid[0] : nonCalmPts.get(0);
		return new Fingerprint(hash, nonCalm, dirs.size(), snap, window, probe);
	}

	/** Re-read the same snapshot at the first non-CALM grid point to assert purity. */
	private static boolean pureFunction(Fingerprint f) {
		FieldSnapshot snap = f.snap;
		int[] p = f.probePoint;
		if (snap == null) {
			// A pure-function re-read needs the snapshot; a null snapshot means the
			// grid was all-CALM (already failed non-calm), so this is not the gate's
			// burden — report vacuously false only if there is no current to re-read.
			return false;
		}
		WindRead.WindReading w1 = WindRead.read(snap, f.window, p[0], p[1], p[2]);
		WindRead.WindReading w2 = WindRead.read(snap, f.window, p[0], p[1], p[2]);
		return w1.equals(w2);
	}

	private static String sha256(byte[] data) {
		try {
			byte[] h = java.security.MessageDigest.getInstance("SHA-256").digest(data);
			StringBuilder sb = new StringBuilder(h.length * 2);
			for (byte b : h) {
				sb.append(String.format("%02x", b));
			}
			return sb.toString();
		} catch (java.security.NoSuchAlgorithmException e) {
			throw new IllegalStateException(e);
		}
	}

	/** One end-to-end run's wind fingerprint + the non-CALM/state-separation evidence. */
	private record Fingerprint(String hash, int nonCalmCount, int directionSet,
			FieldSnapshot snap, double[] window, int[] probePoint) {
		String summary() {
			return "nonCalm=" + nonCalmCount + " dirs=" + directionSet
					+ " hash=" + hash.substring(0, 8);
		}
	}

	/** The frozen settled field (immutable snapshot + its window center) shared
	 * by the two same-seed measurement arms. */
	private record Settled(FieldSnapshot snap, double[] windowCenter) {
	}

	private WindDeterminismMain() {
	}
}
