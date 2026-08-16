package dev.cassicraft.game.surface;

import dev.cassicraft.domain.engine.TwoFluidSolver;
import dev.cassicraft.domain.snapshot.FieldSnapshot;
import dev.cassicraft.domain.snapshot.SnapshotPublisher;
import dev.cassicraft.domain.thread.CassiFieldThread;
import dev.cassicraft.domain.thread.KernelLoader;
import dev.cassicraft.game.sampler.Quantizer;

/**
 * Headless surface + follow-behind diagnostics probe for the owner's priority
 * report — "the world moves through space, but the player doesn't move with
 * it" and "the world is mostly stone with no surface". Built on the proven
 * census pattern (TerrainCensusMain): a fixed-seed {@link CassiFieldThread} via
 * the real publish seam, settled to a named generation, measured at block
 * centers through the pure {@link Quantizer} — never writes a block
 * (only-mutator rule; the writer owns mutation). Runs headlessly under the
 * game runtime classpath, no live client/server.
 *
 * <p>Four measurements answer the two symptoms with numbers:
 *
 * <ol>
 *   <li><b>M1 — vertical structure (the "no surface" truth):</b> the solid
 *       fraction per y-stratum over the full 192³ box, the topSolidY
 *       distribution across a coarse column grid (is there a coherent ground
 *       plane or a random sponge?), and the anchor column's own profile.</li>
 *   <li><b>M2 — the spawn reality:</b> the exact {@code SurfaceSpawn} scan
 *       (first solid down the anchor column from the box top) and the 32³
 *       census around the respawn it would set.</li>
 *   <li><b>M3 — the follow-behind stability (the "world moves" truth):</b> a
 *       fixed world block sampled before/after a real whole-cell re-home
 *       (exact equality or float drift), and the full sampler re-quantization
 *       of a player-vicinity 32³ box across the re-home — how many blocks flip
 *       kind (the "world moves under the player" rate).</li>
 *   <li><b>M4 — the churn rate:</b> at {@code DT=0.001} the player-vicinity
 *       box re-quantized at two settle generations — how alive is the terrain
 *       per wall-clock time.</li>
 * </ol>
 *
 * <p>Exit 0 = green (the probe always prints; it fails only on timeout or an
 * internal contradiction). Prints the full measured report; the fix decision
 * is made from these numbers in the caller's report, never before.
 */
public final class SurfaceDiagnosticsMain {

	/** Fixed seeds — the same domain seeds the other gates replay. */
	private static final long SEED_A = 42L;
	/** The demo box anchor (the Phase-1 window center, spawn) — center {0,70,0}. */
	private static final double ANCHOR_X = 0, ANCHOR_Y = 70, ANCHOR_Z = 0;
	/** Box half-extent per axis (chunk-aligned 192³ m box, chunk-field-quantization §1.2). */
	private static final int EXTENT = (int) TwoFluidSolver.EXTENT;
	/** Worker deadlock guard. */
	private static final long FIRST_TIMEOUT_MS = 12_000;
	/** Settle-generation await timeout (ms). */
	private static final long SETTLE_TIMEOUT_MS = 30_000;
	/** The early settle — matches the census gate's 12-generation settle. */
	private static final int SETTLE_EARLY = 12;
	/** The late settle — a later generation to see the {@code DT=0.001} evolution/churn. */
	private static final int SETTLE_LATE = 30;
	/** The player-vicinity 32³ radius (blocks), matching TickSampler.VICINITY_RADIUS. */
	private static final int VICINITY_RADIUS = 16;

	public static void main(String[] args) throws Exception {
		System.out.println("=== Surface Diagnostics — owner priority report ===");
		System.out.println("seed=" + SEED_A + " anchor=(" + (int) ANCHOR_X + "," + (int) ANCHOR_Y + "," + (int) ANCHOR_Z
				+ ") EXTENT=" + EXTENT + " box=[" + (int) (ANCHOR_Y - EXTENT) + "," + (int) (ANCHOR_Y + EXTENT) + "]"
				+ " DT=" + TwoFluidSolver.DT + " (engine default)");

		// M1 + M2: one settled worker; full-box vertical structure + surface spawn reality.
		FieldSnapshot settle = settleWorker(SEED_A, SETTLE_EARLY);
		measureVerticalStructure(settle);
		int spawnY = measureSpawnReality(settle);
		if (spawnY == Integer.MIN_VALUE) {
			spawnY = (int) ANCHOR_Y; // no spawn column solid — fall back to the box center for the vicinity anchors
		}
		int finalSpawnY = spawnY;

		// M3: the follow-behind re-home — world-fixedness + player-vicinity flip rate.
		measureFollowBehind(finalSpawnY);

		// M4: the churn rate — same player-vicinity box at two settle generations.
		measureChurn(finalSpawnY);

		// M5: the coherent-surface fix — where does the coherent-plane spawn land,
		// and is it a real multi-column roof (not a single-column blob)?
		measureCoherentSurface(settle);

		System.out.println("\n[surface-diagnostics] done");
	}

