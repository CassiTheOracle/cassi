#!/usr/bin/env python3
"""
Resonant Pond: A unified visual explainer for the Cassi φ-framework.

The universe as a plucked guitar string vibrating in a two-fluid medium.
Eight scenes, ~60 seconds, procedural Manim animation.

Render individual scenes:
    manim -pql resonant_pond.py StillPond
    manim -pql resonant_pond.py ThePluck
    manim -pql resonant_pond.py FirstRipples
    manim -pql resonant_pond.py ThePinch
    manim -pql resonant_pond.py CosmicWeb
    manim -pql resonant_pond.py SelfPlucking
    manim -pql resonant_pond.py TwoListeners
    manim -pql resonant_pond.py TheChord

Render full sequence:
    manim -pqh resonant_pond.py ResonantPond

Shared state between scenes:
    - RIPPLE_SOURCES: list of active wave sources along the string
    - STRING_MEAN_X: the string's mean position (r₀ → φ drift)
    - GLOBAL_TIME: elapsed time since pluck
"""

import numpy as np
from manim import *

# ═══════════════════════════════════════════════════════════════════════════════
# Constants
# ═══════════════════════════════════════════════════════════════════════════════
PHI = (1 + np.sqrt(5)) / 2         # ≈ 1.618
PHI_INV = 1 / PHI                  # ≈ 0.618
SQRT_PHI = np.sqrt(PHI)            # ≈ 1.272
PHI_INV3 = PHI_INV ** 3            # ≈ 0.236

# ═══════════════════════════════════════════════════════════════════════════════
# Color palette—indigo (Yin) → gold (Yang)
# ═══════════════════════════════════════════════════════════════════════════════
YIN_DEEP    = "#140a33"
YIN_MID     = "#2a1a5e"
YIN_LIGHT   = "#4a2a8e"
YANG_DARK   = "#5a3a10"
YANG_MID    = "#9a6a1a"
YANG_BRIGHT = "#daa520"
YANG_PEAK   = "#ffe060"
FLUID_BG    = "#060612"
FLUID_DARK  = "#0a0a1e"
PINCH_COLOR = "#a0a0c0"
PINCH_GLOW  = "#c0c0e0"
TEXT_MAIN   = "#e0e0f0"
TEXT_SUB    = "#a0a0c0"
RING_COLOR  = "#303050"

# Safe interpolator: converts hex strings to ManimColor before blending
def _lerp(c1, c2, t):
    return interpolate_color(ManimColor(c1), ManimColor(c2), t)

# ═══════════════════════════════════════════════════════════════════════════════
# Layout
# ═══════════════════════════════════════════════════════════════════════════════
POND_RADIUS   = 3.0
STRING_Y      = 0.0
STRING_LEFT   = np.array([-2.8, STRING_Y, 0])
STRING_RIGHT  = np.array([ 2.8, STRING_Y, 0])
STRING_LENGTH = STRING_RIGHT[0] - STRING_LEFT[0]
PINCH_X       = -0.6    # string x-position corresponding to r = φ⁻¹
PHI_X         =  2.2    # string x-position corresponding to r = φ
R0_X          = -2.5    # string x-position corresponding to r₀ ≈ 0.047
PLUCK_X       = -2.1    # where the string is plucked

# Map ratio r to string x-coordinate: r = r₀ at R0_X, r = φ at PHI_X
def ratio_to_x(r, r0=0.047, r_phi=PHI):
    """Map a ratio value to an x-coordinate along the string."""
    frac = (r - r0) / (r_phi - r0)
    return R0_X + frac * (PHI_X - R0_X)

# Inverse: x-coordinate to ratio
def x_to_ratio(x):
    frac = (x - R0_X) / (PHI_X - R0_X)
    return 0.047 + frac * (PHI - 0.047)

# ═══════════════════════════════════════════════════════════════════════════════
# Ripple source parameters (positions along string with frequencies and colors)
# ═══════════════════════════════════════════════════════════════════════════════
WAVE_SPEED = 1.2
RIPPLE_LIFETIME = 4.0

# Each source: (name, x_position, base_freq, phase_offset, color)
# Frequencies follow φ-scaling: higher harmonics on the Yang side
BASE_RIPPLE_SOURCES = [
    ("s0", -2.3, 0.8,  0.0,    YIN_DEEP),
    ("s1", -1.6, 1.0,  0.4,    YIN_MID),
    ("s2", -0.9, 1.3,  0.7,    _lerp(YIN_LIGHT, YANG_DARK, 0.4)),
    ("s3", -0.2, 1.6,  1.1,    _lerp(YIN_LIGHT, YANG_DARK, 0.7)),
    ("s4",  0.5, 2.0,  1.4,    YANG_MID),
    ("s5",  1.2, 2.5,  1.8,    YANG_BRIGHT),
    ("s6",  1.9, 3.2,  2.1,    YANG_PEAK),
]

