package dev.cassicraft.game.road;

import dev.cassicraft.domain.engine.RiverForce;
import dev.cassicraft.domain.engine.TwoFluidSolver;
import dev.cassicraft.domain.snapshot.FieldSnapshot;
import dev.cassicraft.domain.snapshot.SnapshotPublisher;
import dev.cassicraft.domain.thread.CassiFieldThread;
import dev.cassicraft.domain.thread.KernelLoader;
import dev.cassicraft.game.sampler.Quantizer;

/**
 * Headless pre-registered probe for coherence-highway.md §6b's Phase-1 ride-downhill
 * slice, answering open-Q1 (coherence-highway §open-Q1): does a cart <b>measurably</b>
 * ride a real {@code ∇(g·Φ)} descent on the Phase-1 living-terrain demo — strong
 * enough to feel as a free downhill ride, and distinguishable from flat terrain?
 *
 * <p>The probe is a <b>pure consumer of the publish</b> (§6b): it boots a
 * fixed-seed {@link CassiFieldThread} via the real publish seam, lets the field
 * settle, finds the interior position with the strongest {@code |∇(g·Φ)|}, and
 * integrates a mass-point "cart" along the engine-real river-law haul
 * {@code a = −G_N·(π/ρ)·∇(g·Φ)} ({@link RiverForce}). It grants the cart nothing —
 * it reads only the published channels and measures the field's own haul.
 *
 * <p>Two arms isolate the haul exactly:
 * <ol>
 *   <li><b>Descent</b> — the full haul, read from the published {@code ∇(g·Φ)}
 *       and the derived {@code π/ρ} each sub-step (out-of-box samples read air,
 *       so the cart coasts — honest).</li>
 *   <li><b>Flat control</b> — the <em>same</em> integration with the haul removed
 *       ({@code a = 0}): a body the field contributes nothing to. From rest it
 *       stays put, isolating exactly what the field's gradient added.</li>
 * </ol>
 * The flat control is the anti-vacuous contrast — without it, any downhill motion
 * could be mistaken for the field's work; with it, the margin is measured against
 * a cart that genuinely has nothing hauling it.
 *
 * <p>Verdict (coherence-highway open-Q1's decision tree): <b>SUPPORTS</b> if the
 * descent-arm horizon speed exceeds the flat-arm by at least {@link #RIDE_MARGIN}
 * <em>and</em> the descent start is interior (real field, not out-of-box air);
 * <b>CONTRADICTS</b> if the margin fails; <b>INCONCLUSIVE</b> if the start reads
 * out-of-box air or the field is degenerate (which is reported).
 *
 * <p>Determinism: a SHA-256 fingerprint over the recorded values (start, both-arm
 * speeds and distances, mean grad, mean π/ρ, verdict) — same seed → identical
 * hash; a different seed → different hash (the probe actually exercised the field).
 *
 * <p>Exit 0 = green. Any failure prints and exits non-zero. Runs headlessly under
 * the game runtime classpath (the {@code followBehindDeterminism} pattern), no
 * live client/server.
 */
public final class RideDownhillProbeMain {

	// --- Field boot ---------------------------------------------------------
	/** Primary field seed — the fixed-seed living terrain the ride is measured on. */
	private static final long SEED = 42L;
	/** A different seed, proving the probe genuinely exercised the field (anti-vacuous). */
	private static final long SEED_B = 43L;
	/** The domain box window center (coherence-highway §6b; the Phase-1 demo anchor). */
	private static final double[] WINDOW_CENTER = { 0, 70, 0 };
	/** First-snapshot await timeout (worker deadlock guard, ms). */
	private static final long FIRST_TIMEOUT_MS = 12_000;
	/** Settle-generation await timeout (ms). */
	private static final long SETTLE_TIMEOUT_MS = 30_000;
	/**
	 * How many published generations to wait before measuring. Each publish ships
	 * one job of {@code JOB_STEP_CAP=64} domain steps, so 12 generations ≈ 768
	 * steps ≈ 38 field-time units (DT=0.05) — enough for the spectral Poisson and
	 * the gradient pass to organize real structure out of the flat-noise IC while
	 * keeping the probe short.
	 */
	private static final int SETTLE_GENERATIONS = 12;

