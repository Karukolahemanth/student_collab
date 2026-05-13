"""
Vercel serverless entry point.
Vercel may route requests through this file OR through app.py at the root.
Both import the same app object so behaviour is identical.
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from app import app  # noqa: F401
