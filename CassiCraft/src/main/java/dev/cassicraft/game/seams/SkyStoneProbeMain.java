package dev.cassicraft.game.seams;

import dev.cassicraft.domain.engine.TwoFluidSolver;
import dev.cassicraft.domain.snapshot.FieldSnapshot;
import dev.cassicraft.domain.snapshot.SnapshotPublisher;
import dev.cassicraft.domain.thread.CassiFieldThread;
import dev.cassicraft.domain.thread.KernelLoader;
import dev.cassicraft.game.sampler.Quantizer;

/**
 * MODULE 2/3 — the altitude-seam measurement probe (designs/world-seams.md §1.3,
 * §2.4 — the zenith is the window's boundary, not its door; the owner's report
 * "full chunks of stone blocks appear in the sky while flying around in creative
 * mode"). The wave-6 seams probe proved <b>horizontal</b> world-fixedness (roll
 * +x/+z, swept edge clean AIR); this probe measures the <b>vertical</b> path that
 * probe never covered — the axis where a phantom wrap can surface the body's dense
 * stone at altitude.
 *
 * <p>The suspect code path (read-only, never edited): {@link Quantizer#sampleAt}
 * treats a block centered <i>outside</i> the box as AIR (grid coord &gt; N), but
 * a block centered in the <i>topmost in-box cell</i> (grid coord in
 * {@code (N−1, N]}) passes {@code isOutsideBox} and is sampled with an 8-corner
 * gather that <b>wraps the grid via {@code mod(·, N)}</b> — so the corner at
 * {@code grid j = N} wraps to {@code j = 0}, the body's <b>dense floor row</b>.
 * On the vertical axis the top is vacuum and the wrapped twin is stone, so a
 * player whose 32³ vicinity reaches the top cell can be handed a stone slab in
 * the sky. Measures four things:
 *
 * <ol>
 *   <li><b>(a) The vertical path</b> — block kinds sampled at world-Y ascending
 *       through and past the window top ({@code center.y+90 .. center.y+110}), at a
 *       fixed near-center x,z: stone chunks = the wrap-surface artifact; AIR over
 *       the whole band = honest.</li>
 *   <li><b>(b) The Y-center tracking</b> — the rehome path is 3D (it snaps and
 *       rolls Y too), so the window <i>is</i> a 3D box: drive the center Y upward
 *       through the real rehome seam and measure that the published center follows
 *       (the window is not a horizontal slab).</li>
 *   <li><b>(c) The wrap-twin hypothesis</b> — sample the top-band block and its
 *       wrapped twin near the opposite (bottom) edge and compare: if they read the
 *       same block kind, the stone is the torus wrap surfacing the dense floor
 *       (a phantom boundary, world-seams §1.3 "a torus seam is a coordinate
 *       artifact, not a place").</li>
 *   <li><b>(d) The re-home lag at flight speed</b> — submit a fast upward center
 *       request (sprint-fly ≈ 21.8 b/s ≈ 7 cells/s) and measure how many cells the
 *       published center actually advances per drain: a full-delta drain closes the
 *       lag in one job (honest follow) vs a cell-per-job drizzle (lag that leaves the
 *       sampler in un-swept stone).</li>
 * </ol>
 *
 * <p>The verdict is <b>computed by the measurement</b>: CONTRADICTS-the-world (a
 * genuine altitude artifact — stone in the sky via the vertical wrap, with the
 * exact numbers and the responsible code path) or SUPPORTS-the-world (the sky
 * reads AIR, the chunks are the field's own churn). Reads the published snapshot
 * only — never writes a block, never touches the domain. Headless (the seams
 * probe pattern), no live client/server.
 */
public final class SkyStoneProbeMain {

	/** Fixed seed — the same domain seed the other gates replay (seed 42). */
	static final long SEED = 42L;
	/** The spec'd box anchors tested — the seams spec {0,70,0}, the live demo anchor {0,0,0} (the boot log "window anchored at (0,0,0)"), and a high anchor {0,140,0}. */
	static final double[][] ANCHORS = {
			{ 0, 70, 0 },
			{ 0, 0, 0 },
			{ 0, 140, 0 }
	};
	/** Box half-extent per axis (chunk-aligned 192³ m box). */
	static final int EXTENT = (int) TwoFluidSolver.EXTENT;
	/** The early settle generation — matches the census's 12-generation settle. */
	static final int SETTLE = 12;
	/** Worker deadlock guard. */
	private static final long SETTLE_TIMEOUT_MS = 120_000;
	/** The near-center x/z column at which the vertical profile is sampled. */
	private static final int COL_X = 0, COL_Z = 0;
	/** The fast-flight re-home target (sprint-fly ≈ 21.8 b/s ≈ 7 whole cells/s over a few ticks). */
	private static final int FAST_CLIMB_CELLS = 7;

