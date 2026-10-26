"""WSGI entry point: ``flask --app wsgi run`` or ``waitress-serve wsgi:app``."""

from __future__ import annotations

from app import create_app

app = create_app()
