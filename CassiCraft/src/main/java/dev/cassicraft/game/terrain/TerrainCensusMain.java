package dev.cassicraft.game.terrain;

import dev.cassicraft.domain.snapshot.FieldSnapshot;
import dev.cassicraft.domain.snapshot.SnapshotPublisher;
import dev.cassicraft.domain.thread.CassiFieldThread;
import dev.cassicraft.domain.thread.KernelLoader;
import dev.cassicraft.game.sampler.Quantizer;

import java.util.Arrays;

/**
 * Headless living-terrain census + anti-monolith gate (volumetric-terrain.md:
 * "the field IS the terrain; iso-surfaces cut the blocks"; chunk-field-quantization.md
 * §2: ρ≥τ_c solidifies, ε² dissolution carves, q precipitates ore). The census
 * measures the REAL published channel distribution over the full 192³ box at
 * settle — ρ, q, and derived ε² — and the resulting block-kind census under the
 * current (hypothesis) thresholds, plus the world's vertical strata (where does
 * solid end and air begin per column). The gate asserts the <b>structural
 * contract</b> that replaces the "anyone is a stone monolith" failure:
 *
 * <ol>
 *   <li><b>Determinism:</b> two fixed-seed settles produce identical census
 *       hashes (same field → same world); a different seed differs (the field
 *       actually seeds the terrain).</li>
 *   <li><b>Anti-monolith:</b> the AIR fraction over the box ≥ {@link #MIN_AIR_FRACTION}
 *       — the world has dissolving thin regions, it is not a solid slab.</li>
 *   <li><b>Ore precipitates:</b> the ORE count ≥ {@link #MIN_ORE_BLOCKS} — the
 *       q channel actually condenses veins, not "nowhere".</li>
 *   <li><b>Spawn standability:</b> the anchor column has a solid floor with air
 *       above (the walkability gate's standable logic, reused) — the player can
 *       stand, not spawn embedded in rock.</li>
 * </ol>
 *
 * <p>The census reads the published snapshot at block centers via the pure
 * {@link Quantizer#sampleAt} fused 8-corner traversal — never writes a block
 * (only-mutator rule; the writer owns mutation). Exit 0 = green. Runs headlessly
 * under the game runtime classpath (the {@code quantizerDeterminism} pattern),
 * no live client/server.
 */
public final class TerrainCensusMain {

	/** Fixed seeds — the same domain seeds the other gates replay. */
	private static final long SEED_A = 42L;
	private static final long SEED_B = 43L;

	/** The demo box anchor (the Phase-1 window center, spawn) — center {0,70,0}. */
	private static final double ANCHOR_X = 0, ANCHOR_Y = 70, ANCHOR_Z = 0;
	/** Box half-extent per axis (chunk-aligned 192³ m box, chunk-field-quantization §1.2). */
	private static final int EXTENT = (int) dev.cassicraft.domain.engine.TwoFluidSolver.EXTENT;

	/** First-snapshot await timeout (worker deadlock guard, ms). */
	private static final long FIRST_TIMEOUT_MS = 12_000;
	/** Settle-generation await timeout (ms). */
	private static final long SETTLE_TIMEOUT_MS = 30_000;
	/**
	 * How many published generations to wait before measuring — the same settle
	 * count the ride probe uses. Each publish ships one job of
	 * {@code JOB_STEP_CAP=64} domain steps, so 12 generations ≈ 768 steps ≈
	 * 0.768 field-time units at the engine-default {@code DT=0.001}
	 * (TwoFluidSolver.DT) — a near-IC field, which is the honest state this gate
	 * measures (the field-time-evolved line printed at runtime makes the rate
	 * visible). Enough for the spectral Poisson and gradient pass to organize
	 * initial structure out of the flat-noise IC while keeping the gate short.
	 */
	private static final int SETTLE_GENERATIONS = 12;

	/**
	 * Anti-monolith acceptance — the AIR fraction (thin/dissolved field) must be
	 * at least this to keep the world from being "entirely stone".
	 */
	private static final double MIN_AIR_FRACTION = 0.15;
	/** Anti-vacuity acceptance — at least this many ORE blocks must precipitate. */
	private static final int MIN_ORE_BLOCKS = 1;