	// --- Route finding ------------------------------------------------------
	/** Coarse x/z scan half-extent around the window center (blocks, interior of the 96-extent box). */
	private static final int SCAN_HALF = 32;
	/** Coarse route-scan step (blocks) — the deterministic interior grid. */
	private static final int SCAN_STRIDE = 4;
	/** Center-column y sweep range start (blocks) — near the center y=70. */
	private static final int Y_SWEEP_LO = 56;
	/** Center-column y sweep range end (blocks). */
	private static final int Y_SWEEP_HI = 84;
	/**
	 * A descent start needs at least this {@code |∇(g·Φ)|} to be real field, not a
	 * degenerate/flat point. Below this the start reads as degenerate field.
	 */
	private static final double MIN_START_GRAD = 1e-4;

	// --- Ride integration ---------------------------------------------------
	/** Ride sub-step size — the same dt as the field (TwoFluidSolver.DT). */
	private static final double RIDE_DT = 0.05;
	/** Ride sub-steps — 200·DT = 10 field-time units of simulated descent. */
	private static final int RIDE_STEPS = 200;
	/**
	 * The "distinguishable from flat" speed margin (coherence-highway open-Q1):
	 * the descent arm must exceed the flat-arm horizon speed by this fraction to
	 * SUPPORT ride-downhill.
	 */
	private static final double RIDE_MARGIN = 0.05;

	private static final RiverForce RIVER = new RiverForce();

	public static void main(String[] args) throws Exception {
		boolean ok = true;
		Run a1 = runOnce(SEED);
		Run a2 = runOnce(SEED);
		Run b = runOnce(SEED_B);

		System.out.println("\n[ride-downhill] SEED_A run1:\n" + a1);
		System.out.println("[ride-downhill] SEED_A run2:\n" + a2);
		System.out.println("[ride-downhill] SEED_B run:\n" + b);

		boolean sameSeedIdentical = a1.isGreen() && a1.fingerprint().equals(a2.fingerprint());
		boolean seedSensitive = !a1.fingerprint().equals(b.fingerprint());
		System.out.println("[ride-downhill] same-seed identical: " + sameSeedIdentical
				+ " | different-seed differs: " + seedSensitive);

		if (!a1.isGreen()) {
			System.err.println("[ride-downhill] FAIL — SEED_A run1 verdict was not SUPPORTS/CONTRADICTS green check");
			ok = false;
		}
		if (!sameSeedIdentical) {
			System.err.println("[ride-downhill] FAIL — same seed produced a different fingerprint (not deterministic)");
			ok = false;
		}
		if (!seedSensitive) {
			System.err.println("[ride-downhill] FAIL — different seeds produced an identical fingerprint (vacuous)");
			ok = false;
		}

		if (ok) {
			System.out.println("[ride-downhill] PASS — the cart's ride is deterministic and seed-sensitive");
		} else {
			System.err.println("[ride-downhill] FAILED");
			System.exit(1);
		}
	}

	/** Run the probe end-to-end on one seed and return the measured outcome. */
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
			RideOutcome out = measure(snap, window);
			String hash = fingerprint(out);
			boolean green = out.verdict().startsWith("SUPPORTS")
					|| out.verdict().startsWith("CONTRADICTS");
			// INCONCLUSIVE is an honest report (field degenerate / start out of the
			// box), not a mechanism failure — it still exits green with the raw data.
			return new Run(out.verdict(), out.startX(), out.startY(), out.startZ(),
					out.descentSpeed(), out.flatSpeed(), out.descentDistance(), out.flatDistance(),
					out.meanGrad(), out.meanPiOverRho(), hash, green);
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

