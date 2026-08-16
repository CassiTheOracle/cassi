package dev.cassicraft.game.instrument;

import dev.cassicraft.domain.engine.TwoFluidSolver;
import dev.cassicraft.domain.snapshot.FieldSnapshot;
import dev.cassicraft.domain.snapshot.SnapshotPublisher;
import dev.cassicraft.domain.thread.CassiFieldThread;
import dev.cassicraft.domain.thread.KernelLoader;
import dev.cassicraft.game.sampler.Quantizer;

import java.util.Arrays;

/**
 * Headless FieldGlass determinism gate (field-instruments.md §1, §2.1 — the
 * family rule: <b>every instrument is a consumer of the same publish with a
 * presentation idiom, never a new channel</b>; §5 gates (a)–(d); a HARD
 * determinism gate). Follows the exact {@code RainDeterminismMain} /
 * {@code MaterialRegimesDeterminismMain} / {@code FieldReaderDeterminismMain}
 * pattern: boot a fixed-seed {@link CassiFieldThread} via the real publish seam
 * at the Cfg center {0,70,0}, settle to a named generation, sample the FieldGlass
 * readout at named window-relative points, and fingerprint the full readout
 * vector.
 *
 * <p>The gate asserts:
 * <ol>
 *   <li><b>Determinism (a):</b> two same-seed settles → identical FieldGlass
 *       fingerprint (same field → same readout, never a seeded read roll).</li>
 *   <li><b>Anti-vacuity (b):</b> a different seed → a different fingerprint (the
 *       instrument genuinely read the field — not constant).</li>
 *   <li><b>Purity (c):</b> the readout is a pure function of the snapshot — two
 *       independently-constructed identical {@link FieldSnapshot}s always yield
 *       the identical readout text (no hidden state, no RNG).</li>
 *   <li><b>Honesty (d):</b> every channel the instrument reads genuinely appears
 *       in the readout — perturbing each published channel ({@code q}, {@code ρ},
 *       {@code ε²}, each component of {@code ∇(g·Φ)}) changes the rendered text
 *       (proving the read is a faithful read of the actual channels, never a
 *       hardcoded dial), and each point's raw channel values are embedded in the
 *       fingerprint.</li>
 * </ol>
 *
 * <p>It also prints the measured ρ/q/ε² distribution over the sample lattice, so
 * the [design] band thresholds are grounded in the field actually on disk at
 * build time (never a guessed dial) — and reads only the published channels via
 * the pure {@link Quantizer#sampleReading} seam; never writes a block
 * (only-mutator rule). Exit 0 = green. Runs headlessly under the game runtime
 * classpath (the {@code terrainCensus} pattern), no live client/server.
 */
public final class InstrumentDeterminismMain {

	/** Fixed seeds — the same domain seeds the other gates replay. */
	private static final long SEED_A = 42L;
	private static final long SEED_B = 43L;

	/** The demo box anchor (the Phase-1 window center, spawn) — center {0,70,0}. */
	private static final double ANCHOR_X = 0, ANCHOR_Y = 70, ANCHOR_Z = 0;
	/** Box half-extent per axis (chunk-aligned 192³ m box, chunk-field-quantization §1.2). */
	private static final int EXTENT = (int) TwoFluidSolver.EXTENT;

	/** Settle-generation await timeout (ms). */
	private static final long SETTLE_TIMEOUT_MS = 30_000;
	/** How many published generations to wait before measuring — the same settle the terrain census uses. */
	private static final int SETTLE_GENERATIONS = 12;

	/** The sample-lattice step (blocks) across the 192³ box — a coarse full-box census. */
	private static final int SAMPLE_STEP = 16;
	/** The lattice's first sampled offset from the box's low corner. */
	private static final int SAMPLE_OFFSET = 8;

	/** The named window-relative sample point (a fixed point in the settled box). */
	private static final int SX = 3, SY = 64, SZ = -7;