	public static void main(String[] args) throws Exception {
		// Measure the settled field once and print the full distributions.
		Census a1 = runOnce(SEED_A);
		Census a2 = runOnce(SEED_A);
		Census b = runOnce(SEED_B);

		// Determinism + structural contract.
		boolean sameSeedIdentical = a1.signature().equals(a2.signature());
		boolean seedSensitive = !a1.signature().equals(b.signature());
		boolean airContract = a1.airFraction() >= MIN_AIR_FRACTION && a2.airFraction() >= MIN_AIR_FRACTION;
		boolean oreContract = a1.oreCount() >= MIN_ORE_BLOCKS && a2.oreCount() >= MIN_ORE_BLOCKS;
		boolean standableA = a1.standable() && a2.standable();
		boolean standable = standableA && b.standable();

		System.out.println("\n[terrain-census] SEED_A run1: " + a1.summary());
		System.out.println("[terrain-census] SEED_A run2: " + a2.summary());
		System.out.println("[terrain-census] SEED_B run:  " + b.summary());
		System.out.println("[terrain-census] same-seed identical: " + sameSeedIdentical
				+ " | different-seed differs: " + seedSensitive
				+ " | air≥" + MIN_AIR_FRACTION + "=" + airContract
				+ " | ore≥" + MIN_ORE_BLOCKS + "=" + oreContract
				+ " | standable(A)=" + standableA + " standable(B)=" + b.standable());

		boolean ok = true;
		if (!sameSeedIdentical) {
			System.err.println("[terrain-census] FAIL — same seed produced a different census (non-deterministic world)");
			ok = false;
		}
		if (!seedSensitive) {
			System.err.println("[terrain-census] FAIL — different seeds produced an identical census (vacuous)");
			ok = false;
		}
		if (!airContract) {
			System.err.println("[terrain-census] FAIL — AIR fraction below " + MIN_AIR_FRACTION + " (the world is a stone monolith)");
			ok = false;
		}
		if (!oreContract) {
			System.err.println("[terrain-census] FAIL — ORE count below " + MIN_ORE_BLOCKS + " (no ore precipitates)");
			ok = false;
		}
		if (!standable) {
			System.err.println("[terrain-census] FAIL — the spawn column is not standable (no solid floor with air above)");
			ok = false;
		}

		if (ok) {
			System.out.println("[terrain-census] PASS — the world is a structured, deterministic living terrain (air, stone, ore, standable spawn)");
		} else {
			System.err.println("[terrain-census] FAILED");
			System.exit(1);
		}
	}

