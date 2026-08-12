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
& "C:/Users/Carina/AppData/Local/Microsoft/WinGet/Packages/GodotEngine.GodotEngine_Microsoft.Winget.Source_8wekyb3d8bbwe/Godot_v4.7-stable_win64_console.exe" --path . --write-movie myvideo.avi --fixed-fps 30 res://scenes/main_recorder.tscn -- --record-frames=1800 --record-fps=30
```

`record.ps1` parameters: `-Out` (default `recording.avi`), `-Fps` (30),
`-Duration` (seconds, 30), `-Grid`, `-Particles`, `-Gravity`, `-Init`,
`-Steps` (0 / -1 = leave the scene default), `-Scene`, `-Exe`.

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
- The camera orbits the origin at a fixed elevation; no UI nodes are in
  the video.

## Converting to MP4

```powershell
ffmpeg -i recording.avi -c:v libx264 -crf 18 -pix_fmt yuv420p recording.mp4
```

(only if ffmpeg is installed).

## Settings: recorder scene vs command line

The scene `scenes/main_recorder.tscn` pins the high-res RealSim config:
`grid_N = 256`, `N_particles = 2 500 000`, `gravity_mode = 4` (RealSim,
with its 0.5/0.3/0.01 defaults), Gaussian IC (`initial_condition = 1`),
`cluster_radius = 50`, `cluster_separation = 0` (the cluster sits at the
origin, so the Gaussian ball keeps its full radius), `particle_size = 0.3`
(cloud-like; the interactive 3.0 is oversized billboards),
`recording_mode = true` (suppresses the CPU readbacks that stall the GPU),
`max_steps_per_frame = 60`.

Command line overrides (`--grid=… --particles=… --gravity=… --init=…`)
are applied to the scene's CassiSim and reinitialized before recording;
`--steps=…` changes the per-frame catch-up cap; `--orbit-speed/--orbit-radius`
tune the camera; `-Resolution` on the launcher sets the AVI size (default
1920x1080). `--record-frames` / `--record-fps` come from the launcher
(`-Duration` × `-Fps`); bare runs without them fall back to the scene
defaults (900 frames @ 30 fps, 1920x1080 window).
