package dev.cassicraft.game.spawn;

import dev.cassicraft.domain.engine.TwoFluidSolver;
import dev.cassicraft.domain.snapshot.FieldSnapshot;
import dev.cassicraft.domain.snapshot.SnapshotPublisher;
import dev.cassicraft.game.sampler.Quantizer;
import net.minecraft.core.BlockPos;
import net.minecraft.server.level.ServerLevel;
import net.minecraft.world.level.storage.LevelData;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

/**
 * The player's spawn on the field's surface — the honest entry to the demo world.
 * Because the field interior is a solid mass (ρ ≥ τ_c almost everywhere at the
 * initial state), a player placed at the box's center would be embedded in stone.
 * Instead, once the field's first snapshot publishes, this coordinator finds a
 * <b>coherent surface plane</b> near the box's outer iso-surface and sets the
 * world's <b>respawn data</b> a couple of blocks above it, so the first player
 * stands ON the field, not inside it.
 *
 * <p>The scan is coherent-surface, not single-column (chunk-field-quantization.md
 * §1.3 "an iso-surface cuts the blocks"): it scans DOWN from the box top and
 * finds the highest y where the anchor column is solid AND a local patch of
 * neighboring columns is consistently solid at that level ({@link
 * #PLANE_FRACTION}). A single top-of-column blob is rejected — the player only
 * spawns on a multi-column plane they can actually walk on without immediately
 * toppling into a hole. On the measured field (a uniform ~70%-solid sponge at
 * the near-IC settle, see SurfaceDiagnosticsMain M1) this lands the player on
 * the field's densest coherent roof rather than on a one-column spike. If no
 * coherent plane exists yet, the scan falls back to the single anchor column so
 * the spawn still resolves once the field surfaces at all.
 *
 * <p>The corpus's entry/spawn concept is visible, not hidden: it is the normal
 * world respawn point (a {@code LevelData.RespawnData}, a vanilla-visible world
 * default), and it is placed where the field actually surfaces. This coordinator
 * is a pure consumer of the domain (reads the publish to find the surface) plus
 * one world-default set — it never writes blocks (the only-mutator rule for block
 * state is absolute, held by {@code dev.cassicraft.game.writer.WorldWriter}).
 *
 * <p>It runs once per session: tick until the first snapshot publishes, then set
 * the respawn and stop.
 */
public final class SurfaceSpawn {

	private static final Logger LOGGER = LoggerFactory.getLogger(SurfaceSpawn.class);
	/** Blocks of air above the field surface (feet at topSolid, head clear). */
	private static final int SURFACE_CLEARANCE = 1;
	/**
	 * Half-side of the local column patch scanned for the coherent surface — a
	 * 5×5 patch (radius 2) around the anchor, cheap and local (25 sampleAt calls
	 * per y). The measured field is a ~70%-solid sponge with random air holes, so
	 * a patch this size catches a consistent roof without being smeared across the
	 * whole box.
	 */
	private static final int PATCH_RADIUS = 2;
	/**
	 * Consistency threshold for the coherent surface: at least this fraction of
	 * the patch columns must be solid at the candidate y for it to count as a
	 * walkable plane. On the ~71%-solid sponge a 0.6 threshold accepts the dense
	 * roof while rejecting a lone spike (SurfaceDiagnosticsMain M1).
	 */
	private static final double PLANE_FRACTION = 0.60;

	private final SnapshotPublisher publisher;
	private final double[] anchor;
	private boolean done;

	public SurfaceSpawn(SnapshotPublisher publisher, double[] anchor) {
		this.publisher = publisher;
		this.anchor = anchor.clone();
	}

