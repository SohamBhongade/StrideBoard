#!/usr/bin/env python3
"""
Tiny stand-in for StrideBoard's POST /api/steps, for testing the phone code before
Agent 1's real server is ready. Standard library only, no install needed.

    python3 fake_api.py                     # accepts the token "test-token"
    python3 fake_api.py --token abc123      # accepts your own test token
    python3 fake_api.py --port 5050

Then, on a phone on the same Wi-Fi, use a DEBUG build of the Android app with the address
http://<your-laptop-IP>:5050  (find the IP with `ipconfig` on Windows or `ifconfig` on Mac).

It follows the rules in the shared brief, but it is NOT the real server:
it keeps data in memory only, and weekly_total / tier are rough placeholders.
"""
import argparse
import json
from datetime import datetime, timedelta
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from zoneinfo import ZoneInfo

DUBAI = ZoneInfo("Asia/Dubai")
ALLOWED_SOURCES = {"ios_shortcut", "android_app", "manual"}
ARABIC_DIGITS = str.maketrans("٠١٢٣٤٥٦٧٨٩۰۱۲۳۴۵۶۷۸۹", "01234567890123456789")

STEPS = {}  # (date, source) -> steps   (one fake user)
VALID_TOKEN = "test-token"


def parse_steps(value):
    if isinstance(value, bool):
        raise ValueError("steps must be a number")
    if isinstance(value, str):
        value = value.strip().translate(ARABIC_DIGITS).replace(",", "")
    try:
        number = round(float(value))
    except (TypeError, ValueError):
        raise ValueError("steps must be a number")
    if not 0 <= number <= 100_000:
        raise ValueError("steps must be between 0 and 100,000")
    return number


def parse_date(value, today):
    if value in (None, ""):
        return today
    try:
        day = datetime.strptime(str(value), "%Y-%m-%d").date()
    except ValueError:
        raise ValueError("date must look like 2026-10-14")
    if day > today:
        raise ValueError("date cannot be in the future")
    if day < today - timedelta(days=7):
        raise ValueError("date cannot be more than 7 days ago")
    return day


class Handler(BaseHTTPRequestHandler):
    def _send(self, code, payload):
        body = json.dumps(payload).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if self.path in ("/", "/index.html"):
            rows = "".join(
                f"<tr><td>{d}</td><td>{s}</td><td>{n}</td></tr>"
                for (d, s), n in sorted(STEPS.items())
            )
            html = (
                "<!doctype html><meta name=viewport content='width=device-width'>"
                "<h2>StrideBoard fake API</h2><p>Uploads received:</p>"
                f"<table border=1 cellpadding=6><tr><th>date</th><th>source</th><th>steps</th></tr>{rows}</table>"
            ).encode()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(html)))
            self.end_headers()
            self.wfile.write(html)
        else:
            self._send(404, {"ok": False, "error": "not found"})

    def do_POST(self):
        if self.path != "/api/steps":
            return self._send(404, {"ok": False, "error": "not found"})
        try:
            length = int(self.headers.get("Content-Length", 0))
            data = json.loads(self.rfile.read(length) or b"{}")
            if not isinstance(data, dict):
                raise ValueError
        except ValueError:
            return self._send(400, {"ok": False, "error": "body must be JSON"})

        if data.get("token") != VALID_TOKEN:
            print("REJECTED: invalid token")  # never print the token itself
            return self._send(401, {"ok": False, "error": "invalid token"})

        today = datetime.now(DUBAI).date()
        try:
            day = parse_date(data.get("date"), today)
            steps = parse_steps(data.get("steps"))
            source = data.get("source")
            if source not in ALLOWED_SOURCES:
                raise ValueError("source must be one of: " + ", ".join(sorted(ALLOWED_SOURCES)))
        except ValueError as e:
            print(f"REJECTED: {e}")
            return self._send(400, {"ok": False, "error": str(e)})

        STEPS[(day.isoformat(), source)] = steps
        monday = today - timedelta(days=today.weekday())
        weekly = sum(n for (d, _), n in STEPS.items() if d >= monday.isoformat())
        print(f"ACCEPTED: {day} {steps} steps from {source}")
        return self._send(200, {"ok": True, "weekly_total": weekly, "tier": "Test"})

    def log_message(self, fmt, *args):
        pass  # keep the console clean (and token-free)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--port", type=int, default=5050)
    parser.add_argument("--token", default=VALID_TOKEN)
    args = parser.parse_args()
    VALID_TOKEN = args.token
    print(f"Fake StrideBoard API on http://0.0.0.0:{args.port}  (Ctrl+C to stop)")
    ThreadingHTTPServer(("0.0.0.0", args.port), Handler).serve_forever()
