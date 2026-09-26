package dev.cassicraft.game.route;

import dev.cassicraft.domain.snapshot.FieldSnapshot;
import dev.cassicraft.domain.snapshot.SnapshotPublisher;
import dev.cassicraft.game.wind.WindRead;
import net.minecraft.core.BlockPos;
import net.minecraft.core.particles.ParticleTypes;
import net.minecraft.server.MinecraftServer;
import net.minecraft.server.level.ServerLevel;
import net.minecraft.server.level.ServerPlayer;

/** Bounded vanilla route cue; reads only the published local wind signal. */
public final class CoherenceRoutePresenter {
    private final SnapshotPublisher publisher;

    public CoherenceRoutePresenter(SnapshotPublisher publisher) {
        this.publisher = publisher;
    }

    public void onServerTick(MinecraftServer server) {
        FieldSnapshot snapshot = publisher.freshest();
        ServerLevel level = server.overworld();
        if (snapshot == null || snapshot.job() == null || snapshot.job().isWindowless() || level == null
                || Math.floorMod(server.getTickCount(), CoherenceRoute.CADENCE_TICKS) != 0) return;
        double[] center = snapshot.job().windowCenter();
        for (ServerPlayer player : level.players()) {
            BlockPos position = player.blockPosition();
            WindRead.WindReading wind = WindRead.read(snapshot, center, position.getX(), position.getY(), position.getZ());
            CoherenceRoute.Plan plan = CoherenceRoute.plan(new CoherenceRoute.Input(player.getUUID(), wind.isCalm(), bearing(wind), grade(wind)), server.getTickCount());
            if (plan.active()) present(level, player, plan);
        }
    }

    private static CoherenceRoute.Bearing bearing(WindRead.WindReading wind) {
        return Math.abs(wind.gradX()) >= Math.abs(wind.gradZ())
                ? (wind.gradX() >= 0 ? CoherenceRoute.Bearing.EAST : CoherenceRoute.Bearing.WEST)
                : (wind.gradZ() >= 0 ? CoherenceRoute.Bearing.SOUTH : CoherenceRoute.Bearing.NORTH);
    }

    private static CoherenceRoute.Grade grade(WindRead.WindReading wind) {
        double magnitude = Math.hypot(wind.gradX(), wind.gradZ());
        return magnitude >= 0.10 ? CoherenceRoute.Grade.STRONG : magnitude >= 0.04 ? CoherenceRoute.Grade.STEADY : CoherenceRoute.Grade.GENTLE;
    }

    private static void present(ServerLevel level, ServerPlayer player, CoherenceRoute.Plan plan) {
        double dx = switch (plan.bearing()) { case EAST -> 1.0; case WEST -> -1.0; default -> 0.0; };
        double dz = switch (plan.bearing()) { case SOUTH -> 1.0; case NORTH -> -1.0; default -> 0.0; };
        level.sendParticles(ParticleTypes.HAPPY_VILLAGER, player.getX() + dx * 1.35, player.getY() + 0.7, player.getZ() + dz * 1.35,
                plan.particles(), 0.16, 0.12, 0.16, 0.0);
    }
}
