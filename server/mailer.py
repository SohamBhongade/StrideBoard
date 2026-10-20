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


def send_code(to, code):
    """Email a 6-digit sign-up code. Raises ValueError if it couldn't be sent."""
    if debug_mode():
        log.warning("MAIL DEBUG: sign-up code for %s is %s", to, code)
        print(f"MAIL DEBUG: sign-up code for {to} is {code}", flush=True)
        return
    msg = EmailMessage()
    msg["Subject"] = f"{code} is your StrideBoard code"
    msg["From"] = f"StrideBoard <{config.GMAIL_USER}>"
    msg["To"] = to
    msg.set_content(
        f"Your StrideBoard sign-up code is: {code}\n\n"
        f"Type it on the sign-up page within {config.CODE_MINUTES} minutes.\n\n"
        "If you didn't try to make a StrideBoard account, you can ignore this email.\n")
    try:
        with smtplib.SMTP("smtp.gmail.com", 587, timeout=20) as smtp:
            smtp.starttls()
            smtp.login(config.GMAIL_USER, config.GMAIL_APP_PASSWORD)
            smtp.send_message(msg)
    except (smtplib.SMTPException, OSError):
        log.exception("could not send sign-up email")
        raise ValueError("we couldn't send the email just now. Check the address and try again") from None
