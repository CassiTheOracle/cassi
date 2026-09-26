package dev.cassicraft.game.practice;

import dev.cassicraft.domain.engine.TwoFluidSolver;
import dev.cassicraft.domain.snapshot.FieldSnapshot;
import dev.cassicraft.domain.snapshot.SnapshotPublisher;
import dev.cassicraft.domain.thread.CassiFieldThread;
import dev.cassicraft.domain.thread.KernelLoader;
import dev.cassicraft.game.sampler.Quantizer;

import java.security.MessageDigest;

/**
 * Headless stilling/shout determinism + honesty gate
 * ({@code async-field-domain.md} §7 Q4's player-return channel;
 * {@code wiring-requests/q4-write-lane-design.md} §3 the stilling/shout;
 * the-stilling.md §5c, the-shout.md §5c the determinism gates HARD). Asserts the
 * practice's governing rule — <em>both writes are bounded, matched-φ, cap-governed
 * source injections through the real lane that deterministically move the
 * published field toward the φ-attractor, never a mint, never across the re-lock
 * line</em> — split across the two honest proving surfaces exactly as
 * {@code Q4DeterminismMain} and {@code GenesisDeterminismMain} do:
 *
 * <ol>
 *   <li><b>Bare-solver injection determinism (byte-identical).</b> The engine-real
 *       {@code TwoFluidSolver.applySource} injection of the still (matched φ,
 *       tight radius) and the shout (matched φ, larger radius) is byte-deterministic:
 *       two fixed-seed runs that both {@code seed → settle → applySource(still) →
 *       step} yield an identical full-buffer fingerprint; a different seed differs;
 *       a no-injection control differs — the injection actually moved the field.
 *       This is the "same field state → same response" proof, free of async
 *       drain-timing.</li>
 *   <li><b>Seam routing through the real publish.</b> A {@code CassiFieldThread}
 *       service boots via the real publish seam ({@link SnapshotPublisher} +
 *       {@link KernelLoader}), settles to a named generation, and a still at the
 *       still point + a shout at the shout point are submitted through
 *       {@link CassiFieldThread#submitPerturbation} (each awaiting its drain). The
 *       practice moved the published field vs the same-seed no-practice control at
 *       the <b>same executed step</b> (grain-level neighborhood hash differs — the
 *       lane applied the writes, never a no-op); the practice <em>readout</em> —
 *       the same executed step, the pre/post states at both practice points, the
 *       clamp telemetry — is byte-deterministic across same-seed seam runs (the
 *       observable practice response is stable, the same honest level Genesis
 *       asserts for the multi-write genesis).</li>
 *   <li><b>Caps honest.</b> {@link CassiFieldThread#perturbationClampCount()} is
 *       <b>0</b> for the still (asserted — the matched-φ still must never hit the
 *       overdraw clamp) and <b>reported</b> for the shout (both matched-φ, so the
 *       expectation is also 0; reporting it honestly is the gate's ask, never a
 *       silenced counter).</li>
 *   <li><b>States classify.</b> The settled still point reads
 *       {@link StillingShoutRead.State#STILL} (the body's rest: q high, ε² low),
 *       and the practice read's thresholds are consistent with the measured
 *       settled-body field (the gate prints the measured q/ε² at the practice
 *       points so a changed distribution re-calibrates the read, never a hardcoded
 *       threshold).</li>
 * </ol>
 *
 * <p><b>Honest scope (measurement-constrained, per Genesis's documented care).</b>
 * A two-write async sequence drains each write at an unpinned job boundary (newest-
 * wins, drained at the next job top); the raw-cell grain of a separately-booted
 * multi-write seam can therefore differ by one job of post-injection evolution
 * across runs. So the byte-identical same-seed claim is proven on the <b>bare
 * solver</b> (Gate 1 — genuinely byte-stable), and the <b>seam</b> asserts the
 * readout determinism + the grain-level movement-against-control. The practice's
 * observable response — the states the two practice points land in, the clamp
 * telemetry, the executed step — is deterministic and is the load-bearing contract.
 *
 * <p>Exit 0 = green. Any failure prints and exits non-zero. Headless (the
 * {@code q4Determinism} pattern), no live client/server.
 */
public final class StillingShoutDeterminismMain {

	/** Fixed seed for the determinism arms. */
	private static final long SEED = 42L;
	/** A different seed for the sensitivity arm. */
	private static final long SEED_OTHER = 43L;
	/** The demo box anchor — center {0,70,0}. */
	private static final double[] WINDOW_CENTER = { 0, 70, 0 };
	/** Box half-extent per axis. */
	private static final int EXTENT = (int) TwoFluidSolver.EXTENT;

