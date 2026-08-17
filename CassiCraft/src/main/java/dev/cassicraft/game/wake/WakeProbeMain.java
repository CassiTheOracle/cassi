package dev.cassicraft.game.wake;

import dev.cassicraft.domain.engine.TwoFluidSolver;
import dev.cassicraft.domain.snapshot.FieldSnapshot;
import dev.cassicraft.domain.snapshot.SnapshotPublisher;
import dev.cassicraft.domain.thread.CassiFieldThread;
import dev.cassicraft.domain.thread.KernelLoader;
import dev.cassicraft.game.practice.StillingShoutCommand;

/**
 * Headless wake measurement probe (signature-predator.md §1, §8 the readable-trail
 * slice — the honest question this wave closes). Measures whether a player's
 * practice — ONE shout, the committed practice's exact construction
 * (StillingShoutCommand {@code SHOUT_D_EY}/{@code SHOUT_D_EI}/{@code SHOUT_RADIUS},
 * a bounded matched-φ coherence-delivering write through the REAL Q4 lane) at a
 * named point — leaves a measurable, persistent wake in the published ε²/q
 * channels ABOVE the body's own floor, and whether that wake is a local
 * perturbation that relaxes (a wake) or a propagating disturbance (a front).
 *
 * <p><b>The question.</b> The signature-predator reads {@code S = q·(1+ε²)} —
 * elevated organization weighted by the strain that marks a vent
 * ({@link SignatureSense}, signature-predator.md §1.1). Its Phase-1 prey is the
 * player's wake — the ε²/q trail of perturbation — not the static body. This
 * probe measures whether the wake actually exists above the coherent condensed
 * body's own floor (signature-predator.md §1.2: "the trail is only legible where
 * the field has no order to hide it" — the body is high-q and near-ε²-zero, so a
 * wake must rise ABOVE that; the combustion-body precedent found the coherent
 * dense body absorbs bound writes fast — a wake probe must resolve whether the
 * wake differs from a front, and say which it found).
 *
 * <p><b>Measurement (publish seam, matched control).</b> A fixed-seed
 * {@link CassiFieldThread} boots via the real publish seam ({@code Cfg} center
 * {0,70,0}, seed 42), settles to a named generation, then ONE shout is submitted
 * through the real Q4 lane at a named point ({@link #PRACTICE_POINT} —
 * window-relative, deep in the dense body, a clean STILL at settle reading
 * STILLING-SHOUT-DATE-picked as the point whose wake the predator would read).
 * The ε²/q profile is sampled along the direction away from the point at a
 * spread of field-times after the write (Δt ≈ 0.5, 1, 2, 5 field-units). The
 * <b>matched control</b> is the identical same-seed field-time evolution with no
 * write — the write-attributable Δ is {@code shout − control} at field-time
 * matched snapshots (the body's own evolution is the control). The far-field
 * (beyond the shout's own falloff) is monitored for a propagating front.
 *
 * <p><b>Verdict (computed by the measurement, never forced):</b>
 * <ul>
 *   <li><b>SUPPORTS</b> — a wake exists: peak attributable {@code ΔS} at/above
 *       {@link #WAKE_DELTA_S_FRACTION} (5% of the body's own S at the point) on the
 *       practice arm and absent in the matched control, and a measurable lifetime
 *       (&gt; {@link #WAKE_LIFETIME_FLOOR} = 1 field-unit — the wake persists, it
 *       does not collapse within one field-unit).</li>
 *   <li><b>CONTRADICTS</b> — no attributable wake above the body's floor: the
 *       shout's bound write is absorbed/re-locked by the coherent body within the
 *       measurement floor (the combustion-body probe's precedent — the body absorbs
 *       writes fast; the wake is not resolvable above the body's own evolution).</li>
 *   <li><b>INCONCLUSIVE</b> — with the reason, if the measurement cannot
 *       discriminate (e.g. the micro-scale injection response floor again).</li>
 * </ul>
 * The probe additionally distinguishes <b>wake vs front</b>: a wake is a local
 * perturbation that relaxes (elevation confined near the practice point, decaying
 * over time); a front propagates (the elevation moves outward / appears across
 * the box). With {@code c_s = h₀/dt = 1000} cells/ft, a front traverses the
 * periodic 64-cell box in 0.064 field-time — so a box-uniform far-field elevation
 * at any sample is a front; a confined decaying elevation is a wake.
 *
 * <p>A measurement probe that prints the verdict but is NOT part of the build
 * gate ({@code WakeDeterminismMain} asserts the contract at build). Headless (the
 * {@code combustionBodyProbe} pattern), no live client/server. Reads the publish
 * only + submits ONE shout through the practice's own committed path — no domain
 * edit, no block write, no entity, no free energy.
 */
