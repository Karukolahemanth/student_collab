"""
Vercel serverless entry point.
Vercel looks for api/index.py and expects an `app` (WSGI) object.
"""
import sys
import os

# Add the parent directory (project root) to the Python path
# so that `app.py` at the root level can be imported correctly.
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from app import app  # noqa: F401 — Vercel uses this `app` WSGI object