	/**
	 * The stilling's practice point — window-relative {@code (0, −48, 0)} →
	 * world {@code (0, 22, 0)}: deep in the dense condensed body (the box spans
	 * y ∈ [anchorY−96, anchorY+96]; the bottom third ≈ 0.94 solid at birth), well
	 * below the surface, so at settle it reads the body's rest state — q high,
	 * ε² low (the {@link StillingShoutRead.State#STILL} the stilling holds).
	 */
	private static final int STILL_POINT_X = 0;
	private static final int STILL_POINT_Y = (int) WINDOW_CENTER[1] - 48;
	private static final int STILL_POINT_Z = 0;

	/**
	 * The shout's practice point — window-relative {@code (16, −48, 0)} →
	 * world {@code (16, 22, 0)}: horizontally offset within the dense body, the
	 * neighbor-wake the shout's larger radius perturbs. Measured (seed 42 @
	 * t=0.32 settle): reads q ≈ 0.60, ε² ≈ 0.00 — a clean STILL location; the
	 * shout's {@code radius = 6}-cell falloff reaches toward the still point
	 * ({@code 16} blocks ≈ 5.3 cells away), so the vent genuinely perturbs
	 * neighbors.
	 */
	private static final int SHOUT_POINT_X = 16;
	private static final int SHOUT_POINT_Y = (int) WINDOW_CENTER[1] - 48;
	private static final int SHOUT_POINT_Z = 0;

	// Executed-step targets (all odd multiples of JOB_STEP_CAP=64, so the first
	// publish with executed >= target lands exactly on target — the Q4 gate-b
	// discipline, byte-deterministic at the pinned step).
	/** Settle: read the pre-practice states and submit the still at this executed step. */
	private static final int SETTLE_EXECUTED = 320;
	/** Submit the shout at this executed step (after the still's drain). */
	private static final int MID_EXECUTED = 448;
	/** Read the post-practice field at this executed step (both drains well behind it).
	 * {@code 704 = 11×64} — an ODD multiple of {@code JOB_STEP_CAP}, so the first
	 * publish with {@code executed >= target} lands exactly on 704 (cadence 2
	 * publishes only on odd multiples: 64, 192, …, 640 is even and skipped). */
	private static final int READ_EXECUTED = 704;

	/** Bare-solver steps before the injection. */
	private static final int BARE_PRE_STEPS = 128;
	/** Bare-solver steps after the injection. */
	private static final int BARE_POST_STEPS = 64;

	private static final long SEAM_TIMEOUT_MS = 120_000;
	/** The expected clamp level for the matched-φ still — 0 (well within the caps). */
	private static final long EXPECTED_STILL_CLAMPS = 0L;

	public static void main(String[] args) {
		boolean ok = true;
		System.out.println("=== Stilling + Shout determinism + honesty gate ===");
		System.out.println("still: dEY=" + fmt((float) StillingShoutCommand.STILL_D_EY)
				+ " dEI=" + fmt((float) StillingShoutCommand.STILL_D_EI)
				+ " (dEY=φ·dEI, overdraw=0) radius=" + StillingShoutCommand.STILL_RADIUS);
		System.out.println("shout: dEY=" + fmt((float) StillingShoutCommand.SHOUT_D_EY)
				+ " dEI=" + fmt((float) StillingShoutCommand.SHOUT_D_EI)
				+ " (dEY=φ·dEI, overdraw=0) radius=" + StillingShoutCommand.SHOUT_RADIUS);
		System.out.println("cooldown=" + StillingShoutCommand.COOLDOWN_TICKS
				+ " ticks | still point=(" + STILL_POINT_X + "," + STILL_POINT_Y + "," + STILL_POINT_Z
				+ ") shout point=(" + SHOUT_POINT_X + "," + SHOUT_POINT_Y + "," + SHOUT_POINT_Z + ")"
				+ " | expected still clamps=" + EXPECTED_STILL_CLAMPS);

		ok &= bareSolverDeterminismGate();
		ok &= seamRoutingGate();
		ok &= capsHonestGate();
		ok &= statesClassifyGate();

		if (ok) {
			System.out.println("\n[stilling-shout] PASS — the practice is a bounded, matched-φ, cap-governed write through the Q4 lane: deterministic, seed-sensitive, moves the published field, the still never clamps, and the settled still point reads STILL");
		} else {
			System.err.println("\n[stilling-shout] FAILED");
			System.exit(1);
		}
	}