# ═══════════════════════════════════════════════════════════════════════════════
# Shared state (module-level so separate Scene classes can import)
# ═══════════════════════════════════════════════════════════════════════════════
class PondState:
    """Mutable shared state passed between scenes."""
    def __init__(self):
        self.global_time = 0.0       # seconds since pluck
        self.string_mean_x = R0_X    # current mean x of the string
        self.string_amplitude = 0.0  # vibration amplitude
        self.pinch_visible = False
        self.pinch_crossed = False
        self.ripple_sources = list(BASE_RIPPLE_SOURCES)
        self.cascade_rings_visible = False
        self.nodes_visible = False

# Singleton
STATE = PondState()

# ═══════════════════════════════════════════════════════════════════════════════
# Helper: interpolate between two hex colors
# ═══════════════════════════════════════════════════════════════════════════════
def lerp_color(c1, c2, t):
    """Linearly interpolate between two hex colors."""
    return _lerp(c1, c2, t)

# ═══════════════════════════════════════════════════════════════════════════════
# Helper: create text annotation that fades in, lingers, fades out
# ═══════════════════════════════════════════════════════════════════════════════
def annotation(text, position=DOWN * 2.8, color=TEXT_MAIN, font_size=28):
    """Create a text annotation."""
    return Text(text, font_size=font_size, color=color, font="sans-serif")

def math_annotation(tex_string, position=DOWN * 2.8, color=TEXT_MAIN, font_size=32):
    """Create a math annotation using Unicode (no LaTeX dependency)."""
    return Text(tex_string, font_size=font_size, color=color, font="sans-serif").move_to(position)

# ═══════════════════════════════════════════════════════════════════════════════
# Base elements shared across scenes
# ═══════════════════════════════════════════════════════════════════════════════
def create_pond():
    """The dark circular pond—the 2D universe."""
    pond = Circle(
        radius=POND_RADIUS,
        stroke_color=RING_COLOR,
        stroke_width=1.5,
        fill_color=FLUID_DARK,
        fill_opacity=0.9,
    )
    # Subtle inner glow
    pond_inner = Circle(
        radius=POND_RADIUS - 0.05,
        stroke_color=_lerp(FLUID_DARK, FLUID_BG, 0.5),
        stroke_width=3.0,
        fill_opacity=0,
    )
    return VGroup(pond, pond_inner)


def create_string_baseline():
    """The dormant string—a thin horizontal line."""
    return Line(
        STRING_LEFT + np.array([0.2, 0, 0]),
        STRING_RIGHT - np.array([0.2, 0, 0]),
        stroke_color=_lerp(YIN_DEEP, YANG_MID, 0.4),
        stroke_width=1.0,
        stroke_opacity=0.5,
    )


def create_anchors():
    """The two fixed endpoints of the string."""
    left_anchor = Dot(
        point=STRING_LEFT,
        color=YIN_LIGHT,
        radius=0.08,
    )
    right_anchor = Dot(
        point=STRING_RIGHT,
        color=YANG_BRIGHT,
        radius=0.08,
    )
    left_label = Text("Yin", font_size=16, color=YIN_LIGHT).next_to(left_anchor, DOWN, buff=0.15)
    right_label = Text("Yang", font_size=16, color=YANG_BRIGHT).next_to(right_anchor, DOWN, buff=0.15)
    return VGroup(left_anchor, right_anchor, left_label, right_label)


def create_pinch_ring():
    """The φ⁻¹ transition ring—where self-modeling becomes possible."""
    pinch_x = PINCH_X
    ring = Circle(
        radius=POND_RADIUS * 0.35,
        stroke_color=PINCH_COLOR,
        stroke_width=1.0,
        stroke_opacity=0.0,
        fill_opacity=0,
    ).move_to(np.array([pinch_x + 0.4, STRING_Y, 0]))  # centered slightly right of pinch
    return ring


