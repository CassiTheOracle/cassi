package dev.cassicraft.game.storm;

import dev.cassicraft.domain.snapshot.FieldSnapshot;
import dev.cassicraft.domain.snapshot.SnapshotPublisher;
import dev.cassicraft.game.sampler.Quantizer;
import dev.cassicraft.game.sky.SkyRead;
import net.minecraft.network.chat.Component;
import net.minecraft.server.MinecraftServer;
import net.minecraft.server.level.ServerPlayer;

/** Read-only one-time instrument warning; SkyPresenter remains the visual cue. */
public final class StormWarningPresenter {
    private final SnapshotPublisher publisher;
    private final StormWarning warning = new StormWarning();

    public StormWarningPresenter(SnapshotPublisher publisher) {
        this.publisher = publisher;
    }

    public void onServerTick(MinecraftServer server) {
        FieldSnapshot snapshot = publisher.freshest();
        if (snapshot == null || snapshot.job() == null || snapshot.job().isWindowless()) {
            return;
        }
        double[] center = snapshot.job().windowCenter();
        for (ServerPlayer player : server.getPlayerList().getPlayers()) {
            var pos = player.blockPosition();
            SkyRead.Kind kind = SkyRead.classify(Quantizer.sampleReading(snapshot, center, pos.getX(), pos.getY(), pos.getZ())).kind();
            if (warning.shouldWarn(player.getUUID(), kind)) {
                player.sendSystemMessage(Component.literal("Weatherglass warning: storm edge detected. Follow the field read."));
            }
        }
    }

    public void teardown() {
        warning.clearSession();
    }
}
