package dev.cassicraft.game.progression;

import java.util.Collection;
import java.util.LinkedHashSet;
import java.util.Objects;
import java.util.Set;
import java.util.UUID;

/** Pure, versioned receipt set: completed expedition knowledge only. */
public final class ExpeditionKnowledge {
    public static final int VERSION = 1;
    private final Set<UUID> completed = new LinkedHashSet<>();

    public boolean record(UUID playerId) {
        return completed.add(Objects.requireNonNull(playerId, "playerId"));
    }

    public boolean contains(UUID playerId) {
        return completed.contains(Objects.requireNonNull(playerId, "playerId"));
    }

    public Set<String> serializedIds() {
        return completed.stream().map(UUID::toString).sorted().collect(java.util.stream.Collectors.toUnmodifiableSet());
    }

    public static ExpeditionKnowledge fromSerialized(Collection<String> identifiers) {
        ExpeditionKnowledge knowledge = new ExpeditionKnowledge();
        for (String identifier : identifiers) {
            try {
                knowledge.record(UUID.fromString(identifier));
            } catch (IllegalArgumentException ignored) {
                // A malformed legacy entry is not a receipt and must not become one.
            }
        }
        return knowledge;
    }
}
