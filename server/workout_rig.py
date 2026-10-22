"""A little athlete drawn from joints, moving with real exercise form.

Each exercise is a function of time (phase 0..1) that places the joints: hips, knees, ankles,
shoulders, elbows, hands. Legs and arms are solved with two-bone IK so feet stay planted on the
ground and hands stay on the floor during push-ups. The joint positions are sampled through the
cycle and written out as SVG animation (SMIL), so the browser plays them with no JavaScript.

Coordinates are a 100 x 100 box; the ground is y = 97. Pure drawing; no database.
"""
import math

from markupsafe import Markup

INK = "#17181C"
GROUND = 97
FRAMES = 24
LEGGINGS = "#2E3358"
LEGGINGS_FAR = "#20243F"

# lengths
THIGH = SHIN = 16
UPPER = 12.5
FORE = 12
TORSO = 23
HEAD_R = 7.8


def _ik(root, target, l1, l2, prefer):
    """Two-bone IK: the middle joint for a limb from root to target. prefer(j1, j2) picks the side."""
    (ax, ay), (bx, by) = root, target
    dx, dy = bx - ax, by - ay
    d = max(1e-6, min(math.hypot(dx, dy), l1 + l2 - 1e-3))
    a = math.atan2(dy, dx)
    phi = math.acos(max(-1, min(1, (l1 * l1 + d * d - l2 * l2) / (2 * l1 * d))))
    j1 = (ax + l1 * math.cos(a + phi), ay + l1 * math.sin(a + phi))
    j2 = (ax + l1 * math.cos(a - phi), ay + l1 * math.sin(a - phi))
    return prefer(j1, j2)


def _along(p, angle_deg, length):
    """The point `length` away from p, at angle_deg measured clockwise from straight up."""
    r = math.radians(angle_deg)
    return (p[0] + length * math.sin(r), p[1] - length * math.cos(r))


def _ease(phase):
    """0 at the start and end of a rep, 1 in the middle, smooth both ways."""
    return (1 - math.cos(2 * math.pi * phase)) / 2


def _mix(a, b, t):
    return a + (b - a) * t


forward = lambda j1, j2: j1 if j1[0] >= j2[0] else j2      # knees point the way they face
backward = lambda j1, j2: j1 if j1[0] <= j2[0] else j2     # elbows bend back toward the feet
outward_left = lambda j1, j2: j1 if j1[0] <= j2[0] else j2
outward_right = lambda j1, j2: j1 if j1[0] >= j2[0] else j2


# ------------------------------------------------------------------ the exercises (side view faces right)

def squat(phase):
    t = _ease(phase)
    hip = (_mix(48, 39, t), _mix(GROUND - 33, GROUND - 19, t))
    lean = _mix(4, 42, t)
    shoulder = _along(hip, lean, TORSO)
    ankle = (49, GROUND - 2)
    knee = _ik(hip, ankle, THIGH, SHIN, forward)
    arm = _mix(176, 92, t)                                  # hanging down, then reaching forward
    elbow = _along(shoulder, arm, UPPER)
    hand = _along(elbow, arm - _mix(0, 8, t), FORE)
    return {"view": "side", "hip": hip, "shoulder": shoulder, "head": _along(shoulder, lean * .55, 10.5),
            "knee": knee, "ankle": ankle, "toe": (ankle[0] + 7, GROUND - 1.5),
            "far_knee": (knee[0] - 2.5, knee[1]), "far_ankle": (ankle[0] - 2.5, ankle[1]),
            "far_toe": (ankle[0] + 4.5, GROUND - 1.5),
            "elbow": elbow, "hand": hand, "far_elbow": (elbow[0] - 2, elbow[1]), "far_hand": (hand[0] - 2, hand[1])}


