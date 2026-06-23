# Migrating iTerm2 to Ghostty (and cmux)

A Claude Code skill for moving an iTerm2 profile to a [Ghostty](https://ghostty.org/) (and [cmux](https://cmux.com)) config *correctly* —
colors, font, transparency, cursor, window size, scrollback, and the Option key.

**Moving to cmux?** This is for you too — cmux is built on
Ghostty and reads the same config, so generating that Ghostty config is exactly
how you carry your iTerm2 look-and-feel into cmux.

The catch it exists to solve: a hand-copied config quietly gets things wrong.

## What problem this solves

iTerm2 and Ghostty store the "same" settings differently, and a few translate in
non-obvious ways — so a hand-migrated config usually carries subtle bugs:

- **Transparency is inverted.** iTerm `Transparency = 0.15` is Ghostty
  `background-opacity = 0.85`, not `0.15`.
- **`scrollback-limit = 0` disables scrollback**, so "unlimited scrollback" must
  become a large *byte* count — never `0`, and never iTerm's *line* count pasted
  verbatim.
- **A font's PostScript name is not its family name.** iTerm stores
  `MesloLGS-NF-Regular`; Ghostty wants `MesloLGS NF`. Get it wrong and Ghostty
  silently falls back to its default font.
- **Multiple profiles** shouldn't be resolved by guessing which one you meant.
- **An existing config shouldn't be clobbered** — the skill backs it up and asks
  first.

The skill encodes those rules, verifies the target font is actually installed,
refuses to silently convert the wrong profile, never overwrites an existing
config without asking, and shows a human-readable summary of what changed.

## Requirements

- macOS (iTerm2 and the Ghostty/cmux config are macOS-only)
- Python 3 (runs the converter; `python3`, no extra packages)

## Install

Use the `skills` CLI from vercel-labs.

```bash
# add to your user skills (available in every project)
npx skills add Bytexe/iterm2-to-ghostty -g

# or add it to just the current project
npx skills add Bytexe/iterm2-to-ghostty
```

Manage it later:

```bash
npx skills list                       # list installed skills
npx skills update iterm2-to-ghostty   # pull the latest from this repo
npx skills remove iterm2-to-ghostty   # uninstall
```

See the [`skills` docs](https://www.npmjs.com/package/skills) for more (other
sources, agent targeting, etc.).

## Usage

Drive it conversationally through Claude Code:

- *"migrate my iTerm2 config to Ghostty"*
- *"convert my 'Solarized Dark' iTerm profile to a ghostty config"*
- *"is the font in my ghostty config actually installed?"*

Claude lists your profiles, asks which to migrate if there's more than one,
converts the chosen profile, checks the font is installed, shows you a "what
changed" summary, and — if you already have a config — backs it up and asks before
writing. A running Ghostty reloads with ⌘+⇧+,.

## What's in the skill

| File | Purpose |
| --- | --- |
| `SKILL.md` | The migration workflow Claude follows |
| `scripts/iterm2_to_ghostty.py` | The converter the skill runs |
| `references/mapping.md` | The full iTerm2 → Ghostty key map and the reasoning behind each conversion |
| `examples/` | Sample iTerm2 plists and their converted Ghostty configs |

## Also works with cmux

cmux is a Ghostty-based terminal — its rendering layer is `libghostty` — so it
loads the **same Ghostty config** this skill produces. Nothing extra to set up:

- **Same file.** cmux reads Ghostty's config from the usual locations, in order:
  - `~/.config/ghostty/config`
  - `~/Library/Application Support/com.mitchellh.ghostty/config.ghostty`
- **Shared settings.** Everything this skill migrates — colors, font,
  transparency, cursor, palette, scrollback — applies to cmux and Ghostty alike.
- **Out of scope.** cmux-only features (vertical tabs, sidebar, notifications)
  live in `~/.config/cmux/cmux.json`; they aren't part of an iTerm2 profile.

## License

MIT — see [LICENSE](LICENSE).