	// --- boot helpers --------------------------------------------------------

	/** Boot a fixed-seed field, settle to a named generation, and return the snapshots it produced. */
	private static FieldSnapshot settleWorker(long seed, int settleGen) throws InterruptedException {
		double[] anchor = { ANCHOR_X, ANCHOR_Y, ANCHOR_Z };
		SnapshotPublisher pub = new SnapshotPublisher();
		CassiFieldThread.Cfg cfg = new CassiFieldThread.Cfg(
				seed, CassiFieldThread.JOB_STEP_CAP, CassiFieldThread.SNAPSHOT_CADENCE,
				new KernelLoader().load(), anchor);
		CassiFieldThread worker = new CassiFieldThread(pub);
		worker.start(cfg);
		try {
			FieldSnapshot snap = awaitGen(pub, settleGen);
			return snap;
		} finally {
			worker.close();
		}
	}

	/** Await a snapshot at a publish generation ≥ the given generation. */
	private static FieldSnapshot awaitGen(SnapshotPublisher pub, int gen) throws InterruptedException {
		long deadline = System.currentTimeMillis() + SETTLE_TIMEOUT_MS;
		while (System.currentTimeMillis() < deadline) {
			FieldSnapshot s = pub.freshest();
			if (s != null && s.generation() >= gen) {
				return s;
			}
			Thread.sleep(20);
		}
		throw new IllegalStateException("field never reached generation " + gen + " within timeout");
	}

	/** The snapshot's published window center, falling back to the Cfg anchor if absent. */
	private static double[] centerOf(FieldSnapshot snap) {
		return (snap.job() != null && !snap.job().isWindowless())
				? snap.job().windowCenter()
				: new double[] { ANCHOR_X, ANCHOR_Y, ANCHOR_Z };
	}

	// --- M1: vertical structure ----------------------------------------------

