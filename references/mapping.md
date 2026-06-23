# iTerm2 → Ghostty setting map

The converter script (`scripts/iterm2_to_ghostty.py`) already applies everything
below. Read this when you need to verify a specific mapping, explain a choice to
the user, extend the script, or hand-translate a setting the script skipped.

## Where things live

- **iTerm2 prefs**: `~/Library/Preferences/com.googlecode.iterm2.plist` — a binary
  plist. Profiles live under the `New Bookmarks` array (one dict per profile). The
  active one is whichever profile's `Guid` matches the top-level `Default Bookmark Guid`.
  Read it with Python's `plistlib` (handles binary plists); `plutil -convert json`
  often fails on this file because it contains non-JSON-serialisable values.
- **Ghostty config**: `~/.config/ghostty/config` (the path Ghostty actually reads on
  macOS; **cmux reads the same file** — it's built on libghostty). One
  `key = value` per line; `#` comments; repeat a key (e.g. `palette`,
  `font-family`) to add entries. Reload a running Ghostty or cmux with **⌘+⇧+,**.

## Colors

iTerm stores each color as a dict of `Red/Green/Blue Component` floats in `0..1`
(plus an optional `Alpha Component` and a `Color Space`). Convert to `#rrggbb` by
rounding each component × 255. Alpha and color space are ignored — Ghostty colors
are plain RGB hex, and opacity is global (see Transparency).

| iTerm2 profile key      | Ghostty key            |
| ----------------------- | ---------------------- |
| `Background Color`      | `background`           |
| `Foreground Color`      | `foreground`           |
| `Cursor Color`          | `cursor-color`         |
| `Cursor Text Color`     | `cursor-text`          |
| `Selection Color`       | `selection-background` |
| `Selected Text Color`   | `selection-foreground` |
| `Ansi 0 Color` … `Ansi 15 Color` | `palette = 0=#…` … `palette = 15=#…` |

## Font

iTerm stores `Normal Font` as `"<PostScriptName> <size>"`, e.g.
`"MesloLGS-NF-Regular 16"`. Split off the trailing numeric size →
`font-size`. The name part is a **PostScript name**, not a family name —
Ghostty's `font-family` wants the family name. The converter guesses by
replacing `-`/`_` with spaces and stripping trailing weight/slant words
(`Regular`, `Bold`, `Italic`, …), giving `MesloLGS NF`.

This guess is lossy: PostScript names drop the spaces family names have, so
`FiraCode-Retina` → guess `FiraCode` but the real family is `Fira Code`.
**Always verify** the family resolves to an installed font:

```bash
system_profiler SPFontsDataType | grep -i "<family fragment>"
```

If it doesn't match, fix `font-family` to the `Family:` line that command prints.

- `Use Bright Bold` (or legacy `Brighten Bold Text`) = true → `bold-is-bright = true`.
- `Use Non-ASCII Font` = true → emit `Non Ascii Font` as an extra `font-family`
  line (Ghostty uses repeated `font-family` for fallback). If false, ignore it.

## Window & cell

| iTerm2                         | Ghostty                                    |
| ------------------------------ | ------------------------------------------ |
| `Columns`                      | `window-width` (grid cells, not pixels)    |
| `Rows`                         | `window-height` (grid cells)               |
| `Horizontal Spacing` (× mult.) | `adjust-cell-width = <(m-1)*100>%`          |
| `Vertical Spacing` (× mult.)   | `adjust-cell-height = <(m-1)*100>%`         |

Spacing multipliers of `1.0` are normal → emit nothing.

## Transparency & blur

- `Transparency` is `0..1` where 0 = opaque. Ghostty's `background-opacity` is the
  inverse: `background-opacity = 1 - Transparency`. (This is the easiest mapping to
  get backwards.)
- `Blur` = true → `background-blur = true`. iTerm's `Blur Radius` and Ghostty's
  blur radius are different scales, so prefer `true` (Ghostty's sensible default)
  over copying the raw number.

## Cursor

- `Blinking Cursor` (bool) → `cursor-style-blink = true|false`.
- `Cursor Type`: `0` underline, `1` vertical bar, `2` box →
  `cursor-style = underline|bar|block`.

## Scrollback

- `Unlimited Scrollback` = true → `scrollback-limit = 100000000` (~100 MB).
  **Do not** use `0` — in Ghostty `scrollback-limit = 0` *disables* scrollback.
- `Scrollback Lines` (when not unlimited) has no clean mapping: iTerm counts
  lines, Ghostty counts bytes. Leave Ghostty's default and note it.

## Keyboard — Option as Alt

iTerm option behaviour: `0` Normal (compose chars), `1` Meta, `2` Esc+. Both Meta
and Esc+ mean "act as a modifier", matching Ghostty's option-as-alt. Profile keys
`Option Key Sends` / `Right Option Key Sends` take precedence; top-level
`LeftOption` / `RightOption` are the fallback. Map to:

- both sides modifier → `macos-option-as-alt = true`
- left only → `left`, right only → `right`
- both Normal → omit (Ghostty default is off)

## Keybindings (usually skip)

`GlobalKeyMap` and the profile `Keyboard Map` encode key→action bindings as
opaque `keycode-modifiers` strings. The vast majority are iTerm's default
"natural text editing" bindings (Option+←/→ by word, ⌘+←/→ to line ends), which
Ghostty already provides. Don't bulk-translate them. Only port bindings the user
identifies as genuinely custom, mapping them to Ghostty `keybind = trigger=action`
lines by hand.

## Settings with no clean equivalent (skip, but tell the user)

- `Minimum Contrast` — iTerm `0..1`; Ghostty `minimum-contrast` is a `1..21`
  contrast ratio. No honest conversion.
- Bell settings (`Visual Bell`, `Silence Bell`, `Flashing Bell`) — Ghostty's bell
  configuration is limited and version-dependent; skip unless asked.
- `Badge`, `Background Image`, per-profile working directory, triggers, smart
  selection — no Ghostty analogue.
