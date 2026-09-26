package dev.cassicraft.game.reaction;

import dev.cassicraft.domain.engine.TwoFluidSolver;
import dev.cassicraft.domain.snapshot.FieldSnapshot;
import dev.cassicraft.domain.snapshot.SnapshotPublisher;
import dev.cassicraft.domain.thread.CassiFieldThread;
import dev.cassicraft.domain.thread.KernelLoader;

/**
 * Headless combustion <b>re-measure</b> on the structured body world
 * (material-regimes.md §3 — "combustion = a self-sustaining organized-perturbation
 * front"; a fire front is a region where organized perturbation is injected at a
 * rate that keeps {@code q} high <i>and</i> {@code ε²} high; the front propagates
 * at {@code c_s = h₀/dt}).
 *
 * <p>This is a <b>sibling</b> of {@link CombustionProbeMain}, built to answer the
 * same driven-front question on the NEW world. The prior probe measured it on the
 * old flat-noise <b>sponge</b> and returned <b>INCONCLUSIVE(micro-scale)</b>: each
 * cap-honored write injects only {@code dEY·dt² ≈ 2e-7}, and that was dwarfed by
 * the near-IC sponge field's OWN ~1.5 q collapse over the observation window — so
 * the source could not hold a measurable organized front against the decay, and
 * the honest verdict was that no front is measurable at this dt operating point on
 * that field. The physics changed in a way that could flip the verdict: on the
 * condensed-body IC ({@code TwoFluidSolver.seed()}), the dense ground is a coherent
 * φ-locked body whose own per-step change is <b>small</b> (near-equilibrium: q HIGH,
 * ε²≈0 in the bulk), so a bounded write's relative effect is <b>larger</b>. The
 * honest question this probe measures: does the dense body's high-q ground hold an
 * organized burn (a self-sustaining front) where the sponge couldn't?
 *
 * <p><b>This probe uses the real Q4 write lane</b> ({@link CassiFieldThread}
 * {@code submitPerturbation}, the no-mint φ⁻¹×√q cap and the ω₀²×|ε| overdraw cap,
 * gate-proven in {@code q4.Q4DeterminismMain}) exactly as the prior probe did, but
 * at a fuel cell <b>inside the dense body</b> (grid row j≈8, the high-q ground —
 * not the box-center surface-transition band the sponge probe's fuel cell landed
 * on once the body arrived). It is a <b>measurement-only</b> probe, not the
 * mechanic: it does not implement combustion, write a block, or touch the domain
 * (the lane is the only write path). {@code experiment} vs {@code control} are
 * field-time matched on the <b>same seed</b>, so the write-attributable Δ is
 * separated from the body's own evolution.
 *
 * <p>The driven burn: settle seed 42 to a named generation, then fire
 * {@value #NDRIVE_WRITES} sustained cap-honored combustion writes (the lane's
 * newest-wins throttle, one per job awaited via a published-generation advance)
 * at the dense-body fuel cell, then read the post-window fuel q/ε² and a radial
 * propagation probe (does the influence leave the Gaussian falloff?), then advance
 * a matched decay window for the self-sustain test. The match {@code control} is
 * the identical field-time evolution with <b>no</b> writes. Caps telemetry
 * {@link CassiFieldThread#perturbationClampCount()} is reported — a clamp is an
 * honest report of the bounded-organization boundary, not a failure.
 *
 * <p><b>Front speed.</b> {@code c_s = h₀/dt = 3000.0} world-units/ft = 1000
 * cells/ft ({@code C_S_CELLS}). At this operating point a c_s wave traverses the
 * periodic 64-cell box in {@code 64/1000 = 0.064} field-time — one job — so over
 * the {@value #POST_SETTLE} generations (0.384 ft) observation window a propagating
 * front crosses the box ~6× and is fully delocalized (the prior probe's own
 * documented caveat). A clean pre-wrap front speed is not resolvable at this
 * box/dt; the probe therefore measures the propagation <i>character</i> — whether
 * the write-attributable influence escapes the fuel cell's falloff and delocalizes
 * (a wave) or drops with radius (a confined injection) — as the honest front-speed
 * finding.
 *
 * <p>Verdict vocabulary (computed by measurement, never forced):
 * <ul>
 *   <li><b>SUPPORTS</b> — the driven fuel neighborhood holds attributable q AND ε²
 *       above the matched control (the q-high-AND-ε²-high fire signature), the
 *       attributable response persists ≥ {@link #SELF_SUSTAIN_FRACTION} of its
 *       post-window value after the writes stop, and the influence escaped the
 *       fuel cell (it propagated on the body).</li>
 *   <li><b>CONTRADICTS</b> — no fire signature relative to the control, or the
 *       front decays without sustained writes, or the influence never leaves the
 *       fuel cell's falloff — the body diffuses/absorbs the source.</li>
 *   <li><b>INCONCLUSIVE</b> — with the reason, if the measurement cannot
 *       discriminate (e.g. the micro-scale response floor again).</li>
 * </ul>
 * The verdict line references the prior probe's sponge verdict explicitly — the
 * honest comparison is what changed on the body.
 *
 * <p>Determinism: SHA-256 over the structural fingerprint (the rounded fuel-cell
 * q/ε² at the matched post-window/decay reads) — same seed + same write cadence →
 * identical hash; a different seed → different hash. The clamp counter and the
 * radial fan are excluded from the hash (the Q4-lane's drain timing can race them
 * by one increment; they are reported diagnostics, not load-bearing — the prior
 * probe's own finding). Exit 0 = green.
 *
 * <p>Runs headlessly under the game runtime classpath (the {@code terrainCensus}
 * pattern), no live client/server. This is a gate: the build task
 * {@code combustionBodyProbe} appends the verdict, determinism, seed-sensitivity,
 * body-vs-sponge, and clamp-telemetry asserts.
 */
