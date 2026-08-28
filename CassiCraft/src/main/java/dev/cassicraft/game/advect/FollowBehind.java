package dev.cassicraft.game.advect;

import dev.cassicraft.domain.engine.TwoFluidSolver;
import dev.cassicraft.domain.snapshot.FieldSnapshot;
import dev.cassicraft.domain.snapshot.SnapshotPublisher;
import dev.cassicraft.domain.thread.CassiFieldThread;
import net.minecraft.core.BlockPos;
import net.minecraft.server.level.ServerLevel;
import net.minecraft.server.level.ServerPlayer;

/**
 * Follow-behind advection coordinator (corpus-map.md §4 — the Phase-1.5
 * follow-behind item; world-seams.md §4.2's anchor-to-window relocation policy;
 * async-field-domain.md §7 Q1's movable home-window). On each server tick it
 * reads the first online player's block position and the freshest published
 * {@code window_center} — the seam, never a raw buffer, never a block write —
 * and, when the player's center displacement has crossed a whole cell boundary
 * away from the live center, calls {@link CassiFieldThread#rehome} so the worker
 * drains the move on its own thread (async-field-domain.md §5: the server never
 * touches domain buffers).
 *
 * <p>The box <em>re-homes behind the player</em> — the torus slides so the
 * player stays within ±½ cell (≈±1.5 m) of the box center — while the field
 * itself stays world-fixed (the worker's roll is a pure periodic permutation,
 * the honesty rule: no terrain is created or destroyed at the seam). Fires only
 * on actual whole-cell (3 m) drift, never per-tick spam.
 */
public final class FollowBehind {

	/**
	 * [design] Whole-cell re-home granularity — the box center snaps to the 3 m
	 * grid (PORT-SPEC §5), so a re-home fires only after the player crosses a
	 * whole cell (world-seams.md §4.2's anchor-to-window).
	 */
	public static final double CELL_WIDTH =
			2.0 * TwoFluidSolver.EXTENT / TwoFluidSolver.N;

	private final SnapshotPublisher publisher;
	private final CassiFieldThread fieldThread;

	public FollowBehind(SnapshotPublisher publisher, CassiFieldThread fieldThread) {
		this.publisher = publisher;
		this.fieldThread = fieldThread;
	}

	/**
	 * Called every server tick. Read-only on the domain; submits a re-home only
	 * when the player has drifted a whole cell from the live published center.
	 * With no player online (or no publish yet) it is a no-op.
	 */
	public void onServerTick(ServerLevel level) {
		ServerPlayer player = firstPlayer(level);
		if (player == null) {
			return;
		}
		FieldSnapshot snap = publisher.freshest();
		if (snap == null || snap.job() == null || snap.job().isWindowless()) {
			return;
		}
		double[] center = snap.job().windowCenter();
		BlockPos pos = player.blockPosition();
		int dx = (int) Math.round((pos.getX() - center[0]) / CELL_WIDTH);
		int dy = (int) Math.round((pos.getY() - center[1]) / CELL_WIDTH);
		int dz = (int) Math.round((pos.getZ() - center[2]) / CELL_WIDTH);
		if (dx == 0 && dy == 0 && dz == 0) {
			return;
		}
		// Target the player's position; the worker snaps to whole cells and rolls.
		fieldThread.rehome(pos.getX(), pos.getY(), pos.getZ());
	}

	/** The first online player, or {@code null} if the overworld is empty. */
	private static ServerPlayer firstPlayer(ServerLevel level) {
		for (ServerPlayer p : level.players()) {
			return p;
		}
		return null;
	}
}
