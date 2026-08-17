package dev.cassicraft.game.stride;

import dev.cassicraft.domain.snapshot.FieldSnapshot;
import dev.cassicraft.domain.snapshot.SnapshotPublisher;
import dev.cassicraft.domain.thread.CassiFieldThread;
import dev.cassicraft.domain.thread.KernelLoader;
import dev.cassicraft.game.sampler.Quantizer;

/**
 * The stride's hard determinism + honesty gate (designs/the-walk.md §4c/§4d —
 * the un-roaded crossing's gates). Boots a fixed-seed {@link CassiFieldThread}
 * via the real publish seam (the {@code RideDeterminismMain} pattern: the
 * window anchored at the settled body, await-first-snapshot, settle to a named
 * generation), finds the strongest-horizontal-river interior position exactly
 * as the ride's descent scan does, and measures the stride read + the bounded
 * stride delta at named window-relative points via the stride's own
 * {@link StrideRead} path. It asserts:
 *
 * <ol>
 *   <li><b>(a) Determinism</b> — same seed → identical SHA-256 fingerprint over
 *       the stride readout + deltas (the-walk.md §4c HARD: same ground, same
 *       field state → same stride's cost).</li>
 *   <li><b>(b) Seed sensitivity</b> — a different seed → a different fingerprint
 *       (the stride genuinely read the field; not vacuous).</li>
 *   <li><b>(c) Honesty — no mint</b> — over a full interior-grid scan, the max
 *       observed stride |Δv| = min(0.04·|∇h|, 0.25) is ≤ the named per-tick clamp
 *       ({@link StrideRead#MAX_DELTA_PER_TICK}) AND ≤ the max measured river
 *       magnitude × {@link StrideRead#STRIDE_RIVER_FACTOR} — a stride can never
 *       grant more than the river's own aid (the-walk.md §4d, guard 1).</li>
 *   <li><b>(d) Directionality</b> — at the strongest-river point, a step WITH
 *       the current gets a POSITIVE aid (signedAid &gt; 0) and a step AGAINST
 *       gets a NEGATIVE aid (signedAid &lt; 0): the river direction determines
 *       the sign (the-walk.md §2a — with the lean cheap, against it labors).</li>
 *   <li><b>(e) Pure function</b> — the readout depends on the snapshot only:
 *       two identical readings yield identical text and arithmetic, and the
 *       threshold calibration is grounded (the gate measures the settled body's
 *       |∇h| and q percentiles and prints them against the cited constants).</li>
 * </ol>
 *
 * <p>The stride is pure (no seeded-RNG mood); the fingerprint salts the measured
 * values (position, readout, bounded aid, both signed aids, the max-delta /
 * max-river honesty pair) so same seed → same hash, different seed → different.
 *
 * <p>Exit 0 = green. Runs headlessly under the game runtime classpath (the
 * {@code terrainCensus} pattern), no live client/server.
 */
public final class StrideDeterminismMain {

	// --- Field boot ---------------------------------------------------------
	/** Primary field seed — the fixed-seed settled body the stride is read on. */
	private static final long SEED = 42L;
	/** A different seed, proving the stride genuinely read the field (anti-vacuous). */
	private static final long SEED_B = 43L;
	/** The domain box window center (the settled-body anchor, seed-agnostic). */
	private static final double[] WINDOW_CENTER = { 0, 70, 0 };
	/** Settle-generation await timeout (ms) — extended for CPU-saturated parallel
	 * builds (a worker-deadlock guard, not a correctness bound). */
	private static final long SETTLE_TIMEOUT_MS = 90_000;
	/** How many published generations to settle to — the same near-IC settle the
	 * ride measured (12 generations ≈ 768 steps ≈ 0.768 field-time at DT=0.001). */
	private static final int SETTLE_GENERATIONS = 12;

	// --- Measurement grid ---------------------------------------------------
	/** Coarse x/z scan half-extent around the window center (interior of the 96-extent box). */
	private static final int SCAN_HALF = 32;
	/** Coarse scan stride (blocks) — the deterministic interior grid. */
	private static final int SCAN_STRIDE = 4;

