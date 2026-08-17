package dev.cassicraft.game.rain;

import dev.cassicraft.domain.engine.TwoFluidSolver;
import dev.cassicraft.domain.snapshot.FieldSnapshot;
import dev.cassicraft.domain.snapshot.SnapshotPublisher;
import dev.cassicraft.domain.thread.CassiFieldThread;
import dev.cassicraft.domain.thread.KernelLoader;
import dev.cassicraft.game.sampler.Quantizer;

import java.util.Arrays;

/**
 * Headless Rain determinism gate (the-rain.md §7c — a HARD gate: same window,
 * same field state → same rain; the fall is deterministic, never a seeded
 * weather roll). Follows the exact {@code TerrainCensusMain} pattern: boot a
 * fixed-seed {@link CassiFieldThread} via the real publish seam at the Cfg
 * center {0,70,0}, await a settled snapshot, classify the weather over a fixed
 * sample grid of positions, and fingerprint the classification vector.
 *
 * <p>The gate asserts:
 * <ol>
 *   <li><b>Measurement determinism (a):</b> two censuses of the <b>same</b>
 *       settled field → identical classification fingerprint. The two same-seed
 *       arms share <b>one</b> settle — the lattice census is a pure read of the
 *       published snapshot (no mutation) — so the run-2 arm re-measures the same
 *       frozen snapshot and must equal run-1. Settle determinism is not re-proved
 *       here; it is hard-pinned byte-identically by the domainHarness gate (and
 *       by every mutating gate that still boots fresh).</li>
 *   <li><b>Anti-vacuity (b):</b> a different seed → a different fingerprint (the
 *       classifier genuinely read the field — not constant).</li>
 *   <li><b>Positive-count anti-vacuity (c):</b> across the sample grid at least
 *       one position classifies {@link RainRead.Weather#RAIN} and at least one
 *       classifies NOT-RAIN (the classifier is not constant — it separates states).</li>
 *   <li><b>Purity (d):</b> the classification is a pure function — the same
 *       reading always yields the same verdict (asserted via a round-trip).</li>
 * </ol>
 *
 * <p>It also prints the measured q/ε² distribution over the sample lattice and a
 * calibration sweep, so the {@link RainRead} [design] thresholds are grounded in
 * the field actually on disk at build time (never a guessed dial) — and reads
 * only the published channels via the pure {@link Quantizer#sampleReading}
 * seam; never writes a block (only-mutator rule). Exit 0 = green. Runs headlessly
 * under the game runtime classpath (the {@code terrainCensus} pattern), no live
 * client/server.
 */
public final class RainDeterminismMain {

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

	/** Anti-vacuity acceptance — at least this many RAIN positions on the lattice. */
	private static final int MIN_RAIN_COUNT = 1;
	/** Anti-vacuity acceptance — at least this many NOT-RAIN positions on the lattice. */
	private static final int MIN_NOT_RAIN_COUNT = 1;