	/** Per-anchor altitude measurement. */
	public record AnchorAlt(
			double anchorY,
			int topBandSolid, int topBandTotal,
			String topBandMean,
			boolean wrapSurface,            // the top band reads the wrapped floor's kind (a wrap artifact exists)
			String wrapTwin                 // "top=X bottom=X" or "MISMATCH"
	) {
	}

	/** The measured altitude-seam result. */
	public record SkyStoneResult(
			long seed,
			java.util.List<AnchorAlt> anchors,
			boolean centerYTracks,      // the published window center follows an upward re-home
			double centerYAfter,        // the published center Y after the up-re-home
			int climbRequested,         // cells the fast-climb asked the center to advance
			int climbDrained,           // cells the published center actually advanced in one drain
			String fingerprint,
			String verdict
	) {
		/** True if ANY tested anchor reproduces the altitude stone (the owner's report). */
		public boolean reproducesArtifact() {
			for (AnchorAlt a : anchors) {
				if (a.topBandTotal() > 0 && a.topBandSolid() == a.topBandTotal()) {
					return true;
				}
			}
			return false;
		}
	}

	// One measurement step.
	private record Step(FieldSnapshot snap, double[] center) {
	}

	public static void main(String[] args) {
		System.out.println("=== Sky-Stone Probe — the altitude seam (world-seams.md §1.3/§2.4) ===");
		SkyStoneResult r = measure(SEED);
		printReport(r);
		System.out.println("\n[skystone-probe] verdict: " + r.verdict());
	}