	/**
	 * M1 — the "no surface" truth. Solid fraction per y-stratum over the full
	 * box (a coherent ground plane shows as a sharp y where column solids end),
	 * the topSolidY distribution across a coarse column grid (is that plane
	 * consistent across columns, or a random sponge?), and the anchor column.
	 */
	private static void measureVerticalStructure(FieldSnapshot snap) {
		double[] wc = centerOf(snap);
		// The field box: x/z span ±EXTENT around the anchor's X/Z ({0,0}); y spans
		// ±EXTENT around the anchor's Y (70) → x,z ∈ [-96,96), y ∈ [-26,166).
		int xb0 = (int) ANCHOR_X - EXTENT, xb1 = (int) ANCHOR_X + EXTENT;
		int zb0 = (int) ANCHOR_Z - EXTENT, zb1 = (int) ANCHOR_Z + EXTENT;
		int yb0 = (int) ANCHOR_Y - EXTENT, yb1 = (int) ANCHOR_Y + EXTENT;
		int ax = (int) Math.round(ANCHOR_X);
		int az = (int) Math.round(ANCHOR_Z);

		System.out.println("\n[M1] vertical structure @ settle gen=" + snap.generation()
				+ " (field-time " + String.format("%.3f", snap.job().t()) + "), window=("
				+ wc[0] + "," + wc[1] + "," + wc[2] + ")");
		System.out.println("[M1]   box x/z=[" + xb0 + "," + xb1 + ")  y=[" + yb0 + "," + yb1 + ")");

		// Per-y stratum solid fraction over the full box (every block in the x/z plane),
		// plus a full-box census reconciliation against the census gate.
		int sideX = xb1 - xb0; // 192 (x/z)
		int sideY = yb1 - yb0; // 192 (y)
		double[] solidFracByY = new double[sideY];
		long boxRhoSolid = 0, boxQAir = 0, boxQSolid = 0, boxQOre = 0;
		long boxTotal = (long) sideX * sideX * sideY;
		float[] rhoBox = new float[(int) boxTotal];
		long rhoSum = 0;
		int idx = 0;
		for (int dy = 0; dy < sideY; dy++) {
			int y = yb0 + dy;
			int solid = 0;
			for (int z = zb0; z < zb1; z++) {                       // field x/z window, census-identical
				for (int x = xb0; x < xb1; x++) {
					Quantizer.CellSample s = Quantizer.sampleAt(snap, wc, x, y, z);
					rhoBox[idx++] = s.rho();
					rhoSum += Math.round(s.rho() * 10000.0);
					if (s.rho() >= Quantizer.TAU_C) {
						solid++;
						boxRhoSolid++;
					}
					Quantizer.BlockKind k = Quantizer.quantizeCold(s.rho(), s.q(), s.eps2());
					switch (k) {
					case AIR -> boxQAir++;
					case SOLID -> boxQSolid++;
					case ORE -> boxQOre++;
					}
				}
			}
			solidFracByY[dy] = solid / (double) (sideX * sideX);
		}
		java.util.Arrays.sort(rhoBox);
		int nRb = rhoBox.length;
		double rhoMean = rhoSum / 10000.0 / (double) nRb;
		System.out.println("\n[M1] full-box reconciliation (census cross-check, field box x/z=[" + xb0 + "," + xb1
				+ ") y=[" + yb0 + "," + yb1 + ")):");
		System.out.println("[M1]   rho over box: min=" + rhoBox[0] + " mean=" + String.format("%.4f", rhoMean)
				+ " max=" + rhoBox[nRb - 1] + " p10=" + rhoBox[(int) (nRb * 0.10)] + " p50=" + rhoBox[(int) (nRb * 0.50)]
				+ " p90=" + rhoBox[(int) (nRb * 0.90)]);
		System.out.println("[M1]   rho≥τ_c=" + String.format("%.4f", boxRhoSolid / (double) boxTotal)
				+ " | quantizeCold AIR=" + String.format("%.4f", boxQAir / (double) boxTotal)
				+ " SOLID=" + String.format("%.4f", boxQSolid / (double) boxTotal)
				+ " ORE=" + String.format("%.4f", boxQOre / (double) boxTotal)
				+ " (non-air=" + String.format("%.4f", (boxQSolid + boxQOre) / (double) boxTotal) + ")"
				+ " ← compare to census ρ p50=1.0005, AIR=0.2906 non-air=0.7094");

		// Print the per-y-stratum solid fraction over the x/z field plane.
		System.out.println("[M1] y-stratum solid fraction (over the x/z field plane, y → frac, '*' = tenths of solid):");
		for (int dy = 0; dy < sideY; dy++) {
			int y = yb0 + dy;
			double f = solidFracByY[dy];
			int tenths = (int) Math.round(f * 10);
			String bar = "*".repeat(Math.max(0, tenths));
			String marker = "";
			if (y == (int) ANCHOR_Y) {
				marker = "  <-- box center y=70";
			} else if (y == yb1 - 1) {
				marker = "  <-- near box top (spawn scan starts here)";
			} else if (y == yb0) {
				marker = "  <-- box bottom";
			}
			System.out.println(String.format("  y=%4d  frac=%.3f  %10s%s", y, f, bar, marker));
		}

		// Coarse column grid: topSolidY per column (every 3 blocks across the x/z field plane).
		int step = 3;
		int nCols = 0, nWithSolid = 0;
		int topMin = Integer.MAX_VALUE, topMax = Integer.MIN_VALUE;
		long topSum = 0;
		int[] hist = new int[8]; // classified into 8 equal-height bands of the box
		for (int z = zb0; z < zb1; z += step) {
			for (int x = xb0; x < xb1; x += step) {
				int top = topSolidY(snap, wc, yb1 - 1, x, z);
				nCols++;
				if (top == Integer.MIN_VALUE) {
					continue; // no solid in this column (all air)
				}
				nWithSolid++;
				topMin = Math.min(topMin, top);
				topMax = Math.max(topMax, top);
				topSum += top;
				int band = (int) Math.floor((top - yb0) / (double) sideY * 8);
				band = Math.min(7, Math.max(0, band));
				hist[band]++;
			}
		}
		double topMean = nWithSolid > 0 ? topSum / (double) nWithSolid : Double.NaN;
		System.out.println("\n[M1] coarse grid " + step + "-block spacing: " + nCols + " columns"
				+ " (" + nWithSolid + " have a solid, " + (nCols - nWithSolid) + " are all-air)");
		System.out.println("[M1]   topSolidY across columns: min=" + (topMin == Integer.MAX_VALUE ? "N/A" : topMin)
				+ " max=" + (topMax == Integer.MIN_VALUE ? "N/A" : topMax)
				+ " mean=" + (Double.isNaN(topMean) ? "N/A" : String.format("%.1f", topMean))
				+ " (y spans [" + yb0 + "," + yb1 + ") = " + sideY + " y)");
		System.out.print("[M1]   topSolidY histogram (8 bands, y bottom→top): ");
		for (int h : hist) {
			System.out.print(h + " ");
		}
		System.out.println();
		boolean coherentPlane = nWithSolid > 0 && (topMax - topMin) <= 8; // a plane: narrow topSolid band across columns
		String planeMsg = nWithSolid == 0
				? "NO SOLID IN ANY SAMPLED COLUMN — the field reads all-air at this settle"
				: (coherentPlane
						? "columns form a COHERENT ground plane (topSolid spans only " + (topMax - topMin) + " y)"
						: "topSolid Y is a RANDOM SPONGE (spans " + (topMax - topMin) + " y across columns — no surface)");
		System.out.println("[M1]   verdict: " + planeMsg);

		// Anchor column profile.
		System.out.println("[M1]   anchor column (x=" + ax + ", z=" + az + ") profile (y → kind, S=solid A=air):");
		StringBuilder anchorProfile = new StringBuilder();
		int anchorTop = Integer.MIN_VALUE, anchorSolid = 0;
		for (int y = yb1 - 1; y >= yb0; y--) {
			boolean solid = Quantizer.sampleAt(snap, wc, ax, y, az).rho() >= Quantizer.TAU_C;
			anchorProfile.append(solid ? 'S' : 'A');
			if (solid) {
				anchorSolid++;
				if (anchorTop == Integer.MIN_VALUE) {
					anchorTop = y;
				}
			}
		}
		// Print the profile in compact chunks (top→bottom).
		String prof = anchorProfile.toString();
		for (int off = 0; off < prof.length(); off += 24) {
			int bandTopY = yb1 - 1 - off;
			System.out.println("      y=" + (bandTopY) + "↓  [" + prof.substring(off, Math.min(prof.length(), off + 24)) + "]");
		}
		System.out.println("[M1]   anchor column: topSolidY=" + anchorTop + " solidCount=" + anchorSolid
				+ " boxTop=" + (yb1 - 1));
	}