public final class WakeProbeMain {

	// --- Field boot --------------------------------------------------------
	/** Primary field seed — the fixed-seed body world this probe drives. */
	private static final long SEED = 42L;
	/** A different seed, proving the probe genuinely exercised the body (anti-vacuous). */
	private static final long SEED_B = 43L;
	/** The domain box window center (the Phase-1 demo anchor; the body's dense floor). */
	private static final double[] WINDOW_CENTER = { 0, 70, 0 };
	/** Settle-generation await timeout (ms) — extended for CPU-saturated parallel builds. */
	private static final long SETTLE_TIMEOUT_MS = 120_000;
	/**
	 * The named settle generation — how many published generations to wait before
	 * measuring the shout. Each publish ships one job of {@value
	 * CassiFieldThread#JOB_STEP_CAP} domain steps, so 12 generations ≈ 768 steps ≈
	 * 0.768 field-time — the same near-IC settle the combustion-body / ride gates
	 * and the practice gate use, on the body world.
	 */
	private static final int SETTLE_GENERATIONS = 12;

	/**
	 * The practice point — window-relative, deep in the condensed body (world
	 * {@code (16, 22, 0)} with the {0,70,0} center, the SAME point the
	 * stilling-shout gate's shout uses; reads a clean STILL at settle — q high,
	 * ε² near-zero, the coherent bulk whose wake the predator would read).
	 */
	private static final int[] PRACTICE_POINT = { 16, 22, 0 };

	// --- Field-time sample spread ------------------------------------------
	/**
	 * The field-times (field-units after the write) at which the wake profile is
	 * sampled. One field-unit = 1/DT = 1000 steps = 15.625 generations
	 * ({@code JOB_STEP_CAP} steps/job); each entry maps to a generation offset
	 * {@code round(dt·15.625)}. Distinguishes the wake's early form (Δ≈0.5) from
	 * its late relaxation (Δ≈5) — a wake relaxes, a front would be box-uniform
	 * throughout.
	 */
	private static final double[] SAMPLE_FT = { 0.5, 1.0, 2.0, 5.0 };

	/**
	 * The wake-elevation floor fraction — SUPPORTS requires the peak attributable
	 * {@code ΔS = (q·(1+ε²))_shout − (q·(1+ε²))_control} at/above this fraction of
	 * the body's own S at the practice point (the brief's named floor, 5%).
	 * Single source: {@link WakeVerdict#DELTA_S_FRACTION}.
	 */
	private static final double WAKE_DELTA_S_FRACTION = WakeVerdict.DELTA_S_FRACTION;

	/**
	 * The wake-lifetime floor — SUPPORTS requires the wake to persist this many
	 * field-units (the brief's named bar, 1 field-unit). A wake that collapses
	 * within one field-unit is absorbed, not persistent. Single source:
	 * {@link WakeVerdict#LIFETIME_FLOOR}.
	 */
	private static final double WAKE_LIFETIME_FLOOR = WakeVerdict.LIFETIME_FLOOR;

	/**
	 * The spatial-extent floor fraction — the wake's spatial extent is the radius
	 * at which the attributable elevation drops below this fraction of the peak
	 * (the "floor fraction" of the brief).
	 */
	private static final double EXTENT_FLOOR_FRACTION = 0.5;

