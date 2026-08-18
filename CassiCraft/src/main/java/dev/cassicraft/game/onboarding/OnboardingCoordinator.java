package dev.cassicraft.game.onboarding;

import java.util.HashSet;
import java.util.Set;
import java.util.UUID;

/** Session-scoped, presentation-only onboarding state for the Weatherglass. */
public final class OnboardingCoordinator {
    public static final String PERSISTENCE_TIER = "SESSION_ONLY";
    public static final String DISCOVERY_TEXT =
            "Craft a Weatherglass. Plain use reads the local field; sneak-use begins a Field Expedition.";
    public static final String COMPLETION_RECEIPT =
            "Field Expedition complete. You received a session-only knowledge receipt; no item, energy, or matter was minted. "
                    + "Plain use reads the field; sneak-use starts another expedition when available.";

    private final Set<UUID> completionReceipts = new HashSet<>();

    public String discoveryText() {
        return DISCOVERY_TEXT;
    }

    public Action classifyUse(boolean crouching) {
        return crouching ? Action.EXPEDITION_START : Action.FIELD_READ;
    }

    /** Returns the receipt exactly once per player per live session. */
    public String observeCompletion(UUID playerId) {
        return completionReceipts.add(playerId) ? COMPLETION_RECEIPT : null;
    }

    public boolean hasCompletionReceipt(UUID playerId) {
        return completionReceipts.contains(playerId);
    }

    /** Called by the host lifecycle seam at session/world teardown. */
    public void clearSession() {
        completionReceipts.clear();
    }

    public enum Action {
        FIELD_READ,
        EXPEDITION_START
    }
}
