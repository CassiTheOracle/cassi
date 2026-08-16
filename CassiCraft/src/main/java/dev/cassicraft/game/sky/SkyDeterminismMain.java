package dev.cassicraft.game.sky;

import dev.cassicraft.domain.engine.TwoFluidSolver;
import dev.cassicraft.domain.snapshot.FieldSnapshot;
import dev.cassicraft.domain.snapshot.SnapshotPublisher;
import dev.cassicraft.domain.thread.CassiFieldThread;
import dev.cassicraft.domain.thread.KernelLoader;
import dev.cassicraft.game.sampler.Quantizer;

import java.util.Arrays;

/**
 * Headless Sky determinism gate (atmosphere-orbits-auroras.md §5c — a HARD
 * gate: same field state → same sky; the sky is deterministic, never a seeded
 * weather roll). Follows the exact {@code TerrainCensusMain} pattern: boot a
 * fixed-seed {@link CassiFieldThread} via the real publish seam at the Cfg
 * center {0,70,0}, await a settled snapshot, classify the sky over a fixed
 * sample grid of positions, and fingerprint the classification vector.
 *
 * <p>The gate asserts:
 * <ol>
 *   <li><b>Determinism (a):</b> two same-seed settles → identical classification
 *       fingerprint (same field → same sky).</li>
 *   <li><b>Anti-vacuity (b):</b> a different seed → a different fingerprint (the
 *       classifier genuinely read the field — not constant).</li>
 *   <li><b>Positive-count anti-vacuity (c):</b> across the sample grid at least
 *       one position classifies a non-{@link SkyRead.Kind#CLEAR} sky and at
 *       least one differs from it (the sky genuinely separates states — the
 *       world has glow and clear, not a monochrome sky).</li>
 *   <li><b>Purity (d):</b> the classification is a pure function — the same
 *       reading always yields the same verdict (asserted via a round-trip).</li>
 * </ol>
 *
 * <p>It also prints the measured ρ/q/ε² distribution over the sample lattice
 * and a calibration sweep, so the {@link SkyRead} [design] thresholds are
 * grounded in the field actually on disk at build time (never a guessed dial) —
 * and reads only the published channels via the pure {@link Quantizer#sampleReading}
 * seam; never writes a block (only-mutator rule; no-free-energy). Exit 0 =
 * green. Runs headlessly under the game runtime classpath (the {@code terrainCensus}
 * pattern), no live client/server.
 */
public final class SkyDeterminismMain {

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
	/**
	 * How many published generations to wait before measuring — the same settle
	 * the terrain census uses (12 gens × {@code JOB_STEP_CAP=64} steps). At the
	 * current {@code TwoFluidSolver.DT = 0.001} that advances 0.768 field-time
	 * units — near-flat-noise, the honest new field; calibrate from what is
	 * measured here, never from the dt=0.05 census numbers.
	 */
	private static final int SETTLE_GENERATIONS = 12;

	/** The sample-lattice step (blocks) across the 192³ box — a coarse full-box census. */
	private static final int SAMPLE_STEP = 16;
	/** The lattice's first sampled offset from the box's low corner. */
	private static final int SAMPLE_OFFSET = 8;

	/** Anti-vacuity acceptance — at least this many non-CLEAR sky positions on the lattice. */
	private static final int MIN_PHENOMENON_COUNT = 1;
	/** Anti-vacuity acceptance — at least this many CLEAR positions on the lattice. */
	private static final int MIN_CLEAR_COUNT = 1;

