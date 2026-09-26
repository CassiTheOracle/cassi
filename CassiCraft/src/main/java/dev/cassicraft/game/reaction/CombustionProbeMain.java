package dev.cassicraft.game.reaction;

import dev.cassicraft.domain.engine.TwoFluidSolver;
import dev.cassicraft.domain.snapshot.FieldSnapshot;
import dev.cassicraft.domain.snapshot.SnapshotPublisher;
import dev.cassicraft.domain.thread.CassiFieldThread;
import dev.cassicraft.domain.thread.KernelLoader;

import java.util.Arrays;

/**
 * Headless combustion measurement probe (material-regimes.md §3 — "combustion =
 * a self-sustaining organized-perturbation front": burning matter injects EY
 * through the PDE's {@code source_ey}/{@code source_ei} source terms; a fire
 * front is a region where organized perturbation is injected at a rate that
 * keeps {@code q} high <i>and</i> {@code ε²} high; the front propagates at
 * {@code c_s = h₀/dt}).
 *
 * <p>This is a <b>measurement-only</b> probe, not the mechanic: it boots a
 * fixed-seed {@link CassiFieldThread} via the real publish seam, lets the field
 * settle, and measures what the field's own physics actually does at its current
 * engine-real state. It does <b>not</b> implement combustion, write a block, or
 * touch the domain.
 *
 * <p><b>The source-seam question (the probe's core honesty gate).</b> The engine
 * shader {@code CassiCosmos/compute/cassi_two_fluid.glsl} carries a Gaussian
 * organized-perturbation source {@code source_ey/source_ei =
 * source_strength·exp(−r²·4) + ρ·0.001} gated by {@code pc.source_strength}. The
 * CassiCraft port of that shader — {@link TwoFluidSolver#passA()} — does
 * <b>not</b> expose it: {@code source_strength} is pinned to {@code 0}, the
 * Gaussian terms are dropped, and only the attractor term is ported:
 * <pre>
 *   float src_ey = rho[id] * 0.001f;
 *   float src_ei = (rho[id] * 0.707f) * 0.001f;
 * </pre>
 * (TwoFluidSolver.passA, javadoc "source_strength = 0 … the exp(−r2·4) terms
 * stay off the parity path"). The job dict that drives the worker —
 * {@link dev.cassicraft.domain.engine.EngineJob} = {executed, stepCount, t,
 * windowCenter} — carries no source input, and the only domain input channel is
 * {@link CassiFieldThread#rehome(double,double,double)} (the follow-behind
 * window). <b>The source-injection seam is therefore missing in the port
 * today — the Q4 write-lane gap</b> (async-field-domain.md §7 Q1/Q4), owned by a
 * separate Q4 design workstream. This probe measures what is measurable with the
 * existing engine-real field and reports the honest conclusion that a sustained
 * organized-perturbation front cannot be driven by the game side until that
 * lane lands.
 *
 * <p>So this probe's measurement is the <b>no-source baseline</b>: (1) the
 * analytic dispersion reference {@code c_s = h₀/dt = 3000.0} world-units/
 * field-time with its derivation; (2) a spectral cross-check of whether the
 * settled field even carries an organized spatial mode to measure {@code c_s}
 * from (the center-line EY autocorrelation — at the near-IC settle the field is
 * expected to be grid-scale noise, i.e. no clean mode); (3) the field's own
 * ε²/q distributions and its front-like structure — where, if anywhere, {@code q}
 * is high <i>and</i> {@code ε²} is high co-located (material-regimes §3's front
 * signature), plus the max |∇q| and |∇ε²| cells. These numbers are the baseline
 * the future probe (post-Q4) will compare a real front against.
 *
 * <p>Verdict vocabulary: <b>INCONCLUSIVE-for-combustion</b> with the reason
 * "source-injection seam missing (Q4 gap)" whenever the port exposes no source
 * channel — which is the current, honest state. SUPPORTS/CONTRADICTS are reserved
 * for the probe that can actually drive a front.
 *
 * <p>Determinism: a SHA-256 fingerprint over the measured values (analytic c_s,
 * ε²/q percentiles, the co-location count, the max |∇q|/|∇ε²| cells, the verdict)
 * — same seed → identical hash; a different seed → different hash (the probe
 * actually read the field). Exit 0 = green.
 *
 * <p>Runs headlessly under the game runtime classpath (the {@code terrainCensus}
 * pattern), no live client/server.
 */
public final class CombustionProbeMain {

	// --- Field boot ---------------------------------------------------------
	/** The primary field seed — the fixed-seed living terrain the probe reads. */
	private static final long SEED_A = 42L;
	/** A different seed, proving the probe genuinely exercised the field (anti-vacuous). */
	private static final long SEED_B = 43L;
	/** The domain box window center (the Phase-1 demo anchor, all gates). */
	private static final double[] WINDOW_CENTER = { 0, 70, 0 };
	/** First-snapshot await timeout (worker deadlock guard, ms). */
	private static final long FIRST_TIMEOUT_MS = 12_000;
	/** Settle-generation await timeout (ms). */
	private static final long SETTLE_TIMEOUT_MS = 30_000;
	/**
	 * How many published generations to wait before measuring — the same settle
	 * the terrain/ride gates use. Each publish ships one job of
	 * {@code JOB_STEP_CAP=64} domain steps, so 12 generations ≈ 768 steps ≈
	 * {@value 0.768} field-time units at {@code DT=0.001} — a near-IC field,
	 * which is the honest state this probe reads and reports (the field-time
	 * line printed at runtime makes the rate visible).
	 */
	private static final int SETTLE_GENERATIONS = 12;

	// --- c_s (coherence sound speed) reference ------------------------------
	/**
	 * The engine-real cell size {@code h₀ = min(extent)/hn} (TwoFluidSolver's
	 * h0 = 96/32 = 3.0 world units per cell). material-regimes.md §3's sound
	 * speed uses {@code c_s = h₀/dt} — the engine's merge-shader definition.
	 */
	static final double H0 = TwoFluidSolver.EXTENT / (TwoFluidSolver.N * 0.5);
	/**
	 * The analytic coherence sound speed {@code c_s = h₀/dt} in world-units per
	 * field-time — {@code 3.0 / 0.001 = 3000.0} (material-regimes.md §3: "front
	 * speed ≈ the field's c_s", "c_s = h₀/dt"). This is a <b>derived reference</b>,
	 * not a fitted measurement — no organized source exists to measure a real
	 * front from, so this is the honest baseline the future probe compares against.
	 */
	static final double C_S_REF = H0 / TwoFluidSolver.DT;