	/** Called each server tick; sets the respawn once the field has published. */
	public void onServerTick(ServerLevel level) {
		if (done) {
			return;
		}
		FieldSnapshot snap = publisher.freshest();
		if (snap == null) {
			return; // field not publishing yet — retry next tick
		}
		double[] wc = snap.job() != null && !snap.job().isWindowless()
				? snap.job().windowCenter()
				: anchor;
		int ax = (int) Math.round(anchor[0]);
		int az = (int) Math.round(anchor[2]);

		// Scan downward from the box's top surface for a coherent multi-column plane.
		int boxTopWorldY = (int) Math.round(anchor[1] + TwoFluidSolver.EXTENT);
		int coherentY = findCoherentSurface(snap, wc, ax, az, boxTopWorldY);
		int topSolidY = coherentY;

		// Fall back: no coherent plane yet — use the single anchor column so the
		// spawn still resolves once the anchor column itself surfaces at all.
		if (topSolidY == Integer.MIN_VALUE) {
			topSolidY = topSolidAnchorColumn(snap, wc, ax, az, boxTopWorldY);
		}
		if (topSolidY == Integer.MIN_VALUE) {
			// No solid in the column (nothing to stand on yet) — retry next tick.
			return;
		}
		int standY = topSolidY + 1 + SURFACE_CLEARANCE; // feet one above the top solid
		BlockPos respawn = new BlockPos(ax, standY, az);
		level.setRespawnData(LevelData.RespawnData.of(net.minecraft.world.level.Level.OVERWORLD, respawn, 0f, 0f));
		done = true;
		LOGGER.info("[cassicraft/spawn] window anchored at ({},{},{}), coherent surface top y={}{}, respawn set at {}",
				(int) Math.round(anchor[0]), (int) Math.round(anchor[1]), (int) Math.round(anchor[2]),
				topSolidY, (coherentY == topSolidY ? " (coherent plane)" : " (single-column fallback)"), respawn);
	}

	/**
	 * The highest y where the anchor column is solid, the two blocks above it are
	 * air (headroom to stand), AND at least {@link #PLANE_FRACTION} of the local
	 * {@code PATCH_RADIUS} column patch is solid at that level — a coherent,
	 * walkable plane the player stands on rather than a single-column blob.
	 * {@code Integer.MIN_VALUE} if no such plane exists. Public so the headless
	 * surface probe exercises the real spawn scan.
	 */
	public static int findCoherentSurface(FieldSnapshot snap, double[] wc,
			int ax, int az, int boxTopWorldY) {
		int patchCount = (2 * PATCH_RADIUS + 1) * (2 * PATCH_RADIUS + 1);
		for (int y = boxTopWorldY; y >= boxTopWorldY - (int) TwoFluidSolver.EXTENT * 2; y--) {
			if (Quantizer.sampleAt(snap, wc, ax, y, az).rho() < Quantizer.TAU_C) {
				continue; // the anchor itself is not solid here — no standing block
			}
			// Headroom: the two blocks above the plane must be air on the anchor
			// column, or the player would spawn embedded in an overhang.
			boolean headClear = Quantizer.sampleAt(snap, wc, ax, y + 1, az).rho() < Quantizer.TAU_C
					&& Quantizer.sampleAt(snap, wc, ax, y + 2, az).rho() < Quantizer.TAU_C;
			if (!headClear) {
				continue;
			}
			int patchSolid = 0;
			for (int dz = -PATCH_RADIUS; dz <= PATCH_RADIUS; dz++) {
				for (int dx = -PATCH_RADIUS; dx <= PATCH_RADIUS; dx++) {
					if (Quantizer.sampleAt(snap, wc, ax + dx, y, az + dz).rho() >= Quantizer.TAU_C) {
						patchSolid++;
					}
				}
			}
			if (patchSolid >= PLANE_FRACTION * patchCount) {
				return y;
			}
		}
		return Integer.MIN_VALUE;
	}

	/** The first solid on the anchor column, scanning down from the box top (the classic scan). */
	public static int topSolidAnchorColumn(FieldSnapshot snap, double[] wc,
			int ax, int az, int boxTopWorldY) {
		for (int y = boxTopWorldY; y >= boxTopWorldY - (int) TwoFluidSolver.EXTENT * 2; y--) {
			if (Quantizer.sampleAt(snap, wc, ax, y, az).rho() >= Quantizer.TAU_C) {
				return y;
			}
		}
		return Integer.MIN_VALUE;
	}
}
