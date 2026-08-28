package dev.cassicraft.game.condensation;

import dev.cassicraft.domain.engine.TwoFluidSolver;
import dev.cassicraft.domain.snapshot.FieldSnapshot;
import dev.cassicraft.domain.snapshot.SnapshotPublisher;
import dev.cassicraft.domain.thread.CassiFieldThread;
import dev.cassicraft.domain.thread.KernelLoader;
import dev.cassicraft.game.sampler.Quantizer;
import dev.cassicraft.game.spawn.SurfaceSpawn;

/**
 * Headless condensation-term measurement probe — the domain-level answer to the
 * wave's falsification ({@code SurfaceEmergenceMain}: the field is a uniform
 * ~72–75%-solid sponge with no vertical density plane at any reachable t). The
 * Q4-lane genesis ({@code GenesisProbeMain}) measured <b>CONTRADICTS</b> — a
 * bounded micro-injection diffuses back to the sponge — and named the real
 * requirement. The question this probe measures over the {@link
 * TwoFluidSolver#CONDENSATION_ENABLED} domain term:
 *
 * <blockquote>Can a symmetry-breaking condensation term in the solver organize
 * the field into a real density body with a vertical surface — deterministically,
 * seed-sensitively, honestly (no free energy, OFF path byte-identical)?</blockquote>
 *
 * <p>The probe boots a fixed-seed {@link CassiFieldThread} via the real publish
 * seam (Cfg center {0,70,0}, seed 42) with the term flag ON (or OFF for the
 * falsified-sponge control), settles to a spread of field-times (t≈2, 10, 20,
 * 40), and at each settle measures: the vertical structure (top-third vs
 * bottom-third mean solid fraction via {@link Quantizer#sampleAt} +
 * {@link Quantizer#TAU_C}), the coherent-plane scan
 * ({@link SurfaceSpawn#findCoherentSurface}), total ρ and total q over the full
 * box (the no-mint check: minting = total ρ grows beyond the bounded input
 * scale), and the ε²/q distributions (the decoherence cost of the term). The
 * flag-OFF control is the falsified sponge, measured at the same set-points.
 *
 * <p><b>The verdict is computed by the measurement, never forced.</b>
 * <b>SUPPORTS</b> iff the ON run develops a real vertical gradient (top-third
 * mean solid &lt; {@link #GRADIENT_FRACTION} × bottom-third) at a mature settle,
 * that gradient is materially absent in the OFF control, a standable coherent
 * plane exists, AND the total ρ is bounded (no-mint). <b>CONTRADICTS</b> iff no
 * gradient (the term does not organize a body). <b>INCONCLUSIVE</b> with a
 * reason for any degenerate measurement (minting, decoherence blowup, diffusion
 * back to sponge). Headless, no live client/server. A measurement probe — exits
 * 0 always (the gate asserts the verdict).
 */
public final class CondensationProbeMain {

	/** Fixed seed — the same domain seed the other gates replay. */
	private static final long SEED = 42L;
	/** The demo box anchor — center {0,70,0}. */
	private static final double[] WINDOW_CENTER = { 0, 70, 0 };
	/** Settle-generation await timeout (ms) — a long settle to t=40 takes ~2 min. */
	private static final long SETTLE_TIMEOUT_MS = 600_000;
	/** The gradient margin: real when top-third mean solid &lt; this × bottom-third. */
	private static final double GRADIENT_FRACTION = 0.25;
	/** The no-mint margin: total ρ at the mature settle may not exceed this × the
	 * OFF control's total ρ (the term may REDISTRIBUTE, never mint beyond its
	 * input scale; the Q4 lane's own amplitude cap is φ⁻¹·input,
	 * energy-harnessing §6). */
	private static final double NO_MINT_FRACTION = 1.25;
	/** The four field-times the probe settles to and measures (the emergent spread). */
	private static final double[] SETTLE_TARGETS = { 2.0, 10.0, 20.0, 40.0 };