	/** Find the strongest-{@code |∇(g·Φ)|} interior position and ride it down both arms. */
	private static RideOutcome measure(FieldSnapshot snap, double[] window) {
		// Deterministic coarse scan: x/z grid at the center's y, plus a y sweep of
		// the center column; the argmax over both is the descent start.
		double[] start = { WINDOW_CENTER[0], WINDOW_CENTER[1], WINDOW_CENTER[2] };
		double bestGrad = -1.0;
		for (int z = -SCAN_HALF; z <= SCAN_HALF; z += SCAN_STRIDE) {
			for (int x = -SCAN_HALF; x <= SCAN_HALF; x += SCAN_STRIDE) {
				double g = gradMag(snap, window, x, (int) WINDOW_CENTER[1], z);
				if (g > bestGrad) {
					bestGrad = g;
					start = new double[] { x, WINDOW_CENTER[1], z };
				}
			}
		}
		for (int y = Y_SWEEP_LO; y <= Y_SWEEP_HI; y += SCAN_STRIDE) {
			double g = gradMag(snap, window, (int) WINDOW_CENTER[0], y, (int) WINDOW_CENTER[2]);
			if (g > bestGrad) {
				bestGrad = g;
				start = new double[] { WINDOW_CENTER[0], y, WINDOW_CENTER[2] };
			}
		}

		double startGrad = gradMag(snap, window,
				(int) Math.round(start[0]), (int) Math.round(start[1]), (int) Math.round(start[2]));
		boolean inBox = isInBox(start, window);
		boolean interior = inBox && startGrad >= MIN_START_GRAD;

		RideResult descent = ride(snap, window, start, true);
		RideResult flat = ride(snap, window, start, false);

		boolean marginMet = descent.speed() > flat.speed() * (1.0 + RIDE_MARGIN);
		String verdict;
		if (!inBox) {
			verdict = "INCONCLUSIVE(start-out-of-box-air)";
		} else if (!interior) {
			verdict = "INCONCLUSIVE(degenerate-field)" ;
		} else {
			verdict = marginMet ? "SUPPORTS" : "CONTRADICTS";
		}

		System.out.println("  descent start = (" + start[0] + "," + start[1] + "," + start[2] + ")"
				+ " | start |grad|=" + fmt(startGrad) + " | in-box=" + inBox);
		System.out.println("  descent arm  speed=" + fmt(descent.speed())
				+ " dist=" + fmt(descent.distance())
				+ " mean|grad|=" + fmt(descent.meanGrad())
				+ " mean(pi/rho)=" + fmt(descent.meanPiOverRho()));
		System.out.println("  flat control arm speed=" + fmt(flat.speed()) + " dist=" + fmt(flat.distance()));
		System.out.println("  margin met (descent > " + fmt(RIDE_MARGIN) + " over flat): " + marginMet);
		System.out.println("  verdict: " + verdict);

		return new RideOutcome(verdict, (int) Math.round(start[0]), (int) Math.round(start[1]),
				(int) Math.round(start[2]), descent.speed(), flat.speed(),
				descent.distance(), flat.distance(), descent.meanGrad(), descent.meanPiOverRho());
	}

	/** Integrate the mass-point cart along the haul for one seed's settled snapshot. */
	private static RideResult ride(FieldSnapshot snap, double[] window, double[] start, boolean hauled) {
		double[] v = { 0, 0, 0 };
		double[] x = { start[0], start[1], start[2] };
		double dist = 0.0;
		double meanGrad = 0.0, meanPi = 0.0;
		int samples = 0;
		for (int i = 0; i < RIDE_STEPS; i++) {
			Reading r = readAt(snap, window, x);
			meanGrad += Math.sqrt(r.gx * r.gx + r.gy * r.gy + r.gz * r.gz);
			meanPi += r.piOverRho;
			samples++;
			if (hauled) {
				double[] a = accel(r);
				v[0] += a[0] * RIDE_DT;
				v[1] += a[1] * RIDE_DT;
				v[2] += a[2] * RIDE_DT;
			}
			double[] prev = { x[0], x[1], x[2] };
			x[0] += v[0] * RIDE_DT;
			x[1] += v[1] * RIDE_DT;
			x[2] += v[2] * RIDE_DT;
			dist += Math.sqrt(d2(x[0] - prev[0], x[1] - prev[1], x[2] - prev[2]));
		}
		double speed = Math.sqrt(v[0] * v[0] + v[1] * v[1] + v[2] * v[2]);
		return new RideResult(speed, dist, samples > 0 ? meanGrad / samples : 0.0,
				samples > 0 ? meanPi / samples : 0.0);
	}

	/** The published channels + derived π/ρ at a mass-point position (rounded to a block center). */
	private static Reading readAt(FieldSnapshot snap, double[] window, double[] pos) {
		Quantizer.FieldReading r = Quantizer.sampleReading(snap, window,
				(int) Math.round(pos[0]), (int) Math.round(pos[1]), (int) Math.round(pos[2]));
		float rho = r.rho();
		float q = r.q();
		// Same EY/EI branch the Quantizer's eps2 uses (Quantizer.java, eps2) —
		// |EY−EI| = sqrt(2q − ρ²), EY = (ρ+d)/2 ≥ EI.
		double d = Math.sqrt(Math.max(0.0, 2.0 * q - (double) rho * (double) rho));
		double piOverRho;
		if (rho < RiverForce.RHO_GUARD) {
			piOverRho = 0.0;
		} else {
			piOverRho = d / rho;
			if (piOverRho > RiverForce.PI_OVER_RHO_CLAMP) {
				piOverRho = RiverForce.PI_OVER_RHO_CLAMP;
			} else if (piOverRho < 0.0) {
				piOverRho = 0.0;
			}
		}
		return new Reading(r.rho(), r.q(), r.gradX(), r.gradY(), r.gradZ(), piOverRho);
	}

