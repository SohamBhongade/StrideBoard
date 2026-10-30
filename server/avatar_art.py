"""Draws a StrideBoard avatar: a small round walker with feet, built from parts.

Pure drawing, no database. render(build, size) returns an <svg> for a build such as
{"color": "color_mint", "eyes": "eyes_dots", "mouth": "mouth_smile", "hat": "hat_cap",
 "extra": "extra_none", "shoes": "shoes_sneakers", "bg": "bg_sage"}.
The character and every part are original drawings for StrideBoard.
"""
import itertools

from markupsafe import Markup, escape

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


def _sparkle(x, y, r):
    return (f'<path d="M{x} {y - r}Q{x + r * .18} {y - r * .18} {x + r} {y}Q{x + r * .18} {y + r * .18} {x} {y + r}'
            f'Q{x - r * .18} {y + r * .18} {x - r} {y}Q{x - r * .18} {y - r * .18} {x} {y - r}Z" fill="#fff"/>')


def _bg(key, uid):
    if key == "bg_reaper_night":
        stars = "".join(f'<circle cx="{x}" cy="{y}" r="{r}" fill="#fff" opacity="{o}"/>'
                        for x, y, r, o in ((86, 40, 1.3, .9), (36, 8, .9, .7), (12, 46, 1, .6), (90, 62, 1.2, .8),
                                           (92, 78, .9, .6), (10, 80, 1.1, .7)))
        return (f'<defs><linearGradient id="rn{uid}" x1="0" y1="0" x2="0" y2="1">'
                '<stop offset="0" stop-color="#2A1F45"/><stop offset="1" stop-color="#4B2E6B"/></linearGradient></defs>'
                f'<rect width="100" height="100" fill="url(#rn{uid})"/>{stars}'
                '<path d="M20 9a10 10 0 1 0 8 15a8 8 0 1 1-8-15z" fill="#F3E9C6"/>'
                '<path d="M0 92q25-6 50 0t50 0V100H0z" fill="#21183A"/>')
    if key == "bg_platinum_glow":
        return (f'<defs><radialGradient id="pg{uid}" cx=".5" cy=".45" r=".7">'
                '<stop offset="0" stop-color="#F4FFFD"/><stop offset=".55" stop-color="#BFF0E8"/>'
                '<stop offset="1" stop-color="#7FC9C0"/></radialGradient></defs>'
                f'<rect width="100" height="100" fill="url(#pg{uid})"/>'
                + _sparkle(16, 20, 5) + _sparkle(84, 26, 4) + _sparkle(80, 80, 5.5) + _sparkle(18, 74, 3.5)
                + _sparkle(50, 8, 3))
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


def _skull():
    """The owner's skull face: a friendly bone-white face plate over the eyes and mouth."""
    plate = "M33 54Q32 37 50 36Q68 37 67 54Q67 62 61 64V69Q50 72 39 69V64Q33 62 33 54Z"
    teeth = "".join(f'<path d="M{x} 64.5v4.5" stroke="{INK}" stroke-width="1.1" stroke-linecap="round"/>'
                    for x in (44.5, 50, 55.5))
    return (f'<path d="{plate}" fill="#F4F1E8" stroke="{INK}" stroke-width="1.5" stroke-linejoin="round"/>'
            f'<ellipse cx="42.5" cy="50" rx="5.2" ry="5.8" fill="{INK}"/><ellipse cx="57.5" cy="50" rx="5.2" ry="5.8" fill="{INK}"/>'
            '<circle cx="44" cy="48.4" r="1.5" fill="#fff"/><circle cx="59" cy="48.4" r="1.5" fill="#fff"/>'
            f'<path d="M50 56.5l-2.4 3.6h4.8z" fill="{INK}" stroke="{INK}" stroke-width="1" stroke-linejoin="round"/>'
            f'<path d="M40 64.5Q50 66.5 60 64.5" stroke="{INK}" stroke-width="1.2" fill="none"/>{teeth}'
            '<path d="M37 45Q40 40 46 39" stroke="#fff" stroke-width="1.2" opacity=".8" fill="none" stroke-linecap="round"/>')


