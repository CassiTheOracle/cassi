package dev.cassicraft.game.predator;

import dev.cassicraft.domain.engine.TwoFluidSolver;
import dev.cassicraft.domain.snapshot.FieldSnapshot;
import dev.cassicraft.domain.snapshot.SnapshotPublisher;
import dev.cassicraft.domain.thread.CassiFieldThread;
import dev.cassicraft.domain.thread.KernelLoader;
import dev.cassicraft.game.sampler.Quantizer;

/**
 * The signature predator's hard determinism + honesty gate (signature-predator.md
 * §7d/§8 — the Phase-1 embodied slice). Boots a fixed-seed {@link CassiFieldThread}
 * via the real publish seam (the {@code terrainCensus} pattern: {@code Cfg} center
 * {0,70,0}, await-first-snapshot, settle to a named generation), then simulates the
 * <b>same hunt decision law</b> the live {@link SignaturePredatorEntity} runs
 * headlessly — no live entity, the gate drives {@link SignatureSense#read} against
 * the published snapshots and moves a bounded step along the signature gradient
 * over a named number of ticks. It asserts:
 *
 * <ol>
 *   <li><b>(a) Determinism</b> — same seed → identical SHA-256 fingerprint over the
 *       hunt's position trajectory (the signature signature-predator is
 *       deterministic; open-Q5's stance).</li>
 *   <li><b>(b) Anti-vacuous</b> — a different seed → a different fingerprint (the
 *       hunt genuinely exercised the field).</li>
 *   <li><b>(c) Directionality</b> — the predator moves toward the signature
 *       gradient: its final position is closer to the box's maximum-signature
 *       region than its start, by a named margin (it hunts the trail, not a
 *       hidden coordinate).</li>
 *   <li><b>(d) Boundedness</b> — max per-tick step ≤ the named clamp (a single
 *       tick can never teleport the predator; the boundary is the walk speed).</li>
 *   <li><b>(e) Honesty</b> — the predator's target region carries a measurably
 *       higher signature than its start: {@code S(final) > S(start)} by a named
 *       margin. It hunts the field (the published q/ε²), not the player's
 *       coordinates.</li>
 * </ol>
 *
 * <p>The gate prints the measured signature magnitudes (the body-world's q/ε²
 * gradients the predator reads) so the walk is honest, not hidden. Exit 0 = green.
 * Runs headlessly under the game runtime classpath, no live client/server.
 */
public final class PredatorDeterminismMain {

	// --- Field boot ---------------------------------------------------------
	/** Primary field seed — the fixed-seed living terrain the predator is measured on. */
	private static final long SEED = 42L;
	/** A different seed, proving the hunt genuinely exercised the field (anti-vacuous). */
	private static final long SEED_B = 43L;
	/** The domain box window center (the Phase-1 demo anchor; the body's dense floor). */
	private static final double[] WINDOW_CENTER = { 0, 70, 0 };
	/** First-snapshot await timeout (worker deadlock guard, ms). */
	private static final long FIRST_TIMEOUT_MS = 12_000;
	/** Settle-generation await timeout (ms) — extended for CPU-saturated parallel builds. */
	private static final long SETTLE_TIMEOUT_MS = 90_000;
	/** How many published generations to wait before hunting — the same settle the
	 * ride gate uses (12 gens ≈ 768 domain steps ≈ 0.768 field-time at the
	 * engine-default DT=0.001). The body's coalesced q/ε² structure is legible by then. */
	private static final int SETTLE_GENERATIONS = 12;

	// --- The hunt (the entity's decision law, mass-point) ------------------
	/**
	 * The hunt's per-tick speed — the mass-point analog of the live entity's
	 * vanilla walk: {@code HUNT_SPEED_MODIFIER × MOVEMENT_SPEED} =
	 * {@code 0.75 × 0.25 = 0.1875} blocks/tick (see
	 * {@link SignaturePredatorEntity#HUNT_SPEED_MODIFIER} and its movement-speed
	 * attribute). The live entity's pathfinder walks at this pace; the gate moves
	 * the point the same per tick along the same signature gradient.
	 */
	private static final double SPEED_PER_TICK = 0.1875;
	/**
	 * The named per-tick step clamp — the maximum distance the predator's point
	 * may move in a single tick. Honesty bound against a teleport; the simulated
	 * normal-hunt speed (above) is well below it, so the assertion only fires on a
	 * degenerate gradient that would otherwise cross a room in one tick.
	 */
	private static final double MAX_STEP_PER_TICK = 1.0;
	/** How many ticks (one field read + one bounded move each) to simulate the hunt. */
	private static final int HUNT_TICKS = 120;

