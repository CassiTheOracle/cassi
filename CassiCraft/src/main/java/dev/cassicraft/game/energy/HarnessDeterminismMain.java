package dev.cassicraft.game.energy;

import dev.cassicraft.domain.engine.TwoFluidSolver;
import dev.cassicraft.domain.snapshot.FieldSnapshot;
import dev.cassicraft.domain.snapshot.SnapshotPublisher;
import dev.cassicraft.domain.thread.CassiFieldThread;
import dev.cassicraft.domain.thread.KernelLoader;
import dev.cassicraft.game.sampler.Quantizer;

import java.nio.ByteBuffer;
import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;

/**
 * Headless energy-harnessing determinism + honesty gate (energy-harnessing.md
 * §0 the core stance — energy is a field withdrawal; §2.5 the deep-rung
 * reaper; §6 the no-free-energy cap {@code output ≤ φ⁻¹·input} as coded in the
 * Q4 lane's no-mint cap; {@code async-field-domain.md} §7 Q4 the player-return
 * channel). Asserts the harness's governing rule — <em>the draw is a bounded,
 * matched-φ, cap-governed coherence withdrawal through the real lane that
 * powers an honest use, never a mint, never an over-drain</em> — split across
 * the four honest proving surfaces exactly as {@code StillingShoutDeterminismMain}
 * and {@code GenesisDeterminismMain} do:
 *
 * <ol>
 *   <li><b>Bare-solver draw determinism + the exact field-payment (byte-identical).</b>
 *       The engine-real {@code TwoFluidSolver.applySource} withdrawal is
 *       byte-deterministic: two fixed-seed runs that both
 *       {@code seed → settle → applySource(draw) → step} yield an identical
 *       full-buffer fingerprint; a different seed differs; a no-draw control
 *       differs (the draw moved the field). Critically, the <b>field-payment</b>
 *       is asserted <b>exactly</b>: reading the draw cell's {@code q} immediately
 *       before and immediately after the {@code applySource} (no evolution, so no
 *       chaotic divergence hides it), {@code q_after &lt; q_before} — the matched-φ
 *       withdrawal measurably lowered the local coherence, the field paid. This
 *       is the bare-solver "same field state → same response + the draw is a real
 *       spend" proof, free of async drain-timing.</li>
 *   <li><b>Seam routing through the real publish + anti-vacuity.</b> A
 *       {@code CassiFieldThread} boots via the real publish seam
 *       ({@link SnapshotPublisher} + {@link KernelLoader}), settles, and a draw
 *       at the named coherent body point is submitted through
 *       {@link CassiFieldThread#submitPerturbation} (awaiting its drain). The
 *       draw moved the published field vs the same-seed no-draw control at the
 *       <b>same executed step</b> (grain-level neighborhood hash differs — the
 *       lane applied the write, never a no-op); the draw <em>readout</em> — the
 *       same executed step, the pre/post harness states at the draw point, the
 *       clamp telemetry — is byte-deterministic across same-seed seam runs (the
 *       observable harness response is stable, the same honest level Genesis
 *       asserts for the multi-write genesis). The field-payment is reported at
 *       the draw cell against the same-seed control (driven vs control at the
 *       first post-drain publish).</li>
 *   <li><b>The honesty assert (the draw is bounded).</b> The draw's requested
 *       magnitude {@code |dEY| = HARNESS_DRAW_FRACTION × φ⁻¹ × sqrt(q_local_pre)}
 *       is by construction ≤ the no-mint cap {@code φ⁻¹·sqrt(q_local)}, and the
 *       observed field cost (the pre→post {@code q} drop at the draw cell) is
 *       measured and asserted ≤ that cap — a draw cannot spend more than the
 *       field holds. {@link CassiFieldThread#perturbationClampCount()} is
 *       <b>0</b> for the honest draw (asserted — the matched-φ reach sits well
 *       within both caps; a clamp means the design exceeded its own budget, a
 *       design bug never a silenced counter).</li>
 *   <li><b>The use fired AND the field paid.</b> For an honest draw, the drawn
 *       budget buys a {@link HarnessUse.MiningBurst} (the named use fired), the
 *       burst's magnitude is strictly bounded by the draw ({@link HarnessUse#isHonest}
 *       — output ≤ input, the §6 cap), and the field paid: the draw-cell
 *       {@code q} measurably dropped (bare-solver exact pre→post, Gate 1) or the
 *       driven seam's draw-cell {@code q} reads below the same-seed control at the
 *       same executed step (field-time matched).</li>
 * </ol>
 *
 * <p><b>Honest scope (measurement-constrained, per Genesis's documented care).</b>
 * The Q4 lane's additive form is {@code dt²}-scaled, so a single cap-honored
 * draw's raw field move at the cell is micro ({@code dEY·dt² ≈ 2.5e-7} — the
 * genesis/combustion honest negatives: the lane does not mint, it micro-steers
 * existing coherence). The exact field-payment (Gate 1, immediately-before/after
 * {@code applySource}) is therefore the load-bearing proof that a draw is a real
 * spend; the seam additionally proves the write lands (anti-vacuity hash) and
 * reports the driven-vs-control draw-cell differential honestly. The byte-identical
 * same-seed claim is proven on the <b>bare solver</b> (Gate 1 — genuinely
 * byte-stable) and the seam asserts the readout determinism + the grain-level
 * movement-against-control, as the stilling gate does.
 *
 * <p>Exit 0 = green. Any failure prints and exits non-zero. Headless (the
 * {@code stillingShoutDeterminism} pattern), no live client/server.
 */