def create_cascade_rings():
    """Concentric rings at key φ-scaled positions."""
    rings = VGroup()
    labels = VGroup()

    cascade_info = [
        (0.25, "Electroweak\n$\\sim 10^{-19}$ m", 12),
        (0.55, "Atomic\n$\\sim 10^{-11}$ m", 12),
        (0.85, "Cellular\n$\\sim 10^{-5}$ m", 11),
        (1.15, "Human\n$\\sim 1.7$ m", 11),
        (1.50, "Solar System\n$\\sim 10^{12}$ m", 10),
        (1.85, "Milky Way\n$\\sim 10^{21}$ m", 11),
        (2.20, "BAO\n$\\sim 10^{24}$ m", 12),
        (2.78, "Wu Xing\nbubble", 10),
        (2.98, "Hubble\nradius", 11),
    ]

    for i, (radius, label_text, font_sz) in enumerate(cascade_info):
        alpha = 0.0  # start invisible
        ring = Circle(
            radius=radius,
            stroke_color=RING_COLOR,
            stroke_width=0.8,
            stroke_opacity=alpha,
            fill_opacity=0,
        )
        # Position label at a point on the ring (top-right quadrant)
        angle = PI / 4 + i * 0.05
        label_pos = np.array([
            radius * np.cos(angle),
            radius * np.sin(angle),
            0
        ])
        label = Text(label_text, font_size=font_sz, color=TEXT_SUB, line_spacing=0.5)
        label.move_to(label_pos)
        label.set_opacity(0)

        rings.add(ring)
        labels.add(label)

    return VGroup(rings, labels)


def create_string_vibration(tracker_time, tracker_amp, tracker_mean):
    """Create an always-redrawing vibrating string."""
    def get_string():
        t = tracker_time.get_value()
        amp = tracker_amp.get_value()
        mean_x = tracker_mean.get_value()

        # Damped vibration
        decay = 0.15
        freq = 3.0
        effective_amp = amp * np.exp(-decay * t) * np.clip(1 - t / 20, 0, 1)

        # Build points
        n = 200
        points = []
        for i in range(n):
            frac = i / (n - 1)
            x_base = STRING_LEFT[0] + frac * STRING_LENGTH

            # Mean position shift (subtle)
            shift = (mean_x - R0_X) * 0.15 * frac

            # Standing wave: fundamental + 2nd harmonic
            y_vib = effective_amp * (
                1.0 * np.sin(frac * np.pi) * np.sin(2 * np.pi * freq * t)
                + 0.3 * np.sin(frac * 2 * np.pi) * np.sin(4 * np.pi * freq * t + 0.5)
            )

            points.append([x_base + shift, y_vib, 0])

        # Color gradient along the string
        vm = VMobject()
        vm.set_points_as_corners(points)

        # Color each segment by its x position
        colors = []
        for i in range(len(points)):
            frac = i / (len(points) - 1)
            colors.append(_lerp(YIN_LIGHT, YANG_BRIGHT, frac))
        vm.set_color_by_gradient(*colors)
        vm.set_stroke(width=2.0)

        return vm

    return always_redraw(get_string)


def create_ripple_system(tracker_time):
    """Create an always-redrawing ripple field using expanding circles."""
    def get_ripples():
        t = tracker_time.get_value()
        group = VGroup()

        # Only show ripples after a minimum time (scene-dependent)
        if t < 0.3:
            return group

        for name, sx, freq, phase, color in STATE.ripple_sources:
            period = 1.0 / freq
            # Number of completed cycles
            n_cycles = int(t / period)

            # Show ripples from the last few cycles
            for n in range(max(0, n_cycles - 15), n_cycles + 2):
                emit_t = n * period + phase * period / (2 * np.pi)
                if emit_t > t:
                    continue
                age = t - emit_t
                if age > RIPPLE_LIFETIME:
                    continue

                radius = WAVE_SPEED * age
                if radius > POND_RADIUS * 1.4:
                    continue

                # Opacity fades with radius and age
                opacity = 0.35 * (1 - radius / (POND_RADIUS * 1.3))
                opacity *= (1 - age / RIPPLE_LIFETIME)
                opacity = max(0, min(0.7, opacity))

                # Width narrows with radius
                width = 1.5 * (1 - radius / (POND_RADIUS * 1.2))
                width = max(0.3, width)

                circle = Circle(
                    radius=radius,
                    stroke_color=color,
                    stroke_width=width,
                    stroke_opacity=opacity,
                    fill_opacity=0,
                ).move_to(np.array([sx, STRING_Y, 0]))

                group.add(circle)

        return group

    return always_redraw(get_ripples)


