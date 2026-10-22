"""Animated mini-challenge scenes: the person's own avatar doing the workout in a little
side-scrolling world (sky, drifting clouds, rolling hills, grassy ground, floating EXP gems),
with a game-style timer in the top-right corner. Also the "Challenge complete!" scene.

Pure drawing, no database. Everything here is an original drawing for StrideBoard; the
movement itself is CSS (style.css, "Mini challenge scenes"), so it costs no JavaScript and
stops for people who ask their phone for less motion.
"""
import itertools

from markupsafe import Markup, escape

import avatar_art as art

INK = art.INK
_ids = itertools.count(1)
POSES = {"pushups": "pushup", "squats": "squat", "planks": "plank", "jumping_jacks": "jacks"}


# ------------------------------------------------------------------ the avatar, posable

def _shoe(key, shade):
    if key == "shoes_sneakers":
        return "#FFFFFF"
    if key == "shoes_gold":
        return "#E8C15A"
    return shade


def _face_and_body(build, main):
    """Body, belly, cheeks, face, extra and headwear: the avatar minus its feet (0-100 box)."""
    return (f'<ellipse cx="50" cy="56" rx="27" ry="29" fill="{main}" stroke="{INK}" stroke-width="1.6"/>'
            '<ellipse cx="50" cy="65" rx="15" ry="12" fill="#fff" opacity=".28"/>'
            '<circle cx="34" cy="59" r="3.6" fill="#F49A8F" opacity=".45"/>'
            '<circle cx="66" cy="59" r="3.6" fill="#F49A8F" opacity=".45"/>'
            f'{art._eyes(build.get("eyes"))}{art._mouth(build.get("mouth"))}'
            f'{art._extra(build.get("extra"))}{art._hat(build.get("hat"))}')


def _arm(cls, x, main):
    """A stubby arm pointing sideways from the shoulder; CSS turns it."""
    return (f'<g class="{cls}"><rect x="{x}" y="55" width="21" height="9" rx="4.5" fill="{main}" '
            f'stroke="{INK}" stroke-width="1.4"/></g>')


def _foot(cls, cx, shoe):
    return (f'<g class="{cls}"><ellipse cx="{cx}" cy="86" rx="9" ry="5" fill="{shoe}" '
            f'stroke="{INK}" stroke-width="1.4"/></g>')


def athlete(build, pose):
    """The avatar in a pose: squat, jacks, pushup, plank or cheer. A 100x100 <svg> fragment body."""
    build = build or {}
    main, shade = art.COLORS.get(build.get("color"), art.COLORS["color_mint"])
    shoe = _shoe(build.get("shoes"), shade)
    body = _face_and_body(build, main)
    shadow = '<ellipse class="ath-shadow" cx="50" cy="93" rx="26" ry="4" fill="#000" opacity=".16"/>'

    if pose in ("pushup", "plank"):
        # Seen from the front: hands planted wide on the ground, the body lowering between them.
        # Each arm is anchored at its hand; CSS turns and stretches it up to the shoulder.
        arms = (f'<g class="ath-handl"><rect x="6" y="87.5" width="21" height="9" rx="4.5" fill="{main}" '
                f'stroke="{INK}" stroke-width="1.4"/></g>'
                f'<g class="ath-handr"><rect x="73" y="87.5" width="21" height="9" rx="4.5" fill="{main}" '
                f'stroke="{INK}" stroke-width="1.4"/></g>'
                f'<ellipse cx="7" cy="93" rx="6" ry="3.2" fill="{main}" stroke="{INK}" stroke-width="1.3"/>'
                f'<ellipse cx="93" cy="93" rx="6" ry="3.2" fill="{main}" stroke="{INK}" stroke-width="1.3"/>')
        sweat = ('<path class="ath-sweat" d="M74 30q3.5 6 0 8q-3.5-2 0-8z" fill="#7CC8F2" stroke="#3E8CC0" '
                 'stroke-width=".8"/>' if pose == "plank" else "")
        return (f'<ellipse class="ath-shadow" cx="50" cy="95" rx="30" ry="4" fill="#000" opacity=".16"/>'
                f'{arms}<g class="ath-up">{body}{sweat}</g>')

    feet = _foot("ath-footl", 39, shoe) + _foot("ath-footr", 61, shoe)
    arms = _arm("ath-arml", 8, main) + _arm("ath-armr", 71, main)
    return (f'{shadow}<g class="ath-jump"><g class="ath-feet">{feet}</g>'
            f'<g class="ath-up">{arms}{body}</g></g>')


# ------------------------------------------------------------------ the world

def _clouds():
    one = ('<g fill="#fff"><circle cx="0" cy="0" r="9"/><circle cx="11" cy="-5" r="11"/>'
           '<circle cx="24" cy="0" r="9"/><rect x="0" y="0" width="24" height="8" rx="4"/></g>')
    spots = ((22, 34, 1), (128, 22, .8), (226, 50, 1.1), (300, 30, .7))
    cl = "".join(f'<g transform="translate({x + shift} {y}) scale({s})" opacity=".92">{one}</g>'
                 for shift in (0, 320) for x, y, s in spots)
    return f'<g class="g-clouds">{cl}</g>'


def _hills():
    far = ("Q40 80 80 112 Q130 70 180 108 Q230 84 270 110 Q300 96 320 120 "
           "Q360 80 400 112 Q450 70 500 108 Q550 84 590 110 Q620 96 640 120")
    near = "".join(f"q{w // 2}-{h} {w} 0" for w, h in
                   ((40, 18), (50, 22), (40, 16), (60, 24), (50, 18), (40, 14), (40, 18)) * 2)
    return (f'<g class="g-far"><path d="M0 120 {far} L640 180 L0 180Z" fill="var(--g-far)"/></g>'
            f'<g class="g-near"><path d="M0 142 {near} L640 180 L0 180Z" fill="var(--g-near)"/></g>')


