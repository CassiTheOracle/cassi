package dev.cassicraft.game.beacon;

import net.minecraft.core.particles.ParticleTypes;
import net.minecraft.server.level.ServerLevel;
import net.minecraft.server.level.ServerPlayer;

/** Vanilla-only local rendering for a precomputed safe beacon plan. */
public final class ExpeditionBeaconPresenter {
    public static void present(ServerLevel level, ServerPlayer player, ExpeditionBeacon.Plan plan) {
        if (!plan.active()) {
            return;
        }
        double dx = switch (plan.bearing()) {
            case EAST -> 1.0;
            case WEST -> -1.0;
            default -> 0.0;
        };
        double dz = switch (plan.bearing()) {
            case SOUTH -> 1.0;
            case NORTH -> -1.0;
            default -> 0.0;
        };
        double x = player.getX() + dx * 1.25;
        double y = player.getY() + 1.1;
        double z = player.getZ() + dz * 1.25;
        level.sendParticles(ParticleTypes.END_ROD, x, y, z, plan.particles(), 0.16, 0.18, 0.16, 0.0);
    }

    private ExpeditionBeaconPresenter() {}
}
