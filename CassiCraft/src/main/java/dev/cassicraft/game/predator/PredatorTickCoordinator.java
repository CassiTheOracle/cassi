package dev.cassicraft.game.predator;

import dev.cassicraft.domain.snapshot.SnapshotPublisher;
import net.minecraft.server.MinecraftServer;
import net.minecraft.server.level.ServerLevel;
import net.minecraft.world.level.entity.EntityTypeTest;

/**
 * The signature predator's server-tick handoff (signature-predator.md §8 — the
 * Phase-1 slice): each tick it attaches the session's live publish handoff to
 * every {@link SignaturePredatorEntity} in the world. The entity's own
 * {@link SignaturePredatorEntity#tick()} then reads the freshest snapshot and
 * runs the deterministic hunt decision law against it.
 *
 * <p>This is the only wiring the predator needs beyond registration — same
 * no-mixin, vanilla-entity pattern as the minecart ride coordinator. It never
 * mutates the field, never writes a block, never touches the player; it just
 * hands each live predator the same publish seam every other consumer reads.
 * A safe no-op with zero predators or no publish yet.
 */
public final class PredatorTickCoordinator {

	/**
	 * Iteration box — a wide AABB over the loaded world's predators. The field
	 * box is 96-extent; a predator far outside (out-of-box air) reads zero and
	 * holds, so the iteration only needs to reach every loaded predator.
	 */
	private static final double ITERATE_HALF = 4000.0;

	private final SnapshotPublisher publisher;

	public PredatorTickCoordinator(SnapshotPublisher publisher) {
		this.publisher = publisher;
	}

	/** Attach the live publish handoff to every loaded signature predator, each server tick. */
	public void onServerTick(MinecraftServer server) {
		ServerLevel overworld = server.overworld();
		if (overworld == null) {
			return;
		}
		for (SignaturePredatorEntity pred : overworld.getEntities(
				EntityTypeTest.forClass(SignaturePredatorEntity.class),
				SignaturePredatorEntity::isAlive)) {
			pred.attachPublisher(publisher);
		}
	}
}
