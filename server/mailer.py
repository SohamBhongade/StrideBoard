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


def ready():
    """Can the site send sign-up codes?"""
    return debug_mode() or bool(config.GMAIL_USER and config.GMAIL_APP_PASSWORD)


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
    subject, body = WORDING[purpose]
    msg = EmailMessage()
    msg["Subject"] = subject.format(code=code)
    msg["From"] = f"StrideBoard <{config.GMAIL_USER}>"
    msg["To"] = to
    msg.set_content(body.format(code=code, mins=config.CODE_MINUTES))
    try:
        with smtplib.SMTP("smtp.gmail.com", 587, timeout=20) as smtp:
            smtp.starttls()
            smtp.login(config.GMAIL_USER, config.GMAIL_APP_PASSWORD)
            smtp.send_message(msg)
    except (smtplib.SMTPException, OSError):
        log.exception("could not send sign-up email")
        raise ValueError("we couldn't send the email just now. Check the address and try again") from None