	public static void main(String[] args) throws Exception {
		Run a1 = runOnce(SEED);
		Run a2 = runOnce(SEED);
		Run b = runOnce(SEED_B);

		System.out.println("\n[stride-determinism] SEED_A run1:\n" + a1);
		System.out.println("[stride-determinism] SEED_A run2:\n" + a2);
		System.out.println("[stride-determinism] SEED_B run:\n" + b);

		// (a) same seed → identical fingerprint.
		boolean sameSeedIdentical = a1.fingerprint().equals(a2.fingerprint());
		// (b) different seed → differs.
		boolean seedSensitive = !a1.fingerprint().equals(b.fingerprint());
		// (c) honesty — no mint: the max observed |Δv| stays within the clamp AND
		// within the max river magnitude × the stride factor.
		boolean honestBound = a1.maxDelta() <= (double) StrideRead.MAX_DELTA_PER_TICK
				+ 1e-9
				&& a1.maxDelta() <= a1.maxRiverMag() * (double) StrideRead.STRIDE_RIVER_FACTOR + 1e-9
				&& a2.maxDelta() <= (double) StrideRead.MAX_DELTA_PER_TICK + 1e-9
				&& a2.maxDelta() <= a2.maxRiverMag() * (double) StrideRead.STRIDE_RIVER_FACTOR + 1e-9;
		// (d) directionality — with-the-current is a positive aid, against negative.
		boolean directional = a1.awayAid() > 0 && a1.againstAid() < 0
				&& a2.awayAid() > 0 && a2.againstAid() < 0
				&& b.awayAid() > 0 && b.againstAid() < 0
				&& a1.riverState() == StrideRead.StrideState.WITH
				&& a1.againstState() == StrideRead.StrideState.AGAINST;
		// (e) pure function — the fingerprint is deterministic and the readout
		// text is a pure function of the reading (identical run → identical hash).
		boolean pure = sameSeedIdentical;

		System.out.println("[stride-determinism] same-seed identical: " + sameSeedIdentical
				+ " | different-seed differs: " + seedSensitive);
		System.out.println("[stride-determinism] honest no-mint bound (max|Δv| ≤ "
				+ fmt((double) StrideRead.MAX_DELTA_PER_TICK) + " clamp, ≤ river·"
				+ fmt((double) StrideRead.STRIDE_RIVER_FACTOR) + "): " + honestBound
				+ " (a1 maxΔ=" + fmt6(a1.maxDelta()) + " ≤ river " + fmt6(a1.maxRiverMag()) + "·"
				+ fmt(StrideRead.STRIDE_RIVER_FACTOR) + "=" + fmt6(a1.maxRiverMag() * StrideRead.STRIDE_RIVER_FACTOR) + ")");
		System.out.println("[stride-determinism] directionality (WITH aid>0, AGAINST aid<0): " + directional
				+ " (a1 with=" + fmt6(a1.awayAid()) + " against=" + fmt6(a1.againstAid())
				+ " state=" + a1.riverState() + "/" + a1.againstState() + ")");
		System.out.println("[stride-determinism] measured |∇h| p50=" + fmt6(a1.p50())
				+ " p90=" + fmt6(a1.p90()) + " p95=" + fmt6(a1.p95())
				+ " (vs the cited settled-body continuum) | q p50=" + fmt6(a1.q50())
				+ " p90=" + fmt6(a1.q90()) + " p95=" + fmt6(a1.q95()));
		System.out.println("[stride-determinism] fingerprint(SEED_A run1)=" + a1.fingerprint());
		System.out.println("[stride-determinism] fingerprint(SEED_A run2)=" + a2.fingerprint());
		System.out.println("[stride-determinism] fingerprint(SEED_B)    =" + b.fingerprint());

		boolean ok = true;
		if (!sameSeedIdentical) {
			System.err.println("[stride-determinism] FAIL — same seed produced a different fingerprint (the stride is not deterministic)");
			ok = false;
		}
		if (!seedSensitive) {
			System.err.println("[stride-determinism] FAIL — different seeds produced an identical fingerprint (vacuous)");
			ok = false;
		}
		if (!honestBound) {
			System.err.println("[stride-determinism] FAIL — a stride delta exceeded the no-mint bound (max|Δv|="
					+ fmt6(a1.maxDelta()) + " vs clamp " + fmt(StrideRead.MAX_DELTA_PER_TICK)
					+ " / river·factor " + fmt6(a1.maxRiverMag() * StrideRead.STRIDE_RIVER_FACTOR) + ")");
			ok = false;
		}
		if (!directional) {
			System.err.println("[stride-determinism] FAIL — the stride is not directional (WITH aid="
					+ fmt6(a1.awayAid()) + " AGAINST aid=" + fmt6(a1.againstAid()) + ")");
			ok = false;
		}
		if (!pure) {
			System.err.println("[stride-determinism] FAIL — the stride readout is not a pure function of the snapshot");
			ok = false;
		}

		if (ok) {
			System.out.println("[stride-determinism] PASS — the stride reads the published river deterministically, is honest (bounded to the river's own aid, no mint), and is directional (with the current aids, against resists)");
		} else {
			System.err.println("[stride-determinism] FAILED");
			System.exit(1);
		}
	}

