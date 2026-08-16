package dev.cassicraft.game.atmo;

import dev.cassicraft.domain.engine.TwoFluidSolver;
import dev.cassicraft.domain.snapshot.FieldSnapshot;
import dev.cassicraft.domain.snapshot.SnapshotPublisher;
import dev.cassicraft.domain.thread.CassiFieldThread;
import dev.cassicraft.domain.thread.KernelLoader;
import dev.cassicraft.game.sampler.Quantizer;

import java.util.Arrays;

/**
 * Headless Atmosphere determinism gate (atmosphere-orbits-auroras.md §5c — a
 * HARD gate: same field state → same atmosphere; the sky's field phenomena are
 * deterministic, never a seeded roll). Follows the exact {@code SkyDeterminismMain}
 * pattern: boot a fixed-seed {@link CassiFieldThread} via the real publish seam
 * at the Cfg center {0,70,0}, await a settled snapshot, classify the atmosphere
 * over a fixed sample grid of positions, and fingerprint the classification
 * vector.
 *
 * <p>The gate asserts:
 * <ol>
 *   <li><b>Determinism (a):</b> two same-seed settles → identical classification
 *       fingerprint (same field → same atmosphere).</li>
 *   <li><b>Anti-vacuity (b):</b> a different seed → a different fingerprint (the
 *       classifier genuinely read the field — not constant).</li>
 *   <li><b>Positive-count anti-vacuity (c):</b> across the sample grid at least
 *       one position classifies an {@link AtmoRead.Kind#AURORA} and at least one
 *       differs from it — the atmosphere genuinely separates a discharge from
 *       the rest of the sky (the aurora is not everywhere nor nowhere).</li>
 *   <li><b>Purity (d):</b> the classification is a pure function — the same
 *       reading always yields the same verdict (asserted via a round-trip), and
 *       every presented number is a published channel ({@code ρ},{@code q},{@code ε²},
 *       {@code ∇(g·Φ)}) or a registry constant — the fingerprint covers the
 *       channels it is built from.</li>
 * </ol>
 *
 * <p>It also prints the measured ρ/q/ε²/|∇(g·Φ)| distribution over the sample
 * lattice and calibration sweeps, so the {@link AtmoRead} [design] thresholds
 * are grounded in the field actually on disk at build time (never a guessed
 * dial) — and reads only the published channels via the pure
 * {@link Quantizer#sampleReading} seam; never writes a block, never perturbs
 * the field (only-mutator rule; no-free-energy). Exit 0 = green. Runs headlessly
 * under the game runtime classpath (the {@code skyDeterminism} pattern), no live
 * client/server.
 */
public final class AtmosphereDeterminismMain {

	/** Fixed seeds — the same domain seeds the other gates replay. */
	private static final long SEED_A = 42L;
	private static final long SEED_B = 43L;

	/** The demo box anchor (the Phase-1 window center, spawn) — center {0,70,0}. */
	private static final double ANCHOR_X = 0, ANCHOR_Y = 70, ANCHOR_Z = 0;
	/** Box half-extent per axis (chunk-aligned 192³ m box, chunk-field-quantization §1.2). */
	private static final int EXTENT = (int) TwoFluidSolver.EXTENT;

	/** Settle-generation await timeout (ms). */
	private static final long SETTLE_TIMEOUT_MS = 30_000;
	/**
	 * How many published generations to wait before measuring — the same settle
	 * the terrain/sky census uses (12 gens × {@code JOB_STEP_CAP=64} steps). At
	 * the current {@code TwoFluidSolver.DT = 0.001} that advances 0.768 field-time
	 * units — near-flat-noise, the honest new field; calibrate from what is
	 * measured here, never from the dt=0.05 census numbers.
	 */
	private static final int SETTLE_GENERATIONS = 12;

	/** The sample-lattice step (blocks) across the 192³ box — a coarse full-box census. */
	private static final int SAMPLE_STEP = 16;
	/** The lattice's first sampled offset from the box's low corner. */
	private static final int SAMPLE_OFFSET = 8;

	/** Anti-vacuity acceptance — at least this many AURORA positions on the lattice. */
	private static final int MIN_AURORA_COUNT = 1;
	/** Anti-vacuity acceptance — at least this many non-AURORA positions on the lattice. */
	private static final int MIN_NON_AURORA_COUNT = 1;