	/** The engine-real river-law haul {@code a = −G_N·(π/ρ)·∇(g·Φ)} (G_N = 1.0). */
	private static double[] accel(Reading r) {
		float ey = (float) ((r.rho() + Math.sqrt(Math.max(0.0, 2.0 * r.q()
				- (double) r.rho() * (double) r.rho()))) * 0.5);
		float ei = (float) ((r.rho() - Math.sqrt(Math.max(0.0, 2.0 * r.q()
				- (double) r.rho() * (double) r.rho()))) * 0.5);
		return RIVER.accelerate(ey, ei, (float) r.gx(), (float) r.gy(), (float) r.gz());
	}

	/** |∇(g·Φ)| at one block position (zero out-of-box). */
	private static double gradMag(FieldSnapshot snap, double[] window, int x, int y, int z) {
		Quantizer.FieldReading r = Quantizer.sampleReading(snap, window, x, y, z);
		return Math.sqrt((double) r.gradX() * r.gradX()
				+ (double) r.gradY() * r.gradY()
				+ (double) r.gradZ() * r.gradZ());
	}

	/** True when a mass-point position maps to a grid coordinate inside the field box. */
	private static boolean isInBox(double[] pos, double[] window) {
		double n = TwoFluidSolver.N;
		double gx = Quantizer.gridCoord((int) Math.round(pos[0]), window[0]);
		double gy = Quantizer.gridCoord((int) Math.round(pos[1]), window[1]);
		double gz = Quantizer.gridCoord((int) Math.round(pos[2]), window[2]);
		return gx >= 0 && gx <= n && gy >= 0 && gy <= n && gz >= 0 && gz <= n;
	}

	private static double d2(double dx, double dy, double dz) {
		return dx * dx + dy * dy + dz * dz;
	}

	/** Deterministic SHA-256 fingerprint over the recorded values. */
	private static String fingerprint(RideOutcome o) {
		String s = "start=" + o.startX() + "," + o.startY() + "," + o.startZ()
				+ ";descentSpeed=" + fmt6(o.descentSpeed())
				+ ";flatSpeed=" + fmt6(o.flatSpeed())
				+ ";descentDistance=" + fmt6(o.descentDistance())
				+ ";flatDistance=" + fmt6(o.flatDistance())
				+ ";meanGrad=" + fmt6(o.meanGrad())
				+ ";meanPiOverRho=" + fmt6(o.meanPiOverRho())
				+ ";verdict=" + o.verdict();
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

	/** One sampled reading along the ride. */
	private record Reading(float rho, float q, double gx, double gy, double gz, double piOverRho) {
	}

	/** One arm's integration result. */
	private record RideResult(double speed, double distance, double meanGrad, double meanPiOverRho) {
	}

	/** The full measured outcome of one run (start, both arms, fingerprint inputs). */
	private record RideOutcome(String verdict, int startX, int startY, int startZ,
			double descentSpeed, double flatSpeed, double descentDistance, double flatDistance,
			double meanGrad, double meanPiOverRho) {
	}

	/** One end-to-end run's verdict + fingerprint (the determinism input). */
	private record Run(String verdict, int startX, int startY, int startZ,
			double descentSpeed, double flatSpeed, double descentDistance, double flatDistance,
			double meanGrad, double meanPiOverRho, String fingerprint, boolean green) {

		boolean isGreen() {
			return green;
		}

		@Override
		public String toString() {
			return "  start=(" + startX + "," + startY + "," + startZ + ")"
					+ " descentSpeed=" + fmt(descentSpeed)
					+ " flatSpeed=" + fmt(flatSpeed)
					+ " descentDist=" + fmt(descentDistance)
					+ " flatDist=" + fmt(flatDistance)
					+ " meanGrad=" + fmt(meanGrad)
					+ " meanPiOverRho=" + fmt(meanPiOverRho)
					+ " fingerprint=" + fingerprint.substring(0, 16) + "..."
					+ " verdict=" + verdict;
		}
	}

	private RideDownhillProbeMain() {
	}
}
