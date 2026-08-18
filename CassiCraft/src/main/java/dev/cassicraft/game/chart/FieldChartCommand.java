package dev.cassicraft.game.chart;

import com.mojang.brigadier.CommandDispatcher;
import com.mojang.brigadier.arguments.IntegerArgumentType;
import net.minecraft.commands.CommandSourceStack;
import net.minecraft.commands.Commands;
import net.minecraft.server.level.ServerPlayer;

/** /cassicraft chart command family, following existing separate-root conventions. */
public final class FieldChartCommand {
    public static void register(CommandDispatcher<CommandSourceStack> dispatcher, java.util.function.Supplier<FieldChartCoordinator> coordinator) {
        var root = Commands.literal("cassicraft");
        var chart = Commands.literal("chart").executes(ctx -> inspect(ctx.getSource(), coordinator))
                .then(Commands.literal("draw").executes(ctx -> capture(ctx.getSource(), coordinator, false)))
                .then(Commands.literal("redraw").executes(ctx -> capture(ctx.getSource(), coordinator, true)))
                .then(Commands.literal("slot").then(Commands.argument("slot", IntegerArgumentType.integer(0, FieldChartCoordinator.SLOT_COUNT - 1))
                        .executes(ctx -> slot(ctx.getSource(), coordinator, IntegerArgumentType.getInteger(ctx, "slot")))))
                .then(Commands.literal("summary").executes(ctx -> summary(ctx.getSource(), coordinator)));
        root.then(chart); dispatcher.register(root);
    }
    private static int inspect(CommandSourceStack source, java.util.function.Supplier<FieldChartCoordinator> supplier) {
        ServerPlayer player = source.getPlayer(); FieldChartCoordinator chart = ready(source, supplier);
        if (player == null || chart == null) return 0;
        FieldChartPresenter.present(player, FieldChartActions.inspect(chart, player.getUUID())); return 1;
    }
    private static int capture(CommandSourceStack source, java.util.function.Supplier<FieldChartCoordinator> supplier, boolean redraw) {
        ServerPlayer player = source.getPlayer(); FieldChartCoordinator chart = ready(source, supplier);
        if (player == null || chart == null) return 0;
        FieldChartCoordinator.Result result = redraw ? FieldChartActions.redraw(chart, player.getUUID(), player.blockPosition()) : FieldChartActions.draw(chart, player.getUUID(), player.blockPosition());
        FieldChartPresenter.present(player, result); return result.accepted() ? 1 : 0;
    }
    private static int slot(CommandSourceStack source, java.util.function.Supplier<FieldChartCoordinator> supplier, int slot) {
        ServerPlayer player = source.getPlayer(); FieldChartCoordinator chart = ready(source, supplier);
        if (player == null || chart == null) return 0;
        FieldChartPresenter.present(player, FieldChartActions.slot(chart, player.getUUID(), slot)); return 1;
    }
    private static int summary(CommandSourceStack source, java.util.function.Supplier<FieldChartCoordinator> supplier) {
        ServerPlayer player = source.getPlayer(); FieldChartCoordinator chart = ready(source, supplier);
        if (player == null || chart == null) return 0;
        FieldChartPresenter.present(player, FieldChartActions.summary(chart, player.getUUID())); return 1;
    }
    private static FieldChartCoordinator ready(CommandSourceStack source, java.util.function.Supplier<FieldChartCoordinator> supplier) {
        if (!(source.getEntity() instanceof ServerPlayer)) { source.sendFailure(net.minecraft.network.chat.Component.literal("Field Chart requires a player.")); return null; }
        FieldChartCoordinator chart = supplier.get();
        if (chart == null) source.sendFailure(net.minecraft.network.chat.Component.literal("The Field Chart is not armed (no world loaded)."));
        return chart;
    }
    private FieldChartCommand() {}
}
