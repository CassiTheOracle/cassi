package dev.cassicraft.game.storm;

import dev.cassicraft.game.sky.SkyRead;
import java.util.HashSet;
import java.util.Objects;
import java.util.Set;
import java.util.UUID;

/**
 * Pure, session-local transition latch for the existing storm-edge instrument
 * class. It owns no field, world, Q4, resource, movement, or persistence state.
 */
public final class StormWarning {
    private final Set<UUID> warned = new HashSet<>();

    /** Returns true only on this player's transition into the existing storm-edge class. */
    public boolean shouldWarn(UUID playerId, SkyRead.Kind kind) {
        Objects.requireNonNull(playerId, "playerId");
        Objects.requireNonNull(kind, "kind");
        if (kind != SkyRead.Kind.STORM_EDGE) {
            warned.remove(playerId);
            return false;
        }
        return warned.add(playerId);
    }

    public void clearSession() {
        warned.clear();
    }
}