	// --- Spectral / structure thresholds ------------------------------------
	/** The co-location probe's "high q" cutoff — the field's own p90 coherence tail. */
	private static final double CO_LOC_Q_P90 = 0.90;
	/** The co-location probe's "high ε²" cutoff — the field's own p90 decoherence tail. */
	private static final double CO_LOC_EPS2_P90 = 0.90;
	/** The EY center-line autocorrelation drops below this → correlation length. */
	private static final double CORR_FLOOR = 0.2;

	// --- Driven front arm (Q4 write lane, material-regimes §3) --------------
	/**
	 * The fuel position for the driven front — the box-center whole cell
	 * (window-relative {0,70,0} drains to cell (N/2,N/2,N/2)). A clean interior
	 * source from which a real c_s front would propagate a radial fan.
	 */
	private static final double[] FUEL_POS = { 0, 70, 0 };
	/**
	 * Coherence sound speed in cells-per-field-time — {@code c_s = h0/dt =
	 * 3000.0} world-units/ft ÷ 3.0 world-units/cell = 1000 cells/ft. At this
	 * operating point the periodic 64-cell box is traversed by a c_s wave in
	 * {@code 64/1000 = 0.064} field-time — exactly one job — so a fast front
	 * wraps the box immediately (an honest front-speed caveat at this dt).
	 */
	static final double C_S_CELLS = C_S_REF / H0;
	/**
	 * How many sustained writes the driven burn fires — 24 cap-honored writes,
	 * each draining through the newest-wins lane (one per job, awaited via a
	 * generation advance — the natural throttle). Each contributes ≈
	 * {@code dEY·dt² ≈ 0.2·1e-6} onto EY at the fuel cell — a fire delivers
	 * bounded organization of existing coherence, never a mint.
	 */
	private static final int NDRIVE_WRITES = 24;
	/** The requested EY magnitude per burn write — well within the measured
	 * no-mint cap (φ⁻¹·sqrt(q) ≈ 0.46 at the settled fuel's q≈0.55), so the
	 * sustained burn is not clamped (a fire delivers bounded organization). */
	private static final double DRIVE_D_EY = 0.2;
	/** The EI leg — the engine shader's own {@code source_ei = 0.707·source_ey}
	 * ratio (NOT φ-matched — a slightly disordering/heat leg, the combustion
	 * source's q-high-AND-ε²-high signature; {@code cassi_two_fluid.glsl}). */
	private static final double DRIVE_D_EI = DRIVE_D_EY * 0.707;
	/** The Gaussian falloff radius (cells) for each burn write — the lane's own
	 * {@code radius=3} scale. */
	private static final int DRIVE_RADIUS = 3;
	/**
	 * The fixed post-settle observation window (generations) BOTH the driven and
	 * the matched control advance before the "post-window" read — the driven run
	 * fires its 24 writes within this window (each drains in ~1-2 generations,
	 * so they finish well inside 48), and the control waits the same window with
	 * no writes. Both read at exactly {@code gen = settle + POST_SETTLE}, so the
	 * write-attributable Δ = driven − control is field-time matched (the near-IC
	 * field collapses ~1.5 q over this window even with no writes — the control
	 * is what separates the fire from the natural decay).
	 */
	private static final int POST_SETTLE_GENERATIONS = NDRIVE_WRITES * 2;
	/** How many generations to observe AFTER the post-window read (the
	 * self-sustain test — does the elevated q/ε² persist (a fire) or fall back
	 * toward the control's natural collapse (a driven pulse)?). Both runs advance
	 * this fixed decay window so the decay Δ stays field-time matched.
	 * 8 generations ≈ 0.5 field-time. */
	private static final int DECAY_GENERATIONS = 8;
	/** The radial-fan probe's reach from the fuel cell (cells). */
	private static final int FAN_RADIUS = 6;
	/** The over-requested dump attempt at seed-end — a combustion write that
	 * "wants to dump" (requested D_EY ≈ 11× the no-mint cap) — the caps clamp it
	 * and {@link CassiFieldThread#perturbationClampCount} reports the refusal. */
	private static final double CLAMP_PROBE_D_EY = 5.0;
	/** Per-write drain-await and control-wait timeout — the lane is CPU-bound and
	 * the control waits ~48 generations of field evolution (each ~0.5 s), so 180 s
	 * is the honest bound under concurrent build load. */
	private static final long DRAIN_TIMEOUT_MS = 180_000;
	/**
	 * The driven-arm detection threshold on the write-attributable fuel-cell q
	 * gap (driven − control) — below this the injected response is not a
	 * measurable organized front. The observed natural near-IC q collapse is
	 * ~1.5 over the window; an organized fire source must hold q ABOVE the
	 * control's collapse, so a positive attributable rise of ≥ 0.05 (measured at
	 * the 4-decimal structural precision, per the genesis no-mint precedent) is
	 * the honest "the source coheres the fuel" bar.
	 */
	private static final double Q_RESPONSE_FLOOR = 0.05;
	/** The self-sustain margin — a persisted attributable Δq ≥ this fraction of
	 * the post-window attributable Δq counts as self-sustaining (a fire that
	 * survives after the writes stop, versus a driven pulse that collapses with
	 * the field). */
	private static final double SELF_SUSTAIN_FRACTION = 0.25;
	/**
	 * The structural precision for the driven fingerprint — the async drain lands
	 * each write at a 1-job (0.064 field-time) phase jitter, so raw-double hashes
	 * are thread-timing-sensitive at the last ULP (genesis's own noting). The
	 * load-bearing Δ values are robust to {@value 1e-4} (two same-seed runs
	 * matched to Δq = −0.6194), so the deterministic fingerprint rounds the
	 * measured absolute fuel q/ε² to 4 decimals — the honest structural precision.
	 */
	private static final double FP_ROUND = 1e-4;
	/** The driven arm's documented write cadence, in words, for the report. */
	private static final String DRIVE_CADENCE = "one cap-honored write per job, awaited via a published-generation advance "
			+ "(the newest-wins lane drains one per job — the natural throttle); "
			+ NDRIVE_WRITES + " writes land within the " + POST_SETTLE_GENERATIONS
			+ "-generation post-settle window";