	public static void main(String[] args) throws Exception {
		System.out.println("=== Condensation-term domain probe ===");
		System.out.println("seed=" + SEED + " anchor=(" + (int) WINDOW_CENTER[0] + ","
				+ (int) WINDOW_CENTER[1] + "," + (int) WINDOW_CENTER[2] + ")"
				+ " EXTENT=" + (int) TwoFluidSolver.EXTENT + " DT=" + TwoFluidSolver.DT
				+ " RHO_BASE=" + TwoFluidSolver.CONDENSATION_RHO_BASE
				+ " AMPLITUDE=" + TwoFluidSolver.CONDENSATION_AMPLITUDE
				+ " RATE=" + TwoFluidSolver.CONDENSATION_RATE);
		System.out.println("condensation flag default OFF=" + TwoFluidSolver.CONDENSATION_ENABLED
				+ " (the gate proves the OFF path is byte-identical)");

		// The flag-OFF control is the falsified sponge — measure it first as the
		// honest baseline, then the ON run over the same settle set-points.
		Probe control = runProbe(false);
		Probe on = runProbe(true);

		System.out.println("\n[condensation] FLAG-OFF control (the falsified sponge):");
		System.out.println(control.text());
		System.out.println("\n[condensation] FLAG-ON run (domain condensation term):");
		System.out.println(on.text());

		String verdict = verdict(on, control);
		System.out.println("\n[condensation] VERDICT: " + verdict);
		// The probe is a measurement — it always exits 0 (the gate asserts the verdict).
	}

	/** Boot a fixed-seed worker with the term flag set, settle to each set-point
	 * in sequence, and measure the structure + no-mint at each. */
	private static Probe runProbe(boolean condensate) throws InterruptedException {
		TwoFluidSolver.CONDENSATION_ENABLED = condensate;
		try {
			SnapshotPublisher pub = new SnapshotPublisher();
			CassiFieldThread.Cfg cfg = new CassiFieldThread.Cfg(
					SEED, CassiFieldThread.JOB_STEP_CAP, CassiFieldThread.SNAPSHOT_CADENCE,
					new KernelLoader().load(), WINDOW_CENTER);
			CassiFieldThread worker = new CassiFieldThread(pub);
			worker.start(cfg);
			try {
				awaitGeneration(pub, 1, 12_000);
				Settle[] settles = new Settle[SETTLE_TARGETS.length];
				for (int i = 0; i < SETTLE_TARGETS.length; i++) {
					double target = SETTLE_TARGETS[i];
					FieldSnapshot snap = awaitT(pub, target);
					double[] wc = centerOf(snap, WINDOW_CENTER);
					settles[i] = measure(snap, wc, target);
					System.out.println((condensate ? "[condensation]" : "[control]") + " settled t="
							+ String.format("%.1f", snap.job().t()) + " → " + settles[i].line());
				}
				return new Probe(condensate, settles);
			} finally {
				worker.close();
			}
		} finally {
			TwoFluidSolver.CONDENSATION_ENABLED = false; // restore the default OFF
		}
	}

	/** Measure the vertical 3rd profile, coherent plane, total ρ/q, and the
	 * ε²/q distribution at a settle. */
	private static Settle measure(FieldSnapshot snap, double[] wc, double requestedT) {
		double[] vert = verticalThirdProfile(snap, wc);
		double top = vert[0], bottom = vert[1];
		int coherentY = SurfaceSpawn.findCoherentSurface(snap, wc,
				(int) Math.round(WINDOW_CENTER[0]), (int) Math.round(WINDOW_CENTER[2]),
				(int) Math.round(WINDOW_CENTER[1] + TwoFluidSolver.EXTENT));
		boolean standable = coherentY != Integer.MIN_VALUE;
		int patchSolid = standable ? patchSolidFraction(snap, wc, coherentY) : 0;
		// Total ρ/q over the FULL box (the no-mint check): sum of the published
		// per-cell channels. Also the q/ε² mean distribution over the field window.
		double totalRho = total(snap.rho());
		double totalQ = total(snap.q());
		double[] dist = rhoQDistribution(snap, wc);
		return new Settle(snap.job().t(), top, bottom, coherentY, standable, patchSolid,
				totalRho, totalQ, dist[0], dist[1], dist[2], dist[3], dist[4], dist[5]);
	}

	private static double total(float[] a) {
		double s = 0;
		for (float v : a) {
			s += v;
		}
		return s;
	}

