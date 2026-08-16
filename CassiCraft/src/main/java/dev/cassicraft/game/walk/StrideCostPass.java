package dev.cassicraft.game.walk;

import dev.cassicraft.domain.snapshot.FieldSnapshot;
import dev.cassicraft.domain.snapshot.SnapshotPublisher;
import dev.cassicraft.game.sampler.Quantizer;
import net.minecraft.server.level.ServerLevel;
import net.minecraft.server.level.ServerPlayer;
import net.minecraft.world.entity.player.Inventory;
import net.minecraft.world.phys.Vec3;

/**
 * The movement-cost pass (corpus-map §4 step 4) — applies the stride-cost drag
 * to players as they move. A <b>pure consumer of the domain</b>: each cadence it
 * samples the player's position from the published snapshot and applies a small,
 * bounded horizontal drag derived from the stride-cost read ({@link MovementCost}).
 *
 * <p>Honest mechanics, per the-walk §4d (no-free-energy cap) and §1.2 (no boost):
 * the drag <b>slows</b> movement in dear regions (thin: high {@code (1−q)};
 * decoherent: high {@code ε²}) and it does <b>not</b> speed the player anywhere —
 * a descent easement only <em>reduces</em> the drag toward zero at foot-pace,
 * never taking it below 0 or adding velocity. The effect is deterministic
 * (same field state → same drag), reversible (step out of the region and the
 * drag lifts), and legible (it tracks the (1−q)/ε² channels the Weatherglass
 * already shows). Never mutates blocks — the only-mutator rule for block state
 * is absolute (the {@code dev.cassicraft.game.writer.WorldWriter} alone).
 * The player's carried load is estimated from the inventory's held-item count —
 * a [design] proxy for the pack's field-read weight (the-carry §2).
 */
public final class StrideCostPass {

	/** Cadence in server ticks — re-cost the player's stride this often. */
	private static final int COST_EVERY_TICKS = 10;
	/** Max drag magnitude applied per pass as a fraction of current horizontal speed [design]. */
	private static final float MAX_DRAG_FRACTION = 0.08f;

	private final SnapshotPublisher publisher;
	private long lastCostTick = -1;

	public StrideCostPass(SnapshotPublisher publisher) {
		this.publisher = publisher;
	}

	/** Called every server tick. Read-only on the domain; applies a bounded drag. */
	public void onServerTick(ServerLevel level, long tick) {
		if (tick - lastCostTick < COST_EVERY_TICKS) {
			return;
		}
		lastCostTick = tick;
		for (ServerPlayer player : level.players()) {
			costPlayer(player);
		}
	}

	private void costPlayer(ServerPlayer player) {
		FieldSnapshot snap = publisher.freshest();
		if (snap == null) {
			return;
		}
		double[] windowCenter = snap.job() != null && !snap.job().isWindowless()
				? snap.job().windowCenter()
				: new double[] { 0, 0, 0 };
		Quantizer.FieldReading r = Quantizer.sampleReading(snap, windowCenter,
				player.getBlockX(), player.getBlockY(), player.getBlockZ());
		Vec3 vel = player.getDeltaMovement();
		float load = estimateLoad(player);
		MovementCost.StrideCost cost = MovementCost.strideCost(r, vel.x, vel.y, vel.z, load);
		if (cost.drag() > 0.001f) {
			// Bounded, reversible drag along the current travel — never a boost.
			double keep = 1.0 - MAX_DRAG_FRACTION * cost.drag();
			player.setDeltaMovement(vel.x * keep, vel.y, vel.z * keep);
		}
	}

	/** [design] proxy for the pack's weight: held-inventory occupancy → [0,1] load. */
	private static float estimateLoad(ServerPlayer player) {
		Inventory inv = player.getInventory();
		int occupied = inv.getContainerSize(); // total slots
		int filled = 0;
		for (int i = 0; i < occupied; i++) {
			if (!inv.getItem(i).isEmpty()) {
				filled++;
			}
		}
		return occupied == 0 ? 0f : Math.min(1f, (float) filled / occupied);
	}
}
