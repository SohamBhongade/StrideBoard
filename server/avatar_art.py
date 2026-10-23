"""Draws a StrideBoard avatar: a small round walker with feet, built from parts.

Pure drawing, no database. render(build, size) returns an <svg> for a build such as
{"color": "color_mint", "eyes": "eyes_dots", "mouth": "mouth_smile", "hat": "hat_cap",
 "extra": "extra_none", "shoes": "shoes_sneakers", "bg": "bg_sage"}.
The character and every part are original drawings for StrideBoard.
"""
import itertools

from markupsafe import Markup

INK = "#17181C"
_ids = itertools.count(1)   # unique ids for gradients when several avatars share a page

# body colour -> (main, shade)
COLORS = {
    "color_mint": ("#9EDCC6", "#7CC7AD"), "color_sky": ("#A9CCF2", "#86B3E3"),
    "color_peach": ("#F7C2A1", "#EDA581"), "color_lilac": ("#C9B8F2", "#AE99E6"),
    "color_sunny": ("#F7DB6F", "#EBC54A"), "color_coral": ("#F49A8F", "#E5786B"),
    "color_berry": ("#D97BB0", "#C25E97"), "color_ocean": ("#5FA8C7", "#468FAF"),
    "color_midnight": ("#4A4F7A", "#363A5E"), "color_gold": ("#E8C15A", "#C99B2E"),
}


def _bg(key, uid):
    if key == "bg_sage":
        return '<rect width="100" height="100" fill="#C9DCCC"/>'
    if key == "bg_sky":
        return '<rect width="100" height="100" fill="#CFE6F5"/><circle cx="20" cy="22" r="9" fill="#fff" opacity=".8"/><circle cx="28" cy="20" r="7" fill="#fff" opacity=".8"/>'
    if key == "bg_track":
        return ('<rect width="100" height="100" fill="#D9805F"/>'
                '<path d="M0 74h100M0 88h100M0 60h100" stroke="#fff" stroke-width="2" opacity=".85"/>')
    if key == "bg_sunrise":
        return (f'<defs><linearGradient id="sr{uid}" x1="0" y1="0" x2="0" y2="1">'
                '<stop offset="0" stop-color="#FFB38A"/><stop offset="1" stop-color="#FFE7A8"/></linearGradient></defs>'
                f'<rect width="100" height="100" fill="url(#sr{uid})"/>'
                '<circle cx="50" cy="96" r="22" fill="#FFF3C4" opacity=".9"/>')
    if key == "bg_stars":
        dots = "".join(f'<circle cx="{x}" cy="{y}" r="{r}" fill="#fff"/>'
                       for x, y, r in ((14, 18, 1.4), (84, 14, 1.8), (22, 70, 1.2), (88, 60, 1.4), (70, 30, 1), (10, 44, 1)))
        return f'<rect width="100" height="100" fill="#2B2F55"/>{dots}'
    return '<rect width="100" height="100" fill="#F1F2F4"/>'


# shoes -> (shoe colour, stripe colour, or a list of colours for several thin stripes)
SHOES = {
    "shoes_sneakers": ("#FFFFFF", "#E5786B"), "shoes_runners": ("#E5574B", "#FFFFFF"),
    "shoes_sky": ("#8EC3F2", "#FFFFFF"), "shoes_neon": ("#C8F25A", INK),
    "shoes_pink": ("#F7A8CF", "#FFFFFF"), "shoes_court": ("#FFFFFF", "#3FA66B"),
    "shoes_black": ("#2A2B33", "#FFFFFF"), "shoes_gold": ("#E8C15A", "#FFFFFF"),
    "shoes_rainbow": ("#FFFFFF", ["#E5574B", "#F2C94C", "#4C8FE5"]),
}


