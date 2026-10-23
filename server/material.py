"""Material You colours for Android: a whole colour scheme grown from one seed colour.

Android 12+ builds its look from tonal palettes: one colour at many lightness levels. This
does the same in a simple way (HSL instead of Google's HCT colour space), then sets the
site's colour variables from it, for light and dark. No database, no drawing.
"""
import colorsys


def _hls(seed):
    seed = seed.lstrip("#")
    r, g, b = (int(seed[i:i + 2], 16) / 255 for i in (0, 2, 4))
    return colorsys.rgb_to_hls(r, g, b)


def _hex(h, light, sat):
    r, g, b = colorsys.hls_to_rgb(h % 1, light, sat)
    return "#%02X%02X%02X" % tuple(round(c * 255) for c in (r, g, b))


def is_neutral(seed):
    """A grey or black seed: a theme with no colour at all."""
    return _hls(seed)[2] < .05


def is_black(seed):
    return is_neutral(seed) and _hls(seed)[1] < .1


def palettes(seed):
    """The five tonal palettes of a scheme, each a function: lightness (0-1) -> colour."""
    h, _, s = _hls(seed)
    def p(hue, sat):
        return lambda light: _hex(hue, light, sat)
    if is_neutral(seed):
        grey = p(0, 0)
        return {k: grey for k in ("primary", "secondary", "tertiary", "accent", "neutral", "variant")}
    return {"primary": p(h, min(max(s, .45), .62)), "secondary": p(h, .2),
            "tertiary": p(h + 1 / 6, .38), "accent": p(h - 1 / 9, .3),
            "neutral": p(h, .07), "variant": p(h, .12)}


def scheme(seed, dark=False):
    """CSS custom properties for the site in this colour scheme: {"--name": "#RRGGBB"}."""
    P = palettes(seed)
    pr, se, te, ac, ne, nv = (P[k] for k in ("primary", "secondary", "tertiary", "accent", "neutral", "variant"))
    if is_neutral(seed):
        return _neutral(ne, dark, black=is_black(seed))
    if not dark:
        return {
            "--sage": ne(.955), "--dot": ne(.955), "--white": nv(.985), "--soft": ne(.935),
            "--line": nv(.86), "--input-line": nv(.74), "--hover-soft": ne(.915),
            "--peri-bg": pr(.92), "--peri": pr(.78), "--peri-dash": pr(.62), "--violet-bg": pr(.95),
            "--blue-bg": se(.91), "--blue": se(.78), "--blue-dash": se(.6),
            "--pink-bg": te(.92), "--pink": te(.83), "--peach-bg": ac(.92), "--mint-bg": se(.94),
            "--ink": ne(.1), "--ink-2": nv(.3), "--muted": nv(.38),
            "--chrome": ne(.9), "--chrome-hover": ne(.86), "--card-dark": pr(.3), "--on-ink": "#FFFFFF",
            "--btn-dark-hover": pr(.48), "--btn-soft-hover": te(.87),
            "--m-primary": pr(.42), "--m-on-primary": "#FFFFFF",
            "--m-primary-container": pr(.87), "--m-on-primary-container": pr(.14),
            "--m-secondary-container": se(.86), "--m-on-secondary-container": se(.14),
            "--m-on-chrome": nv(.3),
        }
    return {
        "--sage": ne(.065), "--dot": ne(.065), "--white": ne(.11), "--soft": ne(.15),
        "--line": nv(.24), "--input-line": nv(.32), "--hover-soft": ne(.18),
        "--peri-bg": pr(.22), "--peri": pr(.72), "--peri-dash": pr(.5), "--violet-bg": pr(.17),
        "--blue-bg": se(.19), "--blue": se(.68), "--blue-dash": se(.48),
        "--pink-bg": te(.2), "--pink": te(.72), "--peach-bg": ac(.19), "--mint-bg": se(.16),
        "--ink": ne(.92), "--ink-2": nv(.28), "--muted": nv(.72),
        "--chrome": ne(.14), "--chrome-hover": ne(.2), "--card-dark": pr(.26), "--on-ink": ne(.1),
        "--btn-dark-hover": pr(.84), "--btn-soft-hover": te(.28),
        "--m-primary": pr(.78), "--m-on-primary": pr(.14),
        "--m-primary-container": pr(.3), "--m-on-primary-container": pr(.9),
        "--m-secondary-container": se(.3), "--m-on-secondary-container": se(.9),
        "--m-on-chrome": nv(.78),
    }


