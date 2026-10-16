"""A tiny Flask app with only the database and /api/steps (no web pages).

Agent 1 uses it to test, and it lets the server go online so Agent 2 can test
the phone apps before Agent 3's app.py exists. It does NOT replace app.py.

    flask --app devapp run                  run locally on http://127.0.0.1:5000
    flask --app devapp show-token student1  print a test user's phone token
    flask --app devapp update-goals         recompute adaptive goals now
"""
from flask import Flask

import api
import db


def create_app():
    app = Flask(__name__)
    db.init_app(app)
    app.register_blueprint(api.bp)

    @app.get("/")
    def home():
        return "StrideBoard API is running. The website is coming soon."

    return app


app = create_app()
