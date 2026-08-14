# Cassi UI — Design Language & Component Library

The `addons/cassi_ui/` library is the design language for the Cassi space-sim
research tool's interface. It packages the house visual theme (already
committed at `addons/cassi_ui/theme/cassi_theme.tres`) into self-contained,
interaction-conventioned components a later migration worker can rebuild the
hand-built `scripts/sim_ui.gd` UI from, this document alone.

Everything below is the source of truth: tokens, type scale, spacing,
interaction conventions, the two-palette rule, and the component API.

---

## 1. Palette

All colors live in the theme under the pseudo-type namespace **"Cassi"**
(`Theme.get_color(token, &"Cassi")`). Split into two families — see the
two-palette rule (§4) before choosing one.

### 1.1 UI chrome tokens (surfaces, borders, typography)

| Token | Value | Semantic role |
|---|---|---|
| `panel_bg` | `Color(0.02,0.03,0.1,0.9)` | Panel background — near-black, blue-tinted, 90% opaque. Never used directly; it lives in the panel StyleBoxFlat. |
| `panel_border` | `Color(0.3,0.5,1,0.5)` | Panel border — soft steel blue, 50% alpha. Also the resting border for controls. |
| `text` | `Color(0.8,0.9,1,1)` | Default body text. |
| `text_dim` | `Color(0.7,0.85,1,1)` | Secondary text — diagnostics lines, less prominent readouts. |
| `text_hint` | `Color(0.5,0.7,0.9,1)` | Disabled/hint text — placeholder captions, connection status when idle. |
| `text_bright` | `Color(0.95,0.98,1,1)` | Emphasis text — live numeric readouts, the scale label. |
| `disabled` | `Color(0.5,0.5,0.6,1)` | Disabled controls/fields — e.g. the server LineEdits' modulate. |
| `slate` | `Color(0.4,0.5,0.7,1)` | "Future/placeholder" captions — the Server (future) group label. |

### 1.2 Physics "data" tokens (quantity captions)

| Token | Value | Semantic role |
|---|---|---|
| `gold` | `Color(0.9,0.85,0.5,1)` | **The φ motif.** Primary physics accent — captions for scalar params (Grid N, Particles, Init, Color) and the pressed/highlighted state of toggles. |
| `gold_soft` | `Color(0.9,0.8,0.5,1)` | Softer gold — slider caption text (sim_ui `_build_slider_row` uses it for xi/Source). |
| `gold_bright` | `Color(0.95,0.85,0.5,1)` | Brightest gold — emphasis within gold contexts (live falsification line). |
| `cluster` | `Color(0.8,0.6,0.4,1)` | Cluster-section captions (Clusters). |
| `sep` | `Color(0.4,0.7,0.8,1)` | Separation param caption (Separation). |
| `mint` | `Color(0.6,0.95,0.8,1)` | VFX/subsection captions (VFX label), fresh/active emphasis. |

> Note on `gold` vs `gold_soft`/`gold_bright`: all three are the gold family;
> `gold` is the canonical accent, `gold_soft` the muted caption variant,
> `gold_bright` the hover/highlight variant.

### 1.3 Panel stylebox (the chrome vessel)

`PanelContainer/styles/panel` — the one built-in StyleBoxFlat (a `Cassi`
token `panel_bg` + `panel_border` folded into it):

| Property | Value |
|---|---|
| `bg_color` | `panel_bg` |
| `border_color` | `panel_border`, width 1 (all sides) |
| corner radius | 6 (all corners) |
| content margin | 10 (all sides) |

Applied automatically to `PanelContainer`s by type when a root theme is set;
`CPanel` also applies it as an explicit override so it works without a root.

---

## 2. Type scale

Font sizes also live under the **"Cassi"** namespace
(`Theme.get_font_size(token, &"Cassi")`).

| Token | Value | Usage rule |
|---|---|---|
| `hud` | 16 | Single most prominent readout (the FPS/mode info line). Large, few. |
| `body` | 14 | Default label text when no more specific token fits. |
| `detail` | 13 | Wrapped explanations / diagnostic multi-line blocks (the info-panel diag label). |
| `param` | 12 | Control captions, value readouts, compact hint text — the workhorse for rows of params. |

Usage rules:
- Default to `param` for anything inside a control row (captions, live values).
- `body` for standalone explanatory text.
- `hud` only for the top-line system readout; `detail` only for wrapped/blocks.
- Never mix sizes within a single row of homogeneous controls.

---

## 3. Spacing scale

Fixed separation constants, matching the sim's hand-built values:

