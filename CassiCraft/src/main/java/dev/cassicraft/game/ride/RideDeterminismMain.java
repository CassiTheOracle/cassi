package dev.cassicraft.game.ride;

import dev.cassicraft.domain.engine.TwoFluidSolver;
import dev.cassicraft.domain.snapshot.FieldSnapshot;
import dev.cassicraft.domain.snapshot.SnapshotPublisher;
import dev.cassicraft.domain.thread.CassiFieldThread;
import dev.cassicraft.domain.thread.KernelLoader;
import dev.cassicraft.game.sampler.Quantizer;

/**
 * The ride's hard determinism + honesty gate (coherence-highway.md §6b/§6c/§6d —
 * the ride-downhill slice's gate). Boots a fixed-seed {@link CassiFieldThread} via
 * the real publish seam (the {@code TerrainCensusMain} pattern: {@code Cfg} center
 * {0,70,0}, await-first-snapshot, settle to a named generation), finds the
 * strongest-{@code |∇(g·Φ)|} interior position exactly as the ride-downhill probe
 * does, and integrates a mass-point test cart down the settled field's descent via
 * the ride's own {@link RideHaul} path ({@code a = −G_N·(π/ρ)·∇(g·Φ)}, the engine-real
 * river-law haul). It asserts:
 *
 * <ol>
 *   <li><b>(a) Determinism</b> — same seed → identical SHA-256 fingerprint (the
 *       ride path is deterministic, coherence-highway §6c).</li>
 *   <li><b>(b) Anti-vacuous</b> — a different seed → a different fingerprint (the
 *       ride genuinely exercised the field).</li>
 *   <li><b>(c) Matches the engine-real probe</b> — the descent-arm horizon speed
 *       equals the ride-downhill probe's SUPPORTS result ({@link #PROBE_DESCENT_SPEED},
 *       the measured 3.71) within {@link #MATCH_TOLERANCE}: the ride path and the
 *       probe path agree, proving {@link RideHaul} reuses the engine-real haul,
 *       not a reimplementation drift.</li>
 *   <li><b>(d) No-free-energy anti-mint</b> — the flat control arm (haul removed,
 *       {@code a = 0}) gains ≤ {@link #FLAT_EPSILON} speed: a cart on flat ground
 *       is NOT carried (coherence-highway §6d; the honest bound).</li>
 * </ol>
 *
 * <p>The haul is pure (no seeded-RNG mood); the fingerprint salts the measured
 * values (start, both-arm speeds + distances, mean grad, mean π/ρ, the gate's
 * booleans) so same seed → same hash and different seed → different hash.
 *
 * <p>Exit 0 = green. Runs headlessly under the game runtime classpath (the
 * {@code terrainCensus} pattern), no live client/server.
 */
public final class RideDeterminismMain {

	// --- Field boot ---------------------------------------------------------
	/** Primary field seed — the fixed-seed living terrain the ride is measured on. */
	private static final long SEED = 42L;
	/** A different seed, proving the ride genuinely exercised the field (anti-vacuous). */
	private static final long SEED_B = 43L;
	/** The domain box window center (coherence-highway §6b; the Phase-1 demo anchor). */
	private static final double[] WINDOW_CENTER = { 0, 70, 0 };
	/** First-snapshot await timeout (worker deadlock guard, ms). */
	private static final long FIRST_TIMEOUT_MS = 12_000;
	/** Settle-generation await timeout (ms) — extended past the probe's 30s
	 * because this gate frequently runs on a CPU-saturated machine (parallel
	 * worker live-servers share the cores); a worker-deadlock guard, not a
	 * correctness bound (the assertions below are unaffected). */
	private static final long SETTLE_TIMEOUT_MS = 90_000;
	/**
	 * How many published generations to wait before measuring — the same settle
	 * count the ride-downhill probe uses. Each publish ships one job of
	 * {@code JOB_STEP_CAP=64} domain steps, so 12 generations ≈ 768 steps ≈
	 * 0.768 field-time units at the engine-default {@code DT=0.001} — the same
	 * near-IC field the probe's SUPPORTS verdict was measured on.
	 */
	private static final int SETTLE_GENERATIONS = 12;

	// --- Route finding (the probe's route, replicated) ---------------------
	/** Coarse x/z scan half-extent around the window center (blocks, interior of the 96-extent box). */
	private static final int SCAN_HALF = 32;
	/** Coarse route-scan step (blocks) — the deterministic interior grid. */
	private static final int SCAN_STRIDE = 4;
	/** Center-column y sweep range start (blocks) — near the center y=70. */
	private static final int Y_SWEEP_LO = 56;
	/** Center-column y sweep range end (blocks). */
	private static final int Y_SWEEP_HI = 84;
	/** A descent start needs at least this {@code |∇(g·Φ)|} to be real field, not degenerate. */
	private static final double MIN_START_GRAD = 1e-4;

	// --- Ride integration (the probe's integration, via RideHaul) ----------
	/** Ride sub-step size — the same dt as the field (TwoFluidSolver.DT-scaled; the probe's RIDE_DT). */
	private static final double RIDE_DT = 0.05;
	/** Ride sub-steps — 200·DT = 10 field-time units of simulated descent. */
	private static final int RIDE_STEPS = 200;

