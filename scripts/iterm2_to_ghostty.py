#!/usr/bin/env python3
"""Convert an iTerm2 profile into a Ghostty config file.

Reads an iTerm2 preferences plist (default:
~/Library/Preferences/com.googlecode.iterm2.plist), picks one profile
(default: the profile referenced by "Default Bookmark Guid"), and emits an
equivalent Ghostty config to stdout. Every emitted line carries a short
comment recording the iTerm2 key it came from, so a human (or Claude) can
verify the migration and spot the handful of settings that don't translate
cleanly.

The core conversion is stdlib-only (plistlib) so it runs anywhere Python 3
does. The ONE live-system touch is an optional font-installation check
(`--check-font`, and the verdict embedded in `--report`): it shells out to
`fc-list` or macOS `system_profiler` to confirm the chosen family is actually
installed, because a missing font makes Ghostty silently fall back to its
default. It degrades gracefully (reports "unknown") when those tools or OS
aren't available. `ghostty +validate-config` is still left to the caller.

Usage:
    python iterm2_to_ghostty.py                      # default plist, default profile -> stdout
    python iterm2_to_ghostty.py --plist FILE         # explicit plist
    python iterm2_to_ghostty.py --profile "Default"  # pick profile by Name
    python iterm2_to_ghostty.py --list-profiles      # show profiles and exit
    python iterm2_to_ghostty.py --report             # human-readable "what changed" + font check
    python iterm2_to_ghostty.py --check-font "Menlo"  # is this family installed? (exit 0/1/2)
"""

import argparse
import os
import plistlib
import shutil
import subprocess
import sys

DEFAULT_PLIST = os.path.expanduser(
    "~/Library/Preferences/com.googlecode.iterm2.plist"
)

# Trailing tokens in an iTerm2 font name that describe weight/slant, not the
# family. We strip these to guess the Ghostty `font-family` value, but the
# guess is best-effort: PostScript names lose the spaces a family name has
# (e.g. "FiraCode-Retina" -> family "Fira Code"), so the skill verifies the
# result against the installed-font list.
_FONT_STYLE_WORDS = {
    "regular", "normal", "book", "roman", "text",
    "thin", "extralight", "ultralight", "light", "demilight",
    "medium", "demibold", "semibold", "bold", "extrabold", "ultrabold",
    "black", "heavy",
    "italic", "oblique", "slanted",
    "condensed", "semicondensed", "narrow", "expanded", "wide",
    "retina", "mono", "nerdfont", "nf",  # 'mono'/'nf' only stripped if not the whole name
}
# Words we must never strip even though they look like style words, because
# they are load-bearing parts of common family names.
_FONT_KEEP = {"mono", "nf"}


def color_to_hex(c):
    """An iTerm2 color dict -> '#rrggbb'. Components are 0..1 floats."""
    if not isinstance(c, dict):
        return None
    if "Red Component" not in c:
        return None
    r = round(c.get("Red Component", 0.0) * 255)
    g = round(c.get("Green Component", 0.0) * 255)
    b = round(c.get("Blue Component", 0.0) * 255)
    clamp = lambda v: max(0, min(255, v))
    return "#{:02x}{:02x}{:02x}".format(clamp(r), clamp(g), clamp(b))


def font_family_from_iterm(raw):
    """'MesloLGS-NF-Regular 16' -> ('MesloLGS NF', 16.0).

    Returns (family, size). size is None if not present. family is a
    best-effort guess; the skill must confirm it resolves to an installed
    font.
    """
    raw = raw.strip()
    size = None
    # iTerm stores "<PostScriptName> <size>"; size is the last token if numeric.
    if " " in raw:
        head, tail = raw.rsplit(" ", 1)
        try:
            size = float(tail)
            raw = head
        except ValueError:
            pass
    tokens = raw.replace("-", " ").replace("_", " ").split()
    # Strip trailing style descriptors, but never strip the last surviving
    # token and never strip a "keep" word that anchors the family.
    while len(tokens) > 1 and tokens[-1].lower() in _FONT_STYLE_WORDS \
            and tokens[-1].lower() not in _FONT_KEEP:
        tokens.pop()
    family = " ".join(tokens)
    if size is not None and size == int(size):
        size = int(size)
    return family, size


