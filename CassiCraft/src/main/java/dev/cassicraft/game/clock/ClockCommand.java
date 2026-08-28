package dev.cassicraft.game.clock;

import com.mojang.brigadier.CommandDispatcher;
import net.minecraft.commands.CommandSourceStack;
import net.minecraft.commands.Commands;
import net.minecraft.core.BlockPos;
import net.minecraft.network.chat.Component;
import net.minecraft.server.level.ServerLevel;
import net.minecraft.server.level.ServerPlayer;

/** Read-only /cassicraft tempo companion to the Clock item. */
public final class ClockCommand {
    public static void register(CommandDispatcher<CommandSourceStack> dispatcher) {
        dispatcher.register(Commands.literal("cassicraft")
                .then(Commands.literal("tempo")
                        .executes(ctx -> run(ctx.getSource(), null))
                        .then(Commands.argument("x", com.mojang.brigadier.arguments.IntegerArgumentType.integer())
                                .then(Commands.argument("y", com.mojang.brigadier.arguments.IntegerArgumentType.integer())
                                        .then(Commands.argument("z", com.mojang.brigadier.arguments.IntegerArgumentType.integer())
                                                .executes(ctx -> run(ctx.getSource(), new int[] {
                                                        com.mojang.brigadier.arguments.IntegerArgumentType.getInteger(ctx, "x"),
                                                        com.mojang.brigadier.arguments.IntegerArgumentType.getInteger(ctx, "y"),
                                                        com.mojang.brigadier.arguments.IntegerArgumentType.getInteger(ctx, "z")
                                                })))))));
    }

    public static int run(CommandSourceStack source, int[] xyz) {
        ClockItem clock = dev.cassicraft.CassiCraft.CLOCK;
        if (clock == null) {
            source.sendFailure(Component.literal("The Clock is not armed (no world loaded)."));
            return 0;
        }
        BlockPos pos = xyz == null ? fallbackPos(source) : new BlockPos(xyz[0], xyz[1], xyz[2]);
        ClockRead.Tempo tempo = clock.readAt(pos.getX(), pos.getY(), pos.getZ());
        if (tempo == null) {
            source.sendFailure(Component.literal("The field is not yet publishing."));
            return 0;
        }
        source.sendSuccess(() -> Component.literal("Clock @ (" + pos.getX() + "," + pos.getY() + "," + pos.getZ() + ")\n" + tempo.text()), false);
        return 1;
    }

    private static BlockPos fallbackPos(CommandSourceStack source) {
        ServerPlayer player = source.getPlayer();
        if (player != null) return player.blockPosition();
        ServerLevel overworld = source.getServer().overworld();
        return overworld != null && overworld.getRespawnData() != null && overworld.getRespawnData().pos() != null
                ? overworld.getRespawnData().pos() : BlockPos.ZERO;
    }

    private ClockCommand() {}
}
