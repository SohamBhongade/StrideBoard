"""Mini challenge scenes: each workout gets its own animated pose; walks keep the plain view."""
import pytest

import mini_scene


@pytest.mark.parametrize("track, pose", [("pushups", "pushup"), ("squats", "squat"),
                                         ("planks", "plank"), ("jumping_jacks", "jacks")])
def test_each_workout_has_a_scene_with_the_timer(track, pose):
    html = str(mini_scene.scene({"color": "color_lilac", "hat": "hat_cap"}, track, "10 push-ups", 10))
    assert f"ath-{pose}" in html and "data-mini-clock" in html and "10 PUSH-UPS" in html and "+10 EXP" in html


def test_walks_have_no_scene():
    assert str(mini_scene.scene({}, "steps", "Walk 1,000 steps", 15)) == ""


def test_names_are_escaped_and_celebration_draws():
    assert "<b>" not in str(mini_scene.scene({}, "squats", "<b>x</b>", 5))
    assert "ath-cheer" in str(mini_scene.celebration(None))


def test_walk_scene_puts_the_walker_at_the_last_checkpoint_reached():
    html = str(mini_scene.walk_scene({}, "Walk 2,500 steps", 35, 1200, 2500))
    assert 'data-reached="2"' in html and "1,200" in html and "2,500" in html   # 500 steps per checkpoint
    assert all(f">{n:,}<" in html for n in (500, 1000, 1500, 2000)) and "g-flag" in html
    assert 'data-reached="0"' in str(mini_scene.walk_scene({}, "Walk 1,000 steps", 15, 199, 1000))
    assert 'data-reached="1"' in str(mini_scene.walk_scene({}, "Walk 1,000 steps", 15, 200, 1000))
    assert "game-finish" in str(mini_scene.walk_finish({}, 1000))


def test_last_finished_walk(conn):
    from datetime import timedelta
    import data
    from conftest import TODAY, make_user, put_steps
    from test_mini_challenges import T0
    uid = make_user(conn)
    assert data.last_finished_walk(conn, uid, T0) is None
    put_steps(conn, uid, TODAY, 3000)
    data.start_mini(conn, uid, "walk_1000", T0)
    put_steps(conn, uid, TODAY, 4100)
    data.check_walks(conn, uid, T0 + timedelta(minutes=10))
    won = data.last_finished_walk(conn, uid, T0 + timedelta(minutes=11))
    assert won["label"] == "Walk 1,000 steps" and won["exp"] == 15 and won["amount"] == 1000
