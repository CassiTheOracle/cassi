package dev.cassicraft.game.expedition;

import dev.cassicraft.domain.snapshot.FieldSnapshot;
import dev.cassicraft.game.material.MaterialRegimeRead;
import dev.cassicraft.game.sampler.Quantizer;

import java.util.ArrayList;
import java.util.Comparator;
import java.util.List;

/** Pure deterministic planner for one field expedition. */
public final class ExpeditionPlanner {
    public static final int MIN_DISTANCE = 24;
    public static final int MAX_DISTANCE = 80;
    public static final int ARRIVAL_RADIUS = 3;
    public static final int RETURN_RADIUS = 3;
    public static final int SEARCH_STEP = 4;

    public record Origin(int x, int y, int z) {}
    public record Candidate(int x, int y, int z, String material) {
        public long horizontalDistanceSquared(Origin o) {
            long dx = (long) x - o.x();
            long dz = (long) z - o.z();
            return dx * dx + dz * dz;
        }
    }
    public record Contract(Origin origin, Candidate destination, long seed, int generation) {
        public boolean arrivedAt(int x, int y, int z) {
            long dx = (long)x - destination.x();
            long dz = (long)z - destination.z();
            return dx * dx + dz * dz <= (long) ARRIVAL_RADIUS * ARRIVAL_RADIUS
                    && Math.abs(y - destination.y()) <= 1;
        }
        public boolean returnedTo(int x, int y, int z) {
            long dx = (long)x - origin.x();
            long dz = (long)z - origin.z();
            return dx * dx + dz * dz <= (long) RETURN_RADIUS * RETURN_RADIUS
                    && Math.abs(y - origin.y()) <= 1;
        }
    }

    public static Contract plan(FieldSnapshot snap, double[] window, Origin origin, long seed) {
        if (snap == null || window == null || window.length < 3 || !standable(snap, window, origin.x(), origin.y(), origin.z())) return null;
        List<Candidate> candidates = candidates(snap, window, origin, seed);
        if (candidates.isEmpty()) return null;
        Candidate selected = candidates.stream().min(order(seed, snap.generation())).orElse(null);
        return selected == null ? null : new Contract(origin, selected, seed, snap.generation());
    }

    public static List<Candidate> candidates(FieldSnapshot snap, double[] window, Origin origin, long seed) {
        int minX = (int)Math.ceil(window[0] - 96), maxX = (int)Math.floor(window[0] + 96);
        int minZ = (int)Math.ceil(window[2] - 96), maxZ = (int)Math.floor(window[2] + 96);
        int minY = (int)Math.ceil(window[1] - 96), maxY = (int)Math.floor(window[1] + 96);
        List<Candidate> out = new ArrayList<>();
        for (int z = minZ; z <= maxZ; z += SEARCH_STEP) for (int x = minX; x <= maxX; x += SEARCH_STEP) {
            long d2 = (long)(x-origin.x())*(x-origin.x()) + (long)(z-origin.z())*(z-origin.z());
            if (d2 < (long)MIN_DISTANCE*MIN_DISTANCE || d2 > (long)MAX_DISTANCE*MAX_DISTANCE) continue;
            for (int y = maxY - 2; y >= minY + 2; y--) {
                if (standable(snap, window, x, y, z)) {
                    MaterialRegimeRead.RegimeRead r = MaterialRegimeRead.classify(Quantizer.sampleReading(snap, window, x, y, z));
                    out.add(new Candidate(x,y,z,r.material().name())); break;
                }
            }
        }
        return List.copyOf(out);
    }

    public static boolean standable(FieldSnapshot snap, double[] window, int x, int y, int z) {
        Quantizer.FieldReading here = Quantizer.sampleReading(snap, window, x, y, z);
        Quantizer.FieldReading below = Quantizer.sampleReading(snap, window, x, y - 1, z);
        Quantizer.FieldReading above = Quantizer.sampleReading(snap, window, x, y + 1, z);
        Quantizer.FieldReading head = Quantizer.sampleReading(snap, window, x, y + 2, z);
        return MaterialRegimeRead.classify(here).isSolid()
                && Quantizer.sampleAt(snap, window, x, y - 1, z).rho() >= Quantizer.TAU_C
                && Quantizer.sampleAt(snap, window, x, y + 1, z).rho() < Quantizer.TAU_C
                && Quantizer.sampleAt(snap, window, x, y + 2, z).rho() < Quantizer.TAU_C
                && below.rho() >= Quantizer.TAU_C && above.rho() < Quantizer.TAU_C && head.rho() < Quantizer.TAU_C;
    }

    private static Comparator<Candidate> order(long seed, int generation) {
        return Comparator.<Candidate>comparingLong(c -> mix(seed ^ ((long)generation << 32) ^ (((long)c.x()) * 0x9E3779B97F4A7C15L) ^ (((long)c.y()) * 0xC2B2AE3D27D4EB4FL) ^ c.z()))
                .thenComparingInt(Candidate::x).thenComparingInt(Candidate::y).thenComparingInt(Candidate::z);
    }
    public static long mix(long z) { z = (z ^ (z >>> 30)) * 0xBF58476D1CE4E5B9L; z = (z ^ (z >>> 27)) * 0x94D049BB133111EBL; return z ^ (z >>> 31); }
    private ExpeditionPlanner() {}
}
