package dev.cassicraft.game.sampler;

import dev.cassicraft.domain.snapshot.FieldSnapshot;
import dev.cassicraft.game.sampler.Quantizer.BlockKind;
import dev.cassicraft.game.writer.BlockMutation;
import net.minecraft.core.BlockPos;

import java.util.HashMap;
import java.util.List;
import java.util.Map;
import java.util.UUID;

/** Single-owner, session-local materialization seam used by TickSampler and its gate. */
final class MaterializationSession {
    private final Map<BlockPos, BlockKind> prior = new HashMap<>();
    private final TerrainHorizon horizon = new TerrainHorizon();
    private UUID activeOwner;

    List<BlockMutation> derive(FieldSnapshot snapshot, double[] center, UUID owner,
            BlockPos feet, boolean onGround) {
        if (snapshot == null || center == null || owner == null || feet == null) {
            throw new NullPointerException("snapshot/center/owner/feet");
        }
        if (!owner.equals(activeOwner)) {
            activeOwner = owner;
            prior.clear();
            horizon.clear();
        }
        horizon.observe(owner, feet, onGround);
        return MutationDeriver.derive(snapshot, center, feet.getX(), feet.getY(), feet.getZ(),
                prior, horizon, owner);
    }

    UUID owner() {
        return activeOwner;
    }

    int priorCount() {
        return prior.size();
    }

    boolean tracks(BlockPos pos) {
        return pos != null && prior.containsKey(pos);
    }

    void clear() {
        activeOwner = null;
        prior.clear();
        horizon.clear();
    }
}