def _mouth(key):
    if key == "mouth_skull":
        return _skull()
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


SILVER, SILVER_SHADE = "#D9DEE6", "#A9B2BF"
GOLD, GOLD_SHADE = "#E8C15A", "#C99B2E"
PLAT, PLAT_SHADE = "#BFF0E8", "#8FD5CC"


REAPER, REAPER_SHADE = "#3B2D5C", "#271D40"


def _scythe(main, shade):
    """The owner's scythe, held in front: the handle crosses the body, the blade sweeps over the head.
    The little hand holding it is the avatar's own body colour."""
    return (f'<path d="M64 95L82 13" stroke="{INK}" stroke-width="5.4" stroke-linecap="round"/>'
            '<path d="M64 95L82 13" stroke="#8A5A3C" stroke-width="3.2" stroke-linecap="round"/>'
            '<path d="M70.5 66l3.6-16" stroke="#B07A55" stroke-width="1" stroke-linecap="round" opacity=".8"/>'
            f'<ellipse cx="69.3" cy="78.5" rx="4.6" ry="3.8" transform="rotate(-14 69.3 78.5)" '
            f'fill="{main}" stroke="{INK}" stroke-width="1.3"/>'
            f'<path d="M66.4 80.6q3 1.4 5.8 .4" stroke="{shade}" stroke-width="1.1" fill="none" stroke-linecap="round"/>'
            f'<path d="M83 15Q70 0 48 5Q64 9 75 22Z" fill="#D9DEE6" stroke="{INK}" stroke-width="1.4" stroke-linejoin="round"/>'
            '<path d="M78 10Q66 4 54 6" stroke="#fff" stroke-width="1.3" fill="none" opacity=".9"/>'
            f'<rect x="78.5" y="11" width="7" height="6" rx="1.6" fill="{REAPER}" stroke="{INK}" stroke-width="1.2" '
            'transform="rotate(12 82 14)"/>')


def _wings(key):
    """Extras drawn behind the body: Silver wings, Gold cape."""
    if key == "extra_gold_cape":
        return (f'<path d="M31 46Q50 52 69 46L86 90Q50 97 14 90Z" fill="{GOLD}" stroke="{INK}" stroke-width="1.4" stroke-linejoin="round"/>'
                f'<path d="M27 70Q24 82 22 89M73 70Q76 82 78 89" stroke="{GOLD_SHADE}" stroke-width="1.6" fill="none" stroke-linecap="round"/>'
                f'<path d="M15 88Q50 95 85 88" stroke="#B4492F" stroke-width="2.6" fill="none"/>'
                '<path d="M33 49Q42 53 50 53" stroke="#fff" stroke-width="1.2" opacity=".7" fill="none"/>')
    if key != "extra_silver_wings":
        return ""
    left = ("M29 52C21 40 11 33 5 36C9 40 9 43 7 46C12 46 14 49 12 53C17 53 19 56 17 60"
            "C22 59 26 61 29 64Z")
    feathers = "M10 41l14 9M11 49l15 5M15 57l12 3"
    one = (f'<path d="{left}" fill="{SILVER}" stroke="{INK}" stroke-width="1.3" stroke-linejoin="round"/>'
           f'<path d="{feathers}" stroke="{SILVER_SHADE}" stroke-width="1.2" stroke-linecap="round"/>'
           '<path d="M9 38q8 3 14 10" stroke="#fff" stroke-width="1.2" opacity=".85" fill="none"/>')
    return f'<g>{one}</g><g transform="translate(100 0) scale(-1 1)">{one}</g>'