	/** The top solid y on a column, scanning down from the box top (SurfaceSpawn's scan). */
	private static int topSolidY(FieldSnapshot snap, double[] wc, int boxTop, int x, int z) {
		for (int y = boxTop; y >= boxTop - EXTENT * 2; y--) {
			if (Quantizer.sampleAt(snap, wc, x, y, z).rho() >= Quantizer.TAU_C) {
				return y;
			}
		}
		return Integer.MIN_VALUE;
	}

	// --- M2: the spawn reality -----------------------------------------------

	/**
	 * M2 — where the owner actually spawns. Replicates {@code SurfaceSpawn}'s
	 * exact scan (first solid down the anchor column from the box top, respawn
	 * at {@code topSolid + 1 + clearance}) and censuses the 32³ world around
	 * that respawn — the solid fraction and whether an air pocket exists to
	 * stand in.
	 */
	private static int measureSpawnReality(FieldSnapshot snap) {
		double[] wc = centerOf(snap);
		int boxTop = (int) Math.round(ANCHOR_Y + EXTENT);
		int ax = (int) Math.round(ANCHOR_X);
		int az = (int) Math.round(ANCHOR_Z);

		// The exact SurfaceSpawn scan (SurfaceSpawn.SURFACE_CLEARANCE = 1).
		int topSolidY = Integer.MIN_VALUE;
		for (int y = boxTop; y >= boxTop - (int) TwoFluidSolver.EXTENT * 2; y--) {
			if (Quantizer.sampleAt(snap, wc, ax, y, az).rho() >= Quantizer.TAU_C) {
				topSolidY = y;
				break;
			}
		}
		System.out.println("\n[M2] spawn reality (SurfaceSpawn scan on anchor column x=" + ax + ", z=" + az + ")");
		if (topSolidY == Integer.MIN_VALUE) {
			System.out.println("[M2]   NO solid on the anchor column — SurfaceSpawn would never set a respawn (retries forever)");
			return Integer.MIN_VALUE;
		}
		int standY = topSolidY + 1 + 1; // feet one above the top solid + SURFACE_CLEARANCE
		System.out.println("[M2]   anchor column topSolidY=" + topSolidY + " → SurfaceSpawn set respawn at y=" + standY);

		// Census the 32³ around the respawn (as if the player spawned there).
		int half = VICINITY_RADIUS;
		int cx = ax, cy = standY, cz = az;
		int total = (2 * half) * (2 * half) * (2 * half);
		int solid = 0, ore = 0;
		int j0 = cy - half, j1 = cy + half - 1;
		int[] solidByY = new int[2 * half];
		for (int dz = -half; dz < half; dz++) {
			for (int dy = -half; dy < half; dy++) {
				for (int dx = -half; dx < half; dx++) {
					Quantizer.CellSample s = Quantizer.sampleAt(snap, wc, cx + dx, cy + dy, cz + dz);
					Quantizer.BlockKind k = Quantizer.quantizeCold(s.rho(), s.q(), s.eps2());
					if (k != Quantizer.BlockKind.AIR) {
						solid++;
						if (k == Quantizer.BlockKind.ORE) {
							ore++;
						}
						solidByY[dy + half]++;
					}
				}
			}
		}
		System.out.println("[M2]   " + (2 * half) + "³ around respawn (" + cx + "," + cy + "," + cz + "):"
				+ " solid+ore=" + solid + "/" + total + " (" + String.format("%.1f", 100.0 * solid / total) + "%)"
				+ " ore=" + ore + " total=" + total);
		// Is there an air pocket at the respawn feet (the 2 blocks the player needs)?
		boolean feetAir = true;
		for (int a = 0; a < 2; a++) {
			Quantizer.CellSample s = Quantizer.sampleAt(snap, wc, cx, standY + a, cz);
			if (s.rho() >= Quantizer.TAU_C) {
				feetAir = false;
			}
		}
		System.out.println("[M2]   air pocket for the player's feet @ respawn y=" + standY + " +1,+2: "
				+ (feetAir ? "AIR (standable)" : "SOLID (embedded — hidden in the blob)"));
		System.out.print("[M2]   solid-by-y around respawn (bottom→top, each = count): ");
		for (int c : solidByY) {
			System.out.print(c + " ");
		}
		System.out.println();
		return standY;
	}