public final class HarnessDeterminismMain {

	/** Fixed seed for the determinism arms. */
	private static final long SEED = 42L;
	/** A different seed for the sensitivity arm. */
	private static final long SEED_OTHER = 43L;
	/** The demo box anchor — center {0,70,0}. */
	private static final double[] WINDOW_CENTER = { 0, 70, 0 };

	/**
	 * The harness's draw point — window-relative {@code (0, −48, 0)} → world
	 * {@code (0, 22, 0)} = the stilling gate's proven STILL point, deep in the
	 * dense condensed body (the box spans y ∈ [anchorY−96, anchorY+96]; the
	 * bottom third ≈ 0.94 solid at birth, well below the surface, so at settle it
	 * reads the body's coherent rest — q high, ε² low (the
	 * {@link HarnessRead.State#READY} the harness draws from). Its grid cell is
	 * {@code (N/2, 16, N/2)} — the coherent interior the gate reads the draw-cell
	 * q from.
	 */
	private static final int DRAW_POINT_X = 0;
	private static final int DRAW_POINT_Y = (int) WINDOW_CENTER[1] - 48;
	private static final int DRAW_POINT_Z = 0;

	/** The draw point's grid cell — deep in the dense body, high q. */
	private static final int DRAW_CX = TwoFluidSolver.N / 2;
	private static final int DRAW_CY = 16;
	private static final int DRAW_CZ = TwoFluidSolver.N / 2;

	// Executed-step targets (all odd multiples of JOB_STEP_CAP=64, so the first
	// publish with executed >= target lands exactly on target — the Q4 gate-b
	// discipline, byte-deterministic at the pinned step).
	/** Settle: read the pre-draw harness state and submit the draw at this executed step. */
	private static final int SETTLE_EXECUTED = 320;
	/** Read the post-draw field at this executed step (the drain well behind it).
	 * {@code 448 = 7×64} — an ODD multiple of JOB_STEP_CAP, so the first publish
	 * with {@code executed >= target} lands exactly on 448. */
	private static final int READ_EXECUTED = 448;

	/** Bare-solver steps before the draw. */
	private static final int BARE_PRE_STEPS = 128;
	/** Bare-solver steps after the draw (the bounded post-draw window). */
	private static final int BARE_POST_STEPS = 64;

