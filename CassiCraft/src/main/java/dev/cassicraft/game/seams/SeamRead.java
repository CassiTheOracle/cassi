package dev.cassicraft.game.seams;

import dev.cassicraft.domain.engine.TwoFluidSolver;
import dev.cassicraft.domain.snapshot.FieldSnapshot;
import dev.cassicraft.domain.snapshot.SnapshotPublisher;
import dev.cassicraft.game.sampler.Quantizer;

/**
 * MODULE 2/3 — the player-facing seam read (designs/world-seams.md §1.3, §4.2 —
 * the anchor-to-window seam; built only because the {@code SeamProbeMain}
 * measurement returned SUPPORTS: the block world is seam-honest). A <b>pure,
 * Minecraft-free</b> consumer of the published snapshot that tells the player
 * where they are in the window and the seam's state at their block — never a
 * phantom "edge of the world".
 *
 * <p>The field is a periodic torus living in the anchored 192³ box
 * ({@link TwoFluidSolver#EXTENT} = 96 per axis); the block world is its
 * quantized publish. The read renders two honest facts:
 * <ul>
 *   <li><b>Where you are in the window</b> — your block's local offset from the
 *       live window center (the box re-homes behind you), in metres, and which
 *       whole grid cell that maps to.</li>
 *   <li><b>The seam state</b> — {@code INTERIOR} when you are well inside the
 *       box, {@code EDGE_BAND} when you are within a named distance of the box
 *       boundary (the field's outer iso-surface), always with the honest framing
 *       that the field is a torus and the world is world-fixed: a block at the
 *       window edge reads the field's own content or out-of-box AIR, and the
 *       window re-homes behind you so the boundary stays out of play. There is
 *       never a wall or a void at the edge — only the field thinning to its
 *       outside, deterministically (the probe's T1/T2/T3 verdict).</li>
 * </ul>
 *
 * <p>This class never mutates and has no Minecraft import — a pure read of the
 * published snapshot, exactly as {@link Quantizer#sampleAt} exposes it. The
 * {@code /cassicraft seam} command (wiring-requests/seams-wiring.md) renders
 * {@link #readFreshest}; the command itself is the host seam into Minecraft.
 */
public final class SeamRead {

	/**
	 * The named edge-band distance (world blocks = metres) from a window boundary
	 * that a player reads as {@code EDGE_BAND} — the field's outermost ~2 whole
	 * cells, the layer the seam probe measured for boundary continuity (T3). A
	 * player this close to the box face is well into the outer iso-surface region
	 * (the box's outer face is the world's iso-surface; beyond it reads AIR).
	 */
	public static final int EDGE_BAND_BLOCKS = 6;

	/** The seam state at the player's block. */
	public enum SeamState {
		/** Well inside the box — the re-homed window's living interior. */
		INTERIOR,
		/** Within {@link #EDGE_BAND_BLOCKS} of the window boundary (the outer iso-surface). */
		EDGE_BAND
	}

	/** The seam readout — the local window position + the seam state, rendered to text. */
	public record SeamReadout(
			double offsetX, double offsetY, double offsetZ,
			double distanceToEdge,
			int cellX, int cellY, int cellZ,
			boolean inside,
			SeamState state,
			Quantizer.BlockKind blockKind,
			float rho, float q, float eps2,
			String text
	) {
	}

	/**
	 * Read the freshest published snapshot at a block position: report the local
	 * window position and seam state. Declared pure (Minecraft-free): callers wire
	 * it through {@link #readFreshest} (or a command) to hand the live publish.
	 *
	 * @param snap the published snapshot (freshest)
	 * @param windowCenter the domain box center (the snapshot's job window)
	 * @param blockX/Y/Z the block position to read
	 */
	public static SeamReadout read(FieldSnapshot snap, double[] windowCenter,
			int blockX, int blockY, int blockZ) {
		double[] wc = windowCenter;
		double ox = blockX + 0.5 - wc[0];
		double oy = blockY + 0.5 - wc[1];
		double oz = blockZ + 0.5 - wc[2];
		double distToEdge = Math.max(0.0,
				TwoFluidSolver.EXTENT - Math.max(Math.abs(ox), Math.max(Math.abs(oy), Math.abs(oz))));
		boolean inside = distToEdge > 0.0 || withinSlice(ox, oy, oz);
		SeamState state = inside && distToEdge <= EDGE_BAND_BLOCKS ? SeamState.EDGE_BAND : SeamState.INTERIOR;
		if (!inside) {
			state = null;
		}
		int cellX = (int) Math.floor(Quantizer.gridCoord(blockX, wc[0]));
		int cellY = (int) Math.floor(Quantizer.gridCoord(blockY, wc[1]));
		int cellZ = (int) Math.floor(Quantizer.gridCoord(blockZ, wc[2]));
		Quantizer.CellSample s = Quantizer.sampleAt(snap, wc, blockX, blockY, blockZ);
		Quantizer.BlockKind kind = Quantizer.quantizeCold(s.rho(), s.q(), s.eps2());

		String text = buildText(blockX, blockY, blockZ, wc, ox, oy, oz, distToEdge, inside, state, cellX, cellY, cellZ, kind);
		// distanceToEdge is the height/width clearance to the nearest box face in metres.
		return new SeamReadout(ox, oy, oz, distToEdge, cellX, cellY, cellZ, inside, state, kind, s.rho(), s.q(), s.eps2(), text);
	}