def _feet(key, shade):
    shoe, stripe_colour = SHOES.get(key, (shade, None))
    if isinstance(stripe_colour, list):
        stripe = "".join(f'<path d="M34 {y}h8M54 {y}h8" stroke="{c}" stroke-width="1.2" stroke-linecap="round"/>'
                         for y, c in zip((83.8, 85.4, 87), stripe_colour))
    elif stripe_colour:
        stripe = f'<path d="M33 85h10M53 85h10" stroke="{stripe_colour}" stroke-width="1.6" stroke-linecap="round"/>'
    else:
        stripe = ""
    return (f'<ellipse cx="39" cy="86" rx="9" ry="5" fill="{shoe}" stroke="{INK}" stroke-width="1.4"/>'
            f'<ellipse cx="61" cy="86" rx="9" ry="5" fill="{shoe}" stroke="{INK}" stroke-width="1.4"/>{stripe}')


def _eyes(key):
    if key == "eyes_happy":
        return f'<path d="M37 51q4-6 8 0M55 51q4-6 8 0" stroke="{INK}" stroke-width="2.4" fill="none" stroke-linecap="round"/>'
    if key == "eyes_big":
        return (f'<circle cx="41" cy="49" r="5.5" fill="#fff" stroke="{INK}" stroke-width="1.2"/>'
                f'<circle cx="59" cy="49" r="5.5" fill="#fff" stroke="{INK}" stroke-width="1.2"/>'
                f'<circle cx="42" cy="50" r="2.8" fill="{INK}"/><circle cx="60" cy="50" r="2.8" fill="{INK}"/>')
    if key == "eyes_sleepy":
        return f'<path d="M36 50q5 4 10 0M54 50q5 4 10 0" stroke="{INK}" stroke-width="2.4" fill="none" stroke-linecap="round"/>'
    if key == "eyes_wink":
        return (f'<circle cx="41" cy="49" r="3.4" fill="{INK}"/><circle cx="42.2" cy="47.8" r="1" fill="#fff"/>'
                f'<path d="M55 50q4-5 8 0" stroke="{INK}" stroke-width="2.4" fill="none" stroke-linecap="round"/>')
    if key == "eyes_stars":
        star = "M0 -5 1.5 -1.5 5 -1.5 2.2 .8 3.2 4.6 0 2.3 -3.2 4.6 -2.2 .8 -5 -1.5 -1.5 -1.5z"
        return (f'<path transform="translate(41 49)" d="{star}" fill="{INK}"/>'
                f'<path transform="translate(59 49)" d="{star}" fill="{INK}"/>')
    return (f'<circle cx="41" cy="49" r="3.4" fill="{INK}"/><circle cx="59" cy="49" r="3.4" fill="{INK}"/>'
            '<circle cx="42.2" cy="47.8" r="1" fill="#fff"/><circle cx="60.2" cy="47.8" r="1" fill="#fff"/>')


def _mouth(key):
    if key == "mouth_o":
        return f'<ellipse cx="50" cy="63" rx="3" ry="3.6" fill="{INK}"/>'
    if key == "mouth_grin":
        return f'<path d="M42.5 59.5h15q-1 9-7.5 9t-7.5-9z" fill="{INK}"/><path d="M45 64.5q5 3 10 0" stroke="#F49A8F" stroke-width="2.2" fill="none" stroke-linecap="round"/>'
    if key == "mouth_smirk":
        return f'<path d="M44 63q6 3 12-3" stroke="{INK}" stroke-width="2.4" fill="none" stroke-linecap="round"/>'
    if key == "mouth_tongue":
        return (f'<path d="M43 60q7 7 14 0" stroke="{INK}" stroke-width="2.4" fill="none" stroke-linecap="round"/>'
                f'<path d="M48 63.5h5v2.5a2.5 2.5 0 0 1-5 0z" fill="#F07C8A" stroke="{INK}" stroke-width="1"/>')
    return f'<path d="M43 60q7 7 14 0" stroke="{INK}" stroke-width="2.4" fill="none" stroke-linecap="round"/>'