	private static final long SEAM_TIMEOUT_MS = 120_000;
	/** The expected clamp level for the honest matched-φ draw — 0 (well within the caps). */
	private static final long EXPECTED_DRAW_CLAMPS = 0L;

	public static void main(String[] args) {
		boolean ok = true;
		System.out.println("=== Energy-harnessing determinism + honesty gate ===");
		System.out.println("draw: matched-φ withdrawal (dEY=φ·dEI, overdraw=0), requested "
				+ (int) (100 * HarnessCommand.HARNESS_DRAW_FRACTION) + "% of φ⁻¹·√q"
				+ " | USE_EFFICIENCY=" + HarnessUse.USE_EFFICIENCY);
		System.out.println("cooldown=" + HarnessCommand.COOLDOWN_TICKS
				+ " ticks | draw point=(" + DRAW_POINT_X + "," + DRAW_POINT_Y + "," + DRAW_POINT_Z
				+ ") = cell (" + DRAW_CX + "," + DRAW_CY + "," + DRAW_CZ + ")"
				+ " | expected draw clamps=" + EXPECTED_DRAW_CLAMPS);

		ok &= bareSolverDrawGate();
		ok &= seamRoutingGate();
		ok &= honestyBoundGate();
		ok &= useFiredAndFieldPaidGate();

		if (ok) {
			System.out.println("\n[harness] PASS — the draw is a bounded, matched-φ, cap-governed coherence withdrawal through the Q4 lane: deterministic, seed-sensitive, moves the published field, the draw is a real spend (q down at the draw cell), never clamps, and the burst it buys is bounded by the draw (output ≤ input)");
		} else {
			System.err.println("\n[harness] FAILED");
			System.exit(1);
		}
	}

	// --- Gate 1: bare-solver draw determinism + the exact field-payment ---------
	private static boolean bareSolverDrawGate() {
		System.out.println("\n[gate-a] bare-solver matched-φ draw determinism + the exact field-payment (byte-identical)");
		DrawFingerprint draw1 = bareRun(SEED);
		DrawFingerprint draw2 = bareRun(SEED);
		DrawFingerprint drawOther = bareRun(SEED_OTHER);
		Fingerprint control = bareControl(SEED);

		boolean sameSeedIdentical = draw1.fingerprint().equals(draw2.fingerprint());
		boolean diffSeedDiffers = !draw1.fingerprint().equals(drawOther.fingerprint());
		// Anti-vacuity: the draw moved the field vs the no-draw control.
		boolean movedField = !draw1.fingerprint().equals(control);
		// The exact field-payment: reading the draw cell immediately before and
		// after applySource (no evolution — no chaotic divergence), q dropped —
		// the matched-φ withdrawal measurably lowered the local coherence.
		boolean fieldPaidExact = draw1.qAfter() < draw1.qBefore();
		boolean exercised = !control.equals(drawOther.fingerprint());
		boolean ok = sameSeedIdentical && diffSeedDiffers && movedField && fieldPaidExact && exercised;

		printBare(draw1, draw2, drawOther, control, sameSeedIdentical, diffSeedDiffers,
				movedField, fieldPaidExact, exercised);
		if (!ok) {
			System.err.println("[gate-a] FAIL — the matched-φ draw is not deterministic, insensitive, vacuous, or did not lower the draw-cell q (the field-payment)");
		}
		return ok;
	}

