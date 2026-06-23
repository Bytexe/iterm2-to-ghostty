# Migrating iTerm2 to Ghostty (and cmux)

A Claude Code skill for moving an iTerm2 profile to a [Ghostty](https://github.com/ghostty-org/ghostty) (and [cmux](https://cmux.com)) *correctly* —
colors, font, transparency, cursor, window size, scrollback, and the Option key.
You install it, then ask Claude Code to migrate your setup; it does the
conversion, checks your font, and shows you what changed.

It's just as suitable for cmux: cmux is built on Ghostty
and reads the same config file, so the config this skill generates drives cmux
too — no extra steps.

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

## Install

Installed with [`skills`](https://www.npmjs.com/package/skills) — the open
agent-skills CLI (requires Node ≥ 18). `SKILL.md` is at the repo root, so the
repo installs directly from GitHub:

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

## Requirements

- macOS
- Python 3.8+ (standard library only — nothing to `pip install`)
- The font-installed check uses `fc-list` or `system_profiler` (already on macOS)

## Also works with cmux

[cmux](https://github.com/manaflow-ai/cmux) is a Ghostty-based terminal
(`libghostty`) that reads the **same Ghostty config files** — `~/.config/ghostty/config`,
then `~/Library/Application Support/com.mitchellh.ghostty/config.ghostty`. So the
config this skill generates drives cmux too, with no extra work. cmux-only
features (vertical tabs, sidebar, notifications) live separately in
`~/.config/cmux/cmux.json` and aren't part of an iTerm2 profile, so they're out
of scope here.

## License

MIT — see [LICENSE](LICENSE).