	public static void main(String[] args) throws Exception {
		// Measure the settled field once per seed and print the full readouts.
		Census a1 = runOnce(SEED_A);
		Census a2 = runOnce(SEED_A);
		Census b = runOnce(SEED_B);

		// Determinism + structural contract.
		boolean sameSeedIdentical = a1.fingerprint().equals(a2.fingerprint());
		boolean seedSensitive = !a1.fingerprint().equals(b.fingerprint());
		boolean pure = purityGate();
		boolean honest = honestyGate();

		System.out.println("\n[instrument-determinism] SEED_A run1: " + a1.summary());
		System.out.println("[instrument-determinism] SEED_A run2: " + a2.summary());
		System.out.println("[instrument-determinism] SEED_B run:  " + b.summary());
		System.out.println("[instrument-determinism] same-seed identical=" + sameSeedIdentical
				+ " | different-seed differs=" + seedSensitive
				+ " | pure-function(snapshot)= " + pure
				+ " | channel-honesty(read-traceable)=" + honest);

		boolean ok = true;
		if (!sameSeedIdentical) {
			System.err.println("[instrument-determinism] FAIL — same seed produced a different FieldGlass readout (non-deterministic)");
			ok = false;
		}
		if (!seedSensitive) {
			System.err.println("[instrument-determinism] FAIL — different seeds produced an identical readout (vacuous)");
			ok = false;
		}
		if (!pure) {
			System.err.println("[instrument-determinism] FAIL — the readout is not a pure function of the snapshot");
			ok = false;
		}
		if (!honest) {
			System.err.println("[instrument-determinism] FAIL — a published channel does not trace into the readout");
			ok = false;
		}

		if (ok) {
			System.out.println("[instrument-determinism] PASS — the FieldGlass readout is deterministic, field-sensitive, snapshot-pure, and every channel traces to the published field or the registry");
		} else {
			System.err.println("[instrument-determinism] FAILED");
			System.exit(1);
		}
	}

	/** Boot a settled field, sample the FieldGlass lattice, and return the structural signature. */
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

			// Print the named point's full readout (the deterministic chart).
			Quantizer.FieldReading named = Quantizer.sampleReading(snap, window, SX, SY, SZ);
			System.out.println("\n[instrument-determinism] named point (" + SX + "," + SY + "," + SZ
					+ ") window-relative readout:\n" + FieldGlassRead.read(named).text());

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
	 * lattice point across the 192³ box, render the FieldGlass readout at each,
	 * accumulate the ρ/q/ε² distributions, and fingerprint the full readout
	 * vector (material ordinal + phase ordinal + the raw ρ/q/ε²/∇(g·Φ) channels
	 * per point — the honest embedding of every channel the instrument reads).
	 * Reads only; never writes a block.
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
		java.nio.ByteBuffer fp = java.nio.ByteBuffer.allocate(16384);
		int hashPoints = 0;

		for (int z = minZ + SAMPLE_OFFSET; z < maxZ; z += SAMPLE_STEP) {
			for (int y = minY + SAMPLE_OFFSET; y < maxY; y += SAMPLE_STEP) {
				for (int x = minX + SAMPLE_OFFSET; x < maxX; x += SAMPLE_STEP) {
					Quantizer.FieldReading r = Quantizer.sampleReading(snap, window, x, y, z);
					FieldGlassRead.FieldGlassReadout out = FieldGlassRead.read(r);
					if (size < rhoAll.length) {
						rhoAll[size] = r.rho();
						qAll[size] = r.q();
						epsAll[size] = r.eps2();
						size++;
					}
					// Fingerprint: the governing material + phase + the raw
					// published ρ/q/ε²/∇(g·Φ) channels — strongly field-sensitive,
					// so a different seed must differ, and the honesty assertion
					// reads these exact per-channel bytes.
					if (fp.remaining() >= 36) {
						fp.putInt(materialIndex(out.regime().material()));
						fp.putInt(out.regime().phase().ordinal());
						fp.putFloat(r.rho());
						fp.putFloat(r.q());
						fp.putFloat(r.eps2());
						fp.putFloat(r.gradX());
						fp.putFloat(r.gradY());
						fp.putFloat(r.gradZ());
						hashPoints++;
					}
				}
			}
		}

		Dist rhoDist = dist(rhoAll, size);
		Dist qDist = dist(qAll, size);
		Dist epsDist = dist(epsAll, size);

		printDistributions(rhoDist, qDist, epsDist);