	// --- M3: the follow-behind re-home ---------------------------------------

	/**
	 * M3 — the "world moves" truth, split into its two possible causes.
	 *
	 * <p><b>(A) Pure re-home geometry (float {@code gridCoord} drift):</b> a
	 * frozen {@link TwoFluidSolver} (no stepping between samples) wrapped as a
	 * snapshot at center c0, fixed block P sampled; then {@code roll(k,0,0)} and
	 * the center re-built at {@code c0 + (k·cell)} — the exact documented math —
	 * and P re-sampled. No field evolution: any drift/flip is purely the re-home
	 * geometry. If the re-home is world-fixed, P reads identical and zero blocks
	 * flip.
	 *
	 * <p><b>(B) Production re-home (what the player actually meets):</b> the
	 * real {@link CassiFieldThread#rehome} drain on a live worker, which rolls
	 * AND keeps evolving the field between snapshots. One shared prior map: cold
	 * player-vicinity under the current center, then the re-home, then the same
	 * 32³ re-quantized — the combined (geometry + evolution) flip rate.
	 */
	private static void measureFollowBehind(int spawnY) throws InterruptedException {
		System.out.println("\n[M3] follow-behind re-home stability (the \"world moves\" truth)");

		// (A) pure geometry — a frozen solver, no evolution.
		int k = 4;
		double cell = CassiFieldThread.CELL_WORLD_WIDTH;
		TwoFluidSolver solver = new TwoFluidSolver(SEED_A);
		solver.seed();
		for (int i = 0; i < 64; i++) {
			solver.step(); // settle the raw field once; then freeze it for the geometry test
		}
		double[] c0 = { ANCHOR_X, ANCHOR_Y, ANCHOR_Z };
		FieldSnapshot snapA0 = snapshotFromSolver(solver, c0, 1);
		int px = 45, py = 100, pz = 60;
		Quantizer.CellSample pre = Quantizer.sampleAt(snapA0, c0, px, py, pz);
		System.out.println("[M3 (A)] pure re-home geometry (frozen field, no evolution):"
				+ " fixed block P=(" + px + "," + py + "," + pz + ") under c0=(" + c0[0] + "," + c0[1] + "," + c0[2] + ")"
				+ ": rho=" + pre.rho() + " q=" + pre.q() + " eps2=" + pre.eps2());

		solver.roll(k, 0, 0);
		double[] c1 = { c0[0] + k * cell, c0[1], c0[2] };
		FieldSnapshot snapA1 = snapshotFromSolver(solver, c1, 2);
		Quantizer.CellSample post = Quantizer.sampleAt(snapA1, c1, px, py, pz);
		boolean exactRho = pre.rho() == post.rho();
		boolean exactQ = pre.q() == post.q();
		float driftRho = Math.abs(post.rho() - pre.rho());
		float driftQ = Math.abs(post.q() - pre.q());
		System.out.println("[M3 (A)] center +" + k + " whole cells (+" + (k * cell) + " m), roll(" + k + ",0,0):"
				+ " P re-sampled rho=" + post.rho() + " q=" + post.q() + " eps2=" + post.eps2());
		System.out.println("[M3 (A)]   exact-equal rho=" + exactRho + " (" + String.format("%.2e", driftRho) + " drift)"
				+ " | q=" + exactQ + " (" + String.format("%.2e", driftQ) + " drift)"
				+ " → " + (exactRho && exactQ ? "world-fixed (the float gridCoord is bit-stable across a whole-cell re-home)"
						: "the float gridCoord is NOT bit-stable — the re-home geometry drifts a frozen field by " + String.format("%.2e", driftRho)));

		// The pure-geometry flip rate over the same shared prior (a second frozen pass).
		java.util.Map<net.minecraft.core.BlockPos, Quantizer.BlockKind> geoPrior = new java.util.HashMap<>();
		int a0Cold = reQuantizeVicinity(snapA0, c0, (int) ANCHOR_X, spawnY, (int) ANCHOR_Z, geoPrior)[0];
		int a1Flip = reQuantizeVicinity(snapA1, c1, (int) ANCHOR_X, spawnY, (int) ANCHOR_Z, geoPrior)[0];
		System.out.println("[M3 (A)]   frozen re-quantize of the same 32³ vs shared prior → " + a0Cold
				+ " cold solids, then " + a1Flip + " blocks FLIPPED by the pure re-home geometry (hysteresis-aware)");

		// (B) production re-home — real worker, combined geometry + evolution.
		System.out.println("\n[M3 (B)] production re-home (live worker; geometry + field evolution together):");
		SnapshotPublisher pub = new SnapshotPublisher();
		CassiFieldThread.Cfg cfg = new CassiFieldThread.Cfg(
				SEED_A, CassiFieldThread.JOB_STEP_CAP, CassiFieldThread.SNAPSHOT_CADENCE,
				new KernelLoader().load(), new double[] { ANCHOR_X, ANCHOR_Y, ANCHOR_Z });
		CassiFieldThread worker = new CassiFieldThread(pub);
		worker.start(cfg);
		try {
			FieldSnapshot snap0 = awaitGen(pub, 1);
			double[] center0 = centerOf(snap0);
			System.out.println("[M3 (B)]   worker booted, first snapshot gen=" + snap0.generation()
					+ " center=(" + center0[0] + "," + center0[1] + "," + center0[2] + ")");
			java.util.Map<net.minecraft.core.BlockPos, Quantizer.BlockKind> prior = new java.util.HashMap<>();
			int cold = reQuantizeVicinity(snap0, center0, (int) ANCHOR_X, spawnY, (int) ANCHOR_Z, prior)[0];
			System.out.println("[M3 (B)]   cold player-vicinity 32³ @ (" + (int) ANCHOR_X + "," + spawnY + "," + (int) ANCHOR_Z + "):"
					+ " " + cold + " blocks fell solid (prior filled)");

			worker.rehome(center0[0] + k * cell, center0[1], center0[2]);
			FieldSnapshot moved = awaitCenterChanged(pub, center0);
			double[] c1b = centerOf(moved);
			System.out.println("[M3 (B)]   re-home: center " + center0[0] + " → " + c1b[0]
					+ " (+" + k + " whole cells = +" + (k * cell) + " m), roll(" + k + ",0,0)"
					+ " gen=" + moved.generation());
			int flips = reQuantizeVicinity(moved, c1b, (int) ANCHOR_X, spawnY, (int) ANCHOR_Z, prior)[0];
			System.out.println("[M3 (B)]   re-quantized same 32³ vs shared prior → " + flips
					+ " blocks FLIPPED kind (geometry + evolution — the \"world moves under the player\" rate)"
					+ (flips == 0 ? " — zero: the production re-home is world-fixed at the block level" : ""));
		} finally {
			worker.close();
		}
	}