	/** Top-third vs bottom-third mean solid fraction over the field x/z window
	 * (the {@code SurfaceEmergenceMain} approach — a real body has top ≪ bottom). */
	private static double[] verticalThirdProfile(FieldSnapshot snap, double[] wc) {
		int ext = (int) TwoFluidSolver.EXTENT;
		int xb0 = (int) WINDOW_CENTER[0] - ext, xb1 = (int) WINDOW_CENTER[0] + ext;
		int zb0 = (int) WINDOW_CENTER[2] - ext, zb1 = (int) WINDOW_CENTER[2] + ext;
		int yb0 = (int) WINDOW_CENTER[1] - ext, yb1 = (int) WINDOW_CENTER[1] + ext;
		int sideY = yb1 - yb0; // 192
		int third = sideY / 3;
		int step = 4;
		int[] solidCount = new int[sideY];
		int[] planeCount = new int[sideY];
		for (int z = zb0; z < zb1; z += step) {
			for (int x = xb0; x < xb1; x += step) {
				for (int dy = 0; dy < sideY; dy++) {
					int y = yb0 + dy;
					planeCount[dy]++;
					if (Quantizer.sampleAt(snap, wc, x, y, z).rho() >= Quantizer.TAU_C) {
						solidCount[dy]++;
					}
				}
			}
		}
		double topSum = 0, botSum = 0;
		int topN = 0, botN = 0;
		for (int dy = sideY - third; dy < sideY; dy++) {
			topSum += solidCount[dy] / (double) planeCount[dy];
			topN++;
		}
		for (int dy = 0; dy < third; dy++) {
			botSum += solidCount[dy] / (double) planeCount[dy];
			botN++;
		}
		return new double[] { topN > 0 ? topSum / topN : 0, botN > 0 ? botSum / botN : 0 };
	}

	/** The coherent-roof patch consistency at {@code y} (5×5 patch solid count). */
	private static int patchSolidFraction(FieldSnapshot snap, double[] wc, int y) {
		if (y == Integer.MIN_VALUE) {
			return 0;
		}
		int r = 2, solid = 0;
		for (int dz = -r; dz <= r; dz++) {
			for (int dx = -r; dx <= r; dx++) {
				if (Quantizer.sampleAt(snap, wc, (int) WINDOW_CENTER[0] + dx,
						y, (int) WINDOW_CENTER[2] + dz).rho() >= Quantizer.TAU_C) {
					solid++;
				}
			}
		}
		return solid;
	}

	/** Mean/max ρ, q, and ε² over the field x/z window at the anchor's mid-y
	 * (the body distribution + the term's decoherence cost). */
	private static double[] rhoQDistribution(FieldSnapshot snap, double[] wc) {
		int ext = (int) TwoFluidSolver.EXTENT;
		int step = 8;
		double rhoSum = 0, qSum = 0, rhoMax = 0, qMax = 0;
		double eps2Sum = 0, eps2Max = 0;
		int n = 0;
		int midY = (int) WINDOW_CENTER[1];
		for (int z = (int) WINDOW_CENTER[2] - ext; z < (int) WINDOW_CENTER[2] + ext; z += step) {
			for (int x = (int) WINDOW_CENTER[0] - ext; x < (int) WINDOW_CENTER[0] + ext; x += step) {
				Quantizer.CellSample s = Quantizer.sampleAt(snap, wc, x, midY, z);
				rhoSum += s.rho();
				qSum += s.q();
				rhoMax = Math.max(rhoMax, s.rho());
				qMax = Math.max(qMax, s.q());
				eps2Sum += s.eps2();
				eps2Max = Math.max(eps2Max, s.eps2());
				n++;
			}
		}
		return new double[] { n > 0 ? rhoSum / n : 0, n > 0 ? qSum / n : 0, rhoMax, qMax,
				n > 0 ? eps2Sum / n : 0, eps2Max };
	}