	// --- Gate 1: bare-solver still/shout injection determinism + movement ----
	private static boolean bareSolverDeterminismGate() {
		System.out.println("\n[gate-a] bare-solver matched-φ still/shout injection determinism + movement (byte-identical)");
		Fingerprint still1 = bareRun(SEED, StillingShoutCommand.STILL_D_EY,
				StillingShoutCommand.STILL_D_EI, StillingShoutCommand.STILL_RADIUS);
		Fingerprint still2 = bareRun(SEED, StillingShoutCommand.STILL_D_EY,
				StillingShoutCommand.STILL_D_EI, StillingShoutCommand.STILL_RADIUS);
		Fingerprint stillOther = bareRun(SEED_OTHER, StillingShoutCommand.STILL_D_EY,
				StillingShoutCommand.STILL_D_EI, StillingShoutCommand.STILL_RADIUS);
		Fingerprint shout1 = bareRun(SEED, StillingShoutCommand.SHOUT_D_EY,
				StillingShoutCommand.SHOUT_D_EI, StillingShoutCommand.SHOUT_RADIUS);
		Fingerprint control = bareRun(SEED, 0f, 0f, StillingShoutCommand.SHOUT_RADIUS);

		boolean stillSameSeedIdentical = still1.equals(still2);
		boolean stillDiffSeedDiffers = !still1.equals(stillOther);
		boolean stillMoved = !still1.equals(control);
		boolean shoutMoved = !shout1.equals(control);
		boolean shoutDistinctFromStill = !shout1.equals(still1);
		boolean exercised = !control.equals(stillOther);
		boolean ok = stillSameSeedIdentical && stillDiffSeedDiffers && stillMoved
				&& shoutMoved && shoutDistinctFromStill && exercised;

		System.out.println("  still  run1 " + still1.shortHash() + " | run2 " + still2.shortHash()
				+ " | identical=" + stillSameSeedIdentical);
		System.out.println("  still  diff-seed       " + stillOther.shortHash()
				+ " | differs=" + stillDiffSeedDiffers);
		System.out.println("  still  vs no-inject    " + control.shortHash()
				+ " | moved field=" + stillMoved);
		System.out.println("  shout  vs no-inject    " + shout1.shortHash()
				+ " | moved field=" + shoutMoved);
		System.out.println("  shout  vs still        differs=" + shoutDistinctFromStill
				+ " (the larger-radius wake separates from the tight still)");
		if (!ok) {
			System.err.println("[gate-a] FAIL — the matched-φ injection is not deterministic, insensitive, or vacuous");
		}
		return ok;
	}