def create_nodes(tracker_time, num_nodes=20):
    """Create persistent bright dots at constructive interference points."""
    def get_nodes():
        t = tracker_time.get_value()
        group = VGroup()

        if not STATE.nodes_visible or t < 5:
            return group

        # Place nodes at pseudo-random but deterministically positioned locations
        # where ripples from multiple sources constructively interfere.
        # For procedural generation, use golden-angle spiral distribution
        golden_angle = np.pi * (3 - np.sqrt(5))

        for i in range(num_nodes):
            # Golden spiral distribution
            r = 0.3 + (i / num_nodes) * 2.5
            theta = i * golden_angle

            # Brightness varies with time to suggest dynamic interference
            brightness = 0.4 + 0.3 * np.sin(t * 0.5 + i * 1.7)
            brightness *= 0.6  # overall dim

            x = r * np.cos(theta)
            y = r * np.sin(theta)

            dot = Dot(
                point=np.array([x, y, 0]),
                color=_lerp(YANG_MID, YANG_PEAK, brightness),
                radius=0.02 + 0.02 * brightness,
            )
            dot.set_opacity(brightness)
            group.add(dot)

        return group

    return always_redraw(get_nodes)


# ═══════════════════════════════════════════════════════════════════════════════
# SCENE 1: Still Pond (0–3s)
# ═══════════════════════════════════════════════════════════════════════════════
class StillPond(Scene):
    def construct(self):
        self.camera.background_color = FLUID_BG

        pond = create_pond()
        string = create_string_baseline()
        anchors = create_anchors()

        self.play(
            FadeIn(pond, run_time=1.5),
            FadeIn(string, run_time=1.5),
            FadeIn(anchors, run_time=1.5),
        )

        title = Text("Before the pluck...", font_size=36, color=TEXT_MAIN)
        title.move_to(DOWN * 2.5)
        self.play(Write(title), run_time=1.0)

        self.wait(1.0)
        self.play(FadeOut(title), run_time=0.5)


# ═══════════════════════════════════════════════════════════════════════════════
# SCENE 2: The Pluck (3–8s)
# ═══════════════════════════════════════════════════════════════════════════════
class ThePluck(Scene):
    def construct(self):
        self.camera.background_color = FLUID_BG

        pond = create_pond()
        anchors = create_anchors()
        self.add(pond, anchors)

        # Build the string
        n = 200
        base_points = []
        for i in range(n):
            frac = i / (n - 1)
            x = STRING_LEFT[0] + frac * STRING_LENGTH
            base_points.append([x, STRING_Y, 0])

        string_base = VMobject()
        string_base.set_points_as_corners(base_points)
        string_base.set_color_by_gradient(YIN_LIGHT, YANG_BRIGHT)
        string_base.set_stroke(width=2.0)
        self.add(string_base)

        # Pluck: deform the string downward at PLUCK_X
        pluck_frac = (PLUCK_X - STRING_LEFT[0]) / STRING_LENGTH
        pluck_points = []
        pluck_amp = 0.8
        for i in range(n):
            frac = i / (n - 1)
            # Triangle deformation centered at pluck point
            dist = abs(frac - pluck_frac) / 0.15
            y = -pluck_amp * max(0, 1 - dist) ** 2
            pluck_points.append([base_points[i][0], y, 0])

        string_plucked = VMobject()
        string_plucked.set_points_as_corners(pluck_points)
        string_plucked.set_color_by_gradient(YIN_LIGHT, YANG_BRIGHT)
        string_plucked.set_stroke(width=2.0)

        # Animate the pluck
        gap_text = annotation(
            "The Wu Xing gap sets the initial pluck",
            DOWN * 2.5, TEXT_MAIN, 28
        )
        gap_math = math_annotation(
            "g = 1 \u2212 \u03C6\u207B\u2075 \u2248 0.910",
            DOWN * 2.5, TEXT_MAIN, 32
        )

        # Pull
        self.play(Transform(string_base, string_plucked, run_time=1.5))
        self.play(Write(gap_text), run_time=1.0)

        self.wait(0.5)
        self.play(
            FadeOut(gap_text),
            FadeIn(gap_math, shift=UP * 0.2),
            run_time=1.0
        )

        self.wait(1.0)

        # Release—snap back to baseline
        self.play(
            Transform(string_base, VMobject().set_points_as_corners(base_points)
                      .set_color_by_gradient(YIN_LIGHT, YANG_BRIGHT)
                      .set_stroke(width=2.0)),
            FadeOut(gap_math),
            run_time=0.8,
        )

        self.wait(0.3)