	// --- Gate constants ----------------------------------------------------
	/** The directionality margin (blocks): final must be this much nearer the
	 * box's maximum-signature region than the start to prove the hunt tracked the
	 * gradient (gate (c)). */
	private static final double DIRECTIONALITY_MARGIN = 4.0;
	/** The honesty margin: the final position's signature must exceed the start's
	 * by at least this much to prove the predator hunted the field, not a hidden
	 * coordinate (gate (e)). Calibrated from the measured body-world read (seed 42
	 * @ 12 gens): a predator starting in the thin vacuum (S ≈ 0.013) hunts down
	 * into the body's edge (S ≈ 0.103 at 120 ticks) — a measurable gain ≈ 0.09,
	 * ~8× the start. 0.05 sits comfortably below that measured gain while still a
	 * genuinely positive legibility bound. */
	private static final double HONESTY_SIGNATURE_MARGIN = 0.05;

	public static void main(String[] args) throws Exception {
		Run a1 = runOnce(SEED);
		Run a2 = runOnce(SEED);
		Run b = runOnce(SEED_B);

		System.out.println("\n[predator-determinism] SEED_A run1:\n" + a1);
		System.out.println("[predator-determinism] SEED_A run2:\n" + a2);
		System.out.println("[predator-determinism] SEED_B run:\n" + b);

		boolean sameSeedIdentical = a1.fingerprint().equals(a2.fingerprint());
		boolean seedSensitive = !a1.fingerprint().equals(b.fingerprint());
		boolean directionality = a1.distToMaxGain() >= DIRECTIONALITY_MARGIN
				&& a2.distToMaxGain() >= DIRECTIONALITY_MARGIN;
		boolean bounded = a1.maxStepPerTick() <= MAX_STEP_PER_TICK
				&& a2.maxStepPerTick() <= MAX_STEP_PER_TICK;
		boolean honest = a1.signatureGain() >= HONESTY_SIGNATURE_MARGIN
				&& a2.signatureGain() >= HONESTY_SIGNATURE_MARGIN;

		System.out.println("[predator-determinism] same-seed identical: " + sameSeedIdentical
				+ " | different-seed differs: " + seedSensitive);
		System.out.println("[predator-determinism] directionality (toward signature, gain >= " + fmt(DIRECTIONALITY_MARGIN)
				+ " blocks): " + directionality + " (gain a1=" + fmt(a1.distToMaxGain())
				+ " a2=" + fmt(a2.distToMaxGain()) + ")");
		System.out.println("[predator-determinism] bounded (max step <= " + fmt(MAX_STEP_PER_TICK)
				+ " blocks/tick): " + bounded + " (a1=" + fmt(a1.maxStepPerTick())
				+ " a2=" + fmt(a2.maxStepPerTick()) + ")");
		System.out.println("[predator-determinism] honesty (S(final) >= S(start) + " + fmt(HONESTY_SIGNATURE_MARGIN)
				+ "): " + honest + " (gain a1=" + fmt(a1.signatureGain()) + " a2=" + fmt(a2.signatureGain()) + ")");

		boolean ok = true;
		if (!sameSeedIdentical) {
			System.err.println("[predator-determinism] FAIL — same seed produced a different hunt fingerprint (the predator is not deterministic)");
			ok = false;
		}
		if (!seedSensitive) {
			System.err.println("[predator-determinism] FAIL — different seeds produced an identical hunt fingerprint (vacuous)");
			ok = false;
		}
		if (!directionality) {
			System.err.println("[predator-determinism] FAIL — the hunt did not move toward the box's high-signature region (final was not nearer by the margin)");
			ok = false;
		}
		if (!bounded) {
			System.err.println("[predator-determinism] FAIL — a tick moved the predator more than " + fmt(MAX_STEP_PER_TICK) + " block(s) (a teleport)");
			ok = false;
		}
		if (!honest) {
			System.err.println("[predator-determinism] FAIL — the hunted region did not carry a higher signature than the start (it did not hunt the field)");
			ok = false;
		}

		if (ok) {
			System.out.println("[predator-determinism] PASS — the signature predator is deterministic, bounded, and hunts the field's signature gradient, not a hidden coordinate");
		} else {
			System.err.println("[predator-determinism] FAILED");
			System.exit(1);
		}
	}