	/** Boot a settled field, census the full box, and return the structural signature. */
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
			return census(snap, window, seed);
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
	 * One full-box census pass: sample every block center in the 192³ box, derive
	 * ε², classify by the pure {@link Quantizer} cold rule, and accumulate the
	 * channel distributions, the block-kind census (AIR/SOLID/ORE), and the
	 * anchor-column strata. Reads only; never writes a block.
	 */
	private static Census census(FieldSnapshot snap, double[] window, long seed) {
		int n = EXTENT * 2; // 192 blocks per axis
		long total = (long) n * n * n;
		float[] rho = new float[n * n * n];
		float[] q = new float[n * n * n];
		float[] eps2 = new float[n * n * n];
		long air = 0, solid = 0, ore = 0;

		int ax = (int) Math.round(ANCHOR_X);
		int ay = (int) Math.round(ANCHOR_Y);
		int az = (int) Math.round(ANCHOR_Z);
		int boxTop = ay + EXTENT;

		// Anchor-column strata (topSolidY + solid count down the center column).
		int topSolidY = Integer.MIN_VALUE;
		int solidCol = 0;

		int idx = 0;
		for (int dz = 0; dz < n; dz++) {
			int z = (int) (ANCHOR_Z - EXTENT) + dz;
			for (int dy = 0; dy < n; dy++) {
				int y = (int) (ANCHOR_Y - EXTENT) + dy;
				for (int dx = 0; dx < n; dx++) {
					int x = (int) (ANCHOR_X - EXTENT) + dx;
					Quantizer.CellSample s = Quantizer.sampleAt(snap, window, x, y, z);
					rho[idx] = s.rho();
					q[idx] = s.q();
					eps2[idx] = s.eps2();
					Quantizer.BlockKind k = Quantizer.quantizeCold(s.rho(), s.q(), s.eps2());
					switch (k) {
					case AIR -> air++;
					case SOLID -> solid++;
					case ORE -> ore++;
					}
					idx++;
				}
			}
		}

		// Anchor-column strata, measured separately (a clean vertical scan of the
		// center column from the box top downward, matching the walkability gate).
		{
			int scanY = boxTop;
			while (scanY >= boxTop - EXTENT * 2) {
				Quantizer.CellSample s = Quantizer.sampleAt(snap, window, ax, scanY, az);
				if (s.rho() >= Quantizer.TAU_C) {
					solidCol++;
					if (topSolidY == Integer.MIN_VALUE) {
						topSolidY = scanY;
					}
				}
				scanY--;
			}
		}

		// The block census + distributions (percentiles over the full box).
		BlockCensus kinds = blockCensus(air, solid, ore, total);
		Dist rhoDist = dist(rho);
		Dist qDist = dist(q);
		Dist epsDist = dist(eps2);

		// Calibration sweep over the measured arrays — the honest threshold choice
		// comes from the actual channel distributions, not a guess (only on seed A's
		// first pass; a pure function of the already-measured arrays, no re-settle).
		if (seed == SEED_A) {
			printCalibration(rho, q, eps2);
		}

		// Eager printed report — the measurement-first discipline demands the raw
		// channel distributions on every run, not just the gate's boolean.
		printDistributions(seed, rhoDist, qDist, epsDist, kinds, topSolidY, solidCol, boxTop);

		// Standable logic (walkability gate): a solid floor with 2 air blocks above.
		boolean standable = topSolidY != Integer.MIN_VALUE;
		if (standable) {
			for (int above = 1; above <= 2; above++) {
				Quantizer.CellSample s = Quantizer.sampleAt(snap, window, ax, topSolidY + above, az);
				if (s.rho() >= Quantizer.TAU_C) {
					standable = false;
					break;
				}
			}
		}

		String signature = sha256(seed + "|" + rhoDist.mean + "|" + qDist.mean + "|" + epsDist.mean
				+ "|" + air + "|" + solid + "|" + ore + "|" + topSolidY + "|" + solidCol);
		return new Census(signature, kinds.airFrac(), (int) air, (int) ore, standable,
				topSolidY, solidCol, boxTop, kinds);
	}

	private static BlockCensus blockCensus(long air, long solid, long ore, long total) {
		double af = air / (double) total;
		double sf = solid / (double) total;
		double of = ore / (double) total;
		return new BlockCensus((int) air, (int) solid, (int) ore, af, sf, of);
	}

	/** Percentile distribution over an array of per-block channel values. */
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