# ═══════════════════════════════════════════════════════════════════════════════
# SCENE 3: First Ripples (8–16s)
# ═══════════════════════════════════════════════════════════════════════════════
class FirstRipples(Scene):
    def construct(self):
        self.camera.background_color = FLUID_BG

        pond = create_pond()
        self.add(pond)

        time_tracker = ValueTracker(0)
        amp_tracker = ValueTracker(0.6)
        mean_tracker = ValueTracker(R0_X)

        string = create_string_vibration(time_tracker, amp_tracker, mean_tracker)
        ripples = create_ripple_system(time_tracker)

        self.add(string, ripples)

        # Text annotations
        txt1 = annotation(
            "The vibrating string sends wake waves through the fluid",
            DOWN * 2.5
        )
        txt2 = annotation(
            "These are the first structures—widely spaced, Yin-dominated",
            DOWN * 2.5
        )
        txt3 = annotation(
            "Where ripples cross, the fluid brightens—the first density peaks",
            DOWN * 2.5
        )

        self.play(FadeIn(txt1, shift=UP * 0.1), run_time=0.8)

        # Ramp up vibration and advance time
        self.play(
            time_tracker.animate.set_value(4.0),
            amp_tracker.animate.set_value(0.6),
            run_time=3.0,
            rate_func=linear,
        )

        self.play(FadeOut(txt1), FadeIn(txt2), run_time=0.8)

        self.play(
            time_tracker.animate.set_value(8.0),
            run_time=3.0,
            rate_func=linear,
        )

        self.play(FadeOut(txt2), FadeIn(txt3), run_time=0.8)
        self.wait(1.0)
        self.play(FadeOut(txt3), run_time=0.5)


# ═══════════════════════════════════════════════════════════════════════════════
# SCENE 4: The Pinch (16–26s)
# ═══════════════════════════════════════════════════════════════════════════════
class ThePinch(Scene):
    def construct(self):
        self.camera.background_color = FLUID_BG

        pond = create_pond()
        self.add(pond)

        time_tracker = ValueTracker(0)
        amp_tracker = ValueTracker(0.4)   # amplitude decreasing
        mean_tracker = ValueTracker(R0_X)

        string = create_string_vibration(time_tracker, amp_tracker, mean_tracker)
        ripples = create_ripple_system(time_tracker)

        # Pinch ring
        pinch_ring = Circle(
            radius=POND_RADIUS * 0.32,
            stroke_color=PINCH_COLOR,
            stroke_width=1.2,
            stroke_opacity=0.6,
            fill_opacity=0,
        ).move_to(np.array([PINCH_X + 0.5, STRING_Y, 0]))
        pinch_label = Text("r = \u03C6\u207B\u00B9", font_size=24, color=PINCH_COLOR)
        pinch_label.next_to(pinch_ring, UP, buff=0.1)

        self.add(string, ripples)

        # Start with time already advanced (continuing from FirstRipples)
        time_tracker.set_value(2.0)
        mean_tracker.set_value(R0_X)

        # Advance time, string drifts right toward pinch
        self.play(
            time_tracker.animate.set_value(6.0),
            mean_tracker.animate.set_value(PINCH_X + 0.2),
            run_time=4.0,
            rate_func=linear,
        )

        # Pinch ring appears
        txt_pinch = annotation(
            "At r = φ⁻¹, the Qi gate begins to close",
            DOWN * 2.5
        )
        self.play(
            FadeIn(pinch_ring),
            FadeIn(pinch_label),
            FadeIn(txt_pinch, shift=UP * 0.1),
            run_time=1.5,
        )

        # Pulse the ring
        for _ in range(3):
            self.play(
                pinch_ring.animate.set_stroke(width=2.0, opacity=0.8),
                run_time=0.3,
            )
            self.play(
                pinch_ring.animate.set_stroke(width=1.0, opacity=0.5),
                run_time=0.3,
            )

        # Cross the pinch
        txt_cross = annotation(
            "The field becomes an object to itself",
            DOWN * 2.5
        )
        self.play(
            FadeOut(txt_pinch),
            FadeIn(txt_cross),
            mean_tracker.animate.set_value(PHI_X * 0.5),
            time_tracker.animate.set_value(9.0),
            run_time=2.5,
            rate_func=smooth,
        )

        self.wait(1.0)
        self.play(FadeOut(txt_cross), run_time=0.5)


