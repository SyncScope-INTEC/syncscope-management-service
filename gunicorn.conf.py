"""
Gunicorn configuration for SyncScope Management Service
"""

import multiprocessing
import os

# Server socket
bind = f"0.0.0.0:{os.getenv('PORT', '8000')}"
backlog = 2048

# Worker processes
workers = int(os.getenv("GUNICORN_WORKERS", multiprocessing.cpu_count() * 2 + 1))
worker_class = "sync"
worker_connections = 1000
max_requests = 1000
max_requests_jitter = 50
preload_app = True
timeout = 30
keepalive = 2

# Restart workers after this many seconds to prevent memory leaks
max_worker_age = 3600

# Worker recycling
worker_tmp_dir = "/dev/shm"

# Logging
accesslog = "-"  # Log to stdout
errorlog = "-"  # Log to stderr
loglevel = os.getenv("LOG_LEVEL", "info")
access_log_format = '%(h)s %(l)s %(u)s %(t)s "%(r)s" %(s)s %(b)s "%(f)s" "%(a)s" %(D)s'

# Process naming
proc_name = "syncscope-management-service"

# Server mechanics
daemon = False
pidfile = None
user = None
group = None
tmp_upload_dir = None

# SSL (if needed)
# keyfile = None
# certfile = None


def when_ready(server):
    """Called just after the server is started."""
    server.log.info("SyncScope Management Service is ready to serve requests")


def worker_int(worker):
    """Called just after a worker exited on SIGINT or SIGQUIT."""
    worker.log.info("Worker received INT or QUIT signal")


def on_exit(server):
    """Called just before exiting."""
    server.log.info("SyncScope Management Service is shutting down")


def on_reload(server):
    """Called to recycle workers during a reload via SIGHUP."""
    server.log.info("SyncScope Management Service is reloading")


# Environment-specific overrides
if os.getenv("RAILWAY_ENVIRONMENT") == "production":
    workers = max(2, multiprocessing.cpu_count())
    max_requests = 2000
    timeout = 60
elif os.getenv("RAILWAY_ENVIRONMENT") in ["dev", "qa"]:
    workers = 2
    max_requests = 1500
    timeout = 45
else:  # development
    workers = 1
    reload = True
    timeout = 120