"""
Vercel entry point.
Vercel looks for a file named api/index.py and expects an `app` (WSGI) object.
"""
import sys
import os

# Make the project root importable so we can import student_collab
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from student_collab import app  # noqa: F401 — Vercel uses this `app`