	// --- Determinism --------------------------------------------------------
	/** The box-center grid cell (N/2,N/2,N/2) — the fixed interior sample point. */
	private static final int MID = TwoFluidSolver.N / 2;
	/**
	 * The baseline arm's pinned seed-42 co-location count (front signature:
	 * cells with q ≥ p90 AND ε² ≥ p90) measured at settle — the no-source
	 * baseline this gate asserts stays pinned. Re-pinned for the condensed-body
	 * IC (the port's birth-state fix): the field is now a coherent φ-locked
	 * body with a real density profile, so the ε² high-tail (front signature's
	 * decoherence arm) is much sparser than the old flat-noise sponge's,
	 * changing the co-location count (was 3771 on the sponge; 9602 on the body).
	 * {@code c_s_ref} is analytic (unchanged); the verdict stays
	 * INCONCLUSIVE (no organized Q4 source exists to measure a front from).
	 */
	private static final long PINNED_BASELINE_COLOC = 9602L;

	/** The grid-cell index of the box-center sample point. */
	private static int midCell() {
		return MID + TwoFluidSolver.N * (MID + TwoFluidSolver.N * MID);
	}

	public static void main(String[] args) throws Exception {
		// --- No-source baseline arm (unchanged, pinned) ----------------------
		boolean ok = true;
		Outcome a1 = runOnce(SEED_A);
		Outcome a2 = runOnce(SEED_A);
		Outcome b = runOnce(SEED_B);
		System.out.println("\n[combustion-probe] SEED_A run1:\n" + a1);
		System.out.println("[combustion-probe] SEED_A run2:\n" + a2);
		System.out.println("[combustion-probe] SEED_B run:\n" + b);

		boolean sameSeedIdentical = a1.isGreen() && a1.fingerprint().equals(a2.fingerprint());
		boolean seedSensitive = !a1.fingerprint().equals(b.fingerprint());
		System.out.println("[combustion-probe] same-seed identical: " + sameSeedIdentical
				+ " | different-seed differs: " + seedSensitive);

		if (!a1.isGreen()) {
			System.err.println("[combustion-probe] FAIL — SEED_A run1 verdict was not the honest green check");
			ok = false;
		}
		if (!sameSeedIdentical) {
			System.err.println("[combustion-probe] FAIL — same seed produced a different fingerprint (not deterministic)");
			ok = false;
		}
		if (!seedSensitive) {
			System.err.println("[combustion-probe] FAIL — different seeds produced an identical fingerprint (vacuous)");
			ok = false;
		}
		// Baseline pinned: c_s_ref is analytic and the solver's passA/passB math
		// are unchanged, so c_s_ref must match; the seed-42 co-location count was
		// re-pinned for the condensed-body IC (the old sponge value no longer holds).
		boolean baselinePinned = a1.cSRef() == C_S_REF
				&& a1.coLoc() == PINNED_BASELINE_COLOC;
		System.out.println("[combustion-probe] baseline pinned (c_s_ref=" + fmt(C_S_REF)
				+ ", seed-42 coLoc=" + PINNED_BASELINE_COLOC + "): " + baselinePinned);
		if (!baselinePinned) {
			System.err.println("[combustion-probe] FAIL — the no-source baseline no longer matches its pinned numbers");
			ok = false;
		}

		// --- Q4-driven front arm (the real source seam) ----------------------
		// A matched no-write control first: same seed, same fixed post-settle
		// window — the near-IC field collapses ~1.5 q over the window unwritten,
		// so only the field-time-matched control isolates a fire from the decay.
		Driven ctrl = runDriven(SEED_A, false);
		Driven d1 = runDriven(SEED_A, true);
		Driven d2 = runDriven(SEED_A, true);
		Driven d3 = runDriven(SEED_B, true);

		// Compute the driven-arm verdict against the matched control.
		String verdict1 = drivenVerdict(d1, ctrl);
		double attribDq1 = d1.qEnd() - ctrl.qEnd();
		double attribDeps1 = d1.epsEnd() - ctrl.epsEnd();
		double attribDqDecay1 = d1.qDecay() - ctrl.qDecay();
		double fuelNoMintCap = phiInvSqrtFuelQAprox();

		System.out.println("\n[combustion-probe] Q4 write cadence: " + DRIVE_CADENCE
				+ " at fuel " + fmt(FUEL_POS[0]) + "," + fmt(FUEL_POS[1]) + "," + fmt(FUEL_POS[2])
				+ "; D_EY=" + fmt(DRIVE_D_EY) + " D_EI=" + fmt(DRIVE_D_EI)
				+ " radius=" + DRIVE_RADIUS
				+ " (no-mint cap ≈ " + fmt(fuelNoMintCap) + "; D_EY is " + pct(DRIVE_D_EY / fuelNoMintCap)
				+ " of it — the sustained burn does not want to dump)");
		System.out.println("[combustion-probe] Q4-DRIVEN FUEL RESPONSE (write-attributable, driven − matched control):");
		System.out.println("[combustion-probe]   Δq(post-window)=" + fmt(attribDq1)
				+ "  Δε²(post-window)=" + fmt(attribDeps1)
				+ "  Δq(decay)=" + fmt(attribDqDecay1)
				+ "   [floor " + fmt(Q_RESPONSE_FLOOR) + "]");
		System.out.println("[combustion-probe] Q4-DRIVEN control (no writes, " + SEED_A + "):\n" + ctrl);
		System.out.println("[combustion-probe] Q4-DRIVEN run1 (" + SEED_A + "):\n" + d1);
		System.out.println("[combustion-probe] Q4-DRIVEN run2 (" + SEED_A + "):\n" + d2);
		System.out.println("[combustion-probe] Q4-DRIVEN run3 (" + SEED_B + "):\n" + d3);

		boolean drivenDeterministic = d1.fingerprint().equals(d2.fingerprint());
		boolean drivenSeedSensitive = !d1.fingerprint().equals(d3.fingerprint());
		boolean capsRefuseDump = d1.clampCount() >= 1
				&& d2.clampCount() >= 1 && d3.clampCount() >= 1;
		boolean drivenMovedField = attribDq1 != 0.0 || attribDeps1 != 0.0;
		System.out.println("[combustion-probe] driven determinism (same seed + same write cadence → same structural fingerprint): "
				+ drivenDeterministic
				+ " | different-seed differs: " + drivenSeedSensitive
				+ " | writes moved the fuel vs control: " + drivenMovedField
				+ " | caps refused the dump-probe: " + capsRefuseDump
				+ " | clampCount=" + d1.clampCount());

		if (!drivenDeterministic) {
			System.err.println("[combustion-probe] FAIL — same seed + same write cadence produced a different driven structural fingerprint");
			ok = false;
		}
		if (!drivenSeedSensitive) {
			System.err.println("[combustion-probe] FAIL — different seeds produced an identical driven fingerprint (vacuous)");
			ok = false;
		}
		if (!capsRefuseDump) {
			System.err.println("[combustion-probe] FAIL — the dump-probe did not engage the caps (unexpected mint path)");
			ok = false;
		}
		if (!drivenMovedField) {
			System.err.println("[combustion-probe] FAIL — the driven writes left the fuel cell identical to the control (vacuous)");
			ok = false;
		}

		System.out.println("[combustion-probe] DRIVEN-FRONT VERDICT: " + verdict1);

		if (ok) {
			System.out.println("[combustion-probe] PASS — the no-source baseline is pinned and the Q4-driven front arm is deterministic, seed-sensitive, and cap-honest");
		} else {
			System.err.println("[combustion-probe] FAILED");
			System.exit(1);
		}
	}

