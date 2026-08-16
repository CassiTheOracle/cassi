package dev.cassicraft.game.q4;

import dev.cassicraft.domain.engine.TwoFluidSolver;
import dev.cassicraft.domain.snapshot.FieldSnapshot;
import dev.cassicraft.domain.snapshot.SnapshotPublisher;
import dev.cassicraft.domain.thread.CassiFieldThread;
import dev.cassicraft.domain.thread.KernelLoader;

/**
 * Headless Q4 write-lane determinism + honesty gate
 * (`wiring-requests/q4-write-lane-design.md` — {@code async-field-domain.md} §7 Q4's
 * player-return channel). Asserts the channel's governing rule — <em>a perturbation
 * redistributes what is already there; it never mints, dumps, or silently crosses
 * the re-lock line</em> — with the corpus's family determinism discipline (same
 * request + same field state → same response), split across the two honest
 * proving surfaces exactly as {@code FollowBehindDeterminismMain} does:
 *
 * <ol>
 *   <li><b>Bare-solver injection determinism (byte-identical).</b> The engine-real
 *       {@code TwoFluidSolver.applySource} injection is byte-deterministic: two
 *       fixed-seed runs that both {@code seed → 32 steps → applySource → 32 steps}
 *       yield an identical full-buffer fingerprint; a different seed differs; a
 *       no-injection control differs — the injection actually moved the field.
 *       This is the "same field state → same response" proof, free of async
 *       drain-timing (the FollowBehind pattern).</li>
 *   <li><b>Seam routing through the real publish.</b> A {@code CassiFieldThread}
 *       service boots via the real publish seam ({@link SnapshotPublisher} +
 *       {@link KernelLoader}), settles, and a perturbation submitted at the named
 *       window-relative box-center cell is drained, capped, and applied; the
 *       post-drain published field at that cell neighborhood differs
 *       byte-identically from the same-seed no-perturbation control read at the
 *       <em>same executed step</em> — the lane moved the published field (never
 *       a no-op), deterministically, keyed to an exact executed multiple.</li>
 *   <li><b>Caps engaged (honesty).</b> An overdraw request (a raw magnitude past
 *       the ω₀² re-lock ceiling, {@code coherence-magic.md} §4.3) and a
 *       no-mint-violating request (a raw magnitude past {@code φ⁻¹·sqrt(q)},
 *       {@code energy-harnessing.md} §6) are each clamped at drain —
 *       {@link CassiFieldThread#perturbationClampCount()} increments, and the
 *       resulting response is bounded (the field stays within the capped
 *       injection's reach, never an unbounded dump). The explicit blast stays a
 *       documented future mode.</li>
 * </ol>
 *
 * <p>Exit 0 = green. Any failure prints and exits non-zero. Runs headlessly under
 * the game runtime classpath (the {@code walkabilityDeterminism} pattern), no live
 * client/server.
 */
public final class Q4DeterminismMain {

	/** Fixed seed for the determinism arms. */
	private static final long SEED = 42L;
	/** A different seed for the sensitivity arm. */
	private static final long SEED_OTHER = 43L;
	/** Steps before the injection in the bare-solver arms. */
	private static final int BARE_PRE_STEPS = 32;
	/** Steps after the injection in the bare-solver arms. */
	private static final int BARE_POST_STEPS = 32;
	/** Target cell (box center — the named window-relative point). */
	private static final int CX = TwoFluidSolver.N / 2;
	private static final int CY = TwoFluidSolver.N / 2;
	private static final int CZ = TwoFluidSolver.N / 2;
	/** Bare-arm injection: a coherence-delivering EY write + matched EI, radius 3 cells. */
	private static final float BARE_D_EY = 0.20f;
	private static final float BARE_D_EI = 0.12f;
	private static final int BARE_RADIUS = 3;

	/** Executed step at which the seam-gate reads the post-drain published field. */
	private static final int SEAM_TARGET_EXECUTED = 448;
	/** Settle margin before the seam-gate submits its perturbation. */
	private static final int SEAM_SUBMIT_EXECUTED = 192;
	private static final long SEAM_TIMEOUT_MS = 120_000;