# ═══════════════════════════════════════════════════════════════════════════════
# SCENE 5: Cosmic Web (26–38s)
# ═══════════════════════════════════════════════════════════════════════════════
class CosmicWeb(Scene):
    def construct(self):
        self.camera.background_color = FLUID_BG

        pond = create_pond()
        self.add(pond)

        time_tracker = ValueTracker(0)
        amp_tracker = ValueTracker(0.15)   # gentle vibration
        mean_tracker = ValueTracker(PHI_X * 0.7)

        string = create_string_vibration(time_tracker, amp_tracker, mean_tracker)
        ripples = create_ripple_system(time_tracker)
        STATE.nodes_visible = True
        nodes = create_nodes(time_tracker)

        self.add(string, ripples, nodes)

        # Cascade rings
        cascade_data = [
            (0.25, "Electroweak"),
            (0.55, "Atomic"),
            (0.85, "Cellular"),
            (1.20, "Human"),
            (1.55, "Solar System"),
            (1.90, "Milky Way"),
            (2.30, "BAO"),
            (2.80, "Cassi bubble"),
            (2.98, "Hubble radius"),
        ]
        cascade_rings = VGroup()
        cascade_labels = VGroup()
        for i, (r, lbl) in enumerate(cascade_data):
            angle = PI / 4 + i * 0.04
            ring = Circle(
                radius=r, stroke_color=RING_COLOR,
                stroke_width=0.6, fill_opacity=0,
            ).set_opacity(0)
            label = Text(lbl, font_size=10, color=TEXT_SUB)
            label.move_to(np.array([
                r * np.cos(angle) * 0.9,
                r * np.sin(angle) * 0.9,
                0
            ])).set_opacity(0)
            cascade_rings.add(ring)
            cascade_labels.add(label)

        self.add(cascade_rings, cascade_labels)

        # Advance with ripple interference
        txt1 = annotation(
            "The interference pattern resolves into the cosmic web",
            DOWN * 2.5
        )

        self.play(
            time_tracker.animate.set_value(6.0),
            mean_tracker.animate.set_value(PHI_X * 0.85),
            run_time=3.0,
            rate_func=linear,
        )

        self.play(FadeIn(txt1, shift=UP * 0.1), run_time=1.0)

        self.play(
            time_tracker.animate.set_value(12.0),
            run_time=3.0,
            rate_func=linear,
        )

        # Fade in cascade rings
        txt2 = annotation(
            "292 φ-steps from Planck to Hubble",
            DOWN * 2.5
        )
        self.play(
            FadeOut(txt1),
            FadeIn(txt2),
            cascade_rings.animate.set_opacity(0.5),
            cascade_labels.animate.set_opacity(0.7),
            run_time=2.0,
        )

        self.wait(1.5)
        self.play(FadeOut(txt2), run_time=0.5)
        STATE.nodes_visible = False


# ═══════════════════════════════════════════════════════════════════════════════
# SCENE 6: Self-Plucking Loop (38–46s)
# ═══════════════════════════════════════════════════════════════════════════════
class SelfPlucking(Scene):
    def construct(self):
        self.camera.background_color = FLUID_BG

        # Zoomed-in view—show one bright node
        # Center the view on a node position
        node_center = np.array([0.8, 1.0, 0])

        # Draw the toroidal feedback loop
        # String → wakes → gravity → flow → string
        feedback_points = [
            node_center + np.array([-1.0, -0.5, 0]),   # string segment
            node_center + np.array([-0.2, 0.0, 0]),    # wake emission
            node_center + np.array([0.6, 0.3, 0]),     # gravity/flow
            node_center + np.array([0.3, 0.8, 0]),     # back to string
        ]

        # Curved arrows
        arrow1 = CurvedArrow(
            feedback_points[0], feedback_points[1],
            angle=-0.8, color=YANG_MID,
        )
        arrow2 = CurvedArrow(
            feedback_points[1], feedback_points[2],
            angle=0.5, color=YANG_BRIGHT,
        )
        arrow3 = CurvedArrow(
            feedback_points[2], feedback_points[3],
            angle=-1.0, color=YANG_MID,
        )
        arrow4 = CurvedArrow(
            feedback_points[3], feedback_points[0],
            angle=0.6, color=YANG_PEAK,
        )

        arrows = VGroup(arrow1, arrow2, arrow3, arrow4)

        # Labels
        labels = VGroup(
            Text("String\nr(t)", font_size=14, color=TEXT_MAIN).move_to(feedback_points[0] + UP * 0.4 + LEFT * 0.3),
            Text("Wakes\nε(x)", font_size=14, color=TEXT_MAIN).move_to(feedback_points[1] + DOWN * 0.4 + LEFT * 0.2),
            Text("Gravity\n∇²Φ", font_size=14, color=TEXT_MAIN).move_to(feedback_points[2] + RIGHT * 0.5 + UP * 0.1),
            Text("Flow\n−u·∇", font_size=14, color=TEXT_MAIN).move_to(feedback_points[3] + UP * 0.3 + RIGHT * 0.2),
        )

        # Central node
        node = Dot(
            point=node_center,
            color=YANG_PEAK,
            radius=0.15,
        )
        node_glow = Dot(
            point=node_center,
            color=YANG_PEAK,
            radius=0.3,
        ).set_opacity(0.3)

        # Scene
        self.play(FadeIn(node_glow), FadeIn(node), run_time=0.8)

        txt = annotation(
            "At high density, the fluid feeds back into the string",
            DOWN * 2.5
        )
        self.play(Write(txt), run_time=1.0)

        # Animate arrows appearing one by one
        for arrow in [arrow1, arrow2, arrow3, arrow4]:
            self.play(Create(arrow), run_time=0.6)
            self.wait(0.2)

        # Pulse the loop
        self.play(
            arrows.animate.set_stroke(width=4),
            node.animate.scale(1.3),
            run_time=0.5,
        )
        self.play(
            arrows.animate.set_stroke(width=2),
            node.animate.scale(1/1.3),
            run_time=0.5,
        )

        # Add labels
        self.play(FadeIn(labels), run_time=1.0)

        txt2 = annotation(
            "The self-plucking torus—physical basis of sustained coherence",
            DOWN * 2.5
        )
        self.play(FadeOut(txt), FadeIn(txt2), run_time=1.0)

        self.wait(1.5)
        self.play(FadeOut(txt2), FadeOut(labels), FadeOut(arrows),
                  FadeOut(node), FadeOut(node_glow), run_time=1.0)


