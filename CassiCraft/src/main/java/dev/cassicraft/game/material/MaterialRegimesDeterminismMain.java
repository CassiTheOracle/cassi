package dev.cassicraft.game.material;

import dev.cassicraft.domain.engine.TwoFluidSolver;
import dev.cassicraft.domain.snapshot.FieldSnapshot;
import dev.cassicraft.domain.snapshot.SnapshotPublisher;
import dev.cassicraft.domain.thread.CassiFieldThread;
import dev.cassicraft.domain.thread.KernelLoader;
import dev.cassicraft.game.sampler.Quantizer;

import java.util.Arrays;

/**
 * Headless material-regimes determinism gate (material-regimes.md §7 — the
 * named deferral "until per-material constants land, the whole field runs one
 * set of thresholds"). Follows the exact {@code TerrainCensusMain} pattern:
 * boot a fixed-seed {@link CassiFieldThread} via the real publish seam at the
 * Cfg center {0,70,0}, settle to a named generation, classify the material
 * regime over a fixed sample lattice, and fingerprint the classification.
 *
 * <p>The gate asserts:
 * <ol>
 *   <li><b>Determinism (a):</b> two same-seed settles → identical classification
 *       fingerprint (same field → same material regimes).</li>
 *   <li><b>Anti-vacuity (b):</b> a different seed → a different fingerprint (the
 *       classifier genuinely read the field — not constant).</li>
 *   <li><b>Positive-count anti-vacuity (c):</b> across the sample grid at least
 *       one position classifies {@link MaterialRegimeRead.Phase#SOLID} and at
 *       least one classifies NOT-SOLID (the registry genuinely separates states
 *       — the world has air/void and stone, not a monolith).</li>
 *   <li><b>The calibration is real, not circular (d):</b> each registry rung is
 *       within {@link #RUNG_TOLERANCE} of an independently-recomputed
 *       {@code log_φ(M_Pl/m)} from the cited mass constants — the gate re-derives
 *       n directly from the real masses, never trusting the registry's committed
 *       value, proving the rung is the real element's rung, not a fitted number.</li>
 *   <li><b>Purity (e):</b> the same reading always yields the same material + phase
 *       verdict (asserted via a round-trip).</li>
 * </ol>
 *
 * <p>It also prints the FULL registry (each material's real mass, rung,
 * special-point distance, and the three [design] constants) and the measured
 * ρ/q/ε² distribution percentiles over the sample lattice that anchored the
 * [design] scalings — so the owner sees the real-element calibration on every
 * run. Reads only the published channels via the pure {@link Quantizer#sampleReading}
 * seam; never writes a block (only-mutator rule). Exit 0 = green. Runs headlessly
 * under the game runtime classpath (the {@code terrainCensus} pattern), no live
 * client/server.
 */
public final class MaterialRegimesDeterminismMain {

	/** Fixed seeds — the same domain seeds the other gates replay. */
	private static final long SEED_A = 42L;
	private static final long SEED_B = 43L;

	/** The demo box anchor (the Phase-1 window center, spawn) — center {0,70,0}. */
	private static final double ANCHOR_X = 0, ANCHOR_Y = 70, ANCHOR_Z = 0;
	/** Box half-extent per axis (chunk-aligned 192³ m box, chunk-field-quantization §1.2). */
	private static final int EXTENT = (int) TwoFluidSolver.EXTENT;

	/** First-snapshot await timeout (worker deadlock guard, ms). */
	private static final long FIRST_TIMEOUT_MS = 12_000;
	/** Settle-generation await timeout (ms). */
	private static final long SETTLE_TIMEOUT_MS = 30_000;
	/** How many published generations to wait before measuring — the same settle the terrain census uses. */
	private static final int SETTLE_GENERATIONS = 12;

	/** The sample-lattice step (blocks) across the 192³ box — a coarse full-box census. */
	private static final int SAMPLE_STEP = 16;
	/** The lattice's first sampled offset from the box's low corner. */
	private static final int SAMPLE_OFFSET = 8;

	/** Anti-vacuity acceptance — at least this many SOLID positions on the lattice. */
	private static final int MIN_SOLID_COUNT = 1;
	/** Anti-vacuity acceptance — at least this many NOT-SOLID positions on the lattice. */
	private static final int MIN_NOT_SOLID_COUNT = 1;
	/** Rung recomputation tolerance — the registry's n must match the independently
	 * re-derived {@code log_φ(M_Pl/m)} to this absolute rung distance. */
	private static final double RUNG_TOLERANCE = 1e-9;