def _plank_line(angle_up, toe_x):
    """A straight body from the toes: returns ankle, knee, hip, shoulder for a body raised angle_up degrees."""
    toe = (toe_x, GROUND - 1.5)
    ankle = (toe_x + 2, GROUND - 4)
    r = math.radians(angle_up)
    unit = (math.cos(r), -math.sin(r))
    knee = (ankle[0] + unit[0] * SHIN, ankle[1] + unit[1] * SHIN)
    hip = (knee[0] + unit[0] * THIGH, knee[1] + unit[1] * THIGH)
    shoulder = (hip[0] + unit[0] * TORSO, hip[1] + unit[1] * TORSO)
    return toe, ankle, knee, hip, shoulder, unit


def pushup(phase):
    t = _ease(phase)
    toe, ankle, knee, hip, shoulder, unit = _plank_line(_mix(24, 8, t), 10)
    hand = (63.5, GROUND - 1)
    elbow = _ik(shoulder, hand, UPPER, FORE, backward)
    head = (shoulder[0] + unit[0] * 9 + 1.5, shoulder[1] + unit[1] * 9 - 3)
    return {"view": "side", "hip": hip, "shoulder": shoulder, "head": head, "knee": knee, "ankle": ankle,
            "toe": toe, "far_knee": knee, "far_ankle": ankle, "far_toe": toe,
            "elbow": elbow, "hand": hand, "far_elbow": (elbow[0] - 1.5, elbow[1]), "far_hand": (hand[0] - 2, hand[1])}


def plank(phase):
    wobble = math.sin(2 * math.pi * phase) * .6
    toe, ankle, knee, hip, shoulder, unit = _plank_line(11.2 + wobble, 8)
    elbow = (shoulder[0], GROUND - 2)
    hand = (shoulder[0] + FORE, GROUND - 2)
    head = (shoulder[0] + unit[0] * 9 + 1.5, shoulder[1] + unit[1] * 9 - 3)
    return {"view": "side", "hip": hip, "shoulder": shoulder, "head": head, "knee": knee, "ankle": ankle,
            "toe": toe, "far_knee": knee, "far_ankle": ankle, "far_toe": toe,
            "elbow": elbow, "hand": hand, "far_elbow": (elbow[0] - 2, elbow[1]), "far_hand": (hand[0] - 2, hand[1])}


def _front(open_t, lift, arms_up):
    """Front view: legs spread by open_t (0..1), body lifted by `lift`, arms at angle arms_up (deg from down)."""
    spread = _mix(2, 13, open_t)
    hip_y = GROUND - 2 - math.sqrt((THIGH + SHIN) ** 2 - spread ** 2) - lift
    hips = {"l": (46, hip_y), "r": (54, hip_y)}
    ankles = {"l": (46 - spread, GROUND - 2 - lift), "r": (54 + spread, GROUND - 2 - lift)}
    knees = {s: ((hips[s][0] + ankles[s][0]) / 2, (hips[s][1] + ankles[s][1]) / 2) for s in "lr"}
    shoulders = {"l": (42.5, hip_y - TORSO + 2), "r": (57.5, hip_y - TORSO + 2)}
    arm = {}
    for s, sign in (("l", -1), ("r", 1)):
        a = 180 - arms_up if s == "r" else 180 + arms_up            # clockwise from straight up
        elbow = _along(shoulders[s], a, UPPER)
        hand = _along(elbow, a + sign * -8 * (arms_up / 160), FORE)
        arm[s] = (elbow, hand)
    return {"view": "front", "hip": (50, hip_y), "neck": (50, hip_y - TORSO), "head": (50, hip_y - TORSO - 9),
            "hips": hips, "knees": knees, "ankles": ankles, "shoulders": shoulders, "arms": arm, "lift": lift}


def jacks(phase):
    t = _ease(phase)
    lift = 7 * abs(math.sin(2 * math.pi * phase))
    return _front(t, lift, _mix(14, 160, t))


def cheer(phase):
    lift = 9 * _ease(phase)
    return _front(.35, lift, 148 + 10 * math.sin(4 * math.pi * phase))