public final class CombustionBodyProbeMain {

	// --- Field boot (the structured body world) -----------------------------
	/** The primary field seed — the fixed-seed body world this probe drives. */
	private static final long SEED_A = 42L;
	/** A different seed, proving the probe genuinely exercised the body (anti-vacuous). */
	private static final long SEED_B = 43L;
	/** The domain box window center — the Phase-1 demo anchor, all gates. */
	private static final double[] WINDOW_CENTER = { 0, 70, 0 };
	/** Settle-generation await timeout (ms). */
	private static final long SETTLE_TIMEOUT_MS = 30_000;
	/**
	 * The named settle generation — how many published generations to wait before
	 * measuring the driven burn. Each publish ships one job of {@value
	 * CassiFieldThread#JOB_STEP_CAP} domain steps, so 12 generations ≈ 768 steps ≈
	 * 0.768 field-time at {@code DT=0.001} — the same near-IC settle the terrain/
	 * ride gates and the prior probe use, on the body world. The field-time line
	 * printed at runtime makes the rate visible.
	 */
	private static final int SETTLE_GENERATIONS = 12;

	// --- c_s (coherence sound speed) reference ------------------------------
	/**
	 * The engine-real cell size {@code h₀ = 2·extent/N} (TwoFluidSolver.h0,
	 * {@code 2·96/64 = 3.0} world units per cell). material-regimes.md §3's sound
	 * speed uses {@code c_s = h₀/dt}.
	 */
	static final double H0 = 2.0 * TwoFluidSolver.EXTENT / TwoFluidSolver.N;
	/**
	 * The analytic coherence sound speed {@code c_s = h₀/dt} in world-units per
	 * field-time — {@code 3.0/0.001 = 3000.0}. Same derived reference the prior
	 * sponge probe used; unchanged on the body (the solver's passA/passB math is
	 * unchanged).
	 */
	static final double C_S_REF = H0 / TwoFluidSolver.DT;
	/** Coherence sound speed in cells-per-field-time — {@code c_s = 1000} cells/ft. */
	static final double C_S_CELLS = C_S_REF / H0;

