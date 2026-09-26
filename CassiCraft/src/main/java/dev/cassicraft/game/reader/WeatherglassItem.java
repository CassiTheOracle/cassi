package dev.cassicraft.game.reader;

import dev.cassicraft.domain.snapshot.SnapshotPublisher;
import dev.cassicraft.game.expedition.ExpeditionCoordinator;
import net.minecraft.network.chat.Component;
import net.minecraft.server.level.ServerPlayer;
import net.minecraft.world.InteractionHand;
import net.minecraft.world.InteractionResult;
import net.minecraft.world.entity.player.Player;
import net.minecraft.world.item.Item;
import net.minecraft.world.level.Level;

import java.util.function.Supplier;

/** Player-facing pure field readout with an ordinary sneak-use expedition hook. */
public class WeatherglassItem extends Item {
    private final Supplier<SnapshotPublisher> publisher;
    private final Supplier<ExpeditionCoordinator> expedition;

    public WeatherglassItem(Supplier<SnapshotPublisher> publisher,
            Supplier<ExpeditionCoordinator> expedition, Properties properties) {
        super(properties);
        this.publisher = publisher;
        this.expedition = expedition;
    }

    public Supplier<SnapshotPublisher> publisherSupplier() { return publisher; }

    @Override
    public InteractionResult use(Level level, Player player, InteractionHand hand) {
        if (!level.isClientSide() && player instanceof ServerPlayer serverPlayer) {
            if (serverPlayer.isCrouching()) {
                ExpeditionCoordinator coordinator = expedition.get();
                if (coordinator == null) {
                    serverPlayer.sendSystemMessage(Component.literal("The expedition desk is not ready yet."));
                } else {
                    coordinator.start(serverPlayer);
                }
            } else {
                net.minecraft.core.BlockPos pos = player.blockPosition();
                FieldReader.FieldReadout r = FieldReader.readFreshest(
                        publisher.get(), pos.getX(), pos.getY(), pos.getZ());
                if (r == null) {
                    serverPlayer.sendSystemMessage(Component.literal("The Weatherglass is dark — the field is not yet publishing."));
                } else {
                    serverPlayer.sendSystemMessage(Component.literal(r.text()));
                }
            }
        }
        return InteractionResult.SUCCESS;
    }
}
