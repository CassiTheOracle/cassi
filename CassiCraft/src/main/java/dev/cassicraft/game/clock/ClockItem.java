package dev.cassicraft.game.clock;

import dev.cassicraft.domain.snapshot.SnapshotPublisher;
import dev.cassicraft.game.reader.FieldReader;
import net.minecraft.network.chat.Component;
import net.minecraft.server.level.ServerPlayer;
import net.minecraft.world.InteractionHand;
import net.minecraft.world.InteractionResult;
import net.minecraft.world.entity.player.Player;
import net.minecraft.world.item.Item;
import net.minecraft.world.level.Level;

import java.util.function.Supplier;

/** Player-facing, read-only local tempo presentation over the latest field publish. */
public final class ClockItem extends Item {
    private final Supplier<SnapshotPublisher> publisher;

    public ClockItem(Supplier<SnapshotPublisher> publisher, Properties properties) {
        super(properties);
        this.publisher = publisher;
    }

    @Override
    public InteractionResult use(Level level, Player player, InteractionHand hand) {
        if (!level.isClientSide() && player instanceof ServerPlayer serverPlayer) {
            ClockRead.Tempo tempo = readAt(player.blockPosition().getX(), player.blockPosition().getY(), player.blockPosition().getZ());
            if (tempo == null) {
                serverPlayer.sendSystemMessage(Component.literal("The Clock is dark — the field is not yet publishing."));
            } else {
                serverPlayer.sendSystemMessage(Component.literal(tempo.text()));
            }
        }
        return InteractionResult.SUCCESS;
    }

    /** Shared latest-publish read for the item and /cassicraft tempo command. */
    public ClockRead.Tempo readAt(int x, int y, int z) {
        FieldReader.FieldReadout reading = FieldReader.readFreshest(publisher.get(), x, y, z);
        return reading == null ? null : ClockRead.read(reading.q());
    }

    public Supplier<SnapshotPublisher> publisherSupplier() {
        return publisher;
    }
}