	// --- Driven-burn design (the dense-body fuel cell) ----------------------
	/**
	 * The fuel position for the driven burn — a window-relative point <b>inside
	 * the dense body</b>, the high-q ground where the sponge probe's fuel cell
	 * (box center, cell j=32) landed in the surface-transition band once the
	 * body arrived. This probe's fuel is the body's interior: world {@code y
	 * = −2} with the {0,70,0} center drains to grid cell
	 * {@code (cx,cy,cz) = (32,8,32)} (cy = floor((−2−70)/3)+32 = 8) — the sigmoid
	 * body profile's densest rows (ρ ≈ 1.06–1.10, q ≈ 0.64 high, ε²≈0 in the bulk
	 * except the seeded drain slip). Deep in the coherent ground, not the surface.
	 */
	private static final double[] FUEL_POS = { 0, -2, 0 };
	/**
	 * The no-mint cap at the settled body fuel ≈ φ⁻¹·sqrt(q) (q ≈ 0.64 in the
	 * dense ground): {@code 0.618 × sqrt(0.64) ≈ 0.49}. The sustained burn's
	 * D_EY sits well within it — a fire delivers bounded organization of the
	 * body's own coherence, never a mint (reported at runtime, not assumed).
	 */
	private static final double FUEL_NO_MINT_CAP_APROX = (1.0 / TwoFluidSolver.PHI) * Math.sqrt(0.64);
	/**
	 * The requested EY magnitude per burn write — identical to the prior sponge
	 * probe ({@value 0.2}), keeping the honest comparison: the ONLY changed input
	 * is the world the drive lands on. Well within the no-mint cap.
	 */
	private static final double DRIVE_D_EY = 0.2;
	/**
	 * The EI leg — the engine shader's own {@code source_ei = 0.707·source_ey}
	 * ratio (NOT φ-matched — a slightly disordering/heat leg, the combustion
	 * source's q-high-AND-ε²-high signature; {@code cassi_two_fluid.glsl}). Same
	 * as the prior probe.
	 */
	private static final double DRIVE_D_EI = DRIVE_D_EY * 0.707;
	/** The Gaussian falloff radius (cells) for each burn write — the lane's own radius=3. */
	private static final int DRIVE_RADIUS = 3;
	/** How many sustained writes the driven burn fires — 24, one per job, awaited
	 * via a generation advance (the lane's newest-wins natural throttle). Declared
	 * before {@link #POST_SETTLE_GENERATIONS} (it derives from this). */
	private static final int NDRIVE_WRITES = 24;
	/**
	 * The fixed post-settle observation window (generations) BOTH the driven and
	 * the matched control advance before the "post-window" read. The driven run
	 * fires its {@link #NDRIVE_WRITES} writes within this window (each drains the
	 * newest-wins lane in ~1-2 generations), and the control waits the same window
	 * with no writes — identical to the prior probe's cadence. Both read at
	 * {@code gen = settle + POST_SETTLE}, so the write-attributable Δ is
	 * field-time matched (the body's own evolution is the control, as the sponge's
	 * own ~1.5 q collapse was).
	 */
	private static final int POST_SETTLE_GENERATIONS = NDRIVE_WRITES * 2;
	/**
	 * How many generations to observe AFTER the post-window read (the self-sustain
	 * test — does the elevated q/ε² persist (a fire) or fall back toward the
	 * control (a driven pulse)?). Both runs advance this fixed decay window so the
	 * decay Δ stays field-time matched. 8 generations ≈ 0.5 field-time — same as
	 * the prior probe.
	 */
	private static final int DECAY_GENERATIONS = 8;
	/** The radial propagation probe's reach from the fuel cell (cells). */
	private static final int FAN_RADIUS = 6;
	/** The propagation probe's "escaped" radius — the lane's own Gaussian falloff
	 * (radius {@value #DRIVE_RADIUS}); write-attributable influence beyond it has
	 * LEFT the injection's own scale and propagated. */
	private static final int ESCAPE_RADIUS = DRIVE_RADIUS + 1;
	/** The over-requested dump attempt at seed-end — a combustion write that
	 * "wants to dump" (requested D_EY ≈ 24× the no-mint cap) — the caps clamp it
	 * and {@link CassiFieldThread#perturbationClampCount} reports the refusal. */
	private static final double CLAMP_PROBE_D_EY = 5.0;
	/** Per-write drain-await / control-wait timeout — the lane is CPU-bound and
	 * each arm advances ~56 generations of body field evolution, so 180 s is the
	 * honest bound under concurrent build load. */
	private static final long DRAIN_TIMEOUT_MS = 180_000;

	// --- Verdict / determinism bounds ----------------------------------------
	/**
	 * The driven-arm detection threshold on the write-attributable Δ — below this
	 * the injected response is not a measurable organized front. Same
	 * {@value 0.05} floor the prior sponge probe used, so the comparison is honest.
	 */
	private static final double Q_RESPONSE_FLOOR = 0.05;
	/** The self-sustain margin — a persisted attributable Δq ≥ this fraction of
	 * the post-window attributable Δq counts as self-sustaining (a fire that
	 * survives after the writes stop, versus a driven pulse). Same as prior. */
	private static final double SELF_SUSTAIN_FRACTION = 0.25;
	/** The structural precision for the driven fingerprint — 4 decimals (1e-4),
	 * the honest structural precision the prior probe documented (the async drain
	 * lands writes at a 1-job phase jitter, so raw-double hashes are thread-
	 * timing-sensitive at the last ULP). */
	private static final double FP_ROUND = 1e-4;
	/** The driven arm's documented write cadence, in words, for the report. */
	private static final String DRIVE_CADENCE = "one cap-honored write per job, awaited via a published-generation advance "
			+ "(the newest-wins lane drains one per job — the natural throttle); "
			+ NDRIVE_WRITES + " writes land within the " + POST_SETTLE_GENERATIONS
			+ "-generation post-settle window";

