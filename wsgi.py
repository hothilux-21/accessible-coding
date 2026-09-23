"""Vercel entry point for AccessibleIDE."""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from accessible_ide import create_app

app = create_app()