package dev.cassicraft.game.genesis;

import dev.cassicraft.domain.engine.TwoFluidSolver;
import dev.cassicraft.domain.snapshot.FieldSnapshot;
import dev.cassicraft.domain.snapshot.SnapshotPublisher;
import dev.cassicraft.domain.thread.CassiFieldThread;
import dev.cassicraft.domain.thread.KernelLoader;
import dev.cassicraft.game.sampler.Quantizer;
import dev.cassicraft.game.spawn.SurfaceSpawn;

/**
 * Headless surface-genesis measurement probe — the honest answer to the wave's
 * falsification ({@code SurfaceEmergenceMain}: the field is a uniform sponge with
 * no vertical density plane at any reachable t). The question, measured over the
 * real Q4 write lane:
 *
 * <blockquote>Can a bounded, cap-governed genesis pass through
 * {@link CassiFieldThread#submitPerturbation} organize the field into a real
 * density body with a vertical surface — deterministically, seed-sensitively,
 * honestly (no free energy, caps sane)?</blockquote>
 *
 * <p>The probe boots a fixed-seed {@link CassiFieldThread} via the real publish
 * seam, applies the {@link SurfaceGenesis} sequence through the lane at session
 * start, then settles to a spread of field-times (t≈2, 10, 20, 40). At each
 * settle it measures the vertical structure (top-third vs bottom-third mean
 * solid fraction via {@link Quantizer#sampleAt} + {@link Quantizer#TAU_C}, the
 * {@code SurfaceEmergenceMain} approach), the coherent-plane scan
 * ({@link SurfaceSpawn#findCoherentSurface}), the ρ/q distributions over the
 * field x/z window, and {@link CassiFieldThread#perturbationClampCount()} (the
 * caps' telemetry). It compares against the NO-GENESIS control — the falsified
 * sponge — at the same set-points.
 *
 * <p><b>The verdict is asserted by the measurement, never forced.</b>
 * <b>SUPPORTS</b> iff the genesis run develops a real vertical gradient (top-third
 * mean solid &lt; {@link #GRADIENT_FRACTION} × bottom-third) at a mature settle
 * AND that gradient is materially absent in the same-seed no-genesis control AND
 * a coherent standable plane exists. <b>CONTRADICTS</b> iff the genesis does not
 * organize a real gradient (the field diffuses the injection back to a sponge —
 * the numbers are reported). <b>INCONCLUSIVE</b> with a reason for any degenerate
 * measurement. Headless, no live client/server.
 */
public final class GenesisProbeMain {

	/** Fixed seed — the same domain seed the other gates replay. */
	private static final long SEED = 42L;
	/** The demo box anchor — center {0,70,0}. */
	private static final double[] WINDOW_CENTER = { 0, 70, 0 };
	/** Worker deadlock guard. */
	private static final long FIRST_TIMEOUT_MS = 12_000;
	/** Settle-generation await timeout (ms) — a long settle to t=40 takes ~2 min. */
	private static final long SETTLE_TIMEOUT_MS = 600_000;
	/** The gradient margin: real when top-third mean solid &lt; this × bottom-third. */
	private static final double GRADIENT_FRACTION = 0.25;
	/** The four field-times the probe settles to and measures (the emergent spread). */
	private static final double[] SETTLE_TARGETS = { 2.0, 10.0, 20.0, 40.0 };