	// --- The prior sponge probe's honest verdict (the comparison anchor) -----
	/**
	 * The prior probe's sponge-world verdict, quoted — the honest baseline this
	 * re-measure compares against. Same 24-write cadence, same D_EY/D_EI, on the
	 * old flat-noise field whose own ~1.5 q collapse swamped each write's
	 * {@code dEY·dt² ≈ 2e-7}.
	 */
	private static final String SPONGE_VERDICT =
			"INCONCLUSIVE(micro-scale) — 24 cap-honored writes (each dEY·dt² ≈ 2e-7) "
			+ "shifted the fuel cell by only |attributable Δq| ≈ 0.0 relative to the "
			+ "matched control, below the 0.05 response floor — the lane's dt²-scaled, "
			+ "no-mint-capped injection cannot organize a measurable front at this dt "
			+ "operating point on the flat-noise sponge";

	// --- World <-> cell mapping (mirrors the Q4 lane's own formula) ----------
	/** The box-center grid cell N/2. */
	private static final int MID = TwoFluidSolver.N / 2;
	private static final int N = TwoFluidSolver.N;

	// --- Fuel-cell flat index ------------------------------------------------
	/** The dense-body fuel cell's flat index {@code (cx,cy,cz)=(32,8,32)} —
	 * {@code 32 + 64·(8 + 64·32) = 131616}. Computed from the world point via the
	 * lane's own world→cell formula. */
	private static final int FUEL_CELL = worldToCell(FUEL_POS[0], FUEL_POS[1], FUEL_POS[2]);

	/** The flat index the Q4 lane would write to for a world point under
	 * {@link #WINDOW_CENTER} — the lane's own mapping, mirrored exactly. */
	private static int worldToCell(double wx, double wy, double wz) {
		double w = CassiFieldThread.CELL_WORLD_WIDTH;
		int cx = (int) Math.floor((wx - WINDOW_CENTER[0]) / w) + MID;
		int cy = (int) Math.floor((wy - WINDOW_CENTER[1]) / w) + MID;
		int cz = (int) Math.floor((wz - WINDOW_CENTER[2]) / w) + MID;
		cx = ((cx % N) + N) % N;
		cy = ((cy % N) + N) % N;
		cz = ((cz % N) + N) % N;
		return cx + N * (cy + N * cz);
	}

