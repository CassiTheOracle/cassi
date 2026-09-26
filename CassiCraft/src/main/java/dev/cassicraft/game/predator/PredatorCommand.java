package dev.cassicraft.game.predator;

import com.mojang.brigadier.CommandDispatcher;
import dev.cassicraft.domain.snapshot.SnapshotPublisher;
import net.minecraft.commands.CommandSourceStack;
import net.minecraft.commands.Commands;
import net.minecraft.network.chat.Component;
import net.minecraft.server.level.ServerLevel;
import net.minecraft.server.level.ServerPlayer;
import net.minecraft.world.entity.EntitySpawnReason;

/**
 * The {@code /cassicraft predator} command — spawn a signature predator at the
 * caller's position (attaching the live publish handoff so it can read the
 * published field), or toggle the live predator population in the world. The
 * predator is a vanilla {@link SignaturePredatorEntity} that hunts by field
 * signature (signature-predator.md §8 — the Phase-1 embodied slice).
 *
 * <p>The command is a <b>spawn</b>, not a write: it summons a vanilla entity
 * that reads the field; it never perturbs the field, never writes a block,
 * never mints (with a predator, nothing is created in the field — only an
 * entity that senses it). The publisher is taken from the Weatherglass's live
 * session handoff, the same seam every consumer reads.
 */
public final class PredatorCommand {

	/**
	 * Register {@code /cassicraft predator} — spawn one, or toggle the population.
	 *
	 * <ul>
	 *   <li><b>{@code /cassicraft predator}</b> — spawn one predator at the
	 *       caller's position (console → the world spawn), named
	 *       <code>The Coda</code>.</li>
	 *   <li><b>{@code /cassicraft predator clear}</b> — remove every live
	 *       signature predator from the world (the population toggle down).</li>
	 * </ul>
	 */
	public static void register(CommandDispatcher<CommandSourceStack> dispatcher) {
		dispatcher.register(Commands.literal("cassicraft")
				.then(Commands.literal("predator")
						.executes(ctx -> spawn(ctx.getSource(), 1))
						.then(Commands.literal("clear").executes(ctx -> clear(ctx.getSource())))));
	}

	private static int spawn(CommandSourceStack source, int count) {
		if (dev.cassicraft.CassiCraft.WEATHERGLASS == null || PredatorRegistration.TYPE == null) {
			source.sendFailure(Component.literal("The predator is not armed (no world loaded, or not registered)."));
			return 0;
		}
		ServerLevel level = source.getServer().overworld();
		if (level == null) {
			source.sendFailure(Component.literal("The overworld is not available."));
			return 0;
		}
		SnapshotPublisher pub = dev.cassicraft.CassiCraft.WEATHERGLASS.publisherSupplier().get();
		ServerPlayer player = source.getPlayer();
		double x = player != null ? player.getX() : (level.getRespawnData() != null && level.getRespawnData().pos() != null
				? level.getRespawnData().pos().getX() : 0);
		double y = player != null ? player.getY() : (level.getRespawnData() != null && level.getRespawnData().pos() != null
				? level.getRespawnData().pos().getY() : 70);
		double z = player != null ? player.getZ() : (level.getRespawnData() != null && level.getRespawnData().pos() != null
				? level.getRespawnData().pos().getZ() : 0);

		int spawned = 0;
		for (int i = 0; i < count; i++) {
			SignaturePredatorEntity pred = PredatorRegistration.TYPE.create(level, EntitySpawnReason.COMMAND);
			pred.attachPublisher(pub);
			pred.setPos(x, y, z);
			pred.setYRot(level.getRandom().nextFloat() * 360f);
			pred.setPredatorName("The Coda");
			level.addFreshEntity(pred);
			spawned++;
		}
		final int spawnedFinal = spawned;
		source.sendSuccess(() -> Component.literal("Spawned " + spawnedFinal + " signature predator (The Coda) — "
				+ "it hunts the field's signature gradient, not your coordinates."), true);
		return 1;
	}

	private static int clear(CommandSourceStack source) {
		ServerLevel overworld = source.getServer().overworld();
		if (overworld == null) {
			source.sendFailure(Component.literal("The overworld is not available."));
			return 0;
		}
		java.util.List<? extends SignaturePredatorEntity> preds = overworld.getEntities(
				net.minecraft.world.level.entity.EntityTypeTest.forClass(SignaturePredatorEntity.class),
				SignaturePredatorEntity::isAlive);
		int removed = 0;
		for (SignaturePredatorEntity p : preds) {
			p.discard();
			removed++;
		}
		final int removedFinal = removed;
		source.sendSuccess(() -> Component.literal("Removed " + removedFinal + " signature predator(s)."), true);
		return 1;
	}

	private PredatorCommand() {
	}
}