def _ground():
    pebbles = "".join(f'<ellipse cx="{x}" cy="{y}" rx="{r}" ry="{r * .6:.1f}" fill="#A9693C" opacity=".55"/>'
                      for x, y, r in ((18, 166, 3), (64, 172, 2), (104, 162, 2.5), (150, 174, 3),
                                      (196, 165, 2), (238, 171, 3), (282, 163, 2.5), (312, 175, 2)))
    scallop = "".join(f'<circle cx="{x}" cy="152" r="6"/>' for x in range(0, 330, 12))
    flowers = "".join(f'<g transform="translate({x} 146)"><path d="M0 0v-7" stroke="#2F8A47" stroke-width="1.4"/>'
                      f'<circle cx="0" cy="-8" r="2.6" fill="{c}"/><circle cx="0" cy="-8" r="1" fill="#FFE36E"/></g>'
                      for x, c in ((40, "#fff"), (120, "#F7C2DA"), (262, "#fff"), (300, "#F7C2DA")))
    return (f'<rect x="0" y="150" width="320" height="30" fill="var(--g-soil)"/>{pebbles}'
            f'<g fill="var(--g-grass)">{scallop}<rect x="0" y="144" width="320" height="8"/></g>{flowers}')


def _gem(x, y, cls):
    # The class sits on an inner group: CSS movement would otherwise replace the position.
    return (f'<g transform="translate({x} {y})"><g class="{cls}"><path d="M0 -8 7 0 0 9 -7 0Z" fill="#6FD3F0" '
            f'stroke="#2A8CB4" stroke-width="1.2"/><path d="M-3 -2 0 -5 2 -3" stroke="#fff" stroke-width="1.3" '
            'fill="none" stroke-linecap="round"/></g></g>')


def _sky(uid):
    return (f'<defs><linearGradient id="sky{uid}" x1="0" y1="0" x2="0" y2="1">'
            '<stop offset="0" style="stop-color: var(--g-sky-a)"/><stop offset="1" style="stop-color: var(--g-sky-b)"/>'
            f'</linearGradient></defs><rect width="320" height="180" fill="url(#sky{uid})"/>'
            '<g class="g-sun"><circle cx="196" cy="40" r="20" fill="var(--g-sun)" opacity=".25"/>'
            '<circle cx="196" cy="40" r="13" fill="var(--g-sun)"/></g>')


def _hud(label, exp):
    return ('<g class="g-hud">'
            f'<text x="12" y="25" class="g-hud-name">{escape(label.upper())}</text>'
            f'{_gem(19, 40, "g-hud-gem")}<text x="30" y="45" class="g-hud-exp">+{int(exp)} EXP</text>'
            '<rect x="226" y="10" width="84" height="30" rx="9" fill="#1D2140" stroke="#fff" stroke-width="2"/>'
            '<g transform="translate(240 25)" fill="none" stroke="#FFE36E" stroke-width="1.8">'
            '<circle r="6.5"/><path d="M0 -3.5V0l2.5 2" stroke-linecap="round"/></g>'
            '<text x="300" y="31" text-anchor="end" class="g-hud-clock" data-mini-clock>0:00</text></g>')


def _world(uid, middle, top=""):
    return (f'<svg class="game-svg" viewBox="0 0 320 180" preserveAspectRatio="xMidYMid slice" aria-hidden="true">'
            f'{_sky(uid)}{_clouds()}{_hills()}{_ground()}'
            f'{_gem(92, 78, "g-gem g-gem-a")}{_gem(246, 92, "g-gem g-gem-b")}{_gem(276, 70, "g-gem g-gem-c")}'
            f'{middle}{top}</svg>')


def scene(build, track, label, exp):
    """The live scene while someone does a mini challenge (not walks). Holds the timer."""
    pose = POSES.get(track)
    if pose is None:
        return Markup("")
    uid = next(_ids)
    player = (f'<svg class="ath ath-{pose}" x="112" y="58" width="96" height="96" viewBox="0 0 100 100" '
              f'overflow="visible">{athlete(build, pose)}</svg>')
    return Markup(f'<div class="game game-{pose}">{_world(uid, player, _hud(label, exp))}</div>')


def celebration(build):
    """The 'Challenge complete!' scene: the avatar cheering under a burst of gems and confetti."""
    uid = next(_ids)
    burst = "".join(f'<g class="g-burst" style="--a:{a}deg; --d:{i * 40}ms">{_gem(0, 0, "")}</g>'
                    for i, a in enumerate(range(0, 360, 45)))
    colours = ("#F7DB6F", "#F49A8F", "#9EDCC6", "#A9CCF2", "#C9B8F2", "#fff")
    confetti = "".join(f'<rect class="g-confetti" x="{x}" y="-10" width="5" height="9" rx="1.5" '
                       f'fill="{colours[i % len(colours)]}" style="--d:{(i * 137) % 900}ms; --s:{0.9 + (i % 5) * .15:.2f}"/>'
                       for i, x in enumerate(range(8, 320, 19)))
    player = (f'<svg class="ath ath-cheer" x="112" y="58" width="96" height="96" viewBox="0 0 100 100" '
              f'overflow="visible">{athlete(build, "cheer")}</svg>')
    middle = f'<g transform="translate(160 96)">{burst}</g>{player}{confetti}'
    return Markup(f'<div class="game game-cheer">{_world(uid, middle)}</div>')
