package dev.cassicraft.game.chart;

import java.util.function.Supplier;

import net.minecraft.server.level.ServerPlayer;
import net.minecraft.world.InteractionHand;
import net.minecraft.world.InteractionResult;
import net.minecraft.world.entity.player.Player;
import net.minecraft.world.item.Item;
import net.minecraft.world.level.Level;

/** Session-local chart instrument: plain use inspects; sneak use draws or explicitly redraws. */
public final class FieldChartItem extends Item {
    private final Supplier<FieldChartCoordinator> coordinator;

    public FieldChartItem(Supplier<FieldChartCoordinator> coordinator, Properties properties) {
        super(properties);
        this.coordinator = coordinator;
    }

    @Override
    public InteractionResult use(Level level, Player player, InteractionHand hand) {
        if (!level.isClientSide() && player instanceof ServerPlayer serverPlayer) {
            FieldChartCoordinator chart = coordinator.get();
            if (chart == null) {
                serverPlayer.sendSystemMessage(net.minecraft.network.chat.Component.literal(
                        "The Field Chart is not armed (no world loaded)."));
            } else {
                FieldChartPresenter.present(serverPlayer,
                        FieldChartActions.itemUse(chart, serverPlayer.getUUID(),
                                serverPlayer.blockPosition(), serverPlayer.isCrouching()));
            }
        }
        return InteractionResult.SUCCESS;
    }
}
