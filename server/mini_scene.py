"""Animated mini-challenge scenes: the person's own avatar doing the workout in a little
side-scrolling world (sky, drifting clouds, rolling hills, grassy ground, floating EXP gems),
with a game-style timer in the top-right corner. Also the "Challenge complete!" scene.

Pure drawing, no database. Everything here is an original drawing for StrideBoard; the
movement itself is CSS (style.css, "Mini challenge scenes"), so it costs no JavaScript and
stops for people who ask their phone for less motion.
"""
import itertools
import math

from markupsafe import Markup, escape

import workout_rig

_ids = itertools.count(1)
POSES = {"pushups": "pushup", "squats": "squat", "planks": "plank", "jumping_jacks": "jacks"}


# ------------------------------------------------------------------ the athlete

def _player(build, pose, size=128):
    """The athlete (workout_rig) in a 100x100 box standing on the scene's ground (y = 150)."""
    top = 150 - .97 * size
    return (f'<svg class="ath ath-{pose}" x="{160 - size / 2:g}" y="{top:g}" width="{size}" height="{size}" '
            f'viewBox="0 0 100 100" overflow="visible">{workout_rig.figure(build, pose)}</svg>')


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


def _hud(label, exp, right=None):
    if right is None:   # the timer
        right = ('<rect x="226" y="10" width="84" height="30" rx="9" fill="#1D2140" stroke="#fff" stroke-width="2"/>'
                 '<g transform="translate(240 25)" fill="none" stroke="#FFE36E" stroke-width="1.8">'
                 '<circle r="6.5"/><path d="M0 -3.5V0l2.5 2" stroke-linecap="round"/></g>'
                 '<text x="300" y="31" text-anchor="end" class="g-hud-clock" data-mini-clock>0:00</text>')
    return ('<g class="g-hud">'
            f'<text x="12" y="25" class="g-hud-name">{escape(label.upper())}</text>'
            f'{_gem(19, 40, "g-hud-gem")}<text x="30" y="45" class="g-hud-exp">+{int(exp)} EXP</text>'
            f'{right}</g>')


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
    player = _player(build, pose)
    return Markup(f'<div class="game game-{pose}">{_world(uid, player, _hud(label, exp))}</div>')


def celebration(build):
    """The 'Challenge complete!' scene: the avatar cheering under a burst of gems and confetti."""
    uid = next(_ids)
    burst = "".join(f'<g class="g-burst" style="--a:{a}deg; --d:{i * 40}ms">{_gem(0, 0, "")}</g>'
                    for i, a in enumerate(range(0, 360, 45)))
    colours = ("#F7DB6F", "#F49A8F", "#9EDCC6", "#A9CCF2", "#C9B8F2", "#fff")
    confetti = "".join(f'<rect class="g-confetti" x="{x}" y="-10" width="5" height="9" rx="1.5" '
                       f'fill="{colours[i % len(colours)]}" style="--d:{(i * 137) % 900}ms; --s:{0.9 + (i % 5) * .15:.2f}; '
                       f'--y:{24 + (i * 53) % 120}px"/>'
                       for i, x in enumerate(range(8, 320, 19)))
    # A fountain of confetti shooting up from behind the athlete each time they leap.
    shapes = ('<rect x="-2.5" y="-4" width="5" height="8" rx="1.4"/>', '<circle r="2.6"/>',
              '<path d="M0 -4 3.5 3H-3.5Z"/>')
    fountain = ""
    for i in range(26):
        angle = math.radians(-78 + (i * 61) % 157)          # spread across the sky above
        speed = 52 + (i * 37) % 34
        dx, dy = math.sin(angle) * speed, -math.cos(angle) * speed
        fountain += (f'<g class="g-fountain" style="--dx:{dx:.0f}px; --dy:{dy:.0f}px; --d:{380 + (i * 23) % 160}ms" '
                     f'fill="{colours[i % len(colours)]}">{shapes[i % 3]}</g>')
    player = _player(build, "cheer", 96)
    middle = (f'<g transform="translate(160 96)">{burst}</g>'
              f'<g transform="translate(160 112)">{fountain}</g>{player}{confetti}')
    return Markup(f'<div class="game game-cheer">{_world(uid, middle)}</div>')


# ------------------------------------------------------------------ walks: a course with checkpoints