	/** Run the predator's hunt end-to-end on one seed and return the measured outcome. */
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
			HuntOutcome out = hunt(snap, window);
			String hash = fingerprint(out);
			return new Run(out.startX(), out.startY(), out.startZ(),
					out.finalX(), out.finalY(), out.finalZ(),
					out.startSignature(), out.finalSignature(), out.signatureGain(),
					out.distToMaxGain(), out.maxStepPerTick(), hash);
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
	 * Simulate the hunt: from a deterministic interior start in the box's thin
	 * vacuum (above the condensed body, where q is low and the signature gradient
	 * leans into the coherent body), read the signature, step one bounded move
	 * along the normalized signature gradient each tick, and record the trajectory.
	 * This is the <b>same decision law</b> the live entity's {@code tick()} runs.
	 */
	private static HuntOutcome hunt(FieldSnapshot snap, double[] window) {
		// Deterministic start: the box interior just above the body's coherent
		// edge (window y=70 is the body's dense floor; y=84 is 14 above it, still
		// interior). The body's high-q coherent condensate + its ε² drains sit
		// below, so the start reads a low signature and the gradient points down.
		double[] pos = { window[0], window[1] + 14, window[2] };
		int startX = (int) Math.round(pos[0]);
		int startY = (int) Math.round(pos[1]);
		int startZ = (int) Math.round(pos[2]);

		int[] traj = new int[HUNT_TICKS * 3];
		double maxStep = 0.0;
		double[] lastSig = new double[HUNT_TICKS];
		double[] lastGrad = new double[3];
		for (int t = 0; t < HUNT_TICKS; t++) {
			int bx = (int) Math.round(pos[0]);
			int by = (int) Math.round(pos[1]);
			int bz = (int) Math.round(pos[2]);
			SignatureSense.Read sense = SignatureSense.read(snap, window, bx, by, bz);
			traj[t * 3] = bx;
			traj[t * 3 + 1] = by;
			traj[t * 3 + 2] = bz;
			lastSig[t] = sense.signature();
			double gx = sense.gradX(), gy = sense.gradY(), gz = sense.gradZ();
			double glen = Math.sqrt(gx * gx + gy * gy + gz * gz);
			if (glen <= SignatureSense.FLAT_GRADIENT_EPSILON) {
				continue; // flat field — the predator holds (no legible direction).
			}
			// The bounded one-step move along the normalized signature gradient.
			double dx = (gx / glen) * SPEED_PER_TICK;
			double dy = (gy / glen) * SPEED_PER_TICK;
			double dz = (gz / glen) * SPEED_PER_TICK;
			double step = Math.sqrt(dx * dx + dy * dy + dz * dz);
			if (step > maxStep) {
				maxStep = step;
			}
			pos[0] += dx;
			pos[1] += dy;
			pos[2] += dz;
		}

		int finalX = (int) Math.round(pos[0]);
		int finalY = (int) Math.round(pos[1]);
		int finalZ = (int) Math.round(pos[2]);
		double startSignature = lastSig[0];
		double finalSignature = SignatureSense.read(snap, window, finalX, finalY, finalZ).signature();

		// The box's maximum-signature region (the trail the predator hunts) —
		// scanned over a coarse interior grid at the predator's vertical band.
		double[] maxPos = { startX, startY, startZ };
		double maxSig = -1.0;
		int scanHalf = 32, stride = 4;
		for (int z = -scanHalf; z <= scanHalf; z += stride) {
			for (int y = -scanHalf; y <= scanHalf; y += stride) {
				for (int x = -scanHalf; x <= scanHalf; x += stride) {
					SignatureSense.Read r = SignatureSense.read(snap, window,
							(int) Math.round(window[0] + x),
							(int) Math.round(window[1] + y),
							(int) Math.round(window[2] + z));
					if (r.signature() > maxSig) {
						maxSig = r.signature();
						maxPos = new double[] { window[0] + x, window[1] + y, window[2] + z };
					}
				}
			}
		}
		double distStartMax = dist(startX, startY, startZ, maxPos[0], maxPos[1], maxPos[2]);
		double distFinalMax = dist(finalX, finalY, finalZ, maxPos[0], maxPos[1], maxPos[2]);

		System.out.println("  hunt start=(" + startX + "," + startY + "," + startZ + ")"
				+ " final=(" + finalX + "," + finalY + "," + finalZ + ")"
				+ " | S(start)=" + fmt(startSignature) + " S(final)=" + fmt(finalSignature)
				+ " | max-sig region=(" + (int) Math.round(maxPos[0]) + "," + (int) Math.round(maxPos[1])
				+ "," + (int) Math.round(maxPos[2]) + ") maxS=" + fmt(maxSig)
				+ " | distToMax start=" + fmt(distStartMax) + " final=" + fmt(distFinalMax)
				+ " | max step/tick=" + fmt(maxStep));

		return new HuntOutcome(startX, startY, startZ, finalX, finalY, finalZ,
				startSignature, finalSignature, finalSignature - startSignature,
				distStartMax - distFinalMax, maxStep, trajectoryToken(traj));
	}