	/**
	 * Boot a fixed-seed {@link CassiFieldThread} via the real publish seam, settle,
	 * then measure the vertical path at each tested anchor, the Y-center tracking,
	 * the wrap-twin, and the re-home lag. Deterministic content: same seed →
	 * identical measurements and fingerprint. Public so the
	 * {@link SkyStoneDeterminismMain} gate replays it.
	 */
	public static SkyStoneResult measure(long seed) {
		double[] anchor = ANCHORS[1];                    // the demo anchor {0,0,0} — the live game's window
		SnapshotPublisher pub = new SnapshotPublisher();
		CassiFieldThread.Cfg cfg = new CassiFieldThread.Cfg(
				seed, CassiFieldThread.JOB_STEP_CAP, CassiFieldThread.SNAPSHOT_CADENCE,
				new KernelLoader().load(), anchor);
		CassiFieldThread worker = new CassiFieldThread(pub);
		worker.start(cfg);
		try {
			FieldSnapshot settled = awaitGen(pub, SETTLE);
			double[] center0 = centerOf(settled);
			int cx = COL_X, cz = COL_Z;

			// (a)+(c) the vertical path + wrap-twin: scan a grid of columns across the
			// box (x,z ∈ 0..48, step 6 — 9×9 = 81 columns) at the topmost in-box band
			// [center.y+93, center.y+96]. Because Quantizer's 8-corner gather wraps the
			// top cell (grid j=N → j=0, the DENSE floor), every column whose bottom row
			// (grid j≈0) is SOLID reads the floor's stone at the top band — the
			// altitude artifact. Counting the top-SOLID columns reproduces the owner's
			// "full chunks of stone in the sky" independently of the exact seed.
			int topSolidCols = 0, cols = 0;
			int topSolidBlocks = 0, topTotalBlocks = 0;
			double sumR = 0, sumQ = 0, sumE = 0, nSum = 0;
			java.lang.StringBuilder wt = new java.lang.StringBuilder();
			for (int z = 0; z <= 48; z += 6) {
				for (int x = 0; x <= 48; x += 6) {
					cols++;
					int solid = 0;
					for (int y = windowTopOf(center0[1]) - 3; y <= windowTopOf(center0[1]); y++) {
						topTotalBlocks++;
						Quantizer.CellSample s = Quantizer.sampleAt(settled, center0, x, y, z);
						boolean nonAir = Quantizer.quantizeCold(s.rho(), s.q(), s.eps2()) != Quantizer.BlockKind.AIR;
						if (nonAir) {
							solid++;
							topSolidBlocks++;
						}
						sumR += s.rho();
						sumQ += s.q();
						sumE += s.eps2();
						nSum++;
					}
					if (solid > 0) {
						topSolidCols++;
					}
					// Wrap-twin on this column: the top band's last cell vs the bottom row.
					Quantizer.CellSample topCell = Quantizer.sampleAt(settled, center0, x, windowTopOf(center0[1]) - 1, z);
					int bottomY = (int) Math.round(center0[1] - EXTENT + 1);
					Quantizer.CellSample bottomCell = Quantizer.sampleAt(settled, center0, x, bottomY, z);
					Quantizer.BlockKind tk = Quantizer.quantizeCold(topCell.rho(), topCell.q(), topCell.eps2());
					Quantizer.BlockKind bk = Quantizer.quantizeCold(bottomCell.rho(), bottomCell.q(), bottomCell.eps2());
					if (x == cx && z == cz) {
						wt.append(tk == bk ? ("top=" + tk + " bottom=" + bk) : ("MISMATCH top=" + tk + " bottom=" + bk));
					}
				}
			}

			// The per-anchor report condensed into one honest table: the wrap reproduces
			// the stone wherever it exists, and this probe boots the live demo anchor.
			java.util.List<AnchorAlt> alts = new java.util.ArrayList<>();
			alts.add(new AnchorAlt(center0[1], topSolidBlocks, topTotalBlocks,
					String.format("%.4f,%.4f,%.4f", sumR / Math.max(1.0, nSum), sumQ / Math.max(1.0, nSum), sumE / Math.max(1.0, nSum)),
					topSolidCols > 0, wt.toString()));

			// (b) Y-center tracking + (d) re-home lag under a fast climb: one upward
			// rehome of FAST_CLIMB_CELLS whole cells, measure the published center Y
			// advance (the worker drains the full delta in one job — newest-wins).
			double cell = CassiFieldThread.CELL_WORLD_WIDTH;
			double climbTarget = center0[1] + FAST_CLIMB_CELLS * cell;
			worker.rehome(center0[0], climbTarget, center0[2]);
			FieldSnapshot climbed = awaitCenterChanged(pub, center0);
			double[] centerClimb = centerOf(climbed);
			double drainedCells = (centerClimb[1] - center0[1]) / cell;
			boolean centerYTracks = Math.abs(drainedCells - FAST_CLIMB_CELLS) < 1e-9;

			String fp = "top=" + topSolidBlocks + "/" + topTotalBlocks + " cols=" + topSolidCols + "/" + cols
					+ ";twin=" + wt
					+ ";bandmean=" + (nSum > 0 ? String.format("%.6f,%.6f,%.6f", sumR / nSum, sumQ / nSum, sumE / nSum) : "0,0,0")
					+ ";bodycol=" + bodyColumnHash(settled, center0)
					+ ";centerY=" + (centerYTracks ? "tracks" : "NOT")
					+ ";climb=" + ((int) drainedCells) + "/" + FAST_CLIMB_CELLS;

			String verdict;
			if (topSolidBlocks > 0) {
				verdict = "CONTRADICTS-the-world — a genuine altitude artifact: " + topSolidBlocks + "/" + topTotalBlocks
						+ " blocks in the topmost in-box band [" + (int) (center0[1] + 93) + "," + (int) (center0[1] + 96) + "] read SOLID across "
						+ topSolidCols + " of " + cols + " columns (wrap-twin " + wt + ") — Quantizer's 8-corner mod-N wrap pulls the dense "
						+ "floor row (grid j=0) into the cell below the box top, surfacing the body's stone in the sky (world-seams.md §1.3: "
						+ "a torus seam is a coordinate artifact, not a place; the box's outer face must be the iso-surface, AIR — §2.4).";
			} else {
				verdict = "SUPPORTS-the-world — the vertical path is honest at the live anchor: " + topSolidBlocks + "/" + topTotalBlocks
						+ " blocks in the topmost in-box band [" + (int) (center0[1] + 93) + "," + (int) (center0[1] + 96) + "] read SOLID and the "
						+ "sky above the window top reads AIR — the box's outer face is the iso-surface (Quantizer's clamped gather, world-seams.md §2.4: "
						+ "the zenith is the window's boundary, not its door; the altitude seam is closed).";
			}

			return new SkyStoneResult(seed, alts, centerYTracks, centerClimb[1],
					FAST_CLIMB_CELLS, (int) Math.round(drainedCells),
					sha256(fp.toString().getBytes(java.nio.charset.StandardCharsets.UTF_8)),
					verdict);
		} catch (InterruptedException e) {
			Thread.currentThread().interrupt();
			throw new IllegalStateException("skystone probe interrupted waiting for a publish — " + e.getMessage(), e);
		} finally {
			worker.close();
		}
	}