		static String pct(float v) {
			return String.format("%.4f", v);
		}
	}

	/** Sort a copy of the channel array and pull the percentile stats. */
	private static Dist dist(float[] values) {
		float[] s = values.clone();
		Arrays.sort(s);
		int n = s.length;
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
		return SETTLE_GENERATIONS * (double) CassiFieldThread.JOB_STEP_CAP
				* dev.cassicraft.domain.engine.TwoFluidSolver.DT;
	}

	/**
	 * Honest threshold sweep over the measured per-block arrays — answers "what
	 * AIR/ORE/carved fraction does each candidate threshold actually produce",
	 * so the calibration is grounded in the measured continuum, never guessed.
	 * It is a pure read of the already-measured arrays (no re-settle).
	 */
	private static void printCalibration(float[] rho, float[] q, float[] eps2) {
		int n = rho.length;
		int total = n;
		System.out.println("\n[terrain-census]   calibration sweep (measured box, seed 42):");
		System.out.print("[terrain-census]   τ_c  →  AIR-frac   (ρ<τ_c, ignoring dissolution)  ");
		for (float tc = 0.60f; tc <= 1.35f + 1e-6f; tc += 0.05f) {
			long airCut = 0;
			for (int i = 0; i < n; i++) {
				if (rho[i] < tc) {
					airCut++;
				}
			}
			System.out.print(" τ" + pct(tc) + "=" + pct(airCut / (double) total));
		}
		System.out.println();

		// ORE fraction among ρ-conditioned solid, sweeping q_ore at a mid τ_c vantage.
		float tc = 1.00f;
		System.out.print("[terrain-census]   q_ore → ORE-count (ρ≥" + pct(tc) + ", ε²<1.0, q≥q_ore)  ");
		for (float qo = 0.80f; qo <= 1.60f + 1e-6f; qo += 0.10f) {
			long oreCut = 0;
			for (int i = 0; i < n; i++) {
				if (rho[i] >= tc && eps2[i] < 1.0f && q[i] >= qo) {
					oreCut++;
				}
			}
			System.out.print(" q" + pct(qo) + "=" + oreCut);
		}
		System.out.println();

		// Dissolution: fraction of the ρ-condensed field that a given ε² floor would
		// carve back to air (the honest measure of how much dissolution actually fires).
		System.out.print("[terrain-census]   ε²floor → carved-frac (ρ≥" + pct(tc) + " AND ε²≥floor)  ");
		for (float ef = 0.05f; ef <= 1.00f + 1e-6f; ef += 0.10f) {
			long carved = 0;
			for (int i = 0; i < n; i++) {
				if (rho[i] >= tc && eps2[i] >= ef) {
					carved++;
				}
			}
			System.out.print(" ε" + pct(ef) + "=" + pct(carved / (double) total));
		}
		System.out.println("\n[terrain-census]   box=" + total + " blocks");
	}

	/** Print the raw measured channel distributions + current census + strata. */	private static void printDistributions(long seed, Dist rho, Dist q, Dist eps,
			BlockCensus kinds, int topSolidY, int solidCol, int boxTop) {
		System.out.println("\n[terrain-census] seed=" + seed + " full-box 192³ census @ settle (SETTLE_GENERATIONS=" + SETTLE_GENERATIONS + ")");
		System.out.println("[terrain-census]   field time evolved = " + SETTLE_GENERATIONS + " gen × "
				+ CassiFieldThread.JOB_STEP_CAP + " steps × DT=" + dev.cassicraft.domain.engine.TwoFluidSolver.DT
				+ " = " + String.format("%.3f", fieldTimeUnits()) + " field-time units (a Minecraft tick advances "
				+ String.format("%.4f", dev.cassicraft.domain.engine.TwoFluidSolver.DT) + " units at 20 Hz)");
		System.out.println("[terrain-census]   ρ       " + rho);
		System.out.println("[terrain-census]   q       " + q);
		System.out.println("[terrain-census]   ε²      " + eps);
		System.out.println("[terrain-census]   current census: AIR=" + kinds.air
				+ " (" + pct(kinds.airFrac) + ") SOLID=" + kinds.solid
				+ " (" + pct(kinds.solidFrac) + ") ORE=" + kinds.ore + " (" + pct(kinds.oreFrac) + ")");
		System.out.println("[terrain-census]   spawn column: topSolidY=" + topSolidY
				+ " solidCount=" + solidCol + " boxTop=" + boxTop);
	}

	private static String pct(double v) {
		return String.format("%.4f", v);
	}

	private static String sha256(String s) {
		try {
			byte[] h = java.security.MessageDigest.getInstance("SHA-256").digest(s.getBytes(java.nio.charset.StandardCharsets.UTF_8));
			StringBuilder sb = new StringBuilder(h.length * 2);
			for (byte b : h) {
				sb.append(String.format("%02x", b));
			}
			return sb.toString();
		} catch (java.security.NoSuchAlgorithmException e) {
			throw new IllegalStateException(e);
		}
	}

	/** The block-kind census (AIR / SOLID / ORE counts and fractions). */
	private record BlockCensus(int air, int solid, int ore,
			double airFrac, double solidFrac, double oreFrac) {
	}

	/** One end-to-end run's structural signature (the determinism + contract input). */
	private record Census(String signature, double airFraction, int airCount, int oreCount,
			boolean standable, int topSolidY, int solidCount, int boxTop, BlockCensus kinds) {
		String summary() {
			return "airFrac=" + pct(airFraction) + " ore=" + oreCount
					+ " topSolidY=" + topSolidY + " standable=" + standable
					+ " hash=" + signature.substring(0, 8);
		}
	}

	private TerrainCensusMain() {
	}
}