	/** The far-field front probe's radius (cells) — beyond the shout's own
	 * Gaussian falloff (radius 6), the box beyond the injection's local scale. */
	private static final int FRONT_RADIUS = 8;

	private static final int N = TwoFluidSolver.N;
	private static final int MID = N / 2;

	public static void main(String[] args) throws Exception {
		final int gensPerFt = (int) Math.round((1.0 / TwoFluidSolver.DT) / CassiFieldThread.JOB_STEP_CAP);
		System.out.println("[wake-probe] field boot: seed " + SEED + ", center {0,70,0}, settle "
				+ SETTLE_GENERATIONS + " gens (" + SETTLE_GENERATIONS + "×" + CassiFieldThread.JOB_STEP_CAP
				+ " steps ≈ " + String.format("%.3f", SETTLE_GENERATIONS * CassiFieldThread.JOB_STEP_CAP * TwoFluidSolver.DT)
				+ " ft); gens per ft = " + gensPerFt);

		// Matched control first (the body's own evolution, no write).
		WakeRun ctrl = runOne(SEED, false, gensPerFt);
		// The practice arm — ONE shout through the committed Q4 path.
		WakeRun shout = runOne(SEED, true, gensPerFt);
		WakeRun shout2 = runOne(SEED, true, gensPerFt);
		// Seed-sensitive arm (anti-vacuity — the probe exercised the field).
		WakeRun shoutB = runOne(SEED_B, true, gensPerFt);

		double[] bodyS = { 0, 0, 0 };
		// Body's own S at the practice point = the ctrl settle read.
		double[] pre = sig(ctrl.settle);
		bodyS[0] = pre[0];
		bodyS[1] = pre[1];
		bodyS[2] = pre[2];
		double deltaSFloor = WAKE_DELTA_S_FRACTION * bodyS[2];
		System.out.println("\n[wake-probe] body's own S at practice point (ctrl settle): "
				+ fmt(bodyS[2]) + " (q " + fmt(bodyS[0]) + ", ε² " + fmtE(bodyS[1]) + ")"
				+ " | ΔS floor (5% of body S) = " + fmt(deltaSFloor));

		// Peak wake + S elevation per sample: attributable at the practice point.
		double peakDq = 0, peakDep = 0, peakDS = 0;
		double peakDqFt = 0, peakDSFt = 0;
		boolean[] aboveFloor = new boolean[SAMPLE_FT.length];
		System.out.println("\n[wake-probe] practice-point attributable wake (shout − matched control, same seed " + SEED + "):");
		for (int i = 0; i < SAMPLE_FT.length; i++) {
			double[] ss = sig(shout.samples[i]);
			double[] cs = sig(ctrl.samples[i]);
			double dq = ss[0] - cs[0];
			double de = ss[1] - cs[1];
			double ds = ss[2] - cs[2];
			aboveFloor[i] = ds >= deltaSFloor;
			if (dq > peakDq) { peakDq = dq; peakDqFt = SAMPLE_FT[i]; }
			if (de > peakDep) { peakDep = de; }
			if (ds > peakDS) { peakDS = ds; peakDSFt = SAMPLE_FT[i]; }
			System.out.println("  Δt=" + SAMPLE_FT[i] + " ft (~" + (i == 0 ? "8" : (int) Math.round(SAMPLE_FT[i] * gensPerFt))
					+ " gens): Δq=" + fmtSign(dq) + " Δε²=" + fmtSign(de)
					+ " ΔS=" + fmtSign(ds) + " above-floor: " + aboveFloor[i]);
		}

		// Spatial extent: radius at which attributable ΔS drops below floor fraction
		// of peak, along the +X ray away from the practice point (the last sample,
		// where a wake's far extent is largest).
		double extent = spatialExtent(shout.samples[SAMPLE_FT.length - 1], ctrl.samples[SAMPLE_FT.length - 1],
				peakDS == 0 ? 0 : peakDS * EXTENT_FLOOR_FRACTION, deltaSFloor, peakDS);

		// Lifetime: the last sample where wake still above floor (in ft).
		double lifetime = 0;
		for (int i = SAMPLE_FT.length - 1; i >= 0; i--) {
			if (aboveFloor[i]) {
				lifetime = SAMPLE_FT[i];
				break;
			}
		}
		String lifetimeStr = peakDS >= deltaSFloor
				? String.format("%.1f", lifetime) + " ft (" + (lifetime > WAKE_LIFETIME_FLOOR ? "persists" : "absorbs within bar") + ")"
				: "0 ft — no wake above the floor at any sample (absorbed below the first sample)";

		// Front vs wake: far-field attributable ΔS (beyond the front probe radius).
		double[] front = farField(shout.samples[SAMPLE_FT.length - 1], ctrl.samples[SAMPLE_FT.length - 1], FRONT_RADIUS);
		System.out.println("\n[wake-probe] far-field (beyond " + FRONT_RADIUS + " cells from the point):");
		System.out.println("  mean attributable ΔS = " + fmtSign(front[0]) + "  mean|ΔS| = " + fmtSign(front[1])
				+ "  (a propagating FRONT would carry box-uniform elevation; a confined wake carries ~0)");
		String chara = (Math.abs(front[0]) < deltaSFloor * 0.5 && Math.abs(front[1]) < deltaSFloor)
				? "no box-uniform far-field elevation — NOT a front; a local perturbation the body absorbs"
				: "box-uniform far-field elevation present — front-like propagation";
		System.out.println("  character: " + chara);

		System.out.println("\n[wake-probe] MEASURED WAKE (peak across samples):");
		System.out.println("  peak Δq=" + fmtSign(peakDq) + " @ Δt=" + peakDqFt + " ft"
				+ " | peak Δε²=" + fmtSign(peakDep)
				+ " | peak ΔS=" + fmtSign(peakDS) + " @ Δt=" + peakDSFt + " ft (floor " + fmt(deltaSFloor) + ")");
		System.out.println("  spatial extent (radius where attributable ΔS drops to " + (int) (100 * EXTENT_FLOOR_FRACTION)
				+ "% of peak): r≈" + fmt(extent) + " cells");
		System.out.println("  lifetime: " + lifetimeStr);

		String verdict = WakeVerdict.size(peakDS, deltaSFloor, lifetime, bodyS[2], front[0], front[1]);
		System.out.println("\n[wake-probe] WAKE VERDICT: " + verdict);

		// Determinism + seed-sensitivity + anti-vacuity dumps.
		System.out.println("\n[wake-probe] determinism (same seed + same shout → identical profile fingerprint):");
		System.out.println("  run1 " + shout.fingerprint().substring(0, 16) + " | run2 " + shout2.fingerprint().substring(0, 16)
				+ " | identical=" + shout.fingerprint().equals(shout2.fingerprint()));
		System.out.println("  diff-seed " + shoutB.fingerprint().substring(0, 16)
				+ " | differs=" + !shout.fingerprint().equals(shoutB.fingerprint()));
		System.out.println("  shout arm lane clampCount=" + shout.clamps + " (matched-φ — expected 0; a clamp is an honest report)");
	}