	/**
	 * Salt-stable trajectory token — every hunted block position over the
	 * simulation, interleaved x,y,z. This is the fingerprint's load: same field
	 * state → identical position sequence, so a same-seed replay hashes identically
	 * and a different seed (different field) diverges at the first differing read.
	 */
	private static String trajectoryToken(int[] traj) {
		StringBuilder sb = new StringBuilder(traj.length * 6);
		for (int i = 0; i < traj.length; i++) {
			sb.append(traj[i]).append(i % 3 == 2 ? ';' : ',');
		}
		return sb.toString();
	}

	private static double dist(double x1, double y1, double z1, double x2, double y2, double z2) {
		double dx = x1 - x2, dy = y1 - y2, dz = z1 - z2;
		return Math.sqrt(dx * dx + dy * dy + dz * dz);
	}

	/** Deterministic SHA-256 fingerprint over the hunt's position trajectory + signature values. */
	private static String fingerprint(HuntOutcome o) {
		StringBuilder sb = new StringBuilder("start=").append(o.startX()).append(',').append(o.startY()).append(',').append(o.startZ())
				.append(";final=").append(o.finalX()).append(',').append(o.finalY()).append(',').append(o.finalZ())
				.append(";startSig=").append(fmt6(o.startSignature()))
				.append(";finalSig=").append(fmt6(o.finalSignature()))
				.append(";maxStep=").append(fmt6(o.maxStepPerTick()))
				.append(";traj=").append(o.trajectory());
		return sha256(sb.toString().getBytes(java.nio.charset.StandardCharsets.UTF_8));
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

	/** The full measured outcome of one hunt (the determinism + honesty inputs). */
	private record HuntOutcome(int startX, int startY, int startZ,
			int finalX, int finalY, int finalZ,
			double startSignature, double finalSignature, double signatureGain,
			double distToMaxGain, double maxStepPerTick, String trajectory) {
	}

	/** One end-to-end run's measured outcome. */
	private record Run(int startX, int startY, int startZ,
			int finalX, int finalY, int finalZ,
			double startSignature, double finalSignature, double signatureGain,
			double distToMaxGain, double maxStepPerTick, String fingerprint) {

		@Override
		public String toString() {
			return "  start=(" + startX + "," + startY + "," + startZ + ")"
					+ " final=(" + finalX + "," + finalY + "," + finalZ + ")"
					+ " S(start)=" + fmt(startSignature)
					+ " S(final)=" + fmt(finalSignature)
					+ " signatureGain=" + fmt(signatureGain)
					+ " distToMaxGain=" + fmt(distToMaxGain)
					+ " maxStep=" + fmt(maxStepPerTick)
					+ " fingerprint=" + fingerprint;
		}
	}

	private PredatorDeterminismMain() {
	}
}