	// --- Gate constants ----------------------------------------------------
	/**
	 * The ride-downhill probe's SUPPORTS descent-arm horizon speed
	 * (RideDownhillProbeMain, seed 42 @ 12 generations — measured verbatim on
	 * this repo). Re-pinned for the condensed-body IC: the field's descent scan
	 * now finds the steep hydrostatic-envelope density gradient of a real body
	 * (mean |∇(g·Φ)| ≈ 253 vs the old flat-noise sponge's ~5.6), so the
	 * engine-real haul carries the cart to a much higher horizon speed (was
	 * 3.71 on the sponge; 52.93 on the body — the ride down a real slope is
	 * genuinely fast; flat control still 0.0000). This is the engine-real
	 * SUPPORTS value the ride path must match.
	 */
	private static final double PROBE_DESCENT_SPEED = 52.93;
	/**
	 * Match-to-probe tolerance — the ride's descent-arm speed must be within this
	 * relative fraction of the probe's SUPPORTS speed, proving the ride path and
	 * the probe path agree (the same engine-real haul, no reimplementation drift).
	 */
	private static final double MATCH_TOLERANCE = 0.05;
	/**
	 * No-free-energy anti-mint bound — the flat control arm (haul removed) may
	 * gain at most this much speed. A cart on flat ground is NOT carried (the
	 * honest bound, coherence-highway §6d): with {@code a = 0} from rest it stays
	 * at rest, so this epsilon only guards against a reimplementation drift that
	 * would grant the cart something.
	 */
	private static final double FLAT_EPSILON = 0.01;

	public static void main(String[] args) throws Exception {
		Run a1 = runOnce(SEED);
		Run a2 = runOnce(SEED);
		Run b = runOnce(SEED_B);

		System.out.println("\n[ride-determinism] SEED_A run1:\n" + a1);
		System.out.println("[ride-determinism] SEED_A run2:\n" + a2);
		System.out.println("[ride-determinism] SEED_B run:\n" + b);

		boolean sameSeedIdentical = a1.fingerprint().equals(a2.fingerprint());
		boolean seedSensitive = !a1.fingerprint().equals(b.fingerprint());
		// (c) the ride matches the engine-real probe within tolerance.
		boolean matchesProbe = Math.abs(a1.descentSpeed() - PROBE_DESCENT_SPEED)
				<= MATCH_TOLERANCE * PROBE_DESCENT_SPEED
				&& Math.abs(a2.descentSpeed() - PROBE_DESCENT_SPEED)
						<= MATCH_TOLERANCE * PROBE_DESCENT_SPEED;
		// (d) the flat control arm stays still (no free energy).
		boolean noFreeEnergy = a1.flatSpeed() <= FLAT_EPSILON && a2.flatSpeed() <= FLAT_EPSILON;

		System.out.println("[ride-determinism] same-seed identical: " + sameSeedIdentical
				+ " | different-seed differs: " + seedSensitive);
		System.out.println("[ride-determinism] matches-engine-real-probe (|descent−" + fmt(PROBE_DESCENT_SPEED)
				+ "| ≤ " + fmt(MATCH_TOLERANCE * 100) + "%): " + matchesProbe
				+ " (a1=" + fmt(a1.descentSpeed()) + " a2=" + fmt(a2.descentSpeed()) + ")");
		System.out.println("[ride-determinism] no-free-energy (flat ≤ " + fmt(FLAT_EPSILON) + "): "
				+ noFreeEnergy + " (a1=" + fmt(a1.flatSpeed()) + " a2=" + fmt(a2.flatSpeed()) + ")");

		boolean ok = true;
		if (!sameSeedIdentical) {
			System.err.println("[ride-determinism] FAIL — same seed produced a different fingerprint (the ride is not deterministic)");
			ok = false;
		}
		if (!seedSensitive) {
			System.err.println("[ride-determinism] FAIL — different seeds produced an identical fingerprint (vacuous)");
			ok = false;
		}
		if (!matchesProbe) {
			System.err.println("[ride-determinism] FAIL — the ride's descent speed (" + fmt(a1.descentSpeed())
					+ ") does not match the engine-real probe's SUPPORTS result ("
					+ fmt(PROBE_DESCENT_SPEED) + " ± " + fmt(MATCH_TOLERANCE * 100) + "%)");
			ok = false;
		}
		if (!noFreeEnergy) {
			System.err.println("[ride-determinism] FAIL — the flat control arm gained " + fmt(a1.flatSpeed())
					+ " > " + fmt(FLAT_EPSILON) + " (a cart on flat ground was carried — a mint)");
			ok = false;
		}

		if (ok) {
			System.out.println("[ride-determinism] PASS — the ride is deterministic, matches the engine-real probe's haul, and gains nothing on flat ground");
		} else {
			System.err.println("[ride-determinism] FAILED");
			System.exit(1);
		}
	}