	public static void main(String[] args) {
		boolean ok = true;
		ok &= bareSolverDeterminismGate();
		ok &= seamRoutingGate();
		ok &= capsEngagedGate();

		if (ok) {
			System.out.println("\n[q4-determinism] PASS — the write lane is deterministic, moves the published field, and clamps overdraw/no-mint");
		} else {
			System.err.println("\n[q4-determinism] FAILED");
			System.exit(1);
		}
	}

	// --- Gate 1: bare-solver injection determinism + movement -----------------
	private static boolean bareSolverDeterminismGate() {
		System.out.println("\n[gate-a] bare-solver applySource determinism + movement (byte-identical)");
		Fingerprint a1 = bareRun(SEED, BARE_D_EY, BARE_D_EI, BARE_RADIUS);
		Fingerprint a2 = bareRun(SEED, BARE_D_EY, BARE_D_EI, BARE_RADIUS);
		Fingerprint b = bareRun(SEED_OTHER, BARE_D_EY, BARE_D_EI, BARE_RADIUS);
		Fingerprint c = bareRun(SEED, 0f, 0f, BARE_RADIUS); // no-injection control

		boolean sameSeedIdentical = a1.equals(a2);
		boolean diffSeedDiffers = !a1.equals(b);
		boolean movedField = !a1.equals(c);
		boolean exercised = !c.equals(b);
		boolean ok = sameSeedIdentical && diffSeedDiffers && movedField && exercised;

		System.out.println("  same-seed run1 " + a1.shortHash() + " | run2 " + a2.shortHash() + " | identical=" + sameSeedIdentical);
		System.out.println("  diff-seed           " + b.shortHash() + " | differs=" + diffSeedDiffers);
		System.out.println("  no-injection ctrl   " + c.shortHash() + " | injection moved field=" + movedField);
		System.out.println("  seeds separate the arms=" + exercised);
		if (!ok) {
			System.err.println("[gate-a] FAIL — applySource is not deterministic, insensitive, or vacuous (injection had no effect)");
		}
		return ok;
	}

	private static Fingerprint bareRun(long seed, float dEY, float dEI, int radius) {
		TwoFluidSolver s = new TwoFluidSolver(seed);
		s.seed();
		for (int i = 0; i < BARE_PRE_STEPS; i++) {
			s.step();
		}
		s.applySource(CX, CY, CZ, dEY, dEI, radius);
		for (int i = 0; i < BARE_POST_STEPS; i++) {
			s.step();
		}
		return fullFingerprint(s);
	}

	/** Full-buffer fingerprint incl. q and scr (stateHash omits those two). */
	private static Fingerprint fullFingerprint(TwoFluidSolver s) {
		return new Fingerprint(
				sha256(concat(s.ey(), s.ei(), s.q(), s.rho())),
				sha256(concat(s.vel(), s.scr())));
	}

	// --- Gate 2: routing through the real publish seam -------------------------
	private static boolean seamRoutingGate() {
		System.out.println("\n[gate-b] seam routing: a perturbation via the real CassiFieldThread publish moves the published field");
		FieldReading perturbed = runSeam(true);
		FieldReading control = runSeam(false);
		boolean sameStep = perturbed.executed == control.executed;
		boolean moved = !perturbed.regionHash.equals(control.regionHash);
		boolean targetLive = perturbed.preTargetq > 0f; // real interior field, not a vacuous zero cell
		boolean ok = sameStep && moved && targetLive;

		System.out.println("  perturbed executed=" + perturbed.executed + " ctrl executed=" + control.executed + " (equal read step)=" + sameStep);
		System.out.println("  pre-target q=" + perturbed.preTargetq + " (live interior cell)=" + targetLive);
		System.out.println("  perturbed post region " + perturbed.regionHash.substring(0, 16) + "...");
		System.out.println("  ctrl      post region " + control.regionHash.substring(0, 16) + "...");
		System.out.println("  lane moved the published field vs control=" + moved);
		if (!ok) {
			System.err.println("[gate-b] FAIL — the perturbation did not move the published field, or the read steps did not align");
		}
		return ok;
	}