def _neutral(grey, dark, black):
    """Grey and Black: the same tonal layout with no colour. Black uses black buttons in light
    mode and a true black background in dark mode (saves battery on OLED screens)."""
    if not dark:
        return {
            "--sage": grey(.96), "--dot": grey(.96), "--white": "#FFFFFF", "--soft": grey(.93),
            "--line": grey(.86), "--input-line": grey(.72), "--hover-soft": grey(.91),
            "--peri-bg": grey(.9), "--peri": grey(.62), "--peri-dash": grey(.5), "--violet-bg": grey(.94),
            "--blue-bg": grey(.92), "--blue": grey(.72), "--blue-dash": grey(.55),
            "--pink-bg": grey(.9), "--pink": grey(.78), "--peach-bg": grey(.91), "--mint-bg": grey(.93),
            "--ink": grey(.08), "--ink-2": grey(.28), "--muted": grey(.38),
            "--chrome": grey(.9), "--chrome-hover": grey(.85), "--card-dark": grey(.16 if black else .3),
            "--on-ink": "#FFFFFF", "--btn-dark-hover": grey(.25 if black else .45), "--btn-soft-hover": grey(.84),
            "--m-primary": grey(.06 if black else .36), "--m-on-primary": "#FFFFFF",
            "--m-primary-container": grey(.84), "--m-on-primary-container": grey(.1),
            "--m-secondary-container": grey(.84), "--m-on-secondary-container": grey(.1),
            "--m-on-chrome": grey(.3),
        }
    base = (lambda light: grey(light * .55)) if black else grey   # Black: surfaces near pure black
    return {
        "--sage": "#000000" if black else grey(.07), "--dot": "#000000" if black else grey(.07),
        "--white": base(.11), "--soft": base(.15), "--line": grey(.22), "--input-line": grey(.3),
        "--hover-soft": base(.18),
        "--peri-bg": base(.2), "--peri": grey(.75), "--peri-dash": grey(.5), "--violet-bg": base(.15),
        "--blue-bg": base(.17), "--blue": grey(.68), "--blue-dash": grey(.48),
        "--pink-bg": base(.19), "--pink": grey(.72), "--peach-bg": base(.18), "--mint-bg": base(.16),
        "--ink": grey(.93), "--ink-2": grey(.28), "--muted": grey(.7),
        "--chrome": base(.15), "--chrome-hover": base(.22), "--card-dark": base(.24), "--on-ink": grey(.08),
        "--btn-dark-hover": grey(.85), "--btn-soft-hover": grey(.28),
        "--m-primary": grey(.94 if black else .8), "--m-on-primary": grey(.08),
        "--m-primary-container": grey(.28), "--m-on-primary-container": grey(.92),
        "--m-secondary-container": grey(.3), "--m-on-secondary-container": grey(.92),
        "--m-on-chrome": grey(.78),
    }


def css_vars(seed, dark=False):
    return " ".join(f"{k}: {v};" for k, v in scheme(seed, dark).items())


def swatch(seed):
    """The three colours Android shows on a colour choice: (primary, secondary, tertiary)."""
    if is_black(seed):
        return "#111111", "#5A5A5A", "#9A9A9A"
    P = palettes(seed)
    if is_neutral(seed):
        return P["primary"](.42), P["primary"](.86), P["primary"](.66)
    return P["primary"](.62), P["secondary"](.82), P["tertiary"](.72)
