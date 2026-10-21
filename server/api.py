"""POST /api/steps: where the iPhone Shortcut and the Android app send steps.

In app.py:  import api;  app.register_blueprint(api.bp)

Request (JSON):
    {"token": "<api_token>", "date": "2026-10-14", "steps": 8423, "source": "ios_shortcut"}
"date" and "source" may be left out: they mean today (Dubai time) and the iPhone Shortcut.
Replies:
    200 {"ok": true, "weekly_total": 41230, "tier": "Silver", "message": "..."}
    400 {"ok": false, "error": "<readable reason>"}
    401 {"ok": false, "error": "invalid token"}
    413 {"ok": false, "error": "request is too large"}   (over 16 KB)

Every reply also has "message": one plain sentence the iPhone Shortcut shows as a
notification, so people see "Synced 6,350 steps" instead of raw JSON.

The token is a password: this file never logs it or sends it back.
"""
import json

from flask import Blueprint, jsonify, request

import config
import data
from db import get_db

bp = Blueprint("api", __name__, url_prefix="/api")


def _reply(status, **body):
    response = jsonify(body)
    response.status_code = status
    response.headers["Cache-Control"] = "no-store"
    return response


FRIENDLY = {
    401: "This phone isn't linked to an account. Open StrideBoard, log in, "
         "and tap Sync from Apple Health.",
    403: "Your StrideBoard account is timed out or banned, so steps aren't being saved.",
    413: "Something went wrong sending your steps. Please try again.",
}


def _error(status, message):
    friendly = FRIENDLY.get(status) or f"Steps not saved: {message}."
    return _reply(status, ok=False, error=message, message=friendly)


@bp.post("/steps")
def upload_steps():
    # 1. Size limit: read at most 16 KB (+1 byte to notice anything bigger).
    limit = config.MAX_UPLOAD_BYTES
    if request.content_length is not None and request.content_length > limit:
        return _error(413, "request is too large")
    raw = request.stream.read(limit + 1)
    if len(raw) > limit:
        return _error(413, "request is too large")

    # 2. The body must be a JSON object.
    try:
        body = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, ValueError):
        return _error(400, "body must be JSON")
    if not isinstance(body, dict):
        return _error(400, "body must be a JSON object")

    # 3. Who is it? A missing or wrong token gets the same answer.
    conn = get_db()
    user = data.get_user_by_token(conn, body.get("token"))
    if user is None:
        return _error(401, "invalid token")
    if data.block_status(conn, user["id"]):
        return _error(403, "this account is timed out or banned")

    # 4. Check and save. data.save_steps raises ValueError with a readable reason.
    try:
        # The iPhone Shortcut can leave out "date" (means today) and "source" (means iPhone),
        # so it only has to send the token and today's steps.
        result = data.save_steps(conn, user["id"], body.get("date"),
                                 body.get("steps"), body.get("source") or "ios_shortcut")
    except ValueError as exc:
        return _error(400, str(exc))

    message = (f"Synced {result['steps']:,} steps. "
               f"This week: {result['weekly_total']:,} ({result['tier']}).")
    return _reply(200, ok=True, weekly_total=result["weekly_total"], tier=result["tier"],
                  message=message)