EXERCISES = {"squat": (squat, 2.6), "pushup": (pushup, 2.0), "plank": (plank, 3.2),
             "jacks": (jacks, 1.2), "cheer": (cheer, .8)}


# ------------------------------------------------------------------ drawing

def _angle(p, q):
    """Rotation (degrees) that turns a segment drawn straight down from (0,0) to point from p to q."""
    return math.degrees(math.atan2(-(q[0] - p[0]), q[1] - p[1]))


def _segments(pose, colours):
    """[(key, start, end, width, colour)] back to front."""
    main, shade, shoe = colours
    if pose["view"] == "side":
        return [
            ("farleg1", pose["hip"], pose["far_knee"], 7.4, LEGGINGS_FAR),
            ("farleg2", pose["far_knee"], pose["far_ankle"], 6.6, LEGGINGS_FAR),
            ("farfoot", pose["far_ankle"], pose["far_toe"], 5.6, shoe),
            ("fararm1", pose["shoulder"], pose["far_elbow"], 5.8, shade),
            ("fararm2", pose["far_elbow"], pose["far_hand"], 5.2, shade),
            ("leg1", pose["hip"], pose["knee"], 7.6, LEGGINGS),
            ("leg2", pose["knee"], pose["ankle"], 6.8, LEGGINGS),
            ("foot", pose["ankle"], pose["toe"], 5.8, shoe),
            ("torso", pose["hip"], pose["shoulder"], 12.5, main),
            ("arm1", pose["shoulder"], pose["elbow"], 6, main),
            ("arm2", pose["elbow"], pose["hand"], 5.4, main),
        ]
    segs = []
    for s in "lr":
        segs += [(f"leg{s}1", pose["hips"][s], pose["knees"][s], 7.6, LEGGINGS),
                 (f"leg{s}2", pose["knees"][s], pose["ankles"][s], 6.8, LEGGINGS),
                 (f"foot{s}", pose["ankles"][s],
                  (pose["ankles"][s][0] + (-4 if s == "l" else 4), pose["ankles"][s][1] + .5), 5.6, shoe)]
    segs.append(("torso", pose["hip"], pose["neck"], 15, main))
    for s in "lr":
        elbow, hand = pose["arms"][s]
        segs += [(f"arm{s}1", pose["shoulders"][s], elbow, 6, main), (f"arm{s}2", elbow, hand, 5.4, main)]
    return segs


def _fmt(v):
    return f"{v:.1f}".rstrip("0").rstrip(".")


def _head(view, main, extra):
    """The head at (0, 0), with a sporty headband. Side view looks right."""
    band = "#E5786B"
    if view == "side":
        face = (f'<circle cx="3.4" cy="-1" r="1.25" fill="{INK}"/>'
                f'<path d="M3.2 2.6q2 1.4 3.6-.4" stroke="{INK}" stroke-width="1.1" fill="none" stroke-linecap="round"/>'
                '<circle cx="1" cy="2" r="1.5" fill="#F49A8F" opacity=".55"/>')
        headband = (f'<path d="M-7 -3.2q7-3 14 0v2.6q-7-3-14 0z" fill="{band}" stroke="{INK}" stroke-width=".9"/>'
                    f'<path d="M-6.6 -2.4l-4.2 1.8 1 1.6 3.8-1.6" fill="{band}" stroke="{INK}" stroke-width=".8"/>')
    else:
        face = (f'<circle cx="-2.6" cy="-.6" r="1.25" fill="{INK}"/><circle cx="2.6" cy="-.6" r="1.25" fill="{INK}"/>'
                f'<path d="M-2.2 2.6q2.2 2 4.4 0" stroke="{INK}" stroke-width="1.1" fill="none" stroke-linecap="round"/>'
                '<circle cx="-4.4" cy="1.8" r="1.4" fill="#F49A8F" opacity=".55"/><circle cx="4.4" cy="1.8" r="1.4" fill="#F49A8F" opacity=".55"/>')
        headband = f'<path d="M-7 -3.4q7-3 14 0v2.6q-7-3-14 0z" fill="{band}" stroke="{INK}" stroke-width=".9"/>'
    return (f'<circle r="{HEAD_R}" fill="{main}" stroke="{INK}" stroke-width="1.4"/>'
            f'{headband}{face}{extra}')