def font_is_installed(family):
    """True/False if we can determine whether `family` is installed, else None.

    Tries `fc-list` first (fast, if fontconfig is present), then macOS
    `system_profiler SPFontsDataType` (always present on macOS but slower).
    Returns None when neither tool is usable so callers can say "unverified"
    instead of crying wolf."""
    fam = (family or "").strip().lower()
    if not fam:
        return None

    fc = shutil.which("fc-list")
    if fc:
        try:
            out = subprocess.run([fc, ":", "family"], capture_output=True,
                                 text=True, timeout=10)
            if out.returncode == 0:
                families = set()
                for line in out.stdout.splitlines():
                    for part in line.split(","):  # localized names are comma-joined
                        families.add(part.strip().lower())
                return fam in families
        except (subprocess.SubprocessError, OSError):
            pass

    sp = shutil.which("system_profiler")
    if sp:
        try:
            out = subprocess.run([sp, "SPFontsDataType"], capture_output=True,
                                 text=True, timeout=60)
            if out.returncode == 0:
                for line in out.stdout.splitlines():
                    s = line.strip()
                    if s.lower().startswith("family:") and \
                            s.split(":", 1)[1].strip().lower() == fam:
                        return True
                return False
        except (subprocess.SubprocessError, OSError):
            pass

    return None


def list_profiles(prefs):
    """[(name, is_default), ...] in plist order."""
    default_guid = prefs.get("Default Bookmark Guid")
    return [(bm.get("Name"), bm.get("Guid") == default_guid)
            for bm in prefs.get("New Bookmarks", [])]


def load_profile(plist_path, profile_name=None):
    with open(plist_path, "rb") as f:
        prefs = plistlib.load(f)
    bookmarks = prefs.get("New Bookmarks") or []
    if not bookmarks:
        raise SystemExit("No profiles ('New Bookmarks') found in plist.")
    if profile_name is not None:
        for bm in bookmarks:
            if bm.get("Name") == profile_name:
                return prefs, bm
        names = ", ".join(repr(bm.get("Name")) for bm in bookmarks)
        raise SystemExit(
            f"No profile named {profile_name!r}. Available: {names}"
        )
    default_guid = prefs.get("Default Bookmark Guid")
    if default_guid:
        for bm in bookmarks:
            if bm.get("Guid") == default_guid:
                return prefs, bm
    # Fall back to the single / first profile.
    return prefs, bookmarks[0]


def option_as_alt(prefs, profile):
    """Map iTerm option-key behaviour to Ghostty `macos-option-as-alt`.

    iTerm: 0 = Normal (compose chars), 1 = Meta, 2 = Esc+. Both Meta and
    Esc+ mean "act as a modifier", which is what Ghostty's option-as-alt
    does. Profile-level keys win; the top-level Left/RightOption are the
    fallback for profiles left on "Normal".
    """
    def acts_as_alt(profile_key, global_key):
        v = profile.get(profile_key)
        g = prefs.get(global_key)
        return (v in (1, 2)) or (g in (1, 2))

    left = acts_as_alt("Option Key Sends", "LeftOption")
    right = acts_as_alt("Right Option Key Sends", "RightOption")
    if left and right:
        return "true"
    if left:
        return "left"
    if right:
        return "right"
    return None  # both Normal -> leave Ghostty default (false)


# iTerm2 "Ansi N Color" -> Ghostty `palette = N=...`
_ANSI_KEYS = [(i, f"Ansi {i} Color") for i in range(16)]

# Simple iTerm color key -> Ghostty key.
_COLOR_MAP = [
    ("Background Color", "background"),
    ("Foreground Color", "foreground"),
    ("Cursor Color", "cursor-color"),
    ("Cursor Text Color", "cursor-text"),
    ("Selection Color", "selection-background"),
    ("Selected Text Color", "selection-foreground"),
]

# iTerm "Cursor Type": 0 underline, 1 vertical bar, 2 box.
_CURSOR_STYLE = {0: "underline", 1: "bar", 2: "block"}


