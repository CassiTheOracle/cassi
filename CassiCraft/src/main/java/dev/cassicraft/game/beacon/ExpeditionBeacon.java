package dev.cassicraft.game.beacon;

import dev.cassicraft.game.expedition.ExpeditionCoordinator;
import java.util.Objects;
import java.util.UUID;

/**
 * Pure, coordinate-free plan for the temporary expedition beacon. The planner
 * consumes only a deliberately coarse coordinator view and has no world, field,
 * Q4, inventory, or persistence dependency.
 */
public final class ExpeditionBeacon {
    public static final int CADENCE_TICKS = 10;
    public static final int MAX_PARTICLES = 4;

    public enum Bearing { NORTH, EAST, SOUTH, WEST }
    public enum RangeBand { NEAR, MID, FAR }

    public record SafeView(UUID playerId, ExpeditionCoordinator.State state, Bearing bearing, RangeBand range) {
        public SafeView {
            Objects.requireNonNull(playerId, "playerId");
            Objects.requireNonNull(state, "state");
            Objects.requireNonNull(bearing, "bearing");
            Objects.requireNonNull(range, "range");
        }

        public boolean isActive() {
            return state == ExpeditionCoordinator.State.OUTBOUND || state == ExpeditionCoordinator.State.RETURNING;
        }
    }

    public record Plan(boolean active, Bearing bearing, RangeBand range, int particles) {
        public Plan {
            Objects.requireNonNull(bearing, "bearing");
            Objects.requireNonNull(range, "range");
            if (particles < 0 || particles > MAX_PARTICLES) {
                throw new IllegalArgumentException("particle budget");
            }
        }

        public static Plan inactive() {
            return new Plan(false, Bearing.NORTH, RangeBand.NEAR, 0);
        }
    }

    public static Plan plan(SafeView view, long serverTick) {
        Objects.requireNonNull(view, "view");
        if (!view.isActive() || Math.floorMod(serverTick, CADENCE_TICKS) != 0) {
            return Plan.inactive();
        }
        int particles = switch (view.range()) {
            case NEAR -> 2;
            case MID -> 3;
            case FAR -> MAX_PARTICLES;
        };
        return new Plan(true, view.bearing(), view.range(), particles);
    }

    private ExpeditionBeacon() {}
}