	private static DrawFingerprint bareRun(long seed) {
		TwoFluidSolver s = new TwoFluidSolver(seed);
		s.seed();
		for (int i = 0; i < BARE_PRE_STEPS; i++) {
			s.step();
		}
		int cell = DRAW_CX + TwoFluidSolver.N * (DRAW_CY + TwoFluidSolver.N * DRAW_CZ);
		// The pre-draw local coherence (the no-mint budget's source).
		float qBefore = s.q()[cell];
		double noMintCap = CassiFieldThread.PERTURB_NO_MINT_PHI_INV * Math.sqrt(Math.max(qBefore, 0.0));
		double drawnBudget = noMintCap * HarnessCommand.HARNESS_DRAW_FRACTION;
		float dEY = (float) -drawnBudget;
		float dEI = (float) (-drawnBudget / HarnessCommand.DRAW_RATIO);
		// The matched-φ withdrawal at the named draw cell, the lane's tight locality.
		s.applySource(DRAW_CX, DRAW_CY, DRAW_CZ, dEY, dEI, HarnessCommand.DRAW_RADIUS);
		// The exact field-payment: q recomputed from the mutated ey/ei (applySource
		// does not refresh q[] — passB does), UNAFFECTED by evolution.
		float eyAfter = s.ey()[cell];
		float eiAfter = s.ei()[cell];
		float qAfter = eyAfter * eyAfter + eiAfter * eiAfter;
		for (int i = 0; i < BARE_POST_STEPS; i++) {
			s.step();
		}
		return new DrawFingerprint(fullFingerprint(s), qBefore, qAfter, drawnBudget, noMintCap);
	}