def figure(build, exercise):
    """The animated athlete for one exercise, as the inside of a 100x100 <svg>."""
    from avatar_art import COLORS
    build = build or {}
    main, shade = COLORS.get(build.get("color"), COLORS["color_mint"])
    shoe_key = build.get("shoes")
    shoe = "#FFFFFF" if shoe_key == "shoes_sneakers" else "#E8C15A" if shoe_key == "shoes_gold" else "#E5786B"
    fn, dur = EXERCISES[exercise]
    poses = [fn(i / FRAMES) for i in range(FRAMES + 1)]
    first = _segments(poses[0], (main, shade, shoe))
    frames = [_segments(p, (main, shade, shoe)) for p in poses]
    anim = f'dur="{dur}s" repeatCount="indefinite" calcMode="linear"'

    parts = []
    for k, (key, p, q, width, colour) in enumerate(first):
        length = math.hypot(q[0] - p[0], q[1] - p[1])
        moves = ";".join(f"{_fmt(f[k][1][0])} {_fmt(f[k][1][1])}" for f in frames)
        turns = ";".join(_fmt(_angle(f[k][1], f[k][2])) for f in frames)
        line = (f'<line y2="{_fmt(length)}" stroke="{INK}" stroke-width="{width + 2.6}" stroke-linecap="round"/>'
                f'<line y2="{_fmt(length)}" stroke="{colour}" stroke-width="{width}" stroke-linecap="round"/>')
        if key == "torso":
            line += (f'<line y2="{_fmt(length)}" stroke="#fff" stroke-width="{width * .34:.1f}" stroke-linecap="round" '
                     f'opacity=".22" transform="translate({width * .18:.1f} 0)"/>')
        parts.append(
            f'<g transform="translate({_fmt(p[0])} {_fmt(p[1])})">'
            f'<animateTransform attributeName="transform" type="translate" values="{moves}" {anim}/>'
            f'<g transform="rotate({_fmt(_angle(p, q))})">'
            f'<animateTransform attributeName="transform" type="rotate" values="{turns}" {anim}/>{line}</g></g>')
        if key == "torso":                          # the head goes on after the body, before the near arm
            hx = ";".join(f"{_fmt(pp['head'][0])} {_fmt(pp['head'][1])}" for pp in poses)
            sweat = ""
            if exercise == "plank":
                sweat = ('<path d="M4 -10q2.4 4 0 5.4q-2.4-1.4 0-5.4z" fill="#7CC8F2" stroke="#3E8CC0" stroke-width=".7">'
                         '<animateTransform attributeName="transform" type="translate" values="0 0;0 9" dur="1.6s" '
                         'repeatCount="indefinite"/><animate attributeName="opacity" values="0;1;1;0" dur="1.6s" '
                         'repeatCount="indefinite"/></path>')
            h0 = poses[0]["head"]
            parts.append(f'<g transform="translate({_fmt(h0[0])} {_fmt(h0[1])})">'
                         f'<animateTransform attributeName="transform" type="translate" values="{hx}" {anim}/>'
                         f'{_head(poses[0]["view"], main, sweat)}</g>')

    # A soft shadow that shrinks when the athlete leaves the ground.
    lifts = [p.get("lift", 0) for p in poses]
    scales = ";".join(_fmt(1 - min(.4, l / 20)) for l in lifts)
    shadow_w = 30 if poses[0]["view"] == "side" else 18
    shadow = (f'<g transform="translate(50 {GROUND + .5})"><ellipse rx="{shadow_w}" ry="2.6" fill="#000" opacity=".16">'
              f'<animateTransform attributeName="transform" type="scale" values="{scales}" {anim}/></ellipse></g>')
    return Markup(shadow + "".join(parts))