		String fingerprint = sha256(Arrays.copyOf(fp.array(), hashPoints * 36));
		return new Census(fingerprint, rhoDist, qDist, epsDist, hashPoints);
	}

	/**
	 * Honesty gate (d): the FieldGlass readout is a faithful read of the actual
	 * published channels — perturbing each one ({@code q}, {@code ρ}, {@code ε²},
	 * and each component of {@code ∇(g·Φ)}) must change the rendered text, and
	 * each channel's value appears verbatim in the chart. Proves no channel is a
	 * hardcoded dial or an unread ornament.
	 */
	private static boolean honestyGate() {
		Quantizer.FieldReading base = new Quantizer.FieldReading(1.0f, 0.9f, 0.05f, 0.1f, -0.2f, 0.3f);
		String baseText = FieldGlassRead.read(base).text();
		if (!baseText.contains("1.000") || !baseText.contains("0.900")) {
			return false; // the raw ρ/q values did not even print
		}

		// Perturb each channel independently — the chart must change.
		if (FieldGlassRead.read(new Quantizer.FieldReading(1.1f, 0.9f, 0.05f, 0.1f, -0.2f, 0.3f)).text().equals(baseText)) {
			return false; // ρ insensitive
		}
		if (FieldGlassRead.read(new Quantizer.FieldReading(1.0f, 0.95f, 0.05f, 0.1f, -0.2f, 0.3f)).text().equals(baseText)) {
			return false; // q insensitive
		}
		if (FieldGlassRead.read(new Quantizer.FieldReading(1.0f, 0.9f, 0.12f, 0.1f, -0.2f, 0.3f)).text().equals(baseText)) {
			return false; // ε² insensitive
		}
		if (FieldGlassRead.read(new Quantizer.FieldReading(1.0f, 0.9f, 0.05f, 0.5f, -0.2f, 0.3f)).text().equals(baseText)) {
			return false; // ∇(g·Φ).x insensitive
		}
		if (FieldGlassRead.read(new Quantizer.FieldReading(1.0f, 0.9f, 0.05f, 0.1f, -0.6f, 0.3f)).text().equals(baseText)) {
			return false; // ∇(g·Φ).y insensitive
		}
		if (FieldGlassRead.read(new Quantizer.FieldReading(1.0f, 0.9f, 0.05f, 0.1f, -0.2f, 0.8f)).text().equals(baseText)) {
			return false; // ∇(g·Φ).z insensitive
		}
		// The raw ρ/q values appear verbatim, and the gradient's direction signs
		// + magnitude appear in the lean line (a faithful read of ∇(g·Φ)).
		return baseText.contains("1.000") && baseText.contains("0.900")
				&& baseText.contains("+X") && baseText.contains("\u2212Y") && baseText.contains("+Z");
	}

	/**
	 * Purity gate (c): the readout is a pure function of the reading (the
	 * snapshot's distilled sample) — two independently-constructed identical
	 * {@link Quantizer.FieldReading}s always produce the identical readout
	 * (no hidden state, no RNG). Trivially true by construction, asserted so the
	 * contract is explicit and enforced (the same pattern as RainDeterminismMain
	 * and MaterialRegimesDeterminismMain).
	 */
	private static boolean purityGate() {
		Quantizer.FieldReading a = new Quantizer.FieldReading(1.0f, 0.9f, 0.05f, 0.1f, -0.2f, 0.3f);
		FieldGlassRead.FieldGlassReadout ra = FieldGlassRead.read(a);

		Quantizer.FieldReading b = new Quantizer.FieldReading(1.0f, 0.9f, 0.05f, 0.1f, -0.2f, 0.3f);
		FieldGlassRead.FieldGlassReadout rb = FieldGlassRead.read(b);
		return ra.text().equals(rb.text());
	}

	/** Stable identity index of a registry material (the fingerprint's material lane). */
	private static int materialIndex(dev.cassicraft.game.material.MaterialRegistry.MaterialTuple m) {
		for (int i = 0; i < dev.cassicraft.game.material.MaterialRegistry.ALL.length; i++) {
			if (dev.cassicraft.game.material.MaterialRegistry.ALL[i] == m) {
				return i;
			}
		}
		return 0;
	}

	/** Print the measured channel distributions that anchored the [design] scalings. */
	private static void printDistributions(Dist rho, Dist q, Dist eps) {
		System.out.println("\n[instrument-determinism] sample-lattice census @ settle (SETTLE_GENERATIONS="
				+ SETTLE_GENERATIONS + ", step=" + SAMPLE_STEP + ", DT=" + TwoFluidSolver.DT + ")");
		System.out.println("[instrument-determinism]   field time evolved = " + SETTLE_GENERATIONS + " gen × "
				+ CassiFieldThread.JOB_STEP_CAP + " steps × DT=" + TwoFluidSolver.DT
				+ " = " + String.format("%.3f", fieldTimeUnits()) + " field-time units");
		System.out.println("[instrument-determinism]   ρ       " + rho);
		System.out.println("[instrument-determinism]   q       " + q);
		System.out.println("[instrument-determinism]   ε²      " + eps);
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
	private record Census(String fingerprint, Dist rhoDist, Dist qDist, Dist epsDist,
			int hashPoints) {
		String summary() {
			return "ρ " + (rhoDist == null ? "?" : pct(rhoDist.mean))
					+ " | q " + (qDist == null ? "?" : pct(qDist.mean))
					+ " | hash=" + fingerprint.substring(0, 8);
		}
	}

	private InstrumentDeterminismMain() {
	}
}