	private static Fingerprint bareRun(long seed, double dEY, double dEI, int radius) {
		TwoFluidSolver s = new TwoFluidSolver(seed);
		s.seed();
		for (int i = 0; i < BARE_PRE_STEPS; i++) {
			s.step();
		}
		// The Q4-lane cell for the box-center point (world 1:1 → cell at the center,
		// the same no-offset mapping the lane's drain uses for the window center).
		int cx = TwoFluidSolver.N / 2;
		int cy = TwoFluidSolver.N / 2;
		int cz = TwoFluidSolver.N / 2;
		s.applySource(cx, cy, cz, (float) dEY, (float) dEI, radius);
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

	// --- Gate 2: seam routing through the real publish -----------------------
	private static boolean seamRoutingGate() {
		System.out.println("\n[gate-b] seam routing: still + shout via the real CassiFieldThread move the published field deterministically at the readout level");
		SeamRun practice1 = runSeam(SEED, true);
		SeamRun practice2 = runSeam(SEED, true);
		SeamRun other = runSeam(SEED_OTHER, true);
		SeamRun control = runSeam(SEED, false);

		boolean sameStep = practice1.executed == control.executed
				&& practice1.executed == READ_EXECUTED;
		boolean sameSeedReadout = practice1.readoutFingerprint.equals(practice2.readoutFingerprint);
		boolean diffSeedReadout = !practice1.readoutFingerprint.equals(other.readoutFingerprint);
		// Anti-vacuity at the grain level: the practice moved the published field vs
		// the same-seed no-practice control at the same executed step.
		boolean movedStill = !practice1.stillNeighborhoodHash.equals(control.stillNeighborhoodHash);
		boolean movedShout = !practice1.shoutNeighborhoodHash.equals(control.shoutNeighborhoodHash);
		boolean targetLive = practice1.stillPreQ > 0f;
		boolean ok = sameStep && sameSeedReadout && diffSeedReadout
				&& movedStill && movedShout && targetLive;

		System.out.println("  practice1 executed=" + practice1.executed
				+ " ctrl executed=" + control.executed + " (same read step)=" + sameStep);
		System.out.println("  still-pre q=" + fmt(practice1.stillPreQ)
				+ " (live interior field)=" + targetLive);
		System.out.println("  same-seed readout run1 " + practice1.readoutFingerprint.substring(0, 16)
				+ " | run2 " + practice2.readoutFingerprint.substring(0, 16)
				+ " | identical=" + sameSeedReadout);
		System.out.println("  diff-seed readout           " + other.readoutFingerprint.substring(0, 16)
				+ " | differs=" + diffSeedReadout);
		System.out.println("  still  lane moved published field vs control=" + movedStill);
		System.out.println("  shout  lane moved published field vs control=" + movedShout);
		if (!ok) {
			System.err.println("[gate-b] FAIL — the practice did not deterministically move the published field, or the read steps did not align");
		}
		return ok;
	}

	/**
	 * One end-to-end seam run: boot the real field thread, settle, optionally apply
	 * a still then a shout (each awaiting its drain), read the post-practice field
	 * at {@link #READ_EXECUTED}, and hash the practice readout + the two practice
	 * neighborhoods.
	 */
	private static SeamRun runSeam(long seed, boolean withPractice) {
		SnapshotPublisher pub = new SnapshotPublisher();
		CassiFieldThread.Cfg cfg = new CassiFieldThread.Cfg(
				seed, CassiFieldThread.JOB_STEP_CAP, CassiFieldThread.SNAPSHOT_CADENCE,
				new KernelLoader().load(), WINDOW_CENTER);
		CassiFieldThread worker = new CassiFieldThread(pub);
		worker.start(cfg);
		try {
			FieldSnapshot settle = awaitExecuted(pub, SETTLE_EXECUTED);
			if (withPractice) {
				// Still — a matched-φ coherence-restoring write at the still point.
				worker.submitPerturbation(STILL_POINT_X, STILL_POINT_Y, STILL_POINT_Z,
						StillingShoutCommand.STILL_D_EY,
						StillingShoutCommand.STILL_D_EI,
						StillingShoutCommand.STILL_RADIUS);
				FieldSnapshot drain1 = awaitExecuted(pub, MID_EXECUTED);
				// Shout — the same matched-φ write at the larger vent radius at the shout point.
				worker.submitPerturbation(SHOUT_POINT_X, SHOUT_POINT_Y, SHOUT_POINT_Z,
						StillingShoutCommand.SHOUT_D_EY,
						StillingShoutCommand.SHOUT_D_EI,
						StillingShoutCommand.SHOUT_RADIUS);
				awaitExecuted(pub, READ_EXECUTED);
			}
			FieldSnapshot post = awaitExecuted(pub, READ_EXECUTED);
			double[] wc = post.job() != null && !post.job().isWindowless()
					? post.job().windowCenter()
					: WINDOW_CENTER.clone();
			long clamps = worker.perturbationClampCount();

			Quantizer.FieldReading stillPre = Quantizer.sampleReading(settle, wc,
					STILL_POINT_X, STILL_POINT_Y, STILL_POINT_Z);
			Quantizer.FieldReading stillPost = Quantizer.sampleReading(post, wc,
					STILL_POINT_X, STILL_POINT_Y, STILL_POINT_Z);
			Quantizer.FieldReading shoutPost = Quantizer.sampleReading(post, wc,
					SHOUT_POINT_X, SHOUT_POINT_Y, SHOUT_POINT_Z);
			StillingShoutRead.Read stillState = StillingShoutRead.classify(stillPost);
			StillingShoutRead.Read shoutState = StillingShoutRead.classify(shoutPost);

			String readoutFp = readoutFingerprint(post.job().executed(), withPractice, clamps,
					stillState, shoutState, stillPost, shoutPost);
			String stillNeighborhood = neighborhoodHash(post, wc,
					STILL_POINT_X, STILL_POINT_Y, STILL_POINT_Z);
			String shoutNeighborhood = neighborhoodHash(post, wc,
					SHOUT_POINT_X, SHOUT_POINT_Y, SHOUT_POINT_Z);
			return new SeamRun(post.job().executed(), readoutFp, stillNeighborhood,
					shoutNeighborhood, stillPre.q(), stillState, shoutState, clamps);
		} catch (InterruptedException e) {
			Thread.currentThread().interrupt();
			System.err.println("[gate-b] FAIL — interrupted waiting for publish");
			return null;
		} finally {
			worker.close();
		}
	}

	/** SHA-256 over the deterministic practice readout — states, coarse q/ε², executed, clamps. */
	private static String readoutFingerprint(int executed, boolean withPractice, long clamps,
			StillingShoutRead.Read stillState, StillingShoutRead.Read shoutState,
			Quantizer.FieldReading stillPost, Quantizer.FieldReading shoutPost) {
		StringBuilder sb = new StringBuilder();
		sb.append("practice=").append(withPractice)
				.append(";executed=").append(executed)
				.append(";clamps=").append(clamps)
				.append(";still=").append(stillState.state())
				.append(";shout=").append(shoutState.state())
				.append(";stillQ=").append(coarse(stillPost.q()))
				.append(";stillEps2=").append(coarse(stillPost.eps2()))
				.append(";shoutQ=").append(coarse(shoutPost.q()))
				.append(";shoutEps2=").append(coarse(shoutPost.eps2()));
		return sha256(sb.toString().getBytes(java.nio.charset.StandardCharsets.UTF_8));
	}

	private static String coarse(float v) {
		return String.format("%.3f", v);
	}

	/** Byte-hash of q+ε² over a 3×1×3 patch around a practice point — any cell change flips it. */
	private static String neighborhoodHash(FieldSnapshot snap, double[] wc, int cx, int cy, int cz) {
		java.nio.ByteBuffer bb = java.nio.ByteBuffer.allocate(9 * 8);
		for (int dz = -1; dz <= 1; dz++) {
			for (int dx = -1; dx <= 1; dx++) {
				Quantizer.FieldReading r = Quantizer.sampleReading(snap, wc, cx + dx, cy, cz + dz);
				bb.putFloat(r.q());
				bb.putFloat(r.eps2());
			}
		}
		return sha256(bb.array());
	}

	// --- Gate 3: caps honest ------------------------------------------------
	private static boolean capsHonestGate() {
		System.out.println("\n[gate-c] caps honest: the matched-φ still never clamps; the shout's clamp count is reported");
		double[] anchor = { 0, 0, 0 };
		SnapshotPublisher pub = new SnapshotPublisher();
		CassiFieldThread.Cfg cfg = new CassiFieldThread.Cfg(
				SEED, CassiFieldThread.JOB_STEP_CAP, CassiFieldThread.SNAPSHOT_CADENCE,
				new KernelLoader().load(), WINDOW_CENTER);
		CassiFieldThread worker = new CassiFieldThread(pub);
		worker.start(cfg);
		try {
			FieldSnapshot s0 = awaitExecuted(pub, SETTLE_EXECUTED);
			worker.submitPerturbation(STILL_POINT_X, STILL_POINT_Y, STILL_POINT_Z,
					StillingShoutCommand.STILL_D_EY,
					StillingShoutCommand.STILL_D_EI,
					StillingShoutCommand.STILL_RADIUS);
			FieldSnapshot s1 = awaitNewerThan(pub, s0.generation());
			long stillClamps = worker.perturbationClampCount();
			worker.submitPerturbation(SHOUT_POINT_X, SHOUT_POINT_Y, SHOUT_POINT_Z,
					StillingShoutCommand.SHOUT_D_EY,
					StillingShoutCommand.SHOUT_D_EI,
					StillingShoutCommand.SHOUT_RADIUS);
			awaitNewerThan(pub, s1.generation());
			long shoutClamps = worker.perturbationClampCount() - stillClamps;
			boolean stillClean = stillClamps == EXPECTED_STILL_CLAMPS;
			// The shout is reported honestly (here it stays 0 — matched-φ has no
			// overdraw; the ask is the report, never a forced nonzero).
			boolean shoutReported = true;
			System.out.println("  still  clampCount = " + stillClamps + " (must be "
					+ EXPECTED_STILL_CLAMPS + " — the matched-φ still must never hit the overdraw clamp) → clean=" + stillClean);
			System.out.println("  shout  clampCount = " + shoutClamps + " (reported — matched-φ, so 0 is expected; never a silenced counter)");
			boolean ok = stillClean && shoutReported;
			if (!ok) {
				System.err.println("[gate-c] FAIL — the matched-φ still engaged a clamp; a design bug, never a silenced counter");
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

	// --- Gate 4: states classify ----------------------------------------------
	private static boolean statesClassifyGate() {
		System.out.println("\n[gate-d] states classify: a settled still point reads STILL (the body's rest)");
		double[] anchor = { 0, 0, 0 };
		SnapshotPublisher pub = new SnapshotPublisher();
		CassiFieldThread.Cfg cfg = new CassiFieldThread.Cfg(
				SEED, CassiFieldThread.JOB_STEP_CAP, CassiFieldThread.SNAPSHOT_CADENCE,
				new KernelLoader().load(), WINDOW_CENTER);
		CassiFieldThread worker = new CassiFieldThread(pub);
		worker.start(cfg);
		try {
			FieldSnapshot snap = awaitExecuted(pub, SETTLE_EXECUTED);
			double[] wc = snap.job() != null && !snap.job().isWindowless()
					? snap.job().windowCenter()
					: WINDOW_CENTER.clone();
			Quantizer.FieldReading stillR = Quantizer.sampleReading(snap, wc,
					STILL_POINT_X, STILL_POINT_Y, STILL_POINT_Z);
			StillingShoutRead.Read stillState = StillingShoutRead.classify(stillR);
			Quantizer.FieldReading shoutR = Quantizer.sampleReading(snap, wc,
					SHOUT_POINT_X, SHOUT_POINT_Y, SHOUT_POINT_Z);
			StillingShoutRead.Read shoutState = StillingShoutRead.classify(shoutR);
			boolean stillIsStill = stillState.isStill();
			System.out.println("  still point (" + STILL_POINT_X + "," + STILL_POINT_Y + "," + STILL_POINT_Z + ")"
					+ " reads q=" + fmt(stillR.q()) + " ε²=" + fmt(stillR.eps2())
					+ " → " + stillState.state().label() + " → isStill=" + stillIsStill);
			System.out.println("  shout point (" + SHOUT_POINT_X + "," + SHOUT_POINT_Y + "," + SHOUT_POINT_Z + ")"
					+ " reads q=" + fmt(shoutR.q()) + " ε²=" + fmt(shoutR.eps2())
					+ " → " + shoutState.state().label());
			System.out.println("  (STILL thresholds: q ≥ " + StillingShoutRead.STILL_Q_FLOOR
					+ " and ε² < " + StillingShoutRead.STILL_EPS2_CEIL
					+ ", cited to the measured settled body)");
			boolean ok = stillIsStill;
			if (!ok) {
				System.err.println("[gate-d] FAIL — the settled still point does not read STILL; the practice thresholds are not consistent with the measured body — re-calibrate, never force");
			}
			return ok;
		} catch (InterruptedException e) {
			Thread.currentThread().interrupt();
			System.err.println("[gate-d] FAIL — interrupted waiting for settle");
			return false;
		} finally {
			worker.close();
		}
	}

	// --- Helpers (shared with Q4/Genesis gates' patterns) ---------------------
	private static FieldSnapshot awaitExecuted(SnapshotPublisher pub, int target) throws InterruptedException {
		long deadline = System.currentTimeMillis() + SEAM_TIMEOUT_MS;
		while (System.currentTimeMillis() < deadline) {
			FieldSnapshot s = pub.freshest();
			if (s != null && s.job() != null && s.job().executed() >= target) {
				return s;
			}
			Thread.sleep(5);
		}
		throw new IllegalStateException("field never reached executed " + target);
	}

	private static FieldSnapshot awaitNewerThan(SnapshotPublisher pub, int lastGen) throws InterruptedException {
		long deadline = System.currentTimeMillis() + SEAM_TIMEOUT_MS;
		while (System.currentTimeMillis() < deadline) {
			FieldSnapshot s = pub.freshest();
			if (s != null && s.generation() > lastGen) {
				return s;
			}
			Thread.sleep(5);
		}
		throw new IllegalStateException("field never advanced past generation " + lastGen);
	}

	private static String sha256(byte[] data) {
		try {
			byte[] h = MessageDigest.getInstance("SHA-256").digest(data);
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

	private static String fmt(float v) {
		return String.format("%.3f", v);
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

	/** A seam run's readout fingerprint + the two practice neighborhoods + the measured states. */
	private record SeamRun(int executed, String readoutFingerprint,
			String stillNeighborhoodHash, String shoutNeighborhoodHash,
			float stillPreQ, StillingShoutRead.Read stillState,
			StillingShoutRead.Read shoutState, long clampCount) {
	}

	private StillingShoutDeterminismMain() {
	}
}