	/**
	 * Run one arm (shout or matched control): boot the real field thread, settle
	 * to {@link #SETTLE_GENERATIONS}, then (practice arm) submit ONE shout through
	 * the Q4 lane and sample the ε²/q profile at {@link #SAMPLE_FT} field-times
	 * after the write; the control arm merely waits the same field-times with no
	 * write. Returns the settled+sample snapshots and the write-attributable
	 * fingerprint.
	 */
	private static WakeRun runOne(long seed, boolean shout, int gensPerFt) throws InterruptedException {
		SnapshotPublisher pub = new SnapshotPublisher();
		CassiFieldThread.Cfg cfg = new CassiFieldThread.Cfg(
				seed, CassiFieldThread.JOB_STEP_CAP, CassiFieldThread.SNAPSHOT_CADENCE,
				new KernelLoader().load(), WINDOW_CENTER);
		CassiFieldThread worker = new CassiFieldThread(pub);
		worker.start(cfg);
		try {
			FieldSnapshot settle = awaitGen(pub, SETTLE_GENERATIONS);
			int startGen = settle.generation();
			if (shout) {
				worker.submitPerturbation(PRACTICE_POINT[0], PRACTICE_POINT[1], PRACTICE_POINT[2],
						StillingShoutCommand.SHOUT_D_EY,
						StillingShoutCommand.SHOUT_D_EI,
						StillingShoutCommand.SHOUT_RADIUS);
			}
			FieldSnapshot[] samples = new FieldSnapshot[SAMPLE_FT.length];
			for (int i = 0; i < SAMPLE_FT.length; i++) {
				int off = (int) Math.round(SAMPLE_FT[i] * gensPerFt);
				samples[i] = awaitGen(pub, startGen + off);
			}
			long clamps = worker.perturbationClampCount();
			String fp = fingerprint(settle, samples, shout);
			return new WakeRun(settle, samples, clamps, fp);
		} finally {
			worker.close();
		}
	}