def _extra(key):
    if key == "extra_glasses":
        return (f'<g fill="none" stroke="{INK}" stroke-width="1.8"><circle cx="41" cy="49" r="7"/>'
                '<circle cx="59" cy="49" r="7"/><path d="M48 49h4M34 48l-8-2M66 48l8-2"/></g>')
    if key == "extra_shades":
        return (f'<path d="M32 44h16v5a6 6 0 0 1-6 6h-4a6 6 0 0 1-6-6zM52 44h16v5a6 6 0 0 1-6 6h-4a6 6 0 0 1-6-6z" fill="{INK}"/>'
                f'<path d="M48 46h4M32 45l-6-2M68 45l6-2" stroke="{INK}" stroke-width="1.8"/>'
                '<path d="M35 47l4-2M55 47l4-2" stroke="#fff" stroke-width="1.2" opacity=".7"/>')
    if key == "extra_scarf":
        return (f'<path d="M25 70q25 10 50 0v7q-25 10-50 0z" fill="#E5786B" stroke="{INK}" stroke-width="1.3"/>'
                f'<path d="M62 76l4 12h-7l-2-11z" fill="#E5786B" stroke="{INK}" stroke-width="1.3"/>')
    if key == "extra_whistle":
        return (f'<path d="M36 66q14 12 28 0" stroke="#E5786B" stroke-width="1.6" fill="none"/>'
                f'<rect x="46" y="70" width="10" height="5.5" rx="2.5" fill="#B9C0C9" stroke="{INK}" stroke-width="1.2"/>')
    if key == "extra_medal":
        return (f'<path d="M42 64l8 12 8-12" stroke="#5FA8C7" stroke-width="3.4" fill="none"/>'
                f'<circle cx="50" cy="78" r="5.5" fill="#E8C15A" stroke="{INK}" stroke-width="1.3"/>'
                f'<path d="M50 75.5v5" stroke="{INK}" stroke-width="1.2"/>')
    return ""


def _hat(key):
    if key == "hat_headband":
        return (f'<path d="M24 38q26-9 52 0v6q-26-9-52 0z" fill="#E5786B" stroke="{INK}" stroke-width="1.3"/>'
                '<path d="M30 40l40-2" stroke="#fff" stroke-width="1.2" opacity=".8"/>')
    if key == "hat_cap":
        return (f'<path d="M26 39q24-30 48 0z" fill="#5FA8C7" stroke="{INK}" stroke-width="1.4"/>'
                f'<path d="M58 38h22q1 5-5 5H58z" fill="#468FAF" stroke="{INK}" stroke-width="1.4"/>'
                f'<circle cx="50" cy="24" r="2" fill="{INK}"/>')
    if key == "hat_beanie":
        return (f'<path d="M25 40q25-34 50 0z" fill="#D97BB0" stroke="{INK}" stroke-width="1.4"/>'
                f'<rect x="23" y="35" width="54" height="8" rx="4" fill="#C25E97" stroke="{INK}" stroke-width="1.4"/>'
                f'<circle cx="50" cy="18" r="5" fill="#fff" stroke="{INK}" stroke-width="1.4"/>')
    if key == "hat_flower":
        petals = "".join(f'<circle cx="{68 + dx}" cy="{30 + dy}" r="4.2" fill="#F7C2DA" stroke="{INK}" stroke-width="1"/>'
                         for dx, dy in ((0, -5), (5, -1), (3, 5), (-3, 5), (-5, -1)))
        return petals + f'<circle cx="68" cy="30" r="3" fill="#F7DB6F" stroke="{INK}" stroke-width="1"/>'
    if key == "hat_party":
        return (f'<path d="M50 4l13 30H37z" fill="#A9CCF2" stroke="{INK}" stroke-width="1.4"/>'
                '<path d="M45 16l9 4M42 25l13 5" stroke="#E5786B" stroke-width="2.2"/>'
                f'<circle cx="50" cy="5" r="3.5" fill="#F7DB6F" stroke="{INK}" stroke-width="1.2"/>')
    if key == "hat_headphones":
        return (f'<path d="M24 54q0-38 26-38t26 38" stroke="{INK}" stroke-width="3.4" fill="none"/>'
                f'<rect x="17" y="46" width="11" height="16" rx="5" fill="#E5786B" stroke="{INK}" stroke-width="1.4"/>'
                f'<rect x="72" y="46" width="11" height="16" rx="5" fill="#E5786B" stroke="{INK}" stroke-width="1.4"/>')
    if key == "hat_crown":
        return (f'<path d="M33 34l2-17 8 8 7-12 7 12 8-8 2 17z" fill="#E8C15A" stroke="{INK}" stroke-width="1.4" stroke-linejoin="round"/>'
                '<circle cx="50" cy="27" r="2.2" fill="#E5786B"/><circle cx="40" cy="29" r="1.6" fill="#5FA8C7"/>'
                '<circle cx="60" cy="29" r="1.6" fill="#5FA8C7"/>')
    return ""