COURSE_X = [34 + i * 50.4 for i in range(6)]   # start, four checkpoints, the finish flag
# Where the walker stands: just before each post, so its number stays in view.
STAND_X = [COURSE_X[0]] + [x - 11 for x in COURSE_X[1:]]


def _course(amount):
    step = amount // 5
    posts = ""
    for i in range(1, 5):
        x = COURSE_X[i]
        posts += (f'<g class="g-cp" data-cp="{i}"><line x1="{x:.1f}" y1="150" x2="{x:.1f}" y2="129" stroke="#5B4636" '
                  f'stroke-width="2" stroke-linecap="round"/><path d="M{x:.1f} 129l12 4-12 4z" fill="#F7DB6F" '
                  f'stroke="#1D2140" stroke-width="1"/><text x="{x:.1f}" y="125" text-anchor="middle" '
                  f'class="g-cp-num">{step * i:,}</text></g>')
    fx = COURSE_X[5]
    squares = "".join(f'<rect x="{fx + 1 + c * 4.5:.1f}" y="{106 + r * 4.5:.1f}" width="4.5" height="4.5" '
                      f'fill="{"#1D2140" if (r + c) % 2 else "#fff"}"/>' for r in range(3) for c in range(4))
    flag = (f'<line x1="{fx:.1f}" y1="150" x2="{fx:.1f}" y2="104" stroke="#5B4636" stroke-width="2.4" '
            f'stroke-linecap="round"/><g class="g-flag">{squares}<rect x="{fx + 1:.1f}" y="106" width="18" '
            f'height="13.5" fill="none" stroke="#1D2140" stroke-width="1"/></g>')
    start = (f'<rect x="{COURSE_X[0] - 1.5:.1f}" y="144" width="3" height="10" fill="#fff" opacity=".9"/>'
             f'<text x="{COURSE_X[0]:.1f}" y="164" text-anchor="middle" class="g-cp-num g-start">START</text>')
    trail = (f'<line x1="{COURSE_X[0]:.1f}" y1="157" x2="{fx:.1f}" y2="157" stroke="#fff" stroke-width="2" '
             'stroke-dasharray="2 5" stroke-linecap="round" opacity=".55"/>')
    return f'<g class="g-course">{trail}{start}{posts}{flag}</g>'


def _walker(build, x, finish=False):
    """The athlete on the course: standing at a checkpoint, or walking between them."""
    size = 92
    box = f'x="{-size / 2:g}" y="{150 - .97 * size:g}" width="{size}" height="{size}" viewBox="0 0 100 100" overflow="visible"'
    still = "" if finish else f'<svg class="w-stand" {box}>{workout_rig.figure(build, "stand")}</svg>'
    moving = f'<svg class="w-walk" {box}>{workout_rig.figure(build, "walk")}</svg>'
    return f'<g class="walker{" walking" if finish else ""}" style="transform: translateX({x:.1f}px)">{still}{moving}</g>'


def walk_scene(build, label, exp, walked, amount):
    """The live walk: the athlete waits at the last checkpoint reached and walks on as steps arrive."""
    uid = next(_ids)
    reached = min(5, walked * 5 // amount)
    steps = (f'<rect x="206" y="10" width="104" height="30" rx="9" fill="#1D2140" stroke="#fff" stroke-width="2"/>'
             '<g transform="translate(220 25)" fill="#FFE36E"><ellipse cx="-2.6" cy="-2" rx="2.4" ry="3.6"/>'
             '<ellipse cx="2.8" cy="2.6" rx="2.4" ry="3.6"/></g>'
             f'<text x="300" y="30" text-anchor="end" class="g-hud-steps"><tspan data-walk-done>{walked:,}</tspan>'
             f'<tspan class="g-hud-of"> / {amount:,}</tspan></text>')
    middle = _course(amount) + _walker(build, STAND_X[reached])
    return Markup(f'<div class="game game-walk" data-course="{",".join(f"{x:.1f}" for x in STAND_X)}" '
                  f'data-reached="{reached}">{_world(uid, middle, _hud(label, exp, steps))}</div>')


def walk_finish(build, amount):
    """Over the finish line: from the last checkpoint, past the checkered flag and off the screen."""
    uid = next(_ids)
    middle = _course(amount) + _walker(build, STAND_X[4], finish=True)
    return Markup(f'<div class="game game-walk game-finish">{_world(uid, middle)}</div>')
