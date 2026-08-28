# LOADING

How to load the CassiCraft mod into Minecraft. Version 0.1.0 — a Fabric mod for Minecraft 26.2 (Loader 0.19.3, Loom 1.17.19, Java 25). The demo runs a two-fluid field on a 64³ grid inside a 192³ m box centered at the world origin; a tick-sampler quantizes the player's vicinity into ordinary Minecraft blocks.

Nothing here edits source. All three paths run from the repo root (`CassiCraft/`).

## Path A — dev client (fastest)

From the repo root:

```
JAVA_HOME="C:/Program Files/Zulu/zulu-25" ./gradlew runClient
```

Loom launches a Minecraft client with the mod and Fabric API auto-loaded under a fake offline "Dev" session. The first run downloads client assets and may take several minutes. If a login prompt appears, use Path B instead.

## Path B — production install

1. Build the jar (from the repo root):

   ```
   JAVA_HOME="C:/Program Files/Zulu/zulu-25" ./gradlew build
   ```

2. Install the Fabric Loader for MC 26.2 with the Fabric Installer from fabricmc.net (Loader 0.19.3+; create a new 26.2 installation).
3. Place **both** of these into that installation's `mods/` folder:
   - `build/libs/cassicraft-0.1.0.jar`
   - the Fabric API jar `fabric-api-0.157.0+26.2.jar` — a declared dependency; the mod requires it.
4. Launch and create a single-player world.

## Path C — dedicated server

From the repo root:

```
JAVA_HOME="C:/Program Files/Zulu/zulu-25" ./gradlew runServer
```

Already verified; the eula is accepted and a `cassicraft-demo` world already exists in `run/`.

## Honest expectations

The field box is fixed at the world origin for this demo. A fresh world's spawn is likely far outside the box, so the terrain you see is the field's boundary slab — the quantizer clamps to the box edge. It is still the field's own structure. A player-anchored box that follows you is the next milestone on the map.

The demo renders ordinary Minecraft blocks — there is no custom rendering. Block mapping and thresholds:

- ρ ≥ 0.5 → STONE
- q ≥ 1.35 → COPPER_ORE
- ε² ≥ 1.0 → carved AIR

Thresholds carry hysteresis, so a jittering field does not flicker blocks.