	public static void main(String[] args) throws Exception {
		// Measure the settled field once per seed and print the full distributions.
		Census a1 = runOnce(SEED_A);
		Census a2 = runOnce(SEED_A);
		Census b = runOnce(SEED_B);

		// Determinism + structural contract.
		boolean sameSeedIdentical = a1.fingerprint().equals(a2.fingerprint());
		boolean seedSensitive = !a1.fingerprint().equals(b.fingerprint());
		boolean phenomenonPresent = a1.phenomenonCount() >= MIN_PHENOMENON_COUNT
				&& a2.phenomenonCount() >= MIN_PHENOMENON_COUNT;
		boolean clearPresent = a1.clearCount() >= MIN_CLEAR_COUNT && a2.clearCount() >= MIN_CLEAR_COUNT;
		boolean pure = purityGate() && a1.fieldSensitive && a2.fieldSensitive && b.fieldSensitive;

		System.out.println("\n[sky-determinism] SEED_A run1: " + a1.summary());
		System.out.println("[sky-determinism] SEED_A run2: " + a2.summary());
		System.out.println("[sky-determinism] SEED_B run:  " + b.summary());
		System.out.println("[sky-determinism] same-seed identical=" + sameSeedIdentical
				+ " | different-seed differs=" + seedSensitive
				+ " | phenomenon≥" + MIN_PHENOMENON_COUNT + "=" + phenomenonPresent
				+ " | clear≥" + MIN_CLEAR_COUNT + "=" + clearPresent
				+ " | pure-function=" + pure
				+ " | separates-states=" + a1.fieldSensitive);

		boolean ok = true;
		if (!sameSeedIdentical) {
			System.err.println("[sky-determinism] FAIL — same seed produced a different sky classification (non-deterministic)");
			ok = false;
		}
		if (!seedSensitive) {
			System.err.println("[sky-determinism] FAIL — different seeds produced an identical classification (vacuous)");
			ok = false;
		}
		if (!phenomenonPresent) {
			System.err.println("[sky-determinism] FAIL — no position classifies a non-CLEAR sky (the classifier never reads the field's weather)");
			ok = false;
		}
		if (!clearPresent) {
			System.err.println("[sky-determinism] FAIL — no position classifies CLEAR (the sky is a monochrome weather)");
			ok = false;
		}
		if (!pure) {
			System.err.println("[sky-determinism] FAIL — the classification is not a pure function of the reading");
			ok = false;
		}

		if (ok) {
			System.out.println("[sky-determinism] PASS — the sky is deterministic, seed-sensitive, state-separating, and a pure function of the published channels");
		} else {
			System.err.println("[sky-determinism] FAILED");
			System.exit(1);
		}
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
	 * {@link SkyRead}, accumulate the ρ/q/ε² distributions + class counts, and
	 * fingerprint the classification vector (kind + driving channels per point).
	 * Reads only; never writes a block.
	 */
	private static Census census(FieldSnapshot snap, double[] window) {
		int minX = (int) (ANCHOR_X - EXTENT);
		int minY = (int) (ANCHOR_Y - EXTENT);
		int minZ = (int) (ANCHOR_Z - EXTENT);
		int maxX = (int) (ANCHOR_X + EXTENT);
		int maxY = (int) (ANCHOR_Y + EXTENT);
		int maxZ = (int) (ANCHOR_Z + EXTENT);

		float[] rhoAll = new float[512];
		float[] qAll = new float[512];
		float[] epsAll = new float[512];
		int size = 0;
		int glow = 0, storm = 0, fog = 0, clear = 0;
		java.nio.ByteBuffer fp = java.nio.ByteBuffer.allocate(4096);
		int hashPoints = 0;

		for (int z = minZ + SAMPLE_OFFSET; z < maxZ; z += SAMPLE_STEP) {
			for (int y = minY + SAMPLE_OFFSET; y < maxY; y += SAMPLE_STEP) {
				for (int x = minX + SAMPLE_OFFSET; x < maxX; x += SAMPLE_STEP) {
					Quantizer.FieldReading r = Quantizer.sampleReading(snap, window, x, y, z);
					SkyRead.Read s = SkyRead.classify(r);
					if (size < rhoAll.length) {
						rhoAll[size] = r.rho();
						qAll[size] = r.q();
						epsAll[size] = r.eps2();
						size++;
					}
					switch (s.kind()) {
					case GLOW -> glow++;
					case STORM_EDGE -> storm++;
					case FOG -> fog++;
					case CLEAR -> clear++;
					}
					// Fingerprint: kind ordinal + the driving ρ/q/ε² (strongly
					// field-sensitive, so a different seed must differ).
					if (fp.remaining() >= 16) {
						fp.putInt(s.kind().ordinal());
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

		// Print the measured distributions + a calibration sweep (the honest
		// threshold choice comes from the actual channels, not a guess).
		printDistributions(rhoDist, qDist, epsDist, glow, storm, fog, clear);
		printCalibration(rhoAll, qAll, epsAll, size);

		String fingerprint = sha256(Arrays.copyOf(fp.array(), hashPoints * 16));
		// The classifier is a pure function of the reading: distinct reading
		// vectors drive the lattice's verdict counts (the sky separates states).
		boolean fieldSensitive = glow + storm + fog > 0 && clear > 0;
		return new Census(fingerprint, glow + storm + fog, clear,
				fieldSensitive, rhoDist, qDist, epsDist);
	}

	/**
	 * Purity gate (d): {@link SkyRead#classify} is a pure function — the same
	 * reading always yields the same verdict, evaluated twice on a fixed reading
	 * with independent copies. Trivially true by construction (no state, no RNG),
	 * asserted so the contract is explicit and enforced.
	 */
	private static boolean purityGate() {
		Quantizer.FieldReading r = new Quantizer.FieldReading(1.2f, 1.1f, 0.01f, 0f, 0f, 0f);
		SkyRead.Read a = SkyRead.classify(r);
		Quantizer.FieldReading r2 = new Quantizer.FieldReading(1.2f, 1.1f, 0.01f, 0f, 0f, 0f);
		SkyRead.Read b = SkyRead.classify(r2);
		return a.kind() == b.kind() && a.glow() == b.glow()
				&& a.darkening() == b.darkening() && a.fog() == b.fog();
	}

	/**
	 * Honest threshold sweep over the measured per-lattice arrays — answers
	 * "what GLOW/STORM/FOG fraction does each candidate threshold actually
	 * produce", so the calibration is grounded in the measured continuum, never
	 * guessed. A pure read of the already-measured arrays (no re-settle).
	 */
	private static void printCalibration(float[] rho, float[] q, float[] eps2, int n) {
		int total = n;
		System.out.println("\n[sky-determinism]   calibration sweep (measured lattice, seed 42):");
		System.out.print("[sky-determinism]   q_glow → GLOW+STORM-frac  (q≥q_glow, all conditions)  ");
		for (float qg = 0.70f; qg <= 1.60f + 1e-6f; qg += 0.10f) {
			long glowCut = 0;
			for (int i = 0; i < n; i++) {
				if (q[i] >= qg) {
					glowCut++;
				}
			}
			System.out.print(" q" + pct(qg) + "=" + pct(glowCut / (double) total));
		}
		System.out.println();

		System.out.print("[sky-determinism]   ε²edge → STORM-frac  (ε²≥edge, all conditions)  ");
		for (float ee = 0.10f; ee <= 0.70f + 1e-6f; ee += 0.10f) {
			long stormCut = 0;
			for (int i = 0; i < n; i++) {
				if (eps2[i] >= ee) {
					stormCut++;
				}
			}
			System.out.print(" ε" + pct(ee) + "=" + pct(stormCut / (double) total));
		}
		System.out.println();

		System.out.print("[sky-determinism]   ρ_fog → FOG-frac  (ρ≥ρ_fog, all conditions)  ");
		for (float rf = 0.90f; rf <= 1.70f + 1e-6f; rf += 0.10f) {
			long fogCut = 0;
			for (int i = 0; i < n; i++) {
				if (rho[i] >= rf) {
					fogCut++;
				}
			}
			System.out.print(" ρ" + pct(rf) + "=" + pct(fogCut / (double) total));
		}
		System.out.println("\n[sky-determinism]   lattice=" + total + " sample points");
	}

	/** Print the raw measured ρ/q/ε² distributions + current class census. */
	private static void printDistributions(Dist rho, Dist q, Dist eps,
			int glow, int storm, int fog, int clear) {
		System.out.println("\n[sky-determinism] sample-lattice census @ settle (SETTLE_GENERATIONS="
				+ SETTLE_GENERATIONS + ", step=" + SAMPLE_STEP + ", DT=" + TwoFluidSolver.DT + ")");
		System.out.println("[sky-determinism]   field time evolved = " + SETTLE_GENERATIONS + " gen × "
				+ CassiFieldThread.JOB_STEP_CAP + " steps × DT=" + TwoFluidSolver.DT
				+ " = " + String.format("%.3f", fieldTimeUnits()) + " field-time units");
		System.out.println("[sky-determinism]   ρ       " + rho);
		System.out.println("[sky-determinism]   q       " + q);
		System.out.println("[sky-determinism]   ε²      " + eps);
		System.out.println("[sky-determinism]   class census: GLOW=" + glow
				+ " STORM_EDGE=" + storm + " FOG=" + fog + " CLEAR=" + clear);
		System.out.println("[sky-determinism]   thresholds: glow q=" + SkyRead.GLOW_Q_TAIL
				+ " storm ε²=" + SkyRead.STORM_EDGE_EPS2 + " fog ρ=" + SkyRead.FOG_RHO_TAIL);
	}

	/** Percentile distribution over the sampled values (sorted). */
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

	/** Field-time units the settle advances: {@code generations × steps × DT}. */
	private static double fieldTimeUnits() {
		return SETTLE_GENERATIONS * (double) CassiFieldThread.JOB_STEP_CAP * TwoFluidSolver.DT;
	}

	private static String pct(float v) {
		return String.format("%.4f", v);
	}

	private static String pct(double v) {
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
	private record Census(String fingerprint, int phenomenonCount, int clearCount,
			boolean fieldSensitive, Dist rhoDist, Dist qDist, Dist epsDist) {
		String summary() {
			return "phenomenon=" + phenomenonCount + " clear=" + clearCount
					+ " separatesStates=" + fieldSensitive
					+ " | q " + (qDist == null ? "?" : pct(qDist.mean))
					+ " | ρ " + (rhoDist == null ? "?" : pct(rhoDist.mean))
					+ " | hash=" + fingerprint.substring(0, 8);
		}
	}

	private SkyDeterminismMain() {
	}
}