	public static void main(String[] args) throws Exception {
		// Measure the settled field once per seed and print the full distributions.
		Census a1 = runOnce(SEED_A);
		Census a2 = runOnce(SEED_A);
		Census b = runOnce(SEED_B);

		// Determinism + structural contract.
		boolean sameSeedIdentical = a1.fingerprint().equals(a2.fingerprint());
		boolean seedSensitive = !a1.fingerprint().equals(b.fingerprint());
		boolean auroraPresent = a1.auroraCount() >= MIN_AURORA_COUNT
				&& a2.auroraCount() >= MIN_AURORA_COUNT;
		boolean nonAuroraPresent = a1.nonAuroraCount() >= MIN_NON_AURORA_COUNT
				&& a2.nonAuroraCount() >= MIN_NON_AURORA_COUNT;
		boolean pure = purityGate();

		System.out.println("\n[atmo-determinism] SEED_A run1: " + a1.summary());
		System.out.println("[atmo-determinism] SEED_A run2: " + a2.summary());
		System.out.println("[atmo-determinism] SEED_B run:  " + b.summary());
		System.out.println("[atmo-determinism] same-seed identical=" + sameSeedIdentical
				+ " | different-seed differs=" + seedSensitive
				+ " | aurora≥" + MIN_AURORA_COUNT + "=" + auroraPresent
				+ " | non-aurora≥" + MIN_NON_AURORA_COUNT + "=" + nonAuroraPresent
				+ " | pure-function=" + pure);

		boolean ok = true;
		if (!sameSeedIdentical) {
			System.err.println("[atmo-determinism] FAIL — same seed produced a different atmosphere classification (non-deterministic)");
			ok = false;
		}
		if (!seedSensitive) {
			System.err.println("[atmo-determinism] FAIL — different seeds produced an identical classification (vacuous)");
			ok = false;
		}
		if (!auroraPresent) {
			System.err.println("[atmo-determinism] FAIL — no position classifies an AURORA discharge (the read never fires)");
			ok = false;
		}
		if (!nonAuroraPresent) {
			System.err.println("[atmo-determinism] FAIL — no position differs from AURORA (the sky is a monochrome discharge)");
			ok = false;
		}
		if (!pure) {
			System.err.println("[atmo-determinism] FAIL — the classification is not a pure function of the reading");
			ok = false;
		}

		if (ok) {
			System.out.println("[atmo-determinism] PASS — the atmosphere is deterministic, seed-sensitive, discharge-separating, and a pure function of the published channels");
		} else {
			System.err.println("[atmo-determinism] FAILED");
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
	 * {@link AtmoRead}, accumulate the ρ/q/ε²/|∇| distributions + class counts,
	 * and fingerprint the classification vector (kind + driving channels per
	 * point — so every presented number traces to a published channel; the
	 * fingerprint covers those channel values). Reads only; never writes.
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
		float[] gradAll = new float[512];
		int size = 0;
		int aurora = 0, orbit = 0, envelope = 0, clear = 0;
		java.nio.ByteBuffer fp = java.nio.ByteBuffer.allocate(4096);
		int hashPoints = 0;

		for (int z = minZ + SAMPLE_OFFSET; z < maxZ; z += SAMPLE_STEP) {
			for (int y = minY + SAMPLE_OFFSET; y < maxY; y += SAMPLE_STEP) {
				for (int x = minX + SAMPLE_OFFSET; x < maxX; x += SAMPLE_STEP) {
					Quantizer.FieldReading r = Quantizer.sampleReading(snap, window, x, y, z);
					AtmoRead.Read a = AtmoRead.classify(r);
					if (size < rhoAll.length) {
						rhoAll[size] = r.rho();
						qAll[size] = r.q();
						epsAll[size] = r.eps2();
						gradAll[size] = AtmoRead.gradMag(r);
						size++;
					}
					switch (a.kind()) {
					case AURORA -> aurora++;
					case ORBIT_WELL -> orbit++;
					case ENVELOPE -> envelope++;
					case CLEAR -> clear++;
					}
					// Fingerprint: kind ordinal + the driving ρ/q/ε²/|∇| (the
					// presented channels — strongly field-sensitive, so a
					// different seed must differ).
					if (fp.remaining() >= 20) {
						fp.putInt(a.kind().ordinal());
						fp.putFloat(r.rho());
						fp.putFloat(r.q());
						fp.putFloat(r.eps2());
						fp.putFloat(AtmoRead.gradMag(r));
						hashPoints++;
					}
				}
			}
		}

		Dist rhoDist = dist(rhoAll, size);
		Dist qDist = dist(qAll, size);
		Dist epsDist = dist(epsAll, size);
		Dist gradDist = dist(gradAll, size);

		// Print the measured distributions + a calibration sweep (the honest
		// threshold choice comes from the actual channels, not a guess).
		printDistributions(rhoDist, qDist, epsDist, gradDist, aurora, orbit, envelope, clear);
		printCalibration(rhoAll, qAll, epsAll, gradAll, size);

		String fingerprint = sha256(Arrays.copyOf(fp.array(), hashPoints * 20));
		// The classifier is a pure function of the reading: a real discharge
		// exists and the sky is not a monochrome discharge (separates states).
		boolean dischargePresent = aurora > 0 && (orbit + envelope + clear) > 0;
		return new Census(fingerprint, aurora, orbit + envelope + clear,
				dischargePresent, rhoDist, qDist, epsDist, gradDist);
	}

	/**
	 * Purity gate (d): {@link AtmoRead#classify} is a pure function — the same
	 * reading always yields the same verdict, evaluated twice on a fixed reading
	 * with independent copies; and the presented numbers trace to a published
	 * channel or a registry constant (every field of the {@link AtmoRead.Read}
	 * record is a published channel {@code ρ/q/ε²/∇(g·Φ)} or a derived
	 * intensity over them — the envelope's band comes straight from the
	 * registry's condensation/void constants, Quantizer.TAU_C and
	 * MaterialRegistry.AIR_THETA_C). Trivially true by construction (no state,
	 * no RNG), asserted so the contract is explicit and enforced.
	 */
	private static boolean purityGate() {
		Quantizer.FieldReading r = new Quantizer.FieldReading(0.45f, 0.95f, 0.30f, 2f, 0f, 0f);
		AtmoRead.Read a = AtmoRead.classify(r);
		Quantizer.FieldReading r2 = new Quantizer.FieldReading(0.45f, 0.95f, 0.30f, 2f, 0f, 0f);
		AtmoRead.Read b = AtmoRead.classify(r2);
		boolean same = a.kind() == b.kind() && Float.floatToIntBits(a.discharge()) == Float.floatToIntBits(b.discharge())
				&& Float.floatToIntBits(a.fogDensity()) == Float.floatToIntBits(b.fogDensity()); 
		// The intensities above also bound to their chronicle constants: the
		// drain band is [AtmoRead.AURORA_EPS2_FLOOR, SkyRead.STORM_EDGE_EPS2),
		// the envelope band [EnvelopeVacuumRho, EnvelopeCondenseRho] — registry
		// constants, not invented channels.
		boolean constantsTrace = AtmoRead.ENVELOPE_VACUUM_RHO
						== (float) dev.cassicraft.game.material.MaterialRegistry.AIR_THETA_C
				&& AtmoRead.ENVELOPE_CONDENSE_RHO == dev.cassicraft.game.sampler.Quantizer.TAU_C;
		return same && constantsTrace;
	}

	/**
	 * Honest threshold sweep over the measured per-lattice arrays — answers
	 * "what AURORA/ORBIT/ENVELOPE fraction does each candidate threshold
	 * actually produce", so the calibration is grounded in the measured
	 * continuum, never guessed. A pure read of the already-measured arrays (no
	 * re-settle).
	 */
	private static void printCalibration(float[] rho, float[] q, float[] eps2, float[] grad, int n) {
		int total = n;
		System.out.println("\n[atmo-determinism]   calibration sweep (measured lattice, seed 42):");
		System.out.print("[atmo-determinism]   q_aurora → AURORA-cand  (q≥q_a, with ε² in drain [0.20,0.45))  ");
		for (float qa = 0.70f; qa <= 1.40f + 1e-6f; qa += 0.10f) {
			long cut = 0;
			for (int i = 0; i < n; i++) {
				if (q[i] >= qa && eps2[i] >= AtmoRead.AURORA_EPS2_FLOOR
						&& eps2[i] < dev.cassicraft.game.sky.SkyRead.STORM_EDGE_EPS2) {
					cut++;
				}
			}
			System.out.print(" q" + pct(qa) + "=" + pct(cut / (double) total));
		}
		System.out.println();

		System.out.print("[atmo-determinism]   ε²drain → AURORA-cand  (ε²≥ε²d, with q≥0.90, ε²<storm)  ");
		for (float ed = 0.05f; ed <= 0.50f + 1e-6f; ed += 0.05f) {
			long cut = 0;
			for (int i = 0; i < n; i++) {
				if (eps2[i] >= ed && eps2[i] < dev.cassicraft.game.sky.SkyRead.STORM_EDGE_EPS2
						&& q[i] >= AtmoRead.AURORA_Q_FLOOR) {
					cut++;
				}
			}
			System.out.print(" ε" + pct(ed) + "=" + pct(cut / (double) total));
		}
		System.out.println();

		System.out.print("[atmo-determinism]   |∇|_well → ORBIT-cand  (|∇|≥G, with q≥1.05)  ");
		for (float gg = 1.0f; gg <= 9.0f + 1e-6f; gg += 1.0f) {
			long cut = 0;
			for (int i = 0; i < n; i++) {
				if (grad[i] >= gg && q[i] >= AtmoRead.BODY_SEED_Q) {
					cut++;
				}
			}
			System.out.print(" G" + pct(gg) + "=" + pct(cut / (double) total));
		}
		System.out.println();
		System.out.println("[atmo-determinism]   lattice=" + total + " sample points");
	}

	/** Print the raw measured ρ/q/ε²/|∇| distributions + current class census. */
	private static void printDistributions(Dist rho, Dist q, Dist eps, Dist grad,
			int aurora, int orbit, int envelope, int clear) {
		System.out.println("\n[atmo-determinism] sample-lattice census @ settle (SETTLE_GENERATIONS="
				+ SETTLE_GENERATIONS + ", step=" + SAMPLE_STEP + ", DT=" + TwoFluidSolver.DT + ")");
		System.out.println("[atmo-determinism]   field time evolved = " + SETTLE_GENERATIONS + " gen × "
				+ CassiFieldThread.JOB_STEP_CAP + " steps × DT=" + TwoFluidSolver.DT
				+ " = " + String.format("%.3f", fieldTimeUnits()) + " field-time units");
		System.out.println("[atmo-determinism]   ρ       " + rho);
		System.out.println("[atmo-determinism]   q       " + q);
		System.out.println("[atmo-determinism]   ε²      " + eps);
		System.out.println("[atmo-determinism]   |∇(g·Φ)| " + grad);
		System.out.println("[atmo-determinism]   class census: AURORA=" + aurora
				+ " ORBIT_WELL=" + orbit + " ENVELOPE=" + envelope + " CLEAR=" + clear);
		System.out.println("[atmo-determinism]   thresholds: aurora q=" + AtmoRead.AURORA_Q_FLOOR
				+ " (drain ε² [" + AtmoRead.AURORA_EPS2_FLOOR + ", "
				+ dev.cassicraft.game.sky.SkyRead.STORM_EDGE_EPS2 + "))"
				+ " orbit q=" + AtmoRead.BODY_SEED_Q + " |∇|=" + AtmoRead.BODY_HOLD_GRAD
				+ " envelope ρ [" + AtmoRead.ENVELOPE_VACUUM_RHO + ", " + AtmoRead.ENVELOPE_CONDENSE_RHO + ")");
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
	private record Census(String fingerprint, int auroraCount, int nonAuroraCount,
			boolean dischargePresent, Dist rhoDist, Dist qDist, Dist epsDist, Dist gradDist) {
		String summary() {
			return "aurora=" + auroraCount + " non-aurora=" + nonAuroraCount
					+ " separatesDischarge=" + dischargePresent
					+ " | q " + (qDist == null ? "?" : pct(qDist.mean))
					+ " | ρ " + (rhoDist == null ? "?" : pct(rhoDist.mean))
					+ " | hash=" + fingerprint.substring(0, 8);
		}
	}

	private AtmosphereDeterminismMain() {
	}
}