	public static void main(String[] args) throws Exception {
		// The two same-seed arms share ONE settle: boot+settle SEED_A once, run
		// the pure-read census twice from the same frozen snapshot, and assert the
		// fingerprints match (measurement determinism). The seed-B arm boots a
		// fresh settle for seed sensitivity. The a2 census is re-measured quietly
		// (identical result to a1 — the same frozen field), so the report prints once.
		Settled sa = bootAndSettle(SEED_A);
		Census a1 = measureOn(sa);
		Census a2 = measureOnQuiet(sa);
		Census b = runOnce(SEED_B);

		// Determinism + structural contract.
		boolean sameSeedIdentical = a1.fingerprint().equals(a2.fingerprint());
		boolean seedSensitive = !a1.fingerprint().equals(b.fingerprint());
		boolean rainPresent = a1.rainCount() >= MIN_RAIN_COUNT && a2.rainCount() >= MIN_RAIN_COUNT;
		boolean notRainPresent = a1.notRainCount() >= MIN_NOT_RAIN_COUNT
				&& a2.notRainCount() >= MIN_NOT_RAIN_COUNT;
		boolean pure = purityGate() && a1.fieldSensitive && a2.fieldSensitive && b.fieldSensitive;

		System.out.println("\n[rain-determinism] SEED_A run1: " + a1.summary());
		System.out.println("[rain-determinism] SEED_A run2: " + a2.summary());
		System.out.println("[rain-determinism] SEED_B run:  " + b.summary());
		System.out.println("[rain-determinism] same-seed identical=" + sameSeedIdentical
				+ " | different-seed differs=" + seedSensitive
				+ " | rain≥" + MIN_RAIN_COUNT + "=" + rainPresent
				+ " | not-rain≥" + MIN_NOT_RAIN_COUNT + "=" + notRainPresent
				+ " | pure-function=" + pure
				+ " | field-sensitive(distinct-sample-reads)=" + a1.fieldSensitive);

		boolean ok = true;
		if (!sameSeedIdentical) {
			System.err.println("[rain-determinism] FAIL — same seed produced a different rain classification (non-deterministic)");
			ok = false;
		}
		if (!seedSensitive) {
			System.err.println("[rain-determinism] FAIL — different seeds produced an identical classification (vacuous)");
			ok = false;
		}
		if (!rainPresent) {
			System.err.println("[rain-determinism] FAIL — no position classifies RAIN (the classifier never reads the gentle fall)");
			ok = false;
		}
		if (!notRainPresent) {
			System.err.println("[rain-determinism] FAIL — no position classifies NOT-RAIN (the classifier is constant)");
			ok = false;
		}
		if (!pure) {
			System.err.println("[rain-determinism] FAIL — the classification is not a pure function of the reading");
			ok = false;
		}

		if (ok) {
			System.out.println("[rain-determinism] PASS — the rain is deterministic, field-sensitive, state-separating, and a pure function of the published channels");
		} else {
			System.err.println("[rain-determinism] FAILED");
			System.exit(1);
		}
	}

	/** Boot a settled field, classify the sample lattice, and return the structural signature. */
	private static Census runOnce(long seed) throws InterruptedException {
		return measureOn(bootAndSettle(seed));
	}