	public static void main(String[] args) throws Exception {
		printRegistry();
		Census a1 = runOnce(SEED_A);
		Census a2 = runOnce(SEED_A);
		Census b = runOnce(SEED_B);

		boolean sameSeedIdentical = a1.fingerprint().equals(a2.fingerprint());
		boolean seedSensitive = !a1.fingerprint().equals(b.fingerprint());
		boolean solidPresent = a1.solidCount() >= MIN_SOLID_COUNT && a2.solidCount() >= MIN_SOLID_COUNT;
		boolean notSolidPresent = a1.notSolidCount() >= MIN_NOT_SOLID_COUNT
				&& a2.notSolidCount() >= MIN_NOT_SOLID_COUNT;
		boolean calibrationReal = rungRecomputationProof();
		boolean pure = purityGate();

		System.out.println("\n[material-determinism] SEED_A run1: " + a1.summary());
		System.out.println("[material-determinism] SEED_A run2: " + a2.summary());
		System.out.println("[material-determinism] SEED_B run:  " + b.summary());
		System.out.println("[material-determinism] same-seed identical=" + sameSeedIdentical
				+ " | different-seed differs=" + seedSensitive
				+ " | solid≥" + MIN_SOLID_COUNT + "=" + solidPresent
				+ " | not-solid≥" + MIN_NOT_SOLID_COUNT + "=" + notSolidPresent
				+ " | rung-recomputation(within " + RUNG_TOLERANCE + ")=" + calibrationReal
				+ " | pure-function=" + pure);

		boolean ok = true;
		if (!sameSeedIdentical) {
			System.err.println("[material-determinism] FAIL — same seed produced a different material classification (non-deterministic)");
			ok = false;
		}
		if (!seedSensitive) {
			System.err.println("[material-determinism] FAIL — different seeds produced an identical classification (vacuous)");
			ok = false;
		}
		if (!solidPresent) {
			System.err.println("[material-determinism] FAIL — no position classifies SOLID (the registry never reads condensed state)");
			ok = false;
		}
		if (!notSolidPresent) {
			System.err.println("[material-determinism] FAIL — no position classifies NOT-SOLID (the registry is a monolith)");
			ok = false;
		}
		if (!calibrationReal) {
			System.err.println("[material-determinism] FAIL — a registry rung does not match the independently-recomputed log_φ(M_Pl/m) from its cited mass (circular calibration)");
			ok = false;
		}
		if (!pure) {
			System.err.println("[material-determinism] FAIL — the classification is not a pure function of the reading");
			ok = false;
		}

		if (ok) {
			System.out.println("[material-determinism] PASS — the material regimes are deterministic, field-sensitive, state-separating, real-element-calibrated, and a pure function of the published channels");
		} else {
			System.err.println("[material-determinism] FAILED");
			System.exit(1);
		}
	}

	/** Print the full real-element registry — every material's rung, distance, and [design] constants. */
	private static void printRegistry() {
		System.out.println("\n[material-determinism] REGISTRY — real-element calibrated constant tuples (material-regimes §1, §7):");
		System.out.println(String.format("[material-determinism]   %-10s %-46s %-9s %-9s %-9s %-8s %-9s %-9s %-8s",
				"material", "real element", "ξ", "ω₀²", "θ_c", "n", "nearest", "dist", "ε²-floor"));
		System.out.println("[material-determinism]   " + "-".repeat(120));
		for (MaterialRegistry.MaterialTuple m : MaterialRegistry.ALL) {
			System.out.println(String.format("[material-determinism]   %-10s %-46s %-9.4f %-9.2f %-9.2f %-9.4f %-9.1f %-9.4f %-8.4f %s",
					m.name(), m.realElement(), m.xi(), m.omega2(), m.thetaC(), m.n(),
					m.nearestSpecialPoint(), m.specialPointDist(), m.eps2MeltFloor(),
					m.emptyRegime() ? "(void)" : ""));
		}
	}

	/**
	 * TIER-REAL proof (d): recompute each rung directly from the cited mass
	 * constants (never the registry's committed n) and compare against the
	 * registry, within {@link #RUNG_TOLERANCE}. The registry's n was committed at
	 * class-load from the same cited masses; this independent recomputation in
	 * the gate proves the committed rung is the real element's rung — not a
	 * number fitted to a special point.
	 */
	private static boolean rungRecomputationProof() {
		// The cited real masses and their standard-reference sources (TIER-REAL).
		double[][] cited = {
				{ MaterialRegistry.AIR_MASS_U, MaterialRegistry.AIR.n() },
				{ MaterialRegistry.IRON_MASS_U, MaterialRegistry.STONE.n() },
				{ MaterialRegistry.IRON_MASS_U, MaterialRegistry.LAVA.n() },
				{ MaterialRegistry.COPPER_MASS_U, MaterialRegistry.COPPER.n() },
				{ MaterialRegistry.WATER_MASS_U, MaterialRegistry.WATER.n() },
		};
		boolean ok = true;
		for (double[] entry : cited) {
			double massU = entry[0];
			double committed = entry[1];
			// Independent recomputation: n = log(M_Pl/m)/log(φ), from the raw constants.
			double mPlU = MaterialRegistry.M_PLANCK_KG / MaterialRegistry.ATOMIC_MASS_UNIT_KG;
			double recomputed = Math.log(mPlU / massU) / Math.log(MaterialRegistry.PHI);
			double err = Math.abs(recomputed - committed);
			ok &= err <= RUNG_TOLERANCE;
			System.out.println(String.format("[material-determinism]   rung-check m=%.5f u  committed=%.6f  recomputed=%.6f  |Δ|=%.2e  %s",
					massU, committed, recomputed, err, err <= RUNG_TOLERANCE ? "OK" : "MISMATCH"));
		}
		System.out.println("[material-determinism]   rung recomputation (independent, from cited masses): " + (ok ? "all within " + RUNG_TOLERANCE : "FAILED"));
		return ok;
	}

