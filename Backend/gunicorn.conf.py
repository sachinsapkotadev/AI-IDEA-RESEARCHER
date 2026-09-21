"""Gunicorn configuration for production deployment."""

import os

bind = f"0.0.0.0:{os.environ.get('PORT', '8000')}"
worker_class = "uvicorn.workers.UvicornWorker"
workers = int(os.environ.get("WEB_CONCURRENCY", "2"))
timeout = 120
keepalive = 5
errorlog = "-"
accesslog = "-"
loglevel = os.environ.get("LOG_LEVEL", "info").lower()