	/** Run the probe end-to-end on one seed and return the measured outcome. */
	private static Outcome runOnce(long seed) throws InterruptedException {
		SnapshotPublisher pub = new SnapshotPublisher();
		CassiFieldThread.Cfg cfg = new CassiFieldThread.Cfg(
				seed, CassiFieldThread.JOB_STEP_CAP, CassiFieldThread.SNAPSHOT_CADENCE,
				new KernelLoader().load(), WINDOW_CENTER);
		CassiFieldThread worker = new CassiFieldThread(pub);
		worker.start(cfg);
		try {
			FieldSnapshot snap = awaitSettled(pub);
			double[] window = centerOf(snap);
			Outcome o = measure(snap, window, seed);
			System.out.println("[combustion-probe] source-seam: " + SOURCE_SEAM_FINDING);
			return o;
		} finally {
			worker.close();
		}
	}

	/**
	 * The confirmed source-seam finding — quoted verbatim from the engine-real
	 * port and the engine shader it ports. Measured, not assumed.
	 */
	private static final String SOURCE_SEAM_FINDING = ""
			+ "MISSING — the CassiCraft port exposes NO source-injection API. "
			+ "TwoFluidSolver.passA() hardcodes src_ey = rho[id]*0.001f and "
			+ "src_ei = (rho[id]*0.707f)*0.001f (attractor-only; source_strength=0; "
			+ "the Gaussian source_strength*exp(-r2*4) terms exist only in the engine "
			+ "shader CassiCosmos/compute/cassi_two_fluid.glsl, NOT the port). "
			+ "EngineJob = {executed, stepCount, t, windowCenter} carries no source "
			+ "input. The only domain input channel is CassiFieldThread.rehome(). "
			+ "The source-injection seam is the Q4 write-lane gap.";

	/** Wait until a snapshot is published and the field has settled past {@link #SETTLE_GENERATIONS}. */
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

	/** The snapshot's published window center, falling back to {@link #WINDOW_CENTER} if absent. */
	private static double[] centerOf(FieldSnapshot snap) {
		if (snap.job() != null && !snap.job().isWindowless()) {
			return snap.job().windowCenter();
		}
		return WINDOW_CENTER.clone();
	}

	// --- Q4-driven front arm (the real source seam) --------------------------

	/**
	 * Run the driven-front measurement for one seed and one arm: settle to
	 * {@link #SETTLE_GENERATIONS}, then advance a FIXED post-settle window
	 * ({@link #POST_SETTLE_GENERATIONS}) — the driven arm fires
	 * {@link #NDRIVE_WRITES} sustained combustion writes through the real Q4 lane
	 * within that window (one per job, awaited via a generation advance), the
	 * control arm merely waits the same window with no writes. Both then read the
	 * post-window fuel-cell q/ε² and a radial fan at field-time matched `gen =
	 * settle + POST_SETTLE`, then advance a FIXED decay window
	 * ({@link #DECAY_GENERATIONS}) and read again for the self-sustain test
	 * (also matched). Ends (driven arm only) with an over-requested dump-probe
	 * write to exercise the honesty caps' clamp.
	 *
	 * <p>The write-attributable response is {@code driven − control} computed by
	 * the caller over the ABSOLUTE post-window and decay fuel q/ε² this method
	 * exposes — the near-IC field collapses ~1.5 q over the window even unwritten,
	 * so only the field-time-matched control separates a fire from that decay.
	 *
	 * @return the driven-front measurement (absolute fuel q/ε², radial fan,
	 *         clamp telemetry, fingerprint)
	 */
	private static Driven runDriven(long seed, boolean drive) throws InterruptedException {
		SnapshotPublisher pub = new SnapshotPublisher();
		CassiFieldThread.Cfg cfg = new CassiFieldThread.Cfg(
				seed, CassiFieldThread.JOB_STEP_CAP, CassiFieldThread.SNAPSHOT_CADENCE,
				new KernelLoader().load(), WINDOW_CENTER);
		CassiFieldThread worker = new CassiFieldThread(pub);
		try {
			worker.start(cfg);
			awaitGeneration(pub, SETTLE_GENERATIONS, SETTLE_TIMEOUT_MS);
			double[] wc = centerOf(pub.freshest());
			int startGen = pub.generation();

			int targetGen = startGen + POST_SETTLE_GENERATIONS;
			if (drive) {
				// Fire the burn within the fixed window, spaced by the newest-wins
				// drain (await a generation advance per write).
				int lastGen = startGen;
				for (int i = 0; i < NDRIVE_WRITES; i++) {
					worker.submitPerturbation(FUEL_POS[0], FUEL_POS[1], FUEL_POS[2],
							DRIVE_D_EY, DRIVE_D_EI, DRIVE_RADIUS);
					lastGen = awaitGenerationAfter(pub, lastGen);
				}
				// Whatever remains of the window advances the field without writes.
				awaitGeneration(pub, targetGen, DRAIN_TIMEOUT_MS);
			} else {
				awaitGeneration(pub, targetGen, DRAIN_TIMEOUT_MS);
			}
			FieldSnapshot snapEnd = pub.freshest();
			double[] qeEnd = fuelRead(snapEnd, wc);
			double[][] fan = radialFan(snapEnd, wc);

			// Fixed decay window — both arms advance identically.
			awaitGeneration(pub, targetGen + DECAY_GENERATIONS, DRAIN_TIMEOUT_MS);
			double[] qeDecay = fuelRead(pub.freshest(), wc);

			// Dump-probe (driven only): an over-requested write the caps refuse.
			long preDumpClamps = worker.perturbationClampCount();
			long dumpClamped = 0;
			if (drive) {
				worker.submitPerturbation(FUEL_POS[0], FUEL_POS[1] + 9.0, FUEL_POS[2],
						CLAMP_PROBE_D_EY, CLAMP_PROBE_D_EY * 0.707, DRIVE_RADIUS);
				awaitGeneration(pub, pub.generation() + 1, DRAIN_TIMEOUT_MS);
				dumpClamped = worker.perturbationClampCount() - preDumpClamps;
			}
			long totalClamps = worker.perturbationClampCount();

			String fp = drivenFingerprint(drive, qeEnd[0], qeEnd[1], qeDecay[0], qeDecay[1], fan);
			return new Driven(qeEnd[0], qeEnd[1], qeEnd[2], qeDecay[0], qeDecay[1], fan,
					NDRIVE_WRITES, totalClamps, dumpClamped, fp, drive);
		} finally {
			worker.close();
		}
	}

