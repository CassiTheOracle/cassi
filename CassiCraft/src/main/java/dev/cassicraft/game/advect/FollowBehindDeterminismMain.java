package dev.cassicraft.game.advect;

import dev.cassicraft.domain.engine.TwoFluidSolver;
import dev.cassicraft.domain.snapshot.FieldSnapshot;
import dev.cassicraft.domain.snapshot.SnapshotPublisher;
import dev.cassicraft.domain.thread.CassiFieldThread;
import dev.cassicraft.domain.thread.KernelLoader;
import dev.cassicraft.game.sampler.Quantizer;

/**
 * Headless follow-behind advection gate (corpus-map.md §4; world-seams.md §4.2's
 * anchor-to-window; async-field-domain.md §7 Q1's movable home-window). Asserts
 * the four properties that make the re-home honest — the box slides over a
 * world-fixed field, never minting or destroying content:
 *
 * <ol>
 *   <li><b>World-fixedness (the load-bearing proof):</b> sampling a fixed world
 *       block before and after a {@code roll(+k)} plus a {@code +k}-cell center
 *       update yields a byte-identical sample — the torus link makes the roll an
 *       exact rotation, so the field stays put in the world while the window
 *       slides (a sticker would migrate the sample).</li>
 *   <li><b>Reversibility:</b> {@code roll(+k)} then {@code roll(-k)} returns the
 *       exact prior buffer state (the roll is a bijection).</li>
 *   <li><b>Determinism + sensitivity:</b> two fixed-seed runs rolled by the same
 *       delta produce identical hashes; a different (or no) roll differs — the
 *       gate actually exercised the permutation.</li>
 *   <li><b>Center continuity:</b> after the worker drains a re-home, the
 *       published {@code window_center} equals the old center plus the whole-cell
 *       delta (the sampler sees the moved box).</li>
 * </ol>
 *
 * <p>Exit 0 = green. Any failure prints and exits non-zero. Runs headlessly
 * under the game runtime classpath (the {@code walkabilityDeterminism} pattern),
 * no live client/server.
 */
public final class FollowBehindDeterminismMain {

	/** Fixed seed for the determinism runs. */
	private static final long SEED = 42L;
	/** The world block sampled for the world-fixedness proof (box-interior in both frames). */
	private static final int PX = 45, PY = 100, PZ = 60;
	/** The whole-cell x-delta the box advances for the world-fixedness and reversibility proofs. */
	private static final int K = 4;
	/** Whole-cell delta used for the determinism/sensitivity arms. */
	private static final int DX = 4, DY = 2, DZ = -3;
	/** Worker deadlock guard. */
	private static final long FIRST_TIMEOUT_MS = 12_000;

	public static void main(String[] args) {
		boolean ok = true;
		ok &= worldFixednessGate();
		ok &= reversibilityGate();
		ok &= determinismSensitivityGate();
		ok &= centerContinuityGate();

		if (ok) {
			System.out.println("\n[follow-behind] PASS — the box re-homes over a world-fixed field, deterministically, center-continuously");
		} else {
			System.err.println("\n[follow-behind] FAILED");
			System.exit(1);
		}
	}

	// --- Gate (a): world-fixedness ------------------------------------------
	private static boolean worldFixednessGate() {
		System.out.println("\n[gate-a] world-fixedness: fixed world block P=(" + PX + "," + PY + "," + PZ
				+ ") sampled before/after roll(+" + K + ",0,0) + +" + K + "-cell center advance");
		TwoFluidSolver s = new TwoFluidSolver(SEED);
		s.seed();
		for (int i = 0; i < 32; i++) {
			s.step();
		}
		double[] c0 = { 0, 70, 0 };
		double cell = CassiFieldThread.CELL_WORLD_WIDTH;
		int cellIdx = gridCell(PX, PY, PZ, c0); // the grid cell P reads under the OLD center
		float preRho = s.rho()[cellIdx];
		float preQ = s.q()[cellIdx];

		// Advance the box +K cells in +x and roll by the same delta.
		s.roll(K, 0, 0);
		double[] c1 = { c0[0] + K * cell, c0[1], c0[2] };
		// Under the NEW center P maps K cells lower in x; the world-fixed cell holds
		// what P read before. Also re-read the OLD mapped cell (now under the rolled
		// buffer) to prove content actually moved off it.
		int movedCell = gridCell(PX, PY, PZ, c1);
		float postRho = s.rho()[movedCell];
		float postQ = s.q()[movedCell];
		float strayRho = s.rho()[cellIdx];

		boolean rhoFixed = preRho == postRho;
		boolean qFixed = preQ == postQ;
		boolean exercised = preRho != 0f || preQ != 0f; // P is real interior field, not out-of-box air
		boolean moved = strayRho != preRho; // the old cell no longer holds P's content — the roll truly moved it
		boolean ok = rhoFixed && qFixed && exercised && moved;

		System.out.println("  cell under old center = " + preRho + "," + preQ
				+ " | under new center = " + postRho + "," + postQ);
		System.out.println("  exact-equal rho=" + rhoFixed + " | q=" + qFixed
				+ " | block is interior field (not out-of-box air)=" + exercised
				+ " | roll moved content on the old cell=" + moved);
		if (!ok) {
			System.err.println("[gate-a] FAIL — the fixed world block moved (a sticker, not advection) or P read out-of-box air");
		}
		return ok;
	}