	/** Boot the field thread, await the settled snapshot, capture the frozen
	 * (snapshot + window-center) state, and close the worker. The returned
	 * {@link Settled} is a pure immutable datum — safe to re-read. */
	private static Settled bootAndSettle(long seed) throws InterruptedException {
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
			return new Settled(snap, window);
		} finally {
			worker.close();
		}
	}

	/** A full, printing census pass over a settled snapshot (the first arm + seed-B). */
	private static Census measureOn(Settled s) {
		return census(s.snap(), s.windowCenter(), false);
	}

	/** A quiet second census pass over the same frozen snapshot (identical result,
	 * no duplicate distribution print — the report is printed once from arm a1). */
	private static Census measureOnQuiet(Settled s) {
		return census(s.snap(), s.windowCenter(), true);
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
	 * {@link RainRead}, accumulate the q/ε² distributions + class counts, and
	 * fingerprint the classification vector (kind + driving q/ε² per point).
	 * Reads only; never writes a block.
	 */
	private static Census census(FieldSnapshot snap, double[] window, boolean quiet) {
		int minX = (int) (ANCHOR_X - EXTENT);
		int minY = (int) (ANCHOR_Y - EXTENT);
		int minZ = (int) (ANCHOR_Z - EXTENT);
		int maxX = (int) (ANCHOR_X + EXTENT);
		int maxY = (int) (ANCHOR_Y + EXTENT);
		int maxZ = (int) (ANCHOR_Z + EXTENT);

		float[] qAll = new float[512];
		float[] epsAll = new float[512];
		int size = 0;
		int rain = 0, noRain = 0, flood = 0, storm = 0;
		java.nio.ByteBuffer fp = java.nio.ByteBuffer.allocate(4096);
		int hashPoints = 0;

		for (int z = minZ + SAMPLE_OFFSET; z < maxZ; z += SAMPLE_STEP) {
			for (int y = minY + SAMPLE_OFFSET; y < maxY; y += SAMPLE_STEP) {
				for (int x = minX + SAMPLE_OFFSET; x < maxX; x += SAMPLE_STEP) {
					Quantizer.FieldReading r = Quantizer.sampleReading(snap, window, x, y, z);
					RainRead.WeatherRead w = RainRead.classify(r);
					if (size < qAll.length) {
						qAll[size] = r.q();
						epsAll[size] = r.eps2();
						size++;
					}
					switch (w.kind()) {
					case RAIN -> rain++;
					case NO_RAIN -> noRain++;
					case FLOODS_BEGINNING -> flood++;
					case STORM_FRONT -> storm++;
					}
					// Fingerprint: kind ordinal + the driving q and ε² (strongly
					// field-sensitive, so a different seed must differ).
					if (fp.remaining() >= 12) {
						fp.putInt(w.kind().ordinal());
						fp.putFloat(r.q());
						fp.putFloat(r.eps2());
						hashPoints++;
					}
				}
			}
		}

		Dist qDist = dist(qAll, size);
		Dist epsDist = dist(epsAll, size);

		// Print the measured distributions + a calibration sweep (the honest
		// threshold choice comes from the actual channels, not a guess). The shared
		// second arm (same snapshot) is quiet — its report would be byte-identical.
		if (!quiet) {
			printDistributions(qDist, epsDist, rain, noRain, flood, storm);
		}

		String fingerprint = sha256(Arrays.copyOf(fp.array(), hashPoints * 12));
		// The classifier is a pure function of the reading: distinct reading
		// vectors drive the lattice's verdict counts (field-sensitivity).
		boolean fieldSensitive = rain + flood + storm > 0 && noRain > 0;
		return new Census(fingerprint, rain, noRain, fieldSensitive, qDist, epsDist);
	}

	/**
	 * Purity gate (d): {@link RainRead#classify} is a pure function — the same
	 * reading always yields the same verdict, evaluated twice on a fixed reading
	 * with independent copies. Trivially true by construction (no state, no RNG),
	 * asserted so the contract is explicit and enforced.
	 */
	private static boolean purityGate() {
		Quantizer.FieldReading r = new Quantizer.FieldReading(1.0f, 0.9f, 0.01f, 0f, 0f, 0f);
		RainRead.WeatherRead a = RainRead.classify(r);
		Quantizer.FieldReading r2 = new Quantizer.FieldReading(1.0f, 0.9f, 0.01f, 0f, 0f, 0f);
		RainRead.WeatherRead b = RainRead.classify(r2);
		return a.kind() == b.kind() && a.wetness() == b.wetness()
				&& a.floodDistance() == b.floodDistance();
	}

	/** Percentile distribution over the sampled q values (sorted). */
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

	private static void printDistributions(Dist q, Dist eps,
			int rain, int noRain, int flood, int storm) {
		System.out.println("\n[rain-determinism] sample-lattice census @ settle (SETTLE_GENERATIONS="
				+ SETTLE_GENERATIONS + ", step=" + SAMPLE_STEP + ", DT=" + TwoFluidSolver.DT + ")");
		System.out.println("[rain-determinism]   field time evolved = " + SETTLE_GENERATIONS + " gen × "
				+ CassiFieldThread.JOB_STEP_CAP + " steps × DT=" + TwoFluidSolver.DT
				+ " = " + String.format("%.3f", fieldTimeUnits()) + " field-time units");
		System.out.println("[rain-determinism]   q       " + q);
		System.out.println("[rain-determinism]   ε²      " + eps);
		System.out.println("[rain-determinism]   class census: RAIN=" + rain
				+ " NO_RAIN=" + noRain + " FLOODS_BEGINNING=" + flood + " STORM_FRONT=" + storm);
		System.out.println("[rain-determinism]   thresholds: band floor=" + RainRead.ENRICHING_BAND_FLOOR
				+ " surfeit=" + RainRead.SURFEIT_THRESHOLD + " storm ε²=" + RainRead.STORM_FRONT_EPS2);
	}

	/** Field-time units the settle advances: {@code generations × steps × DT}. */
	private static double fieldTimeUnits() {
		return SETTLE_GENERATIONS * (double) CassiFieldThread.JOB_STEP_CAP * TwoFluidSolver.DT;
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
	private record Census(String fingerprint, int rainCount, int notRainCount,
			boolean fieldSensitive, Dist qDist, Dist epsDist) {
		String summary() {
			return "rain=" + rainCount + " noRain=" + notRainCount
					+ " fieldSensitive=" + fieldSensitive
					+ " | q " + (qDist == null ? "?" : pct(qDist.mean))
					+ " | hash=" + fingerprint.substring(0, 8);
		}
	}

	/** The frozen settled field (immutable snapshot + its window center) shared
	 * by the two same-seed measurement arms. */
	private record Settled(FieldSnapshot snap, double[] windowCenter) {
	}

	private RainDeterminismMain() {
	}
}