# ═══════════════════════════════════════════════════════════════════════════════
# SCENE 7: Two Listeners (46–54s)
# ═══════════════════════════════════════════════════════════════════════════════
class TwoListeners(Scene):
    def construct(self):
        self.camera.background_color = FLUID_BG

        pond = create_pond()
        self.add(pond)

        # Two bright nodes
        node1_pos = np.array([-0.8, 1.2, 0])
        node2_pos = np.array([1.2, -0.6, 0])

        node1 = Dot(point=node1_pos, color=YANG_BRIGHT, radius=0.12)
        node2 = Dot(point=node2_pos, color=YANG_BRIGHT, radius=0.12)
        node1_glow = Dot(point=node1_pos, color=YANG_BRIGHT, radius=0.25).set_opacity(0.25)
        node2_glow = Dot(point=node2_pos, color=YANG_BRIGHT, radius=0.25).set_opacity(0.25)

        self.play(
            FadeIn(node1_glow), FadeIn(node1),
            FadeIn(node2_glow), FadeIn(node2),
            run_time=1.5,
        )

        txt1 = annotation(
            "Two regions of the field—both above the pinch",
            DOWN * 2.5
        )
        self.play(Write(txt1), run_time=1.0)

        # Emit ripples from both nodes
        ripple_groups = []
        for _ in range(3):
            for node_pos, color in [(node1_pos, YANG_BRIGHT), (node2_pos, YANG_BRIGHT)]:
                ripple = Circle(
                    radius=0.1,
                    stroke_color=color,
                    stroke_width=2.0,
                    stroke_opacity=0.5,
                    fill_opacity=0,
                ).move_to(node_pos)
                self.add(ripple)
                ripple_groups.append(ripple)

        self.play(
            *[r.animate.scale(15).set_stroke(opacity=0) for r in ripple_groups],
            run_time=3.0,
            rate_func=linear,
        )
        for r in ripple_groups:
            self.remove(r)

        txt2 = annotation(
            "At φ-spaced separations, their wake waves resonate",
            DOWN * 2.5
        )
        self.play(FadeOut(txt1), FadeIn(txt2), run_time=1.0)

        # Standing wave line between them
        connection = DashedLine(
            node1_pos, node2_pos,
            dash_length=0.1,
            stroke_color=YANG_PEAK,
            stroke_width=1.5,
            stroke_opacity=0.6,
        )
        self.play(Create(connection), run_time=1.0)

        # Pulse the bridge
        for _ in range(2):
            self.play(
                connection.animate.set_stroke(width=3, opacity=0.9),
                node1_glow.animate.scale(1.2),
                node2_glow.animate.scale(1.2),
                run_time=0.4,
            )
            self.play(
                connection.animate.set_stroke(width=1.5, opacity=0.5),
                node1_glow.animate.scale(1/1.2),
                node2_glow.animate.scale(1/1.2),
                run_time=0.4,
            )

        txt3 = annotation(
            "Two-bubble resonance—the physical basis of connection",
            DOWN * 2.5
        )
        self.play(FadeOut(txt2), FadeIn(txt3), run_time=1.0)

        self.wait(1.0)
        self.play(
            FadeOut(txt3), FadeOut(connection),
            FadeOut(node1), FadeOut(node1_glow),
            FadeOut(node2), FadeOut(node2_glow),
            run_time=0.8,
        )


