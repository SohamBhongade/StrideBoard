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
