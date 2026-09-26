package dev.cassicraft.game.route;

import java.util.Objects;
import java.util.UUID;

/** Pure, coordinate-free local cue for the current published coherence route. */
public final class CoherenceRoute {
    public static final int CADENCE_TICKS = 10;
    public static final int MAX_PARTICLES = 4;

    public enum Bearing { NORTH, EAST, SOUTH, WEST }
    public enum Grade { GENTLE, STEADY, STRONG }

    public record Input(UUID playerId, boolean calm, Bearing bearing, Grade grade) {
        public Input {
            Objects.requireNonNull(playerId, "playerId");
            Objects.requireNonNull(bearing, "bearing");
            Objects.requireNonNull(grade, "grade");
        }
    }

    public record Plan(boolean active, Bearing bearing, Grade grade, int particles) {
        public Plan {
            Objects.requireNonNull(bearing, "bearing");
            Objects.requireNonNull(grade, "grade");
            if (particles < 0 || particles > MAX_PARTICLES) throw new IllegalArgumentException("particle budget");
        }
        public static Plan inactive() { return new Plan(false, Bearing.NORTH, Grade.GENTLE, 0); }
    }

    public static Plan plan(Input input, long serverTick) {
        Objects.requireNonNull(input, "input");
        if (input.calm() || Math.floorMod(serverTick, CADENCE_TICKS) != 0) return Plan.inactive();
        int particles = switch (input.grade()) {
            case GENTLE -> 2;
            case STEADY -> 3;
            case STRONG -> MAX_PARTICLES;
        };
        return new Plan(true, input.bearing(), input.grade(), particles);
    }

    private CoherenceRoute() {}
}
