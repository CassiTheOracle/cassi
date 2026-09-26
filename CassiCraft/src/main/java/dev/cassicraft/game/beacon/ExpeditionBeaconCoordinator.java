package dev.cassicraft.game.beacon;

import dev.cassicraft.game.expedition.ExpeditionCoordinator;
import net.minecraft.server.MinecraftServer;
import net.minecraft.server.level.ServerLevel;
import net.minecraft.server.level.ServerPlayer;
import java.util.Optional;

/** Per-tick adapter: requests only a coarse safe expedition view and renders it locally. */
public final class ExpeditionBeaconCoordinator {
    private ExpeditionCoordinator expeditions;

    public ExpeditionBeaconCoordinator(ExpeditionCoordinator expeditions) {
        this.expeditions = expeditions;
    }

    public void onServerTick(MinecraftServer server) {
        ExpeditionCoordinator coordinator = expeditions;
        ServerLevel level = server.overworld();
        if (coordinator == null || level == null || Math.floorMod(server.getTickCount(), ExpeditionBeacon.CADENCE_TICKS) != 0) {
            return;
        }
        for (ServerPlayer player : level.players()) {
            Optional<ExpeditionBeacon.SafeView> view = coordinator.beaconView(player);
            if (view.isEmpty()) {
                continue;
            }
            ExpeditionBeacon.Plan plan = ExpeditionBeacon.plan(view.get(), server.getTickCount());
            ExpeditionBeaconPresenter.present(level, player, plan);
        }
    }

    public void teardown() {
        expeditions = null;
    }
}