	/** Wrap a solver's live arrays in a minimal immutable snapshot (rho/q only — enough for {@link Quantizer#sampleAt}). */
	private static FieldSnapshot snapshotFromSolver(TwoFluidSolver solver, double[] center, int gen) {
		return new FieldSnapshot(
				solver.q(), new float[0], new float[0][0], solver.rho(),
				gen, new dev.cassicraft.domain.engine.EngineJob(gen, 1, gen * TwoFluidSolver.DT, center));
	}

	/**
	 * Re-quantize a player-vicinity 32³ box (TickSampler's exact loop: radius 16,
	 * hysteresis {@code Quantizer.quantize} vs a world-keyed prior) and return
	 * {@code [count, ...]} of emitted (flipped) blocks. With a shared {@code prior}
	 * map this is the TickSampler path verbatim; a cold first pass defaults every
	 * block to AIR prior, so the count is the cold solidification count.
	 */
	private static int[] reQuantizeVicinity(FieldSnapshot snap, double[] wc, int cx, int cy, int cz,
			java.util.Map<net.minecraft.core.BlockPos, Quantizer.BlockKind> prior) {
		java.util.Map<net.minecraft.core.BlockPos, Quantizer.BlockKind> p = prior == null
				? new java.util.HashMap<>() : prior;
		int emitted = 0;
		for (int dz = -VICINITY_RADIUS; dz < VICINITY_RADIUS; dz++) {
			for (int dy = -VICINITY_RADIUS; dy < VICINITY_RADIUS; dy++) {
				for (int dx = -VICINITY_RADIUS; dx < VICINITY_RADIUS; dx++) {
					net.minecraft.core.BlockPos pos = new net.minecraft.core.BlockPos(cx + dx, cy + dy, cz + dz);
					Quantizer.CellSample s = Quantizer.sampleAt(snap, wc, pos.getX(), pos.getY(), pos.getZ());
					Quantizer.BlockKind priorKind = p.getOrDefault(pos, Quantizer.BlockKind.AIR);
					Quantizer.BlockKind kind = Quantizer.quantize(s.rho(), s.q(), s.eps2(), priorKind);
					if (kind != priorKind) {
						p.put(pos, kind);
						emitted++;
					}
				}
			}
		}
		return new int[] { emitted };
	}