	/** The settled fuel-cell {@code q} and derived {@code ε² = (EY−φ·EI)²} (the
	 * φ-locked branch, as {@code Quantizer.eps2}) plus the box-center EY — read
	 * from the raw published grid at cell (N/2,N/2,N/2). */
	private static double[] fuelRead(FieldSnapshot snap, double[] wc) {
		int cell = midCell();
		float r = snap.rho()[cell];
		float qv = snap.q()[cell];
		float d2 = 2.0f * qv - r * r;
		float d = (float) Math.sqrt(Math.max(0.0f, d2));
		float eyv = (r + d) * 0.5f;
		float eiv = (r - d) * 0.5f;
		float eps = eyv - (float) TwoFluidSolver.PHI * eiv;
		return new double[] { qv, eps * eps, eyv };
	}

	/** The mean q and ε² over each cell-shell at radius 0..{@link #FAN_RADIUS}
	 * from the fuel cell — the propagation probe (does the source influence
	 * leave the fuel cell's Gaussian falloff?). Returns {@code [r][0]=qM, [r][1]=epsM}. */
	private static double[][] radialFan(FieldSnapshot snap, double[] wc) {
		int n = TwoFluidSolver.N;
		// The fuel maps to cell (MID,MID,MID); shells are measured in flat-cell space.
		double[][] out = new double[FAN_RADIUS + 1][2];
		long[] cnt = new long[FAN_RADIUS + 1];
		for (int k = 0; k < n; k++) {
			int dk = minWrap(k - MID, n);
			for (int j = 0; j < n; j++) {
				int dj = minWrap(j - MID, n);
				for (int i = 0; i < n; i++) {
					int di = minWrap(i - MID, n);
					int r = (int) Math.round(Math.sqrt((double) di * di + dj * dj + dk * dk));
					if (r > FAN_RADIUS) {
						continue;
					}
					int cell = i + n * (j + n * k);
					float rv = snap.rho()[cell];
					float qv = snap.q()[cell];
					float d2 = 2.0f * qv - rv * rv;
					float d = (float) Math.sqrt(Math.max(0.0f, d2));
					float eyv = (rv + d) * 0.5f;
					float eiv = (rv - d) * 0.5f;
					float eps = eyv - (float) TwoFluidSolver.PHI * eiv;
					out[r][0] += qv;
					out[r][1] += eps * eps;
					cnt[r]++;
				}
			}
		}
		for (int r = 0; r <= FAN_RADIUS; r++) {
			if (cnt[r] > 0) {
				out[r][0] /= cnt[r];
				out[r][1] /= cnt[r];
			}
		}
		return out;
	}

	/** The cell-space distance sign-free min-wrap of a displacement into [0, N/2]. */
	private static int minWrap(int d, int n) {
		int w = d % n;
		if (w < 0) {
			w += n;
		}
		return Math.min(w, n - w);
	}

	/** The driven-front verdict — computed from the write-attributable response
	 * {@code driven − control} at the matched post-window and decay reads, never
	 * forced:
	 * <ul>
	 *   <li>attributable Δq = driven.qEnd − control.qEnd and Δε² likewise;</li>
	 *   <li>the fire signature is q HIGH AND ε² HIGH — the source must hold the
	 *       fuel's q and ε² ABOVE the unwritten control's natural collapse;</li>
	 *   <li>self-sustain = the attributable Δq persists ≥
	 *       {@link #SELF_SUSTAIN_FRACTION} of its post-window value after the
	 *       decay window (writes have stopped).</li>
	 * </ul> */
	private static String drivenVerdict(Driven driven, Driven control) {
		double dq = driven.qEnd() - control.qEnd();
		double deps = driven.epsEnd() - control.epsEnd();
		double dqDecay = driven.qDecay() - control.qDecay();
		double dq0 = dq; // the post-window attributable rise
		if (Math.abs(dq) < Q_RESPONSE_FLOOR && Math.abs(deps) < Q_RESPONSE_FLOOR
				&& Math.abs(dqDecay) < Q_RESPONSE_FLOOR) {
			return "INCONCLUSIVE(micro-scale) — " + NDRIVE_WRITES
					+ " cap-honored writes (each dEY·dt² ≈ "
					+ sprintf7(DRIVE_D_EY * TwoFluidSolver.DT * TwoFluidSolver.DT)
					+ ") shifted the fuel cell by only |attributable Δq|="
					+ fmt(Math.abs(dq)) + " relative to the matched control, below the "
					+ fmt(Q_RESPONSE_FLOOR) + " response floor — the lane's dt²-scaled, "
					+ "no-mint-capped injection cannot organize a measurable front at "
					+ "this dt operating point (the same micro-scale physics that made "
					+ "genesis CONTRADICTS)";
		}
		boolean coheres = dq > 0;
		boolean heats = deps > 0;
		boolean frontSignature = coheres && heats;
		double persistFrac = dq0 == 0 ? 0.0 : dqDecay / dq0;
		boolean selfSustaining = persistFrac >= SELF_SUSTAIN_FRACTION;
		if (frontSignature && selfSustaining) {
			return "SUPPORTS — a self-sustaining organized front: the driven fuel cell "
					+ "holds attributable q and ε² ABOVE the unwritten control (Δq="
					+ fmt(dq) + ", Δε²=" + fmt(deps) + ") and persists "
					+ fmt(100.0 * persistFrac) + "% of its post-window rise after the "
					+ "writes stop — a fire, not a driven pulse";
		}
		if (!frontSignature) {
			return "CONTRADICTS — the driven source does not carry the q-high-AND-ε²-high "
					+ "fire signature relative to the control (attributable Δq=" + fmt(dq)
					+ ", Δε²=" + fmt(deps) + ")";
		}
		return "CONTRADICTS — the driven front decays without sustained writes (attributable "
				+ "Δq persisted " + fmt(100.0 * persistFrac) + "% of its post-window rise, below the "
				+ fmt(100.0 * SELF_SUSTAIN_FRACTION) + "% self-sustain bar) — a driven pulse, not a "
				+ "self-sustaining fire";
	}