	/**
	 * Deterministic SHA-256 fingerprint — over the rounded practice-point q/ε²/S at
	 * each sample and the settled q/ε², plus the shout flag. Same seed + same shout
	 * → identical; different seed → differs. The settle absolute q/ε² (the body's
	 * own state) is included so a same-source seed proves the probe exercised the
	 * body (the anti-vacuity separation comes from the changed body between seeds).
	 */
	private static String fingerprint(FieldSnapshot settle, FieldSnapshot[] samples, boolean shout) {
		StringBuilder sb = new StringBuilder();
		double[] st = sig(settle);
		sb.append("shout=").append(shout)
				.append(";settleQ=").append(coarse(st[0]))
				.append(";settleEps2=").append(coarse(st[1]));
		for (int i = 0; i < SAMPLE_FT.length; i++) {
			double[] s = sig(samples[i]);
			sb.append(";t").append(i).append("q=").append(coarse(s[0]))
					.append(";t").append(i).append("eps2=").append(coarse(s[1]))
					.append(";t").append(i).append("S=").append(coarse(s[2]));
		}
		return sha256(sb.toString().getBytes(java.nio.charset.StandardCharsets.UTF_8));
	}

	private static String coarse(double v) {
		return String.format("%.4f", Math.round(v * 1e4) / 1e4);
	}

	/**
	 * The wake's spatial extent — the cell-radius at which the attributable ΔS
	 * along the ray from the practice point drops to {@link #EXTENT_FLOOR_FRACTION}
	 * of its peak (or the floor if the peak is below it). Returns 0 if no peak
	 * above the floor exists (no wake to have an extent).
	 */
	private static double spatialExtent(FieldSnapshot shout, FieldSnapshot ctrl,
			double halfPeak, double deltaSFloor, double peakDS) {
		if (peakDS < deltaSFloor) {
			return 0;
		}
		int[] c0 = cellCoords(PRACTICE_POINT[0], PRACTICE_POINT[1], PRACTICE_POINT[2]);
		double target = halfPeak;
		// Walk +X in cells from the practice point (the "away" direction within
		// the coherent body's interior), reading attributable ΔS at each shell.
		for (int r = 1; r <= Math.min(12, N / 2); r++) {
			int i = (c0[0] + r) % N;
			int j = c0[1];
			int k = c0[2];
			int id = i + N * (j + N * k);
			double ds = dS(id, shout, ctrl);
			if (ds < target) {
				return r;
			}
		}
		return 12;
	}

	private static double dS(int id, FieldSnapshot s, FieldSnapshot c) {
		return sigCell(s, id)[2] - sigCell(c, id)[2];
	}

	private static double[] sigCell(FieldSnapshot snap, int id) {
		float r = snap.rho()[id];
		float q = snap.q()[id];
		float e2 = eps2(r, q);
		return new double[] { q, e2, q * (1.0 + e2) };
	}