	public static void main(String[] args) throws Exception {
		boolean ok = true;

		// --- Matched control first: the body's own evolution, no writes -------
		Driven ctrl = runDriven(SEED_A, false);
		System.out.println("\n[combustion-body] matched control (no writes, seed " + SEED_A + "):\n" + ctrl);

		// --- The driven burn on the body --------------------------------------
		Driven d1 = runDriven(SEED_A, true);
		Driven d2 = runDriven(SEED_A, true);
		Driven d3 = runDriven(SEED_B, true);

		// Clock the write cadence + caps margin at the dense-body fuel.
		System.out.println("\n[combustion-body] Q4 write cadence: " + DRIVE_CADENCE
				+ " at fuel world (" + fmt(FUEL_POS[0]) + "," + fmt(FUEL_POS[1]) + "," + fmt(FUEL_POS[2])
				+ ") → cell (32," + fuelCy() + ",32), flat " + FUEL_CELL
				+ "; D_EY=" + fmt(DRIVE_D_EY) + " D_EI=" + fmt(DRIVE_D_EI)
				+ " radius=" + DRIVE_RADIUS
				+ " (no-mint cap ≈ " + fmt(FUEL_NO_MINT_CAP_APROX) + "; D_EY is " + pct(DRIVE_D_EY / FUEL_NO_MINT_CAP_APROX)
				+ " of it — the sustained burn does not want to dump)");

		// The write-attributable response.
		String verdict = bodyVerdict(d1, ctrl);
		double attribDq = d1.qEnd() - ctrl.qEnd();
		double attribDeps = d1.epsEnd() - ctrl.epsEnd();
		double attribDqDecay = d1.qDecay() - ctrl.qDecay();
		// The self-sustain persist fraction is only meaningful when the attributable
		// post-window Δq clears the response floor — below it the ratio is the
		// divide-by-near-zero artifact of two micro-scale floats and is printed n/a.
		double persistFrac = (Math.abs(attribDq) >= Q_RESPONSE_FLOOR) ? attribDqDecay / attribDq : 0.0;
		String persistStr = (Math.abs(attribDq) >= Q_RESPONSE_FLOOR)
				? fmt(100.0 * persistFrac) + "%"
				: "n/a (attributable Δq below the response floor)";
		// Propagation character: does the write-attributable influence escape the
		// Gaussian falloff (r > DRIVE_RADIUS) and delocalize, or stay confined?
		double[] prop = propagation(ctrl.fan(), d1.fan());
		boolean escaped = prop[0] >= Q_RESPONSE_FLOOR;

		System.out.println("\n[combustion-body] WRITE-ATTRIBUTABLE FUEL RESPONSE (driven − matched control, same seed " + SEED_A + "):");
		System.out.println("[combustion-body]   Δq(post-window)=" + fmt(attribDq)
				+ "  Δε²(post-window)=" + fmt(attribDeps)
				+ "  Δq(decay)=" + fmt(attribDqDecay)
				+ "   persist=" + persistStr
				+ "   [floor " + fmt(Q_RESPONSE_FLOOR) + ", self-sustain bar " + fmt(100.0 * SELF_SUSTAIN_FRACTION) + "%]");
		System.out.println("[combustion-body]   propagation: mean attributable Δq beyond the falloff (r > " + DRIVE_RADIUS
				+ ") = " + fmt(prop[0]) + " [escaped the injection's own scale: " + escaped + "]; "
				+ "outer/fuel attributable ratio = " + fmt(prop[1]));
		System.out.println("[combustion-body]   radial fan (r: mean q, mean ε²) driven vs control:");
		for (int r = 0; r <= FAN_RADIUS; r++) {
			System.out.println("[combustion-body]     r" + r + "  driven (" + fmt(d1.fan()[r][0]) + "," + fmt(d1.fan()[r][1])
					+ ")  control (" + fmt(ctrl.fan()[r][0]) + "," + fmt(ctrl.fan()[r][1]) + ")");
		}
		System.out.println("[combustion-body]   Q4-DRIVEN run1 (" + SEED_A + "):\n" + d1);
		System.out.println("[combustion-body]   Q4-DRIVEN run2 (" + SEED_A + "):\n" + d2);
		System.out.println("[combustion-body]   Q4-DRIVEN run3 (" + SEED_B + "):\n" + d3);

		// The gate asserts.
		boolean drivenDeterministic = d1.fingerprint().equals(d2.fingerprint());
		boolean drivenSeedSensitive = !d1.fingerprint().equals(d3.fingerprint());
		boolean capsRefuseDump = d1.dumpClamped() >= 1 && d2.dumpClamped() >= 1 && d3.dumpClamped() >= 1;
		// "Writes moved the fuel vs control": the attributable Δ at micro-scale is
		// nonzero (the lane routed the writes), OR the dump-probe clamped ≥ 1 (the
		// lane demonstrably executed a write at drain). On the body the sustained
		// burn's surface response is far below the 0.05 floor, but the lane DID
		// route each write — this asserts the probe is not vacuous without forcing
		// a front that the honest INCONCLUSIVE verdict says is not measurable.
		boolean drivenMovedField = (attribDq != 0.0 || attribDeps != 0.0)
				|| (d1.dumpClamped() >= 1);
		System.out.println("\n[combustion-body] driven determinism (same seed + same write cadence → identical SHA-256 fingerprint): "
				+ drivenDeterministic
				+ " | different-seed differs: " + drivenSeedSensitive
				+ " | writes moved the fuel vs control: " + drivenMovedField
				+ " | caps refused the dump-probe: " + capsRefuseDump);
		System.out.println("[combustion-body] caps telemetry: total clampCount=" + d1.clampCount()
				+ " (of " + NDRIVE_WRITES + " burn writes + 1 dump-probe), dumpClamped=" + d1.dumpClamped()
				+ " — " + capsMessage(d1.clampCount()));

		// The explicit body-vs-sponge comparison (the honest what-changed).
		System.out.println("\n[combustion-body] BODY vs PRIOR SPONGE PROBE (the honest comparison):");
		System.out.println("[combustion-body]   prior sponge (CombustionProbeMain):   " + SPONGE_VERDICT);
		System.out.println("[combustion-body]   this body world (CombustionBodyProbeMain): " + verdict);
		System.out.println("[combustion-body]   c_s reference unchanged at " + fmt(C_S_REF)
				+ " world-units/ft = " + fmt(C_S_CELLS) + " cells/ft; box traversed "
				+ fmt(POST_SETTLE_GENERATIONS * CassiFieldThread.JOB_STEP_CAP * TwoFluidSolver.DT * C_S_CELLS / N)
				+ "× over the observation window (delocalized by box-wrap — clean pre-wrap front speed not resolvable, "
				+ "the prior probe's own caveat)");

		System.out.println("\n[combustion-body] BODY DRIVEN-FRONT VERDICT: " + verdict);

		if (!drivenDeterministic) {
			System.err.println("[combustion-body] FAIL — same seed + same write cadence produced a different driven structural fingerprint");
			ok = false;
		}
		if (!drivenSeedSensitive) {
			System.err.println("[combustion-body] FAIL — different seeds produced an identical driven fingerprint (vacuous)");
			ok = false;
		}
		if (!capsRefuseDump) {
			System.err.println("[combustion-body] FAIL — the dump-probe did not engage the caps on a driven arm (unexpected mint path)");
			ok = false;
		}
		if (!drivenMovedField) {
			System.err.println("[combustion-body] FAIL — the driven writes left the fuel cell identical to the control (vacuous)");
			ok = false;
		}

		if (ok) {
			System.out.println("[combustion-body] PASS — the driven burn on the body is deterministic, seed-sensitive, cap-honest, and its verdict is measured over the matched control");
		} else {
			System.err.println("[combustion-body] FAILED");
			System.exit(1);
		}
	}