def _laurel():
    leaves = []
    for side in (1, -1):
        for i, (x, y, rot) in enumerate(((27, 42, -30), (28, 34, -10), (32, 27, 15), (38, 22, 35), (44, 19, 55))):
            cx = 50 + side * (50 - x)
            r = rot if side == 1 else -rot
            leaves.append(f'<ellipse cx="{cx}" cy="{y}" rx="4.4" ry="2.2" transform="rotate({r} {cx} {y})" '
                          f'fill="{GOLD if i % 2 else GOLD_SHADE}" stroke="{INK}" stroke-width=".9"/>')
    stems = (f'<path d="M26 46Q27 26 47 18M74 46Q73 26 53 18" stroke="{GOLD_SHADE}" stroke-width="1.6" fill="none"/>')
    return stems + "".join(leaves)


def _hood():
    """The owner's hood: covers the top and sides of the head, the face peeks out; a soft point on top."""
    outer = ("M17 68Q14 32 36 19Q46 13 57 5Q55 12 62 18Q86 30 83 68"
             "Q77 76 70 74Q73 46 50 35Q27 46 30 74Q23 76 17 68Z")
    return (f'<path d="{outer}" fill="{REAPER}" stroke="{INK}" stroke-width="1.5" stroke-linejoin="round"/>'
            f'<path d="M30 74Q27 46 50 35Q73 46 70 74" stroke="{REAPER_SHADE}" stroke-width="2.4" fill="none"/>'
            '<path d="M36 25Q44 18 53 16" stroke="#fff" stroke-width="1.3" opacity=".35" fill="none" stroke-linecap="round"/>')


def _hat(key):
    if key == "hat_reaper_hood":
        return _hood()
    if key == "hat_gold_laurel":
        return _laurel()
    if key == "hat_platinum_halo":
        return (f'<ellipse cx="50" cy="17" rx="17" ry="5" fill="none" stroke="{PLAT}" stroke-width="7" opacity=".35"/>'
                f'<ellipse cx="50" cy="17" rx="17" ry="5" fill="none" stroke="{INK}" stroke-width="4.4"/>'
                f'<ellipse cx="50" cy="17" rx="17" ry="5" fill="none" stroke="{PLAT}" stroke-width="2.6"/>'
                '<path d="M38 14.5q6-2 12-2.2" stroke="#fff" stroke-width="1.2" opacity=".9" fill="none"/>')
    if key == "hat_silver_visor":
        return ('<g transform="translate(0 -4.5)">'
                f'<path d="M24 40q26-9 52 0v5q-26-9-52 0z" fill="{SILVER}" stroke="{INK}" stroke-width="1.3"/>'
                f'<path d="M28 44q22 11 44 0q-22 3-44 0z" fill="{SILVER_SHADE}" stroke="{INK}" stroke-width="1.3" stroke-linejoin="round"/>'
                '<path d="M30 39.5q20-6 40 0" stroke="#fff" stroke-width="1.3" opacity=".9" fill="none"/>'
                '<path d="M36 46.5q8 2.4 14 2.4" stroke="#fff" stroke-width="1.1" opacity=".7" fill="none"/></g>')
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
        f'{_wings(build.get("extra"))}'
        f'{_feet(build.get("shoes"), shade)}'
        f'<ellipse cx="50" cy="56" rx="27" ry="29" fill="{main}" stroke="{INK}" stroke-width="1.6"/>'
        f'<ellipse cx="50" cy="65" rx="15" ry="12" fill="#fff" opacity=".28"/>'
        '<circle cx="34" cy="59" r="3.6" fill="#F49A8F" opacity=".45"/><circle cx="66" cy="59" r="3.6" fill="#F49A8F" opacity=".45"/>'
        f'{_eyes(build.get("eyes"))}{_mouth(build.get("mouth"))}'
        f'{_extra(build.get("extra"))}{_hat(build.get("hat"))}'
        f'{_scythe(main, shade) if build.get("extra") == "extra_reaper_scythe" else ""}'   # held in front of everything
    )


def render(build, size=40, title=None):
    """The avatar as a complete inline SVG (Markup). Unknown or missing parts fall back to the defaults."""
    uid = next(_ids)
    label = f'<title>{escape(title)}</title>' if title else ""
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
    label = f'<title>{escape(title)}</title>' if title else ""
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
