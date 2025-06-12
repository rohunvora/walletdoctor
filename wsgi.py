#!/usr/bin/env python3
"""
WSGI entry point for gunicorn
"""
from web_app import app

if __name__ == "__main__":
    app.run() 