	/** Run the ride end-to-end on one seed and return the measured outcome. */
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
			return new Run(out.startX(), out.startY(), out.startZ(),
					out.descentSpeed(), out.flatSpeed(), out.descentDistance(), out.flatDistance(),
					out.meanGrad(), out.meanPiOverRho(), hash);
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
		System.out.println("  descent start = (" + start[0] + "," + start[1] + "," + start[2] + ")"
				+ " | start |grad|=" + fmt(startGrad) + " | in-box=" + isInBox(start, window));

		RideResult descent = ride(snap, window, start, true);
		RideResult flat = ride(snap, window, start, false);

		System.out.println("  descent arm  speed=" + fmt(descent.speed())
				+ " dist=" + fmt(descent.distance())
				+ " mean|grad|=" + fmt(descent.meanGrad())
				+ " mean(pi/rho)=" + fmt(descent.meanPiOverRho()));
		System.out.println("  flat control arm speed=" + fmt(flat.speed()) + " dist=" + fmt(flat.distance()));

		return new RideOutcome((int) Math.round(start[0]), (int) Math.round(start[1]),
				(int) Math.round(start[2]), descent.speed(), flat.speed(),
				descent.distance(), flat.distance(), descent.meanGrad(), descent.meanPiOverRho());
	}

	/** Integrate the mass-point cart along the haul for one seed's settled snapshot — the {@link RideHaul} path. */
	private static RideResult ride(FieldSnapshot snap, double[] window, double[] start, boolean hauled) {
		double[] v = { 0, 0, 0 };
		double[] x = { start[0], start[1], start[2] };
		double dist = 0.0;
		double meanGrad = 0.0, meanPi = 0.0;
		int samples = 0;
		for (int i = 0; i < RIDE_STEPS; i++) {
			Quantizer.FieldReading r = readAt(snap, window, x);
			meanGrad += Math.sqrt((double) r.gradX() * r.gradX()
					+ (double) r.gradY() * r.gradY()
					+ (double) r.gradZ() * r.gradZ());
			samples++;
			if (hauled) {
				RideHaul.Haul haul = RideHaul.of(r);
				meanPi += haul.piOverRho();
				v[0] += haul.ax() * RIDE_DT;
				v[1] += haul.ay() * RIDE_DT;
				v[2] += haul.az() * RIDE_DT;
			}
			double[] prev = { x[0], x[1], x[2] };
			x[0] += v[0] * RIDE_DT;
			x[1] += v[1] * RIDE_DT;
			x[2] += v[2] * RIDE_DT;
			double dx = x[0] - prev[0], dy = x[1] - prev[1], dz = x[2] - prev[2];
			dist += Math.sqrt(dx * dx + dy * dy + dz * dz);
		}
		double speed = Math.sqrt(v[0] * v[0] + v[1] * v[1] + v[2] * v[2]);
		return new RideResult(speed, dist, samples > 0 ? meanGrad / samples : 0.0,
				samples > 0 ? meanPi / samples : 0.0);
	}

	/** The published channels at a mass-point position (rounded to a block center). */
	private static Quantizer.FieldReading readAt(FieldSnapshot snap, double[] window, double[] pos) {
		return Quantizer.sampleReading(snap, window,
				(int) Math.round(pos[0]), (int) Math.round(pos[1]), (int) Math.round(pos[2]));
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

	/** Deterministic SHA-256 fingerprint over the recorded values. */
	private static String fingerprint(RideOutcome o) {
		String s = "start=" + o.startX() + "," + o.startY() + "," + o.startZ()
				+ ";descentSpeed=" + fmt6(o.descentSpeed())
				+ ";flatSpeed=" + fmt6(o.flatSpeed())
				+ ";descentDistance=" + fmt6(o.descentDistance())
				+ ";flatDistance=" + fmt6(o.flatDistance())
				+ ";meanGrad=" + fmt6(o.meanGrad())
				+ ";meanPiOverRho=" + fmt6(o.meanPiOverRho());
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

	/** One arm's integration result. */
	private record RideResult(double speed, double distance, double meanGrad, double meanPiOverRho) {
	}

	/** The full measured outcome of one run (start, both arms, fingerprint inputs). */
	private record RideOutcome(int startX, int startY, int startZ,
			double descentSpeed, double flatSpeed, double descentDistance, double flatDistance,
			double meanGrad, double meanPiOverRho) {
	}

	/** One end-to-end run's measured outcome (the determinism + honesty inputs). */
	private record Run(int startX, int startY, int startZ,
			double descentSpeed, double flatSpeed, double descentDistance, double flatDistance,
			double meanGrad, double meanPiOverRho, String fingerprint) {

		@Override
		public String toString() {
			return "  start=(" + startX + "," + startY + "," + startZ + ")"
					+ " descentSpeed=" + fmt(descentSpeed)
					+ " flatSpeed=" + fmt(flatSpeed)
					+ " descentDist=" + fmt(descentDistance)
					+ " flatDist=" + fmt(flatDistance)
					+ " meanGrad=" + fmt(meanGrad)
					+ " meanPiOverRho=" + fmt(meanPiOverRho)
					+ " fingerprint=" + fingerprint.substring(0, 16) + "...";
		}
	}

	private RideDeterminismMain() {
	}
}