	/** The verdict — computed by the measurement, never forced. */
	private static String verdict(Probe on, Probe control) {
		Settle g = on.settles[on.settles.length - 1];
		Settle c = control.settles[control.settles.length - 1];
		boolean onGradient = g.topThirdFraction < GRADIENT_FRACTION * g.bottomThirdFraction;
		boolean controlGradient = c.topThirdFraction < GRADIENT_FRACTION * c.bottomThirdFraction;
		boolean plane = g.standable && g.coherentSolidY != Integer.MIN_VALUE;
		boolean organized = onGradient && !controlGradient;
		boolean noMint = g.totalRho <= NO_MINT_FRACTION * c.totalRho;
		// A decoherence blowup: the term's ε² cost exploded — a mean ε² at/above
		// the calibrated dissolution floor (Quantizer.EPS2_FLOOR = 0.35) means the
		// body's coherence has collapsed and the world would carve to air (the
		// corpus's dissolution threshold, chunk-field-quantization §2.2). That is
		// an honest INCONCLUSIVE — the term organized only by destroying coherence.
		boolean decohere = g.meanEps2 >= Quantizer.EPS2_FLOOR;
		if (organized && plane && noMint && !decohere) {
			return "SUPPORTS — the condensation term organizes a real vertical gradient (top<"
					+ GRADIENT_FRACTION + "×bottom) absent in the OFF sponge, with a standable coherent plane, and total ρ is bounded (no mint)";
		}
		if (!noMint) {
			return "CONTRADICTS(mint) — the term minted density (ON totalρ="
					+ String.format("%.1f", g.totalRho) + " vs OFF totalρ="
					+ String.format("%.1f", c.totalRho) + "; margin " + NO_MINT_FRACTION
					+ "×) — a failed design, not a silent feature";
		}
		if (decohere) {
			return "INCONCLUSIVE(decoherence-blowup) — the term ran the mean ε² to "
					+ String.format("%.3f", g.meanEps2) + " ≥ the EPS2_FLOOR ("
					+ Quantizer.EPS2_FLOOR + "), so any organized body would carve to air — a coherence collapse, not a surface";
		}
		if (!plane) {
			return "INCONCLUSIVE(no-standable-plane) — the term measured but no coherent standable plane was found at the mature settle";
		}
		return "CONTRADICTS — the term measured but did not organize a real vertical gradient"
				+ " (ON top=" + String.format("%.3f", g.topThirdFraction)
				+ " bottom=" + String.format("%.3f", g.bottomThirdFraction)
				+ "; OFF top=" + String.format("%.3f", c.topThirdFraction)
				+ " bottom=" + String.format("%.3f", c.bottomThirdFraction)
				+ "; gradient-margin " + GRADIENT_FRACTION + ")";
	}

	private static double[] centerOf(FieldSnapshot snap, double[] fallback) {
		return snap.job() != null && !snap.job().isWindowless()
				? snap.job().windowCenter()
				: fallback.clone();
	}

	private static FieldSnapshot awaitGeneration(SnapshotPublisher pub, int gen, long timeoutMs)
			throws InterruptedException {
		long deadline = System.currentTimeMillis() + timeoutMs;
		while (System.currentTimeMillis() < deadline) {
			FieldSnapshot s = pub.freshest();
			if (s != null && s.generation() >= gen) {
				return s;
			}
			Thread.sleep(20);
		}
		throw new IllegalStateException("field never reached generation " + gen);
	}

	private static FieldSnapshot awaitT(SnapshotPublisher pub, double t) throws InterruptedException {
		long deadline = System.currentTimeMillis() + SETTLE_TIMEOUT_MS;
		while (System.currentTimeMillis() < deadline) {
			FieldSnapshot s = pub.freshest();
			if (s != null && s.job() != null && s.job().t() >= t) {
				return s;
			}
			Thread.sleep(20);
		}
		throw new IllegalStateException("field never reached t=" + t);
	}

	/** One settle measurement. */
	private record Settle(double reachedT, double topThirdFraction, double bottomThirdFraction,
			int coherentSolidY, boolean standable, int patchSolid,
			double totalRho, double totalQ, double meanRho, double meanQ, double maxRho, double maxQ,
			double meanEps2, double maxEps2) {
		String line() {
			return "t=" + String.format("%.1f", reachedT)
					+ " topThird=" + String.format("%.3f", topThirdFraction)
					+ " bottomThird=" + String.format("%.3f", bottomThirdFraction)
					+ " coherentY=" + (coherentSolidY == Integer.MIN_VALUE ? "-" : coherentSolidY)
					+ " standable=" + standable + " patch=" + patchSolid + "/25"
					+ " totalρ=" + String.format("%.1f", totalRho)
					+ " totalq=" + String.format("%.1f", totalQ)
					+ " meanρ=" + String.format("%.3f", meanRho) + " meanq=" + String.format("%.3f", meanQ)
					+ " maxρ=" + String.format("%.3f", maxRho) + " maxq=" + String.format("%.3f", maxQ)
					+ " meanε²=" + String.format("%.3f", meanEps2) + " maxε²=" + String.format("%.3f", maxEps2);
		}
	}

	/** A full probe run: per-settle measurements over the settle spread. */
	private record Probe(boolean condensate, Settle[] settles) {
		String text() {
			StringBuilder sb = new StringBuilder();
			sb.append("  condensation=").append(condensate).append('\n');
			for (Settle s : settles) {
				sb.append("  ").append(s.line()).append('\n');
			}
			return sb.toString();
		}
	}

	private CondensationProbeMain() {
	}
}