	private static boolean withinSlice(double ox, double oy, double oz) {
		// A block exactly on an outer face (distToEdge == 0) is still the box's iso-surface cell.
		return Math.abs(ox) <= TwoFluidSolver.EXTENT && Math.abs(oy) <= TwoFluidSolver.EXTENT
				&& Math.abs(oz) <= TwoFluidSolver.EXTENT;
	}

	/**
	 * Shared single entry point used by the {@code /cassicraft seam} command:
	 * pull the freshest publish and read the seam at a block position.
	 *
	 * @return the readout, or {@code null} if the domain has not published yet.
	 */
	public static SeamReadout readFreshest(SnapshotPublisher pub,
			int blockX, int blockY, int blockZ) {
		FieldSnapshot snap = pub.freshest();
		if (snap == null) {
			return null;
		}
		double[] window = snap.job() != null && !snap.job().isWindowless()
				? snap.job().windowCenter()
				: new double[] { 0, 0, 0 };
		return read(snap, window, blockX, blockY, blockZ);
	}

	private static String buildText(int bx, int by, int bz, double[] wc,
			double ox, double oy, double oz, double distToEdge, boolean inside,
			SeamState state, int cellX, int cellY, int cellZ, Quantizer.BlockKind kind) {
		StringBuilder sb = new StringBuilder();
		sb.append("Cassi seam @ (").append(bx).append(",").append(by).append(",").append(bz).append(")\n");
		if (!inside) {
			sb.append("  window position: OUTSIDE the 192\u00b3 box (window center at ")
					.append(fmt(wc[0])).append(",").append(fmt(wc[1])).append(",").append(fmt(wc[2])).append(")\n");
			sb.append("  seam state: beyond the window edge \u2014 reads Air (the field's outer iso-surface)\n");
			sb.append("  the field is a torus; the window re-homes behind you, so the edge stays out of play");
			return sb.toString();
		}
		sb.append("  window position: ").append(fmt(ox)).append("m ").append(fmt(oy)).append("m ").append(fmt(oz)).append("m")
				.append(" from the live window center (").append(fmt(wc[0])).append(",").append(fmt(wc[1])).append(",").append(fmt(wc[2])).append(")\n");
		sb.append("  grid cell: (").append(cellX % TwoFluidSolver.N).append(",").append(cellY % TwoFluidSolver.N).append(",")
				.append(cellZ % TwoFluidSolver.N).append(") / ").append(TwoFluidSolver.N).append(" per axis\n");
		String sit = describeState(state, distToEdge);
		sb.append("  seam state: ").append(sit).append("\n");
		sb.append("  block kind: ").append(kind.name());
		return sb.toString();
	}

	private static String describeState(SeamState state, double distToEdge) {
		if (state == null) {
			return "out of the box";
		}
		if (state == SeamState.EDGE_BAND) {
			return "EDGE_BAND \u2014 within " + EDGE_BAND_BLOCKS + " m of the window boundary (the field's outer iso-surface; here the "
					+ "world is still world-fixed, and the window edge is a deterministic iso-surface, never a wall)";
		}
		return "INTERIOR \u2014 well inside the re-homed window's living field (the edge is " + String.format("%.1f", distToEdge) + " m away)";
	}

	private static String fmt(double v) {
		return String.format("%.1f", v);
	}

	private SeamRead() {
	}
}