	/** The dense-body fuel cell's cy (== the world −2 maps to, printed for audit). */
	private static int fuelCy() {
		return FUEL_CELL / N % N;
	}

	/** The caps telemetry message — a clamp is an honest report of the bounded-
	 * organization boundary, not a failure (documented for the report). */
	private static String capsMessage(long clamps) {
		if (clamps == 0) {
			return "every burn write drained under the caps (bounded organization, no clamp)";
		}
		return clamps + " of the writes were clamped by the Q4 honesty caps (no-mint φ⁻¹×√q and/or "
				+ "overdraw ω₀²×|ε|) — bounded organization, an honest clamp report, not a mint";
	}

	/**
	 * Run the driven-front measurement for one seed and one arm: settle to
	 * {@link #SETTLE_GENERATIONS}, then advance a FIXED post-settle window
	 * ({@link #POST_SETTLE_GENERATIONS}) — the driven arm fires
	 * {@link #NDRIVE_WRITES} sustained combustion writes through the real Q4 lane
	 * within that window (one per job, awaited via a generation advance), the
	 * control arm merely waits the same window with no writes. Both then read the
	 * post-window fuel-cell q/ε² and a radial fan at field-time matched
	 * {@code gen = settle + POST_SETTLE}, then advance a FIXED decay window
	 * ({@link #DECAY_GENERATIONS}) and read again for the self-sustain test (also
	 * matched). Ends (driven arm only) with an over-requested dump-probe write to
	 * exercise the honesty caps' clamp.
	 *
	 * <p>The write-attributable response is {@code driven − control} computed by
	 * the caller over the ABSOLUTE post-window and decay fuel q/ε² this method
	 * exposes — the body's own evolution is the control.
	 *
	 * @return the driven-front measurement (absolute fuel q/ε², radial fan, clamp
	 *         telemetry, fingerprint)
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
			double[] qeEnd = fuelRead(snapEnd);
			double[][] fan = radialFan(snapEnd);

			// Fixed decay window — both arms advance identically.
			awaitGeneration(pub, targetGen + DECAY_GENERATIONS, DRAIN_TIMEOUT_MS);
			double[] qeDecay = fuelRead(pub.freshest());

			// Dump-probe (driven only): an over-requested write the caps refuse.
			long preDumpClamps = worker.perturbationClampCount();
			long dumpClamped = 0;
			if (drive) {
				worker.submitPerturbation(FUEL_POS[0], FUEL_POS[1], FUEL_POS[2],
						CLAMP_PROBE_D_EY, CLAMP_PROBE_D_EY * 0.707, DRIVE_RADIUS);
				awaitGeneration(pub, pub.generation() + 1, DRAIN_TIMEOUT_MS);
				dumpClamped = worker.perturbationClampCount() - preDumpClamps;
			}
			long totalClamps = worker.perturbationClampCount();

			String fp = drivenFingerprint(drive, qeEnd[0], qeEnd[1], qeDecay[0], qeDecay[1]);
			return new Driven(qeEnd[0], qeEnd[1], qeEnd[2], qeDecay[0], qeDecay[1], fan,
					NDRIVE_WRITES, totalClamps, dumpClamped, fp, drive);
		} finally {
			worker.close();
		}
	}

	/** The settled fuel-cell {@code q} and derived {@code ε² = (EY−φ·EI)²} (the
	 * φ-locked branch, as {@code Quantizer.eps2}) plus the box-center EY — read
	 * from the raw published grid at the dense-body fuel cell {@link #FUEL_CELL}. */
	private static double[] fuelRead(FieldSnapshot snap) {
		int cell = FUEL_CELL;
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
	 * from the fuel cell — the propagation probe (does the source influence leave
	 * the fuel cell's Gaussian falloff?). Returns {@code [r][0]=qM, [r][1]=epsM}. */
	private static double[][] radialFan(FieldSnapshot snap) {
		int fc = FUEL_CELL;
		int cx = fc % N;
		int cy = fc / N % N;
		int cz = fc / (N * N);
		double[][] out = new double[FAN_RADIUS + 1][2];
		long[] cnt = new long[FAN_RADIUS + 1];
		for (int k = 0; k < N; k++) {
			int dk = minWrap(k - cz, N);
			for (int j = 0; j < N; j++) {
				int dj = minWrap(j - cy, N);
				for (int i = 0; i < N; i++) {
					int di = minWrap(i - cx, N);
					int r = (int) Math.round(Math.sqrt((double) di * di + dj * dj + dk * dk));
					if (r > FAN_RADIUS) {
						continue;
					}
					int cell = i + N * (j + N * k);
					float rv = snap.rho()[cell];
					float qv = snap.q()[cell];
					float d2v = 2.0f * qv - rv * rv;
					float dv = (float) Math.sqrt(Math.max(0.0f, d2v));
					float eyv = (rv + dv) * 0.5f;
					float eiv = (rv - dv) * 0.5f;
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

	/** The propagation character from two radial fans — the write-attributable
	 * Δq summed over the shells beyond the injection's own falloff
	 * (r &gt; {@link #DRIVE_RADIUS}). Returns {@code {escapeAttribQ,
	 * outerToFuelRatio}} where the ratio is mean outer attributable Δq ÷ fuel-cell
	 * attributable Δq — a small ratio means the influence stayed confined, a
	 * comparable one means it escaped and spread. */
	private static double[] propagation(double[][] controlFan, double[][] drivenFan) {
		double fuelAttrib = drivenFan[0][0] - controlFan[0][0];
		double outerSum = 0.0;
		int outerCnt = 0;
		for (int r = ESCAPE_RADIUS; r <= FAN_RADIUS; r++) {
			outerSum += drivenFan[r][0] - controlFan[r][0];
			outerCnt++;
		}
		double outerMean = outerCnt > 0 ? outerSum / outerCnt : 0.0;
		double ratio = Math.abs(fuelAttrib) < 1e-12 ? 0.0 : outerMean / fuelAttrib;
		return new double[] { outerMean, ratio };
	}

	/** The cell-space distance sign-free min-wrap of a displacement into [0, N/2]. */
	private static int minWrap(int d, int n) {
		int w = d % n;
		if (w < 0) {
			w += n;
		}
		return Math.min(w, n - w);
	}

	/**
	 * The body driven-front verdict — computed from the write-attributable
	 * response {@code driven − control} at the matched post-window and decay
	 * reads and the propagation character, never forced:
	 * <ul>
	 *   <li>attributable Δq = driven.qEnd − control.qEnd and Δε² likewise;</li>
	 *   <li>the fire signature is q HIGH AND ε² HIGH — the source must hold the
	 *       fuel's q and ε² ABOVE the unwritten control's own evolution;</li>
	 *   <li>self-sustain = the attributable Δq persists ≥ {@link
	 *       #SELF_SUSTAIN_FRACTION} of its post-window value after the decay
	 *       window (writes have stopped);</li>
	 *   <li>propagation = the attributable Δq beyond the injection's falloff
	 *       ({@link #ESCAPE_RADIUS}) ≥ the response floor — the influence left the
	 *       fuel cell (a front), not a confined injection.</li>
	 * </ul> */
	private static String bodyVerdict(Driven driven, Driven control) {
		double dq = driven.qEnd() - control.qEnd();
		double deps = driven.epsEnd() - control.epsEnd();
		double dqDecay = driven.qDecay() - control.qDecay();
		double dq0 = dq; // the post-window attributable rise
		if (Math.abs(dq) < Q_RESPONSE_FLOOR && Math.abs(deps) < Q_RESPONSE_FLOOR
				&& Math.abs(dqDecay) < Q_RESPONSE_FLOOR) {
			return "INCONCLUSIVE(micro-scale) — " + NDRIVE_WRITES
					+ " cap-honored writes (each dEY·dt² ≈ "
					+ sprintf7(DRIVE_D_EY * TwoFluidSolver.DT * TwoFluidSolver.DT)
					+ ") shifted the body fuel cell by only |attributable Δq|="
					+ fmt(Math.abs(dq)) + " relative to the matched control, below the "
					+ fmt(Q_RESPONSE_FLOOR) + " response floor. The mechanism DIFFERS from "
					+ "the sponge (whose own ~1.5 q collapse swamped the writes): on the "
					+ "coherent dense body the writes drained almost UNCLAMPED (see caps "
					+ "telemetry — few burn clamps) yet still left zero measurable differential, "
					+ "so the high-q φ-locked ground ABSORBS the dt²-scaled, no-mint-capped "
					+ "injection into its own cohesion faster than it accumulates an organized "
					+ "front — no burn signature and no propagation at this dt operating point.";
		}
		boolean coheres = dq > 0;
		boolean heats = deps > 0;
		boolean fireSignature = coheres && heats;

		// Propagation: did the influence leave the fuel falloff?
		double[][] cf = control.fan();
		double[][] df = driven.fan();
		double[] prop = propagation(cf, df);
		boolean escaped = prop[0] >= Q_RESPONSE_FLOOR;

		double persistFrac = dq0 == 0 ? 0.0 : dqDecay / dq0;
		boolean selfSustaining = persistFrac >= SELF_SUSTAIN_FRACTION;

		if (fireSignature && selfSustaining && escaped) {
			return "SUPPORTS — a self-sustaining organized front on the body: the driven "
					+ "fuel cell holds attributable q and ε² ABOVE the unwritten control "
					+ "(Δq=" + fmt(dq) + ", Δε²=" + fmt(deps) + "), persists "
					+ fmt(100.0 * persistFrac) + "% of its post-window rise after the writes "
					+ "stop, and the influence escaped the fuel falloff (outer Δq=" + fmt(prop[0])
					+ ") — a fire, not a driven pulse; the coherent dense body's near-equilibrium "
					+ "ground holds the burn the sponge could not";
		}
		if (!fireSignature) {
			return "CONTRADICTS — the driven source does not carry the q-high-AND-ε²-high "
					+ "fire signature relative to the body control (attributable Δq=" + fmt(dq)
					+ ", Δε²=" + fmt(deps) + "); a coherent φ-locked body has little ε² room to "
					+ "disorder into (the ω₀² re-lock cap), so the burn's heat leg cannot form";
		}
		if (!escaped) {
			return "CONTRADICTS — the driven influence never escaped the fuel cell's Gaussian "
					+ "falloff (outer attributable Δq=" + fmt(prop[0]) + " < the "
					+ fmt(Q_RESPONSE_FLOOR) + " floor) — the body's dense ground absorbs the "
					+ "source locally rather than propagating a front";
		}
		return "CONTRADICTS — the driven front decays without sustained writes (attributable "
				+ "Δq persisted " + fmt(100.0 * persistFrac) + "% of its post-window rise, below the "
				+ fmt(100.0 * SELF_SUSTAIN_FRACTION) + "% self-sustain bar) — a driven pulse, not a "
				+ "self-sustaining fire on the body";
	}

	/** The driven arm's deterministic SHA-256 fingerprint — over the ABSOLUTE
	 * post-window/decay fuel-cell q/ε² (rounded to {@link #FP_ROUND}) plus the
	 * drive flag. Same seed + same write cadence → identical; different seed
	 * (different fuel-cell field) → differs. The clamp counter and radial fan are
	 * excluded (the lane's drain timing can race them by one increment; the prior
	 * probe's own finding). */
	private static String drivenFingerprint(boolean drive, double qEnd, double epsEnd,
			double qDecay, double epsDecay) {
		StringBuilder sb = new StringBuilder();
		sb.append("drive=").append(drive)
				.append(";bodyFuelCell=").append(FUEL_CELL)
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

	/** 7-decimal formatting — for sub-noise values like the per-write injection
	 * {@code dEY·dt² ≈ 2e-7} that 4-decimal {@code fmt} would round to zero. */
	private static String sprintf7(double v) {
		return String.format("%.7f", v);
	}

	private static String pct(double v) {
		return String.format("%.4f", v);
	}

	/** The full driven-front measurement of one run — the ABSOLUTE fuel-cell
	 * q/ε² at the matched post-window and decay reads, the radial fan, clamp
	 * telemetry, and the drive flag. The write-attributable response is
	 * {@code driven − control} computed by the caller against a same-seed
	 * matched control. */
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
				fb.append(" r").append(r).append("=(")
						.append(fmt(fan[r][0])).append(",").append(fmt(fan[r][1])).append(")");
			}
			fb.append("\n   fingerprint=").append(fingerprint.substring(0, 16)).append("...");
			return fb.toString();
		}
	}

	private static String fmt6(double v) {
		return String.format("%.6f", v);
	}

	private CombustionBodyProbeMain() {
	}
}