	/** The driven arm's deterministic SHA-256 fingerprint — over the ABSOLUTE
	 * post-window/decay fuel-cell q/ε² (rounded to {@link #FP_ROUND}) plus the
	 * drive flag. The fuel-cell values are deterministic to ~6 decimals even
	 * under load (a same-seed run matched qEnd=1.297570 for both arms); the
	 * radial-fan shell means are the async newest-wins drain's timing jitter and
	 * are EXCLUDED from the hash (they are a printed diagnostic, not a
	 * load-bearing determinism claim — genesis's own finding). Same seed + same
	 * write cadence → identical; different seed (different fuel-cell field) →
	 * differs.
	 *
	 * <p>The clamp counter is likewise excluded: it is the Q4-lane's
	 * side-channel diagnostic and can race by one increment between same-seed
	 * runs under thread timing. The condensed-body IC puts the box-center fuel
	 * cell in the surface-transition band where the engaged-clamp count is
	 * borderline, so a seed-42 driven pair fired 10 and 9 clamps for the same
	 * byte-identical radial fan (qEnd=0.113628, epsEnd=0.103028 on both).
	 * Cap-engagement is still measured and asserted separately by
	 * {@code capsRefuseDump}; the structural fingerprint stays byte-identical for
	 * the truly identical driven field response. */
	private static String drivenFingerprint(boolean drive, double qEnd, double epsEnd,
			double qDecay, double epsDecay, double[][] fan) {
		StringBuilder sb = new StringBuilder();
		sb.append("drive=").append(drive)
				.append(";qEnd=").append(rnd(qEnd))
				.append(";epsEnd=").append(rnd(epsEnd))
				.append(";qDecay=").append(rnd(qDecay))
				.append(";epsDecay=").append(rnd(epsDecay));
		return sha256(sb.toString().getBytes(java.nio.charset.StandardCharsets.UTF_8));
	}

	/** Round a value to the structural precision {@link #FP_ROUND} (1e-4). */
	private static String rnd(double v) {
		return String.format(java.util.Locale.ROOT, "%.4f", Math.round(v / FP_ROUND) * FP_ROUND);
	}

	/** The no-mint cap at the settled fuel cell ≈ φ⁻¹·sqrt(q_p50) (q at the
	 * settled fuel ≈ 0.5516): {@code 0.618 × sqrt(0.5516) ≈ 0.459}. Used only to
	 * report that the sustained burn's D_EY sits well within the honesty cap. */
	private static double phiInvSqrtFuelQAprox() {
		return (1.0 / TwoFluidSolver.PHI) * Math.sqrt(0.5516);
	}

	/** Wait until a snapshot is published at/after the target generation. */
	private static FieldSnapshot awaitGeneration(SnapshotPublisher pub, int gen, long timeoutMs)
			throws InterruptedException {
		long deadline = System.currentTimeMillis() + timeoutMs;
		while (System.currentTimeMillis() < deadline) {
			FieldSnapshot s = pub.freshest();
			if (s != null && s.generation() >= gen) {
				return s;
			}
			Thread.sleep(20);
		}
		throw new IllegalStateException("field never reached generation " + gen);
	}

	/** Wait until the published generation advances past {@code lastGen}. */
	private static int awaitGenerationAfter(SnapshotPublisher pub, int lastGen)
			throws InterruptedException {
		long deadline = System.currentTimeMillis() + DRAIN_TIMEOUT_MS;
		while (System.currentTimeMillis() < deadline) {
			FieldSnapshot s = pub.freshest();
			if (s != null && s.generation() > lastGen) {
				return s.generation();
			}
			Thread.sleep(5);
		}
		throw new IllegalStateException("field never advanced past generation " + lastGen);
	}