def build_config(prefs, profile):
    out = []
    notes = []  # settings that don't translate cleanly

    name = profile.get("Name", "?")
    out.append(f'# Migrated from iTerm2 profile "{name}"')
    out.append(f"# Source: {prefs.get('iTerm Version', 'iTerm2')} preferences plist")
    out.append("")

    # --- Font ---
    normal_font = profile.get("Normal Font")
    if normal_font:
        family, size = font_family_from_iterm(normal_font)
        out.append("# --- Font ---")
        out.append(f'# iTerm2: Normal Font = "{normal_font}"  (verify family resolves to an installed font)')
        out.append(f'font-family = "{family}"')
        if size is not None:
            out.append(f"font-size = {size}")
    # Non-ASCII font becomes an additional fallback family, only if enabled.
    if profile.get("Use Non-ASCII Font") and profile.get("Non Ascii Font"):
        nfam, _ = font_family_from_iterm(profile["Non Ascii Font"])
        out.append(f'# iTerm2: Non Ascii Font = "{profile["Non Ascii Font"]}" (fallback)')
        out.append(f'font-family = "{nfam}"')
    if profile.get("Use Bright Bold") or profile.get("Brighten Bold Text"):
        out.append("# iTerm2: Use Bright Bold = true")
        out.append("bold-is-bright = true")
    out.append("")

    # --- Window / cell ---
    cols, rows = profile.get("Columns"), profile.get("Rows")
    if cols or rows:
        out.append("# --- Window ---")
        if cols:
            out.append(f"# iTerm2: Columns = {cols}")
            out.append(f"window-width = {cols}")
        if rows:
            out.append(f"# iTerm2: Rows = {rows}")
            out.append(f"window-height = {rows}")
        out.append("")

    # iTerm spacing multipliers (1.0 == normal) -> Ghostty percentage deltas.
    hspace = profile.get("Horizontal Spacing")
    vspace = profile.get("Vertical Spacing")
    spacing_lines = []
    if isinstance(hspace, (int, float)) and abs(hspace - 1.0) > 1e-6:
        spacing_lines.append(f"adjust-cell-width = {round((hspace - 1.0) * 100)}%")
    if isinstance(vspace, (int, float)) and abs(vspace - 1.0) > 1e-6:
        spacing_lines.append(f"adjust-cell-height = {round((vspace - 1.0) * 100)}%")
    if spacing_lines:
        out.append("# --- Cell spacing (iTerm Horizontal/Vertical Spacing) ---")
        out.extend(spacing_lines)
        out.append("")

    # --- Background transparency & blur ---
    transparency = profile.get("Transparency")
    blur = profile.get("Blur")
    bg_lines = []
    if isinstance(transparency, (int, float)) and transparency > 0:
        opacity = round(1.0 - transparency, 3)
        bg_lines.append(f"# iTerm2: Transparency = {round(transparency, 4)} -> opacity = 1 - that")
        bg_lines.append(f"background-opacity = {opacity}")
    if blur:
        # iTerm and Ghostty blur radii use different scales; `true` maps to
        # Ghostty's sensible default rather than copying the raw number.
        radius = profile.get("Blur Radius")
        rnote = f" (iTerm Blur Radius ~{round(radius, 1)})" if isinstance(radius, (int, float)) else ""
        bg_lines.append(f"# iTerm2: Blur = true{rnote}")
        bg_lines.append("background-blur = true")
    if bg_lines:
        out.append("# --- Background transparency & blur ---")
        out.extend(bg_lines)
        out.append("")

    # --- Cursor ---
    cursor_lines = []
    if "Blinking Cursor" in profile:
        cursor_lines.append(f"cursor-style-blink = {str(bool(profile['Blinking Cursor'])).lower()}")
    ctype = profile.get("Cursor Type")
    if ctype in _CURSOR_STYLE:
        cursor_lines.append(f"cursor-style = {_CURSOR_STYLE[ctype]}")
    if cursor_lines:
        out.append("# --- Cursor ---")
        out.extend(cursor_lines)
        out.append("")

    # --- Scrollback ---
    if profile.get("Unlimited Scrollback"):
        out.append("# --- Scrollback ---")
        out.append("# iTerm2: Unlimited Scrollback = true")
        out.append("# Ghostty caps scrollback in BYTES (0 would DISABLE it); 100MB ~= unlimited.")
        out.append("scrollback-limit = 100000000")
        out.append("")
    elif profile.get("Scrollback Lines"):
        notes.append(
            f"Scrollback Lines = {profile['Scrollback Lines']} (iTerm counts lines; "
            "Ghostty's scrollback-limit is in bytes -- left at default)"
        )

    # --- Keyboard ---
    oaa = option_as_alt(prefs, profile)
    if oaa:
        out.append("# --- Keyboard ---")
        out.append("# iTerm2: Left/Right Option sends Esc+/Meta")
        out.append(f"macos-option-as-alt = {oaa}")
        out.append("")

    # --- Colors ---
    color_lines = []
    for ikey, gkey in _COLOR_MAP:
        hexv = color_to_hex(profile.get(ikey))
        if hexv:
            color_lines.append(f"{gkey} = {hexv}")
    palette_lines = []
    for idx, ikey in _ANSI_KEYS:
        hexv = color_to_hex(profile.get(ikey))
        if hexv:
            palette_lines.append(f"palette = {idx}={hexv}")
    if color_lines or palette_lines:
        out.append("# --- Colors (from iTerm2 profile) ---")
        out.extend(color_lines)
        if palette_lines:
            out.append("# ANSI palette (iTerm2 'Ansi N Color')")
            out.extend(palette_lines)
        out.append("")

    # Settings with no clean Ghostty equivalent.
    mc = profile.get("Minimum Contrast")
    if isinstance(mc, (int, float)) and mc > 0:
        notes.append(
            f"Minimum Contrast = {round(mc, 3)} (iTerm uses 0..1; Ghostty's "
            "minimum-contrast is a 1..21 ratio -- no clean conversion, skipped)"
        )

    if notes:
        out.append("# --- Not migrated (no clean Ghostty equivalent) ---")
        for n in notes:
            out.append(f"# - {n}")
        out.append("")

    # Drop trailing blank line.
    while out and out[-1] == "":
        out.pop()
    return "\n".join(out) + "\n"


