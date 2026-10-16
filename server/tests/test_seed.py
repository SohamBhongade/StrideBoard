"""Tests for seed.py on a temporary database file."""
import data
import db
import seed


def count_users(path):
    conn = db.connect(path)
    n = conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
    conn.close()
    return n


def test_full_seed(tmp_path, capsys):
    path = tmp_path / "s.sqlite3"
    assert seed.main(["--database", str(path), "--admin-pin", "4826"]) == 0
    out = capsys.readouterr().out
    assert "PIN: 4826" in out and "FAKE" in out

    conn = db.connect(path)
    roles = dict(conn.execute("SELECT role, COUNT(*) FROM users GROUP BY role").fetchall())
    assert roles == {"admin": 1, "teacher": 5, "student": 10}
    assert data.authenticate(conn, "admin", "4826")["role"] == "admin"
    assert data.authenticate(conn, "student3", "1234") is not None
    sources = {r[0] for r in conn.execute("SELECT DISTINCT source FROM steps")}
    assert sources == {"ios_shortcut", "android_app", "manual"}
    days = conn.execute("SELECT COUNT(DISTINCT date) FROM steps").fetchone()[0]
    assert days == 14
    assert conn.execute("SELECT COUNT(*) FROM moods").fetchone()[0] > 50
    kinds = {r[0] for r in conn.execute("SELECT kind FROM challenges")}
    assert kinds == {"department", "school_distance"}
    assert conn.execute("SELECT COUNT(*) FROM badges").fetchone()[0] > 0
    # the impact page has data before and during
    stats = data.impact_stats(conn)
    assert stats["avg_before"] and stats["avg_during"]
    conn.close()


def test_refuses_when_users_exist(tmp_path, capsys):
    path = str(tmp_path / "s.sqlite3")
    seed.main(["--database", path, "--admin-only"])
    assert seed.main(["--database", path]) == 1
    assert "Nothing was changed" in capsys.readouterr().out
    assert count_users(path) == 1


def test_bad_pin_checked_before_reset(tmp_path, capsys):
    path = str(tmp_path / "s.sqlite3")
    seed.main(["--database", path])
    assert seed.main(["--database", path, "--reset", "--admin-pin", "12"]) == 2
    assert count_users(path) == 16          # nothing deleted
    assert "PIN must be" in capsys.readouterr().out


def test_reset_and_admin_only(tmp_path):
    path = str(tmp_path / "s.sqlite3")
    seed.main(["--database", path])
    assert seed.main(["--database", path, "--reset", "--admin-only"]) == 0
    assert count_users(path) == 1


def test_random_admin_pin_is_six_digits(tmp_path, capsys):
    seed.main(["--database", str(tmp_path / "s.sqlite3"), "--admin-only"])
    out = capsys.readouterr().out
    pin = out.split("PIN: ")[1].split()[0]
    assert len(pin) == 6 and pin.isdigit()
