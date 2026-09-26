package dev.cassicraft.game.chart;

import net.minecraft.network.chat.Component;
import net.minecraft.server.level.ServerPlayer;

/** Server-side text presentation only; the chart never renders a client map. */
public final class FieldChartPresenter {
    public static void present(ServerPlayer player, FieldChartCoordinator.Result result) {
        player.sendSystemMessage(Component.literal(result.message()));
    }
    public static void present(ServerPlayer player, FieldChartBearing.Result result) {
        player.sendSystemMessage(Component.literal(result.message()));
    }

    private FieldChartPresenter() {}
}
