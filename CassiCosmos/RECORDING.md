# Recording Mode — background batch jobs (Godot 4 Movie Maker)

Run RealSim (or any config) at high resolution as a background batch job:
the console exe runs the engine as fast as possible at a fixed movie fps,
Movie Maker captures the root viewport each rendered frame into an AVI
(MJPEG), and the recorder scene quits itself when the frame count is
reached. Leave it running and walk away.

## Launch

From `godot/space-sim`:

```powershell
powershell -File record.ps1 -Out myvideo.avi -Duration 60
```

Raw one-liner (same thing, no wrapper):

```powershell
& "C:/Users/Carina/AppData/Local/Microsoft/WinGet/Packages/GodotEngine.GodotEngine.Mono_Microsoft.Winget.Source_8wekyb3d8bbwe/Godot_v4.7.1-stable_mono_win64/Godot_v4.7.1-stable_mono_win64_console.exe" --path . --write-movie myvideo.avi --fixed-fps 30 res://scenes/main_recorder.tscn -- --record-frames=1800 --record-fps=30
```

`record.ps1` parameters: `-Out` (default `recording.avi`), `-Fps` (30),
`-Duration` (seconds, 30), `-Grid`, `-Particles`, `-Gravity`, `-Init`,
`-Steps` (0 / -1 = leave the scene default), `-Aspect` (`x,y,z` — the
per-axis box aspect, e.g. `1.618,1,2.618` for the theory φ-aspect box;
empty = inherit from main.tscn), `-Scene`, `-Exe`.

```powershell
# φ-aspect box recording (the theory's incommensurate bubble-lattice
# periods — GRID_LAYOUT.md; removes the cubic box-mode straight-line lock)
powershell -File record.ps1 -Out phi_box.avi -Duration 60 -Aspect 1.618,1,2.618
```

## FPS and resolution (how it actually works)

Movie Maker fixes the game loop at the movie fps, and both the fps and the
AVI resolution are locked in at engine start, before any scene code runs:

- **FPS** — `--fixed-fps N` is the mechanism (verified against the shipped
  `main.cpp`: the value goes straight into `MovieWriter::begin()`; the AVI
  stream header matches the requested rate, e.g. 30/40/60). A runtime
  `ProjectSettings.set_setting("movie_writer/fps", ...)` has no effect on
  the recording. Without `--fixed-fps`, Godot 4.7's Movie Maker defaults
  to 60 fps.
- **Resolution** — the movie size is read from the project settings
  `display/window/size/viewport_width/height` at engine start. The window
  size (`--resolution`, a runtime `get_window().size = ...`) does NOT
  change the movie size, and the `window_width_override` pair comes out
  DPI-scaled on Windows. So `record.ps1` temporarily patches those two
  viewport settings in `project.godot` for the run and restores the file
  afterwards (a `.recbak` from a crashed run is cleaned up on the next
  launch).

## Time-lapse math

Per video frame the sim advances `min(max_steps_per_frame, dt_accum)`
physics steps at `dt = 0.001` s:

| fps | steps | sim time per video second |
|-----|-------|---------------------------|
| 30  | 16 (default) | 0.48 s (≈2× slow-motion) |
| 30  | 60 (recorder scene default) | 1.0 s (real-time) |
| 30  | 300 | 5 s (time-lapse) |

Raise `-Steps` for longer time-lapse coverage per video second.

## Batch job notes

- Movie Maker runs as fast as the GPU allows: one Godot at a time on this
  machine, and the window must stay open — it can be behind other windows,
  but do not minimize it (Windows throttles rendering of minimized
  windows).
- `record.ps1` temporarily edits `project.godot` (viewport size) and
  restores it after the run. If the Godot editor is open, it may pop a
  "project settings changed externally" prompt — close the editor before
  recording, or dismiss the prompt.
- Progress goes to stdout: `[Recorder] frame N/M (sim t=…)` every 30
  frames, then `[Recorder] done`. Exit code 0 means the AVI finalized.
- The camera orbits the SPAWN REGION at a fixed elevation: the orbit center
  is the cluster-centroid (mean of the cluster centers, mirroring
  cassi_sim.gd's ring/Fibonacci placement — NOT the origin, so a
  single-cluster config is framed dead-center) and the default orbit radius
  is derived from the spawn extent (cluster-ring radius + cluster radius),
  so the startup frame shows the particles up close and centered.
  `--orbit-radius` overrides the auto-framed distance; no UI nodes are in
  the video.

## Converting to MP4

```powershell
ffmpeg -i recording.avi -c:v libx264 -crf 18 -pix_fmt yuv420p recording.mp4
```

(only if ffmpeg is installed).

## Settings: main.tscn vs command line

The recorder no longer has its own settings copy. At launch it mirrors
whatever is currently set on `scenes/main.tscn`'s CassiSim node — editor
edits are written to the file, and the recorder reads the file (loading
the scene without adding it to the tree, then copying the settings and
reinitializing). If `main.tscn` is unreadable it falls back to the
script's export defaults. The only recorder-specific flags are
`suppress_readbacks = true` (suppresses the CPU readbacks that stall the
GPU) and `max_steps_per_frame = 60`. The recorder inherits the BH toggle
(`black_holes_enabled`) from main.tscn like every other sim setting.

Command line overrides (`--grid=… --particles=… --gravity=… --init=…
--aspect=x,y,z --v-circ=…`) are applied on top of the inherited settings
and reinitialized before recording; `--v-circ=…` sets the IC rotational
support factor (v_tangential = factor·√(G·M_enc/r) about z; default
0.85); `--bhs=0/1` sets the BH toggle live (no reinit);
`--freeze-field=0/1` freezes the two-fluid field after init (skips the
PDE passes; gravity/particle path unchanged; no reinit — read per step);
`--steps=…` changes the per-frame catch-up cap;
`--orbit-speed/--orbit-radius` tune the camera (radius pins the
auto-framed distance); `-Resolution` on the
launcher sets the AVI size (default 1920x1080). `--record-frames` /
`--record-fps` come from the launcher (`-Duration` × `-Fps`); bare runs
without them fall back to the scene defaults (900 frames @ 30 fps,
1920x1080 window).