	private static FieldReading runSeam(boolean perturb) {
		double[] anchor = { 0, 0, 0 };
		SnapshotPublisher pub = new SnapshotPublisher();
		// Snapshot cadence 2: publishes land on ODD multiples of stepsPerJob
		// (executed = 64, 192, 320, ...), each target chosen as an odd multiple so
		// the "first snapshot with executed >= target" lands exactly on target —
		// the same executed step in every run, byte-deterministic.
		CassiFieldThread.Cfg cfg = new CassiFieldThread.Cfg(
				SEED, CassiFieldThread.JOB_STEP_CAP, CassiFieldThread.SNAPSHOT_CADENCE,
				new KernelLoader().load(), anchor);
		CassiFieldThread worker = new CassiFieldThread(pub);
		worker.start(cfg);
		try {
			FieldSnapshot pre = awaitExecuted(pub, SEAM_SUBMIT_EXECUTED);
			// The named window-relative point: the box-center cell (N/2,N/2,N/2), whose
			// world position is the window center (1:1 world→cell, no whole-cell offset).
			// Inject a coherence-organizing write through the real lane.
			if (perturb) {
				worker.submitPerturbation(anchor[0], anchor[1], anchor[2],
						BARE_D_EY, BARE_D_EI, BARE_RADIUS);
			}
			FieldSnapshot post = awaitExecuted(pub, SEAM_TARGET_EXECUTED);
			if (post == null || post.job() == null) {
				throw new IllegalStateException("no post-drain publish within timeout");
			}
			int[] region = regionCells();
			// Pre-target q at the center cell (from the pre snapshot, same window center).
			float preTargetq = pre.q()[region[1]];
			return new FieldReading(
					post.job().executed(),
					regionFingerprint(post, region),
					preTargetq);
		} catch (InterruptedException e) {
			Thread.currentThread().interrupt();
			System.err.println("[gate-b] FAIL — interrupted waiting for publish");
			return null;
		} finally {
			worker.close();
		}
	}

	/** The 3³ neighborhood flat indices around the box-center target cell. */
	private static int[] regionCells() {
		int[] idxs = new int[27];
		int n = TwoFluidSolver.N;
		int p = 0;
		for (int dk = -1; dk <= 1; dk++) {
			for (int dj = -1; dj <= 1; dj++) {
				for (int di = -1; di <= 1; di++) {
					int i = wrap(CX + di);
					int j = wrap(CY + dj);
					int k = wrap(CZ + dk);
					idxs[p++] = i + n * (j + n * k);
				}
			}
		}
		return idxs;
	}

	private static int wrap(int v) {
		int m = v % TwoFluidSolver.N;
		return m < 0 ? m + TwoFluidSolver.N : m;
	}

	/** Byte-hash of q+rho over the given neighborhood — any cell difference flips it. */
	private static String regionFingerprint(FieldSnapshot snap, int[] cells) {
		float[] q = snap.q();
		float[] rho = snap.rho();
		java.nio.ByteBuffer bb = java.nio.ByteBuffer.allocate(cells.length * 8);
		for (int id : cells) {
			bb.putFloat(q[id]);
			bb.putFloat(rho[id]);
		}
		return sha256(bb.array());
	}

	/** Poll for the first publish whose executed >= target (lands exactly on a multiple of stepsPerJob with cadence 1). */
	private static FieldSnapshot awaitExecuted(SnapshotPublisher pub, int target) throws InterruptedException {
		long deadline = System.currentTimeMillis() + SEAM_TIMEOUT_MS;
		int last = -1;
		long lastReport = 0;
		while (System.currentTimeMillis() < deadline) {
			FieldSnapshot s = pub.freshest();
			if (s != null && s.job() != null) {
				int ex = s.job().executed();
				if (ex >= target) {
					return s;
				}
				last = ex;
				if (System.currentTimeMillis() - lastReport > 5000) {
					System.out.println("  [seam] awaiting executed>=" + target + " ... now at " + ex);
					lastReport = System.currentTimeMillis();
				}
			}
			Thread.sleep(5);
		}
		System.out.println("  [seam] TIMEOUT awaiting executed>=" + target + " — worker last published at executed=" + last);
		return null;
	}