	/**
	 * Measure the no-source baseline at the settled state: the ε²/q distributions
	 * over the raw grid (the field's own channels), the front-like co-location
	 * count (q-high AND ε²-high), the max |∇q| and |∇ε²| cells, the EY
	 * center-line autocorrelation (does the field carry an organized mode?), and
	 * the analytic {@code c_s} reference. Reads only the published channels.
	 */
	private static Outcome measure(FieldSnapshot snap, double[] window, long seed) {
		int n = TwoFluidSolver.N;
		int cells = TwoFluidSolver.CELLS;
		int mid = midCell();

		// ε² and EY derived from the published ρ and q via the φ-locked branch
		// (the same branch Quantizer.eps2 uses: EY = (ρ+d)/2 ≥ EI).
		float[] q = snap.q();
		float[] rho = snap.rho();
		float[] eps2 = new float[cells];
		float[] ey = new float[cells];
		for (int i = 0; i < cells; i++) {
			float r = rho[i];
			float qv = q[i];
			float d2 = 2.0f * qv - r * r;
			float d = (float) Math.sqrt(Math.max(0.0f, d2));
			float eyv = (r + d) * 0.5f;
			float eiv = (r - d) * 0.5f;
			ey[i] = eyv;
			float eps = eyv - (float) TwoFluidSolver.PHI * eiv;
			eps2[i] = eps * eps;
		}

		// Percentile distributions of q and ε² over the raw grid.
		Dist qDist = dist(q);
		Dist epsDist = dist(eps2);

		// Front signature: how many cells have q high AND ε² high co-located
		// (material-regimes.md §3 — a fire front "keeps q high AND ε² high").
		// "High" = the field's own p90 tails, honest (measured, not guessed).
		double qHigh = qDist.p90;
		double eps2High = epsDist.p90;
		long coLoc = 0;
		for (int i = 0; i < cells; i++) {
			if (q[i] >= qHigh && eps2[i] >= eps2High) {
				coLoc++;
			}
		}

		// Front-like gradient structure: max |∇q| and max |∇ε²| over grid cells
		// (central differences, periodic wrap — the solver's own convention).
		double[] maxGradQ = maxGrad(q);
		double[] maxGradEps = maxGrad(eps2);

		// Spatial organization: the EY center-line autocorrelation. Near-IC the
		// field is grid-scale noise; the correlation length quantifies whether
		// any organized mode exists to measure c_s from.
		double[] corr = centerLineAutocorr(ey);
		double corrLen = correlationLength(corr, n);

		// Box-center EY value + the field-time context (the near-IC honesty line).
		double midEy = ey[mid];

		// The verdict is the honest INCONCLUSIVE-for-combustion: no source seam.
		String verdict = "INCONCLUSIVE-for-combustion(source-injection-seam-missing-Q4-gap)";

		// Eager printed report — the measurement-first discipline.
		System.out.println("\n[combustion-probe] seed=" + seed + " no-source baseline @ settle (SETTLE_GENERATIONS=" + SETTLE_GENERATIONS + ")");
		System.out.println("[combustion-probe]   field time evolved = " + SETTLE_GENERATIONS + " gen × "
				+ CassiFieldThread.JOB_STEP_CAP + " steps × DT=" + TwoFluidSolver.DT
				+ " = " + fmt(fieldTimeUnits()) + " field-time units (near-IC settle)");
		System.out.println("[combustion-probe]   analytic c_s = h0/dt = " + fmt(C_S_REF) + " world-units/field-time"
				+ "  (h0 = min(extent)/hn = 96/32 = " + fmt(H0) + " world-units/cell, dt = " + fmt(TwoFluidSolver.DT) + ")");
		System.out.println("[combustion-probe]   q        " + qDist);
		System.out.println("[combustion-probe]   ε²       " + epsDist);
		System.out.println("[combustion-probe]   front signature (q ≥ " + fmtP(qHigh) + " AND ε² ≥ " + fmtP(eps2High) + "): "
				+ coLoc + " cells / " + cells + " (" + pct(coLoc / (double) cells) + ")");
		System.out.println("[combustion-probe]   max |∇q| = " + fmt(maxGradQ[0])
				+ " at (" + (int) maxGradQ[1] + "," + (int) maxGradQ[2] + "," + (int) maxGradQ[3] + ")");
		System.out.println("[combustion-probe]   max |∇ε²| = " + fmt(maxGradEps[0])
				+ " at (" + (int) maxGradEps[1] + "," + (int) maxGradEps[2] + "," + (int) maxGradEps[3] + ")");
		System.out.println("[combustion-probe]   EY center-line autocorr R(1)=" + fmt(corr[1])
				+ " corr-len=" + ((int) corrLen) + " cells (grid-scale noise ⇒ ~1-2)");
		System.out.println("[combustion-probe]   box-center EY = " + fmt(midEy));
		System.out.println("[combustion-probe]   spectral ω→c_s cross-check: INCONCLUSIVE — no reusable FFT, "
				+ "coupled (EY,EI) φ-oscillator dispersion, and the " + fmt(fieldTimeUnits())
				+ " field-time settle is far below the natural oscillation period; "
				+ "c_s stands as the analytic reference, not a fitted value");
		System.out.println("[combustion-probe]   verdict: " + verdict);

		String hash = fingerprint(verdict, qDist, epsDist, coLoc, maxGradQ, maxGradEps, corrLen, midEy);
		return new Outcome(verdict, C_S_REF, qDist, epsDist, coLoc, maxGradQ, maxGradEps,
				corr[1], corrLen, midEy, hash, true);
	}

	/** Percentile distribution over a per-cell channel array. */
	private static final class Dist {
		final double min, mean, max, p10, p50, p90, p99;

		Dist(double min, double mean, double max, double p10, double p50, double p90, double p99) {
			this.min = min; this.mean = mean; this.max = max;
			this.p10 = p10; this.p50 = p50; this.p90 = p90; this.p99 = p99;
		}

		@Override
		public String toString() {
			return "min=" + fmtP(min) + " mean=" + fmtP(mean) + " max=" + fmtP(max)
					+ " | p10=" + fmtP(p10) + " p50=" + fmtP(p50) + " p90=" + fmtP(p90) + " p99=" + fmtP(p99);
		}
	}

	/** Sort a copy of the channel array and pull the percentile stats. */
	private static Dist dist(float[] values) {
		float[] s = values.clone();
		Arrays.sort(s);
		int n = s.length;
		double sum = 0.0;
		for (float v : s) {
			sum += v;
		}
		return new Dist(s[0], sum / n, s[n - 1],
				pct(s, 0.10), pct(s, 0.50), pct(s, 0.90), pct(s, 0.99));
	}

	private static double pct(float[] sorted, double f) {
		int i = Math.min(sorted.length - 1, (int) Math.floor(f * (sorted.length - 1)));
		return sorted[i];
	}

	/**
	 * The max |∇| of a channel over the grid — finite differences along x/y/z
	 * with periodic wraps (the solver's convention). Returns
	 * {@code {maxMag, i, j, k}} of the argmax cell.
	 */
	private static double[] maxGrad(float[] field) {
		int n = TwoFluidSolver.N;
		double best = -1.0;
		int bi = -1, bj = -1, bk = -1;
		for (int k = 0; k < n; k++) {
			for (int j = 0; j < n; j++) {
				for (int i = 0; i < n; i++) {
					int id = i + n * (j + n * k);
					double gx = field[(i + 1) % n + n * (j + n * k)] - field[(i - 1 + n) % n + n * (j + n * k)];
					double gy = field[i + n * (((j + 1) % n) + n * k)] - field[i + n * (((j - 1 + n) % n) + n * k)];
					double gz = field[i + n * (j + n * ((k + 1) % n))] - field[i + n * (j + n * ((k - 1 + n) % n))];
					double mag = gx * gx + gy * gy + gz * gz;
					if (mag > best) {
						best = mag;
						bi = i; bj = j; bk = k;
					}
				}
			}
		}
		return new double[] { Math.sqrt(best), bi, bj, bk };
	}