def _parts(build, uid):
    """Everything inside the <svg>: background, feet, body, face, extras, headwear."""
    main, shade = COLORS.get(build.get("color"), COLORS["color_mint"])
    return (
        f'{_bg(build.get("bg"), uid)}'
        f'{_feet(build.get("shoes"), shade)}'
        f'<ellipse cx="50" cy="56" rx="27" ry="29" fill="{main}" stroke="{INK}" stroke-width="1.6"/>'
        f'<ellipse cx="50" cy="65" rx="15" ry="12" fill="#fff" opacity=".28"/>'
        '<circle cx="34" cy="59" r="3.6" fill="#F49A8F" opacity=".45"/><circle cx="66" cy="59" r="3.6" fill="#F49A8F" opacity=".45"/>'
        f'{_eyes(build.get("eyes"))}{_mouth(build.get("mouth"))}'
        f'{_extra(build.get("extra"))}{_hat(build.get("hat"))}'
    )


def render(build, size=40, title=None):
    """The avatar as a complete inline SVG (Markup). Unknown or missing parts fall back to the defaults."""
    uid = next(_ids)
    label = f'<title>{title}</title>' if title else ""
    return Markup(
        f'<svg class="creature" width="{size}" height="{size}" viewBox="3 3 94 94" role="img" '
        f'aria-hidden="{"false" if title else "true"}">{label}{_parts(build, uid)}</svg>'
    )


# ---- Pages with many avatars (leaderboards): draw each different look once ----------
# A page keeps a small "sheet" of the looks it used; each avatar just points at its look.
# 300 people on a board usually share a handful of looks, so the page stays small.

def look_key(build):
    """A short id for a look, the same for identical builds."""
    import hashlib
    text = "|".join(f"{k}={build.get(k)}" for k in sorted(build))
    return "av" + hashlib.sha1(text.encode()).hexdigest()[:10]


def render_use(key, size=40, title=None):
    """An avatar that points at its look on the page's sheet (see render_sheet)."""
    label = f'<title>{title}</title>' if title else ""
    return Markup(
        f'<svg class="creature" width="{size}" height="{size}" role="img" '
        f'aria-hidden="{"false" if title else "true"}">{label}<use href="#{key}"/></svg>'
    )


def render_sheet(looks):
    """The hidden sheet with one drawing per look: {key: build}. Put it once, at the end of the page.

    It is hidden by size, not display:none, because browsers don't paint gradients
    from a display:none SVG.
    """
    if not looks:
        return Markup("")
    symbols = "".join(f'<symbol id="{key}" viewBox="3 3 94 94">{_parts(build, next(_ids))}</symbol>'
                      for key, build in looks.items())
    return Markup('<svg width="0" height="0" aria-hidden="true" focusable="false" '
                  f'style="position:absolute;width:0;height:0;overflow:hidden">{symbols}</svg>')
