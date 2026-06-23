---
name: iterm2-to-ghostty
description: >-
  Migrate iTerm2 terminal settings — colors, font, transparency, cursor, window
  size, scrollback, and option-key behaviour — into a Ghostty config file.

  Use this skill whenever the user wants to move, port, copy, or convert their
  iTerm2 setup, profile, theme, or preferences to Ghostty, or has an iTerm2
  plist/profile on one side and a Ghostty config on the other. Trigger phrases:
  "migrate my iTerm2 config to Ghostty", "iterm to ghostty", "convert my iterm
  profile to ghostty", "I switched to Ghostty, how do I bring my config over",
  "reproduce my iTerm colors/font in Ghostty".

  Also suitable for cmux, which is built on Ghostty and reads the same config —
  e.g. "move my iTerm config to cmux".

  Also converts an iTerm2 .itermcolors palette into Ghostty palette lines.
---

# iterm2-to-ghostty

Port an iTerm2 profile into an equivalent Ghostty config. The hard part is the
mapping: iTerm stores colors as 0–1 float components, transparency is the inverse
of opacity, fonts are PostScript names not family names, and several Ghostty keys
have non-obvious names or scales. `scripts/iterm2_to_ghostty.py` encodes all of
that, so prefer running it over hand-translating. (The same config also drives
[cmux](https://cmux.com), which is built on Ghostty — see the note at the end.)

## Workflow

1. **Locate the inputs and check for an existing config.**
   - iTerm2 prefs: `~/Library/Preferences/com.googlecode.iterm2.plist` (binary plist).
     If the user points at a different file or an exported `.plist`, use that.
   - Ghostty config target, in macOS search order: `~/.config/ghostty/config`,
     then `~/Library/Application Support/com.mitchellh.ghostty/config.ghostty`.
   - **Check whether a target config already exists.** If it does, don't plan to
     overwrite it silently — you'll stop and ask the user in step 6. Note it now.

2. **List the profiles and pick the right one — don't choose silently.** A
   person's iTerm2 prefs often hold several profiles, and converting the wrong
   one wastes their time:
   ```bash
   python3 scripts/iterm2_to_ghostty.py --list-profiles
   ```
   - **One profile** → just use it.
   - **Several profiles, and the user already told you which** (named it, or said
     "my current/default one") → use `--profile "<Name>"` or `--default`.
   - **Several profiles and the user hasn't said which** → show them the list
     (the `(default)` marker tells them which iTerm2 currently uses) and ask which
     to migrate before converting. The converter enforces this: run with no
     selection on a multi-profile plist and it refuses (exit 2) and prints the
     list, so you can't convert the wrong one by accident.

3. **Generate the config** to stdout and read it:
   ```bash
   python3 scripts/iterm2_to_ghostty.py [--plist FILE] [--profile NAME | --default]
   ```
   Every line carries a comment recording its iTerm2 source, plus a trailing
   "Not migrated" section listing settings with no clean Ghostty equivalent.
   Relay that section to the user — it's where they lose something.

4. **Check the font is installed, and warn the user if it isn't.** The script
   guesses the family from iTerm's PostScript name (e.g. `MesloLGS-NF-Regular`
   → `MesloLGS NF`), which is best-effort — and a missing font makes Ghostty
   silently fall back to its default, which surprises people. Verify it:
   ```bash
   python3 scripts/iterm2_to_ghostty.py [--plist FILE] --check-font "<family from the config>"
   ```
   - **OK** (exit 0) → good, move on.
   - **MISSING** (exit 1) → tell the user plainly that the font isn't installed
     and Ghostty will fall back to its default. Offer to: install it, or change
     `font-family` to a font they do have (if a close match exists in
     `system_profiler SPFontsDataType`, suggest it). Don't quietly ship a config
     that points at a font that isn't there.
   - **UNKNOWN** (exit 2, e.g. no `fc-list`/`system_profiler`) → ask the user to
     confirm the font manually.

   `--report` (step 5) runs this same check and bakes the verdict in.

5. **Show the user what changed.** Re-run with `--report` for a curated,
   human-readable summary (a "what changed" table, the not-migrated list, and
   reminders) and present it — this is the payoff, so don't skip it:
   ```bash
   python3 scripts/iterm2_to_ghostty.py [--plist FILE] [--profile NAME | --default] --report
   ```
   It highlights the conversions a person actually wonders about — the
   transparency→opacity inversion, "unlimited" scrollback becoming a byte cap, the
   PostScript font name becoming a family name — and what didn't carry over. Relay
   it in the user's language.

6. **If a config already exists, ASK before touching it; otherwise write it.**
   This is important — never clobber a config the user may have hand-tuned.
   - **A target config already exists** (from step 1) → stop and ask the user how
     to proceed:
     - **Create a new one** → first move the existing file to a timestamped
       backup, then write the new config:
       ```bash
       mv ~/.config/ghostty/config ~/.config/ghostty/config.backup.$(date +%Y%m%d-%H%M%S)
       ```
       Tell them the exact backup path so they can restore or diff it.
     - **Merge** → keep their existing lines and only add/replace the migrated
       keys, rather than overwriting the whole file.
     - **Cancel** → leave everything as-is.
   - **No existing config** → create `~/.config/ghostty/` if needed and write the
     generated config there.

7. **Validate** if the Ghostty binary is available (it lives inside the app bundle
   and is usually not on `PATH`):
   ```bash
   /Applications/Ghostty.app/Contents/MacOS/ghostty +validate-config --config-file ~/.config/ghostty/config
   ```
   If Ghostty isn't installed yet, say so — the config is still valid, it just
   can't be machine-checked. A running Ghostty reloads with **⌘+⇧+,**.

## What gets migrated

Colors (background/foreground/cursor/selection + the 16 ANSI palette entries),
font family & size, bold-is-bright, window columns/rows, cell spacing,
background opacity (inverted from transparency), background blur, cursor blink &
shape, unlimited scrollback, and Option-as-Alt. Full key-by-key table and the
reasoning behind each conversion is in `references/mapping.md` — read it when you
need to verify a mapping, extend the script, or hand-translate something.

## Things to get right (common mistakes)

- **Opacity is inverted.** iTerm `Transparency = 0.15` → `background-opacity = 0.85`.
- **`scrollback-limit = 0` disables scrollback** in Ghostty; "unlimited" must be a
  large byte count, not 0.
- **Font name ≠ family name.** Always verify (step 4).
- **Never overwrite an existing config without asking** (step 6).
- **Don't bulk-port keybindings.** iTerm's `GlobalKeyMap` is mostly default text
  navigation Ghostty already has. Only port bindings the user calls out as custom.

## Also works with cmux

[cmux](https://github.com/manaflow-ai/cmux) is built on Ghostty (`libghostty`)
and reads the **same Ghostty config files** (`~/.config/ghostty/config`, then
`~/Library/Application Support/com.mitchellh.ghostty/config.ghostty`), so the
config this produces drives cmux too — no extra work. cmux-only features
(vertical tabs, sidebar, notifications) live in `~/.config/cmux/cmux.json` and are
out of scope.

## Converting a `.itermcolors` file

An `.itermcolors` file is an XML plist whose top-level keys are
`Ansi 0 Color`…`Ansi 15 Color`, `Background Color`, etc. — the same color dicts as
a profile. Load it with `plistlib` and apply the color rules from
`references/mapping.md` (or adapt the script's `color_to_hex` + `_COLOR_MAP`).