| Value | Where it applies |
|---|---|
| **4 px** | Tight vertical rhythm inside a group (info-vbox separation, param caption→slider gap). |
| **6 px** | Default between sibling controls in a row (color-row, legend-row, segmented buttons). |
| **8 px** | Wider row separation (row1/row-vfx/legend-row sibling groups). |
| **12 px** | Between top-level control columns (row2/row3 column separation). |

Corner radii: **3** for small interactive controls (CToggle/segment pressed
style), **6** for panels (the house StyleBoxFlat).

UI insets: panels carry 10px content margin (the stylebox); control rows sit
10px from the window edge padded by panels.

---

## 4. Interaction conventions

These are the invariant defaults every interactive component bakes in — the
migration must never hand-set these per control again.

- **`focus_mode = Control.FOCUS_NONE` on every interactive control.** The
  sim's WASD camera must keep keyboard focus. A control that takes focus
  steals the camera keys and silently breaks navigation. `SpinBox`, `HSlider`,
  `Button`, `OptionButton`, `CheckButton` all get it.
- **`mouse_default_cursor_shape = Control.CURSOR_POINTING_HAND` on every
  clickable control** — affordance that the element reacts.
- **`mouse_filter`:** interactive controls use `Control.MOUSE_FILTER_STOP`
  (they claim clicks); passive chrome (panels, labels, containers) use
  `MOUSE_FILTER_IGNORE` so they never swallow camera drags over empty UI.
- **`tooltip_text` on everything interactive.** Every toggle/button explains
  what it does — the sim's buttons all carry explanatory tooltips; keep this.
- **Toggles are `toggle_mode = true`** and read their state from
  `button_pressed`. Exclusive groups use a `ButtonGroup` (see CSegmented).

---

## 5. The two-palette rule

Split color use by *what the color means*:

- **UI "chrome" colors** — `panel_bg`, `panel_border`, `text`, `text_dim`,
  `text_hint`, `text_bright`, `disabled`, `slate`. These are interface
  surfaces, borders, and typography. They describe *the interface*.
- **Physics "data" colors** — `gold`, `gold_soft`, `gold_bright`, `cluster`,
  `sep`, `mint`. These accent *quantities and sections in the physics*. They
  describe *the content*.

Rules:
1. **The rainbow/Qi scale is DATA, never chrome.** The particle color scale
   (hue-from-coherence mapping in the instancer) is a physics quantity and
   must never be reused for UI chrome, and chrome palettes must never leak
   into the data scale. Chrome and data stay visually distinct so a user can
   always tell "interface" from "quantity".
2. **Gold = the φ motif.** `gold` (and its soft/bright variants) is reserved
   for the golden-ratio accent: the pressed/highlighted state of toggles and
   the captions of scalar φ-linked params. It is the one accent color allowed
   to cross the line (it marks "the interesting physics parameter"), but it
   must be used sparingly — an accent, not a fill.
3. Use `cluster`/`sep`/`mint` only for the physics sections they name; `slate`
   for "future/placeholder" chrome.

---

## 6. Component API reference

All components preload the theme (`const CASSI_THEME`) and apply their own
overrides in `_ready()`, so the library renders identically in any project
even without a root theme assignment. All members are snake_case; all types
static. File names are snake_case; `class_name`s are PascalCase.

### 6.1 `CPanel extends PanelContainer` — `components/cpanel.gd`

Styled chrome container — applies `PanelContainer/styles/panel` as an
explicit override.

- `static func with_content(content: Control) -> CPanel` — factory wrapping
  `content` as the single child.
- `func set_content(content: Control) -> void` — clear any prior child and
  add `content`.
- Nothing else; a passive vessel (mouse filter IGNORE). Add a single VBox/HBox
  child and fill it.

### 6.2 `CLabel extends Label` — `components/clabel.gd`

Theme-driven text label. Resolves the named color and font-size tokens and
applies `font_color`/`font_size` overrides.

- `static func make(text: String, color_token: String = "text", size_token: String = "body") -> CLabel` — the migration target replacing every `_make_label(...)` call.
- Exported properties: `color_token: String = "text"`, `size_token: String = "body"`.
- Use `label.text = ...` to change content; `_ready()` and setters re-apply tokens.

### 6.3 `CButton extends Button` — `components/cbutton.gd`

Plain action button with the interaction defaults baked in (FOCUS_NONE,
POINTING_HAND, MOUSE_FILTER_STOP).

- `static func make(text: String, pressed_cb: Callable = Callable()) -> CButton` — optional callback connected to `pressed`.
- Not a toggle — for exclusive selection use `CToggle` / `CSegmented`.