	// --- M4: the churn rate ---------------------------------------------------

	/**
	 * M4 — the "world moves through space" = slowly churning terrain around a
	 * stuck player. At {@code DT=0.001} the field barely evolves per generation;
	 * re-quantize the same player-vicinity box at two settle generations and
	 * count the hysteresis-aware flips.
	 */
	private static void measureChurn(int spawnY) throws InterruptedException {
		System.out.println("\n[M4] terrain churn rate at DT=" + TwoFluidSolver.DT);
		SnapshotPublisher pub = new SnapshotPublisher();
		CassiFieldThread.Cfg cfg = new CassiFieldThread.Cfg(
				SEED_A, CassiFieldThread.JOB_STEP_CAP, CassiFieldThread.SNAPSHOT_CADENCE,
				new KernelLoader().load(), new double[] { ANCHOR_X, ANCHOR_Y, ANCHOR_Z });
		CassiFieldThread worker = new CassiFieldThread(pub);
		worker.start(cfg);
		try {
			FieldSnapshot early = awaitGen(pub, SETTLE_EARLY);
			double[] wc = centerOf(early);
			java.util.Map<net.minecraft.core.BlockPos, Quantizer.BlockKind> prior = new java.util.HashMap<>();
			int earlyEmitted = reQuantizeVicinity(early, wc, (int) ANCHOR_X, spawnY, (int) ANCHOR_Z, prior)[0];
			System.out.println("[M4]   gen=" + SETTLE_EARLY + " (t=" + String.format("%.3f", early.job().t()) + "):"
					+ " cold-pass solid count in 32³=" + earlyEmitted);

			FieldSnapshot late = awaitGen(pub, SETTLE_LATE);
			double[] wc2 = centerOf(late);
			int lateEmitted = reQuantizeVicinity(late, wc2, (int) ANCHOR_X, spawnY, (int) ANCHOR_Z, prior)[0];
			System.out.println("[M4]   gen=" + SETTLE_LATE + " (t=" + String.format("%.3f", late.job().t())
					+ "): re-quantized against gen-" + SETTLE_EARLY + " prior → " + lateEmitted + " blocks flipped");
			double deltaT = late.job().t() - early.job().t();
			System.out.println("[M4]   " + SETTLE_LATE + "→" + SETTLE_EARLY + " now spans Δt=" + String.format("%.3f", deltaT)
					+ " field-time units (wall-clock ≈ " + late.generation() * (CassiFieldThread.JOB_STEP_CAP)
					+ " steps × ~few ms/step) — churn per Δt=" + lateEmitted);
		} finally {
			worker.close();
		}
	}