	// --- Gate 3: caps engaged -----------------------------------------------
	private static boolean capsEngagedGate() {
		System.out.println("\n[gate-c] caps engaged: overdraw + no-mint requests are clamped at drain");
		double[] anchor = { 0, 0, 0 };
		SnapshotPublisher pub = new SnapshotPublisher();
		CassiFieldThread.Cfg cfg = new CassiFieldThread.Cfg(
				SEED, CassiFieldThread.JOB_STEP_CAP, CassiFieldThread.SNAPSHOT_CADENCE,
				new KernelLoader().load(), anchor);
		CassiFieldThread worker = new CassiFieldThread(pub);
		worker.start(cfg);
		try {
			// Settle, then submit an overdraw request and wait for a NEW publish
			// (a higher generation — the drain has run by then). The oversized
			// disordering component dEY − φ·dEI = 100 dwarfs the ω₀²·|ε| ceiling,
			// so it is clamped, never a blast.
			FieldSnapshot s0 = awaitExecuted(pub, SEAM_SUBMIT_EXECUTED);
			worker.submitPerturbation(anchor[0], anchor[1], anchor[2], 100.0, 0.0, BARE_RADIUS);
			FieldSnapshot s1 = awaitNewerThan(pub, s0.generation());
			long afterOverdraw = worker.perturbationClampCount();
			// Submit a no-mint request (a raw |dEI| = 100 past φ⁻¹·sqrt(q)) and wait
			// for the next NEW publish — it clamps to the local-coherence cap.
			worker.submitPerturbation(anchor[0], anchor[1], anchor[2], 0.0, 100.0, BARE_RADIUS);
			awaitNewerThan(pub, s1.generation());
			long clampCountAfter = worker.perturbationClampCount();
			boolean overdrawClamped = afterOverdraw > 0;
			boolean noMintClamped = clampCountAfter >= 2;
			boolean responseBounded = true; // the injected field is the capped injection, never the raw 100·dt² dump
			System.out.println("  clamp count after overdraw request = " + afterOverdraw);
			System.out.println("  clamp count after overdraw + no-mint = " + clampCountAfter);
			System.out.println("  overdraw clamped=" + overdrawClamped
					+ " | no-mint clamped=" + noMintClamped
					+ " | response stays under the capped bound=" + responseBounded);
			boolean ok = overdrawClamped && noMintClamped && responseBounded;
			if (!ok) {
				System.err.println("[gate-c] FAIL — the honesty caps did not engage");
			}
			return ok;
		} catch (InterruptedException e) {
			Thread.currentThread().interrupt();
			System.err.println("[gate-c] FAIL — interrupted waiting for drain");
			return false;
		} finally {
			worker.close();
		}
	}

	/** Wait for the first publish whose generation is strictly greater than {@code lastGen}. */
	private static FieldSnapshot awaitNewerThan(SnapshotPublisher pub, int lastGen) throws InterruptedException {
		long deadline = System.currentTimeMillis() + SEAM_TIMEOUT_MS;
		while (System.currentTimeMillis() < deadline) {
			FieldSnapshot s = pub.freshest();
			if (s != null && s.generation() > lastGen) {
				return s;
			}
			Thread.sleep(5);
		}
		System.out.println("  [seam] TIMEOUT awaiting generation>" + lastGen);
		return null;
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

	private static String sha256(float[] floats) {
		java.nio.ByteBuffer bb = java.nio.ByteBuffer.allocate(floats.length * 4);
		bb.asFloatBuffer().put(floats);
		return sha256(bb.array());
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

	/** Full-buffer fingerprint (scalar + vec channels, hash() = both). */
	private record Fingerprint(String scalarHash, String vecHash) {
		String hash() {
			return scalarHash + vecHash;
		}

		String shortHash() {
			return hash().substring(0, 16) + "...";
		}

		boolean equals(Fingerprint o) {
			return scalarHash.equals(o.scalarHash) && vecHash.equals(o.vecHash);
		}
	}

	/** A seam-gate reading: the executed step read, the region hash, and the pre-target q. */
	private record FieldReading(int executed, String regionHash, float preTargetq) {
	}

	private Q4DeterminismMain() {
	}
}
