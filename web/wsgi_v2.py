#!/usr/bin/env python3
"""
WSGI entry point for gunicorn - V2 with annotations
"""
from web_app_v2 import app

if __name__ == "__main__":
    app.run() 