	/** The buffer flat index of the grid cell a world block maps to under a center. */
	private static int gridCell(int bx, int by, int bz, double[] center) {
		int i = (int) Math.floor(Quantizer.gridCoord(bx, center[0]));
		int j = (int) Math.floor(Quantizer.gridCoord(by, center[1]));
		int k = (int) Math.floor(Quantizer.gridCoord(bz, center[2]));
		return i + TwoFluidSolver.N * (j + TwoFluidSolver.N * k);
	}

	// --- Gate (b): reversibility ---------------------------------------------
	private static boolean reversibilityGate() {
		System.out.println("\n[gate-b] reversibility: roll(+K,0,0) then roll(-K,0,0) returns exact prior state");
		TwoFluidSolver s = new TwoFluidSolver(SEED);
		s.seed();
		for (int i = 0; i < 32; i++) {
			s.step();
		}
		Fingerprint pre = fingerprint(s);
		s.roll(K, 0, 0);
		Fingerprint afterPlus = fingerprint(s);
		s.roll(-K, 0, 0);
		Fingerprint back = fingerprint(s);

		boolean reverseExact = pre.equals(back);
		boolean rollExercised = !pre.equals(afterPlus); // +K must actually move content
		boolean ok = reverseExact && rollExercised;

		System.out.println("  pre / after +K / after -K hashes:");
		System.out.println("    pre      " + pre.hash().substring(0, 16) + "...");
		System.out.println("    after +K " + afterPlus.hash().substring(0, 16) + "...");
		System.out.println("    after -K " + back.hash().substring(0, 16) + "...");
		System.out.println("  roll(+K) changed content (sensitivity)=" + rollExercised
				+ " | roll(-K) restored exact prior state=" + reverseExact);
		if (!ok) {
			System.err.println("[gate-b] FAIL — the roll is not a reversible bijection, or it never moved content");
		}
		return ok;
	}

	// --- Gate (c): determinism + sensitivity -----------------------------------
	private static boolean determinismSensitivityGate() {
		System.out.println("\n[gate-c] determinism+sensitivity: same seed+same roll identical; different roll differs");
		Fingerprint a1 = seededRolledFingerprint();
		Fingerprint a2 = seededRolledFingerprint();
		Fingerprint b = seededDifferentRollFingerprint();
		Fingerprint c = seededNoRollFingerprint();

		boolean sameRollIdentical = a1.equals(a2);
		boolean differentRollDiffers = !a1.equals(b);
		boolean notRolledDiffers = !a1.equals(c);
		boolean exercised = a1.rollCount() > 0 && b.rollCount() > 0;
		boolean ok = sameRollIdentical && differentRollDiffers && notRolledDiffers && exercised;

		System.out.println("  same-seed same-roll run1 " + a1.hash().substring(0, 16) + "... (rolls=" + a1.rollCount() + ")");
		System.out.println("  same-seed same-roll run2 " + a2.hash().substring(0, 16) + "... (rolls=" + a2.rollCount() + ")");
		System.out.println("  same-seed diff-roll      " + b.hash().substring(0, 16) + "... (rolls=" + b.rollCount() + ")");
		System.out.println("  same-seed no-roll        " + c.hash().substring(0, 16) + "... (rolls=" + c.rollCount() + ")");
		System.out.println("  same roll identical=" + sameRollIdentical
				+ " | different roll differs=" + differentRollDiffers
				+ " | no-roll differs=" + notRolledDiffers
				+ " | rolls actually exercised=" + exercised);
		if (!ok) {
			System.err.println("[gate-c] FAIL — the roll is not deterministic, or it is insensitive/vacuous");
		}
		return ok;
	}

