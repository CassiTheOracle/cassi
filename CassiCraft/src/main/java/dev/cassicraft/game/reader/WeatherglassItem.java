package dev.cassicraft.game.reader;

import dev.cassicraft.domain.snapshot.SnapshotPublisher;
import net.minecraft.network.chat.Component;
import net.minecraft.server.level.ServerPlayer;
import net.minecraft.world.InteractionHand;
import net.minecraft.world.InteractionResult;
import net.minecraft.world.entity.player.Player;
import net.minecraft.world.item.Item;
import net.minecraft.world.item.ItemStack;
import net.minecraft.world.level.Level;

import java.util.function.Supplier;

/**
 * The Weatherglass item (field-instruments.md §1, corpus-map §4 step 2) — a
 * player-facing field readout. It is a <b>pure consumer</b> of the published
 * snapshot: right-clicking reads the field at the player's block position via
 * the {@link FieldReader} path and shows the readout as a message. It never
 * mutates world state (the only-mutator rule is absolute).
 *
 * <p>Phase-1 honest slice: the worn, always-on emissive bauble rendering (a
 * continuously-updating client model / lume) is deferred — that needs a client
 * model + network channel. This item carries the same read (the corpus's
 * "glanceable" data path, one sample at the player's position on use), so the
 * readout is visible and testable now; the always-on form is the later slice.
 *
 * <p>The item holds a {@link Supplier} of the live session's
 * {@link SnapshotPublisher} (the publisher is re-created per world session).
 */
public class WeatherglassItem extends Item {

	private final Supplier<SnapshotPublisher> publisher;

	public WeatherglassItem(Supplier<SnapshotPublisher> publisher, Properties properties) {
		super(properties);
		this.publisher = publisher;
	}

	/** The live session's publisher supplier (shared by the {@code /cassicraft read} command). */
	public Supplier<SnapshotPublisher> publisherSupplier() {
		return publisher;
	}

	@Override
	public InteractionResult use(Level level, Player player, InteractionHand hand) {
		if (!level.isClientSide() && player instanceof ServerPlayer serverPlayer) {
			net.minecraft.core.BlockPos pos = player.blockPosition();
			FieldReader.FieldReadout r = FieldReader.readFreshest(
					publisher.get(), pos.getX(), pos.getY(), pos.getZ());
			if (r == null) {
				serverPlayer.sendSystemMessage(Component.literal("The Weatherglass is dark \u2014 the field is not yet publishing."));
			} else {
				serverPlayer.sendSystemMessage(Component.literal(r.text()));
			}
		}
		// Consume the interaction on the client too (swing is expected).
		return InteractionResult.SUCCESS;
	}
}