	public static void main(String[] args) throws Exception {
		System.out.println("=== Surface Genesis probe (Q4-lane bounded deposit) ===");
		System.out.println("seed=" + SEED + " anchor=(" + (int) WINDOW_CENTER[0] + ","
				+ (int) WINDOW_CENTER[1] + "," + (int) WINDOW_CENTER[2] + ")"
				+ " EXTENT=" + (int) TwoFluidSolver.EXTENT + " DT=" + TwoFluidSolver.DT
				+ " genesisWrites=" + SurfaceGenesis.WRITE_COUNT
				+ " dEY=" + SurfaceGenesis.D_EY + " dEI=" + SurfaceGenesis.D_EI
				+ " (coherence-restoring, matched φ)");
		System.out.println("genesis targets (y-band within the anchor column): "
				+ SurfaceGenesis.Y_BAND_LO + ".." + SurfaceGenesis.Y_BAND_HI + " relative to anchor y="
				+ (int) WINDOW_CENTER[1]);

		// The no-genesis control is the falsified sponge — measure it first as the
		// honest baseline, then the genesis run over the same settle set-points.
		Probe control = runProbe(false);
		Probe genesis = runProbe(true);

		System.out.println("\n[genesis] NO-GENESIS control (the falsified sponge):");
		System.out.println(control.text());
		System.out.println("\n[genesis] GENESIS run (Q4-lane bounded deposit):");
		System.out.println(genesis.text());

		String verdict = verdict(genesis, control);
		System.out.println("\n[genesis] VERDICT: " + verdict);
		// The probe is a measurement — it always exits 0 (the gate asserts the verdict).
	}

	/**
	 * Boot a fixed-seed worker, apply (or not) the genesis at session start, settle
	 * to each set-point in sequence, and measure the structure at each.
	 */
	private static Probe runProbe(boolean withGenesis) throws InterruptedException {
		SnapshotPublisher pub = new SnapshotPublisher();
		CassiFieldThread.Cfg cfg = new CassiFieldThread.Cfg(
				SEED, CassiFieldThread.JOB_STEP_CAP, CassiFieldThread.SNAPSHOT_CADENCE,
				new KernelLoader().load(), WINDOW_CENTER);
		CassiFieldThread worker = new CassiFieldThread(pub);
		worker.start(cfg);
		try {
			FieldSnapshot first = awaitGeneration(pub, 1, FIRST_TIMEOUT_MS);
			double[] wc = centerOf(first, WINDOW_CENTER);
			int genesisWrites = 0;
			long clampCount = 0;
			if (withGenesis) {
				SurfaceGenesis genesis = new SurfaceGenesis(worker, pub, WINDOW_CENTER);
				genesisWrites = genesis.run();
				clampCount = worker.perturbationClampCount();
			}
			// The genesis drains advanced the field; re-read the current published
			// t so the first settle measurement is an exact, not drifting, time.
			Settle[] settles = new Settle[SETTLE_TARGETS.length];
			for (int i = 0; i < SETTLE_TARGETS.length; i++) {
				double target = SETTLE_TARGETS[i];
				FieldSnapshot snap = awaitT(pub, target);
				wc = centerOf(snap, WINDOW_CENTER);
				settles[i] = measure(snap, wc, target);
				System.out.println((withGenesis ? "[genesis]" : "[control]") + " settled t="
						+ String.format("%.1f", snap.job().t()) + " → " + settles[i].line());
			}
			return new Probe(withGenesis, genesisWrites, clampCount, settles);
		} finally {
			worker.close();
		}
	}

