package dev.cassicraft.game.expedition;

import net.minecraft.core.BlockPos;
import net.minecraft.core.particles.ParticleTypes;
import net.minecraft.server.level.ServerLevel;

/** Vanilla-only destination marker presentation; never mutates blocks or field. */
public final class ExpeditionPresenter {
    public static void present(ServerLevel level, BlockPos pos) {
        level.sendParticles(ParticleTypes.END_ROD, pos.getX()+0.5, pos.getY()+1.2, pos.getZ()+0.5, 4, 0.4, 0.4, 0.4, 0.0);
    }
    private ExpeditionPresenter() {}
}
