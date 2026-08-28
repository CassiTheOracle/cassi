package dev.cassicraft.game.sampler;

import dev.cassicraft.domain.snapshot.FieldSnapshot;
import dev.cassicraft.domain.snapshot.SnapshotPublisher;
import dev.cassicraft.game.writer.BlockMutation;
import net.minecraft.core.BlockPos;
import net.minecraft.server.MinecraftServer;
import net.minecraft.server.level.ServerLevel;
import net.minecraft.server.level.ServerPlayer;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

import java.util.List;
import java.util.UUID;

/** Server-thread sampler; the world writer remains the only block mutator. */
public class TickSampler {
    private static final Logger LOGGER = LoggerFactory.getLogger(TickSampler.class);
    private static final int QUANTIZE_EVERY_TICKS = 5;
    private final SnapshotPublisher publisher;
    private final MaterializationSession materialization = new MaterializationSession();
    private long lastQuantTick = -1;
    private int lastConsumedGen = -1;
    private boolean announcedConsumption;

    public TickSampler(SnapshotPublisher publisher) {
        this.publisher = publisher;
    }

    public SnapshotPublisher publisher() {
        return publisher;
    }

    public void onServerTick(MinecraftServer server, java.util.Queue<BlockMutation> writerIntent) {
        ServerLevel level = server.overworld();
        ServerPlayer tracked = trackedPlayer(level, materialization.owner());
        if (materialization.owner() != null && tracked == null) {
            materialization.clear();
        }
        ServerPlayer player = tracked != null ? tracked : firstPlayer(level);
        if (player == null) {
            materialization.clear();
            return;
        }
        FieldSnapshot freshest = publisher.freshest();
        if (freshest == null) {
            return;
        }
        long tick = server.getTickCount();
        if (freshest.generation() <= lastConsumedGen || tick - lastQuantTick < QUANTIZE_EVERY_TICKS) {
            return;
        }
        lastQuantTick = tick;
        lastConsumedGen = freshest.generation();
        double[] windowCenter = freshest.job() != null && !freshest.job().isWindowless()
                ? freshest.job().windowCenter() : new double[] { 0, 0, 0 };
        UUID owner = player.getUUID();
        BlockPos feet = player.blockPosition();
        List<BlockMutation> emitted = materialization.derive(freshest, windowCenter, owner,
                feet, player.onGround());
        writerIntent.addAll(emitted);
        if (!announcedConsumption) {
            announcedConsumption = true;
            LOGGER.info("[cassicraft/sampler] consumed snapshot gen={} owner={} emitted {} block mutations",
                    freshest.generation(), owner, emitted.size());
        }
    }

    private static ServerPlayer trackedPlayer(ServerLevel level, UUID owner) {
        if (level == null || owner == null) {
            return null;
        }
        for (ServerPlayer player : level.players()) {
            if (player != null && owner.equals(player.getUUID())) {
                return player;
            }
        }
        return null;
    }

    private static ServerPlayer firstPlayer(ServerLevel level) {
        if (level == null) {
            return null;
        }
        for (ServerPlayer player : level.players()) {
            if (player != null) {
                return player;
            }
        }
        return null;
    }

    public void close() {
        materialization.clear();
    }
}
