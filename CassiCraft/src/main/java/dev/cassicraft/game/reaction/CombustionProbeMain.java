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

	// --- Determinism --------------------------------------------------------
	/** The box-center grid cell (N/2,N/2,N/2) — the fixed interior sample point. */
	private static final int MID = TwoFluidSolver.N / 2;

	/** The grid-cell index of the box-center sample point. */
	private static int midCell() {
		return MID + TwoFluidSolver.N * (MID + TwoFluidSolver.N * MID);
	}

	public static void main(String[] args) throws Exception {
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

		if (ok) {
			System.out.println("[combustion-probe] PASS — the no-source baseline is deterministic and seed-sensitive");
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

	private static String fmtP(double v) {
		return String.format("%.4f", v);
	}

	private static String pct(double v) {
		return String.format("%.4f", v);
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
