# gunicorn_coverage.py
# Gunicorn server hooks for proper coverage collection in worker processes.
#
# Based on Gemini research recommendations:
# - post_fork: Log worker startup (coverage already started via sitecustomize.py)
# - worker_exit: CRITICAL - Save coverage data before worker dies
#
# Usage: gunicorn -c gunicorn_coverage.py app:app

import os


def post_fork(server, worker):
    """
    Called immediately after a worker has been forked.

    At this point, sitecustomize.py has already started coverage in this process.
    We just log for debugging purposes.
    """
    server.log.info(f"[coverage] Worker spawned (pid: {worker.pid})")


def worker_exit(server, worker):
    """
    Called just before a worker exits.

    CRITICAL: This is our only chance to save the worker's coverage data.
    Without this hook, all coverage collected in the worker is lost when it dies.
    """
    try:
        import coverage

        # Get the active coverage instance for THIS process
        # (started by sitecustomize.py via coverage.process_startup())
        cov = coverage.Coverage.current()

        if cov:
            cov.stop()
            cov.save()  # Writes to /dev/shm/.coverage.<hostname>.<pid>.<random>
            server.log.info(f"[coverage] Worker {worker.pid} coverage saved")
        else:
            server.log.warning(f"[coverage] No active coverage for worker {worker.pid}")

    except ImportError:
        pass  # coverage not installed
    except Exception as e:
        server.log.error(f"[coverage] Failed to save coverage for worker {worker.pid}: {e}")


def on_exit(server):
    """
    Called just before the master process exits.

    We save the master's coverage data here too.
    """
    try:
        import coverage
        cov = coverage.Coverage.current()
        if cov:
            cov.stop()
            cov.save()
            server.log.info("[coverage] Master process coverage saved")
    except Exception as e:
        server.log.error(f"[coverage] Failed to save master coverage: {e}")
