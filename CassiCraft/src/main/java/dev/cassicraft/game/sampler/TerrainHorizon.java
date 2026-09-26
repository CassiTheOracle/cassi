package dev.cassicraft.game.sampler;

import net.minecraft.core.BlockPos;

import java.util.HashMap;
import java.util.Map;
import java.util.Set;
import java.util.UUID;

/** Session-local horizon for the single deterministic materialization owner. */
final class TerrainHorizon {
    private final Map<UUID, BlockPos> grounded = new HashMap<>();

    void observe(UUID playerId, BlockPos feet, boolean onGround) {
        if (playerId == null || feet == null) {
            throw new NullPointerException("playerId/feet");
        }
        if (onGround) {
            grounded.put(playerId, feet.below().immutable());
        }
    }

    BlockPos horizon(UUID playerId) {
        if (playerId == null) {
            throw new NullPointerException("playerId");
        }
        return grounded.get(playerId);
    }

    void retainActive(Set<UUID> active) {
        if (active == null) {
            throw new NullPointerException("active");
        }
        grounded.keySet().retainAll(active);
    }

    void clear() {
        grounded.clear();
    }
}