	/**
	 * M5 — the coherent-surface fix verification. Runs the <b>real</b>
	 * {@code SurfaceSpawn} scans (the coherent-plane scan and its single-column
	 * fallback) on the settled field, reports the spawn each yields, and checks
	 * that the coherent spawn stands on a real multi-column roof (patch
	 * consistency) with a standable 32³ around it.
	 */
	private static void measureCoherentSurface(FieldSnapshot snap) {
		double[] wc = centerOf(snap);
		int ax = (int) Math.round(ANCHOR_X);
		int az = (int) Math.round(ANCHOR_Z);
		int boxTop = (int) Math.round(ANCHOR_Y + EXTENT); // 166, the SurfaceSpawn scan start
		int coherentY = dev.cassicraft.game.spawn.SurfaceSpawn.findCoherentSurface(snap, wc, ax, az, boxTop);
		int colTopY = dev.cassicraft.game.spawn.SurfaceSpawn.topSolidAnchorColumn(snap, wc, ax, az, boxTop);

		System.out.println("\n[M5] coherent-surface spawn fix (real SurfaceSpawn scans on the settled field)");
		System.out.println("[M5]   single-column scan (old):  topSolidY=" + colTopY + " → spawn at y="
				+ (colTopY == Integer.MIN_VALUE ? "N/A" : (colTopY + 2)));
		System.out.println("[M5]   coherent-plane scan (new): topSolidY=" + coherentY + " → spawn at y="
				+ (coherentY == Integer.MIN_VALUE ? "N/A" : (coherentY + 2)));

		if (coherentY != Integer.MIN_VALUE) {
			// Patch consistency at the chosen plane: what fraction of the local
			// patch is solid there (the "real roof" proof).
			double patchFrac = patchSolidFraction(snap, wc, ax, az, coherentY);
			System.out.println("[M5]   patch consistency at chosen y=" + coherentY + ": "
					+ String.format("%.2f", patchFrac) + " of the " + (2 * 2 + 1) * (2 * 2 + 1)
					+ "-column patch solid (a coherent roof; the anchor spawns standing on it)");

			// The 32³ around the coherent spawn: solid fraction + standable feet.
			int standY = coherentY + 2;
			int half = VICINITY_RADIUS;
			int total = (2 * half) * (2 * half) * (2 * half);
			int solid = 0;
			for (int dz = -half; dz < half; dz++) {
				for (int dy = -half; dy < half; dy++) {
					for (int dx = -half; dx < half; dx++) {
						Quantizer.CellSample s = Quantizer.sampleAt(snap, wc, ax + dx, standY + dy, az + dz);
						if (s.rho() >= Quantizer.TAU_C) {
							solid++;
						}
					}
				}
			}
			boolean feetAir = Quantizer.sampleAt(snap, wc, ax, standY, az).rho() < Quantizer.TAU_C
					&& Quantizer.sampleAt(snap, wc, ax, standY + 1, az).rho() < Quantizer.TAU_C;
			System.out.println("[M5]   32³ around coherent spawn (" + ax + "," + standY + "," + az + "):"
					+ " solid=" + String.format("%.1f", 100.0 * solid / total) + "%"
					+ " | spawn feet air=" + (feetAir ? "standable" : "EMBEDDED"));
		}
	}

	/** The solid fraction of the local (radius-2) column patch at a y — the coherent-roof consistency. */
	private static double patchSolidFraction(FieldSnapshot snap, double[] wc, int cx, int cz, int y) {
		int r = 2;
		int count = 0, solid = 0;
		for (int dz = -r; dz <= r; dz++) {
			for (int dx = -r; dx <= r; dx++) {
				count++;
				if (Quantizer.sampleAt(snap, wc, cx + dx, y, cz + dz).rho() >= Quantizer.TAU_C) {
					solid++;
				}
			}
		}
		return solid / (double) count;
	}

	/** Wait until a publish carries a center different from {@code old} (the roll drained). */
	private static FieldSnapshot awaitCenterChanged(SnapshotPublisher pub, double[] old)
			throws InterruptedException {
		long deadline = System.currentTimeMillis() + FIRST_TIMEOUT_MS;
		while (System.currentTimeMillis() < deadline) {
			FieldSnapshot s = pub.freshest();
			if (s != null && s.job() != null && !s.job().isWindowless()) {
				double[] c = s.job().windowCenter();
				if (c[0] != old[0] || c[1] != old[1] || c[2] != old[2]) {
					return s;
				}
			}
			Thread.sleep(20);
		}
		throw new IllegalStateException("no re-homed snapshot within timeout");
	}

	private SurfaceDiagnosticsMain() {
	}
}
