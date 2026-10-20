"""The Gmail settings are read when needed, so the WSGI file can set them after importing the app."""
import mailer


def test_ready_reads_settings_late(monkeypatch):
    monkeypatch.delenv("STRIDEBOARD_MAIL_DEBUG", raising=False)
    monkeypatch.delenv("STRIDEBOARD_GMAIL_USER", raising=False)
    monkeypatch.delenv("STRIDEBOARD_GMAIL_APP_PASSWORD", raising=False)
    monkeypatch.setattr(mailer.config, "GMAIL_USER", "")
    monkeypatch.setattr(mailer.config, "GMAIL_APP_PASSWORD", "")
    assert not mailer.ready()
    monkeypatch.setenv("STRIDEBOARD_GMAIL_USER", "strideboard.alsout@gmail.com")
    monkeypatch.setenv("STRIDEBOARD_GMAIL_APP_PASSWORD", "abcd efgh ijkl mnop")
    assert mailer.ready()
    assert mailer.gmail_login() == ("strideboard.alsout@gmail.com", "abcdefghijklmnop")