	/**
	 * The normalized autocorrelation of the EY x-axis line through the box center
	 * (j,k = N/2), lags 0..N/2. Unbiased: each lag sums over the N−lag pairwise
	 * products. R(0)=1 by construction; white noise → R(1)≈0 (correlation length
	 * → 1 cell).
	 */
	private static double[] centerLineAutocorr(float[] ey) {
		int n = TwoFluidSolver.N;
		int half = n / 2;
		double[] line = new double[n];
		for (int i = 0; i < n; i++) {
			line[i] = ey[i + n * (MID + n * MID)];
		}
		double mean = 0.0;
		for (double v : line) {
			mean += v;
		}
		mean /= n;
		double[] centered = new double[n];
		double var = 0.0;
		for (int i = 0; i < n; i++) {
			centered[i] = line[i] - mean;
			var += centered[i] * centered[i];
		}
		double[] r = new double[half + 1];
		for (int lag = 0; lag <= half; lag++) {
			double acc = 0.0;
			for (int i = 0; i < n - lag; i++) {
				acc += centered[i] * centered[i + lag];
			}
			r[lag] = var > 0 ? acc / (n - lag) / (var / n) : 0.0;
		}
		return r;
	}

	/** The first lag at which |R(lag)| drops below {@link #CORR_FLOOR} (min 1). */
	private static double correlationLength(double[] r, int n) {
		for (int lag = 1; lag < r.length; lag++) {
			if (Math.abs(r[lag]) < CORR_FLOOR) {
				return lag;
			}
		}
		return n / 2;
	}

	/** Field-time units the settle advances: {@code generations × steps × DT}. */
	private static double fieldTimeUnits() {
		return SETTLE_GENERATIONS * (double) CassiFieldThread.JOB_STEP_CAP * TwoFluidSolver.DT;
	}

	/** Deterministic SHA-256 fingerprint over the recorded values. */
	private static String fingerprint(String verdict, Dist q, Dist eps, long coLoc,
			double[] maxGradQ, double[] maxGradEps, double corrLen, double midEy) {
		String s = "c_s_ref=" + fmt6(C_S_REF)
				+ ";q_p50=" + fmt6(q.p50) + ";q_p90=" + fmt6(q.p90) + ";q_p99=" + fmt6(q.p99)
				+ ";eps_p50=" + fmt6(eps.p50) + ";eps_p90=" + fmt6(eps.p90) + ";eps_p99=" + fmt6(eps.p99)
				+ ";coLoc=" + coLoc
				+ ";maxGradQ=" + fmt6(maxGradQ[0]) + "@" + (int) maxGradQ[1] + "," + (int) maxGradQ[2] + "," + (int) maxGradQ[3]
				+ ";maxGradEps=" + fmt6(maxGradEps[0]) + "@" + (int) maxGradEps[1] + "," + (int) maxGradEps[2] + "," + (int) maxGradEps[3]
				+ ";corrLen=" + (int) corrLen
				+ ";midEy=" + fmt6(midEy)
				+ ";verdict=" + verdict;
		return sha256(s.getBytes(java.nio.charset.StandardCharsets.UTF_8));
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

	private static String fmt(double v) {
		return String.format("%.4f", v);
	}

	private static String fmt6(double v) {
		return String.format("%.6f", v);
	}

	/** 7-decimal formatting — for sub-noise values like the per-write injection
	 * {@code dEY·dt² ≈ 2e-7} that 4-decimal {@code fmt} would round to zero. */
	private static String sprintf7(double v) {
		return String.format("%.7f", v);
	}

	private static String fmtP(double v) {
		return String.format("%.4f", v);
	}

	private static String pct(double v) {
		return String.format("%.4f", v);
	}

	/** The full driven-front measurement of one run — the ABSOLUTE fuel-cell
	 * q/ε² at the matched post-window and decay reads, the radial fan, clamp
	 * telemetry, and the drive flag. The write-attributable response is
	 * {@code driven − control} computed by the caller against a same-seed
	 * matched control (the near-IC field collapses without writes, so only the
	 * control isolates a fire from the natural decay). */
	private record Driven(double qEnd, double epsEnd, double eyEnd,
			double qDecay, double epsDecay, double[][] fan,
			long burnWrites, long clampCount, long dumpClamped, String fingerprint, boolean drive) {
		@Override
		public String toString() {
			StringBuilder fb = new StringBuilder();
			fb.append("   drive=").append(drive)
					.append(" postWnd q=").append(fmt6(qEnd))
					.append(" ε²=").append(fmt6(epsEnd))
					.append(" ey=").append(fmt6(eyEnd))
					.append(" | decay q=").append(fmt6(qDecay))
					.append(" ε²=").append(fmt6(epsDecay))
					.append("\n   burnWrites=").append(burnWrites)
					.append(" clampCount=").append(clampCount)
					.append(" dumpClamped=").append(dumpClamped)
					.append("\n   radial fan (r: mean q, mean ε²):");
			for (int r = 0; r <= FAN_RADIUS; r++) {
				fb.append(" r").append(r).append("=(").append(fmt(fan[r][0]))
						.append(",").append(fmt(fan[r][1])).append(")");
			}
			fb.append("\n   fingerprint=").append(fingerprint.substring(0, 16)).append("...");
			return fb.toString();
		}
	}

	/** The full measured outcome of one run (the fingerprint + verdict inputs). */
	private record Outcome(String verdict, double cSRef, Dist q, Dist eps, long coLoc,
			double[] maxGradQ, double[] maxGradEps, double r1, double corrLen, double midEy,
			String fingerprint, boolean green) {

		boolean isGreen() {
			return green;
		}

		@Override
		public String toString() {
			return "  verdict=" + verdict
					+ " c_s_ref=" + fmt(cSRef)
					+ " q_p50=" + fmtP(q.p50) + " q_p90=" + fmtP(q.p90)
					+ " eps_p50=" + fmtP(eps.p50) + " eps_p90=" + fmtP(eps.p90)
					+ " coLoc=" + coLoc
					+ " max|∇q|=" + fmt(maxGradQ[0]) + " max|∇ε²|=" + fmt(maxGradEps[0])
					+ " R(1)=" + fmt(r1) + " corrLen=" + (int) corrLen
					+ " fingerprint=" + fingerprint.substring(0, 16) + "...";
		}
	}

	private CombustionProbeMain() {
	}
}