def build_report(prefs, profile, font_status=None):
    """A short, human-readable 'what changed' summary for the user.

    font_status: True/False/None from font_is_installed() for the chosen family,
    surfaced inline so the user is warned when the font would silently fall back.

    The config file (build_config) is the full source of truth; this is the
    curated highlight reel so a person can see the notable conversions at a
    glance — especially the surprising ones (transparency inverts to opacity,
    'unlimited' scrollback becomes a byte cap, a PostScript font name becomes a
    family name)."""
    name = profile.get("Name", "?")
    rows = []   # (setting, iTerm2, Ghostty)
    notes = []  # not migrated

    nf = profile.get("Normal Font")
    fam = None
    if nf:
        fam, size = font_family_from_iterm(nf)
        to = fam + (f", size {size}" if size is not None else "")
        if font_status is True:
            to += "  [installed]"
        elif font_status is False:
            to += "  [NOT INSTALLED -> Ghostty falls back to its default]"
        elif fam.lower() not in nf.lower().replace("-", " "):
            to += "  (verify this family is installed)"
        rows.append(("Font", nf, to))

    bg = color_to_hex(profile.get("Background Color"))
    fg = color_to_hex(profile.get("Foreground Color"))
    n_palette = sum(1 for i in range(16) if color_to_hex(profile.get(f"Ansi {i} Color")))
    if bg or fg or n_palette:
        rows.append(("Colors",
                     "theme colors + ANSI palette",
                     f"background {bg}, foreground {fg}, + {n_palette}/16 palette colors"))

    t = profile.get("Transparency")
    if isinstance(t, (int, float)) and t > 0:
        rows.append(("Transparency", f"{round(t, 3)} (0=opaque)",
                     f"background-opacity = {round(1 - t, 3)}  (note: inverted)"))
    if profile.get("Blur"):
        rows.append(("Background blur", "on", "background-blur = true"))

    c, r = profile.get("Columns"), profile.get("Rows")
    if c or r:
        rows.append(("Window size", f"{c} cols x {r} rows",
                     f"window-width = {c}, window-height = {r}"))

    hspace, vspace = profile.get("Horizontal Spacing"), profile.get("Vertical Spacing")
    for label, val, key in (("Cell width", hspace, "adjust-cell-width"),
                            ("Cell height", vspace, "adjust-cell-height")):
        if isinstance(val, (int, float)) and abs(val - 1.0) > 1e-6:
            rows.append((label, f"x{val}", f"{key} = {round((val - 1.0) * 100)}%"))

    if "Blinking Cursor" in profile:
        rows.append(("Cursor blink", "on" if profile["Blinking Cursor"] else "off",
                     f"cursor-style-blink = {str(bool(profile['Blinking Cursor'])).lower()}"))
    ct = profile.get("Cursor Type")
    if ct in _CURSOR_STYLE:
        rows.append(("Cursor shape", {0: "underline", 1: "bar", 2: "box"}[ct],
                     f"cursor-style = {_CURSOR_STYLE[ct]}"))

    if profile.get("Unlimited Scrollback"):
        rows.append(("Scrollback", "unlimited (line-based)",
                     "scrollback-limit = 100000000 bytes (~100MB; Ghostty has no 'unlimited', and 0 would disable it)"))

    oaa = option_as_alt(prefs, profile)
    if oaa:
        rows.append(("Option key", "sends Esc+/Meta", f"macos-option-as-alt = {oaa}"))
    if profile.get("Use Bright Bold") or profile.get("Brighten Bold Text"):
        rows.append(("Bold text", "use bright color variant", "bold-is-bright = true"))

    mc = profile.get("Minimum Contrast")
    if isinstance(mc, (int, float)) and mc > 0:
        notes.append(f"Minimum Contrast ({round(mc, 3)}) — Ghostty's minimum-contrast uses a different 1..21 scale")
    if profile.get("Scrollback Lines") and not profile.get("Unlimited Scrollback"):
        notes.append(f"Scrollback Lines ({profile['Scrollback Lines']}) — Ghostty caps scrollback by bytes, not lines, so it's left at default")
    for k, desc in (("Background Image Location", "Background image"),
                    ("Badge Color", "Badge"),
                    ("Cursor Guide Color", "Cursor guide")):
        v = profile.get(k)
        if v and not (isinstance(v, str) and v == ""):
            notes.append(f"{desc} — no Ghostty equivalent")

    w = max((len(s) for s, _, _ in rows), default=7)
    out = [f'# What changed: iTerm2 "{name}" -> Ghostty', "",
           "## Migrated", ""]
    out.append(f"| {'Setting'.ljust(w)} | iTerm2 | Ghostty |")
    out.append(f"| {'-' * w} | --- | --- |")
    for s, frm, to in rows:
        out.append(f"| {s.ljust(w)} | {frm} | {to} |")
    if notes:
        out += ["", "## Not migrated (no clean Ghostty equivalent)", ""]
        out += [f"- {n}" for n in notes]
    out += ["", "## Before it takes effect"]
    if font_status is False:
        out.append(f"- WARNING: the font '{fam}' is NOT installed. Install it, or "
                   "change font-family, or Ghostty will silently use its default font.")
    elif font_status is True:
        out.append(f"- The font '{fam}' is installed and will be used.")
    else:
        out.append("- Confirm the font family above is installed (otherwise Ghostty silently uses its default).")
    out.append("- A running Ghostty reloads the config with Cmd+Shift+,.")
    return "\n".join(out) + "\n"


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--plist", default=DEFAULT_PLIST,
                   help="Path to the iTerm2 plist (default: %(default)s)")
    p.add_argument("--profile", default=None,
                   help="Profile Name to convert")
    p.add_argument("--default", action="store_true",
                   help="Convert the iTerm2 default profile (use when the user "
                        "has explicitly asked for their current/default profile)")
    p.add_argument("--list-profiles", action="store_true",
                   help="List profile names in the plist and exit")
    p.add_argument("--report", action="store_true",
                   help="Print a human-readable 'what changed' summary instead "
                        "of the config file (show this to the user)")
    p.add_argument("--check-font", metavar="FAMILY", default=None,
                   help="Check whether a font family is installed and exit "
                        "(0 installed, 1 missing, 2 could not determine)")
    args = p.parse_args(argv)

    if args.check_font is not None:
        status = font_is_installed(args.check_font)
        if status is True:
            print(f"OK: font '{args.check_font}' is installed.")
            return 0
        if status is False:
            print(f"MISSING: font '{args.check_font}' is NOT installed. Ghostty "
                  "would fall back to its default — install it or pick another "
                  "font-family.")
            return 1
        print(f"UNKNOWN: could not verify '{args.check_font}' (no fc-list or "
              "system_profiler available). Please confirm manually.")
        return 2

    if not os.path.exists(args.plist):
        raise SystemExit(f"Plist not found: {args.plist}")

    with open(args.plist, "rb") as f:
        prefs = plistlib.load(f)
    profiles = list_profiles(prefs)

    if args.list_profiles:
        for name, is_default in profiles:
            print(f"{name!r}{' (default)' if is_default else ''}")
        return 0

    # Don't silently pick for the user when the choice is ambiguous: more than
    # one profile and no explicit selection. Surface the list and stop so the
    # caller asks the user which profile to migrate.
    if len(profiles) > 1 and not args.profile and not args.default:
        sys.stderr.write(
            "Multiple iTerm2 profiles found. Ask the user which one to migrate, "
            "then re-run with --profile \"<Name>\" (or --default for the iTerm2 "
            "default profile):\n"
        )
        for name, is_default in profiles:
            sys.stderr.write(f"  - {name}{' (default)' if is_default else ''}\n")
        return 2

    _, profile = load_profile(args.plist, args.profile)
    if args.report:
        nf = profile.get("Normal Font")
        font_status = None
        if nf:
            fam, _ = font_family_from_iterm(nf)
            font_status = font_is_installed(fam)
        sys.stdout.write(build_report(prefs, profile, font_status=font_status))
    else:
        sys.stdout.write(build_config(prefs, profile))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