### 6.4 `CToggle extends Button` — `components/ctoggle.gd`

Toggle-mode button with the defaults plus a gold pressed-state style
(gold text + gold-bordered pressed stylebox built from `panel_border` /
`gold` tokens — the sim's gold-accent look).

- `static func make(text: String, pressed: bool = false) -> CToggle`.
- `toggle_mode = true`; reads `button_pressed`; emits `toggled(pressed)`.
- Use as the member of a `CSegmented`, or standalone for check/radio-style
  on-off flags.

### 6.5 `CSegmented extends Control` — `components/csegmented.gd`

Exclusive segmented control — an HBox of mutually-exclusive `CToggle`s
(ButtonGroup mutex). Replaces `_build_mode_buttons` / `_build_gravity_buttons`.

- `func setup(options: Array[String], selected: int, on_changed: Callable = Callable()) -> void` — builds/re-builds the button row (idempotent), sets the initial index, wires the change callback to `selection_changed`. The callback may be a method `Callable(self, "method")` or a lambda.
- `var selected_index: int` — getter returns the live index; **setter presses the matching button** respecting the group mutex and emits `selection_changed`.
- `signal selection_changed(index: int)` — emitted on user pick or on `selected_index` assignment.
- `var buttons: Array[CToggle]` — exposed for per-button styling/tooltips after setup.
- `var button_min_width: int = 100` — configurable segment min width (matches the sim's Mode buttons).
- `func set_selected_no_signal(i: int) -> void` — sync from external state without emitting.

### 6.6 `CParam extends Control` — `components/cparam.gd`

Parameter row: caption `CLabel` above an HBox of `HSlider` + live value
`CLabel`. Restructured from `_build_slider_row` — the caption stays fixed
while the value label beside the slider updates live.

- `func setup(caption: String, caption_token: String, min_v: float, max_v: float, step_v: float, value: float, changed_cb: Callable) -> void` — configure the row (idempotent). `caption_token` is the color token for both labels (the sim's sliders use `"gold_soft"`).
- Exposed members: `caption_label: CLabel`, `value_label: CLabel`, `slider: HSlider`.
- **Value label formatting** (matches the sim's live readouts): fractional `step_v` → `"%.1f"` (one decimal); integer `step_v` → `"%d"` (integer). E.g. xi (step 0.5) shows `18.0`; Grid N (step 64) shows `64`.
- `func set_value_no_signal(v: float) -> void` — update slider + label without firing the callback; `func get_value() -> float` — current value.
- The slider is FOCUS_NONE + POINTING_HAND; changes fire `changed_cb` with the new value.

### 6.7 `CGroupPanel extends CPanel` — `components/cgroup_panel.gd`

CPanel with a collapse header (CButton) over a content VBoxContainer.

- `func set_title(t: String) -> void` — set the group title; header reads `"▸ Title"` (collapsed) / `"▾ Title"` (expanded).
- `func content() -> VBoxContainer` — the container to fill with rows.
- `var collapsed: bool` — default `false` (expanded). Assigning flips the header glyph and `content().visible` synchronously, and emits `toggled`.
- `signal toggled(is_collapsed: bool)`.
- Header is a `CButton` (FOCUS_NONE, pointing hand), tooltip `"collapse/expand"`. No animation (kept simple and layout-safe). `content_box: VBoxContainer` is the same container as `content()`.

---

## 7. Migration notes (for the worker rebuilding sim_ui.gd)

- Replace `_make_label(text, tok, size)` → `CLabel.make(text, tok, size)`.
- Replace the hand `Button.new()` + focus/cursor lines → construct `CButton` /
  `CToggle` / `CSegmented` directly; the defaults are already correct.
- Replace `_build_mode_buttons` / `_build_gravity_buttons` → a `CSegmented`
  whose buttons get min-width 100 (Mode) / 90 (Gravity).
- Replace `_build_slider_row` + the `_xi_label = ...get_child(0)` re-grab
  gymnastics → a `CParam`; read `cparam.value_label.text` directly.
- `_set_mode_highlight` / `_set_grav_highlight` press-state loops →
  `segmented.selected_index = i` (or `set_selected_no_signal` when syncing
  from the sim without a callback).
- The `focus_mode = FOCUS_NONE` block at the end of `_ready` (for SpinBoxes
  and sliders) becomes unnecessary — components bake it in. Only standalone
  `Label`/`PanelContainer` nodes need nothing.
- Value-label formats: `CParam` handles "%.1f unless integer step" already;
  captions that embed a value (the old `"xi: 18.0"` caption) should move the
  value out of the caption into `value_label` — the caption keeps just the
  param name.