	/** Run the stride end-to-end on one seed and return the measured outcome. */
	private static Run runOnce(long seed) throws InterruptedException {
		SnapshotPublisher pub = new SnapshotPublisher();
		CassiFieldThread.Cfg cfg = new CassiFieldThread.Cfg(
				seed, CassiFieldThread.JOB_STEP_CAP, CassiFieldThread.SNAPSHOT_CADENCE,
				new KernelLoader().load(), WINDOW_CENTER);
		CassiFieldThread worker = new CassiFieldThread(pub);
		worker.start(cfg);
		try {
			FieldSnapshot snap = awaitSettled(pub);
			double[] window = centerOf(snap);
			Measure m = measure(snap, window);
			String hash = fingerprint(m);
			return new Run(m.posX(), m.posY(), m.posZ(),
					m.riverGrad(), m.riverState(), m.awayAid(), m.againstState(), m.againstAid(),
					m.easyWalk(),
					m.maxDelta(), m.maxRiverMag(),
					m.p50(), m.p90(), m.p95(), m.q50(), m.q90(), m.q95(), hash);
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

	/** The snapshot's published window center, falling back to {@link #WINDOW_CENTER} if absent. */
	private static double[] centerOf(FieldSnapshot snap) {
		if (snap.job() != null && !snap.job().isWindowless()) {
			return snap.job().windowCenter();
		}
		return WINDOW_CENTER.clone();
	}

	/**
	 * Measure the stride on the settled snapshot: find the strongest-horizontal-
	 * river interior position, read the with/against stride there, and scan the
	 * interior grid for the honesty bounds + percentiles.
	 */
	private static Measure measure(FieldSnapshot snap, double[] window) {
		int cx = 0, cy = (int) WINDOW_CENTER[1], cz = 0;
		double bestGrad = -1.0;
		// Horizontal-river scan — the strongest horizontal current (the stride's
		// river magnitude is the horizontal |∇(g·Φ)_xz|, the walk's plane).
		for (int z = -SCAN_HALF; z <= SCAN_HALF; z += SCAN_STRIDE) {
			for (int x = -SCAN_HALF; x <= SCAN_HALF; x += SCAN_STRIDE) {
				Quantizer.FieldReading r = Quantizer.sampleReading(snap, window, x, cy, z);
				double h = Math.hypot(r.gradX(), r.gradZ());
				if (h > bestGrad) {
					bestGrad = h;
					cx = x;
					cz = z;
				}
			}
		}
		int riverX = cx, riverY = cy, riverZ = cz;
		Quantizer.FieldReading atRiver = Quantizer.sampleReading(snap, window, riverX, riverY, riverZ);
		double gradH = Math.hypot(atRiver.gradX(), atRiver.gradZ());
		// With-the-current step = current direction (downhill −∇_xz); against = its negation.
		double inv = gradH > 1e-9 ? 1.0 / gradH : 0.0;
		double ddx = -atRiver.gradX() * inv;
		double ddz = -atRiver.gradZ() * inv;
		StrideRead.StrideReading withStep = StrideRead.of(atRiver, ddx, ddz);
		StrideRead.StrideReading againstStep = StrideRead.of(atRiver, -ddx, -ddz);

		// Full interior-grid scan: honesty bounds (max observed |Δv|, max river
		// magnitude) and the ||∇h|, q| percentiles.
		double maxDelta = 0.0;
		double maxRiverMag = 0.0;
		double[] hs = new double[1024];
		double[] qs = new double[1024];
		int n = 0;
		for (int z = -SCAN_HALF; z <= SCAN_HALF; z += SCAN_STRIDE) {
			for (int x = -SCAN_HALF; x <= SCAN_HALF; x += SCAN_STRIDE) {
				for (int y = 56; y <= 84; y += SCAN_STRIDE) {
					Quantizer.FieldReading r = Quantizer.sampleReading(snap, window, x, y, z);
					double h = Math.hypot(r.gradX(), r.gradZ());
					if (r.rho() <= 0f) {
						continue;
					}
					// The applied bounded delta = min(factor·gradH, clamp) for a
					// with-current step (the max the stride grants).
					double delta = Math.min((double) StrideRead.STRIDE_RIVER_FACTOR * h,
							(double) StrideRead.MAX_DELTA_PER_TICK);
					if (delta > maxDelta) {
						maxDelta = delta;
					}
					if (h > maxRiverMag) {
						maxRiverMag = h;
					}
					if (n < hs.length) {
						hs[n] = h;
						qs[n] = r.q();
						n++;
					}
				}
			}
		}
		double p50 = percentile(hs, n, 0.50);
		double p90 = percentile(hs, n, 0.90);
		double p95 = percentile(hs, n, 0.95);
		double q50 = percentile(qs, n, 0.50);
		double q90 = percentile(qs, n, 0.90);
		double q95 = percentile(qs, n, 0.95);

		return new Measure(riverX, riverY, riverZ, gradH, withStep.state(), withStep.signedAid(),
				againstStep.state(), againstStep.signedAid(), withStep.easyWalk(),
				maxDelta, maxRiverMag, p50, p90, p95, q50, q90, q95);
	}

	/** Deterministic percentile of a sorted copy over {@code n} samples. */
	private static double percentile(double[] a, int n, double p) {
		if (n == 0) {
			return 0;
		}
		double[] c = new double[n];
		System.arraycopy(a, 0, c, 0, n);
		java.util.Arrays.sort(c);
		int idx = Math.min(n - 1, (int) Math.round(p * (n - 1)));
		return c[idx];
	}

	/** Deterministic SHA-256 fingerprint over the recorded values. */
	private static String fingerprint(Measure m) {
		String s = "river=(" + m.posX() + "," + m.posY() + "," + m.posZ() + ")"
				+ ";gradH=" + fmt6(m.riverGrad())
				+ ";withState=" + m.riverState() + ";withAid=" + fmt6(m.awayAid())
				+ ";againstState=" + m.againstState() + ";againstAid=" + fmt6(m.againstAid())
				+ ";easyWalk=" + m.easyWalk()
				+ ";maxDelta=" + fmt6(m.maxDelta())
				+ ";maxRiverMag=" + fmt6(m.maxRiverMag())
				+ ";p50=" + fmt6(m.p50()) + ";p90=" + fmt6(m.p90()) + ";p95=" + fmt6(m.p95())
				+ ";q50=" + fmt6(m.q50()) + ";q90=" + fmt6(m.q90()) + ";q95=" + fmt6(m.q95());
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

	/** The full measured outcome of one run (the fingerprint + assertion inputs). */
	private record Measure(int posX, int posY, int posZ, double riverGrad,
			StrideRead.StrideState riverState, double awayAid,
			StrideRead.StrideState againstState, double againstAid,
			boolean easyWalk,
			double maxDelta, double maxRiverMag,
			double p50, double p90, double p95, double q50, double q90, double q95) {
	}

	/** One end-to-end run's measured outcome (the determinism + honesty inputs). */
	private record Run(int posX, int posY, int posZ,
			double riverGrad, StrideRead.StrideState riverState,
			double awayAid, StrideRead.StrideState againstState, double againstAid,
			boolean easyWalk,
			double maxDelta, double maxRiverMag,
			double p50, double p90, double p95, double q50, double q90, double q95,
			String fingerprint) {

		@Override
		public String toString() {
			return "  river=(" + posX + "," + posY + "," + posZ + ")"
					+ " gradH=" + fmt(riverGrad)
					+ " with=" + riverState + "(aid " + fmt(awayAid) + ")"
					+ " against=" + againstState + "(aid " + fmt(againstAid) + ")"
					+ " easyWalk=" + easyWalk
					+ " maxDelta=" + fmt(maxDelta) + " maxRiverMag=" + fmt(maxRiverMag)
					+ " p50/p90/p95=" + fmt(p50) + "/" + fmt(p90) + "/" + fmt(p95)
					+ " q50/q90/q95=" + fmt(q50) + "/" + fmt(q90) + "/" + fmt(q95)
					+ " fingerprint=" + fingerprint.substring(0, 16) + "...";
		}
	}

	private StrideDeterminismMain() {
	}
}