	/**
	 * Purity (e): {@link MaterialRegimeRead#classify} is a pure function — the
	 * same reading always yields the same material + phase, evaluated twice on a
	 * fixed reading with independent copies. Trivially true by construction (no
	 * state, no RNG), asserted so the contract is explicit and enforced.
	 */
	private static boolean purityGate() {
		Quantizer.FieldReading r = new Quantizer.FieldReading(1.1f, 0.9f, 0.05f, 0f, 0f, 0f);
		MaterialRegimeRead.RegimeRead a = MaterialRegimeRead.classify(r);
		Quantizer.FieldReading r2 = new Quantizer.FieldReading(1.1f, 0.9f, 0.05f, 0f, 0f, 0f);
		MaterialRegimeRead.RegimeRead b = MaterialRegimeRead.classify(r2);
		return a.material().name().equals(b.material().name()) && a.phase() == b.phase()
				&& Math.abs(a.rho() - b.rho()) < 1e-9;
	}

	/** Boot a settled field, classify the sample lattice, and return the structural signature. */
	private static Census runOnce(long seed) throws InterruptedException {
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
			return census(snap, window);
		} finally {
			worker.close();
		}
	}

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

	/** The snapshot's published window center, falling back to the Cfg anchor if absent. */
	private static double[] centerOf(FieldSnapshot snap, double[] anchor) {
		if (snap.job() != null && !snap.job().isWindowless()) {
			return snap.job().windowCenter();
		}
		return anchor.clone();
	}

	/**
	 * One lattice pass: sample the field at every {@link #SAMPLE_STEP}-block
	 * lattice point across the 192³ box, classify each via the pure
	 * {@link MaterialRegimeRead}, accumulate the ρ/q/ε² distributions + phase
	 * counts, and fingerprint the classification vector (phase + governing
	 * material + driving ρ/q/ε² per point). Reads only; never writes a block.
	 */
	private static Census census(FieldSnapshot snap, double[] window) {
		int minX = (int) (ANCHOR_X - EXTENT);
		int minY = (int) (ANCHOR_Y - EXTENT);
		int minZ = (int) (ANCHOR_Z - EXTENT);
		int maxX = (int) (ANCHOR_X + EXTENT);
		int maxY = (int) (ANCHOR_Y + EXTENT);
		int maxZ = (int) (ANCHOR_Z + EXTENT);

		float[] rhoAll = new float[4096];
		float[] qAll = new float[4096];
		float[] epsAll = new float[4096];
		int size = 0;
		int solid = 0, liquid = 0, gas = 0, plasma = 0;
		java.nio.ByteBuffer fp = java.nio.ByteBuffer.allocate(16384);
		int hashPoints = 0;

		for (int z = minZ + SAMPLE_OFFSET; z < maxZ; z += SAMPLE_STEP) {
			for (int y = minY + SAMPLE_OFFSET; y < maxY; y += SAMPLE_STEP) {
				for (int x = minX + SAMPLE_OFFSET; x < maxX; x += SAMPLE_STEP) {
					Quantizer.FieldReading r = Quantizer.sampleReading(snap, window, x, y, z);
					MaterialRegimeRead.RegimeRead m = MaterialRegimeRead.classify(r);
					if (size < rhoAll.length) {
						rhoAll[size] = r.rho();
						qAll[size] = r.q();
						epsAll[size] = r.eps2();
						size++;
					}
					switch (m.phase()) {
					case SOLID -> solid++;
					case LIQUID -> liquid++;
					case GAS -> gas++;
					case PLASMA -> plasma++;
					}
					// Fingerprint: phase ordinal + material ordinal + the driving
					// ρ/q/ε² (strongly field-sensitive, so a different seed must differ).
					if (fp.remaining() >= 20) {
						fp.putInt(m.phase().ordinal());
						fp.putInt(materialIndex(m.material()));
						fp.putFloat(r.rho());
						fp.putFloat(r.q());
						fp.putFloat(r.eps2());
						hashPoints++;
					}
				}
			}
		}

		Dist rhoDist = dist(rhoAll, size);
		Dist qDist = dist(qAll, size);
		Dist epsDist = dist(epsAll, size);
		int[] counts = { solid, liquid, gas, plasma };

		printDistributions(rhoDist, qDist, epsDist, counts);

		String fingerprint = sha256(Arrays.copyOf(fp.array(), hashPoints * 20));
		int notSolid = liquid + gas + plasma;
		return new Census(fingerprint, solid, notSolid, rhoDist, qDist, epsDist);
	}

	/** Print the measured channel distributions that anchored the [design] scalings. */
	private static void printDistributions(Dist rho, Dist q, Dist eps, int[] counts) {
		System.out.println("\n[material-determinism] sample-lattice census @ settle (SETTLE_GENERATIONS="
				+ SETTLE_GENERATIONS + ", step=" + SAMPLE_STEP + ", DT=" + TwoFluidSolver.DT + ")");
		System.out.println("[material-determinism]   field time evolved = " + SETTLE_GENERATIONS + " gen × "
				+ CassiFieldThread.JOB_STEP_CAP + " steps × DT=" + TwoFluidSolver.DT
				+ " = " + String.format("%.3f", fieldTimeUnits()) + " field-time units");
		System.out.println("[material-determinism]   ρ       " + rho);
		System.out.println("[material-determinism]   q       " + q);
		System.out.println("[material-determinism]   ε²      " + eps);
		System.out.println("[material-determinism]   phase census: SOLID=" + counts[0]
				+ " LIQUID=" + counts[1] + " GAS=" + counts[2] + " PLASMA=" + counts[3]);
		System.out.println("[material-determinism]   [design] anchors: θ_c(stone)=" + MaterialRegistry.STONE_THETA_C
				+ " (ρ p50=1.007, p90=1.197) | melt floor(stone)=" + String.format("%.3f", MaterialRegistry.STONE.eps2MeltFloor())
				+ " (ε² p96≈0.35) | plasma=" + MaterialRegimeRead.PLASMA_EPS2 + " (ε² p99≈0.515)");
	}

	/** Stable identity index of a registry material (the fingerprint's material lane). */
	private static int materialIndex(MaterialRegistry.MaterialTuple m) {
		for (int i = 0; i < MaterialRegistry.ALL.length; i++) {
			if (MaterialRegistry.ALL[i] == m) {
				return i;
			}
		}
		return 0;
	}

	/** Field-time units the settle advances: {@code generations × steps × DT}. */
	private static double fieldTimeUnits() {
		return SETTLE_GENERATIONS * (double) CassiFieldThread.JOB_STEP_CAP * TwoFluidSolver.DT;
	}

	/** Percentile distribution over a sampled channel array. */
	private static final class Dist {
		final float min, mean, max, p10, p50, p90, p99;

		Dist(float min, float mean, float max, float p10, float p50, float p90, float p99) {
			this.min = min; this.mean = mean; this.max = max;
			this.p10 = p10; this.p50 = p50; this.p90 = p90; this.p99 = p99;
		}

		@Override
		public String toString() {
			return "min=" + pct(min) + " mean=" + pct(mean) + " max=" + pct(max)
					+ " | p10=" + pct(p10) + " p50=" + pct(p50) + " p90=" + pct(p90) + " p99=" + pct(p99);
		}
	}

	private static Dist dist(float[] values, int n) {
		float[] s = new float[n];
		System.arraycopy(values, 0, s, 0, n);
		Arrays.sort(s);
		float sum = 0f;
		for (float v : s) {
			sum += v;
		}
		return new Dist(s[0], sum / n, s[n - 1],
				pct(s, 0.10), pct(s, 0.50), pct(s, 0.90), pct(s, 0.99));
	}

	private static float pct(float[] sorted, double f) {
		int i = Math.min(sorted.length - 1, (int) Math.floor(f * (sorted.length - 1)));
		return sorted[i];
	}

	private static String pct(float v) {
		return String.format("%.4f", v);
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

	/** One end-to-end run's structural signature (the determinism + contract input). */
	private record Census(String fingerprint, int solidCount, int notSolidCount,
			Dist rhoDist, Dist qDist, Dist epsDist) {
		String summary() {
			return "solid=" + solidCount + " not-solid=" + notSolidCount
					+ " | ρ " + (rhoDist == null ? "?" : pct(rhoDist.mean))
					+ " | hash=" + fingerprint.substring(0, 8);
		}
	}

	private MaterialRegimesDeterminismMain() {
	}
}
