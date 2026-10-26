"""Serve the built Vue SPA from Flask.

Keeping the frontend and the API behind one origin is what makes the session
cookie and the CSRF token work without any CORS configuration, both in
development (Vite proxies ``/api``) and in production (Flask serves ``dist``).
"""

from __future__ import annotations

from pathlib import Path

from flask import Flask, abort, send_from_directory

from .config import FRONTEND_DIST

ASSET_CACHE_SECONDS = 60 * 60 * 24 * 365


def register_frontend(app: Flask, dist: Path | None = None) -> bool:
    """Mount the SPA when a build exists; return whether it was mounted."""
    root = dist or FRONTEND_DIST
    index_file = root / "index.html"
    if not index_file.is_file():
        app.logger.info("Frontend build not found at %s; serving API only", root)
        return False
    if "spa" in app.view_functions:
        return True

    @app.get("/")
    @app.get("/<path:asset_path>")
    def spa(asset_path: str = ""):  # type: ignore[no-untyped-def]
        if asset_path.startswith("api/"):
            abort(404)
        if asset_path:
            candidate = root / asset_path
            if candidate.is_file():
                cache = ASSET_CACHE_SECONDS if asset_path.startswith("assets/") else 0
                return send_from_directory(root, asset_path, max_age=cache)
        return send_from_directory(root, "index.html", max_age=0)

    app.logger.info("Serving frontend build from %s", root)
    return True