	/**
	 * Far-field front probe — the mean attributable ΔS over all cells beyond
	 * {@code r > FRONT_RADIUS} cells from the practice point (the box beyond the
	 * shout's own Gaussian falloff). A propagating front carries box-uniform
	 * elevation here; a confined wake carries ~0 (both returned: signed mean and
	 * mean|ΔS|).
	 */
	private static double[] farField(FieldSnapshot shout, FieldSnapshot ctrl, int rFront) {
		int[] c0 = cellCoords(PRACTICE_POINT[0], PRACTICE_POINT[1], PRACTICE_POINT[2]);
		double sum = 0, sumAbs = 0;
		long cnt = 0;
		for (int k = 0; k < N; k++) {
			int dk = minWrap(k - c0[2], N);
			for (int j = 0; j < N; j++) {
				int dj = minWrap(j - c0[1], N);
				for (int i = 0; i < N; i++) {
					int di = minWrap(i - c0[0], N);
					double rr = Math.sqrt(di * di + dj * dj + dk * dk);
					if (rr > rFront) {
						int id = i + N * (j + N * k);
						double ds = dS(id, shout, ctrl);
						sum += ds;
						sumAbs += Math.abs(ds);
						cnt++;
					}
				}
			}
		}
		if (cnt == 0) {
			return new double[] { 0, 0 };
		}
		return new double[] { sum / cnt, sumAbs / cnt };
	}

	/** The signature channels {@code {q, ε², S}} at the practice point of a snapshot. */
	private static double[] sig(FieldSnapshot snap) {
		int id = cellOf(PRACTICE_POINT[0], PRACTICE_POINT[1], PRACTICE_POINT[2]);
		double[] s = sigCell(snap, id);
		return new double[] { s[0], s[1], s[2] };
	}

	private static int cellOf(int bx, int by, int bz) {
		int cx = floorCell(bx, WINDOW_CENTER[0]);
		int cy = floorCell(by, WINDOW_CENTER[1]);
		int cz = floorCell(bz, WINDOW_CENTER[2]);
		return cx + N * (cy + N * cz);
	}

	/** The practice point's cell coordinates {@code {i, j, k}}. */
	private static int[] cellCoords(int bx, int by, int bz) {
		return new int[] {
				floorCell(bx, WINDOW_CENTER[0]),
				floorCell(by, WINDOW_CENTER[1]),
				floorCell(bz, WINDOW_CENTER[2]),
		};
	}

	private static int floorCell(double w, double center) {
		int c = (int) Math.floor((w - center) / 3.0) + MID;
		c = ((c % N) + N) % N;
		return c;
	}

	private static int minWrap(int d, int n) {
		int w = d % n;
		if (w < 0) {
			w += n;
		}
		return Math.min(w, n - w);
	}

	private static float eps2(float r, float q) {
		float d2 = 2f * q - r * r;
		float d = (float) Math.sqrt(Math.max(0f, d2));
		float ey = (r + d) * 0.5f;
		float ei = (r - d) * 0.5f;
		float eps = ey - (float) TwoFluidSolver.PHI * ei;
		return eps * eps;
	}

	private static FieldSnapshot awaitGen(SnapshotPublisher pub, int gen) throws InterruptedException {
		long deadline = System.currentTimeMillis() + SETTLE_TIMEOUT_MS;
		while (System.currentTimeMillis() < deadline) {
			FieldSnapshot s = pub.freshest();
			if (s != null && s.generation() >= gen) {
				return s;
			}
			Thread.sleep(10);
		}
		throw new IllegalStateException("field never reached generation " + gen);
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

	private static String fmtE(double v) {
		return String.format("%.6f", v);
	}

	private static String fmtSign(double v) {
		return String.format("%+.6f", v);
	}

	/** One end-to-end arm: the settle snapshot, the sample-time snapshots, clamps, fingerprint. */
	private record WakeRun(FieldSnapshot settle, FieldSnapshot[] samples, long clamps, String fingerprint) {
	}

	private WakeProbeMain() {
	}
}