	// --- Gate (d): center continuity ---------------------------------------------
	private static boolean centerContinuityGate() {
		System.out.println("\n[gate-d] center continuity: after a re-home the published window_center = old center + whole-cell delta");
		double[] anchor = { 0, 70, 0 };
		SnapshotPublisher pub = new SnapshotPublisher();
		CassiFieldThread.Cfg cfg = new CassiFieldThread.Cfg(
				SEED, CassiFieldThread.JOB_STEP_CAP, CassiFieldThread.SNAPSHOT_CADENCE,
				new KernelLoader().load(), anchor);
		CassiFieldThread worker = new CassiFieldThread(pub);
		worker.start(cfg);
		try {
			FieldSnapshot first = awaitFirst(pub);
			double[] c0 = first.job().windowCenter();
			System.out.println("  initial published center = (" + c0[0] + "," + c0[1] + "," + c0[2] + ")");
			if (c0[0] != 0.0 || c0[1] != 70.0 || c0[2] != 0.0) {
				System.err.println("[gate-d] FAIL — the initial publish did not ship the Cfg center");
				return false;
			}

			double cell = CassiFieldThread.CELL_WORLD_WIDTH;
			int k = 2; // advance +2 whole cells in +x
			worker.rehome(c0[0] + k * cell, c0[1], c0[2]);
			FieldSnapshot moved = awaitCenterChanged(pub, c0);
			double[] c1 = moved.job().windowCenter();
			double expected = c0[0] + k * cell;
			boolean ok = Math.abs(c1[0] - expected) < 1e-9
					&& c1[1] == c0[1] && c1[2] == c0[2];
			System.out.println("  post-rehome published center = (" + c1[0] + "," + c1[1] + "," + c1[2] + ")"
					+ " | expected (" + expected + ",70,0)");
			System.out.println("  center advanced exactly " + k + " cells, other axes unchanged=" + ok);
			if (!ok) {
				System.err.println("[gate-d] FAIL — published center did not advance by the exact whole-cell delta");
			}
			return ok;
		} catch (InterruptedException e) {
			Thread.currentThread().interrupt();
			System.err.println("[gate-d] FAIL — interrupted waiting for publish");
			return false;
		} finally {
			worker.close();
		}
	}

	/** Full-buffer fingerprint including q and scr (stateHash omits those two). */
	private static Fingerprint fingerprint(TwoFluidSolver s) {
		return new Fingerprint(
				sha256(concat(s.ey(), s.ei(), s.q(), s.rho())),
				sha256(concat(s.vel(), s.scr())),
				0);
	}

	private static Fingerprint seededRolledFingerprint() {
		TwoFluidSolver s = new TwoFluidSolver(SEED);
		s.seed();
		for (int i = 0; i < 32; i++) {
			s.step();
		}
		s.roll(DX, DY, DZ);
		return fingerprint(s).withRollCount(1);
	}

	private static Fingerprint seededDifferentRollFingerprint() {
		TwoFluidSolver s = new TwoFluidSolver(SEED);
		s.seed();
		for (int i = 0; i < 32; i++) {
			s.step();
		}
		s.roll(DX, DY, DZ + 1);
		return fingerprint(s).withRollCount(1);
	}

	private static Fingerprint seededNoRollFingerprint() {
		TwoFluidSolver s = new TwoFluidSolver(SEED);
		s.seed();
		for (int i = 0; i < 32; i++) {
			s.step();
		}
		return fingerprint(s).withRollCount(0);
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

	/** Wait until a publish carries a center different from {@code old} (the roll drained). */
	private static FieldSnapshot awaitCenterChanged(SnapshotPublisher pub, double[] old)
			throws InterruptedException {
		long deadline = System.currentTimeMillis() + FIRST_TIMEOUT_MS;
		while (System.currentTimeMillis() < deadline) {
			FieldSnapshot s = pub.freshest();
			if (s != null && s.job() != null && !s.job().isWindowless()) {
				double[] c = s.job().windowCenter();
				if (c[0] != old[0] || c[1] != old[1] || c[2] != old[2]) {
					return s;
				}
			}
			Thread.sleep(20);
		}
		throw new IllegalStateException("no re-homed snapshot within timeout");
	}

	private static float[] concat(float[] a, float[] b) {
		float[] out = new float[a.length + b.length];
		System.arraycopy(a, 0, out, 0, a.length);
		System.arraycopy(b, 0, out, a.length, b.length);
		return out;
	}

	private static float[] concat(float[] a, float[] b, float[] c, float[] d) {
		return concat(concat(concat(a, b), c), d);
	}

	private static String sha256(float[] floats) {
		java.nio.ByteBuffer bb = java.nio.ByteBuffer.allocate(floats.length * 4);
		bb.asFloatBuffer().put(floats);
		return sha256(bb.array());
	}

	private static String sha256(byte[] data) {
		try {
			byte[] h = java.security.MessageDigest.getInstance("SHA-256").digest(data);
			StringBuilder sb = new StringBuilder(h.length * 2);
			for (byte x : h) {
				sb.append(String.format("%02x", x));
			}
			return sb.toString();
		} catch (java.security.NoSuchAlgorithmException e) {
			throw new IllegalStateException(e);
		}
	}

	/** Full-buffer fingerprint: scalar channels (ey/ei/q/rho) and vec channels (vel/scr). */
	private record Fingerprint(String scalarHash, String vecHash, int rollCount) {
		String hash() {
			return scalarHash + vecHash;
		}

		boolean equals(Fingerprint o) {
			return scalarHash.equals(o.scalarHash) && vecHash.equals(o.vecHash);
		}

		Fingerprint withRollCount(int n) {
			return new Fingerprint(scalarHash, vecHash, n);
		}
	}

	private FollowBehindDeterminismMain() {
	}
}
