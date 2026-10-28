"""Send sign-up codes by email through Gmail (PythonAnywhere allows Gmail on free accounts).

Set STRIDEBOARD_GMAIL_USER and STRIDEBOARD_GMAIL_APP_PASSWORD (a Google "app password",
not the normal password). STRIDEBOARD_MAIL_DEBUG=1 prints codes to the log instead
(for testing on a laptop only).
"""
import logging
import os
import smtplib
from email.message import EmailMessage

import config

log = logging.getLogger(__name__)


def debug_mode():
    return os.environ.get("STRIDEBOARD_MAIL_DEBUG") == "1"


def gmail_login():
    """(address, app password), read when needed, so the WSGI file can set them in any order."""
    user = os.environ.get("STRIDEBOARD_GMAIL_USER", "").strip() or config.GMAIL_USER
    password = os.environ.get("STRIDEBOARD_GMAIL_APP_PASSWORD", "").replace(" ", "") or config.GMAIL_APP_PASSWORD
    return user, password


def ready():
    """Can the site send email codes?"""
    user, password = gmail_login()
    return debug_mode() or bool(user and password)


WORDING = {
    "signup": ("{code} is your StrideBoard code",
               "Your StrideBoard sign-up code is: {code}\n\nType it on the sign-up page within {mins} minutes.\n\n"
               "If you didn't try to make a StrideBoard account, you can ignore this email.\n"),
    "link": ("{code} is your StrideBoard code",
             "Your code to add this email to your StrideBoard account is: {code}\n\n"
             "Type it on the Settings page within {mins} minutes.\n\n"
             "If you didn't ask for this, you can ignore this email.\n"),
    "reset": ("{code} is your StrideBoard PIN reset code",
              "Someone asked to reset the PIN of the StrideBoard account that uses this email.\n\n"
              "Your code is: {code}\n\nType it on the 'Forgot your PIN?' page within {mins} minutes.\n\n"
              "If it wasn't you, ignore this email. Your PIN stays the same.\n"),
}


def send_code(to, code, purpose="signup"):
    """Email a 6-digit code. Raises ValueError if it couldn't be sent."""
    if debug_mode():
        log.warning("MAIL DEBUG: %s code for %s is %s", purpose, to, code)
        print(f"MAIL DEBUG: {purpose} code for {to} is {code}", flush=True)
        return
    user, password = gmail_login()
    subject, body = WORDING[purpose]
    msg = EmailMessage()
    msg["Subject"] = subject.format(code=code)
    msg["From"] = f"StrideBoard <{user}>"
    msg["To"] = to
    msg.set_content(body.format(code=code, mins=config.CODE_MINUTES))
    try:
        with smtplib.SMTP("smtp.gmail.com", 587, timeout=20) as smtp:
            smtp.starttls()
            smtp.login(user, password)
            smtp.send_message(msg)
    except (smtplib.SMTPException, OSError):
        log.exception("could not send sign-up email")
        raise ValueError("we couldn't send the email just now. Check the address and try again") from None


def send_backup(filename, data):
    """Email a database backup to the site's own Gmail (an off-site copy). Returns the address."""
    user, password = gmail_login()
    if not (user and password):
        raise ValueError("Gmail isn't set up, so the backup wasn't emailed")
    msg = EmailMessage()
    msg["Subject"] = f"StrideBoard weekly backup ({filename})"
    msg["From"] = f"StrideBoard <{user}>"
    msg["To"] = user
    if data is None:   # too big for Gmail: a reminder instead
        msg.set_content("This week's StrideBoard backup is too big to attach to an email. Please log in, "
                        "open Admin > Backups and click Download a backup to keep a copy on your computer.\n")
    else:
        msg.set_content("This week's copy of the StrideBoard database is attached, encrypted. Keep this "
                        "email for up to 4 weeks: if anything goes wrong, the site can be restored from it "
                        "(see README, 'Backups and restoring').\n")
        msg.add_attachment(data, maintype="application", subtype="octet-stream", filename=filename)
    try:
        with smtplib.SMTP("smtp.gmail.com", 587, timeout=60) as smtp:
            smtp.starttls()
            smtp.login(user, password)
            smtp.send_message(msg)
    except (smtplib.SMTPException, OSError):
        log.exception("could not email the backup")
        raise ValueError("Gmail didn't accept the email just now") from None
    return user


def send_parent_request(to, child_name, link):
    """Ask a parent to approve their under-13's StrideBoard account. Raises ValueError if not sent."""
    subject = f"Please approve {child_name}'s StrideBoard account"
    body = (f"Hello,\n\n{child_name} signed up for StrideBoard, the school step-count game, and said "
            f"they are under 13. Their account stays switched off until you say yes.\n\n"
            f"Open this link to see what StrideBoard collects and to approve or decline:\n{link}\n\n"
            "StrideBoard only stores your child's name, class, daily step total and anything they "
            "choose to log (water, mood, activities). No location, no photos, no ads, never sold.\n\n"
            f"Keep this email: the same link lets you withdraw consent and delete the account at any "
            f"time. If nobody answers within {config.PARENT_WAIT_DAYS} days, the account is deleted.\n\n"
            "If you don't know what this is, you can ignore this email.\n")
    if debug_mode():
        log.warning("MAIL DEBUG: parent link for %s: %s", to, link)
        print(f"MAIL DEBUG: parent link for {to}: {link}", flush=True)
        return
    user, password = gmail_login()
    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = f"StrideBoard <{user}>"
    msg["To"] = to
    msg.set_content(body)
    try:
        with smtplib.SMTP("smtp.gmail.com", 587, timeout=20) as smtp:
            smtp.starttls()
            smtp.login(user, password)
            smtp.send_message(msg)
    except (smtplib.SMTPException, OSError):
        log.exception("could not send the parent email")
        raise ValueError("we couldn't email your parent just now. Check their address and try again") from None
