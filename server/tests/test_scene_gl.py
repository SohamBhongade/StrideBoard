"""The WebGL scenes (static/js/scene-gl.js) get their movement from the same rig as the SVG ones."""
import html
import json
import re

import pytest

import mini_scene
import workout_rig

BUILD = {"color": "color_coral", "shoes": "shoes_neon"}


def gl_info(markup):
    raw = re.search(r'data-gl="([^"]+)"', str(markup)).group(1)
    return json.loads(html.unescape(raw))


@pytest.mark.parametrize("exercise", sorted(workout_rig.EXERCISES))
def test_every_exercise_sends_a_looping_movement(exercise):
    pose = workout_rig.pose_data(BUILD, exercise)
    n = len(pose["segs"])
    assert pose["view"] in ("side", "front") and pose["dur"] > 0
    assert len(pose["frames"]) == workout_rig.FRAMES                     # one cycle, no repeated last frame
    assert all(len(f) == n * 4 + 3 for f in pose["frames"])             # segments, head x/y, lift
    assert pose["segs"][pose["head_after"]][0] == "torso"
    assert all(re.fullmatch(r"#[0-9A-Fa-f]{6}", c) for _k, _w, c in pose["segs"])
    assert n <= 14                                                       # the shader's limit
    ys = [v for f in pose["frames"] for v in f[1:n * 4:2]]
    assert max(ys) <= workout_rig.GROUND + 3                             # feet stay on the ground


def test_the_athlete_wears_the_avatars_colours():
    pose = workout_rig.pose_data(BUILD, "squat")
    torso = pose["segs"][pose["head_after"]][2]
    assert torso == workout_rig.colours(BUILD)[0]
    assert dict((k, c) for k, _w, c in pose["segs"])["foot"] == workout_rig.colours(BUILD)[2]


def test_each_scene_carries_what_webgl_needs():
    work = gl_info(mini_scene.scene(BUILD, "pushups", "10 push-ups", 10))
    assert (work["kind"], list(work["poses"]), work["size"]) == ("work", ["pushup"], 128)
    walk = gl_info(mini_scene.walk_scene(BUILD, "Walk 1,000 steps", 15, 300, 1000))
    assert walk["kind"] == "walk" and set(walk["poses"]) == {"walk", "stand"} and len(walk["course"]) == 6
    assert gl_info(mini_scene.walk_finish(BUILD, 1000))["kind"] == "finish"
    cheer = gl_info(mini_scene.celebration(BUILD))
    assert cheer["kind"] == "cheer" and cheer["poses"]["cheer"]["view"] == "front"
    # The SVG scene is still all there underneath, as the fallback
    assert "<svg" in str(mini_scene.scene(BUILD, "pushups", "10 push-ups", 10))


def test_only_the_challenges_page_loads_the_webgl_script(tmp_path):
    import app as A
    import data
    import db
    from werkzeug.security import generate_password_hash
    path = str(tmp_path / "s.sqlite3")
    conn = db.connect(path)
    db.create_tables(conn)
    uid = data._insert_user(conn, "amal", "Amal Khan", "student", "Grade 9A", "teen_13_17", generate_password_hash("4826"))
    conn.commit()
    data.start_mini(conn, uid, "squats_15")
    web = A.create_app()
    web.config.update(TESTING=True, DATABASE=path)
    c = web.test_client()
    with c.session_transaction() as s:
        s["user_id"], s["csrf"] = uid, "x"
    page = c.get("/challenges").get_data(as_text=True)
    assert "js/scene-gl.js" in page and 'data-gl="' in page
    assert "js/scene-gl.js" not in c.get("/log").get_data(as_text=True)
    assert c.get("/static/js/scene-gl.js").status_code == 200