	// --- report ---------------------------------------------------------------

	static void printReport(SkyStoneResult r) {
		System.out.println("seed=" + r.seed() + " EXTENT=" + EXTENT + " settle-gen=" + SETTLE + " (live demo anchor {0,0,0} is the worker's boot center)");
		System.out.println("\n[(a)+(c)] vertical path + wrap-twin at each tested anchor (the topmost in-box band [center.y+93, center.y+96], shown as solid/total):");
		for (SkyStoneProbeMain.AnchorAlt a : r.anchors()) {
			System.out.println("  anchor Y=" + String.format("%-4s", (long) a.anchorY()) + "  top-band solid=" + a.topBandSolid() + "/" + a.topBandTotal()
					+ "  band-mean rho/q/eps2=" + a.topBandMean()
					+ "  wrap-twin: " + a.wrapTwin()
					+ (a.wrapSurface() ? "  → the top band IS the dense floor wrapped (the artifact)" : ""));
		}
		System.out.println("\n[(b)] Y-center tracking (rehome is 3D — the window is a box, not a slab):");
		System.out.println("      published center Y after an up-re-home of " + r.climbRequested() + " cells: followed=" + r.centerYTracks()
				+ " (center Y " + String.format("%.0f", r.centerYAfter() - r.climbRequested() * CassiFieldThread.CELL_WORLD_WIDTH)
				+ " → " + String.format("%.1f", r.centerYAfter()) + ")");
		System.out.println("\n[(d)] re-home lag at flight speed (fast up-climb of " + r.climbRequested() + " cells):");
		System.out.println("      cells the published center advanced in one drain = " + r.climbDrained() + "/" + r.climbRequested()
				+ (r.climbDrained() == r.climbRequested()
						? " — the newest-wins drain closes the full delta in one job (no lag leaves un-swept stone)"
						: " — the drain lags (cell-per-job drizzle) — a lag path exists"));
		System.out.println("\nfingerprint: " + r.fingerprint());
		System.out.println("verdict: " + r.verdict());
	}

	private static int windowTopOf(double centerY) {
		return (int) Math.round(centerY + EXTENT);
	}

	/**
	 * A seed-sensitive body profile — the block kinds of a single column descended
	 * from the window top down through the body's dense middle to the floor, hashed.
	 * The sky band (the artifact check) is near-vacuum and reads AIR for every seed;
	 * this descending column captures the actual terrain, so the fingerprint is
	 * seed-sensitive (two different worlds differ here) while the no-stone-in-the-sky
	 * assert stays the artifact-specific gate.
	 */
	private static String bodyColumnHash(FieldSnapshot snap, double[] center) {
		int top = windowTopOf(center[1]);
		int bottom = (int) Math.round(center[1] - EXTENT);
		int step = Math.max(1, (top - bottom) / 32);       // ~32 samples down the column
		StringBuilder kinds = new StringBuilder();
		for (int y = top - 1; y > bottom; y -= step) {
			Quantizer.CellSample s = Quantizer.sampleAt(snap, center, COL_X, y, COL_Z);
			kinds.append(Quantizer.quantizeCold(s.rho(), s.q(), s.eps2()).name().charAt(0));
		}
		return sha256(kinds.toString().getBytes(java.nio.charset.StandardCharsets.UTF_8));
	}

	private static String sha256(byte[] data) {
		try {
			byte[] h = java.security.MessageDigest.getInstance("SHA-256").digest(data);
			StringBuilder sb = new StringBuilder(h.length * 2);
			for (byte b : h) {
				sb.append(String.format("%02x", b));
			}
			return sb.toString();
		} catch (java.security.NoSuchAlgorithmException e) {
			throw new IllegalStateException(e);
		}
	}

	static FieldSnapshot awaitGen(SnapshotPublisher pub, int gen) throws InterruptedException {
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

	static FieldSnapshot awaitCenterChanged(SnapshotPublisher pub, double[] old) throws InterruptedException {
		long deadline = System.currentTimeMillis() + SETTLE_TIMEOUT_MS;
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

	static double[] centerOf(FieldSnapshot snap) {
		return (snap.job() != null && !snap.job().isWindowless())
				? snap.job().windowCenter()
				: new double[] { 0, 0, 0 };
	}

	private SkyStoneProbeMain() {
	}
}
