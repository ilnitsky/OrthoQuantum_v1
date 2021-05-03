import multiprocessing
from os import environ

cores = 1 if environ.get("DEBUG") else multiprocessing.cpu_count()
workers_per_core = 4.0

# Gunicorn config variables
loglevel = "info"
workers = int(workers_per_core * cores)
bind = "0.0.0.0:8050"

errorlog = "-"
capture_output = True
preload_app = True
# For debugging and testing
log_data = {
    "loglevel": loglevel,
    "workers": workers,
    "bind": bind,
    # Additional, non-gunicorn variables
    "workers_per_core": workers_per_core,
}
timeout = 600
graceful_timeout = 600