# ═══════════════════════════════════════════════════════════════════════════════
# SCENE 8: The Chord (54–59s)
# ═══════════════════════════════════════════════════════════════════════════════
class TheChord(Scene):
    def construct(self):
        self.camera.background_color = FLUID_BG

        # Full pond with all elements
        pond = create_pond()
        self.add(pond)

        time_tracker = ValueTracker(0)
        amp_tracker = ValueTracker(0.08)
        mean_tracker = ValueTracker(PHI_X * 0.9)

        string = create_string_vibration(time_tracker, amp_tracker, mean_tracker)
        ripples = create_ripple_system(time_tracker)
        STATE.nodes_visible = True
        nodes = create_nodes(time_tracker)

        self.add(string, ripples, nodes)

        # Cascade rings (from scene 5)
        cascade_data = [
            (0.25, "E-weak"), (0.55, "Atomic"), (0.85, "Cell"),
            (1.20, "Human"), (1.55, "Solar"), (1.90, "Galaxy"),
            (2.30, "BAO"), (2.80, "Wu Xing"), (2.98, "Hubble"),
        ]
        cascade_rings = VGroup()
        cascade_labels = VGroup()
        for i, (r, lbl) in enumerate(cascade_data):
            angle = PI / 4 + i * 0.04
            ring = Circle(
                radius=r, stroke_color=RING_COLOR,
                stroke_width=0.4, fill_opacity=0,
            ).set_opacity(0.4)
            label = Text(lbl, font_size=9, color=TEXT_SUB)
            label.move_to(np.array([
                r * np.cos(angle) * 0.85,
                r * np.sin(angle) * 0.85,
                0
            ])).set_opacity(0.6)
            cascade_rings.add(ring)
            cascade_labels.add(label)

        self.add(cascade_rings, cascade_labels)

        # Advance time gently
        self.play(
            time_tracker.animate.set_value(5.0),
            run_time=2.0,
            rate_func=linear,
        )

        # Final title
        title = Text(
            "The Resonant Pond",
            font_size=48,
            color=YANG_PEAK,
        )
        title.move_to(UP * 2.8)

        subtitle = Text(
            "One pluck. One string. One constant. Everything else is harmonics.",
            font_size=20,
            color=TEXT_SUB,
        )
        subtitle.next_to(title, DOWN, buff=0.3)

        phi_tag = Text("\u03C6 \u2248 1.618", font_size=28, color=YANG_BRIGHT)
        phi_tag.move_to(DOWN * 2.8)

        self.play(
            Write(title),
            FadeIn(subtitle, shift=DOWN * 0.1),
            Write(phi_tag),
            run_time=2.5,
        )

        # Gentle final hold
        self.wait(2.0)
        STATE.nodes_visible = False


# ═══════════════════════════════════════════════════════════════════════════════
# MASTER: Full sequence (for single-render convenience)
# ═══════════════════════════════════════════════════════════════════════════════
class ResonantPond(Scene):
    """Master scene that chains all 8 scenes. Render with: manim -pqh resonant_pond.py ResonantPond"""

    def construct(self):
        # Scene 1: Still Pond
        still = StillPond()
        still.camera = self.camera
        still.construct()

        # Scene 2: The Pluck
        self.clear()
        pluck = ThePluck()
        pluck.camera = self.camera
        pluck.construct()

        # Scene 3: First Ripples
        self.clear()
        ripples = FirstRipples()
        ripples.camera = self.camera
        ripples.construct()

        # Scene 4: The Pinch
        self.clear()
        pinch = ThePinch()
        pinch.camera = self.camera
        pinch.construct()

        # Scene 5: Cosmic Web
        self.clear()
        web = CosmicWeb()
        web.camera = self.camera
        web.construct()

        # Scene 6: Self-Plucking
        self.clear()
        sp = SelfPlucking()
        sp.camera = self.camera
        sp.construct()

        # Scene 7: Two Listeners
        self.clear()
        listeners = TwoListeners()
        listeners.camera = self.camera
        listeners.construct()

        # Scene 8: The Chord
        self.clear()
        chord = TheChord()
        chord.camera = self.camera
        chord.construct()


# ═══════════════════════════════════════════════════════════════════════════════
# Render entry point
# ═══════════════════════════════════════════════════════════════════════════════
if __name__ == "__main__":
    # When run directly (not through manim), print usage
    print(__doc__)