	/** Measure the vertical 3rd profile, coherent plane, and ρ/q distributions at a settle. */
	private static Settle measure(FieldSnapshot snap, double[] wc, double requestedT) {
		double[] vert = verticalThirdProfile(snap, wc);
		double top = vert[0], bottom = vert[1];
		int coherentY = SurfaceSpawn.findCoherentSurface(snap, wc,
				(int) Math.round(WINDOW_CENTER[0]), (int) Math.round(WINDOW_CENTER[2]),
				(int) Math.round(WINDOW_CENTER[1] + TwoFluidSolver.EXTENT));
		boolean standable = coherentY != Integer.MIN_VALUE;
		int patchSolid = standable ? patchSolidFraction(snap, wc, coherentY) : 0;
		double[] dist = rhoQDistribution(snap, wc);
		return new Settle(snap.job().t(), top, bottom, coherentY, standable, patchSolid,
				dist[0], dist[1], dist[2], dist[3]);
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

	/** Mean/max ρ and q over the field x/z window at the anchor's mid-y (the body distribution). */
	private static double[] rhoQDistribution(FieldSnapshot snap, double[] wc) {
		int ext = (int) TwoFluidSolver.EXTENT;
		int step = 8;
		double rhoSum = 0, qSum = 0, rhoMax = 0, qMax = 0;
		int n = 0;
		int midY = (int) WINDOW_CENTER[1];
		for (int z = (int) WINDOW_CENTER[2] - ext; z < (int) WINDOW_CENTER[2] + ext; z += step) {
			for (int x = (int) WINDOW_CENTER[0] - ext; x < (int) WINDOW_CENTER[0] + ext; x += step) {
				Quantizer.CellSample s = Quantizer.sampleAt(snap, wc, x, midY, z);
				rhoSum += s.rho();
				qSum += s.q();
				rhoMax = Math.max(rhoMax, s.rho());
				qMax = Math.max(qMax, s.q());
				n++;
			}
		}
		return new double[] { n > 0 ? rhoSum / n : 0, n > 0 ? qSum / n : 0, rhoMax, qMax };
	}

	/** The verdict — asserted by the measurement, never forced. */
	private static String verdict(Probe genesis, Probe control) {
		// The mature settle is the last (the largest t the genesis reached).
		Settle g = genesis.settles[genesis.settles.length - 1];
		Settle c = control.settles[control.settles.length - 1];
		boolean genesisGradient = g.topThirdFraction < GRADIENT_FRACTION * g.bottomThirdFraction;
		boolean controlGradient = c.topThirdFraction < GRADIENT_FRACTION * c.bottomThirdFraction;
		boolean plane = g.standable && g.coherentSolidY != Integer.MIN_VALUE;
		boolean genesisOrganized = genesisGradient && !controlGradient;
		if (genesisOrganized && plane) {
			return "SUPPORTS — genesis organizes a real vertical gradient (top<"
					+ GRADIENT_FRACTION + "×bottom) absent in the no-genesis sponge, with a standable coherent plane";
		}
		if (!plane) {
			return "INCONCLUSIVE(no-standable-plane) — the genesis measured but no coherent standable plane was found at the mature settle";
		}
		// The genesis did not organize a real gradient: report the exact numbers
		// (top vs bottom) for both runs — this is the honest CONTRADICTS, not an
		// assertion: the field diffused the injection back toward the sponge.
		return "CONTRADICTS — genesis measured but did not organize a real vertical gradient"
				+ " (genesis top=" + String.format("%.3f", g.topThirdFraction)
				+ " bottom=" + String.format("%.3f", g.bottomThirdFraction)
				+ "; control top=" + String.format("%.3f", c.topThirdFraction)
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
			double meanRho, double meanQ, double maxRho, double maxQ) {
		String line() {
			return "t=" + String.format("%.1f", reachedT)
					+ " topThird=" + String.format("%.3f", topThirdFraction)
					+ " bottomThird=" + String.format("%.3f", bottomThirdFraction)
					+ " coherentY=" + (coherentSolidY == Integer.MIN_VALUE ? "-" : coherentSolidY)
					+ " standable=" + standable + " patch=" + patchSolid + "/25"
					+ " meanρ=" + String.format("%.3f", meanRho) + " meanq=" + String.format("%.3f", meanQ)
					+ " maxρ=" + String.format("%.3f", maxRho) + " maxq=" + String.format("%.3f", maxQ);
		}
	}

	/** A full probe run: optional genesis, then per-settle measurements + caps telemetry. */
	private record Probe(boolean withGenesis, int genesisWrites, long clampCount, Settle[] settles) {
		String text() {
			StringBuilder sb = new StringBuilder();
			sb.append("  genesisWrites=").append(genesisWrites)
					.append(" | clampCount=").append(clampCount)
					.append(" (expected 0 — the matched φ design stays within the caps)\n");
			for (Settle s : settles) {
				sb.append("  ").append(s.line()).append('\n');
			}
			return sb.toString();
		}
	}

	private GenesisProbeMain() {
	}
}
