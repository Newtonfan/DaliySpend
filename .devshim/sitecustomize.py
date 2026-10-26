"""Development shim for running this project inside the DSH Windows sandbox.

Python 3.13 on Windows maps the ``mode`` argument of :func:`os.mkdir` onto an
explicit "owner only" NTFS ACL.  ``tempfile.mkdtemp()`` creates its directory
with ``mode=0o700``, so every temporary directory it creates is inaccessible
to the confined (restricted-token) process that just created it.  The result
is a cascade of ``PermissionError [Errno 13]`` failures from pip, venv,
pytest and anything else that needs scratch space.

Forcing ``0o777`` restores the inherited workspace ACL, which is what plain
Python 3.12 and earlier produce for the same call.

This file is only wired up by ``scripts/dev.ps1`` (which puts this directory
on ``PYTHONPATH``).  It is never part of the application and can be deleted
once the project runs outside the sandbox.
"""

from __future__ import annotations

import os

_real_mkdir = os.mkdir


def mkdir(path, mode=0o777, *, dir_fd=None):
    if dir_fd is None:
        return _real_mkdir(path, 0o777)
    return _real_mkdir(path, 0o777, dir_fd=dir_fd)


os.mkdir = mkdir