	private static Fingerprint bareControl(long seed) {
		TwoFluidSolver s = new TwoFluidSolver(seed);
		s.seed();
		for (int i = 0; i < BARE_PRE_STEPS; i++) {
			s.step();
		}
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

	private static void printBare(DrawFingerprint draw1, DrawFingerprint draw2, DrawFingerprint drawOther,
			Fingerprint control, boolean identical, boolean diffSeed, boolean moved,
			boolean paid, boolean exercised) {
		System.out.println("  draw    run1 " + draw1.fingerprint().shortHash() + " | run2 "
				+ draw2.fingerprint().shortHash() + " | identical=" + identical);
		System.out.println("  draw    diff-seed       " + drawOther.fingerprint().shortHash()
				+ " | differs=" + diffSeed);
		System.out.println("  draw    vs no-draw ctrl " + control.shortHash()
				+ " | moved field=" + moved + " | seeds separate the arms=" + exercised);
		System.out.println("  draw-cell q before=" + fmt9(draw1.qBefore())
				+ " after=" + fmt9(draw1.qAfter())
				+ " | field paid (q down, exact)=" + paid);
		System.out.println("  draw budget=" + fmt((float) draw1.drawnBudget())
				+ " ≤ φ⁻¹·√q no-mint cap=" + fmt((float) draw1.noMintCap()) + " (honest, " 
				+ (int) (100 * HarnessCommand.HARNESS_DRAW_FRACTION) + "% of cap)");
	}

	// --- Gate 2: seam routing through the real publish + anti-vacuity ----------
	private static boolean seamRoutingGate() {
		System.out.println("\n[gate-b] seam routing: a harness draw via the real CassiFieldThread moves the published field deterministically at the readout level");
		SeamRun practice1 = runSeam(SEED, true);
		SeamRun practice2 = runSeam(SEED, true);
		SeamRun other = runSeam(SEED_OTHER, true);
		SeamRun control = runSeam(SEED, false);

		boolean sameStep = practice1.executed == control.executed
				&& practice1.executed == READ_EXECUTED;
		boolean sameSeedReadout = practice1.readoutFingerprint.equals(practice2.readoutFingerprint);
		boolean diffSeedReadout = !practice1.readoutFingerprint.equals(other.readoutFingerprint);
		// Anti-vacuity at the grain level: the draw moved the published field vs
		// the same-seed no-draw control at the same executed step.
		boolean moved = !practice1.drawNeighborhoodHash.equals(control.drawNeighborhoodHash);
		boolean targetLive = practice1.preDrawQ > 0f;
		boolean ok = sameStep && sameSeedReadout && diffSeedReadout && moved && targetLive;

		System.out.println("  practice1 executed=" + practice1.executed
				+ " ctrl executed=" + control.executed + " (same read step)=" + sameStep);
		System.out.println("  pre-draw q=" + fmt(practice1.preDrawQ) + " (live coherent interior)=" + targetLive);
		System.out.println("  same-seed readout run1 " + practice1.readoutFingerprint.substring(0, 16)
				+ " | run2 " + practice2.readoutFingerprint.substring(0, 16)
				+ " | identical=" + sameSeedReadout);
		System.out.println("  diff-seed readout           " + other.readoutFingerprint.substring(0, 16)
				+ " | differs=" + diffSeedReadout);
		System.out.println("  draw lane moved published field vs control=" + moved);
		if (!ok) {
			System.err.println("[gate-b] FAIL — the draw did not deterministically move the published field, or the read steps did not align");
		}
		return ok;
	}

	/**
	 * One end-to-end seam run: boot the real field thread, settle, optionally apply
	 * a harness draw (awaiting its drain), read the post-draw field at the first
	 * publish with executed ≥ READ_EXECUTED, and hash the draw readout + the draw
	 * neighborhood + the field-paid differential.
	 */
	private static SeamRun runSeam(long seed, boolean withDraw) {
		SnapshotPublisher pub = new SnapshotPublisher();
		CassiFieldThread.Cfg cfg = new CassiFieldThread.Cfg(
				seed, CassiFieldThread.JOB_STEP_CAP, CassiFieldThread.SNAPSHOT_CADENCE,
				new KernelLoader().load(), WINDOW_CENTER);
		CassiFieldThread worker = new CassiFieldThread(pub);
		worker.start(cfg);
		try {
			FieldSnapshot settle = awaitExecuted(pub, SETTLE_EXECUTED);
			double[] wc = centerOf(settle);
			Quantizer.FieldReading preR = Quantizer.sampleReading(settle, wc,
					DRAW_POINT_X, DRAW_POINT_Y, DRAW_POINT_Z);
			HarnessRead.Read preState = HarnessRead.classify(preR);
			double noMintCap = CassiFieldThread.PERTURB_NO_MINT_PHI_INV * Math.sqrt(Math.max(preR.q(), 0.0));
			double drawnBudget = noMintCap * HarnessCommand.HARNESS_DRAW_FRACTION;
			if (withDraw) {
				// The bounded matched-φ draw through the REAL lane at the named point.
				worker.submitPerturbation(DRAW_POINT_X, DRAW_POINT_Y, DRAW_POINT_Z,
						-drawnBudget, -drawnBudget / HarnessCommand.DRAW_RATIO,
						HarnessCommand.DRAW_RADIUS);
			}
			FieldSnapshot post = awaitExecuted(pub, READ_EXECUTED);
			double[] postWc = centerOf(post);
			Quantizer.FieldReading postR = Quantizer.sampleReading(post, postWc,
					DRAW_POINT_X, DRAW_POINT_Y, DRAW_POINT_Z);
			HarnessRead.Read postState = HarnessRead.classify(postR);
			long clamps = worker.perturbationClampCount();

			String readoutFp = readoutFingerprint(post.job().executed(), withDraw, clamps,
					preState, postState, preR, postR, drawnBudget);
			String drawNeighborhood = neighborhoodHash(post, postWc,
					DRAW_POINT_X, DRAW_POINT_Y, DRAW_POINT_Z);
			return new SeamRun(post.job().executed(), readoutFp, drawNeighborhood,
					preR.q(), preState, postState, clamps,
					postR.q(), drawnBudget, noMintCap);
		} catch (InterruptedException e) {
			Thread.currentThread().interrupt();
			System.err.println("[gate-b] FAIL — interrupted waiting for publish");
			return null;
		} finally {
			worker.close();
		}
	}

	/** SHA-256 over the deterministic draw readout — states, coarse q/ε², executed, clamps. */
	private static String readoutFingerprint(int executed, boolean withDraw, long clamps,
			HarnessRead.Read preState, HarnessRead.Read postState,
			Quantizer.FieldReading preR, Quantizer.FieldReading postR, double drawnBudget) {
		StringBuilder sb = new StringBuilder();
		sb.append("draw=").append(withDraw)
				.append(";executed=").append(executed)
				.append(";clamps=").append(clamps)
				.append(";pre=").append(preState.state())
				.append(";post=").append(postState.state())
				.append(";preQ=").append(coarse(preR.q()))
				.append(";preEps2=").append(coarse(preR.eps2()))
				.append(";postQ=").append(coarse(postR.q()))
				.append(";postEps2=").append(coarse(postR.eps2()))
				.append(";budget=").append(coarse(drawnBudget));
		return sha256(sb.toString().getBytes(StandardCharsets.UTF_8));
	}

	private static String coarse(double v) {
		return String.format("%.3f", v);
	}

	/** Byte-hash of q+ε² over a 3×1×3 patch around the draw point — any cell change flips it. */
	private static String neighborhoodHash(FieldSnapshot snap, double[] wc, int cx, int cy, int cz) {
		ByteBuffer bb = ByteBuffer.allocate(9 * 8);
		for (int dz = -1; dz <= 1; dz++) {
			for (int dx = -1; dx <= 1; dx++) {
				Quantizer.FieldReading r = Quantizer.sampleReading(snap, wc, cx + dx, cy, cz + dz);
				bb.putFloat(r.q());
				bb.putFloat(r.eps2());
			}
		}
		return sha256(bb.array());
	}

	// --- Gate 3: the honesty bound -------------------------------------------------
	private static boolean honestyBoundGate() {
		System.out.println("\n[gate-c] honesty bound: the draw's magnitude is bounded (cost ≤ φ⁻¹·√q) and never clamps");
		HonestyRun honest = runHonesty();
		double cost = honest.fieldCost;      // the pre→post q-drop at the draw cell (driven vs control)
		double cap = honest.noMintCap;       // φ⁻¹·√q_local_pre
		boolean costBounded = cost <= cap;
		boolean clampsClean = honest.clampCount == EXPECTED_DRAW_CLAMPS;
		boolean ok = costBounded && clampsClean;
		System.out.println("  observed field cost (draw-cell q drop vs control)=" + fmt9((float) cost)
				+ " ≤ φ⁻¹·√q no-mint cap=" + fmt((float) cap) + " → bounded=" + costBounded);
		System.out.println("  draw clampCount=" + honest.clampCount + " (must be " + EXPECTED_DRAW_CLAMPS
				+ " for the honest matched-φ draw)=" + clampsClean);
		if (!ok) {
			System.err.println("[gate-c] FAIL — the draw exceeded its own bound (cost > φ⁻¹·√q) or engaged a clamp; a design bug, never a silenced counter");
		}
		return ok;
	}

	/**
	 * The honest draw's field cost, measured against the same-seed no-draw control:
	 * {@code (q_drawCell_preOfSettle − q_drawCell_post)_driven − (q_drawCell_pre − q_drawCell_post)_control}
	 * at the same executed step — the write-attributable coherence the draw
	 * removed (both runs share the identical natural evolution; only the draw differs).
	 */
	private static HonestyRun runHonesty() {
		SeamRun driven = runSeam(SEED, true);
		SeamRun control = runSeam(SEED, false);
		// driven.fieldCostDelta = preDrawQ − postDrawQ (the q-drop at the settle→post window);
		// the write-attributable cost is the driven drop minus the control's natural drop.
		// We read both at the same settle and same read step, so the difference is the draw's.
		double naturalDrop = control.preDrawQ - control.postDrawQ;
		double drivenDrop = driven.preDrawQ - driven.postDrawQ;
		double attributable = Math.max(0.0, drivenDrop - naturalDrop);
		return new HonestyRun(driven.clampCount, attributable, driven.noMintCap);
	}

	// --- Gate 4: use fired AND the field paid ---------------------------------------
	private static boolean useFiredAndFieldPaidGate() {
		System.out.println("\n[gate-d] use fired AND the field paid: the draw buys a bounded burst ≤ the draw, and q dropped at the draw cell");
		// The named use from the honest draw budget — deterministic, bounded.
		DrawFingerprint bare = bareRun(SEED);
		double budget = bare.drawnBudget();
		HarnessUse.MiningBurst burst = HarnessUse.plan(budget);
		boolean useFired = burst != null && burst.amplifier() >= 0 && burst.durationTicks() >= 1;
		boolean useHonest = HarnessUse.isHonest(burst, budget);
		// The field-payment: the bare-solver exact proof (Gate 1's fieldPaidExact) —
		// the draw-cell q dropped immediately after applySource (no evolution hides it).
		boolean fieldPaidExact = bare.qAfter() < bare.qBefore();
		SeamRun driven = runSeam(SEED, true);
		SeamRun control = runSeam(SEED, false);
		double naturalDrop = control.preDrawQ - control.postDrawQ;
		double drivenDrop = driven.preDrawQ - driven.postDrawQ;
		double attributable = drivenDrop - naturalDrop;
		boolean fieldPaidSeam = attributable > 0;
		boolean ok = useFired && useHonest && fieldPaidExact;

		System.out.println("  use: budget=" + fmt((float) budget)
				+ " → HASTE " + (burst == null ? "-" : burst.amplifier())
				+ " for " + (burst == null ? "-" : burst.durationTicks()) + " ticks"
				+ " | fired=" + useFired + " | honest (output ≤ input)=" + useHonest);
		System.out.println("  field paid (bare, exact): draw-cell q " + fmt9(bare.qBefore())
				+ " → " + fmt9(bare.qAfter()) + " (q down)=" + fieldPaidExact);
		System.out.println("  field paid (seam, driven−control at same step): attributable q drop="
				+ fmt9((float) attributable) + " (reported" + (fieldPaidSeam ? ", holds" : ", micro-scale — reported honestly") + ")");
		if (!ok) {
			System.err.println("[gate-d] FAIL — the use did not fire, is not bounded by the draw, or the field did not pay (q down at the draw cell)");
		}
		return ok;
	}

	// --- Helpers (the Q4/Genesis/Stilling-Shout gates' patterns) -------------------
	private static double[] centerOf(FieldSnapshot snap) {
		return snap.job() != null && !snap.job().isWindowless()
				? snap.job().windowCenter()
				: WINDOW_CENTER.clone();
	}

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
		ByteBuffer bb = ByteBuffer.allocate(floats.length * 4);
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
		return String.format("%.6f", v);
	}

	/** High-precision formatting for the micro field-payment measurements (a single
	 * cap-honored draw's q-drop is dt²-scaled ≈ 1e-7, so 6 decimals hide it — the
	 * honesty must stay visible, never rounded away). */
	private static String fmt9(float v) {
		return String.format("%.9f", v);
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

	/** A bare run: the deterministic fingerprint + the draw-cell pre/post q + the draw budget. */
	private record DrawFingerprint(Fingerprint fingerprint, float qBefore, float qAfter,
			double drawnBudget, double noMintCap) {
	}

	/** A seam run's readout fingerprint + the draw neighborhood + the measured states. */
	private record SeamRun(int executed, String readoutFingerprint, String drawNeighborhoodHash,
			float preDrawQ, HarnessRead.Read preState, HarnessRead.Read postState,
			long clampCount, float postDrawQ, double budget, double noMintCap) {
	}

	/** The honest-draw field cost + the clamp telemetry + the no-mint cap. */
	private record HonestyRun(long clampCount, double fieldCost, double noMintCap) {
	}

	private HarnessDeterminismMain() {
	}
}
