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
 * Instead, once the field's first snapshot publishes, this coordinator finds the
 * top solid block on the anchor column (the box's outer iso-surface) and sets the
 * world's <b>respawn data</b> a couple of blocks above it, so the first player
 * stands ON the field, not inside it.
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

		// Scan downward from the box's top surface for the first solid block.
		int boxTopWorldY = (int) Math.round(anchor[1] + TwoFluidSolver.EXTENT);
		int topSolidY = Integer.MIN_VALUE;
		for (int y = boxTopWorldY; y >= boxTopWorldY - (int) TwoFluidSolver.EXTENT * 2; y--) {
			Quantizer.CellSample s = Quantizer.sampleAt(snap, wc, ax, y, az);
			if (s.rho() >= Quantizer.TAU_C) {
				topSolidY = y;
				break;
			}
		}
		if (topSolidY == Integer.MIN_VALUE) {
			// No solid in the column (nothing to stand on yet) — retry next tick.
			return;
		}
		int standY = topSolidY + 1 + SURFACE_CLEARANCE; // feet one above the top solid
		BlockPos respawn = new BlockPos(ax, standY, az);
		level.setRespawnData(LevelData.RespawnData.of(net.minecraft.world.level.Level.OVERWORLD, respawn, 0f, 0f));
		done = true;
		LOGGER.info("[cassicraft/spawn] window anchored at ({},{},{}), surface top solid y={}, respawn set at {}",
				(int) Math.round(anchor[0]), (int) Math.round(anchor[1]), (int) Math.round(anchor[2]),
				topSolidY, respawn);
	}
}
